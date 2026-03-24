"""
Edge TTS voice provider — cloud-based TTS via Microsoft Edge's neural voices.

This is the cloud fallback provider. It uses Microsoft's neural TTS service
(the same one behind Edge browser's Read Aloud feature) — no API key needed.

When to use this:
  - Internet is available and you want the best Hindi/English quality without
    any local GPU resources
  - As a fallback when Kokoro or Piper models aren't downloaded yet
  - On a Raspberry Pi where even Kokoro might be too heavy

Trade-offs:
  + Zero local resources (all inference happens on Microsoft servers)
  + Excellent Hindi voices (hi-IN-SwaraNeural, hi-IN-MadhurNeural)
  + 60+ languages, multiple voices per language
  + Rate, pitch, volume control
  - Requires internet (breaks the "local-first" principle)
  - Latency depends on network (typically 200-500ms for short sentences)
  - Privacy: your text is sent to Microsoft's servers
  - Output is MP3, needs conversion to WAV for our playback pipeline

How Edge TTS works (the AI/ML angle):
  Microsoft's neural TTS uses a transformer-based architecture trained on
  massive speech corpora. The voices are "neural" (not concatenative or
  parametric), meaning the model generates speech from scratch rather than
  stitching together pre-recorded audio clips. The quality rivals dedicated
  local models because Microsoft trains on thousands of hours per voice.

  The edge-tts library works by connecting to the same WebSocket endpoint
  that the Edge browser uses for its Read Aloud feature. No API key needed
  because it piggybacks on the browser's free tier.

Available Hindi voices:
  hi-IN-SwaraNeural  — female, supports Empathetic/Newscast/Cheerful styles
  hi-IN-MadhurNeural — male

Available English voices (many, here are some good ones):
  en-US-AriaNeural   — female, versatile
  en-US-GuyNeural    — male
  en-GB-SoniaNeural  — British female
  en-IN-NeerjaNeural — Indian English female
  en-IN-PrabhatNeural — Indian English male

Usage:
    voice = EdgeTTSVoiceProvider()
    audio_bytes = voice.speak("Hello, how are you?", voice_model="en-US-AriaNeural")
    voice.speak_to_device("नमस्ते", voice_model="hi-IN-SwaraNeural")
"""

import asyncio
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.interfaces import VoiceProvider
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("voice.edge")

# edge-tts is an optional dependency
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    log.debug("edge-tts not installed. Install with: pip install edge-tts")


# Good default voices per language
_DEFAULT_VOICES = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "en-in": "en-IN-NeerjaNeural",  # Indian English
}


def _get_or_create_event_loop():
    """
    Get the current event loop or create a new one.

    edge-tts is async-only, but our VoiceProvider interface is sync.
    We need to bridge the gap carefully, handling cases where an event
    loop may or may not already exist.
    """
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, we can't use asyncio.run()
        # This shouldn't happen in our text-mode loop, but handle it
        return loop, True
    except RuntimeError:
        return None, False


