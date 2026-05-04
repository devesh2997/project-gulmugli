"""
Intent classification test suite.

Tests that the LLM correctly classifies user inputs into the right intent type
with correct parameters, across English, Hindi, and Hinglish inputs.

IMPORTANT: Test inputs must NOT overlap with examples in the system prompt.
The system prompt has "Sajni", "Channa Mereya", "Starboy", etc. — we test
with DIFFERENT songs/commands so we're measuring generalization, not memorization.

## Difficulty tiers
Each test case carries a `tier` field. Tiers reflect what we're really
measuring:

  - "easy"   — single, clear intent in plain language. Baseline competence.
               If the model fails these, the system prompt is broken or the
               model is too small. (~28 cases)
  - "medium" — Hinglish code-mixing, polite/verbose phrasing, slot-filling,
               simple 2-step chains, less-common synonyms. Tests whether
               the model handles real Indian-user speech, not just textbook
               examples. (~32 cases)
  - "hard"   — adversarial pattern-traps, indirect requests, false friends
               ("play it safe" → chat, NOT music_play), 3-step chains,
               negations, edge numerics, STT-style mangled inputs, intent
               boundaries (chat vs knowledge_search vs system). The
               threshold separating "good enough for a demo" from "good
               enough to live with daily." (~30 cases)

The runner reports per-tier pass rates so a regression in hard cases isn't
hidden by easy-case wins.

## Tags
Optional `tags` list for filtering / focused debugging:
  - "hinglish"      — code-mixed Hindi+English
  - "polite"        — verbose / "could you" / "please" forms
  - "negation"      — contains negation that changes intent
  - "false-friend"  — surface looks like one intent, semantics another
  - "chain"         — multi-intent in one utterance
  - "edge-numeric"  — extreme volume/brightness values
  - "stt-artifact"  — common Whisper mishears
  - "boundary"      — sits on the chat/knowledge/system boundary
  - "indirect"      — implicit request (no imperative verb)
  - "modern"        — post-2020 catalog (often outside training data)
"""

import time
from collections import defaultdict

from core.logger import get_logger

log = get_logger("tests.intent")


# Each test: dict with keys: input, intent, params, desc, tier, tags (optional)
# - intent: str OR list[str] (for chains — order doesn't matter, all must be present)
# - params: dict of {param_name: expected_value_or_callable}.
#   Callable form: lambda v: True/False. Use this for fuzzy matching.
# - tier: "easy" | "medium" | "hard"
# - tags: list[str], optional

