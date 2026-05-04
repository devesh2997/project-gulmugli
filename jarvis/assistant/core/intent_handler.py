"""
Intent execution — routes classified intents to the appropriate provider.

This is the "do the thing" layer. It takes a structured Intent object
(from the brain's classifier or the prefilter) and executes it using
the right provider.

## Architecture

`handle_intent(assistant, intent) -> str` is the single public entry
point. Internally it dispatches via the `_DISPATCH` dict:

    _DISPATCH = {
        "music_play": _handle_music_play,
        "music_control": _handle_music_control,
        ...
    }

Each `_handle_<intent>(assistant, intent) -> str | None` is a single
function that implements one intent. Returning `None` means the handler
declined to act (typically because the required provider isn't loaded);
the dispatcher falls through to a generic "not sure" response.

## Why the dispatch refactor (was: a 1100-line elif chain)

The previous structure was a single 1100-line `if/elif` chain inside
`handle_intent`. It worked, but:
- It was impossible to grep for "where is intent X handled" without scrolling.
- Test-mocking one branch required a full `assistant` dict with every provider stubbed.
- Adding a new intent meant editing the middle of a giant function.

The dispatch dict makes each handler:
- Trivially locatable (`_handle_music_play` is one Cmd-Click away).
- Independently testable (mock just the providers that handler touches).
- Independently extensible (new intent = new function + one dict entry).

Behavior is intentionally byte-identical to the previous version —
this refactor is mechanical, not semantic. The intent test suite was
93.3% before AND 93.3% after (verified on Jetson).

## Module-level state

`_sleep_mode`, `_pre_sleep_volume`, `_story_state` and `_quiz_provider_ref`
are kept at module level because:
- They're per-process singletons (one assistant per process).
- Multiple handlers + the prefilter need to read/mutate them.
- The locking pattern (`_sleep_lock`) is already in place for thread safety.

If we ever support multiple assistants in one process (probably never),
these become per-instance state.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Dict, Optional

from core.config import config
from core.interfaces import Intent
from core.logger import get_logger
from core.personality import personality_manager

log = get_logger("intent_handler")

# ── Sleep mode state ─────────────────────────────────────────────
# Module-level flag so main.py can check it from the wake word loop.
# Protected by _sleep_lock for thread safety — accessed from the wake word
# thread, the pipeline thread pool, and the UI action handler.
_sleep_mode = threading.Event()
_sleep_lock = threading.Lock()
_pre_sleep_volume: int | None = None

# ── Story mode state ────────────────────────────────────────────
# Tracks the last story generated so "continue" can pick up from it.
# Reads/writes are infrequent and predominantly from one thread (the
# pipeline executor). Not currently locked — if we observe story-state
# corruption under concurrent story_continue + story_start, add a lock.
_story_state: dict = {
    "active": False,
    "genre": None,
    "topic": None,
    "paragraphs": [],     # accumulated story text (list of paragraph strings)
    "personality_id": "",  # which personality told the story
}


def is_sleep_mode() -> bool:
    """Check if the assistant is currently in sleep mode."""
    return _sleep_mode.is_set()


def trigger_wake(assistant: dict) -> str:
    """
    Programmatic wake — called from main.py when wake word fires during sleep,
    or from ui/actions.py when the user taps the screen.
    Returns the spoken response string.
    """
    intent = Intent(
        name='sleep',
        params={'action': 'wake'},
        response='Good morning! Ready when you are.',
        confidence=1.0,
        meta={'source': 'auto_wake'},
    )
    return handle_intent(assistant, intent)


# ── Quiz state helper ────────────────────────────────────────────
# Exposed as a module-level function so the prefilter can check if a
# quiz is active (for context-sensitive matching of "hint", "score", etc.)

def _quiz_is_active() -> bool:
    """Check if a quiz session is active. Used by prefilter for context-sensitive matching."""
    return _quiz_provider_ref is not None and _quiz_provider_ref.is_active()


# Module-level ref to the quiz provider, set by set_quiz_provider() from main.py.
_quiz_provider_ref = None


def set_quiz_provider(quiz_provider) -> None:
    """Store a reference to the quiz provider for prefilter access."""
    global _quiz_provider_ref
    _quiz_provider_ref = quiz_provider


# ── Helpers ──────────────────────────────────────────────────────

def _forecast_day_name(date_str: str) -> str:
    """Convert YYYY-MM-DD to a friendly day name (Today, Tomorrow, or weekday)."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        if d == today:
            return "Today"
        from datetime import timedelta
        if d == today + timedelta(days=1):
            return "Tomorrow"
        return d.strftime("%A")
    except (ValueError, TypeError):
        return date_str


def _build_now_playing_data(song, video_id: str | None = None) -> dict:
    """Build a now-playing payload dict for the dashboard from a SongResult.

    Args:
        song: The SongResult being played.
        video_id: Override video ID. If provided, uses this instead of song.uri.
                  This should be the actual music video ID (from filter='videos'),
                  not the Topic/audio-only ID (from filter='songs').
    """
    data = {
        "title": song.title,
        "artist": song.artist,
        "album": song.album or "",
        "duration": _parse_duration(song.duration),
        "position": 0,
    }
    # Use the music video ID if available, otherwise fall back to song URI
    vid = video_id or song.uri
    if vid:
        data["video_id"] = vid
    return data


def _parse_duration(duration_str: str) -> int:
    """Parse YouTube Music duration string ("3:45") to seconds."""
    if not duration_str:
        return 0
    parts = duration_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, IndexError):
        pass
    return 0


def _notify_lights_state(face_ui, action: str, value: str) -> None:
    """Push light state to the dashboard after a light command."""
    if action == "off":
        face_ui.set_lights(on=False)
    elif action == "on":
        face_ui.set_lights(on=True)
    elif action == "color":
        face_ui.set_lights(on=True, color=value)
    elif action == "brightness":
        numeric = ''.join(c for c in value if c.isdigit())
        face_ui.set_lights(on=True, brightness=int(numeric) if numeric else 50)
    elif action == "scene":
        face_ui.set_lights(on=True, scene=value)


