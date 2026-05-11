"""
Main entry point for the assistant.

This file wires up all providers based on config.yaml and runs the main loop.
In simulation mode (Mac), it uses text input instead of a microphone.

Usage:
    python main.py              # Run with config.yaml settings
    python main.py --text       # Force text-input mode (no mic)
    python main.py --config /path/to/config.yaml  # Custom config
"""

import argparse
import platform
import shutil
import threading

from core.config import config
from core.logger import get_logger
from core.registry import get_provider, list_providers
from core.personality import personality_manager
from core.voice_router import VoiceRouter
from core.interfaces import WakeWordDetection
from core.pipeline import process_input
from core.intent_handler import is_sleep_mode, trigger_wake
from core.audio_focus import AudioFocusManager, AudioChannel
from ui.server import FaceUI
from ui.actions import handle_ui_action

# This import triggers provider auto-discovery via @register decorators
import providers  # noqa: F401

log = get_logger("main")


def _resolve_audio_provider() -> str | None:
    """
    Auto-detect the best audio provider for the current platform.

    Detection order:
      1. macOS → "coreaudio"
      2. Linux with pactl → "pulseaudio" (Jetson, desktop Linux, PipeWire compat)
      3. Linux with amixer → "alsa" (bare Pi, minimal Linux)
      4. None → no system audio control, fall back to mpv volume
    """
    if platform.system() == "Darwin":
        return "coreaudio"
    if shutil.which("pactl"):
        return "pulseaudio"
    if shutil.which("amixer"):
        return "alsa"
    return None