INTENT_TESTS = [
    # ════════════════════════════════════════════════════════════════
    #   EASY — baseline competence
    # ════════════════════════════════════════════════════════════════

    # ── Music Play ──────────────────────────────────────────────
    # Bare song names without verbs are NOT expected to classify as music_play —
    # the user must say "play X" or "X bajao" so playback isn't accidental.
    {
        "input": "play Husn by Anuv Jain",
        "intent": "music_play",
        "params": {"query": lambda v: "husn" in v.lower()},
        "desc": "Indian indie song with artist",
        "tier": "easy",
    },
    {
        "input": "play something by Prateek Kuhad",
        "intent": "music_play",
        "params": {"query": lambda v: "prateek" in v.lower() or "kuhad" in v.lower()},
        "desc": "Indie artist request",
        "tier": "easy",
    },
    {
        "input": "play Do I Wanna Know",
        "intent": "music_play",
        "params": {"query": lambda v: "wanna know" in v.lower()},
        "desc": "Alt rock song (Arctic Monkeys) — conversational title",
        "tier": "easy",
    },

    # ── Music Control ───────────────────────────────────────────
    {
        "input": "pause the music",
        "intent": "music_control",
        "params": {"action": "pause"},
        "desc": "Pause in English",
        "tier": "easy",
    },
    {
        "input": "gaana rok do",
        "intent": "music_control",
        "params": {"action": lambda v: v in ("pause", "stop")},
        "desc": "Pause/stop in Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },
    {
        "input": "next song please",
        "intent": "music_control",
        "params": {"action": "skip"},
        "desc": "Skip in English",
        "tier": "easy",
    },
    {
        "input": "resume",
        "intent": "music_control",
        "params": {"action": "resume"},
        "desc": "Resume — single word",
        "tier": "easy",
    },

    # ── Volume ──────────────────────────────────────────────────
    {
        "input": "volume 40",
        "intent": "volume",
        "params": {"level": lambda v: str(v).strip("%") == "40"},
        "desc": "Explicit volume level",
        "tier": "easy",
    },
    {
        "input": "awaaz kam karo",
        "intent": "volume",
        "params": {"level": lambda v: int(str(v).strip("%")) < 50},
        "desc": "Volume down in Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Light Control ───────────────────────────────────────────
    {
        "input": "turn off the lights",
        "intent": "light_control",
        "params": {"action": "off"},
        "desc": "Lights off in English",
        "tier": "easy",
    },
    {
        "input": "light ka colour green karo",
        "intent": "light_control",
        "params": {"action": "color", "value": lambda v: "green" in v.lower()},
        "desc": "Color in Hinglish",
        "tier": "easy",
        "tags": ["hinglish"],
    },
    {
        "input": "study mode laga do",
        "intent": "light_control",
        "params": {"action": "scene", "value": lambda v: "study" in v.lower()},
        "desc": "Scene in Hinglish",
        "tier": "easy",
        "tags": ["hinglish"],
    },
    {
        "input": "brightness 30 percent",
        "intent": "light_control",
        "params": {"action": "brightness"},
        "desc": "Brightness in English",
        "tier": "easy",
    },

    # ── Switch Personality ──────────────────────────────────────
    {
        "input": "switch to Chandler mode",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "chandler" in v.lower()},
        "desc": "Personality switch English",
        "tier": "easy",
    },
    {
        "input": "Devesh ban ja",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "devesh" in v.lower()},
        "desc": "Personality switch Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Chat ────────────────────────────────────────────────────
    {
        "input": "tell me a joke",
        "intent": "chat",
        "params": {},
        "desc": "Chat — joke request",
        "tier": "easy",
    },
    {
        "input": "what is machine learning",
        "intent": "chat",
        "params": {},
        "desc": "Chat — knowledge question (LLM trained on this — should NOT be knowledge_search)",
        "tier": "easy",
        "tags": ["boundary"],
    },

    # ── System ──────────────────────────────────────────────────
    {
        "input": "what time is it",
        "intent": "system",
        "params": {"action": "time"},
        "desc": "System time English",
        "tier": "easy",
    },
    {
        "input": "aaj kya date hai",
        "intent": "system",
        "params": {"action": "date"},
        "desc": "System date Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Memory ──────────────────────────────────────────────────
    {
        "input": "what songs did I play today",
        "intent": "memory_recall",
        "params": {"query": lambda v: len(v) > 0},
        "desc": "Memory recall English",
        "tier": "easy",
    },
    {
        "input": "kitna yaad hai tujhe",
        "intent": "memory_stats",
        "params": {},
        "desc": "Memory stats Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Knowledge Search ────────────────────────────────────────
    {
        "input": "who is the current prime minister of UK",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "prime minister" in v.lower() or "uk" in v.lower()},
        "desc": "Knowledge — current affairs English",
        "tier": "easy",
    },
    {
        "input": "aaj India mein kya news hai",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "india" in v.lower() or "news" in v.lower()},
        "desc": "Knowledge — news Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Weather ─────────────────────────────────────────────────
    {
        "input": "what's the weather like",
        "intent": "weather",
        "params": {},
        "desc": "Weather plain English",
        "tier": "easy",
    },
    {
        "input": "mausam kaisa hai",
        "intent": "weather",
        "params": {},
        "desc": "Weather Hindi",
        "tier": "easy",
        "tags": ["hinglish"],
    },

    # ── Timer / Reminder ────────────────────────────────────────
    {
        "input": "set a timer for five minutes",
        "intent": "timer",
        "params": {"action": "set_timer", "duration": lambda v: int(v) == 300},
        "desc": "Timer English with word-number",
        "tier": "easy",
    },
    {
        "input": "remind me to call mom at 5pm",
        "intent": "reminder",
        "params": {"action": "add", "text": lambda v: "mom" in v.lower()},
        "desc": "Reminder add English",
        "tier": "easy",
    },

    # ── Ambient ─────────────────────────────────────────────────
    {
        "input": "play rain sounds",
        "intent": "ambient",
        "params": {"action": "play", "sound": "rain"},
        "desc": "Ambient — explicit",
        "tier": "easy",
    },

    # ════════════════════════════════════════════════════════════════
    #   MEDIUM — real-world phrasing
    # ════════════════════════════════════════════════════════════════

    # ── Hinglish music ──────────────────────────────────────────
    {
        "input": "kuch lo-fi type bajao yaar",
        "intent": "music_play",
        "params": {"query": lambda v: "lo-fi" in v.lower() or "lofi" in v.lower()},
        "desc": "Hinglish mood request (lo-fi genre)",
        "tier": "medium",
        "tags": ["hinglish"],
    },
    {
        "input": "Choo Lo laga do The Local Train wala",
        "intent": "music_play",
        "params": {"query": lambda v: "choo lo" in v.lower() or "local train" in v.lower()},
        "desc": "Indie rock song in Hinglish",
        "tier": "medium",
        "tags": ["hinglish"],
    },
    {
        "input": "When Chai Met Toast ka Firefly laga do",
        "intent": "music_play",
        "params": {"query": lambda v: "firefly" in v.lower() or "chai" in v.lower()},
        "desc": "Kerala indie-folk band specific song in Hinglish",
        "tier": "medium",
        "tags": ["hinglish"],
    },
    {
        "input": "Heeriye sunaa do",
        "intent": "music_play",
        "params": {"query": lambda v: "heeriye" in v.lower() or "heeriy" in v.lower()},
        "desc": "Recent (2023) Hindi song in Hinglish",
        "tier": "medium",
        "tags": ["hinglish", "modern"],
    },
    {
        "input": "Pasoori bajao",
        "intent": "music_play",
        "params": {"query": lambda v: "pasoori" in v.lower()},
        "desc": "Coke Studio Pakistan crossover hit",
        "tier": "medium",
        "tags": ["hinglish", "modern"],
    },
    {
        "input": "AUR ka Tu Hai Kahaan lagao",
        "intent": "music_play",
        "params": {"query": lambda v: "tu hai kahaan" in v.lower() or "aur" in v.lower()},
        "desc": "Pakistani indie band, recent",
        "tier": "medium",
        "tags": ["hinglish", "modern"],
    },
    {
        "input": "Brahmastra ka koi gaana lagao",
        "intent": "music_play",
        "params": {"query": lambda v: "brahmastra" in v.lower()},
        "desc": "Movie-name as music query (Hinglish)",
        "tier": "medium",
        "tags": ["hinglish"],
    },

    # ── Polite / verbose ────────────────────────────────────────
    {
        "input": "could you please turn down the volume a bit",
        "intent": "volume",
        "params": {"level": lambda v: int(str(v).strip("%")) < 50},
        "desc": "Polite volume down (verbose)",
        "tier": "medium",
        "tags": ["polite"],
    },
    {
        "input": "if you don't mind, can you play something nice and chill",
        "intent": "music_play",
        "params": {"query": lambda v: len(v) > 0},
        "desc": "Polite indirect music request",
        "tier": "medium",
        "tags": ["polite", "indirect"],
    },
    {
        "input": "hey would you mind dimming the lights",
        "intent": "light_control",
        "params": {"action": lambda v: v in ("brightness", "dim", "scene", "off")},
        "desc": "Polite dim (no exact level)",
        "tier": "medium",
        "tags": ["polite"],
    },

    # ── Slot-filling / unusual order ────────────────────────────
    {
        "input": "set the lights to red",
        "intent": "light_control",
        "params": {"action": "color", "value": lambda v: "red" in v.lower()},
        "desc": "Light color, common form",
        "tier": "medium",
    },
    {
        "input": "make the room a warm white",
        "intent": "light_control",
        "params": {"action": "color", "value": lambda v: "warm" in v.lower() or "white" in v.lower()},
        "desc": "Light color, indirect ('make the room')",
        "tier": "medium",
        "tags": ["indirect"],
    },
    {
        "input": "lights at twenty percent",
        "intent": "light_control",
        "params": {"action": "brightness", "value": lambda v: "20" in str(v)},
        "desc": "Brightness with word-number",
        "tier": "medium",
    },

    # ── Synonyms / less common phrasings ────────────────────────
    {
        "input": "skip this one",
        "intent": "music_control",
        "params": {"action": "skip"},
        "desc": "Skip with 'this one'",
        "tier": "medium",
    },
    {
        "input": "agle gaane pe jao",
        "intent": "music_control",
        "params": {"action": "skip"},
        "desc": "Skip in Hindi",
        "tier": "medium",
        "tags": ["hinglish"],
    },
    {
        "input": "shut down the music",
        "intent": "music_control",
        "params": {"action": lambda v: v in ("stop", "pause")},
        "desc": "Stop with informal verb",
        "tier": "medium",
    },
    {
        "input": "kill the lights",
        "intent": "light_control",
        "params": {"action": "off"},
        "desc": "Lights off — colloquial verb",
        "tier": "medium",
    },

    # ── Knowledge boundary ──────────────────────────────────────
    {
        "input": "what's the latest score in the IPL match",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "ipl" in v.lower() or "score" in v.lower()},
        "desc": "Sports score = knowledge_search",
        "tier": "medium",
        "tags": ["boundary"],
    },
    {
        "input": "explain quantum entanglement",
        "intent": "chat",
        "params": {},
        "desc": "General knowledge = chat (LLM has it)",
        "tier": "medium",
        "tags": ["boundary"],
    },
    {
        "input": "who won the Oscar for Best Picture this year",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "oscar" in v.lower() or "best picture" in v.lower()},
        "desc": "Time-sensitive trivia = knowledge_search",
        "tier": "medium",
        "tags": ["boundary"],
    },
    {
        "input": "tell me about the Mughal empire",
        "intent": "chat",
        "params": {},
        "desc": "History = chat (LLM has it)",
        "tier": "medium",
        "tags": ["boundary"],
    },

    # ── Personality / wake-related ──────────────────────────────
    {
        "input": "talk like Chandler from now on",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "chandler" in v.lower()},
        "desc": "Personality, longer phrasing",
        "tier": "medium",
    },
    {
        "input": "default mode pe wapas aa ja",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "jarvis" in v.lower() or "default" in v.lower()},
        "desc": "Reset to default in Hinglish",
        "tier": "medium",
        "tags": ["hinglish"],
    },

    # ── Story / quiz / ambient ──────────────────────────────────
    {
        "input": "tell me a bedtime story about a dragon",
        "intent": "story",
        "params": {"action": "start", "topic": lambda v: "dragon" in (v or "").lower()},
        "desc": "Story with topic — should NOT be chat",
        "tier": "medium",
    },
    {
        "input": "let's play a Bollywood quiz, hard difficulty",
        "intent": "quiz",
        "params": {
            "action": "start",
            "category": lambda v: "bollywood" in v.lower(),
            "difficulty": lambda v: v == "hard",
        },
        "desc": "Quiz with category + difficulty",
        "tier": "medium",
    },
    {
        "input": "thunderstorm sounds for sleep",
        "intent": "ambient",
        "params": {"action": "play", "sound": lambda v: "thunder" in v.lower() or "rain" in v.lower()},
        "desc": "Ambient — non-default sound",
        "tier": "medium",
    },

    # ── Reminder / Timer with relative time ─────────────────────
    {
        "input": "remind me in two hours to check the oven",
        "intent": "reminder",
        "params": {"action": "add", "text": lambda v: "oven" in v.lower()},
        "desc": "Reminder with relative time",
        "tier": "medium",
    },
    {
        "input": "yaad dilana 8 baje medicine leni hai",
        "intent": "reminder",
        "params": {"action": "add", "time": lambda v: "8" in str(v) or "20:00" in str(v)},
        "desc": "Reminder Hindi 24h-ish",
        "tier": "medium",
        "tags": ["hinglish"],
    },

    # ── Simple chains ───────────────────────────────────────────
    {
        "input": "play Husn and set lights to warm white",
        "intent": ["music_play", "light_control"],
        "params": {},
        "desc": "Chained: indie song + lights",
        "tier": "medium",
        "tags": ["chain"],
    },
    {
        "input": "stop music and turn off lights",
        "intent": ["music_control", "light_control"],
        "params": {},
        "desc": "Chained: stop + lights off",
        "tier": "medium",
        "tags": ["chain"],
    },
    {
        "input": "switch to Devesh and tell me a joke",
        "intent": ["switch_personality", "chat"],
        "params": {},
        "desc": "Chained: personality + chat",
        "tier": "medium",
        "tags": ["chain"],
    },

    # ════════════════════════════════════════════════════════════════
    #   HARD — adversarial / boundary / multi-step
    # ════════════════════════════════════════════════════════════════

    # ── False friends — surface looks like X but means Y ────────
    {
        "input": "let's play it safe",
        "intent": "chat",
        "params": {},
        "desc": "Idiom 'play it safe' — must NOT trigger music_play",
        "tier": "hard",
        "tags": ["false-friend"],
    },
    {
        "input": "lights, camera, action",
        "intent": "chat",
        "params": {},
        "desc": "Movie cliché — must NOT trigger light_control",
        "tier": "hard",
        "tags": ["false-friend"],
    },
    {
        "input": "stop being so dramatic",
        "intent": "chat",
        "params": {},
        "desc": "Conversational 'stop' — must NOT trigger music_control",
        "tier": "hard",
        "tags": ["false-friend"],
    },
    {
        "input": "I love this song",
        "intent": "chat",
        "params": {},
        "desc": "Reaction — must NOT trigger music_play",
        "tier": "hard",
        "tags": ["false-friend"],
    },
    {
        "input": "play with the dog",
        "intent": "chat",
        "params": {},
        "desc": "'play' as verb but no music — must NOT trigger music_play",
        "tier": "hard",
        "tags": ["false-friend"],
    },

    # ── Indirect / no imperative verb ───────────────────────────
    {
        "input": "I'm tired",
        "intent": "chat",
        "params": {},
        "desc": "Statement of state — should be chat, NOT a command",
        "tier": "hard",
        "tags": ["indirect", "boundary"],
    },
    {
        "input": "this music is too loud",
        "intent": lambda v: v in ("volume", "chat"),
        "params": {},
        "desc": "Implicit volume request — either volume OR chat is acceptable, but NOT music_control",
        "tier": "hard",
        "tags": ["indirect"],
    },

    # ── Negations that should NOT swap intent ───────────────────
    {
        "input": "I don't want any sad songs right now",
        "intent": lambda v: v in ("chat", "music_play"),
        "params": {},
        "desc": "Negation phrasing — chat OR music_play (mood) both reasonable",
        "tier": "hard",
        "tags": ["negation"],
    },
    {
        "input": "don't turn off the lights yet",
        "intent": "chat",
        "params": {},
        "desc": "Negated command — must NOT trigger light_control(off)",
        "tier": "hard",
        "tags": ["negation"],
    },

    # ── Edge numerics ───────────────────────────────────────────
    {
        "input": "volume zero",
        "intent": "volume",
        "params": {"level": lambda v: int(str(v).strip("%")) == 0},
        "desc": "Volume = 0 (mute via volume intent)",
        "tier": "hard",
        "tags": ["edge-numeric"],
    },
    {
        "input": "volume to one hundred",
        "intent": "volume",
        "params": {"level": lambda v: int(str(v).strip("%")) >= 90},
        "desc": "Volume max with word-number",
        "tier": "hard",
        "tags": ["edge-numeric"],
    },
    {
        "input": "set the lights to 1 percent",
        "intent": "light_control",
        "params": {"action": "brightness", "value": lambda v: "1" in str(v)},
        "desc": "Extreme low brightness",
        "tier": "hard",
        "tags": ["edge-numeric"],
    },
    {
        "input": "set a 30 second timer",
        "intent": "timer",
        "params": {"action": "set_timer", "duration": lambda v: int(v) == 30},
        "desc": "Sub-minute timer",
        "tier": "hard",
        "tags": ["edge-numeric"],
    },

    # ── STT-style mishears ──────────────────────────────────────
    {
        "input": "play kesriya",
        "intent": "music_play",
        "params": {"query": lambda v: "kes" in v.lower()},
        "desc": "Kesariya misspelled (Whisper-style 'kesriya')",
        "tier": "hard",
        "tags": ["stt-artifact", "modern"],
    },
    {
        "input": "play apna bana le piya",
        "intent": "music_play",
        "params": {"query": lambda v: "apna bana" in v.lower() or "piya" in v.lower()},
        "desc": "Modern (2022) song — Whisper transcribes more words",
        "tier": "hard",
        "tags": ["stt-artifact", "modern"],
    },
    {
        "input": "play Tum Hi Hoo",
        "intent": "music_play",
        "params": {"query": lambda v: "tum hi" in v.lower()},
        "desc": "Aashiqui 2 song — extra vowel from Whisper",
        "tier": "hard",
        "tags": ["stt-artifact"],
    },

    # ── Knowledge / chat / system boundary ──────────────────────
    {
        "input": "what's the temperature in Tokyo",
        "intent": lambda v: v in ("knowledge_search", "weather"),
        "params": {},
        "desc": "Foreign-city weather — knowledge OR weather",
        "tier": "hard",
        "tags": ["boundary"],
    },
    {
        "input": "what time is it in New York",
        "intent": lambda v: v in ("knowledge_search", "system", "chat"),
        "params": {},
        "desc": "Time in another timezone — boundary case",
        "tier": "hard",
        "tags": ["boundary"],
    },
    {
        "input": "do you remember when I asked about Pasoori",
        "intent": "memory_recall",
        "params": {"query": lambda v: "pasoori" in v.lower()},
        "desc": "Memory recall with specific past topic",
        "tier": "hard",
    },

    # ── Volume vs music_control boundary ────────────────────────
    {
        "input": "make this song softer",
        "intent": lambda v: v in ("volume", "music_control"),
        "params": {},
        "desc": "Implicit volume down — either intent acceptable",
        "tier": "hard",
        "tags": ["boundary"],
    },

    # ── 3-step chains ───────────────────────────────────────────
    {
        "input": "play Heeriye, dim the lights to 30%, and tell me a joke",
        "intent": ["music_play", "light_control", "chat"],
        "params": {},
        "desc": "3-step chain: music + lights + chat",
        "tier": "hard",
        "tags": ["chain", "modern"],
    },
    {
        "input": "set volume to 30, switch to Chandler, and play Channa Mereya",
        "intent": ["volume", "switch_personality", "music_play"],
        "params": {},
        "desc": "3-step chain — order shuffled relative to intent priority",
        "tier": "hard",
        "tags": ["chain"],
    },
    {
        "input": "stop the music, turn off the lights, set an alarm for 7am",
        "intent": ["music_control", "light_control", "timer"],
        "params": {},
        "desc": "3-step chain: stop + lights + alarm",
        "tier": "hard",
        "tags": ["chain"],
    },

    # ── Modern / post-2020 catalog ──────────────────────────────
    {
        "input": "play Maan Meri Jaan",
        "intent": "music_play",
        "params": {"query": lambda v: "maan meri jaan" in v.lower()},
        "desc": "King's 2022 hit — outside many models' training data",
        "tier": "hard",
        "tags": ["modern"],
    },
    {
        "input": "play 295 by Sidhu",
        "intent": "music_play",
        "params": {"query": lambda v: "295" in v},
        "desc": "Punjabi crossover, numeric song name",
        "tier": "hard",
        "tags": ["modern"],
    },
    {
        "input": "play Brown Munde",
        "intent": "music_play",
        "params": {"query": lambda v: "brown munde" in v.lower()},
        "desc": "AP Dhillon Punjabi crossover",
        "tier": "hard",
        "tags": ["modern"],
    },

    # ── Video request (different param) ─────────────────────────
    {
        "input": "play Heeriye with video",
        "intent": "music_play",
        "params": {
            "query": lambda v: "heeriye" in v.lower(),
            "with_video": True,
        },
        "desc": "Video flag — query must NOT contain 'with video'",
        "tier": "hard",
        "tags": ["modern"],
    },
    {
        "input": "Pasoori ka video chalao",
        "intent": "music_play",
        "params": {
            "query": lambda v: "pasoori" in v.lower() and "video" not in v.lower(),
            "with_video": True,
        },
        "desc": "Hinglish video flag — strip 'video' from query",
        "tier": "hard",
        "tags": ["hinglish", "modern"],
    },

    # ── Sleep / wake ────────────────────────────────────────────
    {
        "input": "good night",
        "intent": "sleep",
        "params": {"action": "sleep"},
        "desc": "Sleep — common phrasing",
        "tier": "hard",
        "tags": ["boundary"],
    },
    {
        "input": "wake up Jarvis",
        "intent": lambda v: v in ("sleep", "switch_personality"),
        "params": {},
        "desc": "Wake — could read as 'wake' OR personality address",
        "tier": "hard",
        "tags": ["boundary"],
    },

    # ── Quiz answer mid-flow (no quiz state, edge) ──────────────
    {
        "input": "the answer is Shah Rukh Khan",
        "intent": lambda v: v in ("quiz", "chat"),
        "params": {},
        "desc": "Bare answer — without quiz state, chat is reasonable",
        "tier": "hard",
        "tags": ["boundary"],
    },

    # ── Event trigger (manual launch of birthday / festival packs) ──
    {
        "input": "Vesper, project AG begins",
        "intent": "event_trigger",
        "params": {},
        "desc": "Codename trigger phrase from pack.yaml manual_phrases",
        "tier": "easy",
        "tags": ["event_trigger"],
    },
    {
        "input": "Vesper, ek surprise hai",
        "intent": "event_trigger",
        "params": {},
        "desc": "Hinglish trigger phrase",
        "tier": "easy",
        "tags": ["event_trigger", "hinglish"],
    },
    {
        "input": "Vesper, light it up",
        "intent": "event_trigger",
        "params": {},
        "desc": "Short codename trigger",
        "tier": "easy",
        "tags": ["event_trigger"],
    },

    # ── Astha jokes (year-round mode) ───────────────────────────
    # Hard-mode boundary: a plain "tell me a joke" must STAY in chat,
    # but anything that invokes Astha's style explicitly maps here.
    {
        "input": "Vesper, mujhe Astha jaisi joke sunao",
        "intent": "astha_jokes",
        "params": {},
        "desc": "Astha-style joke request, Hinglish",
        "tier": "easy",
        "tags": ["astha_jokes", "hinglish"],
    },
    {
        "input": "Vesper, Astha mode chalu karo",
        "intent": "astha_jokes",
        "params": {},
        "desc": "Astha mode invocation",
        "tier": "easy",
        "tags": ["astha_jokes", "hinglish"],
    },
    {
        "input": "Vesper, phasaa do mujhe",
        "intent": "astha_jokes",
        "params": {},
        "desc": "Phasaa-do verb-form invocation",
        "tier": "medium",
        "tags": ["astha_jokes", "hinglish"],
    },
    {
        "input": "tell me a joke",
        "intent": "chat",
        "params": {},
        "desc": "Generic 'tell me a joke' MUST stay chat (not astha_jokes)",
        "tier": "medium",
        "tags": ["astha_jokes", "boundary"],
    },

    # ── Birthday quiz (Phase 5.4) ───────────────────────────────
    # Hard-mode boundary: a plain "let's play a quiz" stays in generic
    # `quiz`. Only relationship-framed wording maps to `birthday_quiz`.
    {
        "input": "Vesper, birthday quiz khelte hain",
        "intent": "birthday_quiz",
        "params": {},
        "desc": "Explicit birthday-quiz invocation, Hinglish",
        "tier": "easy",
        "tags": ["birthday_quiz", "hinglish"],
    },
    {
        "input": "Vesper, quiz me on us",
        "intent": "birthday_quiz",
        "params": {},
        "desc": "Relationship-framed quiz request",
        "tier": "easy",
        "tags": ["birthday_quiz"],
    },
    {
        "input": "Vesper, kitna jaanti ho mujhe",
        "intent": "birthday_quiz",
        "params": {},
        "desc": "How-well-do-you-know-me framing → birthday quiz",
        "tier": "medium",
        "tags": ["birthday_quiz", "hinglish"],
    },

    # ── Yaadein (photo slideshow) ───────────────────────────────
    # The keyword "yaadein" or the explicit "slideshow"/"memories"
    # noun must route here; a bare "show me" or "stop" stays generic.
    {
        "input": "Vesper, mujhe yaadein dikhao",
        "intent": "yaadein_show",
        "params": {},
        "desc": "Hinglish trigger using the yaadein keyword",
        "tier": "easy",
        "tags": ["yaadein", "hinglish"],
    },
    {
        "input": "Vesper, show me memories",
        "intent": "yaadein_show",
        "params": {},
        "desc": "English trigger using the memories keyword",
        "tier": "easy",
        "tags": ["yaadein"],
    },
    {
        "input": "Vesper, slideshow start karo",
        "intent": "yaadein_show",
        "params": {},
        "desc": "Hinglish 'slideshow' invocation",
        "tier": "medium",
        "tags": ["yaadein", "hinglish"],
    },
    {
        "input": "Vesper, slideshow band karo",
        "intent": "yaadein_stop",
        "params": {},
        "desc": "Stop yaadein — Hinglish 'band karo'",
        "tier": "medium",
        "tags": ["yaadein", "hinglish"],
    },
    {
        "input": "Vesper, stop yaadein",
        "intent": "yaadein_stop",
        "params": {},
        "desc": "Stop yaadein — explicit yaadein keyword + stop",
        "tier": "easy",
        "tags": ["yaadein"],
    },
]