# ════════════════════════════════════════════════════════════════
#  Per-intent handlers
# ════════════════════════════════════════════════════════════════
#
# Each `_handle_<intent>(assistant, intent) -> Optional[str]` returns:
#   - A non-empty string: the spoken response. Dispatcher uses this directly.
#   - An empty string ("")  : success but no response (rare; used for
#                             intents whose effect is purely visual).
#   - None                  : the handler declined (e.g. provider missing).
#                             Dispatcher falls through to the generic
#                             "I'm not sure what to do with that" response.

def _handle_music_play(assistant: dict, intent: Intent) -> Optional[str]:
    music = assistant.get("music")
    if music is None:
        return None
    raw_query = intent.params.get("query", "")
    with_video = intent.params.get("with_video", False)

    # If no query (or query is just "play"/"resume"), resume last song
    if not raw_query or raw_query.lower().strip() in ("play", "resume", "continue"):
        if music._paused and music._last_song:
            music.resume()
            song = music._last_song
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_music_paused(False)
            return f"Resuming {song.title} by {song.artist}."
        elif music._last_song:
            # Not paused but we have a last song — replay it
            song = music._last_song
            music.play(song, video=with_video)
            music_video_id = None
            if hasattr(music, 'find_music_video_id'):
                music_video_id = music.find_music_video_id(song)
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_now_playing(_build_now_playing_data(song, video_id=music_video_id))
            return f"Playing {song.title} by {song.artist} again."
        elif not raw_query:
            return "I don't have anything to play. Tell me what you'd like to hear."

    # Step 1.5: STT-mishear correction on the raw query BEFORE both
    # branches (enrichment + raw search). Whisper transcribes Hindi
    # proper nouns badly — "kesriya" for Kesariya, "hayriye" for
    # Heeriye, "sajney" for Sajni. If we left raw_query unchanged
    # going into the dual-search raw branch, we'd land on the wrong
    # language song (observed: "hayriye" → Turkish folk song with
    # "Hayriye" in the title). By correcting upstream, both raw
    # search and enrichment operate on the right title — and the
    # dual-search disagreement rule's distinctive-word check still
    # works because both queries share the corrected token.
    from core.song_corrections import correct_title
    corrected_query = correct_title(raw_query)
    if corrected_query != raw_query:
        log.info('STT correction: "%s" → "%s"', raw_query, corrected_query)
        raw_query = corrected_query

    # Step 2: Enrich + search IN PARALLEL.
    #
    # The naive flow is serial:
    #   enrich (LLM, ~2-3s) → search (network, ~3s) → play
    # …which compounds to ~6s of dead air between the prefilter's
    # spoken "Playing Sajni" ack and the actual song starting. By
    # kicking off enrichment AND a raw-query search concurrently,
    # the wall-clock collapses to max(enrich, raw_search) ≈ 3s. If
    # enrichment changes the query, we issue ONE more search with
    # the enriched form and reconcile via the existing dual-search
    # picker logic in the music provider. If enrichment yields the
    # same query (low-information short titles like "Sajni"), we
    # skip the redundant second search entirely.
    #
    # Pattern source: OVOS Common Play (parallel skill query) +
    # Pipecat tool-use (background work behind a spoken ack).
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2,
                            thread_name_prefix="music-search") as pool:
        enrich_fut = pool.submit(assistant["brain"].enrich_query, raw_query)
        # Bypass the music provider's own dual-search wrapper for the
        # raw side — we want JUST the raw results, then we'll let the
        # provider's picker reconcile if needed.
        raw_search_fut = pool.submit(
            getattr(music, "_raw_search",
                    lambda q, n: music.search(q, limit=n)),
            raw_query, 3,
        )
        try:
            enriched_query = enrich_fut.result(timeout=8)
        except Exception as e:
            log.warning("Enrichment failed (%s) — using raw query only", e)
            enriched_query = raw_query
        try:
            raw_results = raw_search_fut.result(timeout=10)
        except Exception as e:
            log.warning("Raw search failed: %s", e)
            raw_results = []

    log.debug('Raw query: "%s"', raw_query)
    if enriched_query != raw_query:
        log.debug('Enriched query: "%s"', enriched_query)
        # Enrichment changed the query — do the enriched search and
        # let the provider's picker reconcile both result sets.
        results = music.search(enriched_query, limit=3, raw_input=raw_query)
    else:
        # Enrichment was a no-op (or failed and fell back to raw).
        # Save a network round-trip and use the parallel raw_results.
        results = raw_results
    if results:
        song = results[0]
        log.info('Playing: "%s" by %s%s', song.title, song.artist,
                 " (video)" if with_video else "")
        music.play(song, video=with_video)

        # Find the actual music video ID (not the Topic/audio-only version).
        # This runs in the current thread but is fast (~100-200ms).
        # The music video has real footage; the song's URI is often a static thumbnail.
        music_video_id = None
        if hasattr(music, 'find_music_video_id'):
            music_video_id = music.find_music_video_id(song)

        # Notify dashboard with the music video ID
        face_ui = assistant.get("face_ui")
        if face_ui:
            face_ui.set_now_playing(_build_now_playing_data(song, video_id=music_video_id))

        suffix = " with video" if with_video else ""
        return f"Playing {song.title} by {song.artist}{suffix}."
    return f"I couldn't find anything for '{raw_query}'."


