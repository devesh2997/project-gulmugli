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
from core.intent_handler import handle_intent
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
        # Full text input from the dashboard — process as if typed
        text = params.get("text", "").strip()
        if text:
            # Run in a separate thread to avoid blocking the WS event loop
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

    elif action == "get_settings":
        # Dashboard requesting the config settings list
        from core.config_manager import config_manager
        face_ui = assistant.get("face_ui")
        if face_ui:
            settings = config_manager.get_settings_by_category()
            face_ui._broadcast({"type": "settings", "categories": settings})
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
            # If successful, send the updated settings list
            if result.get("ok"):
                settings = config_manager.get_settings_by_category()
                face_ui._broadcast({"type": "settings", "categories": settings})
        return

    if intent:
        try:
            handle_intent(assistant, intent)
        except Exception as e:
            log.warning("UI action failed: %s — %s", action, e)
