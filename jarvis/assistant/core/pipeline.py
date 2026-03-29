"""
Input processing pipeline — the shared classify → execute → speak flow.

This is the hub that all input modes (text, voice, wake word) and the
dashboard UI feed into. It takes raw text, classifies it into intents,
executes each intent, logs the interaction, and speaks the response.

Why extracted from main.py?
  - Three run modes + the UI action handler all call this same pipeline
  - It's the most-touched code path during UI iteration
  - Separating it makes the flow testable without starting the full assistant
"""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.config import config
from core.logger import get_logger
from core.personality import personality_manager
from core.interfaces import Interaction
from core.prefilter import prefilter_intent
from core.intent_handler import handle_intent

# Shared thread pool for intent execution — avoids creating threads per request.
# max_workers=4 is plenty for I/O-bound intent handlers (Tuya, YouTube, Ollama).
_intent_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="intent")

# Per-intent-type timeout in seconds. Device control (lights) gets a short
# timeout so a missing device doesn't block everything.
INTENT_TIMEOUTS = {
    "light_control": 5.0,
    "music_play": 15.0,       # YouTube search + mpv startup can be slow
    "music_control": 5.0,
    "volume": 3.0,
    "switch_personality": 2.0,
    "chat": 30.0,             # LLM generation can take a while
    "knowledge_search": 20.0, # web search + LLM summarization
    "system": 2.0,
    "memory_recall": 15.0,
    "memory_stats": 5.0,
    "story": 120.0,           # LLM generates multi-paragraph story — needs time on CPU
    "quiz": 60.0,             # LLM generates question + options
    "weather": 15.0,          # API call + LLM summary
    "ambient": 15.0,          # YouTube search for ambient sounds
    "timer": 5.0,
    "reminder": 5.0,
    "youtube_search": 5.0,
}



# Maps intent type names to icon identifiers shown by the dashboard.
INTENT_ICONS = {
    "music_play": "music",
    "music_control": "music",
    "light_control": "bulb",
    "volume": "volume",
    "switch_personality": "personality",
    "chat": "brain",
    "knowledge_search": "search",
    "system": "general",
    "memory_recall": "brain",
    "memory_stats": "brain",
}

# Maps intent type names to human-readable labels shown by the dashboard.
INTENT_LABELS = {
    "music_play": "Playing music",
    "music_control": "Music",
    "light_control": "Lights",
    "volume": "Volume",
    "switch_personality": "Personality",
    "chat": "Thinking",
    "knowledge_search": "Searching",
    "system": "System",
    "memory_recall": "Remembering",
    "memory_stats": "Memory",
}

log = get_logger("pipeline")


