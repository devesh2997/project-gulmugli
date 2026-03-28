"""
Dashboard action handler — converts browser UI actions into assistant intents.

When the user clicks a button in the dashboard (pause, skip, volume slider,
text input, personality switch, settings change), it arrives here as a JSON
message via WebSocket. This module translates those actions into the same
Intent objects used by the voice/text pipeline, then routes through
handle_intent. Browser controls use the exact same code path as voice
commands — no duplication.

Runs in the WebSocket server thread, so it must be thread-safe.
The providers (mpv, tinytuya) are already thread-safe for simple commands.
"""

import threading

from core.interfaces import Intent
from core.logger import get_logger
from core.intent_handler import handle_intent, is_sleep_mode, trigger_wake
from core.pipeline import process_input

log = get_logger("ui.actions")


def handle_ui_action(assistant: dict, action_data: dict) -> None:
    """
    Handle an action sent from the browser dashboard.

    Converts browser button presses into Intent objects and routes them
    through handle_intent. Text input goes through the full pipeline
    (classify → execute → speak) in a separate thread.
    """
    action = action_data.get("action", "")
    params = action_data.get("params", {})

    if action == "text_input":
        text = params.get("text", "").strip()
        if not text:
            return

        # Special: __wake__ = tap-to-activate (visual feedback only for now)
        if text == "__wake__":
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_state("listening")
                import time
                def _flash():
                    time.sleep(2.0)
                    if face_ui:
                        face_ui.set_state("idle")
                threading.Thread(target=_flash, daemon=True).start()
            return

        # Full text input — process as if typed/spoken
        t = threading.Thread(
            target=process_input, args=(assistant, text),
            name="ui-text-input", daemon=True,
        )
        t.start()
        return

    # Map browser actions to Intent objects and execute directly
    intent = None
    if action == "music_control":
        intent = Intent(
            name="music_control",
            params={"action": params.get("action", "")},
            response="",
        )
    elif action == "volume":
        intent = Intent(
            name="volume",
            params={"level": str(params.get("level", 50))},
            response="",
        )
    elif action == "light_control":
        intent = Intent(
            name="light_control",
            params=params,
            response="",
        )
    elif action == "switch_personality":
        intent = Intent(
            name="switch_personality",
            params={"personality": params.get("personality", "")},
            response="",
        )
    elif action == "seek":
        # Seek is a direct music provider call, not an intent
        music = assistant.get("music")
        if music and hasattr(music, "seek"):
            position = float(params.get("position", 0))
            music.seek(position)

            # Update the dashboard's now-playing position so the progress bar jumps
            face_ui = assistant.get("face_ui")
            if face_ui and face_ui._now_playing:
                face_ui._now_playing["position"] = position
                face_ui.set_now_playing(face_ui._now_playing)
        return

    elif action == "wake":
        # Tap-to-wake from dashboard — trigger the same wake flow as voice
        if is_sleep_mode():
            log.info("UI wake action received — waking from sleep mode.")
            response = trigger_wake(assistant)
            # Speak the wake response via TTS in a background thread
            voice_router = assistant.get("voice_router")
            if voice_router and response:
                face_ui = assistant.get("face_ui")
                if face_ui:
                    face_ui.show_transcript(response, role="assistant")
                def _speak_wake():
                    try:
                        voice_router.speak(response)
                    except Exception as e:
                        log.warning("Wake TTS failed: %s", e)
                threading.Thread(target=_speak_wake, daemon=True).start()
        return

    # ── Audio controls ──
    elif action == "audio_volume":
        # Set system volume
        level = action_data.get("value", action_data.get("params", {}).get("level", 50))
        intent = Intent(
            name="volume",
            params={"level": str(level)},
            response="",
        )

    elif action == "audio_list_outputs":
        # List available audio output devices
        face_ui = assistant.get("face_ui")
        audio = assistant.get("audio")
        if face_ui:
            outputs = []
            if audio and hasattr(audio, "list_outputs"):
                try:
                    outputs = audio.list_outputs()
                except Exception as e:
                    log.warning("Failed to list audio outputs: %s", e)
            face_ui._broadcast({"type": "audio_outputs", "outputs": outputs})
        return

    elif action == "audio_set_output":
        # Switch audio output device
        device = action_data.get("device", "")
        audio = assistant.get("audio")
        if audio and hasattr(audio, "set_output"):
            try:
                audio.set_output(device)
                log.info("Audio output switched to: %s", device)
            except Exception as e:
                log.warning("Failed to switch audio output: %s", e)
        return

    elif action == "bt_scan":
        # Start Bluetooth scan — results come back asynchronously
        face_ui = assistant.get("face_ui")
        audio = assistant.get("audio")
        if face_ui:
            face_ui._broadcast({
                "type": "bt_scan_result",
                "devices": [],
                "scanning": True,
            })
        if audio and hasattr(audio, "bluetooth_scan"):
            def _scan():
                try:
                    devices = audio.bluetooth_scan()
                    if face_ui:
                        face_ui._broadcast({
                            "type": "bt_scan_result",
                            "devices": devices,
                            "scanning": False,
                        })
                except Exception as e:
                    log.warning("Bluetooth scan failed: %s", e)
                    if face_ui:
                        face_ui._broadcast({
                            "type": "bt_scan_result",
                            "devices": [],
                            "scanning": False,
                        })
            threading.Thread(target=_scan, daemon=True).start()
        else:
            if face_ui:
                face_ui._broadcast({
                    "type": "bt_scan_result",
                    "devices": [],
                    "scanning": False,
                })
        return

    elif action == "bt_pair":
        # Pair with a Bluetooth device
        mac = action_data.get("mac", "")
        face_ui = assistant.get("face_ui")
        audio = assistant.get("audio")
        if audio and hasattr(audio, "bluetooth_pair") and mac:
            def _pair():
                try:
                    success = audio.bluetooth_pair(mac)
                    if face_ui:
                        face_ui._broadcast({
                            "type": "bt_pair_result",
                            "mac": mac,
                            "success": bool(success),
                        })
                except Exception as e:
                    log.warning("Bluetooth pair failed: %s", e)
                    if face_ui:
                        face_ui._broadcast({
                            "type": "bt_pair_result",
                            "mac": mac,
                            "success": False,
                        })
            threading.Thread(target=_pair, daemon=True).start()
        return

    elif action == "bt_disconnect":
        # Disconnect a Bluetooth device
        mac = action_data.get("mac", "")
        audio = assistant.get("audio")
        if audio and hasattr(audio, "bluetooth_disconnect") and mac:
            try:
                audio.bluetooth_disconnect(mac)
                log.info("Bluetooth disconnected: %s", mac)
            except Exception as e:
                log.warning("Bluetooth disconnect failed: %s", e)
        return

    elif action == "get_settings":
        # Dashboard requesting the flat settings list with current values
        from core.config_manager import config_manager
        face_ui = assistant.get("face_ui")
        if face_ui:
            settings = config_manager.get_settings()
            face_ui.send_settings(settings)
        return

    elif action == "update_setting":
        # Dashboard updating a config value
        from core.config_manager import config_manager
        path = params.get("path", "")
        value = params.get("value")
        result = config_manager.update(path, value)
        face_ui = assistant.get("face_ui")
        if face_ui:
            face_ui._broadcast({"type": "setting_result", "path": path, **result})
            # If successful, resend updated settings list
            if result.get("ok"):
                settings = config_manager.get_settings()
                face_ui.send_settings(settings)
        return

    elif action == "quiz_answer":
        # User tapped an answer option on the quiz card
        # Frontend sends answer at top level OR inside params
        answer = params.get("answer", "") or action_data.get("answer", "")
        if answer:
            intent = Intent(
                name="quiz",
                params={"action": "answer", "answer": answer},
                response="",
            )

    elif action == "position_report":
        music = assistant.get("music")
        if music and hasattr(music, "report_position"):
            pos = params.get("position", 0) or action_data.get("position", 0)
            dur = params.get("duration", 0) or action_data.get("duration", 0)
            music.report_position(pos, dur)
        return

    elif action == "player_ended":
        music = assistant.get("music")
        if music:
            music._browser_playing = False
        face_ui = assistant.get("face_ui")
        if face_ui:
            face_ui.set_now_playing(None)
        from core.audio_focus import AudioFocusManager, AudioChannel
        AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, False)
        return

    elif action == "quiz_hint":
        # User tapped the hint button on the quiz card
        intent = Intent(
            name="quiz",
            params={"action": "hint"},
            response="",
        )

    elif action == "quiz_quit":
        # User tapped the X/quit button on the quiz card
        intent = Intent(
            name="quiz",
            params={"action": "quit"},
            response="",
        )

    elif action == "timer_cancel":
        # Cancel a specific timer/alarm from the dashboard
        entry_id = params.get("id", "") or action_data.get("id", "")
        cancel_type = params.get("type", "timer")
        intent = Intent(
            name="timer",
            params={"action": "cancel", "cancel_type": entry_id or cancel_type},
            response="",
        )

    elif action == "timer_snooze":
        # Snooze an alarm from the dashboard
        entry_id = params.get("id", "") or action_data.get("id", "")
        snooze_mins = int(params.get("minutes", 5))
        timer_mgr = assistant.get("timer_manager")
        if timer_mgr:
            snoozed = timer_mgr.snooze(entry_id or "alarm", minutes=snooze_mins)
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_timers(timer_mgr.list_active())
            if snoozed:
                log.info("Snoozed %s for %d minutes via dashboard", snoozed.label, snooze_mins)
        return

    if intent:
        try:
            response = handle_intent(assistant, intent)
            # For quiz actions, speak the response via TTS
            if action in ("quiz_answer", "quiz_hint", "quiz_quit") and response:
                voice_router = assistant.get("voice_router")
                face_ui = assistant.get("face_ui")
                if face_ui:
                    face_ui.show_transcript(response, role="assistant")
                if voice_router:
                    def _speak_quiz():
                        try:
                            voice_router.speak(response)
                        except Exception as e:
                            log.warning("Quiz TTS failed: %s", e)
                    threading.Thread(target=_speak_quiz, daemon=True).start()
        except Exception as e:
            log.warning("UI action failed: %s — %s", action, e)
