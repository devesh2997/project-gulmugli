"""
Main entry point for the assistant.

This file wires up all providers based on config.yaml and runs the main loop.
In simulation mode (Mac), it uses text input instead of a microphone.

Usage:
    python main.py              # Run with config.yaml settings
    python main.py --text       # Force text-input mode (no mic)
    python main.py --config /path/to/config.yaml  # Custom config
"""

import sys
import json
import argparse
import threading
from datetime import datetime, timezone

from core.config import config
from core.logger import get_logger
from core.registry import get_provider, list_providers
from core.personality import personality_manager
from core.voice_router import VoiceRouter
from core.interfaces import Interaction, WakeWordDetection
from core.prefilter import prefilter_intent
from ui.server import FaceUI

# This import triggers provider auto-discovery via @register decorators
import providers  # noqa: F401

log = get_logger("main")


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

    # Voice (TTS) — smart routing per personality with fallback
    # VoiceRouter handles: preferred provider → fallback → text-only
    assistant["voice_router"] = VoiceRouter()

    # Ears (STT) — optional, needed for voice mode
    ears_cfg = config.get("ears", {})
    try:
        assistant["ears"] = get_provider(
            "ears",
            ears_cfg.get("provider", "faster_whisper"),
        )
    except Exception as e:
        log.info("Ears (STT) not available (%s). Voice input disabled, text mode only.", e)
        assistant["ears"] = None

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

    # Face UI — browser-based animated face (purely cosmetic, optional)
    face_ui = FaceUI(port=config.get("ui", {}).get("port", 8765))
    face_ui.start()
    assistant["face_ui"] = face_ui

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
        for p in personality_manager.list():
            if p.wake_word:
                wake_words[p.wake_word.lower()] = p.id

        # Then: system wake word (only if not already claimed by a personality)
        system_ww = config.get("assistant", {}).get("wake_word", "")
        if system_ww and system_ww.lower() not in wake_words:
            wake_words[system_ww.lower()] = ""  # "" = don't switch personality

        assistant["wake_word"].register_wake_words(wake_words)
    except Exception as e:
        log.info("Wake word not available (%s). Using manual activation.", e)
        assistant["wake_word"] = None

    return assistant


