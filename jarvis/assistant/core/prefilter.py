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


def _match_reminder(text: str) -> list[Intent] | None:
    """Match unambiguous reminder commands."""
    t = text.strip().lower()

    # List reminders: "list reminders", "what reminders do I have", "my reminders"
    # Hindi: "reminders dikha", "kya reminders hain"
    if re.fullmatch(
        r"(list\s+reminders?|what\s+reminders?\s+(do\s+i\s+have|are\s+there)|"
        r"my\s+reminders?|show\s+reminders?|"
        r"reminders?\s+dikha(o)?|kya\s+reminders?\s+hain?|"
        r"reminders?\s+(bata(o)?|batao))",
        t,
    ):
        return [Intent(name="reminder", params={"action": "list"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Cancel reminder: "cancel reminder", "delete reminder"
    # Hindi: "reminder cancel karo", "reminder hatao"
    if re.fullmatch(
        r"(cancel\s+(my\s+)?reminders?|delete\s+(my\s+)?reminders?|"
        r"reminders?\s+(cancel|hatao|hata\s+do|band)\s*(karo?)?)",
        t,
    ):
        return [Intent(name="reminder", params={"action": "cancel"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Add reminder with "remind me to X at Y" pattern
    m = re.match(
        r"remind\s+me\s+to\s+(.+?)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*$",
        t,
    )
    if m:
        return [Intent(name="reminder",
                       params={"action": "add", "text": m.group(1).strip(),
                               "time": m.group(2).strip(), "date": "today"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # "remind me tomorrow to X"
    m = re.match(
        r"remind\s+me\s+tomorrow\s+to\s+(.+)$",
        t,
    )
    if m:
        return [Intent(name="reminder",
                       params={"action": "add", "text": m.group(1).strip(),
                               "time": "morning", "date": "tomorrow"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # "reminder: X at Y"
    m = re.match(
        r"reminder[:\s]+(.+?)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*$",
        t,
    )
    if m:
        return [Intent(name="reminder",
                       params={"action": "add", "text": m.group(1).strip(),
                               "time": m.group(2).strip(), "date": "today"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Hindi: "yaad dilana ki 5 baje call karna hai"
    m = re.match(
        r"yaad\s+dila(?:na|o)\s+(?:ki\s+)?(\d{1,2})\s+baje\s+(.+)$",
        t,
    )
    if m:
        hour = m.group(1).strip()
        task = m.group(2).strip()
        return [Intent(name="reminder",
                       params={"action": "add", "text": task,
                               "time": f"{hour}:00", "date": "today"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Hindi: "reminder set karo X at Y"
    m = re.match(
        r"reminder\s+set\s+karo?\s+(.+?)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*$",
        t,
    )
    if m:
        return [Intent(name="reminder",
                       params={"action": "add", "text": m.group(1).strip(),
                               "time": m.group(2).strip(), "date": "today"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_timer(text: str) -> list[Intent] | None:
    """Match unambiguous timer and alarm commands."""
    t = text.strip().lower()

    # ── Set timer: "set timer for 5 minutes", "5 minute timer", "timer 10 min"
    # Hindi: "timer lagao 5 minute", "5 minute ka timer"
    m = re.match(
        r"(?:set\s+(?:a\s+)?timer\s+(?:for\s+)?|timer\s+(?:lagao\s+|set\s+(?:karo?\s+)?)?)"
        r"(\d+)\s*(?:minute|min|minat)s?",
        t,
    )
    if m:
        minutes = int(m.group(1))
        return [Intent(name="timer", params={"action": "set_timer", "duration": minutes * 60, "label": ""},
                       response=f"Timer set for {minutes} minute{'s' if minutes != 1 else ''}.",
                       confidence=1.0, meta={"source": "prefilter"})]

    m = re.match(r"(\d+)\s*(?:minute|min|minat)s?\s+(?:ka\s+)?timer", t)
    if m:
        minutes = int(m.group(1))
        return [Intent(name="timer", params={"action": "set_timer", "duration": minutes * 60, "label": ""},
                       response=f"Timer set for {minutes} minute{'s' if minutes != 1 else ''}.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # Timer with seconds: "timer 30 seconds", "30 second timer"
    m = re.match(
        r"(?:set\s+(?:a\s+)?timer\s+(?:for\s+)?|timer\s+(?:lagao\s+)?)"
        r"(\d+)\s*(?:second|sec)s?",
        t,
    )
    if m:
        seconds = int(m.group(1))
        return [Intent(name="timer", params={"action": "set_timer", "duration": seconds, "label": ""},
                       response=f"Timer set for {seconds} seconds.",
                       confidence=1.0, meta={"source": "prefilter"})]

    m = re.match(r"(\d+)\s*(?:second|sec)s?\s+timer", t)
    if m:
        seconds = int(m.group(1))
        return [Intent(name="timer", params={"action": "set_timer", "duration": seconds, "label": ""},
                       response=f"Timer set for {seconds} seconds.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # Timer with hours: "timer 1 hour", "1 hour timer"
    m = re.match(
        r"(?:set\s+(?:a\s+)?timer\s+(?:for\s+)?|timer\s+(?:lagao\s+)?)"
        r"(\d+)\s*(?:hour|hr|ghante?)s?",
        t,
    )
    if m:
        hours = int(m.group(1))
        return [Intent(name="timer", params={"action": "set_timer", "duration": hours * 3600, "label": ""},
                       response=f"Timer set for {hours} hour{'s' if hours != 1 else ''}.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # ── Set alarm: "set alarm for 7am", "alarm at 7:00", "wake me up at 7"
    # Hindi: "alarm set karo 7 baje", "alarm lagao 7 baje"
    m = re.match(
        r"(?:set\s+(?:an?\s+)?alarm\s+(?:for\s+|at\s+)?|alarm\s+(?:set\s+karo?\s+|lagao\s+)?(?:at\s+)?|wake\s+me\s+(?:up\s+)?(?:at\s+)?)"
        r"(\d{1,2})(?::(\d{2}))?\s*(?:am|pm|baje)?",
        t,
    )
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        if "pm" in t and hour < 12:
            hour += 12
        elif "am" in t and hour == 12:
            hour = 0
        time_str = f"{hour:02d}:{minute:02d}"
        return [Intent(name="timer", params={"action": "set_alarm", "time": time_str, "label": "", "repeat": "none"},
                       response=f"Alarm set for {hour:02d}:{minute:02d}.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # ── Cancel timer/alarm
    if re.fullmatch(
        r"(cancel\s+(the\s+)?timer|stop\s+(the\s+)?timer|timer\s+(cancel|band)\s*(karo?)?|timer\s+hatao)",
        t,
    ):
        return [Intent(name="timer", params={"action": "cancel", "cancel_type": "timer"},
                       response="Timer cancelled.", confidence=1.0,
                       meta={"source": "prefilter"})]

    if re.fullmatch(
        r"(cancel\s+(the\s+)?alarm|stop\s+(the\s+)?alarm|alarm\s+(cancel|band)\s*(karo?)?|alarm\s+hatao)",
        t,
    ):
        return [Intent(name="timer", params={"action": "cancel", "cancel_type": "alarm"},
                       response="Alarm cancelled.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # ── Snooze
    if re.fullmatch(r"(snooze|snooze\s+karo?|snooze\s+kar\s+do)", t):
        return [Intent(name="timer", params={"action": "snooze"},
                       response="Snoozed for 5 minutes.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # ── List timers/alarms
    if re.fullmatch(r"(list\s+timers?|active\s+timers?|show\s+timers?|what\s+timers?)", t):
        return [Intent(name="timer", params={"action": "list"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_weather(text: str) -> list[Intent] | None:
    """Match weather queries — keyword-based for typo tolerance."""
    t = text.strip().lower()

    # Keyword detection: if any weather-related word appears, it's a weather query.
    # This is intentionally broad — false positives are better than missing weather.
    weather_keywords = r"\b(weather|mausam|temperature|forecast|barish|rain|snow|garmi|sardi|thand)\b"
    if re.search(weather_keywords, t):
        # Determine if forecast or current
        forecast_keywords = r"\b(forecast|weekly|tomorrow|kal|agle|hafta|week)\b"
        query = "forecast" if re.search(forecast_keywords, t) else "current"
        return [Intent(name="weather", params={"query": query},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Additional patterns without the word "weather" — "how hot is it", "will it rain"
    if re.search(
        r"(how (hot|cold|warm) is it|is it (hot|cold|warm|raining|snowing)|"
        r"will it rain|kitni garmi|kitni sardi|kitni thand)",
        t,
    ):
        return [Intent(name="weather", params={"query": "current"},
                       response="", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_story(text: str) -> list[Intent] | None:
    """Match unambiguous story mode commands."""
    t = text.strip().lower()

    # Stop story: "stop the story", "story band karo"
    if re.fullmatch(
        r"(stop\s+(the\s+)?story|story\s+(band|stop)\s*(karo?)?|"
        r"kahani\s+band\s*(karo?)?|story\s+rok(o)?)",
        t,
    ):
        return [Intent(name="story", params={"action": "stop"},
                       response="Story stopped.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Continue story: "continue the story", "tell me more", "aage ki kahani"
    if re.fullmatch(
        r"(continue\s+(the\s+)?story|tell\s+me\s+more|more\s+story|"
        r"aage\s+(ki\s+)?kahani|aur\s+sunao|phir\s+kya\s+hua|"
        r"story\s+continue\s*(karo?)?|aage\s+batao)",
        t,
    ):
        return [Intent(name="story", params={"action": "continue"},
                       response="Continuing the story...", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Start story: "tell me a story", "story time", "ek kahani sunao"
    if re.fullmatch(
        r"(tell\s+me\s+a\s+(bedtime\s+)?story|"
        r"story\s+time|bedtime\s+story|"
        r"ek\s+kahani\s+sunao|kahani\s+sunao|"
        r"tell\s+me\s+a\s+(funny|romantic|scary|adventure)\s+story|"
        r"(funny|romantic|scary|adventure)\s+story\s+sunao)",
        t,
    ):
        # Extract genre if present
        genre = None
        for g in ("funny", "romantic", "scary", "adventure", "bedtime"):
            if g in t:
                genre = g
                break
        params = {"action": "start"}
        if genre:
            params["genre"] = genre
        return [Intent(name="story", params=params,
                       response="Let me tell you a story...", confidence=1.0,
                       meta={"source": "prefilter"})]

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
def _match_video_control(text: str) -> list[Intent] | None:
    """Match video player control commands (fullscreen, exit fullscreen)."""
    t = text.strip().lower()

    if re.fullmatch(
        r"(full\s*screen|make it full\s*screen|"
        r"video full\s*screen|go full\s*screen|"
        r"video bada karo|bada karo|"
        r"maximize|maximise)",
        t,
    ):
        return [Intent(name="video_control", params={"action": "fullscreen"},
                       response="Going fullscreen.", confidence=1.0,
                       meta={"source": "prefilter"})]

    if re.fullmatch(
        r"(exit full\s*screen|leave full\s*screen|"
        r"small (screen|window)|chhota karo|"
        r"minimize video|minimize)",
        t,
    ):
        return [Intent(name="video_control", params={"action": "exit_fullscreen"},
                       response="Exiting fullscreen.", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


def _match_ambient(text: str) -> list[Intent] | None:
    """Match unambiguous ambient sound commands."""
    t = text.strip().lower()

    # Stop ambient: "stop ambient", "stop rain sounds", "stop white noise"
    # Hindi: "ambient band karo", "rain sounds band karo"
    if re.fullmatch(
        r"(stop\s+ambient(\s+sounds?)?|stop\s+(rain|ocean|white\s+noise|nature|sleep)\s+sounds?|"
        r"ambient\s+(band|stop|off)\s*(karo?)?|"
        r"stop\s+(the\s+)?(ambient|background)\s*(sounds?|noise|music)?)",
        t,
    ):
        return [Intent(name="ambient", params={"action": "stop"},
                       response="Ambient sounds stopped.", confidence=1.0,
                       meta={"source": "prefilter"})]

    # Volume: "ambient volume 20", "make rain louder", "ambient louder/quieter"
    m = re.match(r"ambient\s+volume\s+(\d{1,3})%?", t)
    if m:
        level = int(m.group(1))
        if level <= 100:
            return [Intent(name="ambient", params={"action": "volume", "level": level},
                           response=f"Ambient volume set to {level}%.", confidence=1.0,
                           meta={"source": "prefilter"})]

    if re.fullmatch(r"(make\s+(rain|ambient|background)\s+(louder|quieter|softer))", t):
        direction = "louder" if "louder" in t else "quieter"
        level = 50 if direction == "louder" else 15
        return [Intent(name="ambient", params={"action": "volume", "level": level},
                       response=f"Ambient volume {'up' if direction == 'louder' else 'down'}.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # Play specific sounds: "play rain sounds", "rain sounds", "white noise"
    # "play white noise", "play ambient sounds", "sleep sounds", "nature sounds"
    # Hindi: "barish ki awaaz", "baarish sounds"
    ambient_sounds = (
        r"rain|ocean|thunderstorm|white\s+noise|pink\s+noise|brown\s+noise|"
        r"fireplace|forest|birds|wind|cafe|fan|"
        r"barish|baarish|nature"
    )

    # "play rain sounds", "rain sounds please", "put on rain sounds"
    m = re.fullmatch(
        rf"(?:play\s+|put\s+on\s+|start\s+)?({ambient_sounds})"
        r"(?:\s+(?:sounds?|noise|awaaz|ki\s+awaaz))?(?:\s+please)?",
        t,
    )
    if m:
        sound = m.group(1).strip().replace(" ", "_")
        # Normalize Hindi variants
        if sound in ("barish", "baarish"):
            sound = "rain"
        elif sound == "nature":
            sound = "forest"
        return [Intent(name="ambient", params={"action": "play", "sound": sound},
                       response=f"Playing {sound.replace('_', ' ')} sounds.",
                       confidence=1.0, meta={"source": "prefilter"})]

    # "play ambient sounds", "ambient sounds", "sleep sounds"
    if re.fullmatch(
        r"(?:play\s+)?(ambient|sleep|relaxing|background)\s+sounds?",
        t,
    ):
        return [Intent(name="ambient", params={"action": "play", "sound": "rain"},
                       response="Playing rain sounds.", confidence=1.0,
                       meta={"source": "prefilter"})]

    return None


PREFILTER_CHAIN = [
    _match_ambient,
    _match_timer,
    _match_weather,
    _match_story,
    _match_sleep,
    _match_reminder,
    _match_quiz,
    _match_youtube_search,
    _match_video_music,
    _match_video_control,
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
