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

from core.config import config
from core.logger import get_logger
from core.registry import get_provider, list_providers

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

    elif intent.name == "chat":
        # For chat, we'd want a longer response from the LLM
        message = intent.params.get("message", "")
        resp = assistant["brain"].generate(prompt=message, temperature=0.7)
        return resp.text

    elif intent.name == "system":
        action = intent.params.get("action", "")
        if action == "time":
            from datetime import datetime
            return f"It's {datetime.now().strftime('%I:%M %p')}."
        elif action == "date":
            from datetime import datetime
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
        return intent.response or "I can't do that yet."

    else:
        return intent.response or "I'm not sure what to do with that."


def run_text_mode(assistant: dict):
    """Interactive text mode — for Mac simulation and testing."""
    name = assistant["name"]
    brain = assistant["brain"]

    print(f"\n{'═' * 60}")
    print(f"  {name} — Text Mode")
    print(f"  Model: {brain.model}")
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

        # Classify intent(s) — may return multiple for chained commands
        intents = brain.classify_intent(user_input)

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

        # Always use the actual response from handle_intent, not the LLM's pre-written text.
        # The LLM says "Playing Sajni" before it knows what song was found — the handler
        # knows the actual result.
        print(f"{name}: {' '.join(responses)}\n")


def main():
    parser = argparse.ArgumentParser(description="Run the voice assistant")
    parser.add_argument("--text", action="store_true", help="Force text-input mode")
    parser.add_argument("--config", type=str, help="Path to config.yaml")
    args = parser.parse_args()

    name = config["assistant"]["name"]
    log.info("Starting %s...", name)
    log.debug("Registered providers: %s", list_providers())

    assistant = build_assistant()

    # For now, always text mode. When ears/voice providers are implemented,
    # this will check hardware.platform and auto-select.
    run_text_mode(assistant)


if __name__ == "__main__":
    main()