def handle_intent(assistant: dict, intent) -> str:
    """
    Execute an intent using the appropriate provider.
    Returns a spoken response string.
    """
    name = config["assistant"]["name"]

    if intent.name == "music_play" and assistant.get("music"):
        raw_query = intent.params.get("query", "")
        if not raw_query:
            return "I didn't catch what you want to play."

        # Step 2: Enrich the raw query (separate from classification)
        enriched_query = assistant["brain"].enrich_query(raw_query)

        log.debug('Raw query: "%s"', raw_query)
        if enriched_query != raw_query:
            log.debug('Enriched query: "%s"', enriched_query)

        # Dual search: enriched for primary, raw for fallback
        results = assistant["music"].search(enriched_query, limit=3, raw_input=raw_query)
        if results:
            song = results[0]
            log.info('Playing: "%s" by %s', song.title, song.artist)
            assistant["music"].play(song)
            return f"Playing {song.title} by {song.artist}."
        else:
            return f"I couldn't find anything for '{raw_query}'."

    elif intent.name == "music_control" and assistant.get("music"):
        action = intent.params.get("action", "")
        music = assistant["music"]

        actions = {
            "pause": music.pause,
            "resume": music.resume,
            "stop": music.stop,
            "skip": music.skip,
        }

        if action in actions:
            actions[action]()
            return intent.response or f"{action.title()}."
        else:
            return f"I don't know how to {action}."

    elif intent.name == "volume":
        # System-level volume — applies to all audio output (music, TTS, etc.)
        # Currently routes through the music provider's mpv instance since that's
        # the only audio output. When AudioOutputProvider is implemented, this
        # will route through that instead.
        value = str(intent.params.get("level", ""))
        output = intent.params.get("output", "default")
        numeric = ''.join(c for c in value if c.isdigit())
        level = min(100, max(0, int(numeric))) if numeric else 50

        if assistant.get("audio"):
            # Future: use AudioOutputProvider
            assistant["audio"].set_volume(level, output=output)
        elif assistant.get("music"):
            # Fallback: route through mpv (current state)
            assistant["music"].set_volume(level)
        else:
            return "No audio output available."

        return intent.response or f"Volume set to {level}."

    elif intent.name == "light_control" and assistant.get("lights"):
        action = intent.params.get("action", "")
        value = str(intent.params.get("value", ""))
        lights = assistant["lights"]

        try:
            if action == "on":
                lights.turn_on()
            elif action == "off":
                lights.turn_off()
            elif action == "color":
                lights.set_color(value)
            elif action == "brightness":
                # LLM might return "20%", "20", "20 percent", etc.
                numeric = ''.join(c for c in value if c.isdigit())
                lights.set_brightness(int(numeric) if numeric else 50)
            elif action == "scene":
                lights.set_scene(value)
            return intent.response or "Done."
        except Exception as e:
            return f"Light control failed: {e}"

    elif intent.name == "switch_personality":
        target = intent.params.get("personality", "")
        try:
            p = personality_manager.switch(target)
            return intent.response or f"Switched to {p.display_name}."
        except KeyError as e:
            available = ", ".join(p.display_name for p in personality_manager.list())
            return f"I don't know that personality. Available: {available}."

    elif intent.name == "chat":
        # For chat, use the ORIGINAL user input — not the classified "message" param.
        # The classifier sometimes generates a response as the message param
        # (e.g., generating a story instead of just classifying "tell me a story"
        # as a chat intent). Sending that generated text back to the LLM causes
        # the LLM to respond to its own output instead of the user's request.
        #
        # Fall back to intent.params["message"] only if original_input isn't available
        # (e.g., when called from a test without the full pipeline).
        original_input = intent.meta.get("original_input", "")
        message = original_input or intent.params.get("message", "")
        p = personality_manager.active
        system = f"You are {p.display_name}. {p.tone}\nRespond naturally and concisely."
        resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.7)
        return resp.text

    elif intent.name == "memory_recall" and assistant.get("memory"):
        query = intent.params.get("query", "")
        memory = assistant["memory"]

        if not query:
            # No specific query — show recent interactions
            memories = memory.get_recent(limit=5)
        else:
            memories = memory.recall(query, limit=5)

        if not memories:
            return "I don't have any memories matching that yet."

        # Format memories into a natural response
        # Feed the memories to the LLM so it can summarize them conversationally
        memory_text = "\n".join(
            f"- [{m.timestamp[:16]}] {m.raw.get('input_text', '')} → "
            f"{', '.join(m.raw.get('responses', []))[:100]}"
            for m in memories
        )

        p = personality_manager.active
        system = (
            f"You are {p.display_name}. {p.tone}\n"
            f"The user is asking about past interactions. Here are the relevant memories:\n\n"
            f"{memory_text}\n\n"
            f"Summarize these memories naturally and concisely in response to: \"{query}\"\n"
            f"If the user asked 'what did I play', focus on the songs. "
            f"If they asked 'what did I ask', summarize the commands. Keep it short."
        )
        resp = assistant["brain"].generate(
            prompt=query or "What have I been doing recently?",
            system=system,
            temperature=0.5,
        )
        return resp.text

    elif intent.name == "memory_stats" and assistant.get("memory"):
        stats = assistant["memory"].get_stats()
        total = stats.get("total_interactions", 0)
        if total == 0:
            return "No interactions logged yet. I just started remembering!"
        top = stats.get("top_intents", {})
        top_str = ", ".join(f"{k} ({v})" for k, v in list(top.items())[:3])
        return (
            f"I've logged {total} interactions. "
            f"Most common: {top_str}. "
            f"First memory: {stats.get('first_interaction', 'unknown')[:10]}."
        )

    elif intent.name == "knowledge_search":
        query = intent.params.get("query", "")
        knowledge = assistant.get("knowledge")

        if not knowledge:
            # No knowledge provider — fall back to the LLM's own knowledge via chat
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked a factual question. Answer as best you can from your "
                f"own knowledge, but be honest if you're not sure or if the information "
                f"might be outdated. Keep it concise — this is a voice assistant."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        if not knowledge.is_available():
            # Provider exists but internet is down — degrade gracefully
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked about current events or real-time info, but internet "
                f"is not available right now. Answer from your own knowledge if you can, "
                f"but mention that you couldn't check online for the latest info."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        # Search for information
        results = knowledge.search(query)
        if not results:
            # Search returned nothing — fall back to LLM knowledge
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked a question. I searched online but found nothing relevant. "
                f"Answer from your own knowledge if possible, or say you couldn't find anything."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        # Build context from search results — keep it SHORT for 3B models.
        # Each snippet is ~1-2 sentences. 3 results ≈ 300-400 tokens.
        context_lines = []
        for i, r in enumerate(results, 1):
            # Truncate snippets to ~150 chars to stay within context budget
            snippet = r.snippet[:200].strip()
            context_lines.append(f"{i}. {r.title}: {snippet}")
        context = "\n".join(context_lines)

        original_input = intent.meta.get("original_input", "")
        message = original_input or query
        p = personality_manager.active
        system = (
            f"You are {p.display_name}. {p.tone}\n"
            f"The user asked a question. Here are relevant search results:\n\n"
            f"{context}\n\n"
            f"Using ONLY the information above, answer the user's question naturally "
            f"and concisely. This is a voice assistant — keep it to 2-3 sentences max. "
            f"If the search results don't fully answer the question, say what you found "
            f"and mention you're not sure about the rest."
        )
        resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
        return resp.text

    elif intent.name == "system":
        action = intent.params.get("action", "")
        if action == "time":
            return f"It's {datetime.now().strftime('%I:%M %p')}."
        elif action == "date":
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
        return intent.response or "I can't do that yet."

    else:
        return intent.response or "I'm not sure what to do with that."


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

        _process_input(assistant, user_input)