def _handle_music_control(assistant: dict, intent: Intent) -> Optional[str]:
    music = assistant.get("music")
    if music is None:
        return None
    action = intent.params.get("action", "")

    actions = {
        "pause": music.pause,
        "resume": music.resume,
        "stop": music.stop,
        "skip": music.skip,
    }

    if action not in actions:
        return f"I don't know how to {action}."

    actions[action]()

    # Notify dashboard of playback state changes
    face_ui = assistant.get("face_ui")
    if face_ui:
        if action == "stop":
            face_ui.set_now_playing(None)
        elif action == "pause":
            face_ui.set_music_paused(True)
        elif action == "resume":
            face_ui.set_music_paused(False)
            # Always broadcast now-playing after resume.
            # If mpv was dead and resume() replayed the song, the
            # dashboard needs fresh now-playing data (new duration/position).
            # If mpv was just unpaused, this is a harmless refresh.
            if music._last_song:
                face_ui.set_now_playing(_build_now_playing_data(music._last_song))

    return intent.response or f"{action.title()}."


def _handle_volume(assistant: dict, intent: Intent) -> Optional[str]:
    # System-level volume — applies to all audio output (music, TTS, etc.)
    # Prefers AudioOutputProvider (system volume) when available,
    # falls back to mpv volume via MusicProvider.
    value = str(intent.params.get("level", ""))
    output = intent.params.get("output", "default")
    numeric = ''.join(c for c in value if c.isdigit())
    level = min(100, max(0, int(numeric))) if numeric else 50

    if assistant.get("audio"):
        assistant["audio"].set_volume(level, output=output)
    elif assistant.get("music"):
        # Fallback: route through mpv (current state)
        assistant["music"].set_volume(level)
    else:
        return "No audio output available."

    # Notify dashboard
    face_ui = assistant.get("face_ui")
    if face_ui:
        face_ui.set_volume(level)

    return intent.response or f"Volume set to {level}."


def _handle_light_control(assistant: dict, intent: Intent) -> Optional[str]:
    lights = assistant.get("lights")
    if lights is None:
        return None
    action = intent.params.get("action", "")
    value = str(intent.params.get("value", ""))

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

        # Notify dashboard of light state change
        face_ui = assistant.get("face_ui")
        if face_ui:
            _notify_lights_state(face_ui, action, value)

        return intent.response or "Done."
    except Exception as e:
        return f"Light control failed: {e}"


def _handle_switch_personality(assistant: dict, intent: Intent) -> Optional[str]:
    target = intent.params.get("personality", "")
    try:
        p = personality_manager.switch(target)

        # Notify dashboard
        face_ui = assistant.get("face_ui")
        if face_ui:
            face_ui.set_personality(p.id)

        return intent.response or f"Switched to {p.display_name}."
    except KeyError:
        available = ", ".join(p.display_name for p in personality_manager.list())
        return f"I don't know that personality. Available: {available}."


def _handle_sleep(assistant: dict, intent: Intent) -> Optional[str]:
    global _pre_sleep_volume
    action = intent.params.get("action", "")
    face_ui = assistant.get("face_ui")
    music = assistant.get("music")
    lights = assistant.get("lights")
    sleep_cfg = config.get("sleep_mode", {})

    if action == "sleep":
        with _sleep_lock:
            _sleep_mode.set()

            # Turn lights OFF completely (if configured)
            if lights and sleep_cfg.get("turn_off_lights", True):
                try:
                    lights.turn_off()
                except Exception as e:
                    log.warning("Could not turn off lights for sleep: %s", e)

            # Save current music volume, then start soothing sleep music
            if music:
                try:
                    _pre_sleep_volume = music._focus_get_volume()
                except Exception:
                    _pre_sleep_volume = 100

                sleep_volume = sleep_cfg.get("sleep_music_volume", 10)

                if sleep_cfg.get("play_sleep_music", True):
                    # Search for and play soothing sleep music at low volume
                    try:
                        sleep_query = sleep_cfg.get("sleep_music_query", "soothing relaxing sleep music ambient")
                        results = music.search(sleep_query, raw_input=sleep_query)
                        if results:
                            music.play(results[0])
                            log.info("Playing sleep music: %s", results[0].title)
                        music.set_volume(sleep_volume)
                    except Exception as e:
                        log.warning("Could not start sleep music: %s", e)
                        # At least duck existing music
                        try:
                            music.set_volume(sleep_volume)
                        except Exception:
                            pass
                elif sleep_cfg.get("duck_existing_music", True):
                    # No sleep music requested, but duck existing music
                    try:
                        music.set_volume(sleep_volume)
                    except Exception:
                        pass
                else:
                    # No ducking — stop existing music entirely
                    try:
                        music.stop()
                    except Exception:
                        pass

        # Update dashboard
        if face_ui:
            face_ui.set_state("sleeping")
            face_ui.set_sleep_mode(True)

        log.info("Sleep mode activated.")
        return intent.response or "Good night, sleep well."

    if action == "wake":
        with _sleep_lock:
            _sleep_mode.clear()

            # Restore music volume (if configured)
            if music and _pre_sleep_volume is not None and sleep_cfg.get("restore_volume_on_wake", True):
                try:
                    music.set_volume(_pre_sleep_volume)
                except Exception as e:
                    log.warning("Could not restore music volume: %s", e)
            _pre_sleep_volume = None

            # Restore lights (if configured)
            if lights and sleep_cfg.get("restore_lights_on_wake", True):
                try:
                    lights.turn_on()
                    lights.set_brightness(sleep_cfg.get("wake_lights_brightness", 50))
                except Exception as e:
                    log.warning("Could not restore lights: %s", e)

        # Update dashboard
        if face_ui:
            face_ui.set_state("idle")
            face_ui.set_sleep_mode(False)

        log.info("Sleep mode deactivated — good morning.")
        return intent.response or "Good morning! Ready when you are."

    return intent.response or "I'm not sure what to do with that."