def _run_async(coro):
    """Run an async coroutine from sync context."""
    _, in_async = _get_or_create_event_loop()
    if in_async:
        # We're inside an existing event loop — shouldn't happen in our
        # text-mode assistant, but handle gracefully
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@register("voice", "edge")
class EdgeTTSVoiceProvider(VoiceProvider):
    """
    Edge TTS provider — cloud-based, zero local resources, great Hindi.

    Config:
        voice:
          edge_default_voice: "en-US-AriaNeural"  # override default
          edge_rate: "+0%"     # speech rate adjustment
          edge_pitch: "+0Hz"   # pitch adjustment

    Personality config:
        personalities:
          profiles:
            jarvis:
              voice_provider: "edge"
              voice_model: "en-US-AriaNeural"
            devesh:
              voice_provider: "edge"
              voice_model: "en-IN-PrabhatNeural"  # Indian English male
    """

    def __init__(self, **kwargs):
        if not HAS_EDGE_TTS:
            raise ImportError(
                "edge-tts not installed. Install with: pip install edge-tts\n"
                "Note: Requires internet connection for synthesis."
            )

        voice_cfg = config.get("voice", {})
        self._default_voice = voice_cfg.get("edge_default_voice", "en-US-AriaNeural")
        self._rate = voice_cfg.get("edge_rate", "+0%")
        self._pitch = voice_cfg.get("edge_pitch", "+0Hz")

        log.info("Edge TTS ready (cloud-based, requires internet).")

    async def _synthesize(self, text: str, voice: str) -> bytes:
        """Async synthesis — returns MP3 bytes."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=self._rate,
            pitch=self._pitch,
        )

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    def speak(self, text: str, voice_model: str = "") -> bytes:
        """
        Synthesize text to WAV bytes.

        Note: Edge TTS returns MP3 internally. We convert to WAV for
        consistency with our playback pipeline. The conversion uses mpv
        or ffmpeg if available, otherwise returns raw MP3 bytes.
        """
        voice = voice_model or self._default_voice
        log.debug('Synthesizing: "%s" (voice: %s)', text[:60], voice)

        mp3_bytes = _run_async(self._synthesize(text, voice))

        if not mp3_bytes:
            log.warning("Edge TTS returned empty audio.")
            return b""

        # Convert MP3 → WAV using ffmpeg (most reliable)
        wav_bytes = self._mp3_to_wav(mp3_bytes)
        return wav_bytes if wav_bytes else mp3_bytes

    def _mp3_to_wav(self, mp3_bytes: bytes) -> bytes | None:
        """
        Convert MP3 bytes to WAV bytes using ffmpeg.

        Returns None if ffmpeg isn't available (caller should fall back
        to playing the MP3 directly).
        """
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            log.debug("ffmpeg not found — returning MP3 bytes as-is.")
            return None

        try:
            result = subprocess.run(
                [ffmpeg, "-i", "pipe:0", "-f", "wav", "-acodec", "pcm_s16le",
                 "-ar", "24000", "-ac", "1", "pipe:1"],
                input=mp3_bytes,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                log.warning("ffmpeg conversion failed: %s", result.stderr[:200])
                return None
        except Exception as e:
            log.warning("ffmpeg conversion error: %s", e)
            return None

    def speak_to_device(self, text: str, voice_model: str = "") -> None:
        """Synthesize and play through speakers."""
        voice = voice_model or self._default_voice
        log.debug('Speaking: "%s" (voice: %s)', text[:60], voice)

        mp3_bytes = _run_async(self._synthesize(text, voice))

        if not mp3_bytes:
            log.warning("Edge TTS returned empty audio.")
            return

        # Try WAV conversion + our standard playback first
        wav_bytes = self._mp3_to_wav(mp3_bytes)
        if wav_bytes:
            from providers.voice.piper_tts import _play_wav_bytes
            _play_wav_bytes(wav_bytes)
            return

        # Fallback: write MP3 to temp file and play with mpv/afplay
        self._play_mp3_bytes(mp3_bytes)

    def _play_mp3_bytes(self, mp3_bytes: bytes) -> None:
        """Play MP3 bytes using system audio player (fallback when ffmpeg unavailable)."""
        import platform as plat

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_bytes)
            tmp_path = f.name

        try:
            system = plat.system()
            if system == "Darwin" and shutil.which("afplay"):
                subprocess.run(["afplay", tmp_path], check=True)
            elif shutil.which("mpv"):
                subprocess.run(["mpv", "--no-video", "--really-quiet", tmp_path], check=True)
            elif shutil.which("ffplay"):
                subprocess.run(["ffplay", "-nodisp", "-autoexit", tmp_path], check=True)
            else:
                log.error(
                    "No audio player can play MP3. Install ffmpeg for WAV conversion, "
                    "or mpv/afplay for direct MP3 playback."
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def list_voices(self) -> list[str]:
        """
        List available Edge TTS voices.

        Returns a curated list of good voices for English and Hindi.
        The full list has 400+ voices — use `edge-tts --list-voices` for all.
        """
        return [
            # English (American)
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            # English (British)
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
            # English (Indian)
            "en-IN-NeerjaNeural",
            "en-IN-PrabhatNeural",
            # Hindi
            "hi-IN-SwaraNeural",
            "hi-IN-MadhurNeural",
        ]
