"""
Coqui XTTS v2 voice provider — high-quality TTS with voice cloning.

This is the premium voice provider for personality voices. It can clone
anyone's voice from a short audio sample (~10 seconds of clean speech).

How voice cloning works (the AI/ML angle):
  XTTS v2 uses a GPT-like architecture adapted for speech:

  1. **Speaker encoder**: Takes your reference WAV file and extracts a "speaker embedding"
     — a vector of ~512 numbers that captures the unique characteristics of that voice
     (pitch, timbre, speaking rate, accent). This is like a fingerprint for the voice.

  2. **Text encoder**: Converts input text to a sequence of language tokens.

  3. **GPT decoder**: Takes the speaker embedding + text tokens and autoregressively
     generates speech tokens (similar to how an LLM generates text tokens, but for audio).
     This is where the quality comes from — and also why it's slower than Piper.

  4. **HiFi-GAN vocoder**: Converts the speech tokens to actual audio waveform.

  The reference WAV doesn't need to say the same words — the model extracts voice
  characteristics, not content. 10 seconds of clean speech is enough. More audio
  (up to ~30 seconds) can improve quality, but has diminishing returns.

  Model size: ~1.5-2GB in VRAM. On Jetson Orin Nano (8GB shared), this fits alongside
  a 3B quantized LLM, but you'd want to lazy-load the TTS model and unload when idle.

Platform notes:
  - CUDA (Jetson, desktop GPU): Full support, ~2-3x realtime
  - MPS (Apple Silicon): NOT SUPPORTED (GitHub issue #3649, marked wontfix)
  - CPU: Works but slow (~0.3-0.5x realtime on Mac M-series)

Usage:
    voice = XTTSVoiceProvider()
    # voice_model is the path to the reference WAV
    audio = voice.speak("Hello!", voice_model="voices/xtts/devesh.wav")
    voice.speak_to_device("Playing Sajni", voice_model="voices/xtts/chandler.wav")
"""

import io
import wave
import tempfile
from pathlib import Path

from core.interfaces import VoiceProvider
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("voice.xtts")

# XTTS is a heavy optional dependency — graceful handling required.
# We catch Exception (not just ImportError) because coqui-tts can be installed
# but fail to import due to missing PyTorch, version mismatches in transformers,
# etc. — all of which raise ImportError deep in the dependency chain.
try:
    from TTS.api import TTS as CoquiTTS
    HAS_XTTS = True
except Exception as _e:
    HAS_XTTS = False
    log.debug("coqui-tts not available: %s", _e)


def _get_voices_dir() -> Path:
    """Directory where reference voice WAV files are stored for cloning."""
    voice_cfg = config.get("voice", {})
    custom_dir = voice_cfg.get("voices_dir")
    if custom_dir:
        return Path(custom_dir)
    return Path(__file__).parent.parent.parent / "voices" / "xtts"


def _detect_device() -> str:
    """
    Auto-detect the best available compute device for XTTS.

    Priority: CUDA > CPU (MPS is explicitly excluded — doesn't work with XTTS).
    """
    device_cfg = config.get("voice", {}).get("device", "auto")
    if device_cfg != "auto":
        return device_cfg

    try:
        import torch
        if torch.cuda.is_available():
            log.info("XTTS using CUDA")
            return "cuda"
    except ImportError:
        pass

    # MPS intentionally skipped — XTTS hangs on Apple Silicon MPS
    # See: https://github.com/coqui-ai/TTS/issues/3649
    log.info("XTTS using CPU (MPS not supported, CUDA not available)")
    return "cpu"