# ── Helpers for matching ────────────────────────────────────────────

def _intent_matches(expected, actual_name: str) -> bool:
    """Compare an expected intent (str | callable) to the actual classified name."""
    if callable(expected):
        return bool(expected(actual_name))
    return actual_name == expected


def _check_param(expected, actual) -> bool:
    """Compare a param value: callable predicate or case-insensitive string match."""
    if callable(expected):
        try:
            return bool(expected(actual))
        except Exception:
            return False
    return str(actual).lower() == str(expected).lower()


# ── Runner ──────────────────────────────────────────────────────────

def run_intent_tests(brain) -> dict:
    """Run all intent classification tests, scored overall + per-tier."""
    results = []
    total_latency = 0.0

    for test_case in INTENT_TESTS:
        user_input = test_case["input"]
        expected_intent = test_case["intent"]
        param_checks = test_case.get("params", {})
        desc = test_case["desc"]
        tier = test_case.get("tier", "easy")
        tags = test_case.get("tags", [])

        start = time.time()
        passed = False
        detail = ""

        try:
            intents = brain.classify_intent(user_input)
            latency = time.time() - start
            total_latency += latency

            if isinstance(expected_intent, list):
                # Chained: every expected intent must appear (order doesn't matter)
                actual_names = [i.name for i in intents]
                passed = all(e in actual_names for e in expected_intent)
                if not passed:
                    detail = f"expected {expected_intent}, got {actual_names}"

            else:
                actual_name = intents[0].name if intents else "none"
                # Defensive: model occasionally returns `params` as a string
                # instead of a dict. Coerce so .get() doesn't crash and we get
                # a meaningful failure message instead of an exception.
                raw_params = intents[0].params if intents else {}
                actual_params = raw_params if isinstance(raw_params, dict) else {}

                if _intent_matches(expected_intent, actual_name):
                    passed = True
                    if not isinstance(raw_params, dict) and param_checks:
                        passed = False
                        detail = (
                            f"params is {type(raw_params).__name__}, "
                            f"expected dict (got {raw_params!r})"
                        )
                    # Check parameters
                    if passed:
                        for param_name, expected_val in param_checks.items():
                            actual_val = actual_params.get(param_name, "")
                            if not _check_param(expected_val, actual_val):
                                passed = False
                                detail = (
                                    f"param '{param_name}' check failed: "
                                    f"got {actual_val!r}"
                                )
                                break

                    # Story/joke must not be split into multiple chats
                    if expected_intent == "chat" and len(intents) > 1:
                        if all(i.name == "chat" for i in intents):
                            detail = "Multiple chat intents — defensive merge missed"
                else:
                    expected_label = (
                        expected_intent
                        if isinstance(expected_intent, str)
                        else "<predicate>"
                    )
                    detail = (
                        f"expected '{expected_label}', got '{actual_name}'"
                    )
                    if intents:
                        detail += f" (params: {intents[0].params})"

        except Exception as e:
            latency = time.time() - start
            total_latency += latency
            passed = False
            detail = f"Exception: {e}"

        status = "PASS" if passed else "FAIL"
        log.info("[%s][%s] %s — %s (%.2fs)", status, tier, desc,
                 user_input[:40], latency)
        if not passed:
            log.warning("  → %s", detail)

        results.append({
            "name": desc,
            "input": user_input,
            "passed": passed,
            "latency": latency,
            "detail": detail,
            "tier": tier,
            "tags": tags,
        })

    passed_count = sum(1 for r in results if r["passed"])

    # Per-tier breakdown
    by_tier_total: dict[str, int] = defaultdict(int)
    by_tier_pass: dict[str, int] = defaultdict(int)
    by_tag_total: dict[str, int] = defaultdict(int)
    by_tag_pass: dict[str, int] = defaultdict(int)
    for r in results:
        by_tier_total[r["tier"]] += 1
        if r["passed"]:
            by_tier_pass[r["tier"]] += 1
        for tag in r.get("tags", []):
            by_tag_total[tag] += 1
            if r["passed"]:
                by_tag_pass[tag] += 1

    by_tier = {
        tier: {
            "passed": by_tier_pass[tier],
            "total": by_tier_total[tier],
            "score": (by_tier_pass[tier] / by_tier_total[tier] * 100.0)
                     if by_tier_total[tier] else 0.0,
        }
        for tier in ("easy", "medium", "hard")
        if by_tier_total[tier] > 0
    }
    by_tag = {
        tag: {
            "passed": by_tag_pass[tag],
            "total": by_tag_total[tag],
            "score": (by_tag_pass[tag] / by_tag_total[tag] * 100.0)
                     if by_tag_total[tag] else 0.0,
        }
        for tag, _ in sorted(by_tag_total.items(), key=lambda kv: -kv[1])
    }

    # Console summary so a human running this directly sees per-tier scores.
    log.info("─" * 60)
    log.info("Intent classification — per-tier")
    for tier in ("easy", "medium", "hard"):
        if tier in by_tier:
            t = by_tier[tier]
            log.info("  %-7s  %2d/%-2d  (%5.1f%%)",
                     tier, t["passed"], t["total"], t["score"])
    if by_tag:
        log.info("Top tags by case count:")
        for tag, t in list(by_tag.items())[:6]:
            log.info("  %-15s %2d/%-2d  (%5.1f%%)",
                     tag, t["passed"], t["total"], t["score"])

    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
        "by_tier": by_tier,
        "by_tag": by_tag,
    }
