"""
Ollama brain provider.

Talks to an Ollama server to classify intents and generate responses.
This is currently the primary brain provider for local inference.

To swap to a different LLM backend:
  - Create a new file (e.g., llamacpp.py, openai.py)
  - Implement BrainProvider
  - Register with @register("brain", "your_name")
  - Set brain.provider in config.yaml
"""

import requests
import json
import time

from core.interfaces import BrainProvider, LLMResponse, Intent
from core.registry import register
from core.config import config
from core.logger import get_logger
from core.personality import personality_manager

log = get_logger("brain.ollama")


# ═══════════════════════════════════════════════════════════════
# Prompt builders — these read from personality_manager.active
# so they always reflect the current personality.
# ═══════════════════════════════════════════════════════════════

def _build_music_preference_block(override_prefs: dict = None) -> str:
    """
    Build the music preferences section for prompts.

    Uses per-personality music_preferences if set, otherwise falls back
    to the global config.music.user_preferences.
    """
    # Per-personality override takes priority
    music_prefs = override_prefs or config.get("music", {}).get("user_preferences", {})
    if not music_prefs:
        return ""

    lines = ["\n## User's Music Taste (use this to disambiguate songs)"]

    languages = music_prefs.get("languages", [])
    region = music_prefs.get("region")
    if languages or region:
        langs = ", ".join(languages) if languages else "any"
        lines.append(f"- Languages: {langs}. Region: {region or 'any'}")

    artists = music_prefs.get("favorite_artists", [])
    if artists:
        lines.append(f"- Favorite artists: {', '.join(artists)}")

    genres = music_prefs.get("favorite_genres", [])
    if genres:
        lines.append(f"- Favorite genres: {', '.join(genres)}")

    bias = music_prefs.get("disambiguation_bias", "")
    if bias == "recent_bollywood":
        lines.append("- For Hindi songs: when ambiguous, prefer the recent Bollywood version by a favorite artist.")
        lines.append("- For English songs: prefer the globally popular version. Do NOT add Hindi artists to English songs.")

    return "\n".join(lines)


def _get_personality_names_for_prompt() -> str:
    """Build a list of available personality names for the classification prompt."""
    return ", ".join(
        f'"{p.id}" ({p.display_name})'
        for p in personality_manager.list()
    )


