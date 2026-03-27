"""
Intent execution — routes classified intents to the appropriate provider.

This is the "do the thing" layer. It takes a structured Intent object
(from the brain's classifier or the prefilter) and executes it using
the right provider. Each intent type has its own handler function.

The main entry point is handle_intent(assistant, intent) → response string.

Why a module of functions, not a class?
  - handle_intent is stateless — it reads from the assistant dict and config,
    but doesn't hold its own state. Same pattern as prefilter_intent().
  - Easy to test: pass a mock assistant dict, get a string back.
  - Easy to extend: add a new elif branch + handler function.
"""

import threading
from datetime import datetime

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

def _build_now_playing_data(song, with_video: bool = False) -> dict:
    """Build a now-playing payload dict for the dashboard from a SongResult."""
    data = {
        "title": song.title,
        "artist": song.artist,
        "album": song.album or "",
        "duration": _parse_duration(song.duration),
        "position": 0,
    }
    if with_video and song.uri:
        data["video_id"] = song.uri
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


# ── Intent handlers ──────────────────────────────────────────────

def handle_intent(assistant: dict, intent) -> str:
    """
    Execute an intent using the appropriate provider.
    Returns a spoken response string.
    """
    name = config["assistant"]["name"]

    if intent.name == "music_play" and assistant.get("music"):
        raw_query = intent.params.get("query", "")
        with_video = intent.params.get("with_video", False)
        music = assistant["music"]

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
                face_ui = assistant.get("face_ui")
                if face_ui:
                    face_ui.set_now_playing(_build_now_playing_data(song, with_video))
                return f"Playing {song.title} by {song.artist} again."
            elif not raw_query:
                return "I don't have anything to play. Tell me what you'd like to hear."

        # Step 2: Enrich the raw query (separate from classification)
        enriched_query = assistant["brain"].enrich_query(raw_query)

        log.debug('Raw query: "%s"', raw_query)
        if enriched_query != raw_query:
            log.debug('Enriched query: "%s"', enriched_query)

        # Dual search: enriched for primary, raw for fallback
        results = assistant["music"].search(enriched_query, limit=3, raw_input=raw_query)
        if results:
            song = results[0]
            log.info('Playing: "%s" by %s%s', song.title, song.artist,
                     " (video)" if with_video else "")
            assistant["music"].play(song, video=with_video)

            # Notify dashboard
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_now_playing(_build_now_playing_data(song, with_video))

            suffix = " with video" if with_video else ""
            return f"Playing {song.title} by {song.artist}{suffix}."
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

            # Notify dashboard of playback state changes
            face_ui = assistant.get("face_ui")
            if face_ui:
                if action == "stop":
                    face_ui.set_now_playing(None)
                elif action == "pause":
                    face_ui.set_music_paused(True)
                elif action == "resume":
                    face_ui.set_music_paused(False)
                    # If resume replayed the last song, update now-playing
                    if music._last_song and not music._paused:
                        face_ui.set_now_playing(_build_now_playing_data(music._last_song))

            return intent.response or f"{action.title()}."
        else:
            return f"I don't know how to {action}."

    elif intent.name == "volume":
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

            # Notify dashboard of light state change
            face_ui = assistant.get("face_ui")
            if face_ui:
                _notify_lights_state(face_ui, action, value)

            return intent.response or "Done."
        except Exception as e:
            return f"Light control failed: {e}"

    elif intent.name == "switch_personality":
        target = intent.params.get("personality", "")
        try:
            p = personality_manager.switch(target)

            # Notify dashboard
            face_ui = assistant.get("face_ui")
            if face_ui:
                face_ui.set_personality(p.id)

            return intent.response or f"Switched to {p.display_name}."
        except KeyError as e:
            available = ", ".join(p.display_name for p in personality_manager.list())
            return f"I don't know that personality. Available: {available}."

    elif intent.name == "sleep":
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

        elif action == "wake":
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

    elif intent.name == "chat":
        # For chat, use the ORIGINAL user input — not the classified "message" param.
        # The classifier sometimes generates a response as the message param
        # (e.g., generating a story instead of just classifying "tell me a story"
        # as a chat intent). Sending that generated text back to the LLM causes
        # the LLM to respond to its own output instead of the user's request.
        #
        # Fall back to intent.params["message"] only if original_input isn't available
        # (e.g., when called from a test without the full pipeline).
        original_input = intent.meta.get("original_input", "")
        message = original_input or intent.params.get("message", "")
        p = personality_manager.active
        system = f"You are {p.display_name}. {p.tone}\nRespond naturally and concisely."
        resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.7)
        return resp.text

    elif intent.name == "memory_recall" and assistant.get("memory"):
        query = intent.params.get("query", "")
        memory = assistant["memory"]

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

    elif intent.name == "memory_stats" and assistant.get("memory"):
        stats = assistant["memory"].get_stats()
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

    elif intent.name == "knowledge_search":
        query = intent.params.get("query", "")
        knowledge = assistant.get("knowledge")

        if not knowledge:
            # No knowledge provider — fall back to the LLM's own knowledge via chat
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked a factual question. Answer as best you can from your "
                f"own knowledge, but be honest if you're not sure or if the information "
                f"might be outdated. Keep it concise — this is a voice assistant."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        if not knowledge.is_available():
            # Provider exists but internet is down — degrade gracefully
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked about current events or real-time info, but internet "
                f"is not available right now. Answer from your own knowledge if you can, "
                f"but mention that you couldn't check online for the latest info."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        # Search for information
        results = knowledge.search(query)
        if not results:
            # Search returned nothing — fall back to LLM knowledge
            original_input = intent.meta.get("original_input", "")
            message = original_input or query
            p = personality_manager.active
            system = (
                f"You are {p.display_name}. {p.tone}\n"
                f"The user asked a question. I searched online but found nothing relevant. "
                f"Answer from your own knowledge if possible, or say you couldn't find anything."
            )
            resp = assistant["brain"].generate(prompt=message, system=system, temperature=0.5)
            return resp.text

        # Build context from search results — keep it SHORT for 3B models.
        # Each snippet is ~1-2 sentences. 3 results ≈ 300-400 tokens.
        context_lines = []
        for i, r in enumerate(results, 1):
            # Truncate snippets to ~150 chars to stay within context budget
            snippet = r.snippet[:200].strip()
            context_lines.append(f"{i}. {r.title}: {snippet}")
        context = "\n".join(context_lines)

        original_input = intent.meta.get("original_input", "")
        message = original_input or query
        p = personality_manager.active
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

    elif intent.name == "quiz" and assistant.get("quiz"):
        action = intent.params.get("action", "start")
        quiz = assistant["quiz"]
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

            # Broadcast to dashboard
            if face_ui:
                face_ui.show_quiz({
                    "category": category,
                    "difficulty": difficulty,
                    "total": num_questions,
                    "question": question,
                    "score": 0,
                })

            # Speak the question
            options_text = ", ".join(question.get("options", []))
            return f"{question.get('text', '')} Your options are: {options_text}"

        elif action == "answer":
            user_answer = intent.params.get("answer", "")
            if not quiz.is_active():
                return "There's no quiz running right now."

            result = quiz.check_answer(user_answer)
            if "error" in result:
                return result["error"]

            # Broadcast result to dashboard
            if face_ui:
                face_ui.update_quiz({
                    "result": result,
                    "score": result.get("score", 0),
                    "question_number": result.get("question_number", 0),
                    "total": result.get("total", 0),
                })

            reaction = result.get("reaction", "")
            explanation = result.get("explanation", "")

            # Auto-generate next question if session isn't complete
            if quiz.is_active() and result.get("question_number", 0) < result.get("total", 0):
                # Generate next question after a brief pause
                next_q = quiz.generate_question()
                if "error" not in next_q:
                    if face_ui:
                        face_ui.show_quiz({
                            "category": quiz._category,
                            "difficulty": quiz._difficulty,
                            "total": quiz._num_questions,
                            "question": next_q,
                            "score": result.get("score", 0),
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

        elif action == "hint":
            if not quiz.is_active():
                return "No quiz is running right now."
            hint = quiz.get_hint()
            return f"Here's a hint: {hint}"

        elif action == "score":
            if not quiz.is_active():
                return "No quiz is running right now."
            stats = quiz.get_session_stats()
            return (
                f"You've got {stats['correct']} out of {stats['total']} correct "
                f"({stats['accuracy']}% accuracy). "
                f"{stats['out_of'] - stats['total']} questions remaining."
            )

        elif action == "quit":
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

    elif intent.name == "system":
        action = intent.params.get("action", "")
        if action == "time":
            return f"It's {datetime.now().strftime('%I:%M %p')}."
        elif action == "date":
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
        return intent.response or "I can't do that yet."

    else:
        return intent.response or "I'm not sure what to do with that."
