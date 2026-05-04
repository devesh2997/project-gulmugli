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


# Module-level recent context — set once at startup by set_conversation_context()
_recent_context: str = ""


# ── Intent JSON-schema enforcement ──────────────────────────────────
#
# llama3.2:3b's classification baseline scored 44% on our hard test suite
# because the model treated `## Intents` as a suggestion list and invented
# its own names: `joke_teller` instead of `chat`, `weather_report` instead
# of `weather`, `sound_play` instead of `ambient`, `bollywood_quiz` instead
# of `quiz`, etc. Ollama 0.5+ accepts a JSON Schema as the `format` value
# (https://ollama.com/blog/structured-outputs) — when provided, the
# generation is mathematically constrained: tokens that would violate the
# schema get zero probability and can't be sampled. The model literally
# CANNOT return an intent name outside this enum.
#
# This is the single most important fix for the intent suite. Adding new
# intents = add to this list. Removing any value here is a breaking change
# for `core/intent_handler.py`'s dispatch.

_VALID_INTENTS = [
    "music_play", "music_control", "volume", "light_control",
    "switch_personality", "chat", "system", "weather",
    "knowledge_search", "memory_recall", "memory_stats", "sleep",
    "quiz", "youtube_search", "reminder", "story", "timer", "ambient",
    # Event-pack intents — manually firing the active event's launch
    # sequence (birthday surprise, Diwali kickoff, etc.). NLU-classified,
    # not regex-locked. See events/<pack>/pack.yaml → trigger.manual_phrases
    # for the per-pack training examples the prompt seeds with.
    "event_trigger",
    # Astha jokes — a year-round mode that delivers silly questions /
    # puns / phasaa-do gotchas. Triggered by phrasings like
    # "Astha-style joke", "phasaa do mujhe", "Astha mode". Distinct
    # from `chat`-mode jokes (generic one-liners): astha_jokes is a
    # specific bait-and-switch *style*. Corpus lives at
    # events/astha-birthday/jokes/astha_jokes.yaml.
    "astha_jokes",
    # Birthday quiz — playful "how well does Vesper know us" mini-game
    # with a heartfelt recorded reveal at the end. Hand-curated
    # questions about Astha live at events/astha-birthday/quiz/about_us.yaml.
    # Distinct from the generic `quiz` intent (LLM-generated trivia):
    # this is finite, relationship-themed, and reveal-anchored.
    "birthday_quiz",
    # Yaadein — full-screen photo slideshow on the dashboard with
    # captions in Hinglish. Voice-triggered by "show me memories" /
    # "yaadein dikhao" / "photos chalu karo" / "slideshow start karo".
    # Photos + captions live at events/<pack>/media/photos/captions.yaml.
    # The slideshow ends when photos exhaust OR the user says
    # `yaadein_stop` ("slideshow band karo" / "stop yaadein").
    "yaadein_show",
    "yaadein_stop",
    # Sorry mode — apology channel from project_ag. Plays a recorded
    # apology voice memo + queues a calming playlist. Phrases:
    # "Vesper, sorry shona", "Vesper, sorry mode", "Vesper, naraz mat ho".
    "sorry_mode",
    # Besura — Devesh's pre-recorded singing clips. Phrases:
    # "Vesper, sing for me", "Devesh ki gaane sunao", "play besura".
    "besura_play",
    # Voice memo recall by topic — different from `birthday_quiz` (a
    # game) and from `astha_jokes` (humor). These are letters from
    # Devesh accessed by mood/topic. Phrases: "Devesh ne kuch chhoda
    # hai mere liye?", "agar main udaas hoon", "Devesh ka birthday
    # message".
    "voice_memo_play",
    # Sing happy birthday — plays the personalized recording for the
    # active event subject. Phrases: "sing happy birthday", "Astha ke
    # liye happy birthday gaao".
    "sing_happy_birthday",
    # Memory recall scoped to a past event/year. Distinct from
    # generic memory_recall (which searches free-form): this surfaces
    # interactions tagged with `event:<id>` + `year:<YYYY>`. Phrases:
    # "last year mere birthday pe kya kiya tha?", "remind me of last
    # birthday", "what did we do on Diwali last year?".
    "memory_recall_event",
    # Explicit memory log — Astha proactively asks Vesper to remember
    # something. Stored as a tagged interaction; recallable later via
    # memory_recall. Phrases: "Vesper, remember that I love biryani",
    # "Vesper, log this: [text]", "Vesper, yaad rakhna ki Devesh ke
    # papa ka birthday June 12 hai".
    "memory_log",
]

_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intents": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": _VALID_INTENTS},
                    # `params` stays loose — each intent has its own param
                    # schema and we don't want to multiply schema complexity.
                    # Strict per-intent action enums are handled by the
                    # post-classify normalization below.
                    "params": {"type": "object"},
                },
                "required": ["intent"],
            },
        },
        # Free-form spoken acknowledgement; for `chat` intents, this is the
        # actual reply.
        "response": {"type": "string"},
    },
    "required": ["intents"],
}