@register("voice", "xtts")
class XTTSVoiceProvider(VoiceProvider):
    """
    Coqui XTTS v2 provider — high-quality TTS with voice cloning.

    Config:
        voice:
          provider: "xtts"
          model: "tts_models/multilingual/multi-dataset/xtts_v2"
          device: "auto"          # auto = CUDA if available, else CPU (no MPS)
          voices_dir: null        # auto = assistant/voices/xtts/
          language: "en"          # XTTS supports 16 languages

    Personality voice_model should point to a reference WAV:
        personalities:
          profiles:
            devesh:
              voice_model: "devesh"  # → looks for voices/xtts/devesh.wav
            chandler:
              voice_model: "chandler"  # → looks for voices/xtts/chandler.wav
    """

    def __init__(self, **kwargs):
        if not HAS_XTTS:
            raise ImportError(
                "coqui-tts not installed. Install with: pip install coqui-tts\n"
                "Note: Requires ~2GB disk for the XTTS v2 model (auto-downloaded on first use)."
            )

        voice_cfg = config.get("voice", {})
        self._model_name = voice_cfg.get(
            "xtts_model", "tts_models/multilingual/multi-dataset/xtts_v2"
        )
        self._language = voice_cfg.get("xtts_language", "en")
        self._voices_dir = _get_voices_dir()
        self._device = _detect_device()

        # Lazy-load the model — it's 1.5-2GB, don't load at startup
        self._tts = None  # CoquiTTS instance, loaded on first speak()
        self._default_voice = voice_cfg.get("default_voice", "")

        log.info("XTTS provider ready (model loads on first speak). Device: %s", self._device)

    def _ensure_model(self):
        """Lazy-load the XTTS model on first use."""
        if self._tts is None:
            log.info("Loading XTTS model (this takes a moment on first run)...")

            # PyTorch 2.6+ changed torch.load default to weights_only=True for security.
            # Coqui TTS's checkpoint loader doesn't pass weights_only=False, so it fails
            # with newer PyTorch. We monkey-patch TTS.utils.io.load_fsspec to fix this.
            # This is safe — the XTTS model is from Coqui's official repo (trusted source).
            try:
                import torch
                import TTS.utils.io as tts_io
                _original_load_fsspec = tts_io.load_fsspec

                def _patched_load_fsspec(path, map_location=None, **kwargs):
                    kwargs.setdefault("weights_only", False)
                    return _original_load_fsspec(path, map_location=map_location, **kwargs)

                tts_io.load_fsspec = _patched_load_fsspec
                log.debug("Patched torch.load weights_only for XTTS compatibility")
            except Exception as e:
                log.debug("Could not patch load_fsspec (may not be needed): %s", e)

            gpu = self._device == "cuda"
            self._tts = CoquiTTS(model_name=self._model_name, gpu=gpu)
            log.info("XTTS model loaded.")
        return self._tts

    def _resolve_voice_path(self, voice_model: str) -> str:
        """
        Resolve a voice_model name to a WAV file path.

        Accepts:
          - Full path: "/absolute/path/to/voice.wav"
          - Relative to voices_dir: "devesh" → voices/xtts/devesh.wav
          - Relative with extension: "devesh.wav" → voices/xtts/devesh.wav
        """
        if not voice_model:
            if self._default_voice:
                voice_model = self._default_voice
            else:
                raise ValueError(
                    "No voice_model specified and no default_voice configured. "
                    "XTTS requires a reference WAV file for voice cloning. "
                    f"Place WAV files in: {self._voices_dir}/"
                )

        p = Path(voice_model)

        # Absolute path
        if p.is_absolute() and p.exists():
            return str(p)

        # Relative to voices dir
        if not p.suffix:
            p = p.with_suffix(".wav")

        candidate = self._voices_dir / p
        if candidate.exists():
            return str(candidate)

        raise FileNotFoundError(
            f"Voice reference '{voice_model}' not found. "
            f"Looked in: {candidate}. "
            f"Record ~10 seconds of clean speech and save as WAV."
        )

    def speak(self, text: str, voice_model: str = "") -> bytes:
        """
        Synthesize text using a cloned voice.

        voice_model should be the name or path of a reference WAV file
        containing ~10 seconds of the target voice speaking naturally.
        """
        tts = self._ensure_model()
        speaker_wav = self._resolve_voice_path(voice_model)

        log.debug('XTTS synthesizing: "%s" (voice: %s)', text[:60], Path(speaker_wav).stem)

        # XTTS generates to a file, so we use a temp file and read it back
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        try:
            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=self._language,
                file_path=tmp_path,
            )

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def speak_to_device(self, text: str, voice_model: str = "", interrupt_event=None) -> bool:
        """
        Synthesize with cloned voice and play through speakers.

        Returns True if playback completed, False if interrupted.
        """
        log.debug('Speaking: "%s" (voice: %s)', text[:60], voice_model or "default")
        wav_bytes = self.speak(text, voice_model)

        # Reuse Piper's playback function — it's platform-safe
        from providers.voice.piper_tts import _play_wav_bytes
        return _play_wav_bytes(wav_bytes, interrupt_event=interrupt_event)

    def list_voices(self) -> list[str]:
        """List available reference voice WAV files."""
        if not self._voices_dir.exists():
            return []
        return sorted(p.stem for p in self._voices_dir.glob("*.wav"))