def build_assistant() -> dict:
    """
    Instantiate all providers based on config.yaml.

    Returns a dict of initialized provider instances, ready to use.
    """
    brain_cfg = config.get("brain", {})
    music_cfg = config.get("music", {})
    lights_cfg = config.get("lights", {})

    assistant = {
        "name": config["assistant"]["name"],
    }

    # Brain — always needed
    assistant["brain"] = get_provider(
        "brain",
        brain_cfg.get("provider", "ollama"),
        model=brain_cfg.get("model"),
        endpoint=brain_cfg.get("endpoint"),
    )

    # Music — optional but core
    try:
        assistant["music"] = get_provider(
            "music",
            music_cfg.get("provider", "youtube_music"),
        )
    except Exception as e:
        log.warning("Music provider not available (%s). Music features disabled.", e)
        assistant["music"] = None

    # Lights — optional
    try:
        if lights_cfg.get("devices"):
            assistant["lights"] = get_provider(
                "lights",
                lights_cfg.get("provider", "tuya"),
            )
        else:
            assistant["lights"] = None
            log.info("No light devices configured. Light features disabled.")
    except Exception as e:
        log.warning("Light provider not available (%s). Light features disabled.", e)
        assistant["lights"] = None

    # Audio output — system volume, device switching, Bluetooth
    audio_cfg = config.get("audio", {})
    audio_provider_name = audio_cfg.get("provider", "auto")
    if audio_provider_name == "auto":
        audio_provider_name = _resolve_audio_provider()

    if audio_provider_name:
        try:
            audio = get_provider("audio", audio_provider_name)
            if audio.is_available():
                assistant["audio"] = audio
                log.info("AudioOutputProvider: %s", audio_provider_name)
            else:
                assistant["audio"] = None
                log.info(
                    "Audio provider '%s' registered but not available on this platform.",
                    audio_provider_name,
                )
        except Exception as e:
            log.info("Audio provider not available (%s). Volume falls back to mpv.", e)
            assistant["audio"] = None
    else:
        assistant["audio"] = None
        log.info("No audio provider detected. Volume falls back to mpv.")

    # Bluetooth auto-reconnect daemon — keeps the preferred speaker
    # (e.g., Marshall Willen II on the Jetson) connected across power
    # cycles, range changes, and multi-point switches from other sources.
    # The daemon ALSO runs the device resolver every tick: it consults
    # audio.output_priority + audio.input_priority + the persistent
    # AudioOverrideStore and flips the default sink/source when needed.
    #
    # The daemon spawns when EITHER (a) a preferred BT mac is configured,
    # OR (b) the resolver has something to do (audio provider + priority
    # lists). Both flavours coexist on the same 30s tick.
    bt_cfg = audio_cfg.get("bluetooth", {}) or {}
    bt_mac = (bt_cfg.get("preferred_mac") or "").strip()
    output_priority = audio_cfg.get("output_priority", []) or []
    input_priority = audio_cfg.get("input_priority", []) or []
    audio = assistant.get("audio")

    # Override store — persistent user-pinned device choice. Stored next
    # to data/event_triggers.json so all runtime state lives under
    # assistant/data/. Mirrors trigger_state.py's path resolution.
    from core.audio_override import AudioOverrideStore
    override_store = AudioOverrideStore()
    assistant["audio_override_store"] = override_store

    wants_bt = bool(bt_mac) and audio is not None and hasattr(audio, "bluetooth_pair")
    wants_resolver = audio is not None and (bool(output_priority) or bool(input_priority))

    if wants_bt or wants_resolver:
        try:
            from core.audio_session import AudioSessionManager
            session_mgr = AudioSessionManager(
                preferred_mac=bt_mac,
                device_name=bt_cfg.get("device_name", "") or "",
                reconnect_interval_s=int(bt_cfg.get("reconnect_interval_s", 30) or 30),
                auto_reconnect=bool(bt_cfg.get("auto_reconnect", True)),
                audio_provider=audio,
                output_priority=output_priority,
                input_priority=input_priority,
                override_store=override_store,
            )
            session_mgr.start()
            assistant["audio_session"] = session_mgr
            # Stop the daemon cleanly on process exit. Modeled after the
            # mDNS unregister pattern below — we DON'T disconnect the
            # speaker (that would break "Jetson reboots, song picks up
            # again" UX), we just stop the polling thread.
            try:
                import atexit
                atexit.register(session_mgr.stop)
            except Exception:
                pass
        except Exception as e:
            log.warning(
                "AudioSession: failed to start (%s). "
                "Bluetooth auto-reconnect AND device resolver disabled.", e,
            )
            assistant["audio_session"] = None
    else:
        assistant["audio_session"] = None
        if not bt_mac and not (output_priority or input_priority):
            log.debug(
                "AudioSession: no preferred_mac and no priority lists in config — "
                "daemon inert.",
            )
        elif audio is None:
            log.debug("AudioSession: no audio provider — daemon inert.")
        elif bt_mac and not hasattr(audio, "bluetooth_pair"):
            log.debug("AudioSession: audio provider lacks Bluetooth methods — auto-reconnect disabled.")

    # Voice (TTS) — smart routing per personality with fallback
    # VoiceRouter handles: preferred provider → fallback → text-only
    assistant["voice_router"] = VoiceRouter()

    # Ears (STT) — optional, needed for voice mode
    # IMPORTANT: load BEFORE warming up the LLM. On Jetson (8GB shared NvMap),
    # Whisper-on-CUDA wants ~250MB and the LLM wants ~2GB. Allocating Whisper's
    # small chunk first leaves a clean ~6GB block for the LLM. Reverse order
    # fragments NvMap and the LLM's per-request KV cache allocations start
    # failing mid-request ("llama runner process has terminated").
    ears_cfg = config.get("ears", {})
    try:
        assistant["ears"] = get_provider(
            "ears",
            ears_cfg.get("provider", "faster_whisper"),
        )
    except Exception as e:
        log.info("Ears (STT) not available (%s). Voice input disabled, text mode only.", e)
        assistant["ears"] = None

    # Now that Whisper has its NvMap chunk (or didn't need one on CPU),
    # warm up the LLM. Catches an OllamaBrainProvider with a deferred warm_up();
    # other brain providers may not implement it — that's fine, skip silently.
    if hasattr(assistant["brain"], "warm_up"):
        try:
            assistant["brain"].warm_up()
        except Exception as e:
            log.warning("Brain warm-up failed: %s. First request will be slow.", e)

    # Eager-load the active personality's voice provider. Why now, after the
    # LLM warm-up: on Jetson all three (Whisper, Ollama, Kokoro) live in the
    # shared NvMap pool. Loading order: small ↑ large is the safe sequence —
    # Whisper (~250MB) → Ollama KV cache (variable, ~2-3GB) → Kokoro
    # (~350MB). Lazy-loading Kokoro on the first voice request fragmented
    # NvMap on dev hardware AND added ~3.5s to the first response. With
    # eager loading + a one-shot warmup synth, the first voice call hits
    # steady-state TTS latency (~0.7s for a typical sentence on Ampere) from
    # the very first request.
    try:
        from core.personality import personality_manager
        active = personality_manager.active
        provider_name = getattr(active, "voice_provider", None) or \
                        config.get("voice", {}).get("fallback_provider", "kokoro")
        # Touch the provider to force model load + warmup.
        provider = assistant["voice_router"]._get_provider(provider_name)
        if provider is None:
            log.warning("Voice provider '%s' not loaded. First voice call will be slow.", provider_name)
    except Exception as e:
        log.warning("Voice provider eager-load failed: %s", e)

    # Also eager-load the chat-fast English TTS provider (typically Piper).
    # Without this, the first English chat reply pays a one-time ~2s cost
    # loading the Piper ONNX model + warming the voice. With it, the first
    # chat reply hits steady-state synth latency immediately.
    fast_provider_name = config.get("voice", {}).get("fast_voice_provider", "piper")
    fast_voice_model = config.get("voice", {}).get("fast_voice_model", "en_US-amy-low")
    if fast_provider_name and fast_provider_name != provider_name:
        try:
            fast_provider = assistant["voice_router"]._get_provider(fast_provider_name)
            if fast_provider:
                # Warm the actual voice model (loading + first inference)
                try:
                    _ = fast_provider.speak("warm up", voice_model=fast_voice_model)
                    log.info("Fast voice provider '%s' warmed (model=%s).",
                             fast_provider_name, fast_voice_model)
                except Exception as e:
                    log.warning("Fast voice provider warmup failed: %s", e)
        except Exception as e:
            log.info("Fast voice provider '%s' not loaded: %s", fast_provider_name, e)

    # Memory — interaction logging and recall
    memory_cfg = config.get("memory", {})
    if memory_cfg.get("enabled", True):
        try:
            assistant["memory"] = get_provider(
                "memory",
                memory_cfg.get("provider", "sqlite"),
            )
        except Exception as e:
            log.warning("Memory provider not available (%s). Memory features disabled.", e)
            assistant["memory"] = None
    else:
        assistant["memory"] = None
        log.info("Memory disabled in config.")

    # Inject recent conversation context into LLM system prompt
    if assistant.get("memory"):
        try:
            from providers.brain.ollama import set_conversation_context
            set_conversation_context(assistant["memory"])
        except Exception as e:
            log.debug("Could not set conversation context: %s", e)

    # Knowledge — optional, needs internet + library installed
    # This is the "internet-enhanced" layer. Without it, the assistant still works
    # perfectly for all local features. With it, the LLM can answer questions about
    # current events, news, and real-time information.
    knowledge_cfg = config.get("knowledge", {})
    if knowledge_cfg.get("enabled", True):
        try:
            assistant["knowledge"] = get_provider(
                "knowledge",
                knowledge_cfg.get("provider", "duckduckgo"),
            )
        except Exception as e:
            log.info(
                "Knowledge provider not available (%s). "
                "Factual questions will use LLM knowledge only.", e,
            )
            assistant["knowledge"] = None
    else:
        assistant["knowledge"] = None
        log.info("Knowledge provider disabled in config.")

    # Quiz — LLM-generated trivia with personality-flavored hosting
    quiz_cfg = config.get("quiz", {})
    if quiz_cfg.get("provider", "trivia"):
        try:
            from providers.quiz.trivia import TriviaQuizProvider
            quiz = TriviaQuizProvider(brain=assistant["brain"])
            assistant["quiz"] = quiz

            # Register with intent_handler so prefilter can check is_active()
            from core.intent_handler import set_quiz_provider
            set_quiz_provider(quiz)

            log.info("Quiz provider ready.")
        except Exception as e:
            log.info("Quiz provider not available (%s). Quiz features disabled.", e)
            assistant["quiz"] = None
    else:
        assistant["quiz"] = None

    # Timer/Alarm manager — background scheduling with persistent alarms
    try:
        from providers.timer.manager import TimerManager

        def _on_timer_fire(entry):
            """Called when a timer/alarm fires — speak + broadcast to dashboard."""
            face_ui = assistant.get("face_ui")
            voice_router = assistant.get("voice_router")
            lights = assistant.get("lights")

            # Build the spoken message
            if entry.type == "alarm":
                label_str = f" — {entry.label}" if entry.label and entry.label != "Alarm" else ""
                message = f"Alarm{label_str}! Time to wake up!"

                # Wake-up alarm: gradually increase light brightness
                if lights and entry.label.lower() in ("wake up", "alarm", "morning"):
                    sleep_cfg = config.get("sleep_mode", {})
                    target_brightness = sleep_cfg.get("wake_lights_brightness", 50)
                    def _gradual_lights():
                        import time as _time
                        try:
                            lights.turn_on()
                            # Ramp up over 5 minutes (or less if brightness is low)
                            steps = 10
                            step_delay = 30  # 30s between steps = 5 min total
                            for i in range(1, steps + 1):
                                brightness = int((i / steps) * target_brightness)
                                lights.set_brightness(brightness)
                                # Warm color at start, neutral at end
                                if i <= steps // 2:
                                    lights.set_color("#FF8C00")  # warm orange
                                _time.sleep(step_delay)
                        except Exception as e:
                            log.warning("Gradual wake lights failed: %s", e)
                    threading.Thread(target=_gradual_lights, name="wake-lights", daemon=True).start()
            else:
                label_str = f" — {entry.label}" if entry.label and entry.label != "Timer" else ""
                message = f"Timer done{label_str}!"

            # Broadcast to dashboard
            if face_ui:
                face_ui.timer_fired(entry.to_dict())
                face_ui.set_timers(assistant["timer_manager"].list_active())

            # Speak the alert
            if voice_router:
                try:
                    if face_ui:
                        face_ui.show_transcript(message, role="assistant")
                    voice_router.speak(message)
                except Exception as e:
                    log.warning("Timer fire TTS failed: %s", e)
            else:
                print(f"\n*** {message} ***\n")

        timer_mgr = TimerManager(on_fire=_on_timer_fire)
        timer_mgr.start()
        assistant["timer_manager"] = timer_mgr
        log.info("TimerManager ready.")
    except Exception as e:
        log.info("TimerManager not available (%s). Timer/alarm features disabled.", e)
        assistant["timer_manager"] = None

    # Weather — Open-Meteo (free, no API key, local-first with cache)
    weather_cfg = config.get("weather", {})
    if weather_cfg.get("provider", "openmeteo"):
        try:
            from providers.weather.openmeteo import OpenMeteoWeatherProvider
            assistant["weather"] = OpenMeteoWeatherProvider()
            log.info("Weather provider ready (Open-Meteo).")
        except Exception as e:
            log.info("Weather provider not available (%s). Weather features disabled.", e)
            assistant["weather"] = None
    else:
        assistant["weather"] = None

    # Ambient sounds — background audio for sleep/relaxation (rain, white noise, etc.)
    try:
        from providers.ambient.sounds import AmbientSoundProvider
        assistant["ambient"] = AmbientSoundProvider()
        log.info("AmbientSoundProvider ready.")
    except Exception as e:
        log.info("Ambient sound provider not available (%s). Ambient features disabled.", e)
        assistant["ambient"] = None

    # Reminders — persistent scheduling with repeat support
    try:
        from providers.reminder.manager import ReminderManager

        def _on_reminder_fire(reminder):
            """Called when a reminder fires — speak + broadcast to dashboard."""
            face_ui_ref = assistant.get("face_ui")
            voice_router_ref = assistant.get("voice_router")

            message = f"Reminder: {reminder['text']}"

            if face_ui_ref:
                face_ui_ref.show_reminder(reminder)
                face_ui_ref.show_transcript(message, role="assistant")

            if voice_router_ref:
                try:
                    voice_router_ref.speak(message)
                except Exception as e:
                    log.warning("Reminder fire TTS failed: %s", e)
            else:
                print(f"\n*** {message} ***\n")

        reminder_mgr = ReminderManager(on_fire=_on_reminder_fire)
        reminder_mgr.start()
        assistant["reminder"] = reminder_mgr
        log.info("ReminderManager ready.")
    except Exception as e:
        log.info("ReminderManager not available (%s). Reminder features disabled.", e)
        assistant["reminder"] = None

    # Face UI — browser-based animated face (purely cosmetic, optional)
    face_ui = FaceUI(port=config.get("ui", {}).get("port", 8765))
    face_ui.start()
    assistant["face_ui"] = face_ui

    # Wire up browser → assistant action routing.
    # Uses a closure to capture the assistant dict. The callback runs in the
    # WebSocket thread, which is fine — handle_ui_action is thread-safe.
    face_ui.on_action = lambda action_data: handle_ui_action(assistant, action_data)

    # Sync FaceUI with the (possibly restored) active personality
    face_ui.set_personality(personality_manager.active.id)

    # Send personality list to dashboard so it can show a switcher
    face_ui.set_personalities([
        {"id": p.id, "display_name": p.display_name, "description": p.description, "avatar_type": p.avatar_type}
        for p in personality_manager.list()
    ])

    # Send settings schema to dashboard
    try:
        from core.config_manager import config_manager
        face_ui.send_settings(config_manager.get_settings())
    except Exception as e:
        log.debug("Could not send settings to dashboard: %s", e)

    # Companion App API — FastAPI server on a separate port.
    # Runs alongside FaceUI; the Flutter app talks to this.
    api_cfg = config.get("api", {})
    if api_cfg.get("enabled", True):
        try:
            from api.app import create_api, start_api_server
            api_app = create_api(assistant)
            if api_app:
                api_port = api_cfg.get("port", 8766)
                start_api_server(api_app, host="0.0.0.0", port=api_port)
                assistant["api"] = api_app

                # Wire FaceUI broadcasts → API WebSocket clients.
                # The API's WebSocket manager receives a copy of every
                # FaceUI broadcast and forwards it to connected Flutter apps.
                from api.ws import ws_manager
                face_ui.add_listener(ws_manager.forward_broadcast)

                # mDNS discovery — register the API so the Flutter app
                # can find the server on the LAN without manual IP entry.
                # Also register an atexit + SIGTERM handler that unregisters
                # the service on clean shutdown. Without that, the service
                # record stays advertised until its TTL expires (~120s),
                # so a Flutter app that opened during the window between
                # Jetson restart and the next service record refresh would
                # see a stale "Jarvis" entry pointing at no listener and
                # report "Could not connect."
                if api_cfg.get("discovery", {}).get("enabled", True):
                    try:
                        from api.discovery import register_service, unregister_service
                        register_service(api_cfg)
                        import atexit, signal
                        atexit.register(unregister_service)
                        # systemd's `systemctl stop` sends SIGTERM. The
                        # default Python handler raises SystemExit, which
                        # WILL fire atexit. But on some shells/CI runners
                        # SIGTERM hits before atexit is wired up; install
                        # an explicit handler for symmetry.
                        try:
                            _prev_term = signal.getsignal(signal.SIGTERM)
                            def _sigterm(_sig, _frm):
                                try:
                                    unregister_service()
                                finally:
                                    if callable(_prev_term):
                                        _prev_term(_sig, _frm)
                                    else:
                                        # Default — exit cleanly
                                        raise SystemExit(143)
                            signal.signal(signal.SIGTERM, _sigterm)
                        except (ValueError, OSError):
                            # signal.signal must be called from main thread;
                            # if main.py is ever imported as a library this
                            # would fail. Best effort.
                            pass
                    except Exception as e:
                        log.debug("mDNS registration skipped: %s", e)
        except Exception as e:
            log.info("API server not available (%s). Companion app features disabled.", e)
            assistant["api"] = None
    else:
        assistant["api"] = None

    # Wake word — background listening for activation phrases
    ww_cfg = config.get("wake_word", {})
    try:
        assistant["wake_word"] = get_provider(
            "wake_word",
            ww_cfg.get("provider", "openwakeword"),
        )

        # Build wake word → personality mapping from config:
        # Per-personality wake words take priority. The system wake word
        # (assistant.wake_word) is only added if it doesn't duplicate
        # a personality's wake word — it keeps the current personality.
        wake_words = {}

        # First: personality-specific wake words
        # Until custom wake word models are trained, all wake words just activate
        # without switching personality. The user switches personality via voice command.
        for p in personality_manager.list():
            if p.wake_word:
                wake_words[p.wake_word.lower()] = ""  # "" = don't switch personality

        # Then: system wake word (only if not already claimed by a personality)
        system_ww = config.get("assistant", {}).get("wake_word", "")
        if system_ww and system_ww.lower() not in wake_words:
            wake_words[system_ww.lower()] = ""  # "" = don't switch personality

        assistant["wake_word"].register_wake_words(wake_words)
    except Exception as e:
        log.info("Wake word not available (%s). Using manual activation.", e)
        assistant["wake_word"] = None

    return assistant