def _handle_story(assistant: dict, intent: Intent) -> Optional[str]:
    global _story_state
    action = intent.params.get("action", "start")
    face_ui = assistant.get("face_ui")
    story_cfg = config.get("story", {})
    max_paragraphs = story_cfg.get("max_paragraphs", 5)
    default_genre = story_cfg.get("default_genre", "bedtime")

    if action == "stop":
        _story_state = {"active": False, "genre": None, "topic": None,
                        "paragraphs": [], "personality_id": ""}
        if face_ui:
            face_ui.set_story_mode({"active": False})
        return intent.response or "Story stopped."

    if action == "continue":
        if not _story_state["active"] or not _story_state["paragraphs"]:
            return "There's no story to continue. Ask me to tell you a story first."

        p = personality_manager.active
        last_text = "\n\n".join(_story_state["paragraphs"])
        system = (
            f"You are {p.display_name}, a storyteller. {p.tone}\n\n"
            f"Continue this story from where it left off. Add 2-3 more paragraphs. "
            f"Keep the same tone and characters. End with a satisfying moment."
        )
        resp = assistant["brain"].generate(
            prompt=f"Continue this story:\n\n{last_text}",
            system=system,
            temperature=0.8,
        )
        new_text = resp.text.strip()
        new_paragraphs = [p_text.strip() for p_text in new_text.split("\n\n") if p_text.strip()]
        _story_state["paragraphs"].extend(new_paragraphs)

        # Broadcast updated story to dashboard
        if face_ui:
            face_ui.set_story_mode({
                "active": True,
                "genre": _story_state["genre"],
                "paragraphs": _story_state["paragraphs"],
                "current_paragraph": len(_story_state["paragraphs"]) - 1,
                "finished": False,
            })

        return new_text

    # action == "start"
    genre = intent.params.get("genre") or default_genre
    topic = intent.params.get("topic")
    p = personality_manager.active

    # Build story prompt based on genre and personality
    genre_instructions = {
        "bedtime": "Make it calming, gentle, and soothing. Use peaceful imagery. End with a tranquil, sleepy scene.",
        "funny": "Make it hilarious and witty. Use clever wordplay and unexpected twists. End with a great punchline.",
        "romantic": "Make it sweet and heartwarming. Build emotional connection between characters. End with a tender moment.",
        "scary": "Make it suspenseful and eerie. Build tension gradually. End with a surprising twist, but keep it fun, not traumatic.",
        "adventure": "Make it exciting and action-packed. Include brave characters and challenges. End with a triumphant victory.",
    }
    genre_note = genre_instructions.get(genre, genre_instructions["bedtime"])

    topic_note = f"The story should be about: {topic}. " if topic else ""

    system = (
        f"You are {p.display_name}, telling a story in character. {p.tone}\n\n"
        f"TASK: Tell an original {genre} story in 3-{max_paragraphs} paragraphs.\n"
        f"{topic_note}"
        f"Keep it engaging — use dialogue, vivid descriptions, and a clear arc.\n"
        f"{genre_note}\n"
        f"Format: Write the story directly as plain text. Separate paragraphs with blank lines.\n"
        f"Do NOT include a title, headers, or meta-commentary. Just tell the story."
    )

    resp = assistant["brain"].generate(
        prompt=f"Tell me a {genre} story" + (f" about {topic}" if topic else ""),
        system=system,
        temperature=0.8,
    )

    story_text = resp.text.strip()
    paragraphs = [p_text.strip() for p_text in story_text.split("\n\n") if p_text.strip()]

    _story_state = {
        "active": True,
        "genre": genre,
        "topic": topic,
        "paragraphs": paragraphs,
        "personality_id": p.id,
    }

    # Broadcast to dashboard
    if face_ui:
        face_ui.set_story_mode({
            "active": True,
            "genre": genre,
            "paragraphs": paragraphs,
            "current_paragraph": 0,
            "finished": False,
        })

    return story_text


def _handle_chat(assistant: dict, intent: Intent) -> Optional[str]:
    # FAST PATH: the classifier may have already produced a short reply
    # in the top-level "response" field (single LLM call instead of two).
    # If it did, just speak that and skip the second LLM round-trip.
    # On Jetson this halves the chat-turn latency (~5s saved per turn).
    if intent.response and intent.response.strip():
        return intent.response.strip()

    # SLOW PATH (fallback): classifier left "response" empty (e.g. for
    # long-form requests like stories) — generate the reply now.
    # Use the ORIGINAL user input — not the classified "message" param —
    # because the classifier sometimes echoes its own pre-thought into
    # the message field, which would loop back through the LLM.
    original_input = intent.meta.get("original_input", "")
    message = original_input or intent.params.get("message", "")
    p = personality_manager.active
    # Voice-assistant-friendly system prompt: keep replies SHORT for short
    # questions (1-2 sentences). Longer answers only when the question
    # genuinely calls for them (e.g. "explain how black holes work").
    # The hard num_predict cap (max_tokens=60) bounds latency at ~3s on
    # Jetson regardless of how chatty the model gets, but the prompt does
    # most of the work; max_tokens is a safety net, not the main mechanism.
    system = (
        f"You are {p.display_name}. {p.tone}\n"
        "REPLY RULES:\n"
        "- LANGUAGE: reply in the SAME language the user used (English/Hindi/Hinglish).\n"
        "  Never translate the user's message into English before answering.\n"
        "- Match reply length to question depth.\n"
        "- 1 sentence for greetings, factoids, simple questions.\n"
        "- 2-3 sentences max for normal questions.\n"
        "- Skip filler ('Sure!', 'Great question!', 'Let me explain'). Just answer.\n"
        "- For follow-up details, wait for the user to ask."
    )
    # Cap output at 60 tokens (~45 words). For voice assistant turns this
    # is plenty — typical helpful replies fit in 1-2 spoken sentences.
    # On Jetson at ~22 tok/s this caps chat-handler generation at ~3s,
    # vs >5s when uncapped. We let the model stop earlier on its own
    # for short factoids ("It's 6:30 PM" = 5 tokens, ~0.2s).
    resp = assistant["brain"].generate(
        prompt=message, system=system, temperature=0.7, max_tokens=60,
    )
    return resp.text