def _build_system_prompt() -> str:
    """
    Build the classification system prompt.

    Called fresh each time because the active personality can change.
    The personality's tone is injected so the LLM's response text
    matches the character, but the intent extraction logic stays stable.
    """
    p = personality_manager.active

    return f"""You are {p.display_name}, a smart voice assistant used in India. {p.tone}

Your ONLY job is to classify the user's spoken request into structured intents.
Extract parameters EXACTLY as the user said them. Do NOT modify, translate, or enrich song names.
The user speaks in English, Hindi, or Hinglish. You must understand all three.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {{"query": "the song/artist/mood keywords EXACTLY as the user said them"}}
   IMPORTANT: Do NOT add artist names, movie names, or any enrichment. Just extract what the user said.
   "play Sajni" → query: "Sajni"
   "kuch romantic sa bajao" → query: "romantic Hindi songs"
   "Coldplay bajao" → query: "Coldplay"
   For mood/vague requests, translate Hindi to English search terms: "kuch sad sa" → "sad Hindi songs"

2. "music_control" — Control current playback
   Params: {{"action": "pause|resume|skip|stop"}}

3. "volume" — Change system volume (applies to ALL audio)
   Params: {{"level": "0-100", "output": "default"}}
   Clamp to 100 max. "volume up"→80, "volume down"→30.

4. "light_control" — Change room lights
   Params: {{"action": "on|off|brightness|color|scene", "value": "..."}}

5. "switch_personality" — Switch assistant personality/character
   Params: {{"personality": "name of the personality to switch to"}}
   Available personalities: {_get_personality_names_for_prompt()}
   "switch to Devesh mode" → personality: "devesh"
   "talk like Chandler" → personality: "chandler"
   "Devesh ban ja" → personality: "devesh"
   "normal mode" / "default mode" / "Jarvis mode" → personality: "jarvis"

6. "chat" — General question or conversation
   Params: {{"message": "the user's question"}}

7. "system" — System info (time, date, weather, alarms)
   Params: {{"action": "time|date|weather|alarm|reminder"}}

## Format
Always return an "intents" array, even for a single command.
{{"intents": [{{"intent": "...", "params": {{...}}}}], "response": "Brief spoken acknowledgment IN CHARACTER."}}

## Response tone
Your "response" field MUST match your current personality:
{p.tone}

## Examples

User: "Sajni"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}], "response": "Playing Sajni."}}

User: "play Channa Mereya"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Channa Mereya"}}}}], "response": "Playing Channa Mereya."}}

User: "Starboy"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Starboy"}}}}], "response": "Playing Starboy."}}

User: "kuch romantic sa bajao"
{{"intents": [{{"intent": "music_play", "params": {{"query": "romantic Hindi songs"}}}}], "response": "Playing romantic songs."}}

User: "woh gaana jisme ladka train pe naachta hai"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Chaiyya Chaiyya"}}}}], "response": "Playing Chaiyya Chaiyya."}}

User: "pause"
{{"intents": [{{"intent": "music_control", "params": {{"action": "pause"}}}}], "response": "Paused."}}

User: "gaana band karo"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}], "response": "Stopped."}}

User: "awaaz badha do"
{{"intents": [{{"intent": "volume", "params": {{"level": "80", "output": "default"}}}}], "response": "Volume up."}}

User: "volume 50"
{{"intents": [{{"intent": "volume", "params": {{"level": "50", "output": "default"}}}}], "response": "Volume set to 50."}}

User: "turn the lights blue"
{{"intents": [{{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Lights set to blue."}}

User: "neeli light kar do"
{{"intents": [{{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Lights set to blue."}}

User: "movie mode"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "movie"}}}}], "response": "Movie mode on."}}

User: "what time is it"
{{"intents": [{{"intent": "system", "params": {{"action": "time"}}}}], "response": ""}}

User: "switch to Chandler mode"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "chandler"}}}}], "response": "Oh, so NOW you want the funny one."}}

User: "Devesh ban ja"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "devesh"}}}}], "response": "Haan bolo, Devesh here."}}

User: "normal mode"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "jarvis"}}}}], "response": "Back to normal."}}

### Chained commands
User: "play Sajni and set the lights to red"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}, {{"intent": "light_control", "params": {{"action": "color", "value": "red"}}}}], "response": "Playing Sajni with red lights."}}

User: "play Sajni volume 30"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}, {{"intent": "volume", "params": {{"level": "30", "output": "default"}}}}], "response": "Playing Sajni at volume 30."}}

User: "Coldplay bajao aur light neeli kar do"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Coldplay"}}}}, {{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Playing Coldplay with blue lights."}}

User: "romantic mode laga do with some music"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "romantic"}}}}, {{"intent": "music_play", "params": {{"query": "romantic Hindi songs"}}}}], "response": "Setting romantic mood with music."}}

User: "stop the music and turn off the lights"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}, {{"intent": "light_control", "params": {{"action": "off"}}}}], "response": "Music stopped, lights off."}}
"""


def _build_enrichment_prompt(personality_music_prefs: dict = None) -> str:
    """
    Separate prompt for Step 2: query enrichment.

    Uses per-personality music prefs if available, otherwise global.
    """
    music_prefs = _build_music_preference_block(personality_music_prefs or None)

    return f"""You are a music search query enhancer.
Given a song name or music query, add the singer/artist name if you KNOW it.
If you don't know the artist, return the query unchanged.
Do NOT guess. Do NOT add movie names unless certain.

{music_prefs}

Respond with JSON: {{"enriched": "the enhanced query"}}

Examples:
"Sajni" → {{"enriched": "Sajni Arijit Singh"}}
"Channa Mereya" → {{"enriched": "Channa Mereya Arijit Singh"}}
"Starboy" → {{"enriched": "Starboy The Weeknd"}}
"Bohemian Rhapsody" → {{"enriched": "Bohemian Rhapsody Queen"}}
"romantic Hindi songs" → {{"enriched": "romantic Hindi songs"}}
"Coldplay" → {{"enriched": "Coldplay"}}
"some random song I don't know" → {{"enriched": "some random song I don't know"}}
"""