# ── Run modes ────────────────────────────────────────────────────

def _keep_api_alive(reason: str) -> None:
    """
    Block forever so daemon threads (API server, FaceUI, position poller)
    keep running. Used when an interactive run mode can't proceed (e.g.,
    --wake mode booted by systemd on a Jetson with no microphone plugged in)
    but we still want the network API on port 8766 to serve the Mac client.

    Returning from main() instead would let the process exit and tear down
    the API thread, defeating the point of auto-start.
    """
    import signal
    log.warning("Local input unavailable (%s). API server stays up. "
                "Plug in a mic and restart the service to enable wake mode.",
                reason)
    print(f"[headless] {reason}. API server is serving on port 8766.")
    print("[headless] Use Ctrl+C / SIGTERM to stop.")
    # signal.pause() blocks until any signal arrives. systemd's stop sends
    # SIGTERM, which raises KeyboardInterrupt-style exit cleanly.
    try:
        signal.pause()
    except (KeyboardInterrupt, SystemExit):
        pass


def run_text_mode(assistant: dict):
    """Interactive text mode — for Mac simulation and testing."""
    name = assistant["name"]
    brain = assistant["brain"]

    p = personality_manager.active
    personalities = ", ".join(x.display_name for x in personality_manager.list())

    print(f"\n{'═' * 60}")
    print(f"  {p.display_name} — Text Mode")
    print(f"  Model: {brain.model}")
    print(f"  Personalities: {personalities}")
    print(f"  Type a command, or 'quit' to exit")
    print(f"{'═' * 60}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"{name}: Goodbye!")
            break

        process_input(assistant, user_input)


def run_voice_mode(assistant: dict):
    """
    Voice input mode — speak to the assistant via microphone.

    v1 approach: Press Enter to start recording, press Enter to stop.
    Future: wake word detection starts recording automatically.

    The flow:
      1. User presses Enter
      2. Mic records until Enter is pressed again (or max duration)
      3. Audio → faster-whisper → text
      4. Text → intent classification → action → response
      5. Response → TTS → speaker
      6. Repeat
    """
    from core.mic import record_with_enter_to_stop, check_mic_available

    name = assistant["name"]
    brain = assistant["brain"]
    ears = assistant["ears"]

    if not ears:
        _keep_api_alive("No STT provider available for voice mode")
        return

    if not check_mic_available():
        _keep_api_alive("No microphone detected for voice mode")
        return

    p = personality_manager.active
    personalities = ", ".join(x.display_name for x in personality_manager.list())

    print(f"\n{'═' * 60}")
    print(f"  {p.display_name} — Voice Mode")
    print(f"  Model: {brain.model}")
    print(f"  STT: {ears.__class__.__name__}")
    print(f"  Personalities: {personalities}")
    print(f"  Press Enter to start talking, Enter again to stop")
    print(f"  Type 'quit' + Enter to exit")
    print(f"{'═' * 60}\n")

    while True:
        try:
            # Wait for Enter to start recording
            prompt = input("🎤 Press Enter to speak (or type 'quit')... ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if prompt.lower() in ("quit", "exit", "bye"):
            print(f"{name}: Goodbye!")
            break

        # If they typed something instead of pressing Enter, use it as text input
        if prompt:
            process_input(assistant, prompt)
            continue

        # Record from microphone
        print("🔴 Listening... (press Enter to stop)")
        face_ui = assistant.get("face_ui")
        if face_ui:
            face_ui.set_state("listening")
        try:
            audio_bytes = record_with_enter_to_stop()
        except Exception as e:
            log.error("Recording failed: %s", e)
            print(f"Recording error: {e}")
            continue

        if not audio_bytes:
            print("No audio captured. Try again.")
            continue

        # Transcribe
        print("🧠 Transcribing...")
        try:
            result = ears.transcribe(audio_bytes)
        except Exception as e:
            log.error("Transcription failed: %s", e)
            print(f"Transcription error: {e}")
            continue

        user_input = result.text.strip()
        if not user_input:
            print("Didn't catch that. Try again.")
            continue

        print(f"You: {user_input}  [{result.language}, {result.confidence:.0%}]\n")

        # Process the transcribed input
        process_input(assistant, user_input)


def run_wake_word_mode(assistant: dict):
    """
    Fully hands-free voice mode — wake word activates recording.

    This is the "real" assistant experience:
      1. OpenWakeWord runs in a background thread, listening for activation phrases
      2. User says "Hey Jarvis, play some music"
      3. Wake word detected → personality switched (if applicable) → mic records command
      4. Recording stops on silence (VAD) or max duration
      5. Audio → STT → intent → action → TTS response
      6. Resume listening for next wake word

    Wake word behavior:
      - "Hey Jarvis" activates listening with whatever personality is currently active
      - The wake word does NOT switch personality — all personalities share one
        wake word model ("hey_jarvis")
      - Personality switching happens via explicit voice command ("switch to Chandler")

    Interruption ("barge-in"):
      Wake word detection resumes BEFORE TTS starts speaking. If the user
      says a wake word while the assistant is talking, TTS stops immediately
      and the assistant begins listening for a new command. This is how real
      smart speakers work — you can say "Hey Jarvis, stop" mid-story.

      Without proper Acoustic Echo Cancellation (AEC), the wake word model
      might occasionally trigger on the assistant's own voice. The cooldown
      timer (default 2s) helps, and OpenWakeWord's neural model is trained
      on human speech patterns, not TTS output. In practice this works well
      in a quiet room at normal speaker volume.

    Falls back to the press-Enter voice mode if wake word provider isn't available.
    """
    from core.mic import record_with_enter_to_stop, record_fixed, record_smart, check_mic_available

    name = assistant["name"]
    ears = assistant["ears"]
    wake_word_provider = assistant.get("wake_word")

    if not ears:
        _keep_api_alive("No STT provider available for wake-word mode")
        return

    if not check_mic_available():
        # Common case on a headless Jetson without a USB mic plugged in.
        # The Mac client can still reach the API, so keep it alive instead
        # of exiting (which would also kill the API thread).
        _keep_api_alive("No microphone detected for wake-word mode")
        return

    if not wake_word_provider:
        log.warning("Wake word provider not available. Falling back to manual voice mode.")
        run_voice_mode(assistant)
        return

    p = personality_manager.active
    personalities = ", ".join(x.display_name for x in personality_manager.list())
    wake_words = ", ".join(
        f'"{ww}" → {pid or "system"}'
        for ww, pid in wake_word_provider._word_to_personality.items()
    )

    print(f"\n{'═' * 60}")
    print(f"  {p.display_name} — Wake Word Mode")
    print(f"  Wake words: {wake_words}")
    print(f"  Personalities: {personalities}")
    print(f"  Say a wake word to activate, or Ctrl+C to exit")
    print(f"  Interruption: say wake word while speaking to stop")
    print(f"{'═' * 60}\n")

    # Thread-safe event for signaling wake word detection to main thread
    detection_event = threading.Event()
    detection_data = [None]  # mutable container for passing data between threads

    # Pipeline state — protected by a lock so the main loop and the wake word
    # callback can safely coordinate cancellation.
    _pipeline_lock = threading.Lock()
    _active_cancel_event = [None]   # the cancel event for the currently running pipeline
    _active_interrupt_event = [None]  # the TTS interrupt event for the current pipeline

    def on_wake_word(detection: WakeWordDetection):
        """
        Called from the wake word listener thread.

        Two scenarios:
          1. Assistant is idle → normal activation (detection_event signals main loop)
          2. Assistant is thinking/speaking → cancel current pipeline + barge-in

        When the user says the wake word while a pipeline is running:
          - cancel_event is set → pipeline aborts at next checkpoint
          - interrupt_event is set → TTS playback stops immediately
          - detection_event is set → main loop starts a new record/transcribe cycle
        """
        with _pipeline_lock:
            # Cancel the running pipeline (if any)
            if _active_cancel_event[0] is not None:
                _active_cancel_event[0].set()
            # Interrupt TTS playback (if any)
            if _active_interrupt_event[0] is not None:
                _active_interrupt_event[0].set()

        detection_data[0] = detection
        detection_event.set()

    # Start wake word listener
    wake_word_provider.start_listening(on_wake_word)

    try:
        while True:
            # Show idle state
            p = personality_manager.active
            print(f"💤 {p.display_name} listening for wake word...")

            # Wait for wake word detection
            while True:
                if detection_event.wait(timeout=0.1):
                    break

            # Wake word detected!
            detection = detection_data[0]
            detection_data[0] = None
            detection_event.clear()

            if detection is None:
                continue

            # ── Sleep mode: wake word = auto-wake (no recording needed) ──
            if is_sleep_mode():
                log.info("Wake word during sleep mode — auto-waking.")
                face_ui = assistant.get("face_ui")
                try:
                    response = trigger_wake(assistant)
                    # Speak the wake response via TTS
                    voice_router = assistant.get("voice_router")
                    if voice_router and response:
                        if face_ui:
                            face_ui.set_state("speaking")
                            face_ui.show_transcript(response, role="assistant")
                        voice_router.speak(response)
                        if face_ui:
                            face_ui.set_state("idle")
                    elif response:
                        print(f"{name}: {response}")
                except Exception as e:
                    log.error("Auto-wake failed: %s", e)
                continue  # Resume listening, don't record a command

            # Wake word activates listening — it does NOT switch personality.
            # All wake words share a single model ("hey_jarvis") regardless of
            # active personality. Personality only changes via explicit voice
            # command ("switch to Chandler").
            face_ui = assistant.get("face_ui")
            p = personality_manager.active
            print(f"🔴 {p.display_name} is listening...")

            # Face UI: show listening state
            if face_ui:
                face_ui.set_state("listening")

            # Pause wake word detection while recording (prevents self-trigger
            # AND avoids mic contention — macOS only allows one InputStream)
            wake_word_provider.pause_listening()

            try:
                # Smart recording: auto-detects when you stop talking.
                # Uses fixed energy threshold (configurable via ears.vad_threshold).
                # Stops after 2s of genuine silence. Max 30s safety cap.
                audio_bytes = record_smart(
                    silence_timeout=0.8,    # 0.8s of silence = done talking (was 2.0 — too slow for commands)
                    max_duration=30.0,      # safety cap (stories, long commands)
                    pre_speech_timeout=5.0,  # give up if no speech after 5s
                )
            except Exception as e:
                log.error("Recording failed: %s", e)
                wake_word_provider.resume_listening()
                continue

            if not audio_bytes:
                print("Didn't hear anything. Try again.")
                wake_word_provider.resume_listening()
                continue

            # Transcribe
            print("🧠 Transcribing...")
            try:
                result = ears.transcribe(audio_bytes)
            except Exception as e:
                log.error("Transcription failed: %s", e)
                wake_word_provider.resume_listening()
                continue

            user_input = result.text.strip()
            if not user_input:
                print("Didn't catch that. Try again.")
                wake_word_provider.resume_listening()
                continue

            print(f"You: {user_input}  [{result.language}, {result.confidence:.0%}]\n")

            # Resume wake word detection IMMEDIATELY after transcription.
            # The entire pipeline (classify → execute → speak) runs in a
            # background thread. The main loop is free to handle the next
            # wake word detection at any time.
            #
            # This means the user is NEVER blocked — they can say "Hey Jarvis"
            # to interrupt or give a new command even while the assistant is
            # thinking, executing actions, or speaking.
            wake_word_provider.resume_listening()

            # Create fresh events for this pipeline run, and cancel any
            # previous pipeline atomically under the lock.
            cancel_event = threading.Event()
            interrupt_event = threading.Event()

            with _pipeline_lock:
                # Cancel the old pipeline (if still running)
                if _active_cancel_event[0] is not None:
                    _active_cancel_event[0].set()
                if _active_interrupt_event[0] is not None:
                    _active_interrupt_event[0].set()
                # Install new events
                _active_cancel_event[0] = cancel_event
                _active_interrupt_event[0] = interrupt_event

            def _run_pipeline(text, cancel_evt, interrupt_evt):
                """Run the full pipeline in a background thread."""
                if cancel_evt.is_set():
                    log.info("Pipeline cancelled before start.")
                    return
                try:
                    process_input(
                        assistant, text,
                        interrupt_event=interrupt_evt,
                        cancel_event=cancel_evt,
                    )
                except Exception as e:
                    log.error("Pipeline error: %s", e)
                finally:
                    # Clear ourselves as the active pipeline (only if we're
                    # still the active one — a newer pipeline may have replaced us)
                    with _pipeline_lock:
                        if _active_cancel_event[0] is cancel_evt:
                            _active_cancel_event[0] = None
                            _active_interrupt_event[0] = None
                    # Back to idle if this pipeline wasn't cancelled
                    if not cancel_evt.is_set():
                        face_ui = assistant.get("face_ui")
                        if face_ui:
                            face_ui.set_state("idle")

            # Fire the pipeline in a background thread
            import concurrent.futures
            _intent_executor = getattr(run_wake_word_mode, '_executor', None)
            if _intent_executor is None:
                _intent_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="pipeline"
                )
                run_wake_word_mode._executor = _intent_executor

            _intent_executor.submit(_run_pipeline, user_input, cancel_event, interrupt_event)

    except (KeyboardInterrupt, EOFError):
        print(f"\n{name}: Goodbye!")
    finally:
        wake_word_provider.stop_listening()


def main():
    parser = argparse.ArgumentParser(description="Run the voice assistant")
    parser.add_argument("--text", action="store_true", help="Force text-input mode")
    parser.add_argument("--voice", action="store_true", help="Force voice-input mode (press Enter to record)")
    parser.add_argument("--wake", action="store_true", help="Force wake word mode (hands-free)")
    # NOTE: --config is currently non-functional. Config loads at import time
    # (core/config.py) before argparse runs. To use a custom config path, set
    # the JARVIS_CONFIG env var or symlink config.yaml. Fixing this properly
    # requires lazy config loading, which is a larger refactor.
    parser.add_argument("--config", type=str, help="Path to config.yaml (not yet implemented)")
    args = parser.parse_args()

    name = config["assistant"]["name"]
    log.info("Starting %s...", name)
    log.debug("Registered providers: %s", list_providers())

    assistant = build_assistant()

    # Register callback for when mpv exits naturally (song ends).
    # Clears the dashboard's now-playing state and audio focus so the UI
    # doesn't show stale data after a song finishes.
    music = assistant.get("music")
    if music and hasattr(music, "register_on_ended"):
        def _on_music_ended():
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_now_playing(None)
            AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, False)

        music.register_on_ended(_on_music_ended)

    # Wire dashboard into music provider so browser mode can route playback
    # through the iframe instead of mpv.
    face_ui = assistant.get("face_ui")
    if music and face_ui:
        music.set_face_ui(face_ui)

    # Start playback position polling thread — updates dashboard progress bar every second
    def _position_poll_loop():
        import time as _time
        music = assistant.get("music")
        face_ui = assistant.get("face_ui")
        while True:
            try:
                if (music and face_ui
                        and not getattr(face_ui, '_music_paused', False)
                        and not getattr(music, '_browser_playing', False)
                        and music.is_playing()):
                    pos = music.get_playback_position()
                    if pos:
                        face_ui.update_playback_position(pos["position"], pos["duration"])
            except Exception:
                pass  # Never crash the poller thread
            _time.sleep(1)

    _poll_thread = threading.Thread(target=_position_poll_loop, name="position-poller", daemon=True)
    _poll_thread.start()

    # Wake-word listener watchdog. The OpenWakeWord listener thread runs
    # forever in a daemon thread; if it crashes (mic disconnect, ALSA
    # device removal, ONNX glitch — all observed), the previous behavior
    # was: log silently and the assistant goes deaf with no signal. The
    # monitor restarts the listener up to 3 times in a 5-minute window.
    # If it keeps crashing, we surface the failure and stop trying so
    # the user notices something is wrong instead of seeing infinite
    # restart spam.
    def _wake_watchdog_loop():
        import time as _time
        ww = assistant.get("wake_word")
        if ww is None or not hasattr(ww, "is_alive"):
            # Old wake word provider without is_alive() — nothing to monitor.
            return
        crash_history: list[float] = []
        while True:
            _time.sleep(15.0)
            try:
                # Only check while we believe we should be listening:
                # is_alive() returns False both when (a) we explicitly
                # called stop_listening (correct behaviour) and (b) when
                # the thread died unexpectedly. Heuristic: if _running
                # is True (set by start_listening), we EXPECT the thread
                # to be alive. is_alive() reads both, so a False here
                # while we're "supposed to be listening" means a crash.
                if not getattr(ww, "_running", False):
                    continue  # not currently listening — nothing to do
                if ww.is_alive():
                    continue  # healthy

                now = _time.time()
                # Drop crashes older than the 5-minute window
                crash_history[:] = [t for t in crash_history if now - t < 300]
                crash_history.append(now)
                if len(crash_history) > 3:
                    log.error(
                        "Wake-word listener has crashed %d times in 5 minutes — "
                        "giving up auto-restart. Microphone or audio stack is "
                        "unhealthy. Service restart required.",
                        len(crash_history),
                    )
                    return
                log.warning(
                    "Wake-word listener thread died — restarting (attempt %d/3 in window).",
                    len(crash_history),
                )
                try:
                    cb = ww._callback  # save the registered callback
                    if cb is not None:
                        ww.start_listening(cb)
                except Exception as e:
                    log.error("Wake-word restart failed: %s", e)
            except Exception as e:
                log.debug("Wake-watchdog loop error: %s", e)

    _wake_watchdog_thread = threading.Thread(
        target=_wake_watchdog_loop, name="wake-watchdog", daemon=True,
    )
    _wake_watchdog_thread.start()

    if args.wake:
        run_wake_word_mode(assistant)
    elif args.voice:
        run_voice_mode(assistant)
    elif args.text:
        run_text_mode(assistant)
    else:
        # Auto-detect: wake word > voice > text
        if assistant.get("wake_word") and assistant.get("ears"):
            from core.mic import check_mic_available
            if check_mic_available():
                log.info("Wake word + mic detected — starting wake word mode. Use --text to force text mode.")
                run_wake_word_mode(assistant)
            else:
                log.info("No mic detected — starting text mode.")
                run_text_mode(assistant)
        elif assistant.get("ears"):
            from core.mic import check_mic_available
            if check_mic_available():
                log.info("Mic detected — starting voice mode. Use --text to force text mode.")
                run_voice_mode(assistant)
            else:
                log.info("No mic detected — starting text mode.")
                run_text_mode(assistant)
        else:
            run_text_mode(assistant)


if __name__ == "__main__":
    main()