def _handle_memory_recall(assistant: dict, intent: Intent) -> Optional[str]:
    memory = assistant.get("memory")
    if memory is None:
        return None
    query = intent.params.get("query", "")

    if not query:
        # No specific query — show recent interactions
        memories = memory.get_recent(limit=5)
    else:
        memories = memory.recall(query, limit=5)

    if not memories:
        return "I don't have any memories matching that yet."

    # Format memories clearly so the LLM can parse them.
    # Filter out memory_recall interactions (don't report "you asked me
    # what you played" as a result when asking what was played).
    memory_lines = []
    for m in memories:
        intents = m.raw.get("intents", [])
        intent_names = [i.get("name", "") for i in intents] if isinstance(intents, list) else []
        if "memory_recall" in intent_names or "memory_stats" in intent_names:
            continue
        responses = m.raw.get("responses", [])
        response_text = responses[0] if responses else ""
        memory_lines.append(
            f"- {m.timestamp[:16]} | You said: \"{m.raw.get('input_text', '')}\" "
            f"| I did: {response_text[:120]}"
        )

    if not memory_lines:
        return "I don't have any relevant memories for that yet."

    memory_text = "\n".join(memory_lines)

    p = personality_manager.active
    system = (
        f"You are {p.display_name}. {p.tone}\n\n"
        f"TASK: The user asked about past interactions. Answer ONLY based on "
        f"the log below. Do NOT suggest new actions. Do NOT offer to play "
        f"anything. Just report what happened.\n\n"
        f"INTERACTION LOG:\n{memory_text}\n\n"
        f"USER QUESTION: \"{query}\"\n\n"
        f"RULES:\n"
        f"- Only mention what is in the log above\n"
        f"- Do not suggest, recommend, or offer anything\n"
        f"- Keep it to 1-2 sentences\n"
        f"- If the log doesn't answer the question, say so"
    )
    resp = assistant["brain"].generate(
        prompt=query or "What have I been doing recently?",
        system=system,
        temperature=0.2,
    )
    return resp.text


def _handle_memory_stats(assistant: dict, intent: Intent) -> Optional[str]:
    memory = assistant.get("memory")
    if memory is None:
        return None
    stats = memory.get_stats()
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


def _handle_knowledge_search(assistant: dict, intent: Intent) -> Optional[str]:
    query = intent.params.get("query", "")
    knowledge = assistant.get("knowledge")
    p = personality_manager.active
    original_input = intent.meta.get("original_input", "")
    message = original_input or query

    def _fallback_to_llm(reason_in_prompt: str) -> str:
        """Generate a chat-style reply when search isn't available or empty."""
        system = f"You are {p.display_name}. {p.tone}\n{reason_in_prompt}"
        resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
        return resp.text

    if not knowledge:
        return _fallback_to_llm(
            "The user asked a factual question. Answer as best you can from your "
            "own knowledge, but be honest if you're not sure or if the information "
            "might be outdated. Keep it concise — this is a voice assistant."
        )

    if not knowledge.is_available():
        # Provider exists but internet is down — degrade gracefully
        return _fallback_to_llm(
            "The user asked about current events or real-time info, but internet "
            "is not available right now. Answer from your own knowledge if you can, "
            "but mention that you couldn't check online for the latest info."
        )

    # Search for information
    results = knowledge.search(query)
    if not results:
        return _fallback_to_llm(
            "The user asked a question. I searched online but found nothing relevant. "
            "Answer from your own knowledge if possible, or say you couldn't find anything."
        )

    # Build context from search results — keep it SHORT for 3B models.
    # Each snippet is ~1-2 sentences. 3 results ≈ 300-400 tokens.
    context_lines = []
    for i, r in enumerate(results, 1):
        # Truncate snippets to ~150 chars to stay within context budget
        snippet = r.snippet[:200].strip()
        context_lines.append(f"{i}. {r.title}: {snippet}")
    context = "\n".join(context_lines)

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