def _process_input(assistant: dict, user_input: str, interrupt_event=None):
    """
    Process a single user input: classify → execute → respond → log.

    Shared between text mode and voice mode — the only difference is
    how the input is obtained (typed vs spoken).

    Args:
        interrupt_event: Optional threading.Event. If set during TTS playback,
            audio stops immediately (wake word barge-in). The caller is
            responsible for handling the interrupted state.

    Returns:
        (response_text, was_interrupted) — the response string and whether
        TTS was interrupted by a wake word.

    Also pushes state transitions to the Face UI (if running):
      thinking → speaking → idle
    """
    brain = assistant["brain"]
    name = assistant["name"]
    face_ui = assistant.get("face_ui")

    # Show user's input on the face UI
    if face_ui:
        face_ui.show_transcript(user_input, role="user")
        face_ui.set_state("thinking")

    # Try keyword pre-filter first — resolves obvious commands in <1ms
    intents = prefilter_intent(user_input)

    # Fall through to LLM for ambiguous inputs
    if intents is None:
        intents = brain.classify_intent(user_input)

    # Attach original user input to each intent's meta so handlers can
    # use it instead of the classified params (important for chat — see handler)
    for intent in intents:
        intent.meta["original_input"] = user_input

    # Intent debug output — only visible in DEBUG mode
    latency = intents[0].meta.get("latency", 0) if intents else 0
    tok_s = intents[0].meta.get("tok_per_sec", 0) if intents else 0
    intent_names = " + ".join(i.name for i in intents)
    log.debug("[%s] (%.2fs, %.0f tok/s)", intent_names, latency, tok_s)
    for i in intents:
        log.debug("  → %s: %s", i.name, json.dumps(i.params))

    # Execute each intent in order
    responses = []
    for intent in intents:
        response = handle_intent(assistant, intent)
        responses.append(response)

    # Use active personality's display name (may have changed mid-loop)
    p = personality_manager.active
    response_text = " ".join(responses)
    print(f"{p.display_name}: {response_text}\n")

    # Update face UI with personality (may have changed) and response
    if face_ui:
        face_ui.set_personality(p.id)
        face_ui.show_transcript(response_text, role="assistant")
        face_ui.set_state("speaking")

    # Log this interaction to memory
    memory = assistant.get("memory")
    if memory:
        try:
            interaction = Interaction(
                user_id="default",
                input_text=user_input,
                intents=intents,
                responses=responses,
                outcome="success",
            )
            memory.log_interaction(interaction)
        except Exception as e:
            log.warning("Failed to log interaction to memory: %s", e)

    # Speak the response aloud via the voice router
    was_interrupted = False
    voice_router = assistant.get("voice_router")
    if voice_router and voice_router.enabled and response_text.strip():
        completed = voice_router.speak_to_device(
            response_text, personality=p, interrupt_event=interrupt_event,
        )
        was_interrupted = not completed

    # Back to idle after speaking
    if face_ui:
        face_ui.set_state("idle")

    return response_text, was_interrupted


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
        print("ERROR: No STT provider available. Use --text mode instead.")
        return

    if not check_mic_available():
        print("ERROR: No microphone detected. Use --text mode instead.")
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
            _process_input(assistant, prompt)
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
        _process_input(assistant, user_input)


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

    Per-personality wake words:
      - "Hey Jarvis" → activates with Jarvis personality
      - "Hey Devesh" → switches to Devesh personality, then listens
      - "Hey Chandler" → switches to Chandler personality, then listens

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
        print("ERROR: No STT provider available. Use --text mode instead.")
        return

    if not check_mic_available():
        print("ERROR: No microphone detected. Use --text mode instead.")
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

    # Interrupt event — shared with TTS playback. When the wake word fires
    # during TTS, this event is set, causing _play_wav_bytes to call sd.stop()
    # and return immediately.
    tts_interrupt = threading.Event()

    def on_wake_word(detection: WakeWordDetection):
        """
        Called from the wake word listener thread.

        Two scenarios:
          1. Assistant is idle → normal activation (detection_event signals main loop)
          2. Assistant is speaking → barge-in (tts_interrupt stops playback,
             then detection_event signals the main loop to process the new command)
        """
        # Always interrupt TTS if it's playing (harmless if not playing)
        tts_interrupt.set()

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
            tts_interrupt.clear()  # reset for next cycle

            if detection is None:
                continue

            # Switch personality if the wake word maps to one
            face_ui = assistant.get("face_ui")
            if detection.personality_id:
                try:
                    personality_manager.switch(detection.personality_id)
                    p = personality_manager.active
                    log.info('Wake word switched personality to "%s"', p.display_name)
                    if face_ui:
                        face_ui.set_personality(p.id)
                except KeyError:
                    log.warning('Unknown personality "%s" for wake word', detection.personality_id)

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
                    silence_timeout=2.0,    # 2s of silence = done talking
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

            # Resume wake word detection BEFORE speaking. This enables barge-in:
            # the user can say "Hey Jarvis" to interrupt mid-speech.
            # The wake word listener will set tts_interrupt, causing playback
            # to stop immediately.
            #
            # Why resume here instead of after TTS?
            # Real smart speakers (Alexa, Google Home) keep listening at all
            # times. They use Acoustic Echo Cancellation (AEC) to subtract
            # their own speaker output from the mic. We don't have AEC, but
            # OpenWakeWord's neural model has natural resistance to non-speech
            # audio, and the cooldown timer prevents rapid re-triggers.
            wake_word_provider.resume_listening()

            # Process the command — TTS playback happens inside _process_input.
            # If wake word fires during TTS, tts_interrupt is set, playback
            # stops, and was_interrupted is True.
            response_text, was_interrupted = _process_input(
                assistant, user_input, interrupt_event=tts_interrupt,
            )

            if was_interrupted:
                log.info("Response interrupted by wake word. Processing new command...")
                # Don't resume listening — it's already running.
                # The detection_event is already set by on_wake_word,
                # so the next iteration will pick up the new command immediately.

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