@register("brain", "ollama")
class OllamaBrainProvider(BrainProvider):
    """Ollama-backed brain. Talks to a local Ollama server."""

    def __init__(self, model: str = None, endpoint: str = None, **kwargs):
        brain_config = config.get("brain", {})
        self.model = model or brain_config.get("model", "llama3.2:3b")
        self.endpoint = endpoint or brain_config.get("endpoint", "http://localhost:11434")
        self.temperature = brain_config.get("temperature", 0.3)
        # Prompts are NOT cached — they rebuild each call to reflect the active personality.
        # _build_system_prompt() and _build_enrichment_prompt() read from personality_manager.active.

    def generate(self, prompt: str, system: str = "", json_mode: bool = False,
                 temperature: float = None) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature or self.temperature},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        start = time.time()
        resp = requests.post(f"{self.endpoint}/api/generate", json=payload)
        latency = time.time() - start

        data = resp.json()
        text = data.get("response", "").strip()
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 1)
        tok_per_sec = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0

        return LLMResponse(
            text=text,
            model=self.model,
            latency=latency,
            tokens_generated=eval_count,
            tokens_per_second=tok_per_sec,
            raw=data,
        )

    def classify_intent(self, user_input: str) -> list[Intent]:
        resp = self.generate(
            prompt=user_input,
            system=_build_system_prompt(),
            json_mode=True,
            temperature=self.temperature,
        )

        meta = {
            "model": resp.model,
            "latency": resp.latency,
            "tok_per_sec": resp.tokens_per_second,
        }

        try:
            parsed = json.loads(resp.text)
        except json.JSONDecodeError:
            log.warning("LLM returned invalid JSON, falling back to chat. Raw: %s", resp.text)
            return [Intent(
                name="chat",
                params={"message": user_input},
                response="",
                confidence=0.0,
                meta={**meta, "error": "json_parse_failed", "raw": resp.text},
            )]

        response = parsed.get("response", "")

        # New format: {"intents": [...], "response": "..."}
        if "intents" in parsed and isinstance(parsed["intents"], list):
            return [
                Intent(
                    name=i.get("intent", "chat"),
                    params=i.get("params", {}),
                    response=response,
                    confidence=1.0,
                    meta=meta,
                )
                for i in parsed["intents"]
            ] or [Intent(name="chat", params={"message": user_input}, response="", meta=meta)]

        # Backward compat: old format {"intent": "...", "params": {...}, "response": "..."}
        return [Intent(
            name=parsed.get("intent", "chat"),
            params=parsed.get("params", {}),
            response=response,
            confidence=1.0,
            meta=meta,
        )]

    def enrich_query(self, raw_query: str) -> str:
        """
        Step 2: Enrich a music query with artist/context.

        Separate from classification so that:
          - Classification extracts clean params ("Sajni", not "Sajni Arijit Singh")
          - Enrichment adds artist when confident ("Sajni" → "Sajni Arijit Singh")
          - The raw query is always available for fallback search
        """
        # Use per-personality music prefs if available
        p = personality_manager.active
        enrichment_prompt = _build_enrichment_prompt(p.music_preferences)

        resp = self.generate(
            prompt=raw_query,
            system=enrichment_prompt,
            json_mode=True,
            temperature=0.2,  # lower temp = more conservative
        )

        try:
            parsed = json.loads(resp.text)
            enriched = parsed.get("enriched", raw_query)
            if enriched != raw_query:
                log.debug('Enriched "%s" → "%s"', raw_query, enriched)
            return enriched
        except json.JSONDecodeError:
            log.warning("Enrichment returned invalid JSON, using raw query. Raw: %s", resp.text)
            return raw_query  # enrichment failed, return original

    def list_models(self) -> list[str]:
        resp = requests.get(f"{self.endpoint}/api/tags")
        return [m["name"] for m in resp.json().get("models", [])]