def _handle_quiz(assistant: dict, intent: Intent) -> Optional[str]:
    quiz = assistant.get("quiz")
    if quiz is None:
        return None
    action = intent.params.get("action", "start")
    face_ui = assistant.get("face_ui")

    if action == "start":
        category = intent.params.get("category", "general")
        difficulty = intent.params.get("difficulty", "medium")
        quiz_cfg = config.get("quiz", {})
        num_questions = quiz_cfg.get("default_num_questions", 10)
        p = personality_manager.active
        tone = p.tone

        result = quiz.start_session(
            category=category,
            difficulty=difficulty,
            num_questions=num_questions,
            personality_tone=tone,
        )

        if not result.get("session_started"):
            return result.get("error", "Could not start quiz.")

        # Generate first question
        question = quiz.generate_question()
        if "error" in question:
            return question["error"]

        # Broadcast to dashboard — flatten question fields for frontend
        if face_ui:
            face_ui.show_quiz({
                "category": category,
                "difficulty": difficulty,
                "total_questions": num_questions,
                "question_number": 1,
                "question": question.get("text", ""),
                "options": question.get("options", []),
                "time_limit": config.get("quiz", {}).get("time_limit_seconds", 30),
                "score": {"correct": 0, "total": 0},
            })

        # Speak the question
        options_text = ", ".join(question.get("options", []))
        return f"{question.get('text', '')} Your options are: {options_text}"

    if action == "answer":
        user_answer = intent.params.get("answer", "")
        if not quiz.is_active():
            return "There's no quiz running right now."

        result = quiz.check_answer(user_answer)
        if "error" in result:
            return result["error"]

        # Broadcast result to dashboard — match frontend QuizUpdateMessage shape
        stats = quiz.get_session_stats()
        if face_ui:
            face_ui.update_quiz({
                "correct": result.get("correct", False),
                "correct_answer": result.get("correct_answer", ""),
                "explanation": result.get("explanation", ""),
                "reaction": result.get("reaction", ""),
                "score": {"correct": stats.get("correct", 0), "total": stats.get("total", 0)},
            })

        reaction = result.get("reaction", "")
        explanation = result.get("explanation", "")

        # Auto-generate next question if session isn't complete
        if quiz.is_active() and stats.get("total", 0) < quiz._num_questions:
            next_q = quiz.generate_question()
            if "error" not in next_q:
                if face_ui:
                    face_ui.show_quiz({
                        "category": quiz._category,
                        "difficulty": quiz._difficulty,
                        "total_questions": quiz._num_questions,
                        "question_number": stats.get("total", 0) + 1,
                        "question": next_q.get("text", ""),
                        "options": next_q.get("options", []),
                        "time_limit": config.get("quiz", {}).get("time_limit_seconds", 30),
                        "score": {"correct": stats.get("correct", 0), "total": stats.get("total", 0)},
                    })
                options_text = ", ".join(next_q.get("options", []))
                return f"{reaction} {explanation} Next question: {next_q.get('text', '')} Options: {options_text}"

        elif quiz.is_active():
            # Last question answered — show final stats
            stats = quiz.get_session_stats()
            quiz.end_session()
            if face_ui:
                face_ui.close_quiz()
            return (
                f"{reaction} {explanation} "
                f"Quiz complete! You got {stats['correct']} out of {stats['total']} "
                f"({stats['accuracy']}% accuracy)."
            )

        return f"{reaction} {explanation}"

    if action == "hint":
        if not quiz.is_active():
            return "No quiz is running right now."
        hint = quiz.get_hint()
        return f"Here's a hint: {hint}"

    if action == "score":
        if not quiz.is_active():
            return "No quiz is running right now."
        stats = quiz.get_session_stats()
        return (
            f"You've got {stats['correct']} out of {stats['total']} correct "
            f"({stats['accuracy']}% accuracy). "
            f"{stats['out_of'] - stats['total']} questions remaining."
        )

    if action == "quit":
        if not quiz.is_active():
            return "No quiz is running."
        stats = quiz.get_session_stats()
        quiz.end_session()
        if face_ui:
            face_ui.close_quiz()
        return (
            f"Quiz ended. Final score: {stats['correct']} out of {stats['total']} "
            f"({stats['accuracy']}% accuracy)."
        )

    return intent.response or "I'm not sure what to do with that quiz command."


def _handle_reminder(assistant: dict, intent: Intent) -> Optional[str]:
    reminder_mgr = assistant.get("reminder")
    if reminder_mgr is None:
        return None
    action = intent.params.get("action", "")
    face_ui = assistant.get("face_ui")

    if action == "add":
        text = intent.params.get("text", "")
        time_str = intent.params.get("time", "")
        date_str = intent.params.get("date", "today")
        repeat = intent.params.get("repeat", "none")

        if not text:
            return "What should I remind you about?"
        if not time_str:
            return "When should I remind you?"

        from providers.reminder.manager import parse_reminder_time
        remind_at = parse_reminder_time(time_str, date_str)
        if not remind_at:
            return f"I couldn't understand the time '{time_str}'. Try something like 'at 5pm' or 'in 2 hours'."

        reminder_mgr.add(text, remind_at, repeat=repeat)

        # Broadcast updated reminder list to dashboard
        if face_ui:
            face_ui.update_reminders(reminder_mgr.list_active())

        time_display = remind_at.strftime("%I:%M %p")
        if date_str in ("tomorrow", "kal") or remind_at.date() != datetime.now().date():
            time_display = remind_at.strftime("%b %d at %I:%M %p")

        repeat_str = f" ({repeat})" if repeat != "none" else ""
        return intent.response or f"Reminder set: '{text}' at {time_display}{repeat_str}."

    if action == "list":
        active = reminder_mgr.list_active()
        if not active:
            return "You don't have any active reminders."

        lines = []
        for r in active:
            dt = datetime.fromisoformat(r["remind_at"])
            time_str_fmt = dt.strftime("%b %d %I:%M %p")
            repeat_tag = f" [{r['repeat']}]" if r.get("repeat", "none") != "none" else ""
            lines.append(f"- {r['text']} at {time_str_fmt}{repeat_tag}")

        summary = "\n".join(lines)
        return f"You have {len(active)} reminder{'s' if len(active) != 1 else ''}:\n{summary}"

    if action == "cancel":
        text = intent.params.get("text", "")
        if text:
            cancelled = reminder_mgr.cancel_by_text(text)
            if cancelled:
                if face_ui:
                    face_ui.update_reminders(reminder_mgr.list_active())
                return f"Cancelled reminder: '{cancelled['text']}'."
            return f"I couldn't find an active reminder matching '{text}'."

        # Cancel the most recent active reminder
        active = reminder_mgr.list_active()
        if active:
            cancelled = reminder_mgr.cancel(active[0]["id"])
            if cancelled and face_ui:
                face_ui.update_reminders(reminder_mgr.list_active())
            return f"Cancelled reminder: '{active[0]['text']}'." if cancelled else "Could not cancel."
        return "You don't have any active reminders to cancel."

    if action == "snooze":
        # Snooze the most recently fired or next due reminder
        minutes = 15
        time_param = intent.params.get("time", "")
        if time_param:
            try:
                minutes = int(''.join(c for c in time_param if c.isdigit()) or "15")
            except ValueError:
                minutes = 15

        active = reminder_mgr.list_active()
        if active:
            snoozed = reminder_mgr.snooze(active[0]["id"], minutes=minutes)
            if snoozed and face_ui:
                face_ui.update_reminders(reminder_mgr.list_active())
            return f"Snoozed for {minutes} minutes." if snoozed else "Could not snooze."
        return "No active reminders to snooze."

    return intent.response or "I'm not sure what to do with that reminder command."


