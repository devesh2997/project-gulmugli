"""
Model-agnostic intent router.

The model is a parameter, not a hardcoded choice.
In production, this reads from config.yaml.
In testing, the eval framework passes different models in.
"""

import json
from llm_client import client

# Default system prompt — this is your prompt engineering playground.
# Save your best version to best_system_prompt.txt
DEFAULT_SYSTEM_PROMPT = """You are JARVIS, a smart voice assistant. Classify the user's spoken request into a structured action.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {"query": "search terms", "platform": "youtube|spotify|any"}
   Resolve vague descriptions into specific search terms.

2. "music_control" — Control current playback
   Params: {"action": "pause|resume|skip|stop|volume_up|volume_down"}

3. "light_control" — Change room lights
   Params: {"action": "on|off|brightness|color|scene", "value": "..."}

4. "chat" — General question or conversation
   Params: {"message": "the user's question"}

5. "system" — System info
   Params: {"action": "time|date|weather|alarm|reminder"}

## Format
{"intent": "...", "params": {...}, "response": "Brief spoken acknowledgment. Empty for chat."}

## Examples
User: "play that sad Coldplay song from the space movie"
{"intent": "music_play", "params": {"query": "Atlas Coldplay Interstellar", "platform": "any"}, "response": "Playing Atlas by Coldplay."}

User: "turn the lights blue"
{"intent": "light_control", "params": {"action": "color", "value": "blue"}, "response": "Setting the lights to blue."}

User: "pause"
{"intent": "music_control", "params": {"action": "pause"}, "response": "Paused."}

User: "what's the meaning of life"
{"intent": "chat", "params": {"message": "what is the meaning of life"}, "response": ""}

User: "make the room romantic"
{"intent": "light_control", "params": {"action": "scene", "value": "romantic"}, "response": "Setting the mood."}
"""


class IntentRouter:
    def __init__(self, model: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.model = model
        self.system_prompt = system_prompt

    def classify(self, user_input: str) -> dict:
        """Classify a voice command into a structured intent."""
        parsed, response_meta = client.generate_json(
            prompt=user_input,
            model=self.model,
            system=self.system_prompt,
            temperature=0.3,
        )
        # Attach metadata for debugging/logging
        parsed["_meta"] = {
            "model": self.model,
            "latency": response_meta.latency,
            "tok_per_sec": response_meta.tokens_per_second,
        }
        return parsed

    def swap_model(self, new_model: str):
        """Hot-swap the model. Useful for A/B testing or multi-model setups."""
        self.model = new_model


# ─── Interactive Testing ──────────────────────────────────────────

if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"
    router = IntentRouter(model=model)

    print(f"Intent Router — using model: {model}")
    print(f"Type a command (or 'quit' to exit, 'swap <model>' to change model)\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower().startswith("swap "):
            new_model = user_input.split(" ", 1)[1]
            router.swap_model(new_model)
            print(f"Swapped to: {new_model}\n")
            continue

        try:
            result = router.classify(user_input)
            meta = result.pop("_meta", {})
            print(f"  Intent:   {result.get('intent')}")
            print(f"  Params:   {json.dumps(result.get('params', {}))}")
            print(f"  Response: {result.get('response', '')}")
            print(f"  [{meta.get('model')} | {meta.get('latency', 0):.2f}s | {meta.get('tok_per_sec', 0):.0f} tok/s]\n")
        except Exception as e:
            print(f"  Error: {e}\n")
