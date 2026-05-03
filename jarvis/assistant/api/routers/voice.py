"""
Voice endpoint — full audio-in / audio-out pipeline on the server.

This endpoint mirrors what main.py --voice does, but exposed over HTTP so
remote clients (e.g. a Mac dev box, a browser, the AMOLED dashboard) can
act as dumb mic+speaker while ALL processing — STT, intent classification,
chat, TTS — runs on the server.

This is the right shape for measuring real production latency: the client
contributes only network round-trip + capture/playback, exactly what the
final on-Jetson appliance will look like (once the ReSpeaker mic and
speaker are wired in).

POST /api/voice with multipart/form-data:
  audio: WAV file (preferred) or raw PCM int16 mono 16kHz bytes

Response (application/json):
  {
    "ok": true,
    "transcribed": "what time is it",
    "response": "It's 06:01 PM.",
    "audio_b64": "<base64 WAV bytes of the spoken response, or null if TTS off>",
    "audio_format": "wav",
    "timings": {
      "stt_ms":      1234,
      "pipeline_ms": 5678,
      "tts_ms":       901,
      "total_ms":    7813
    }
  }
"""

import base64
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.auth import verify_token
from api.deps import get_assistant
from core.logger import get_logger
from core.personality import personality_manager
from core.pipeline import process_input

log = get_logger("api.voice")

router = APIRouter(dependencies=[Depends(verify_token)])


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


@router.post("/api/voice", response_model=VoiceResponse)
async def voice(
    audio: UploadFile = File(...),
    assistant: dict = Depends(get_assistant),
):
    """
    Full audio-in / audio-out pipeline.

    Pipeline stages (timed individually so clients can see where time goes):
      1. STT — assistant["ears"].transcribe(audio_bytes)
      2. process_input — intent classify + handler + chat reply
      3. TTS — voice_router.speak(response_text, active_personality)

    All three run on the server. The client just sent audio and will get
    audio back. Latency you observe here is what production will feel like
    once the mic/speaker are physically on the Jetson.
    """
    t_total = time.monotonic()

    ears = assistant.get("ears")
    if not ears:
        return VoiceResponse(
            ok=False,
            error="STT (ears) provider is not configured. Check config.yaml ears section.",
        )

    # 1. Read uploaded audio
    audio_bytes = await audio.read()
    if not audio_bytes:
        return VoiceResponse(ok=False, error="Empty audio upload.")
    log.info("Voice request: %d bytes (filename=%s, content_type=%s)",
             len(audio_bytes), audio.filename, audio.content_type)

    # 2. STT
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
            transcribed="",
            response="",
            timings=VoiceTimings(
                stt_ms=stt_ms, pipeline_ms=0, tts_ms=0,
                total_ms=(time.monotonic() - t_total) * 1000,
            ),
        )

    log.info("Voice transcribed: %r [lang=%s, %.0f%% conf]",
             transcribed, result.language, result.confidence * 100)

    # 3. Pipeline (intent classify + execute + reply)
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

    # 4. TTS — synthesize the response audio (might be None if voice disabled)
    t_tts = time.monotonic()
    audio_b64 = None
    try:
        vr = assistant.get("voice_router")
        active_personality = personality_manager.active
        wav_bytes = vr.speak(response_text, active_personality) if (vr and response_text) else None
        if wav_bytes:
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    except Exception as e:
        # TTS failures are non-fatal — return the text response anyway.
        log.warning("TTS failed (non-fatal): %s", e)
    tts_ms = (time.monotonic() - t_tts) * 1000

    total_ms = (time.monotonic() - t_total) * 1000

    log.info(
        "Voice round-trip: %.0fms total (stt=%.0fms, pipeline=%.0fms, tts=%.0fms)",
        total_ms, stt_ms, pipeline_ms, tts_ms,
    )

    return VoiceResponse(
        ok=True,
        transcribed=transcribed,
        response=response_text,
        audio_b64=audio_b64,
        audio_format="wav",
        timings=VoiceTimings(
            stt_ms=stt_ms,
            pipeline_ms=pipeline_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
        ),
    )