def _handle_youtube_search(assistant: dict, intent: Intent) -> Optional[str]:
    query = intent.params.get("query", "")
    face_ui = assistant.get("face_ui")
    if face_ui and query:
        import urllib.parse
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        face_ui.open_youtube(url)
    return intent.response or f"Opening YouTube search for {query}"


def _handle_video_control(assistant: dict, intent: Intent) -> Optional[str]:
    action = intent.params.get("action", "")
    face_ui = assistant.get("face_ui")
    if face_ui:
        face_ui.video_control(action)
    return intent.response or ""


def _handle_weather(assistant: dict, intent: Intent) -> Optional[str]:
    weather = assistant.get("weather")
    face_ui = assistant.get("face_ui")
    query = intent.params.get("query", "current")

    if not weather:
        return "Weather is not configured. Add a weather section to config.yaml."

    if not weather.is_available():
        return "I can't check the weather right now — no internet connection."

    weather_cfg = config.get("weather", {})
    location_name = weather_cfg.get("location", {}).get("name", "your area")
    unit_symbol = "F" if weather_cfg.get("units") == "fahrenheit" else "C"

    if query in ("current", "temperature", "rain"):
        current = weather.get_current()
        if not current:
            return "I couldn't get the weather data right now."

        # Build dashboard payload
        dashboard_data = {
            "temperature": current.temperature,
            "feels_like": current.feels_like,
            "humidity": current.humidity,
            "wind_speed": current.wind_speed,
            "condition": current.condition,
            "description": current.description,
            "icon": current.icon,
            "sunrise": current.sunrise,
            "sunset": current.sunset,
            "location": location_name,
            "unit": unit_symbol,
        }

        # Add forecast for dashboard expansion
        forecast = weather.get_forecast(days=3)
        if forecast:
            dashboard_data["forecast"] = [
                {
                    "date": f.date,
                    "temp_min": f.temp_min,
                    "temp_max": f.temp_max,
                    "condition": f.condition,
                    "description": f.description,
                    "icon": f.icon,
                    "precipitation_chance": f.precipitation_chance,
                }
                for f in forecast
            ]

        # Add hourly for dashboard expansion
        hourly = weather.get_hourly(hours=12)
        if hourly:
            dashboard_data["hourly"] = [
                {
                    "time": h.time,
                    "temperature": h.temperature,
                    "condition": h.condition,
                    "icon": h.icon,
                    "precipitation_chance": h.precipitation_chance,
                }
                for h in hourly
            ]

        # Broadcast to dashboard
        if face_ui:
            face_ui.show_weather(dashboard_data)

        # Build spoken response
        if query == "rain":
            rain_conditions = ("rain", "thunderstorm")
            if current.condition in rain_conditions:
                return (
                    f"Yes, it's currently {current.description.lower()} in {location_name}. "
                    f"Temperature is {current.temperature:.0f} degrees {unit_symbol}."
                )
            # Check forecast for rain today
            if forecast:
                today = forecast[0]
                if today.condition in rain_conditions or today.precipitation_chance > 50:
                    return (
                        f"Not right now, but there's a {today.precipitation_chance}% chance of rain today in {location_name}. "
                        f"Currently {current.temperature:.0f} degrees {unit_symbol} and {current.description.lower()}."
                    )
            return (
                f"No rain expected in {location_name}. "
                f"It's {current.temperature:.0f} degrees {unit_symbol} and {current.description.lower()}."
            )

        if query == "temperature":
            return (
                f"It's {current.temperature:.0f} degrees {unit_symbol} in {location_name}. "
                f"Feels like {current.feels_like:.0f}."
            )

        # Default: full current weather
        return (
            f"It's {current.temperature:.0f} degrees {unit_symbol} and {current.description.lower()} "
            f"in {location_name}. Feels like {current.feels_like:.0f} with "
            f"{current.humidity}% humidity."
        )

    if query == "forecast":
        forecast = weather.get_forecast(days=3)
        if not forecast:
            return "I couldn't get the forecast right now."

        # Broadcast to dashboard
        if face_ui:
            dashboard_data = {
                "forecast": [
                    {
                        "date": f.date,
                        "temp_min": f.temp_min,
                        "temp_max": f.temp_max,
                        "condition": f.condition,
                        "description": f.description,
                        "icon": f.icon,
                        "precipitation_chance": f.precipitation_chance,
                    }
                    for f in forecast
                ],
                "location": location_name,
                "unit": unit_symbol,
            }
            # Also get current for the widget
            current = weather.get_current()
            if current:
                dashboard_data.update({
                    "temperature": current.temperature,
                    "feels_like": current.feels_like,
                    "humidity": current.humidity,
                    "condition": current.condition,
                    "description": current.description,
                    "icon": current.icon,
                })
            face_ui.show_weather(dashboard_data)

        # Build spoken response (keep short for voice)
        lines = []
        for f in forecast[:3]:
            day_name = _forecast_day_name(f.date)
            lines.append(
                f"{day_name}: {f.temp_min:.0f} to {f.temp_max:.0f} degrees, {f.description.lower()}"
            )
        return f"Here's the forecast for {location_name}. " + ". ".join(lines) + "."

    return intent.response or "I'm not sure what weather info you need."


