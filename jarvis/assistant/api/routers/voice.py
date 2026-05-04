"""
Voice endpoint — server-side STT + pipeline + TTS, audio in / audio out.

Two modes:

1. POST /api/voice (existing, JSON)
   - Synchronous: STT → pipeline → TTS, returns one big JSON with all the
     audio embedded as base64. Simple to consume but you wait the full
     duration before any audio reaches the client.

2. POST /api/voice/stream (new, Server-Sent Events)
   - Same pipeline but streams events as they happen:
       transcribed   { "text": "..."}                      after STT
       response_text { "text": "..." }                     after the LLM
                                                           response field
                                                           is complete
       audio_chunk   { "index": N, "url": "/api/voice/    per sentence
                        audio/<id>", "chunk_id": "...",     as TTS finishes —
                        "sentence": "...", "bytes": N }     fetch via GET
       done          { "timings": { ... }, "intent": ... } at the end
   - Time-to-first-audio drops to ~3-5s on Jetson because we synthesize and
     ship sentence 1 to the client while the LLM is still generating
     sentence 2.

Both endpoints use the same internal pipeline; /stream just wraps it in a
streaming response.
"""

import asyncio
import base64
import io
import json
import re
import time
import uuid
import wave
import threading
from queue import Queue, Empty

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from api.auth import verify_token
from api.deps import get_assistant
from core.logger import get_logger
from core.personality import personality_manager
from core.pipeline import process_input
from core.prefilter import prefilter_intent

# ── Lifted helpers (audio cache, filler clips, chat-fast heuristic) ──
# These were inline in this file (~280 LOC of standalone helpers) until
# the refactor moved them into siblings under api/voice/. Each module
# is independently testable. The `_audio_cache_*` aliases preserve the
# pre-refactor names so test_api_smoke.py keeps working without rewrites.
from api.voice.audio_cache import (
    put as _audio_cache_put,
    pop as _audio_cache_pop,
    router as _audio_cache_router,
    _AUDIO_CACHE,
    _AUDIO_CACHE_LOCK,
    _AUDIO_CACHE_TTL,
)
from api.voice.filler import (
    ensure_filler_for as _ensure_filler_for,
    pick_filler_wav as _pick_filler_wav,
    ensure_error_audio_for as _ensure_error_audio_for,
    pick_error_wav as _pick_error_wav,
    _FILLER_CACHE, _FILLER_LOCK, _ERROR_CACHE,
    _FILLER_PHRASES, _ERROR_PHRASES,
)
from api.voice.chat_fast import (
    find_first_chunk_boundary as _find_first_chunk_boundary,
    is_obvious_chat as _is_obvious_chat,
    _CHAT_HEURISTIC_RE,
    _SENTENCE_END_RE,
    _CLAUSE_BREAK_RE,
)

log = get_logger("api.voice")
router = APIRouter(dependencies=[Depends(verify_token)])

# Mount the audio-cache GET endpoint on this router so the public URL
# stays at /api/voice/audio/{chunk_id} — clients don't need to know
# the cache moved.
router.include_router(_audio_cache_router)


# ─── Schema (non-streaming) ──────────────────────────────────────────────

class VoiceTimings(BaseModel):
    stt_ms: float
    pipeline_ms: float
    tts_ms: float
    total_ms: float


class VoiceResponse(BaseModel):
    ok: bool
    transcribed: str = ""
    response: str = ""
    audio_b64: str | None = None
    audio_format: str = "wav"
    timings: VoiceTimings | None = None
    error: str | None = None


# ─── Non-streaming endpoint (kept for simple JSON consumers) ─────────────

