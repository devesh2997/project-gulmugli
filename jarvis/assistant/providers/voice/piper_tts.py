"""
Piper TTS voice provider — fast, CPU-friendly text-to-speech.

Piper is the default voice provider because:
  - Runs on CPU at ~5x realtime (sub-second for short responses)
  - Tiny memory footprint (~50MB per model)
  - Works on Mac, Jetson, and Pi with zero config changes
  - Pre-built voices in multiple quality tiers

Voice models are ONNX files downloaded from Hugging Face (rhasspy/piper-voices).
Each model has a .onnx file and a .onnx.json config file.

How Piper works (the AI/ML angle):
  Piper uses VITS (Variational Inference Text-to-Speech), a neural architecture
  that combines a variational autoencoder with a normalizing flow and an adversarial
  training process. In simpler terms:

  1. Text → phonemes (using espeak-ng for pronunciation)
  2. Phonemes → mel spectrogram (the "shape" of the sound, via the neural network)
  3. Mel spectrogram → raw audio waveform (via HiFi-GAN vocoder, baked into the model)

  All three steps run in a single forward pass through the ONNX model, which is why
  it's so fast — there's no autoregressive token-by-token generation like an LLM.
  The entire audio is produced in one shot.

  Quality tiers correspond to model size:
    x_low:  ~15MB, 16kHz, noticeable artifacts
    low:    ~30MB, 16kHz, decent quality
    medium: ~60MB, 22kHz, good quality (recommended)
    high:   ~100MB, 22kHz, best quality, slower

Usage:
    voice = PiperVoiceProvider()
    audio_bytes = voice.speak("Hello, how are you?")
    voice.speak_to_device("Playing Sajni by Arijit Singh")
"""

import io
import wave
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.interfaces import VoiceProvider
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("voice.piper")

# Piper is an optional dependency — handle its absence gracefully
try:
    from piper.voice import PiperVoice
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False
    log.debug("piper-tts not installed. Install with: pip install piper-tts")


def _get_models_dir() -> Path:
    """
    Directory where Piper voice models are stored.

    Uses config if set, otherwise defaults to a 'voices/piper/' directory
    next to config.yaml. Platform-safe via pathlib.
    """
    voice_cfg = config.get("voice", {})
    custom_dir = voice_cfg.get("models_dir")
    if custom_dir:
        return Path(custom_dir)
    return Path(__file__).parent.parent.parent / "voices" / "piper"


def _find_model(voice_model: str) -> tuple[Path | None, Path | None]:
    """
    Find the .onnx and .onnx.json files for a voice model.

    Searches:
      1. Exact path (if voice_model is a full path)
      2. models_dir/voice_model.onnx
      3. models_dir/voice_model/voice_model.onnx (nested folder structure)
    """
    # If it's already a full path
    p = Path(voice_model)
    if p.suffix == ".onnx" and p.exists():
        json_path = Path(str(p) + ".json")
        return p, json_path if json_path.exists() else None

    # Search in models directory
    models_dir = _get_models_dir()

    # Try: models_dir/en_US-lessac-medium.onnx
    candidate = models_dir / f"{voice_model}.onnx"
    if candidate.exists():
        json_path = Path(str(candidate) + ".json")
        return candidate, json_path if json_path.exists() else None

    # Try: models_dir/en_US-lessac-medium/en_US-lessac-medium.onnx
    candidate = models_dir / voice_model / f"{voice_model}.onnx"
    if candidate.exists():
        json_path = Path(str(candidate) + ".json")
        return candidate, json_path if json_path.exists() else None

    return None, None


