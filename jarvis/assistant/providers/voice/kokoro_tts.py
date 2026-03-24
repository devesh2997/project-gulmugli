"""
Kokoro TTS voice provider — the sweet spot between Piper and XTTS.

Kokoro is the recommended default TTS for this project because:
  - 82M parameters (~350MB) — fits alongside a 3B LLM on Jetson
  - Ranked #1 on TTS Arena despite being 5.7x smaller than XTTS
  - Native Hindi support with dedicated Hindi voices
  - Sub-0.3 second inference on GPU, ~3-11x realtime on CPU
  - Apache 2.0 license — no restrictions
  - ONNX variant available — no PyTorch dependency needed

How Kokoro works (the AI/ML angle):
  Kokoro uses a StyleTTS2-inspired architecture with a few key innovations:

  1. **Text → Phonemes**: Uses espeak-ng (PyTorch version) or a built-in
     phonemizer (ONNX version) to convert text to IPA phonemes.

  2. **Phoneme encoder**: Encodes phoneme sequences into a latent representation.

  3. **Style/voice conditioning**: Each of the 48 preset voices is a learned
     "style vector" — a set of numbers that captures the voice characteristics.
     Unlike XTTS, these aren't extracted from audio at runtime; they were learned
     during training and are stored in a voices.bin file (~voice embeddings).

  4. **Flow-matching decoder**: Generates mel spectrograms from the phoneme
     encoding + style vector. This is similar to diffusion but more efficient.

  5. **HiFi-GAN vocoder**: Converts mel spectrogram to audio waveform.

  The key insight: by using pre-computed style vectors instead of runtime
  speaker encoding, Kokoro skips the expensive voice analysis step that makes
  XTTS slow. Trade-off: no voice cloning, but 48 high-quality preset voices
  including Hindi male/female.

Available voices:
  English (American): af_heart, af_bella, af_sarah, af_sky, af_nova, af_jessica,
                      af_nicole, af_river, af_alloy, af_aoede, af_kore,
                      am_adam, am_michael, am_echo, am_liam, am_onyx, am_puck, am_santa
  English (British):  bf_emma, bf_isabella, bf_alice, bf_lily,
                      bm_daniel, bm_fable, bm_george, bm_lewis
  Hindi:              hf_alpha, hf_beta, hm_omega, hm_psi
  + Spanish, French, Italian, Portuguese, Japanese, Mandarin

We use the kokoro-onnx variant (not the PyTorch one) because:
  - No PyTorch dependency (lighter install, no conflict with XTTS's torch)
  - ONNX Runtime works on Mac, Jetson (CUDA EP), and Pi (CPU)
  - FP16 model is only 169MB, INT8 is 88MB
  - API is simpler: kokoro.create(text, voice, lang) → (samples, sample_rate)

Model files needed (download from HuggingFace or GitHub releases):
  voices/kokoro/kokoro-v1.0.onnx       (310MB FP32, or fp16/int8 variants)
  voices/kokoro/voices-v1.0.bin         (voice embeddings)

Usage:
    voice = KokoroVoiceProvider()
    audio_bytes = voice.speak("Hello, how are you?", voice_model="af_heart")
    voice.speak_to_device("नमस्ते", voice_model="hf_alpha")
"""

import io
import wave
import numpy as np
from pathlib import Path

from core.interfaces import VoiceProvider
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("voice.kokoro")

# kokoro-onnx is an optional dependency
try:
    from kokoro_onnx import Kokoro
    HAS_KOKORO = True
except ImportError:
    HAS_KOKORO = False
    log.debug("kokoro-onnx not installed. Install with: pip install kokoro-onnx")


# ═══════════════════════════════════════════════════════════════
# Voice → language mapping
# ═══════════════════════════════════════════════════════════════

# Kokoro voices follow a naming convention: prefix determines language
_VOICE_LANG_MAP = {
    "af_": "en-us",  # American Female
    "am_": "en-us",  # American Male
    "bf_": "en-gb",  # British Female
    "bm_": "en-gb",  # British Male
    "hf_": "hi",     # Hindi Female
    "hm_": "hi",     # Hindi Male
    "ef_": "es",     # Spanish Female
    "em_": "es",     # Spanish Male
    "ff_": "fr",     # French Female
    "fm_": "fr",     # French Male
    "if_": "it",     # Italian Female
    "im_": "it",     # Italian Male
    "pf_": "pt-br",  # Portuguese Female
    "pm_": "pt-br",  # Portuguese Male
    "jf_": "ja",     # Japanese Female
    "jm_": "ja",     # Japanese Male
    "zf_": "cmn",    # Mandarin Female
    "zm_": "cmn",    # Mandarin Male
}

# All known voices for validation and listing
_ALL_VOICES = [
    # American English
    "af_heart", "af_bella", "af_sarah", "af_sky", "af_nova", "af_jessica",
    "af_nicole", "af_river", "af_alloy", "af_aoede", "af_kore",
    "am_adam", "am_michael", "am_echo", "am_liam", "am_onyx", "am_puck", "am_santa",
    # British English
    "bf_emma", "bf_isabella", "bf_alice", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    # Hindi
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    # Spanish
    "ef_dora", "em_alex",
    # French
    "ff_siwis",
    # Italian
    "if_sara", "im_nicola",
    # Portuguese
    "pf_dora",
    # Japanese
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jm_kumo",
    # Mandarin
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zm_yunjian",
]