def process_input(assistant: dict, user_input: str, interrupt_event=None,
                   cancel_event=None):
    """
    Process a single user input: classify → execute → respond → log.

    Shared between text mode and voice mode — the only difference is
    how the input is obtained (typed vs spoken).

    Args:
        assistant: dict of provider instances (brain, music, lights, etc.)
        user_input: raw text from user (typed or transcribed from speech)
        interrupt_event: Optional threading.Event. If set during TTS playback,
            audio stops immediately (wake word barge-in). The caller is
            responsible for handling the interrupted state.
        cancel_event: Optional threading.Event. If set at any point, the
            pipeline aborts at the next checkpoint. Used when a new wake word
            detection supersedes the current pipeline. Unlike interrupt_event
            (which only stops TTS), cancel_event halts the entire pipeline —
            classification, intent execution, TTS, everything.

    Returns:
        (response_text, was_interrupted) — the response string and whether
        TTS was interrupted by a wake word.

    Also pushes state transitions to the Face UI (if running):
      thinking → speaking → idle
    """
    brain = assistant["brain"]
    face_ui = assistant.get("face_ui")

    # ── Cancellation checkpoint helper ───────────────────────────
    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    # Show user's input on the face UI
    if face_ui:
        face_ui.show_transcript(user_input, role="user")
        face_ui.set_state("thinking")

    # Try keyword pre-filter first — resolves obvious commands in <1ms
    intents = prefilter_intent(user_input)

    # Fall through to LLM for ambiguous inputs
    if intents is None:
        # ── Checkpoint: before LLM classification (~8-11s on CPU) ──
        if _cancelled():
            log.info("Pipeline cancelled before classification.")
            return "", False
        intents = brain.classify_intent(user_input)

    # ── Checkpoint: after classification, before execution ──────
    if _cancelled():
        log.info("Pipeline cancelled after classification.")
        return "", False

    # Attach original user input to each intent's meta so handlers can
    # use it instead of the classified params (important for chat — see handler)
    for intent in intents:
        intent.meta["original_input"] = user_input

    # Intent debug output — only visible in DEBUG mode
    latency = intents[0].meta.get("latency", 0) if intents else 0
    tok_s = intents[0].meta.get("tok_per_sec", 0) if intents else 0
    intent_names = " + ".join(i.name for i in intents)
    log.debug("[%s] (%.2fs, %.0f tok/s)", intent_names, latency, tok_s)
    for i in intents:
        log.debug("  → %s: %s", i.name, json.dumps(i.params))

    # Assign a short ID to each intent for dashboard tracking, then broadcast
    # all of them at once so the UI can render the full pipeline upfront.
    intent_payloads = []
    for intent in intents:
        iid = uuid.uuid4().hex[:8]
        intent.meta["dashboard_id"] = iid
        intent_payloads.append({
            "id": iid,
            "type": intent.name,
            "icon": INTENT_ICONS.get(intent.name, "general"),
            "label": INTENT_LABELS.get(intent.name, intent.name.replace("_", " ").title()),
            "status": "queued",
        })

    if face_ui and intent_payloads:
        face_ui.send_intents(intent_payloads)

    # ── Checkpoint: before intent execution ─────────────────────
    if _cancelled():
        log.info("Pipeline cancelled before intent execution.")
        # Mark queued intents as cancelled on the dashboard
        if face_ui:
            for intent in intents:
                iid = intent.meta.get("dashboard_id")
                if iid:
                    face_ui.update_intent(iid, "failed", "Cancelled")
        return "", False

    # Execute intents in parallel with per-type timeouts.
    # The entire pipeline runs in a background thread (see main.py), so
    # blocking here is fine — the user can still interact via wake word.
    # We wait for ALL results so we can speak accurate responses
    # (e.g., "Playing Sajni" only after search completes, "Lights on" only
    # after the light actually turns on).

    def _execute_one(intent):
        """Run a single intent in a worker thread."""
        # Check cancellation before starting this intent
        if _cancelled():
            iid = intent.meta.get("dashboard_id")
            if face_ui and iid:
                face_ui.update_intent(iid, "failed", "Cancelled")
            return ""

        iid = intent.meta.get("dashboard_id")
        if face_ui and iid:
            face_ui.update_intent(iid, "processing")
        try:
            response = handle_intent(assistant, intent)
            if face_ui and iid:
                detail = response[:120] if response else None
                face_ui.update_intent(iid, "done", detail)
            return response
        except Exception as exc:
            log.error("Intent %s failed: %s", intent.name, exc)
            if face_ui and iid:
                face_ui.update_intent(iid, "failed", str(exc)[:120])
            return f"Something went wrong with {intent.name}."

    # Submit all intents to the thread pool
    futures = {}
    for intent in intents:
        future = _intent_executor.submit(_execute_one, intent)
        futures[future] = intent

    # Collect results in original order.
    # Use as_completed(timeout=) to bound total wall-clock wait —
    # individual future.result() timeouts are meaningless since the future
    # is already done when yielded by as_completed.
    responses = [""] * len(intents)
    intent_order = {id(intent): idx for idx, intent in enumerate(intents)}

    # Overall timeout = max of all per-intent timeouts (they run in parallel)
    overall_timeout = max(
        (INTENT_TIMEOUTS.get(i.name, 10.0) for i in intents),
        default=10.0,
    )

    try:
        for future in as_completed(futures, timeout=overall_timeout):
            intent = futures[future]
            idx = intent_order[id(intent)]
            try:
                responses[idx] = future.result()
            except Exception as exc:
                iid = intent.meta.get("dashboard_id")
                log.error("Intent %s unexpected error: %s", intent.name, exc)
                responses[idx] = f"Something went wrong with {intent.name}."
                if face_ui and iid:
                    face_ui.update_intent(iid, "failed", str(exc)[:120])
    except TimeoutError:
        # Some futures didn't finish in time — log and continue with partial results
        for future, intent in futures.items():
            if not future.done():
                idx = intent_order[id(intent)]
                iid = intent.meta.get("dashboard_id")
                timeout = INTENT_TIMEOUTS.get(intent.name, 10.0)
                log.warning("Intent %s timed out after %.1fs", intent.name, overall_timeout)
                responses[idx] = f"{intent.name.replace('_', ' ').title()} timed out."
                if face_ui and iid:
                    face_ui.update_intent(iid, "failed", f"Timed out after {timeout:.0f}s")

    # ── Checkpoint: after execution, before speaking ────────────
    if _cancelled():
        log.info("Pipeline cancelled after intent execution.")
        return "", False

    # Use active personality's display name (may have changed mid-loop)
    p = personality_manager.active
    response_text = " ".join(r for r in responses if r).strip()
    if not response_text:
        return "", False

    print(f"{p.display_name}: {response_text}\n")

    # Update face UI with personality (may have changed) and response
    if face_ui:
        face_ui.set_personality(p.id)
        face_ui.show_transcript(response_text, role="assistant")
        face_ui.set_state("speaking")

    # Log this interaction to memory (do this even if TTS gets cancelled —
    # the action already happened, we want it in the log)
    memory = assistant.get("memory")
    if memory:
        try:
            interaction = Interaction(
                user_id="default",
                input_text=user_input,
                intents=intents,
                responses=responses,
                outcome="success",
            )
            memory.log_interaction(interaction)
        except Exception as e:
            log.warning("Failed to log interaction to memory: %s", e)

    # ── Checkpoint: before TTS ────────────────────────────────
    if _cancelled():
        log.info("Pipeline cancelled before TTS.")
        if face_ui:
            face_ui.set_state("idle")
        return response_text, False

    # Speak the response aloud via the voice router
    was_interrupted = False
    voice_router = assistant.get("voice_router")
    if voice_router and voice_router.enabled and response_text.strip():
        completed = voice_router.speak_to_device(
            response_text, personality=p, interrupt_event=interrupt_event,
        )
        was_interrupted = not completed

    # Back to idle after speaking
    if face_ui:
        face_ui.set_state("idle")

    return response_text, was_interrupted