# Synonym → canonical mapping for the `action` param within each intent.
# The prompt already says "skip" includes "next", but the model still
# sometimes echoes the user's word. We normalize here so handlers in
# core/intent_handler.py only ever see canonical action names.
_ACTION_SYNONYMS = {
    "music_control": {
        "next": "skip", "next_song": "skip", "next_track": "skip",
        "forward": "skip", "play": "resume", "continue": "resume",
        "halt": "stop", "end": "stop",
    },
    "light_control": {
        # The model loves "dim" / "adjust" — both mean brightness in
        # production. "Increase" / "decrease" we leave for context.
        "dim": "brightness", "adjust": "brightness", "set": "brightness",
        "set_brightness": "brightness", "change_brightness": "brightness",
        "change": "color", "set_color": "color",
        # Cross-intent leakage we've seen: model sometimes puts
        # "volume" as a light action. Map to a sensible default.
        "volume": "brightness",
    },
}


# Per-intent default action when the model returns an empty/missing one.
# Observed model failure mode: produces `intent: ambient, params: {}` for
# "play rain sounds" — schema didn't require `action`, model didn't fill
# it. We default to the most common action so handlers can still dispatch.
_DEFAULT_ACTIONS = {
    "ambient": "play",
    "sleep": "sleep",   # "good night" — default to sleep, not wake
    "music_control": "pause",  # bare "music control" → pause is safest
    "story": "start",
}


def _normalize_intent(name: str, params: dict) -> tuple[str, dict]:
    """
    Apply synonym → canonical normalization on the action param + fill
    in default actions for intents where the model left it empty.

    Returns (intent_name, normalized_params). Pure function — does not mutate
    its inputs. We keep this defensive even with JSON-schema enforcement
    because the schema constrains intent names but not param values.
    """
    if not isinstance(params, dict):
        return name, {}

    new = dict(params)

    # Synonym normalization
    syn_table = _ACTION_SYNONYMS.get(name, {})
    if syn_table:
        action = new.get("action")
        if isinstance(action, str) and action.lower() in syn_table:
            new["action"] = syn_table[action.lower()]

    # Default action — only when missing/empty AND the intent has a
    # known sensible default
    default_action = _DEFAULT_ACTIONS.get(name)
    if default_action:
        action = new.get("action")
        if not isinstance(action, str) or not action.strip():
            new["action"] = default_action

    return name, new


def set_conversation_context(memory_provider) -> None:
    """
    Load recent interactions from memory and cache as a compact context string.
    Called once at startup from build_assistant() in main.py.
    """
    global _recent_context
    if not memory_provider:
        return
    try:
        recent = memory_provider.get_recent(limit=5)
        if not recent:
            return
        lines = []
        for mem in reversed(recent):  # oldest first
            # mem.content is a formatted string like "User asked to play Sajni"
            summary = mem.content[:100] if mem.content else ""
            if summary:
                lines.append(f"- {summary}")
        if lines:
            _recent_context = "Recent conversation:\n" + "\n".join(lines)
            log.debug("Loaded %d recent interactions for context", len(lines))
    except Exception as e:
        log.debug("Could not load conversation context: %s", e)