def _play_wav_bytes(wav_bytes: bytes, interrupt_event=None) -> bool:
    """
    Play WAV audio bytes through the system default output.

    Uses sounddevice if available (preferred — pure Python, cross-platform),
    falls back to platform-specific commands (afplay on Mac, aplay on Linux).

    Args:
        wav_bytes: WAV audio data to play.
        interrupt_event: Optional threading.Event. If set during playback,
            audio stops immediately. Used for wake word interruption — when
            the user says "Hey Jarvis" while the assistant is speaking.

    Returns:
        True if playback completed normally, False if interrupted.
    """
    try:
        import sounddevice as sd
        import numpy as np

        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16)
                if n_channels > 1:
                    audio = audio.reshape(-1, n_channels)

                if interrupt_event is not None:
                    # Interruptible playback: start non-blocking, then poll
                    # the interrupt event every 100ms. If it fires, stop
                    # playback immediately (kills audio mid-word).
                    sd.play(audio, samplerate=sample_rate)
                    try:
                        stream = sd.get_stream()
                        while stream is not None and stream.active:
                            if interrupt_event.wait(timeout=0.1):
                                sd.stop()
                                log.info("Audio playback interrupted by wake word.")
                                return False
                    except RuntimeError:
                        # get_stream() can raise if the stream ended between
                        # play() and our first poll — that means playback
                        # finished almost instantly (very short audio).
                        pass
                else:
                    # Simple blocking playback (text mode, no interruption needed)
                    sd.play(audio, samplerate=sample_rate)
                    sd.wait()
        return True
    except ImportError:
        pass  # sounddevice not available, try fallback

    # Fallback: write to temp file and play with system command
    # Note: subprocess fallback doesn't support interrupt_event (yet).
    # To support it, we'd need to Popen + poll + terminate.
    import platform as plat
    system = plat.system()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp_path = f.name

    try:
        if system == "Darwin" and shutil.which("afplay"):
            proc = subprocess.Popen(["afplay", tmp_path])
        elif shutil.which("aplay"):
            proc = subprocess.Popen(["aplay", "-q", tmp_path])
        elif shutil.which("mpv"):
            proc = subprocess.Popen(["mpv", "--no-video", "--really-quiet", tmp_path])
        else:
            log.error("No audio player found. Install sounddevice: pip install sounddevice")
            return True

        # Poll for interrupt or completion
        if interrupt_event is not None:
            while proc.poll() is None:
                if interrupt_event.wait(timeout=0.1):
                    proc.terminate()
                    proc.wait(timeout=2.0)
                    log.info("Audio playback interrupted (subprocess).")
                    return False
        else:
            proc.wait()
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@register("voice", "piper")
class PiperVoiceProvider(VoiceProvider):
    """
    Piper TTS provider — fast, local, CPU-friendly.

    Config:
        voice:
          provider: "piper"
          model: "en_US-lessac-medium"  # default voice
          models_dir: null              # auto = assistant/voices/piper/
    """

    def __init__(self, **kwargs):
        if not HAS_PIPER:
            raise ImportError(
                "piper-tts not installed. Install with: pip install piper-tts\n"
                "Then download a voice model:\n"
                "  mkdir -p voices/piper\n"
                "  # Download from https://huggingface.co/rhasspy/piper-voices"
            )

        voice_cfg = config.get("voice", {})
        self._default_model = voice_cfg.get("model", "en_US-lessac-medium")
        self._models_dir = _get_models_dir()
        self._loaded: dict = {}  # cache loaded models (str → PiperVoice)

        log.info("Piper TTS ready. Models dir: %s", self._models_dir)

    def _get_voice(self, voice_model: str = ""):
        """Load and cache a Piper voice model."""
        model_name = voice_model or self._default_model

        if model_name in self._loaded:
            return self._loaded[model_name]

        model_path, config_path = _find_model(model_name)
        if model_path is None:
            available = self.list_voices()
            raise FileNotFoundError(
                f"Piper model '{model_name}' not found in {self._models_dir}. "
                f"Available: {available}. "
                f"Download from: https://huggingface.co/rhasspy/piper-voices"
            )

        log.debug("Loading Piper model: %s", model_path)
        voice = PiperVoice.load(str(model_path), config_path=str(config_path) if config_path else None)
        self._loaded[model_name] = voice
        return voice

    def speak(self, text: str, voice_model: str = "") -> bytes:
        """
        Synthesize text to WAV bytes.

        Piper 1.4+ returns an Iterable[AudioChunk] from synthesize().
        Each chunk has audio_int16_bytes (PCM), sample_rate, sample_width,
        and sample_channels. We collect all chunks and write a single WAV.
        """
        voice = self._get_voice(voice_model)

        # Collect all audio chunks (one per sentence)
        pcm_parts = []
        sample_rate = 22050
        sample_width = 2
        n_channels = 1

        for chunk in voice.synthesize(text):
            sample_rate = chunk.sample_rate
            sample_width = chunk.sample_width
            n_channels = chunk.sample_channels
            pcm_parts.append(chunk.audio_int16_bytes)

        if not pcm_parts:
            return b""

        # Build a proper WAV file from the raw PCM
        pcm_data = b"".join(pcm_parts)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(n_channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        return buf.getvalue()

    def speak_to_device(self, text: str, voice_model: str = "", interrupt_event=None) -> bool:
        """
        Synthesize and play through speakers.

        Returns True if playback completed, False if interrupted.
        """
        log.debug('Speaking: "%s" (voice: %s)', text[:60], voice_model or self._default_model)
        wav_bytes = self.speak(text, voice_model)
        return _play_wav_bytes(wav_bytes, interrupt_event=interrupt_event)

    def list_voices(self) -> list[str]:
        """List available voice models in the models directory."""
        if not self._models_dir.exists():
            return []
        # Find all .onnx files
        voices = []
        for p in self._models_dir.rglob("*.onnx"):
            # Return the stem without .onnx
            voices.append(p.stem)
        return sorted(voices)
