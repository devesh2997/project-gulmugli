"""
Keyword pre-filter for instant intent resolution.

This is the FIRST line of defense before the LLM even sees the input.
Pattern-based matching resolves obvious commands in <1ms, bypassing the
LLM entirely. The LLM is only called for ambiguous inputs.

Why this matters for latency:
  - LLM classification takes 1-3 seconds (Mac) or 3-6 seconds (Jetson)
  - "pause", "volume 50", "lights off" don't NEED an LLM
  - This handles ~40-60% of real-world commands at near-zero cost
  - The remaining ambiguous commands still go to the LLM

Architecture:
  - Each pattern returns a list[Intent] (same as brain.classify_intent)
  - If no pattern matches, returns None → caller falls through to LLM
  - Patterns are intentionally conservative — false negatives are fine
    (the LLM catches them), false positives are NOT (wrong action taken)
  - All regex is case-insensitive and handles Hindi/Hinglish equivalents

Adding new patterns:
  - Add a function that takes user_input and returns list[Intent] or None
  - Register it in PREFILTER_CHAIN
  - Test it in the test suite — if it ever misclassifies, remove it
"""

import re
import time
from core.interfaces import Intent
from core.logger import get_logger

log = get_logger("core.prefilter")


# ─── Pattern matchers ──────────────────────────────────────────────
# Each returns list[Intent] on match, None on no match.
# Order matters: more specific patterns first.