def _build_system_prompt() -> str:
    """
    Build the classification system prompt.

    Called fresh each time because the active personality can change.
    The personality's tone is injected so the LLM's response text
    matches the character, but the intent extraction logic stays stable.
    """
    p = personality_manager.active

    context_section = f"\n\n## Recent Context\n{_recent_context}" if _recent_context else ""

    return f"""You are {p.display_name}, a smart voice assistant used in India. {p.tone}{context_section}

Your ONLY job is to classify the user's spoken request into structured intents.
Extract parameters EXACTLY as the user said them. Do NOT modify, translate, or enrich song names.
The user speaks in English, Hindi, or Hinglish. You must understand all three.

Respond with valid JSON only. No explanation. No markdown.

## CRITICAL — disambiguation rules (read before classifying)

These are the most common confusions. Resolve them in this order:

1. **Time of day** ("what time is it", "kitna baj raha hai") → `system` action="time".
   NOT `timer` (timer is for "set a 5 minute timer").
   NOT `chat`.

2. **Date** ("what day is it", "aaj kya date hai", "today's date") → `system` action="date".

3. **Weather** is its own intent — ALWAYS use `weather`, never `knowledge_search`,
   even though weather is "current information":
   - "what's the weather", "weather kaisi hai", "mausam kaisa hai",
     "is it raining", "temperature", "barish hogi kya" → `weather`.
   - "weather in Tokyo", "Delhi ka mausam" → `weather` with location.

4. **Volume vs ambient sounds — read the words carefully:**
   - "awaaz kam karo", "awaaz badhao", "volume up/down" → `volume`. The
     word "awaaz" means "sound/voice volume" here, NOT ambient noise.
   - "rain sounds", "thunderstorm", "white noise", "ocean sounds",
     "fireplace", "barish ki awaaz" (this exact phrase = rain sound),
     "sleep sounds" → `ambient`.
   - When in doubt: if the user is controlling EXISTING audio output
     it's `volume` or `music_control`. If they want to START a new
     environmental sound it's `ambient`.

5. **Music vs ambient — songs always win**:
   - Bare song name or "play <X>" / "<X> bajao" / "<X> sunaa do" /
     "<X> sunna hai" / "<X> lagao" — where X is a recognizable song
     name or artist — is ALWAYS `music_play` with query=X. Examples:
     "Heeriye sunaa do" → music_play(query="Heeriye"),
     "Pasoori bajao yaar" → music_play(query="Pasoori"),
     "play Sajni" → music_play(query="Sajni"),
     "Tum Hi Ho lagao" → music_play(query="Tum Hi Ho").
   - "play something nice", "play music", "play some song" →
     `music_play` (vague but real music intent).
   - ONLY use `ambient` when the user explicitly asked for a nature /
     relaxation / noise sound (rain, ocean, white noise, fireplace).
   - A NAME (proper noun) is almost always a song. If you don't
     recognize it, default to music_play, NOT chat.

6. **Stories** vs **jokes**:
   - "tell me a story", "ek kahani sunao", "bedtime story" → `story`.
   - "tell me a joke", "ek joke sunao", "make me laugh" → `chat` (the
     personality replies with the joke in the `response` field).

7. **Knowledge search** vs **chat**:
   - Time-sensitive ("current", "latest", "today", "this week", "abhi")
     about real-world facts → `knowledge_search`.
   - Stable knowledge ("what is photosynthesis", "explain gravity",
     "tell me about the Mughal empire") → `chat` — the LLM knows it.
   - "Who is the current prime minister of UK" → `knowledge_search`.
   - "Who was the first PM of India" → `chat` (historical, stable).

8. **Memory recall** vs **knowledge search**:
   - About what the USER did with the assistant before → `memory_recall`.
   - About facts in the world → `knowledge_search` or `chat`.

9. **Personality switch** vs **chat**:
   - User says "talk like X", "switch to X", "be X", "X bana de", "X mode",
     "act like X", where X is one of {_get_personality_names_for_prompt()}.
   - DO NOT reply in character first — return `switch_personality` with
     the matching name. Replying as the new character is the system's
     job after the switch, not the classifier's.

10. **Reminder** vs **timer**:
    - Reminder = action at a specific time/date with a description.
    - Timer = countdown duration without a description ("5 minute timer").
    - "Remind me in 2 hours to check the oven" → `reminder` (has
      a description "check the oven").
    - "yaad dilana" / "yaad rakhna" / "remind me" / "reminder set karo"
      → `reminder`. NOT `memory_recall`. memory_recall is asking ABOUT
      the past; reminder is creating a future notification.

10b. **"X mode" with a scene word** ("study mode", "party mode",
    "sleep mode", "movie mode", "reading mode", "focus mode",
    "romantic mode", "sunset mode") → `light_control` action="scene".
    NOT `switch_personality`. switch_personality is ONLY for the
    listed personality names.

11. **NEGATIONS DO NOT CHANGE INTENT.** "don't turn off the lights"
    is `chat` (the user is making conversation about lights, not
    asking you to turn them off). "stop being annoying" is `chat`,
    NOT `music_control`. Treat negated commands as chat by default.

12. **False-friend traps — these are CHAT, not commands:**
    - "let's play it safe" → chat (idiom)
    - "lights, camera, action" → chat (movie cliché)
    - "I love this song" → chat (reaction)
    - "play with the dog/baby/kids" → chat (the verb is for an
      activity, not music)
    - "I'm tired" → chat (statement of state, not a sleep command)

13. **CHAINS — capture EVERY action.** When the user says multiple
    things separated by "and", ",", or "then", return ALL intents in
    the array, in the order spoken. Do not stop after the first.

    Examples:
      "stop music and turn off lights"
      → 2 intents: music_control(stop) AND light_control(off)

      "play Heeriye and dim the lights to 30 percent"
      → 2 intents: music_play("Heeriye") AND light_control(brightness, 30)

      "switch to Devesh and tell me a joke"
      → 2 intents: switch_personality(devesh) AND chat("tell me a joke")

      "stop the music, turn off the lights, and set an alarm for 7am"
      → 3 intents: music_control(stop) AND light_control(off) AND timer(set_alarm, 07:00)

      "set volume to 30, switch to Chandler, and play Channa Mereya"
      → 3 intents: volume(30) AND switch_personality(chandler) AND music_play("Channa Mereya")

    Three intents at once is normal. Don't truncate.

14. **Volume direction:** "up", "louder", "badhao" → 80. "down",
    "softer", "kam karo" → 30. "a bit down" / "thoda kam" still means
    DOWN — pick 30, not 70.

15. **Fall back to chat** when nothing else fits. Better to chat than
    invent.

## Intents (signature reference)

- `music_play` — params: {{"query": <song/artist/mood string>, "with_video": true|false}}
  Extract the user's words as-is. Don't enrich. Strip "play"/"bajao"/"sunao".
  with_video=true only when the user says "video", "with video", "video chalao".

- `music_control` — params: {{"action": "pause"|"resume"|"skip"|"stop"}}
  "next"/"agle gaane"/"change the song"/"dusra gaana" all map to "skip".

- `volume` — params: {{"level": "0..100", "output": "default"}}
  up/badhao→80, down/kam karo→30. Even "a bit down" = 30.

- `light_control` — params: {{"action": "on"|"off"|"brightness"|"color"|"scene", "value": <string>}}
  Scenes: romantic, movie, party, sleep, reading, sunset, focus, study.
  "warm white" / "cool white" → action="color", value="warm white".

- `switch_personality` — params: {{"personality": <id>}}
  Valid ids: {_get_personality_names_for_prompt()}.
  "talk like X"/"X mode"/"X bana de"/"act like X". Don't reply in character; just emit the switch.

- `chat` — params: {{"message": <user's exact words>}} + non-empty `response` for short replies.
  Catch-all for jokes, factoids, opinions, idioms, reactions ("I love this song"),
  stable knowledge, negated commands ("don't turn off the lights"). Leave `response`
  empty for long-form (essay, story, etc.) — system handles.

- `system` — params: {{"action": "time"|"date"|"alarm"|"reminder"}}
  ALWAYS for "what time is it"/"kitna baj raha hai"/"what's the date".

- `weather` — params: {{"query": "current"|"forecast"|"rain"|"temperature", "location": <opt>}}
  ALL weather questions, even "current". Never knowledge_search.

- `knowledge_search` — params: {{"query": <english search string>}}
  Real-world facts that change over time: current PM, latest score, today's
  news, this week's events. Stable knowledge → `chat`.

- `memory_recall` — params: {{"query": <topic>}}
  About the USER's past interactions ("what did I play yesterday"). Trim filler.
  "yaad hai" = past interactions. "yaad dilana" = future reminder (use `reminder`).

- `memory_stats` — params: {{}}. "how much do you remember", "kitna yaad hai tujhe".

- `sleep` — params: {{"action": "sleep"|"wake"}}
  sleep: "good night", "sleep mode", "sone ja". wake: "good morning", "wake up", "jag ja".

- `quiz` — params: {{"action": "start"|"answer"|"hint"|"score"|"quit",
                     "category": "general|bollywood|movies|music|geography|tech|food|cricket",
                     "difficulty": "easy|medium|hard", "answer": <text>}}.

- `youtube_search` — params: {{"query": <terms>}}. Only when user says "youtube" / "yt pe".

- `reminder` — params: {{"action": "add"|"cancel"|"list"|"snooze",
                         "text": <description>, "time": "HH:MM"|"in N hours",
                         "date": "today"|"tomorrow"|"YYYY-MM-DD",
                         "repeat": "none"|"daily"|"weekly"|"monthly"}}.

- `story` — params: {{"action": "start"|"continue"|"stop", "genre": <genre|null>,
                      "topic": <text|null>}}.
  Don't write the story in `response` — leave it brief.

- `timer` — params: {{"action": "set_timer"|"set_alarm"|"cancel"|"snooze"|"list",
                      "duration": <seconds>, "time": "HH:MM",
                      "label": <opt>, "repeat": "none"|"daily"|"weekdays"}}.
  Timer = duration. Alarm = clock time. Convert minutes→seconds.

- `ambient` — params: {{"action": "play"|"stop"|"volume",
                        "sound": "rain"|"ocean"|"thunderstorm"|"white_noise"|"pink_noise"|"brown_noise"|"fireplace"|"forest"|"birds"|"wind"|"cafe"|"fan",
                        "level": 0..100}}.
  Nature/relaxation sounds ONLY. NEVER for music or volume control.

- `event_trigger` — params: {{}}. Used to manually fire a special-day
  launch sequence (birthday surprise, festival kickoff, etc.). Phrases
  are deliberately codename-y and unusual: "project AG begins",
  "ek surprise hai", "light it up", "kick it off", "<assistant>, shuru
  karo". These phrases ONLY make sense as triggers — they never look
  like a chat or song request. When in doubt about a generic phrase
  ("start", "begin"), prefer `chat` instead.

- `astha_jokes` — params: {{}}. The "tell silly jokes like Astha would"
  mode. Triggered by phrasings like "Astha-style joke sunao", "phasaa
  do mujhe", "Astha mode chalu karo", "tell me jokes like Astha", "do
  that thing Astha does", "silly questions". Distinct from `chat`
  joke requests: a plain "tell me a joke" stays in `chat` (generic
  one-liner); only phrasings that explicitly invoke Astha's style or
  the phasaa-do/silly-question pattern map to this.

- `birthday_quiz` — params: {{}}. The hand-curated "how well does Vesper
  know us" relationship quiz, ending with a heartfelt recorded reveal.
  Triggered by phrasings like "birthday quiz khelte hain", "ek game
  khelte hain", "quiz me on us", "kitna jaanti ho mujhe", "let's play
  the birthday game". DISTINCT from the generic `quiz` intent (which
  is open-domain LLM trivia): birthday_quiz only fires when the user
  invokes the relationship/birthday/"about us" framing, OR an explicit
  "birthday quiz" wording. A bare "let's play a quiz" with no relationship
  hint stays in generic `quiz`. Bare "ek game khelte hain" leans
  birthday_quiz.

- `yaadein_show` — params: {{}}. Starts the full-screen photo slideshow
  ("yaadein") on the dashboard. Triggered by "mujhe yaadein dikhao",
  "show me memories", "photos chalu karo", "slideshow start karo",
  "memories dikhao", "tasveerein dikhao". The word "yaadein" (Hindi for
  "memories") is the strongest signal — when present, this intent wins
  even over generic media verbs like "show". A bare "show me photos"
  with no other context maps here. NOT `music_play` (no song requested).
  NOT `chat` (the user wants the slideshow surface, not a conversation).

- `yaadein_stop` — params: {{}}. Ends the slideshow. Triggered by
  "slideshow band karo", "stop yaadein", "memories band karo",
  "yaadein bandh karo", "close the slideshow", "exit yaadein". A bare
  "stop" while NO slideshow is running stays as `music_control`
  (action="stop") — context here is the literal yaadein/slideshow word
  in the utterance, not the standalone verb.

- `sorry_mode` — params: {{}}. Apology channel — plays a recorded
  apology memo from Devesh + queues a calming playlist. Triggered by
  "Vesper, sorry shona", "Vesper, sorry mode", "Vesper, naraz mat ho",
  "Vesper, mujhe sorry bol". Distinct from `chat` apologies (which are
  generic): this maps to the dedicated personality channel and plays
  pre-recorded audio.

- `besura_play` — params: {{}}. Plays one of Devesh's recorded singing
  clips. Triggered by "Vesper, sing for me", "Devesh ki gaane sunao",
  "play besura", "Devesh ka gaana lagao". Distinct from `music_play`
  (which searches YouTube): this is the personal-recording channel.

- `voice_memo_play` — params: {{"topic": <string, optional>}}. Plays
  a recorded voice memo from Devesh, optionally filtered by topic
  (sad / birthday / love / etc.). Triggered by "Devesh ne kuch chhoda
  hai mere liye?", "Devesh ka message sunao", "agar main udaas hoon"
  (topic="sad"), "Devesh ka birthday message" (topic="birthday").

- `sing_happy_birthday` — params: {{}}. Plays the personalized
  happy-birthday recording. Triggered by "sing happy birthday",
  "Astha ke liye happy birthday gaao", "happy birthday gaa do".

- `memory_recall_event` — params: {{"event_id": <opt>, "year": <opt int>}}.
  Recalls interactions from a past event-day. Triggered by phrasings
  that explicitly reference both a specific event AND a past time:
  "last year mere birthday pe kya kiya tha", "what did we do on my
  birthday last year", "Diwali pe pichle saal kya hua tha". A bare
  "what did I play yesterday" stays as `memory_recall` (free-form);
  this intent is event-scoped specifically.

- `memory_log` — params: {{"text": <string, the thing to remember>}}.
  Astha asks Vesper to explicitly remember something. The text param
  is what to store. Triggered by "Vesper, remember that <X>", "Vesper,
  log this: <X>", "Vesper, yaad rakhna ki <X>", "Vesper, ye yaad
  rakh: <X>". Distinct from `chat`: chat is a conversation; this is
  a write-to-memory action. The classifier extracts the user's `<X>`
  payload into `text`, NOT including the trigger phrase.

## Format
{{"intents": [{{"intent": "...", "params": {{...}}}}], "response": "<short ack in character>"}}

A single conversational request is ONE chat intent (e.g. "tell me a joke and a riddle"
= one chat). Multiple intents only for genuinely separate actions.

## Response tone
{p.tone}

The `response` field MUST be in the SAME language the user used (English/Hindi/Hinglish — romanized Hindi is fine). One short sentence.

## Few-shot examples (covers the trickiest patterns)

User: "play Sajni"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni", "with_video": false}}}}], "response": "Playing Sajni."}}

# Bare song-name input (no "play" prefix) is STILL music_play.
User: "Channa Mereya"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Channa Mereya", "with_video": false}}}}], "response": "Playing Channa Mereya."}}

User: "Gerua"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Gerua", "with_video": false}}}}], "response": "Playing Gerua."}}

User: "Heeriye sunaa do"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Heeriye", "with_video": false}}}}], "response": "Playing Heeriye."}}

User: "Sajni ka video lagao"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni", "with_video": true}}}}], "response": "Playing Sajni video."}}

User: "skip this one"
{{"intents": [{{"intent": "music_control", "params": {{"action": "skip"}}}}], "response": "Skipping."}}

User: "study mode laga do"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "study"}}}}], "response": "Study mode on."}}

User: "tell me a joke"
{{"intents": [{{"intent": "chat", "params": {{"message": "tell me a joke"}}}}], "response": "Why don't scientists trust atoms? Because they make up everything."}}

User: "what time is it"
{{"intents": [{{"intent": "system", "params": {{"action": "time"}}}}], "response": ""}}

User: "what's the weather like"
{{"intents": [{{"intent": "weather", "params": {{"query": "current"}}}}], "response": ""}}

User: "good night"
{{"intents": [{{"intent": "sleep", "params": {{"action": "sleep"}}}}], "response": "Good night, sleep well."}}

User: "play rain sounds"
{{"intents": [{{"intent": "ambient", "params": {{"action": "play", "sound": "rain"}}}}], "response": "Rain sounds."}}

User: "remind me in 2 hours to check the oven"
{{"intents": [{{"intent": "reminder", "params": {{"action": "add", "text": "check the oven", "time": "in 2 hours"}}}}], "response": "I'll remind you in 2 hours."}}

User: "let's play it safe"
{{"intents": [{{"intent": "chat", "params": {{"message": "let's play it safe"}}}}], "response": "Sure, playing it safe."}}

User: "stop music and turn off lights"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}, {{"intent": "light_control", "params": {{"action": "off"}}}}], "response": "Music stopped, lights off."}}

User: "play Sajni and set the lights to red"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni", "with_video": false}}}}, {{"intent": "light_control", "params": {{"action": "color", "value": "red"}}}}], "response": "Playing Sajni with red lights."}}

User: "set volume to 30, switch to Chandler, and play Channa Mereya"
{{"intents": [{{"intent": "volume", "params": {{"level": "30", "output": "default"}}}}, {{"intent": "switch_personality", "params": {{"personality": "chandler"}}}}, {{"intent": "music_play", "params": {{"query": "Channa Mereya", "with_video": false}}}}], "response": "Volume 30, Chandler mode, playing Channa Mereya."}}
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

        # keep_alive controls how long Ollama keeps the model loaded in GPU/RAM
        # after the last request. Default values in Ollama land:
        #   "5m"  → unload after 5 min idle (Ollama default)
        #   "-1"  → never unload (keeps the model hot forever)
        #   <int> → seconds (e.g., 600 = 10 min)
        #
        # On Jetson 8GB shared NvMap, "-1" is dangerous: the model's KV
        # cache fragments NvMap over hours of use until allocations fail
        # ("llama runner process has terminated"). A periodic unload-reload
        # gives the allocator a clean slate. Cost: 5-15s reload on next
        # request after the idle window, which is fine — voice assistant
        # users don't notice an occasional long warm-up if they've been
        # away for 10 min.
        #
        # 600s (10 min) is the sweet spot: user chatting through a
        # conversation never sees a reload; overnight idle resets state
        # cleanly. Tunable via config.brain.keep_alive.
        self._keep_alive = brain_config.get("keep_alive", 600)

        # Reusable HTTP session — avoids TCP handshake + connection setup per request.
        # On localhost this saves ~2-5ms per call, which adds up across
        # classify + enrich + chat (3 calls per interaction).
        self._session = requests.Session()

        # Prompts are NOT cached — they rebuild each call to reflect the active personality.
        # _build_system_prompt() and _build_enrichment_prompt() read from personality_manager.active.

        # NOTE: warm-up is deferred — call self.warm_up() explicitly AFTER
        # other CUDA-using providers (e.g. faster-whisper on Jetson) have
        # claimed their memory. On the 8GB Jetson, the LLM's ~2GB allocation
        # combined with Whisper's ~250MB on the same NvMap pool can fragment
        # memory if loaded in the wrong order. Loading Whisper first (small
        # contiguous chunk), then the LLM (large chunk in remaining contiguous
        # space), keeps both happy. On Mac / discrete GPU machines, order
        # doesn't matter — but the deferred call still works there.

    def warm_up(self):
        """
        Force Ollama to load the model into memory AND pre-process the
        long classifier system prompt so its KV cache is hot.

        Why this matters: Ollama's prompt processing is ~0.5 ms/token on
        Jetson. Our classifier system prompt is ~24,000 characters (~6,000
        tokens) — that's ~3 seconds of prompt processing on every cold
        request. If we pre-send the prompt with `num_predict=1`, Ollama
        keeps the KV cache for those 6,000 tokens around (controlled by
        OLLAMA_KEEP_ALIVE). Next request that reuses the same prefix gets
        the cache hit instead of reprocessing — dropping classifier TTFT
        from ~3-4 s to ~1 s.

        For the chat fast-path, we also warm the smaller model with its
        own short system prompt so first-token latency on chat queries
        stays consistent.
        """
        # 1. Default model + classifier prompt
        try:
            log.info("Warming up Ollama model %s...", self.model)
            start = time.time()
            classifier_prompt = _build_system_prompt()
            self._session.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "hi",
                    "system": classifier_prompt,
                    "stream": False,
                    "keep_alive": self._keep_alive,
                    "options": {"num_predict": 1},
                },
                timeout=120,  # large prompt + first model load
            )
            elapsed = time.time() - start
            log.info("Ollama %s warm (%.1fs, classifier prompt cached).",
                     self.model, elapsed)
        except Exception as e:
            log.warning("Ollama warm-up failed: %s. First request will be slow.", e)

        # 2. Chat fast-path model — warm it too. Default matches voice.py
        # so the first chat-fast request doesn't pay model-load cost.
        from core.config import config as _cfg
        chat_fast_model = _cfg.get("brain", {}).get(
            "chat_fast_model", "qwen2.5:1.5b"
        )
        if chat_fast_model and chat_fast_model != self.model:
            try:
                log.info("Warming up chat-fast model %s...", chat_fast_model)
                start = time.time()
                self._session.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": chat_fast_model,
                        "prompt": "hi",
                        "system": (
                            "You are a helpful voice assistant. Reply concisely."
                        ),
                        "stream": False,
                        "keep_alive": self._keep_alive,
                        "options": {"num_predict": 1},
                    },
                    timeout=120,
                )
                elapsed = time.time() - start
                log.info("Ollama %s warm (%.1fs).", chat_fast_model, elapsed)
            except Exception as e:
                log.warning("Chat-fast model warm-up failed: %s.", e)

    def generate_stream(self, prompt: str, system: str = "", json_mode: bool = False,
                        temperature: float = None, max_tokens: int | None = None,
                        model: str | None = None):
        """
        Stream tokens from Ollama as they're generated. Yields strings (not chunks
        of bytes) — each yield is the new text since the last yield.

        `model` overrides the configured default for this single call. We use
        this to route the chat fast-path to a smaller model (e.g.,
        qwen2.5:1.5b) for ~3x lower TTFT, while keeping intent classification
        on the more accurate llama3.2:3b.

        This is what powers /api/voice's "stream first sentence to TTS while the
        model is still generating" pattern. Total wall time isn't reduced, but
        time-to-first-audio drops dramatically because we don't wait for the
        full reply before starting synthesis.

        After the generator exhausts, the final iteration's value (caught via
        StopIteration.value) is the LLMResponse with timing metadata. Most
        callers can ignore it; the streaming consumer cares about the tokens.
        """
        options = {"temperature": temperature or self.temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        chosen_model = model or self.model
        payload = {
            "model": chosen_model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": self._keep_alive,
            "options": options,
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        # NB: streaming path doesn't support format_schema yet — none of our
        # streaming consumers (chat reply path) need strict schema validation.
        # If they ever do, route through a non-streaming call instead.

        start = time.time()
        # stream=True keeps the response open as a chunked HTTP stream.
        # Timeout tuple: (connect, read). Large generous read timeout — 90s
        # — because streaming generation can legitimately take that long
        # for a chat reply on Jetson 8B-shared. But ANY timeout is critical:
        # without one, an Ollama wedge (NvMap fragmentation, CUDA driver
        # hang — both observed on Jetson) blocks every pipeline worker
        # forever and the entire intent executor dies.
        resp = self._session.post(
            f"{self.endpoint}/api/generate",
            json=payload, stream=True, timeout=(5, 90),
        )
        full_text = ""
        eval_count = 0
        eval_duration = 0
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            try:
                chunk = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            piece = chunk.get("response", "")
            if piece:
                full_text += piece
                yield piece
            if chunk.get("done"):
                eval_count = chunk.get("eval_count", 0)
                eval_duration = chunk.get("eval_duration", 1)
                break
        latency = time.time() - start
        # Stash final stats on the generator for the caller to retrieve via
        # `.gi_frame.f_locals` in tests if they care, but the primary contract
        # is the yielded tokens.
        return LLMResponse(
            text=full_text,
            model=chosen_model,
            latency=latency,
            tokens_generated=eval_count,
            tokens_per_second=(eval_count * 1e9 / eval_duration) if eval_duration > 0 else 0,
            raw={"streamed": True},
        )

    def generate(self, prompt: str, system: str = "", json_mode: bool = False,
                 temperature: float = None, max_tokens: int | None = None,
                 format_schema: dict | None = None) -> LLMResponse:
        """
        Generate a response from the LLM.

        max_tokens: hard cap on output length (Ollama's `num_predict`). The model
            stops generating after this many tokens. Use this for chat-style replies
            on edge hardware to keep latency bounded — at 22 tok/s on Jetson, an
            80-token cap means the chat call returns in <4s no matter how chatty
            the model wants to be. None = no cap (default).

        format_schema: a JSON Schema dict (Ollama 0.5+ feature). When provided,
            Ollama constrains the model output to match the schema — `enum`
            fields literally cannot produce values outside the enum, `required`
            fields are guaranteed present. Takes precedence over `json_mode`.
            We use this for classify_intent so the model can't invent new
            intent names like "joke_teller" or "weather_report" that aren't
            in our 17-intent dispatch table.
        """
        options = {"temperature": temperature or self.temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        # Force a 4096-token context. Ollama's default is 2048, which
        # silently truncates our classification system prompt (currently
        # ~7700 tokens after the disambiguation block was added). When
        # the bottom of the prompt is dropped, the model loses critical
        # routing rules and falls back to surface-word matching against
        # the truncated head — observed Jetson pass rate drop from 91%
        # to 51%. 4096 fits everything with headroom; KV cache memory
        # cost is ~480MB extra on llama3.2:3b, well within Jetson's
        # 8GB shared memory.
        options.setdefault("num_ctx", 4096)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": options,
        }
        if system:
            payload["system"] = system
        if format_schema is not None:
            payload["format"] = format_schema
        elif json_mode:
            payload["format"] = "json"

        start = time.time()
        # Same rationale as the streaming path: bounded read timeout
        # so a wedged Ollama can't pin pipeline workers indefinitely.
        # 60s read covers worst-case classify (cold KV cache + max
        # output) on Jetson at ~22 tok/s; chat-fast generations hit
        # the per-call num_predict cap (typically 60-200 tokens) so
        # they finish in well under the budget.
        resp = self._session.post(
            f"{self.endpoint}/api/generate",
            json=payload, timeout=(5, 60),
        )
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
        # max_tokens=200 caps the classifier output. The JSON itself is
        # ~30-60 tokens; the embedded chat "response" field is the variable
        # part. 200 is enough for a 1-2 sentence chat reply (~120-150 tokens
        # of reply text + ~50 tokens of JSON overhead). On Jetson at 22 tok/s
        # this caps classification at ~9s in the worst case (verbose chat).
        #
        # format_schema=_INTENT_SCHEMA forces the output to conform — the
        # `intent` field can only be one of the 17 valid names. This single
        # change addresses ~30 of the 50 failures in the intent test suite
        # baseline (model used to invent names like `joke_teller`,
        # `weather_report`, `sound_play`, etc.).
        # Lower temperature for classification — we want deterministic
        # intent picks, not creative ones. Chat replies inside chat
        # intents come from a separate generation path with a higher
        # temperature, so the classifier being deterministic doesn't
        # make conversation feel robotic.
        resp = self.generate(
            prompt=user_input,
            system=_build_system_prompt(),
            format_schema=_INTENT_SCHEMA,
            temperature=0.1,
            max_tokens=200,
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
            intents = []
            for i in parsed["intents"]:
                # Coerce malformed param values to dict so handlers don't crash
                raw_params = i.get("params", {})
                if not isinstance(raw_params, dict):
                    raw_params = {}
                # Apply synonym → canonical normalization on action param
                canon_name, canon_params = _normalize_intent(
                    i.get("intent", "chat"), raw_params
                )
                intents.append(Intent(
                    name=canon_name,
                    params=canon_params,
                    response=response,
                    confidence=1.0,
                    meta=meta,
                ))
            if not intents:
                intents = [Intent(name="chat", params={"message": user_input},
                                  response="", meta=meta)]

            # Defensive: if the LLM returned multiple chat intents, merge them.
            # A single conversational request should never be split into two
            # chat intents — that causes duplicate responses (e.g., two stories).
            chat_intents = [i for i in intents if i.name == "chat"]
            non_chat_intents = [i for i in intents if i.name != "chat"]
            if len(chat_intents) > 1:
                log.warning(
                    "LLM returned %d chat intents — merging into one. "
                    "This usually means the classifier over-split a single request.",
                    len(chat_intents),
                )
                merged_chat = Intent(
                    name="chat",
                    params={"message": user_input},  # use original input, not LLM output
                    response=response,
                    confidence=1.0,
                    meta=meta,
                )
                intents = non_chat_intents + [merged_chat]

            return intents

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

        Pipeline:
          1. Curated enrichment hint (`core.song_corrections.enrichment_hint`).
             Hits known-difficult cases like "Pasoori" (Coke Studio
             original loses YT popularity to a Bollywood remake of a
             different song) by hardcoding a verified enrichment. Skips
             the LLM call entirely on hit, saving ~2s.
          2. LLM enrichment fallback — same as before, low temperature.

        Note: STT-mishear correction (`correct_title`) is intentionally
        applied UPSTREAM in `core/intent_handler.py` rather than here,
        so that BOTH the enriched query AND the raw_input passed to the
        dual search use the corrected title. Otherwise the raw search
        runs on the misheard string and lands on a wrong-language song
        ("hayriye" → Turkish "Fıldır Fıldır Hayriye").
        """
        from core.song_corrections import enrichment_hint

        if not raw_query:
            return raw_query

        # Stage 1: explicit enrichment hint for known-difficult cases.
        hint = enrichment_hint(raw_query)
        if hint:
            log.debug('Enrichment hint: "%s" → "%s"', raw_query, hint)
            return hint

        # Stage 2: LLM enrichment.
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
            return raw_query

    def list_models(self) -> list[str]:
        # Short timeout: this is a metadata call (cheap on Ollama's side),
        # used for healthcheck and one-off CLI listing — failing fast is
        # better than blocking on a hung daemon.
        resp = self._session.get(f"{self.endpoint}/api/tags", timeout=(3, 10))
        return [m["name"] for m in resp.json().get("models", [])]