def _get_models_dir() -> Path:
    """Directory where Kokoro model files are stored."""
    voice_cfg = config.get("voice", {})
    custom_dir = voice_cfg.get("kokoro_models_dir")
    if custom_dir:
        return Path(custom_dir)
    return Path(__file__).parent.parent.parent / "voices" / "kokoro"


def _detect_lang(voice_name: str) -> str:
    """
    Auto-detect language from voice name prefix.

    "af_heart" → "en-us", "hf_alpha" → "hi", etc.
    Falls back to "en-us" for unknown prefixes.
    """
    prefix = voice_name[:3] if len(voice_name) >= 3 else ""
    return _VOICE_LANG_MAP.get(prefix, "en-us")


def _samples_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """
    Convert float32 numpy audio samples to WAV bytes.

    Kokoro returns float32 samples in [-1.0, 1.0] range at 24kHz.
    We convert to int16 PCM and wrap in a WAV container.
    """
    # Clip and convert to int16
    samples_int16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)       # Kokoro outputs mono
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int16.tobytes())

    return buf.getvalue()


@register("voice", "kokoro")
class KokoroVoiceProvider(VoiceProvider):
    """
    Kokoro TTS provider — high quality, fast, multilingual, lightweight.

    Config (all optional — sensible defaults):
        voice:
          kokoro_models_dir: null          # auto = assistant/voices/kokoro/
          kokoro_model: "kokoro-v1.0.onnx" # or fp16/int8 variants

    Personality config:
        personalities:
          profiles:
            jarvis:
              voice_provider: "kokoro"
              voice_model: "af_heart"      # any of the 48 preset voices
            devesh:
              voice_provider: "kokoro"
              voice_model: "hm_omega"      # Hindi male voice
    """

    def __init__(self, **kwargs):
        if not HAS_KOKORO:
            raise ImportError(
                "kokoro-onnx not installed. Install with: pip install kokoro-onnx\n"
                "Then download model files to voices/kokoro/:\n"
                "  kokoro-v1.0.onnx (or fp16/int8 variant)\n"
                "  voices-v1.0.bin\n"
                "From: https://github.com/thewh1teagle/kokoro-onnx/releases"
            )

        voice_cfg = config.get("voice", {})
        self._models_dir = _get_models_dir()
        self._model_name = voice_cfg.get("kokoro_model", "kokoro-v1.0.onnx")
        self._default_voice = voice_cfg.get("kokoro_default_voice", "af_heart")

        # Lazy-load the model
        self._kokoro = None  # Kokoro instance, loaded on first speak()

        log.info(
            "Kokoro TTS ready (model loads on first speak). Models dir: %s",
            self._models_dir,
        )

    def _ensure_model(self):
        """Lazy-load the Kokoro ONNX model on first use."""
        if self._kokoro is not None:
            return self._kokoro

        model_path = self._models_dir / self._model_name
        voices_path = self._models_dir / "voices-v1.0.bin"

        if not model_path.exists():
            # Try common variants
            for variant in ["kokoro-v1.0.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.int8.onnx"]:
                candidate = self._models_dir / variant
                if candidate.exists():
                    model_path = candidate
                    break
            else:
                raise FileNotFoundError(
                    f"Kokoro model not found in {self._models_dir}. "
                    f"Download kokoro-v1.0.onnx and voices-v1.0.bin from:\n"
                    f"  https://github.com/thewh1teagle/kokoro-onnx/releases"
                )

        if not voices_path.exists():
            raise FileNotFoundError(
                f"Kokoro voices file not found: {voices_path}. "
                f"Download voices-v1.0.bin from:\n"
                f"  https://github.com/thewh1teagle/kokoro-onnx/releases"
            )

        log.info("Loading Kokoro model: %s", model_path.name)
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        log.info("Kokoro model loaded.")
        return self._kokoro

    def speak(self, text: str, voice_model: str = "") -> bytes:
        """
        Synthesize text to WAV bytes.

        voice_model: one of Kokoro's 48 preset voices (e.g., "af_heart", "hm_omega").
                     Language is auto-detected from the voice prefix.
        """
        kokoro = self._ensure_model()
        voice = voice_model or self._default_voice
        lang = _detect_lang(voice)

        log.debug('Synthesizing: "%s" (voice: %s, lang: %s)', text[:60], voice, lang)

        samples, sample_rate = kokoro.create(
            text=text,
            voice=voice,
            speed=1.0,
            lang=lang,
        )

        return _samples_to_wav(samples, sample_rate)

    def speak_to_device(self, text: str, voice_model: str = "") -> None:
        """Synthesize and play through speakers."""
        log.debug('Speaking: "%s" (voice: %s)', text[:60], voice_model or self._default_voice)
        wav_bytes = self.speak(text, voice_model)

        # Reuse Piper's cross-platform playback function
        from providers.voice.piper_tts import _play_wav_bytes
        _play_wav_bytes(wav_bytes)

    def list_voices(self) -> list[str]:
        """List all available Kokoro preset voices."""
        return list(_ALL_VOICES)