def _handle_timer(assistant: dict, intent: Intent) -> Optional[str]:
    timer_mgr = assistant.get("timer_manager")
    if timer_mgr is None:
        return None
    action = intent.params.get("action", "")
    face_ui = assistant.get("face_ui")

    if action == "set_timer":
        duration = int(intent.params.get("duration", 300))
        label = intent.params.get("label", "")
        timer_mgr.set_timer(duration, label=label)

        # Broadcast updated timer list
        if face_ui:
            face_ui.set_timers(timer_mgr.list_active())

        # Format duration for speech
        mins, secs = divmod(duration, 60)
        hours, mins = divmod(mins, 60)
        parts = []
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if mins:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        if secs and not hours:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        duration_str = " and ".join(parts) if parts else "0 seconds"
        label_str = f" for {label}" if label else ""
        return intent.response or f"Timer set for {duration_str}{label_str}."

    if action == "set_alarm":
        time_str = intent.params.get("time", "07:00")
        label = intent.params.get("label", "")
        repeat = intent.params.get("repeat", "none")
        timer_mgr.set_alarm(time_str, label=label, repeat=repeat)

        if face_ui:
            face_ui.set_timers(timer_mgr.list_active())

        repeat_str = f" ({repeat})" if repeat != "none" else ""
        return intent.response or f"Alarm set for {time_str}{repeat_str}."

    if action == "cancel":
        cancel_type = intent.params.get("cancel_type", "timer")
        cancelled = timer_mgr.cancel(cancel_type)

        if face_ui:
            if cancelled:
                face_ui.timer_cancelled(cancelled.to_dict())
            face_ui.set_timers(timer_mgr.list_active())

        if cancelled:
            return intent.response or f"{cancelled.type.title()} '{cancelled.label}' cancelled."
        return "No active timer or alarm to cancel."

    if action == "snooze":
        snooze_mins = int(intent.params.get("duration", 300)) // 60 if intent.params.get("duration") else 5
        snoozed = timer_mgr.snooze("alarm", minutes=snooze_mins)

        if face_ui:
            face_ui.set_timers(timer_mgr.list_active())

        if snoozed:
            return intent.response or f"Snoozed {snoozed.label} for {snooze_mins} minutes."
        return "No alarm to snooze."

    if action == "list":
        active = timer_mgr.list_active()
        if not active:
            return "No active timers or alarms."
        lines = []
        for t_entry in active:
            remaining = int(t_entry["remaining_seconds"])
            if t_entry["type"] == "timer":
                m, s = divmod(remaining, 60)
                lines.append(f"Timer '{t_entry['label']}': {m}m {s}s remaining")
            else:
                target_dt = datetime.fromtimestamp(t_entry["target_time"])
                lines.append(f"Alarm '{t_entry['label']}' at {target_dt.strftime('%I:%M %p')}")
        return ". ".join(lines) + "."

    return intent.response or "I'm not sure what to do with that timer command."


def _handle_ambient(assistant: dict, intent: Intent) -> Optional[str]:
    ambient = assistant.get("ambient")
    if ambient is None:
        return None
    action = intent.params.get("action", "play")
    face_ui = assistant.get("face_ui")

    if action == "play":
        sound = intent.params.get("sound", "rain")
        success = ambient.play(sound)
        if success:
            if face_ui:
                face_ui.set_ambient(ambient.get_state())
            return intent.response or f"Playing {sound.replace('_', ' ')} sounds."
        available = ", ".join(ambient.list_sounds())
        return f"I couldn't play '{sound}'. Available sounds: {available}."

    if action == "stop":
        ambient.stop()
        if face_ui:
            face_ui.set_ambient(ambient.get_state())
        return intent.response or "Ambient sounds stopped."

    if action == "volume":
        level = int(intent.params.get("level", 30))
        ambient.set_volume(level)
        if face_ui:
            face_ui.set_ambient(ambient.get_state())
        return intent.response or f"Ambient volume set to {level}%."

    return intent.response or "I'm not sure what to do with that ambient command."


def _handle_system(assistant: dict, intent: Intent) -> Optional[str]:
    action = intent.params.get("action", "")
    if action == "time":
        return f"It's {datetime.now().strftime('%I:%M %p')}."
    if action == "date":
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
    return intent.response or "I can't do that yet."


# ════════════════════════════════════════════════════════════════
#  Dispatch table — single source of truth for "which handler runs"
# ════════════════════════════════════════════════════════════════
#
# Order is irrelevant — `_DISPATCH` is consulted by name. To add a new
# intent: implement `_handle_<name>`, append a `"<name>": _handle_<name>`
# row here, and you're done. The classifier's JSON-schema enum (in
# `providers/brain/ollama.py`) is the other half of this contract;
# adding an intent there without a handler here means the dispatcher
# falls through to "I'm not sure what to do with that".

_DISPATCH: Dict[str, Callable[[dict, Intent], Optional[str]]] = {
    "music_play":         _handle_music_play,
    "music_control":      _handle_music_control,
    "volume":             _handle_volume,
    "light_control":      _handle_light_control,
    "switch_personality": _handle_switch_personality,
    "sleep":              _handle_sleep,
    "story":              _handle_story,
    "chat":               _handle_chat,
    "memory_recall":      _handle_memory_recall,
    "memory_stats":       _handle_memory_stats,
    "knowledge_search":   _handle_knowledge_search,
    "quiz":               _handle_quiz,
    "reminder":           _handle_reminder,
    "youtube_search":     _handle_youtube_search,
    "video_control":      _handle_video_control,
    "weather":            _handle_weather,
    "timer":              _handle_timer,
    "ambient":            _handle_ambient,
    "system":             _handle_system,
}


def handle_intent(assistant: dict, intent: Intent) -> str:
    """
    Execute an intent using the appropriate provider.

    Returns the spoken response string. Empty string is allowed for
    intents whose effect is purely visual (e.g. video_control with
    no spoken response).
    """
    handler = _DISPATCH.get(intent.name)
    if handler is not None:
        result = handler(assistant, intent)
        if result is not None:
            return result
        # Handler explicitly returned None — provider unavailable or
        # intent not actionable with current state. Fall through to
        # the generic response below.

    return intent.response or "I'm not sure what to do with that."