@router.post("/api/voice", response_model=VoiceResponse)
async def voice(
    audio: UploadFile = File(...),
    assistant: dict = Depends(get_assistant),
):
    """Synchronous voice round-trip: returns one JSON with audio embedded."""
    t_total = time.monotonic()

    ears = assistant.get("ears")
    if not ears:
        return VoiceResponse(
            ok=False,
            error="STT (ears) provider is not configured. Check config.yaml ears section.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        return VoiceResponse(ok=False, error="Empty audio upload.")

    # 1. STT
    t_stt = time.monotonic()
    try:
        result = ears.transcribe(audio_bytes)
        transcribed = (result.text or "").strip()
    except Exception as e:
        log.warning("STT failed: %s", e)
        return VoiceResponse(ok=False, error=f"STT failed: {e}")
    stt_ms = (time.monotonic() - t_stt) * 1000

    if not transcribed:
        return VoiceResponse(
            ok=True,
            timings=VoiceTimings(
                stt_ms=stt_ms, pipeline_ms=0, tts_ms=0,
                total_ms=(time.monotonic() - t_total) * 1000,
            ),
        )

    # 2. Pipeline
    t_pipe = time.monotonic()
    try:
        pipe_result = process_input(assistant, transcribed)
        if isinstance(pipe_result, tuple):
            response_text = pipe_result[0] or ""
        else:
            response_text = pipe_result or ""
    except Exception as e:
        log.warning("Pipeline failed: %s", e)
        return VoiceResponse(ok=False, transcribed=transcribed, error=f"Pipeline failed: {e}")
    pipeline_ms = (time.monotonic() - t_pipe) * 1000

    # 3. TTS (full reply at once for non-streaming endpoint)
    t_tts = time.monotonic()
    audio_b64 = None
    try:
        vr = assistant.get("voice_router")
        active_personality = personality_manager.active
        wav_bytes = vr.speak(response_text, active_personality) if (vr and response_text) else None
        if wav_bytes:
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    except Exception as e:
        log.warning("TTS failed (non-fatal): %s", e)
    tts_ms = (time.monotonic() - t_tts) * 1000

    total_ms = (time.monotonic() - t_total) * 1000
    return VoiceResponse(
        ok=True,
        transcribed=transcribed,
        response=response_text,
        audio_b64=audio_b64,
        audio_format="wav",
        timings=VoiceTimings(
            stt_ms=stt_ms, pipeline_ms=pipeline_ms, tts_ms=tts_ms, total_ms=total_ms,
        ),
    )


# ─── Streaming endpoint (the perceived-latency win) ──────────────────────

def _sse(event: str, data: dict) -> bytes:
    """Format an event as SSE."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _audio_chunk_sse(index: int, sentence: str, wav: bytes | None) -> bytes:
    """
    Build an SSE `audio_chunk` event using the out-of-band cache.

    If `wav` is None (synthesis failed), we still emit the event but
    without a URL — the client logs and continues. If `wav` is present,
    we cache it and emit a tiny event carrying just the chunk_id + URL,
    so the SSE stream isn't head-of-line-blocked by audio bytes.
    """
    if wav:
        chunk_id = _audio_cache_put(wav)
        return _sse("audio_chunk", {
            "index": index,
            "sentence": sentence,
            "chunk_id": chunk_id,
            "url": f"/api/voice/audio/{chunk_id}",
            "bytes": len(wav),
        })
    return _sse("audio_chunk", {
        "index": index,
        "sentence": sentence,
        "chunk_id": None,
        "url": None,
    })


@router.post("/api/voice/stream")
async def voice_stream(
    request: Request,
    audio: UploadFile = File(...),
    play_local: bool = False,
    filler: bool = True,
    assistant: dict = Depends(get_assistant),
):
    """
    Stream the voice round-trip as Server-Sent Events.

    Pipeline:
      1. STT (~0.5s on Jetson CUDA Whisper "base") → emit transcribed
      2. Pre-filter → if obvious command (lights off, pause, etc.) skip the LLM
      3. Otherwise LLM streams; we extract the chat reply incrementally
      4. As each sentence completes, synthesize TTS in a worker thread and emit
         the audio chunk to the client. Client plays each chunk on arrival.

    Time-to-first-audio is what matters here: with streaming, the client gets
    the first audible word ~3-5s after end-of-speech (vs 9-12s with the
    non-streaming /api/voice endpoint), even though total completion time
    is similar.
    """
    audio_bytes = await audio.read()

    async def event_stream():
        t_total = time.monotonic()
        timings = {"stt_ms": 0, "first_token_ms": 0, "first_audio_ms": 0, "total_ms": 0}

        ears = assistant.get("ears")
        if not ears:
            yield _sse("error", {"message": "STT (ears) provider is not configured."})
            return

        if not audio_bytes:
            yield _sse("error", {"message": "Empty audio upload."})
            return

        # 1. STT
        t_stt = time.monotonic()
        try:
            result = ears.transcribe(audio_bytes)
            transcribed = (result.text or "").strip()
        except Exception as e:
            yield _sse("error", {"message": f"STT failed: {e}"})
            # Audible failure feedback — user shouldn't stare at silence.
            try:
                active_p = personality_manager.active
                _ensure_error_audio_for(assistant.get("voice_router"), active_p)
                err_wav = _pick_error_wav(active_p.id)
                if err_wav:
                    yield _audio_chunk_sse(-2, "<error>", err_wav)
            except Exception:
                pass
            return
        timings["stt_ms"] = (time.monotonic() - t_stt) * 1000

        if not transcribed:
            timings["total_ms"] = (time.monotonic() - t_total) * 1000
            yield _sse("done", {"timings": timings})
            return

        yield _sse("transcribed", {
            "text": transcribed,
            "language": getattr(result, "language", ""),
            "confidence": getattr(result, "confidence", 0),
            "stt_ms": timings["stt_ms"],
        })

        # 2. Pre-filter (instant, regex-based)
        intents = prefilter_intent(transcribed)
        prefilter_hit = intents is not None

        # ─── Filler audio: emit BEFORE LLM/TTS pipeline starts ──────────
        # Drops perceived TTFA from ~3s to ~600ms (STT + filler emit + GET).
        # The filler is a pre-synthesized "Hmm" / "Let me think." clip that
        # plays while the real answer is being generated.
        # Skip filler for prefilter hits — those resolve in <200ms anyway,
        # so a filler would actually slow things down on its own.
        # Also skip when filler=false (for benches/tests where filler
        # skews the answer-TTFA measurement).
        if filler and not prefilter_hit and assistant.get("voice_router"):
            active_p = personality_manager.active
            try:
                _ensure_filler_for(assistant["voice_router"], active_p)
            except Exception as e:
                log.warning("Filler cache build failed: %s", e)
            wav = _pick_filler_wav(active_p.id)
            if wav:
                # Special index -1 marks this as a filler vs an answer chunk
                yield _audio_chunk_sse(-1, "<filler>", wav)
        # Chat fast-path: if the input is obviously a chat question (and the
        # prefilter didn't already match it as something more specific like
        # weather/time/story), we skip the JSON-mode classifier and stream
        # a free-form chat reply directly. This is the single biggest TTFA
        # win for chat queries on Jetson — saves ~3-5s.
        chat_fast = (not prefilter_hit) and _is_obvious_chat(transcribed)
        first_audio_emitted = False
        first_token_emitted = False

        # Audio synth + emit pipeline. We use a worker thread to synthesize
        # so the SSE generator can keep yielding while a sentence is being
        # turned into WAV. On Jetson Kokoro CPU is ~3x realtime, so a
        # 4-word sentence synthesizes in ~0.3s.
        vr = assistant.get("voice_router")
        active_personality = personality_manager.active

        # Why ONE worker (not N parallel threads): Kokoro ONNX inference is
        # CPU-bound and uses all available cores via OMP. Spawning one thread
        # per sentence creates 3-way CPU contention — measured on Jetson Orin:
        # 3 sentences in parallel = ~28s wall-clock; 3 sentences serial via a
        # single worker = ~14s wall-clock AND the first sentence finishes ~3x
        # faster (3.5s vs 9.5s). Time-to-first-audio is what matters, so we
        # serialize. The producer (the LLM consumer below) keeps streaming
        # tokens while the worker is synthesizing — that overlap is the win.
        synth_in: Queue = Queue()   # (index, sentence) — work to do
        synth_out: Queue = Queue()  # (index, sentence, wav) — completed work
        synth_count = [0]
        WORKER_SENTINEL = object()

        # NOTE: `play_local` parameter is currently a no-op — the Jetson has
        # no speaker attached. Keeping the parameter declared for forward
        # compatibility (if a future Jetson build has a 3.5mm jack or USB
        # audio device, this hook will route audio there). Today, the Mac
        # client is the only audio sink, and tests should play audio
        # client-side (e.g., via afplay in tools/bench_voice_e2e.py).
        _ = play_local  # acknowledge parameter without `del` (which trips
                        # Python's "referenced-before-assignment" check on
                        # the closure capture)

        # ─── Fast TTS path (Piper for English) ──────────────────────────
        #
        # Why dual-TTS: on Jetson 8GB shared memory, putting Kokoro on CUDA
        # alongside Whisper + Ollama caused NvMap fragmentation that
        # crashed Ollama after extended use. Putting Kokoro on CPU was
        # stable but Kokoro CPU is only ~1.6x realtime → real-answer TTFA
        # of ~9s for a 5-second sentence.
        #
        # Industry pattern (Home Assistant Voice / Wyoming / Willow /
        # Rhasspy all do this): Piper for English on CPU. Piper is much
        # smaller and ~10x realtime on CPU — synthesizes the same 5-second
        # sentence in ~0.4s, faster than Kokoro on GPU.
        #
        # CRITICAL: this is a SPEED optimization, NOT a voice override.
        # Personalities with custom/cloned voices (XTTS reference WAVs,
        # personality.use_fast_voice = false) ALWAYS use their configured
        # voice — we never substitute a generic Piper voice for a user's
        # own cloned voice. The fast path is a generic-voice optimization.
        #
        # The decision tree per request:
        #   1. If personality.voice_provider is XTTS (voice cloning) →
        #      use personality voice (preserves identity)
        #   2. If personality.use_fast_voice is explicitly False →
        #      use personality voice (user opted out of fast path)
        #   3. If text contains Devanagari (Hindi) →
        #      use personality voice (Piper has no good Hindi voices)
        #   4. Else → use Piper (English speed optimization)
        from core.config import config as _cfg
        _voice_cfg = _cfg.get("voice", {})
        _fast_provider_name = _voice_cfg.get("fast_voice_provider", "piper")
        _fast_voice_model = _voice_cfg.get("fast_voice_model", "en_US-amy-low")
        _fast_provider = None
        if _fast_provider_name and assistant.get("voice_router"):
            try:
                _fast_provider = assistant["voice_router"]._get_provider(
                    _fast_provider_name
                )
            except Exception as e:
                log.warning("Fast TTS provider '%s' unavailable: %s",
                            _fast_provider_name, e)

        # Detect whether this personality wants its own voice preserved.
        # We check `voice_provider` attribute on the personality object;
        # values like "xtts" indicate runtime voice cloning where identity
        # matters. `use_fast_voice` (when set) is an explicit override.
        #
        # IMPORTANT: a Piper voice that was FINE-TUNED on the user's voice
        # is NOT the same as runtime cloning. It's still a vanilla Piper
        # provider, just with a custom .onnx. Those personalities SHOULD
        # use the fast path — Piper inference time is the same regardless
        # of which Piper voice file is loaded. So the rule is:
        #   - personality.voice_provider == "xtts" (or other cloning) →
        #     bypass fast path (slow runtime cloning, identity matters)
        #   - personality.voice_provider == "piper" with a custom model →
        #     USE fast path with the personality's own model (preserves
        #     the trained voice AND keeps the speed)
        #   - personality.voice_provider == "kokoro" or empty (default) →
        #     use Piper amy-low fast path for English speed
        _personality_provider = (getattr(active_personality, "voice_provider", "") or "").lower()
        _personality_voice_model = getattr(active_personality, "voice_model", "") or ""
        _personality_use_fast = getattr(active_personality, "use_fast_voice", None)
        _CLONING_PROVIDERS = {"xtts", "openvoice", "tortoise", "coqui"}
        _is_cloned_voice = (
            _personality_provider in _CLONING_PROVIDERS
            or _personality_use_fast is False
        )

        # If the personality is ALREADY using Piper (i.e., a fine-tuned
        # custom Piper voice), use that model on the fast path instead
        # of substituting amy-low. Preserves the user's trained voice.
        _effective_fast_model = _fast_voice_model
        if _personality_provider == "piper" and _personality_voice_model:
            _effective_fast_model = _personality_voice_model
            log.debug("Fast path will use personality's Piper voice: %s",
                      _effective_fast_model)

        _DEVANAGARI = re.compile(r"[ऀ-ॿ]")

        def _is_english(text: str) -> bool:
            """Heuristic: text is English if it has no Devanagari characters."""
            return not _DEVANAGARI.search(text)

        def _synth(text: str) -> bytes | None:
            """
            Synthesize text. Picks fastest provider per-utterance while
            preserving voice identity for cloned-voice personalities and
            for fine-tuned Piper voices.
            """
            # Cloned-voice personalities (XTTS reference WAVs): ALWAYS use
            # their voice (never sub in a generic Piper voice).
            if _is_cloned_voice:
                return vr.speak(text, active_personality) if vr else None

            # Hindi (any Devanagari): use the personality's voice — Piper
            # doesn't have good Hindi voices and Kokoro/XTTS do.
            if not _is_english(text):
                return vr.speak(text, active_personality) if vr else None

            # English: use Piper fast path with the right voice model.
            # `_effective_fast_model` is the personality's Piper voice if
            # it has one, else the global default (en_US-amy-low).
            if _fast_provider:
                try:
                    return _fast_provider.speak(text, voice_model=_effective_fast_model)
                except Exception as e:
                    log.warning("Piper synth failed (%s) — falling back to "
                                "personality voice", e)
            return vr.speak(text, active_personality) if vr else None

        def _synth_worker():
            # Self-healing exit: time out on idle so a leaked worker
            # eventually dies on its own. The streaming generator is
            # supposed to send WORKER_SENTINEL at the end of every
            # request's event_stream, but if it's cancelled before
            # reaching that line (client disconnect mid-stream, server
            # shutdown, exception escaping the generator), the worker
            # would block forever on synth_in.get(). The 60s idle
            # timeout caps that leak window — even under sustained
            # disconnect storms, leaked workers GC themselves within
            # a minute, well before they accumulate enough to fragment
            # the Jetson's 8GB shared memory.
            #
            # 60s is generous: the longest legitimate idle we expect is
            # the gap between LLM token streaming and the first sentence
            # boundary, typically <5s. If we ever see legitimate idles
            # >60s the worker will incorrectly exit early — but that's
            # easy to spot in logs and we can tune up.
            from queue import Empty as _Empty
            while True:
                try:
                    item = synth_in.get(timeout=60.0)
                except _Empty:
                    log.debug("TTS worker idle timeout — exiting (likely a leaked instance from a disconnected stream).")
                    return
                if item is WORKER_SENTINEL:
                    return
                idx, sentence = item
                try:
                    wav = _synth(sentence)
                except Exception as e:
                    log.warning("TTS sentence %d failed: %s", idx, e)
                    wav = None
                synth_out.put((idx, sentence, wav))

        import threading
        synth_thread = threading.Thread(
            target=_synth_worker, name="tts-worker", daemon=True
        )
        synth_thread.start()

        # Track whether the sentinel has already been put on the worker
        # queue so the cleanup `finally` doesn't double-send it (which is
        # harmless but creates a queue.put backlog under disconnect storms).
        _worker_signalled = [False]

        def _signal_worker_exit():
            if _worker_signalled[0]:
                return
            _worker_signalled[0] = True
            try:
                synth_in.put(WORKER_SENTINEL)
            except Exception:
                pass  # queue is unbounded so this should never raise

        def fire_sentence(text: str):
            """Queue TTS synth for `text` in the single worker thread."""
            idx = synth_count[0]
            synth_count[0] += 1
            synth_in.put((idx, text))

        async def drain_synth_queue():
            """Yield any audio chunks ready in the output queue."""
            chunks = []
            while True:
                try:
                    item = synth_out.get_nowait()
                except Empty:
                    break
                idx, sentence, wav = item
                chunks.append(_audio_chunk_sse(idx, sentence, wav))
            return chunks

        # ── Action paths: prefilter or non-chat intent. No streaming LLM. ──
        if prefilter_hit:
            # Pattern adapted from Home Assistant's intent dispatch:
            #   homeassistant/helpers/intent.py::DynamicServiceIntentHandler
            #
            # Two-phase execution:
            #
            #   PHASE 1 — speak the prefilter's pre-defined response IMMEDIATELY.
            #     The matcher already produced a response string ("Lights off.",
            #     "Paused.") at parse time, before any hardware was touched. We
            #     fire TTS synth on that string right away so the user hears
            #     feedback in <1 second regardless of how long the actual
            #     hardware action takes.
            #
            #   PHASE 2 — run the hardware-touching intent handler in a
            #     background thread with a SHORT validation window
            #     (`HARDWARE_VALIDATION_TIMEOUT`, default 200ms — same value
            #     HA uses). If the handler returns inside the window, we
            #     surface validation errors. If it doesn't, we let it keep
            #     running in the background and continue. We do NOT later
            #     speak "actually, that failed" — by the time a 30-second
            #     Tuya timeout fires, the user is in a different mental
            #     context and a delayed error message is worse than silent
            #     failure (HA's design choice; see helpers/intent.py 887-1182).
            #
            # The handler's RETURN value is preferred over the prefilter's
            # `response` field for non-trivial cases (e.g., "what time is it"
            # → handler computes "It's 11:23 PM."), so we hold the prefilter
            # response as a fallback and let the handler override if it
            # finishes in time.
            from core.intent_handler import handle_intent
            from concurrent.futures import TimeoutError as FuturesTimeout
            # Reuse the shared intent executor from pipeline.py — bounded
            # to max_workers=4. Per-request executors leaked threads when
            # background hardware calls outlived the request: a 30-second
            # Tuya hang would keep an executor + worker thread alive for
            # 30s, and 100 such hangs would be 100 stuck threads. The
            # shared pool caps total in-flight at 4; further submissions
            # queue rather than spawn.
            from core.pipeline import _intent_executor

            HARDWARE_VALIDATION_TIMEOUT = 0.2  # match HA exactly

            def run_intent(intent):
                intent.meta["original_input"] = transcribed
                try:
                    return handle_intent(assistant, intent)
                except Exception as e:
                    log.warning("Intent %s handler raised: %s", intent.name, e)
                    return None

            futures = [_intent_executor.submit(run_intent, i) for i in intents]

            # Collect results inside the validation window. Anything beyond
            # the window keeps running but its result is discarded — we use
            # the prefilter's pre-defined response instead.
            t_intent_start = time.monotonic()
            handler_responses: list[str] = []
            for fut, intent in zip(futures, intents):
                remaining = max(
                    0.0,
                    HARDWARE_VALIDATION_TIMEOUT - (time.monotonic() - t_intent_start),
                )
                try:
                    r = fut.result(timeout=remaining)
                    if r:
                        handler_responses.append(r)
                except FuturesTimeout:
                    log.info(
                        "Intent '%s' exceeded %.0fms validation window — "
                        "running in background. Falling back to prefilter response.",
                        intent.name, HARDWARE_VALIDATION_TIMEOUT * 1000,
                    )
                except Exception as e:
                    log.warning("Intent %s background error: %s", intent.name, e)

            # Use handler responses if all intents finished in time AND
            # produced text. Otherwise use the prefilter's pre-set responses
            # so the user always gets feedback.
            if len(handler_responses) == len(intents) and handler_responses:
                response_text = " ".join(handler_responses).strip()
            else:
                # Mix: handler responses where available, prefilter fallback
                # for intents that didn't finish in time.
                parts: list[str] = []
                for fut, intent in zip(futures, intents):
                    if fut.done():
                        try:
                            r = fut.result(timeout=0)
                            if r:
                                parts.append(r)
                                continue
                        except Exception:
                            pass
                    # Fallback to the prefilter's pre-defined response
                    if intent.response:
                        parts.append(intent.response)
                response_text = " ".join(parts).strip()

            yield _sse("response_text", {"text": response_text})
            if response_text and vr:
                from core.voice_router import VoiceRouter
                for sentence in VoiceRouter._split_sentences(response_text):
                    fire_sentence(sentence)
                # Wait for synth worker to produce each sentence in order.
                emitted = 0
                while emitted < synth_count[0]:
                    try:
                        item = synth_out.get(timeout=15)
                    except Empty:
                        break
                    idx, sent, wav = item
                    if not first_audio_emitted:
                        timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                        first_audio_emitted = True
                    yield _audio_chunk_sse(idx, sent, wav)
                    emitted += 1
            # Stop the TTS worker (idempotent — finally will skip if already signalled)
            _signal_worker_exit()
            timings["total_ms"] = (time.monotonic() - t_total) * 1000
            yield _sse("done", {
                "timings": timings,
                "intents": [i.name for i in intents],
                "response": response_text,
            })
            return

        # ── LLM path: classifier streams (JSON mode) OR chat fast-path
        # (free-form mode). Both end up shipping sentences to TTS as they
        # complete; the difference is only in HOW we extract the response
        # text from the token stream.
        from providers.brain.ollama import _build_system_prompt

        brain = assistant["brain"]

        if chat_fast:
            # Free-form chat reply, no JSON wrapping. Shorter system prompt
            # = faster prompt processing; non-JSON mode = ~2x faster decoding.
            #
            # We also route to a SMALLER model (qwen2.5:1.5b) when available,
            # because the chat fast-path is "answer this factual question in
            # 1-3 sentences" — well within a 1.5B model's capability and ~3x
            # faster TTFT than llama3.2:3b on Jetson. The classifier path
            # still uses llama3.2:3b for accuracy.
            p = personality_manager.active
            system_prompt = (
                f"You are {p.display_name}. {p.tone}\n\n"
                "Reply concisely — voice replies should be 1-3 sentences. "
                "No markdown, no lists, no preamble like 'Sure' or 'Of course'. "
                "Match reply length to question depth: factoids = 1 sentence, "
                "explanations = 2-3 sentences."
            )
            stream_temperature = 0.7
            stream_max_tokens = 120
            stream_json = False
            # Override model for chat fast-path. Read from config so this
            # can be tuned per-deployment.
            from core.config import config as _cfg
            stream_model = _cfg.get("brain", {}).get(
                "chat_fast_model", "qwen2.5:1.5b"
            )
        else:
            system_prompt = _build_system_prompt()
            stream_temperature = 0.3
            stream_max_tokens = 200
            stream_json = True
            stream_model = None  # use brain.model default

        buffer = ""
        last_emitted = 0
        in_response_field = False
        response_done = False  # set true once closing `"` of "response": "..." seen
        response_start_idx = -1
        first_chunk_emitted = False  # chat-fast: first sub-sentence chunk fired
        already_emitted_texts: set[str] = set()  # dedupe — never fire same sentence twice

        # Run the streaming generator in a worker thread, push tokens into a queue
        # that the async generator can poll. Necessary because `for piece in
        # brain.generate_stream(...)` is sync and would block the event loop.
        token_queue: Queue = Queue()

        def stream_worker():
            # On Jetson 8GB shared NvMap, the smaller chat-fast model
            # (qwen2.5:1.5b) can fail under memory pressure two ways:
            #   1. raises an exception ("llama runner process has terminated")
            #   2. completes silently with ZERO tokens emitted (Ollama returns
            #      done=true with no response field — silent runner crash)
            # Both are recoverable by retrying with the default (larger)
            # model. We stream tokens live (no buffering — preserves TTFA);
            # if the first attempt produced nothing, we kick off a second
            # attempt with the default model. The user only sees the second
            # attempt's tokens — the failed first attempt is invisible.
            tried_models = []
            current_model = stream_model
            piece_emitted = False
            for attempt in range(2):
                tried_models.append(current_model or "<default>")
                try:
                    for piece in brain.generate_stream(
                        prompt=transcribed,
                        system=system_prompt,
                        json_mode=stream_json,
                        temperature=stream_temperature,
                        max_tokens=stream_max_tokens,
                        model=current_model,
                    ):
                        if piece and piece.strip():
                            piece_emitted = True
                        token_queue.put(piece)
                    if piece_emitted:
                        break  # success — stream ended cleanly with content
                    # Stream completed but produced no real content
                    if attempt == 0 and current_model is not None:
                        log.warning(
                            "Chat-fast model %s returned empty completion "
                            "(silent crash?) — falling back to default %s",
                            current_model, brain.model,
                        )
                        current_model = None
                        continue
                    token_queue.put({
                        "__error__": f"empty completion from {tried_models}"
                    })
                    break
                except Exception as e:
                    err_text = str(e).lower()
                    is_runner_crash = (
                        "llama runner" in err_text
                        or "out of memory" in err_text
                        or "model not found" in err_text
                    )
                    if (attempt == 0 and is_runner_crash
                            and current_model is not None
                            and not piece_emitted):
                        log.warning(
                            "Chat-fast model %s failed (%s) — falling back to "
                            "default %s",
                            current_model, e, brain.model,
                        )
                        current_model = None
                        continue
                    token_queue.put({"__error__": f"{e} (tried: {tried_models})"})
                    break
            token_queue.put(None)

        threading.Thread(target=stream_worker, name="llm-stream", daemon=True).start()

        # Consumer loop: pull tokens, extract response field, fire TTS
        #
        # CRITICAL: this loop must yield to the asyncio event loop on every
        # iteration. Without it, parallel HTTP handlers (notably the
        # /api/voice/audio/{chunk_id} GET that the client uses to fetch
        # synthesized WAVs) get starved while the LLM keeps producing
        # tokens. A long response (20+ seconds of streaming) was blocking
        # all parallel GETs for the full duration. The fix is the
        # `await asyncio.sleep(0)` below — even a zero-second sleep yields
        # control to the event loop, letting other coroutines run before
        # we resume.
        while True:
            # Yield any audio that's been synthesized
            for chunk in (await drain_synth_queue()):
                if not first_audio_emitted:
                    timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                    first_audio_emitted = True
                yield chunk

            # Cooperative yield — lets parallel HTTP handlers run between
            # iterations even when LLM is producing tokens continuously.
            await asyncio.sleep(0)

            try:
                piece = token_queue.get(timeout=0.05)
            except Empty:
                # No new token yet — brief sleep to avoid busy loop
                await asyncio.sleep(0.02)
                continue

            if piece is None:
                break  # end of stream
            if isinstance(piece, dict) and "__error__" in piece:
                # LLM crashed mid-stream OR empty-completion-after-retry.
                # Emit error event AND audible error message so the user
                # knows something happened — never let them stare at silence.
                err_msg = piece["__error__"]
                log.error("Streaming LLM failed: %s", err_msg)
                yield _sse("error", {"message": err_msg})
                try:
                    active_p = personality_manager.active
                    _ensure_error_audio_for(assistant.get("voice_router"), active_p)
                    err_wav = _pick_error_wav(active_p.id)
                    if err_wav:
                        yield _audio_chunk_sse(-2, "<error>", err_wav)
                        # Mark first_audio_emitted so the post-stream fallback
                        # doesn't ALSO call process_input (which will crash too).
                        first_audio_emitted = True
                        timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                except Exception as ex:
                    log.warning("Error-audio playback failed: %s", ex)
                # Don't drop the SSE stream silently — emit done so client
                # cleanly closes and the user's UI updates.
                timings["total_ms"] = (time.monotonic() - t_total) * 1000
                yield _sse("done", {"timings": timings, "error": err_msg})
                return

            if not first_token_emitted:
                timings["first_token_ms"] = (time.monotonic() - t_total) * 1000
                first_token_emitted = True

            buffer += piece

            if chat_fast:
                # Free-form mode: every token is part of the response.
                #
                # First chunk: emit aggressively on the earliest natural
                # break (sentence end OR comma after 5 words OR 8+ words at
                # any word boundary) so the user hears audio sooner. After
                # the first chunk has fired, we fall back to whole-sentence
                # emission for the rest of the reply — Kokoro's prosody is
                # better on full sentences and the user is already hearing
                # audio so a slightly later second chunk doesn't matter for
                # perceived latency.
                pending = buffer[last_emitted:]

                while True:
                    if not first_chunk_emitted:
                        idx = _find_first_chunk_boundary(pending)
                        if idx > 0:
                            candidate = pending[:idx].strip()
                            if candidate and candidate not in already_emitted_texts:
                                already_emitted_texts.add(candidate)
                                yield _sse("response_text", {"text": candidate})
                                fire_sentence(candidate)
                                last_emitted += idx
                                pending = pending[idx:]
                                first_chunk_emitted = True
                                continue
                        break

                    # Subsequent chunks: full sentence boundaries only
                    matches = list(_SENTENCE_END_RE.finditer(pending))
                    emitted_one = False
                    for m in matches:
                        candidate = pending[: m.end()].strip()
                        if len(candidate) >= 20 and candidate not in already_emitted_texts:
                            already_emitted_texts.add(candidate)
                            yield _sse("response_text", {"text": candidate})
                            fire_sentence(candidate)
                            consumed = m.end()
                            last_emitted += consumed
                            pending = pending[consumed:]
                            emitted_one = True
                            break
                    if not emitted_one:
                        break
                # Don't run the JSON state machine in chat-fast mode
                continue

            # State machine: are we inside the "response": "..." string?
            # `response_done` latches once we've seen the closing quote, so we
            # never re-enter and re-emit the same response field a second time.
            if not in_response_field and not response_done:
                # Look for `"response":` followed by `"`
                m = re.search(r'"response"\s*:\s*"', buffer)
                if m:
                    in_response_field = True
                    response_start_idx = m.end()
                    last_emitted = response_start_idx

            if in_response_field:
                # Look for closing quote (unescaped) to know when response is done
                # Simple heuristic: scan from response_start for unescaped "
                resp_text_raw = buffer[response_start_idx:]
                end_idx = -1
                i = 0
                while i < len(resp_text_raw):
                    c = resp_text_raw[i]
                    if c == "\\":
                        i += 2
                        continue
                    if c == '"':
                        end_idx = i
                        break
                    i += 1

                # The visible response text we have so far
                if end_idx >= 0:
                    visible = resp_text_raw[:end_idx]
                else:
                    visible = resp_text_raw  # still streaming

                # Decode JSON-style escapes (\n, \", etc.) for sentence detection
                try:
                    decoded = json.loads('"' + visible.replace('"', '\\"') + '"')
                except Exception:
                    decoded = visible

                # Try to emit complete sentences from the buffered response.
                # `so_far` is what the user's reply contains so far; pending is
                # the slice we haven't TTS'd yet.
                so_far = buffer[response_start_idx:response_start_idx + len(visible)]
                pending = so_far[last_emitted - response_start_idx:]
                while True:
                    matches = list(_SENTENCE_END_RE.finditer(pending))
                    emitted_one = False
                    for m in matches:
                        candidate = pending[: m.end()].strip()
                        if len(candidate) >= 20 and candidate not in already_emitted_texts:
                            already_emitted_texts.add(candidate)
                            yield _sse("response_text", {"text": candidate})
                            fire_sentence(candidate)
                            consumed = m.end()
                            last_emitted += consumed
                            pending = pending[consumed:]
                            emitted_one = True
                            break
                    if not emitted_one:
                        break

                if end_idx >= 0:
                    # Response field is closed; flush any final remainder
                    final_remaining = (so_far[last_emitted - response_start_idx:]).strip()
                    if final_remaining and final_remaining not in already_emitted_texts:
                        already_emitted_texts.add(final_remaining)
                        yield _sse("response_text", {"text": final_remaining})
                        fire_sentence(final_remaining)
                        last_emitted = response_start_idx + len(so_far)
                    in_response_field = False
                    response_done = True  # latch — never re-enter this state

        # In chat-fast mode there's no closing JSON quote to trigger the
        # final-flush path. Emit any trailing remainder now (e.g., a single
        # sentence that doesn't have whitespace after the period because the
        # LLM stopped right at the period).
        if chat_fast:
            tail = buffer[last_emitted:].strip()
            if tail and tail not in already_emitted_texts:
                already_emitted_texts.add(tail)
                yield _sse("response_text", {"text": tail})
                fire_sentence(tail)

        # Stream is done — wait for the synth worker to finish all queued
        # sentences. We loop yielding chunks as they complete (instead of
        # blocking until ALL are done) so the client gets each sentence's
        # audio as soon as it's synthesized — even after the LLM is done.
        target_count = synth_count[0]
        emitted_audio = 0
        # Drain anything already-completed first
        for chunk in (await drain_synth_queue()):
            if not first_audio_emitted:
                timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                first_audio_emitted = True
            yield chunk
            emitted_audio += 1
        # Then block on remaining items, yielding each as it lands
        while emitted_audio < target_count:
            try:
                item = synth_out.get(timeout=20)
            except Empty:
                log.warning("TTS worker timeout: emitted %d of %d", emitted_audio, target_count)
                break
            idx, sentence, wav = item
            if not first_audio_emitted:
                timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                first_audio_emitted = True
            yield _audio_chunk_sse(idx, sentence, wav)
            emitted_audio += 1

        # If we got here without ever emitting audio (no chat reply, just a
        # non-chat intent JSON), parse the intents from buffer and run the
        # synchronous handler. This is the slower path; the streaming win is
        # specifically for chat where the LLM's "response" field is filled.
        if not first_audio_emitted:
            try:
                parsed = json.loads(buffer)
            except Exception:
                parsed = {}
            # Reuse the standard pipeline for non-chat handling
            try:
                pipe_result = process_input(assistant, transcribed)
                response_text = (
                    pipe_result[0] if isinstance(pipe_result, tuple) else pipe_result
                ) or ""
            except Exception as e:
                yield _sse("error", {"message": f"Pipeline failed: {e}"})
                # Audible error too
                try:
                    active_p = personality_manager.active
                    _ensure_error_audio_for(assistant.get("voice_router"), active_p)
                    err_wav = _pick_error_wav(active_p.id)
                    if err_wav:
                        yield _audio_chunk_sse(-2, "<error>", err_wav)
                except Exception:
                    pass
                response_text = ""
            if response_text:
                yield _sse("response_text", {"text": response_text})
                from core.voice_router import VoiceRouter
                start_idx = synth_count[0]
                for sentence in VoiceRouter._split_sentences(response_text):
                    fire_sentence(sentence)
                emitted = start_idx
                while emitted < synth_count[0]:
                    try:
                        item = synth_out.get(timeout=15)
                    except Empty:
                        break
                    idx, sent, wav = item
                    if not first_audio_emitted:
                        timings["first_audio_ms"] = (time.monotonic() - t_total) * 1000
                        first_audio_emitted = True
                    yield _audio_chunk_sse(idx, sent, wav)
                    emitted += 1

        # Tell the worker to exit (idempotent — finally will skip if already signalled)
        _signal_worker_exit()
        timings["total_ms"] = (time.monotonic() - t_total) * 1000
        yield _sse("done", {"timings": timings})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