def _match_music_control(text: str) -> list[Intent] | None:
    """Match unambiguous playback control commands."""
    t = text.strip().lower()

    # Pause
    if re.fullmatch(r"(pause|pause (the )?(music|song|gaana))", t):
        return [Intent(name="music_control", params={"action": "pause"},
                       response="Paused.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Resume / continue — only match explicit resume words, NOT bare "play"
    # (bare "play" is ambiguous — could mean resume OR "play something")
    if re.fullmatch(r"(resume|continue)", t):
        return [Intent(name="music_control", params={"action": "resume"},
                       response="Resuming.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Stop
    if re.fullmatch(r"(stop|stop (the )?(music|song|gaana)|gaana (band|rok|stop) (karo?|do))", t):
        return [Intent(name="music_control", params={"action": "stop"},
                       response="Stopped.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Skip / next
    if re.fullmatch(
        r"(skip|skip (this )?(one|song|track)|"
        r"next|next (song|track|one)|"
        r"agl[ae] (gaana|song|track)|"
        r"dusra gaana|"
        r"change the song)",
        t,
    ):
        return [Intent(name="music_control", params={"action": "skip"},
                       response="Skipping.", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_volume(text: str) -> list[Intent] | None:
    """Match unambiguous volume commands."""
    t = text.strip().lower()

    # Explicit level: "volume 50", "volume 50%"
    m = re.fullmatch(r"volume\s+(\d{1,3})%?", t)
    if m:
        level = int(m.group(1))
        if level > 100:
            return None  # out of range — let the LLM handle it conversationally
        return [Intent(name="volume", params={"level": str(level), "output": "default"},
                       response=f"Volume set to {level}.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Relative: "volume up", "volume down", "awaaz badha/kam"
    if re.fullmatch(r"(volume up|awaaz badha(o| do)?|loud(er)?)", t):
        return [Intent(name="volume", params={"level": "80", "output": "default"},
                       response="Volume up.", confidence=1.0,
                       meta={"source": "prefilter"})]

    if re.fullmatch(r"(volume down|awaaz kam (karo?|do)|quiet(er)?)", t):
        return [Intent(name="volume", params={"level": "30", "output": "default"},
                       response="Volume down.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Mute
    if re.fullmatch(r"(mute|mute (the )?(volume|sound|audio)|awaaz band (karo?|do))", t):
        return [Intent(name="volume", params={"level": "0", "output": "default"},
                       response="Muted.", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_lights_simple(text: str) -> list[Intent] | None:
    """Match unambiguous light on/off commands."""
    t = text.strip().lower()

    # Lights off
    if re.fullmatch(
        r"(lights? off|turn off (the )?lights?|"
        r"batti band (karo?|do)|light band (karo?|do)|"
        r"lights? (band|off) (karo?|do))",
        t,
    ):
        return [Intent(name="light_control", params={"action": "off"},
                       response="Lights off.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Lights on
    if re.fullmatch(
        r"(lights? on|turn on (the )?lights?|"
        r"batti (jala(o)?|on (karo?|do))|light on (karo?|do)|"
        r"lights? (on|jala(o)?) (karo?|do)?)",
        t,
    ):
        return [Intent(name="light_control", params={"action": "on"},
                       response="Lights on.", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_video_music(text: str) -> list[Intent] | None:
    """
    Detect "with video" / "video mein" / "video mode" / "video chalao" in music requests.

    When detected, return a music_play intent with with_video: true and the
    video-related phrase stripped from the query.
    """
    t = text.strip().lower()

    # Patterns that signal video mode in a music request.
    # Each tuple: (regex pattern to strip, whether the remainder is the query)
    video_suffixes = [
        r"\s+with\s+video$",
        r"\s+video\s+mein$",
        r"\s+video\s+mode$",
        r"\s+ka\s+video\s+(lagao|chalao|dikha(o)?)$",
        r"\s+ka\s+video$",
    ]
    video_prefixes = [
        r"^video\s+chalao\s+",
        r"^video\s+lagao\s+",
        r"^video\s+baja(o)?\s+",
    ]

    # Check for "play X with video" style (suffix patterns)
    # Must start with a play-like trigger or be a bare query + video suffix
    play_prefixes = r"^(play\s+|baja(o)?\s+|laga(o)?\s+)?"
    for pat in video_suffixes:
        m = re.match(play_prefixes + r"(.+?)" + pat, t)
        if m:
            # The query is the captured group (everything between play-prefix and video-suffix)
            query = m.group(m.lastindex).strip() if m.lastindex else ""
            # Also strip leading play words from the query
            query = re.sub(r"^(play\s+|baja(o)?\s+|laga(o)?\s+)", "", query).strip()
            if query:
                return [Intent(name="music_play",
                               params={"query": query, "with_video": True},
                               response=f"Playing {query} with video.",
                               confidence=1.0,
                               meta={"source": "prefilter"})]

    # Check for "video chalao X" style (prefix patterns)
    for pat in video_prefixes:
        m = re.match(pat + r"(.+)$", t)
        if m:
            query = m.group(m.lastindex).strip()
            if query:
                return [Intent(name="music_play",
                               params={"query": query, "with_video": True},
                               response=f"Playing {query} with video.",
                               confidence=1.0,
                               meta={"source": "prefilter"})]

    return None


def _match_system(text: str) -> list[Intent] | None:
    """Match unambiguous system queries."""
    t = text.strip().lower()

    if re.fullmatch(r"(what time is it|what'?s the time|time (bata(o)?|kya hai)|kitne baje hain?)", t):
        return [Intent(name="system", params={"action": "time"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    if re.fullmatch(r"(what'?s the date|what date is it|aaj (kya )?date (hai|bata(o)?)|aaj kya (tarikh|taareekh) hai)", t):
        return [Intent(name="system", params={"action": "date"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_quiz(text: str) -> list[Intent] | None:
    """Match unambiguous quiz commands."""
    t = text.strip().lower()

    # Start quiz: "play quiz", "quiz khelna hai", "trivia start", "let's play a game", "quiz chalao"
    if re.fullmatch(
        r"(play\s+quiz|play\s+trivia|quiz\s+(khelna?\s+hai|chalao|start|shuru\s+karo?)|"
        r"trivia\s+start|let'?s\s+play\s+(a\s+)?game|start\s+(a\s+)?quiz|"
        r"quiz\s+khel(te|na)\s+hain?)",
        t,
    ):
        return [Intent(name="quiz", params={"action": "start"},
                       response="Let's play!", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Quit quiz: "quit quiz", "stop quiz", "quiz band karo", "end quiz"
    if re.fullmatch(
        r"(quit\s+quiz|stop\s+quiz|end\s+quiz|exit\s+quiz|"
        r"quiz\s+band\s+(karo?|do)|quiz\s+(stop|quit|end))",
        t,
    ):
        return [Intent(name="quiz", params={"action": "quit"},
                       response="Quiz ended.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Score: "score", "my score", "kitne aaye", "quiz score"
    # Only match during active quiz — check lazily via import
    if re.fullmatch(r"(my\s+score|quiz\s+score|kitne\s+aa?ye|score\s+bata(o)?|score)", t):
        try:
            # Lazy check: only match if quiz is actually active
            # This prevents "score" from matching when no quiz is running
            from core.intent_handler import _quiz_is_active
            if _quiz_is_active():
                return [Intent(name="quiz", params={"action": "score"},
                               response="", confidence=1.0,
                               meta={"source": "prefilter"})]
        except (ImportError, AttributeError):
            pass

    # Hint: "hint", "clue", "give me a hint" — only during active quiz
    if re.fullmatch(r"(hint|clue|give\s+me\s+a\s+hint|hint\s+do|hint\s+de\s+do)", t):
        try:
            from core.intent_handler import _quiz_is_active
            if _quiz_is_active():
                return [Intent(name="quiz", params={"action": "hint"},
                               response="", confidence=1.0,
                               meta={"source": "prefilter"})]
        except (ImportError, AttributeError):
            pass

    return None


def _match_youtube_search(text: str) -> list[Intent] | None:
    """Match unambiguous YouTube search commands."""
    t = text.strip().lower()

    # "search X on youtube", "youtube search X", "search X on yt"
    m = re.match(r"search\s+(.+?)\s+on\s+(youtube|yt)$", t)
    if m:
        query = m.group(1).strip()
        if query:
            return [Intent(name="youtube_search", params={"query": query},
                           response=f"Opening YouTube search for {query}.",
                           confidence=1.0, meta={"source": "prefilter"})]

    m = re.match(r"(youtube|yt)\s+search\s+(.+)$", t)
    if m:
        query = m.group(2).strip()
        if query:
            return [Intent(name="youtube_search", params={"query": query},
                           response=f"Opening YouTube search for {query}.",
                           confidence=1.0, meta={"source": "prefilter"})]

    # "youtube pe X dhundho/search karo"
    m = re.match(r"(youtube|yt)\s+pe\s+(.+?)\s+(dhundho|search\s+karo?|khojo)$", t)
    if m:
        query = m.group(2).strip()
        if query:
            return [Intent(name="youtube_search", params={"query": query},
                           response=f"Opening YouTube search for {query}.",
                           confidence=1.0, meta={"source": "prefilter"})]

    # "X youtube pe dhundho"
    m = re.match(r"(.+?)\s+(youtube|yt)\s+pe\s+(dhundho|search\s+karo?|khojo)$", t)
    if m:
        query = m.group(1).strip()
        if query:
            return [Intent(name="youtube_search", params={"query": query},
                           response=f"Opening YouTube search for {query}.",
                           confidence=1.0, meta={"source": "prefilter"})]

    return None


def _match_sleep(text: str) -> list[Intent] | None:
    """Match unambiguous sleep/wake commands."""
    t = text.strip().lower()

    # Sleep
    if re.fullmatch(
        r"(good\s*night|sleep mode|go to sleep|sone? ja|so ja)",
        t,
    ):
        return [Intent(name="sleep", params={"action": "sleep"},
                       response="Good night, sleep well.",
                       confidence=1.0,
                       meta={"source": "prefilter"})]

    # Wake
    if re.fullmatch(
        r"(good\s*morning|wake up|jag ja|uth ja)",
        t,
    ):
        return [Intent(name="sleep", params={"action": "wake"},
                       response="Good morning! Ready when you are.",
                       confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


# ─── Chain of matchers ─────────────────────────────────────────────
# Tried in order. First match wins.
# IMPORTANT: Only include patterns where we're 100% confident.
# If there's any ambiguity, let the LLM handle it.
PREFILTER_CHAIN = [
    _match_sleep,
    _match_quiz,
    _match_youtube_search,
    _match_video_music,
    _match_music_control,
    _match_volume,
    _match_lights_simple,
    _match_system,
]


def prefilter_intent(user_input: str) -> list[Intent] | None:
    """
    Try to resolve the user's input via keyword/regex patterns.

    Returns:
        list[Intent] if a pattern matched (bypass the LLM)
        None if no pattern matched (fall through to LLM)
    """
    start = time.time()

    # Strip trailing punctuation that STT adds — "What's the time?" → "What's the time"
    # This prevents fullmatch failures on otherwise-matching patterns.
    cleaned = re.sub(r'[.!?]+$', '', user_input.strip())

    for matcher in PREFILTER_CHAIN:
        result = matcher(cleaned)
        if result is not None:
            elapsed_ms = (time.time() - start) * 1000
            intent_names = " + ".join(i.name for i in result)
            log.debug(
                "Pre-filter matched: [%s] in %.1fms (skipping LLM)",
                intent_names, elapsed_ms,
            )
            return result

    return None
