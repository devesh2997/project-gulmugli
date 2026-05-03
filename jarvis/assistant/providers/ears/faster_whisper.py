"""
Faster Whisper speech-to-text provider.

Uses CTranslate2-optimized Whisper models for local, offline transcription.
This is the primary STT engine — it runs entirely on-device with no internet needed.

How faster-whisper works (the AI/ML angle):
  OpenAI's Whisper is a transformer-based encoder-decoder model trained on 680,000 hours
  of multilingual audio. It's remarkably good at handling accented English, Hindi, and
  code-switching (Hinglish) because the training data includes massive amounts of
  non-native English and multilingual content.

  faster-whisper is a CTranslate2 port that runs 4x faster than the original PyTorch
  Whisper with the same accuracy. CTranslate2 achieves this through:
    - INT8 quantization (reduces model size and speeds up inference)
    - Batch decoding optimizations
    - KV-cache reuse across beam search hypotheses

  Model sizes and their tradeoffs:
    tiny   (~39M params, ~75MB)  — fastest, least accurate, fine for clear English
    base   (~74M params, ~142MB) — good balance for voice commands (recommended for v1)
    small  (~244M params, ~466MB) — noticeably better for Hindi and accented speech
    medium (~769M params, ~1.5GB) — excellent multilingual, but heavy for Jetson
    large-v3 (~1.5B, ~3GB)       — best quality, too heavy for 8GB Jetson alongside LLM

  For the Jetson (8GB shared), "base" or "small" is the sweet spot. "base" leaves more
  room for the LLM, "small" is better for Hindi. On Mac, you can use "small" or "medium".

  Language detection is automatic — Whisper figures out if you're speaking English, Hindi,
  or Hinglish without being told. You can also force a language if auto-detect is wrong.

Platform notes:
  - CUDA (Jetson): Full acceleration via CTranslate2's CUDA backend. ~10x realtime on base.
  - CPU (Mac/Pi): Uses CTranslate2's CPU optimizations (INT8). ~3-5x realtime on base.
  - MPS: NOT supported by CTranslate2. Falls back to CPU on Apple Silicon.
    (Still fast enough — base model transcribes 5 seconds of audio in <1 second on M1.)

Usage:
    ears = FasterWhisperProvider()
    result = ears.transcribe(audio_bytes)       # from mic
    result = ears.transcribe_file("test.wav")   # from file
    print(result.text, result.language)          # "play Sajni", "en"
"""

import io
import os
import time
import tempfile
import numpy as np
from pathlib import Path

from core.interfaces import EarsProvider, TranscriptionResult
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("ears.whisper")

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False
    log.debug("faster-whisper not installed. Install with: pip install faster-whisper")


def _detect_device() -> str:
    """
    Auto-detect the best compute device for Whisper inference.

    CTranslate2 supports: cuda, cpu, auto.
    MPS is NOT supported — falls back to CPU on Apple Silicon.
    "auto" lets CTranslate2 decide (picks CUDA if available).
    """
    device_cfg = config.get("ears", {}).get("device", "auto")
    if device_cfg != "auto":
        return device_cfg

    # On Jetson 8GB, both Whisper (when on CUDA) and the Ollama LLM live in
    # the same shared NvMap pool. Loading order matters: if Whisper allocates
    # before the LLM gets its full KV cache, NvMap fragments enough that new
    # LLM allocations (per-request KV cache for incoming queries) fail with
    # "llama runner process has terminated" mid-request.
    #
    # We dodge this by detecting via CTranslate2 directly (not torch — the
    # stock pip torch wheel is CPU-only on aarch64) AND by ensuring at the
    # service level that Ollama is fully warmed before JARVIS starts (the
    # systemd ordering: ollama.service before jarvis-assistant.service).
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass

    # Fallback: torch (covers x86 Linux + dGPU machines)
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass

    return "cpu"


def _detect_compute_type(device: str) -> str:
    """
    Pick the best quantization level for the device.

    Quantization reduces model size and speeds up inference at a tiny accuracy cost.
    - float16: Best for CUDA GPUs (fast, good accuracy)
    - int8: Best for CPU (fastest on x86/ARM, slight accuracy loss)
    - float32: Fallback if nothing else works
    """
    compute_cfg = config.get("ears", {}).get("compute_type", "auto")
    if compute_cfg != "auto":
        return compute_cfg

    if device == "cuda":
        # int8_float16 cuts Whisper VRAM roughly in half (~250MB vs ~470MB
        # for "small") with negligible accuracy cost on short voice commands.
        # On Jetson 8GB shared memory the saving matters — it leaves room for
        # the LLM's KV cache to grow under multi-turn conversations without
        # hitting NvMap allocation failures.
        # Override to "float16" via config if VRAM isn't constrained (dGPU box).
        return "int8_float16"
    else:
        return "int8"


@register("ears", "faster_whisper")
class FasterWhisperProvider(EarsProvider):
    """
    CTranslate2-optimized Whisper for fast local STT.

    Config (config.yaml):
        ears:
          provider: "faster_whisper"
          model_size: "base"      # tiny, base, small, medium, large-v3
          language: "auto"        # auto-detect, or force: "en", "hi"
          device: "auto"          # auto (CUDA if available, else CPU)
          compute_type: "auto"    # auto (float16 for CUDA, int8 for CPU)
          beam_size: 5            # beam search width (higher = more accurate, slower)
          vad_filter: true        # voice activity detection — skips silence
    """

    def __init__(self, **kwargs):
        if not HAS_FASTER_WHISPER:
            raise ImportError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        ears_cfg = config.get("ears", {})
        self._model_size = kwargs.get("model_size") or ears_cfg.get("model_size", "base")
        self._language = ears_cfg.get("language", "auto")
        self._beam_size = ears_cfg.get("beam_size", 5)
        self._vad_filter = ears_cfg.get("vad_filter", True)
        self._device = _detect_device()
        self._compute_type = _detect_compute_type(self._device)

        # Initial prompt — biases the decoder toward expected vocabulary.
        # This is a key Whisper trick: the model's decoder is autoregressive,
        # so providing a "prompt" of example text makes it more likely to
        # produce similar vocabulary. For Hindi/Hinglish voice commands,
        # we prime it with common Hindi words, Bollywood terms, and the kinds
        # of phrases our users actually say. This dramatically improves
        # Hindi transcription accuracy without any fine-tuning.
        #
        # IMPORTANT: keep this BALANCED across English and Hindi. Earlier
        # versions had an all-Hindi prompt; on noisy/compressed real-mic
        # input, Whisper would hallucinate Hindi words (e.g., "what is the
        # speed of light" → "Kya sam sam"). The fix is to seed examples in
        # both languages so the decoder doesn't drift toward Devanagari
        # transliteration when uncertain.
        self._initial_prompt = ears_cfg.get("initial_prompt", (
            # English chat / questions
            "What is the speed of light? Who invented the telephone? "
            "Tell me about black holes. How does photosynthesis work? "
            # English commands
            "Lights off. Volume up. Pause the music. "
            "Play Sajni by Arijit Singh. Set lights to blue. "
            # Hindi / Hinglish (kept lighter than before)
            "Gaana bajao. Lights band karo. Kya time ho raha hai? "
            "Sajni ka gaana lagao. Romantic mode."
        ))

        # Model identifier: can be a standard size ("base", "small", "medium")
        # OR a HuggingFace model path ("vasista22/whisper-hindi-small").
        # faster-whisper handles both natively — if the string contains "/",
        # it downloads from HuggingFace Hub. This lets us swap in fine-tuned
        # Hindi models without any code changes, just a config edit.
        #
        # Good Hindi-tuned options to try:
        #   "vasista22/whisper-hindi-small"  — fine-tuned on Hindi data, small size
        #   "vasista22/whisper-hindi-medium" — fine-tuned on Hindi data, medium size
        #   "ai4bharat/whisper-medium-hi"    — AI4Bharat's Hindi model
        model_id = self._model_size  # works for both "medium" and "org/model-name"

        # Load model immediately — STT needs to be ready the moment someone speaks.
        # Unlike TTS (lazy-loaded), STT is on the critical path of every interaction.
        log.info(
            "Loading Whisper %s on %s (%s)...",
            model_id, self._device, self._compute_type,
        )
        self._model = WhisperModel(
            model_id,
            device=self._device,
            compute_type=self._compute_type,
        )
        log.info("Whisper %s ready.", self._model_size)

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe raw audio bytes (PCM or WAV) to text.

        audio_data: Raw audio bytes. Can be:
          - WAV file bytes (with header)
          - Raw PCM int16 mono 16kHz bytes (no header)
        sample_rate: Only used for raw PCM. WAV header takes precedence.

        Converts to a float32 numpy array and passes directly to faster-whisper,
        avoiding temp file I/O entirely. faster-whisper accepts numpy arrays
        natively — this saves ~1-2ms per transcription vs the file path.

        OOM resilience: on Jetson 8GB shared NvMap, Whisper occasionally hits
        "CUDA failed with error out of memory" when other CUDA users (Ollama,
        Kokoro) have fragmented the pool. We catch that, build a CPU fallback
        model on demand, and retry. The CPU model is cached after the first
        OOM so subsequent OOMs reuse it without rebuild cost.
        """
        if audio_data[:4] == b'RIFF':
            # WAV file — parse header to extract raw PCM samples
            import wave
            with wave.open(io.BytesIO(audio_data), 'rb') as wf:
                sample_rate = wf.getframerate()
                raw_pcm = wf.readframes(wf.getnframes())
        else:
            # Already raw PCM int16 mono
            raw_pcm = audio_data

        # Convert int16 PCM to float32 in [-1.0, 1.0] — the format
        # faster-whisper expects for numpy input.
        samples = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            return self._transcribe_audio(samples, sample_rate)
        except Exception as e:
            err = str(e).lower()
            is_oom = "out of memory" in err or "nvmap" in err or (
                "cuda" in err and "failed" in err
            )
            if not is_oom or self._device != "cuda":
                raise
            # Strategy: rebuild the CUDA Whisper model from scratch. On Jetson
            # 8GB shared NvMap, OOM is almost always fragmentation rather than
            # genuine exhaustion — releasing the model and reallocating gives
            # the allocator a clean slate. CPU fallback is unreliable on
            # aarch64 (CTranslate2's "No SGEMM backend on CPU" error has bitten
            # us) so we prefer to retry on CUDA.
            log.warning(
                "Whisper CUDA OOM — rebuilding model on CUDA (NvMap fragmentation). "
                "Error: %s", e,
            )
            return self._rebuild_and_retry(samples, sample_rate)

    def _rebuild_and_retry(self, samples: np.ndarray, sample_rate: int,
                           attempts: int = 2) -> TranscriptionResult:
        """
        Drop the existing CUDA Whisper model, free its memory, build a fresh
        one, and retry. Falls back to CPU only if all CUDA rebuilds fail.
        """
        import gc
        for attempt in range(attempts):
            try:
                # Drop existing model — its CUDA buffers will be freed on GC
                self._model = None
                gc.collect()
                # Hint CUDA to release cached blocks (works for ctranslate2's
                # CUDA backend if torch is also installed; safe no-op otherwise)
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

                log.info(
                    "Rebuilding Whisper %s on CUDA (attempt %d/%d)...",
                    self._model_size, attempt + 1, attempts,
                )
                self._model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                )
                # Try the transcription on the fresh model
                return self._transcribe_audio(samples, sample_rate)
            except Exception as e:
                log.warning(
                    "Rebuild attempt %d failed: %s", attempt + 1, e,
                )
                continue

        # All CUDA rebuild attempts failed — last-ditch CPU fallback.
        log.error(
            "All CUDA rebuild attempts failed; trying CPU fallback. "
            "If you see 'No SGEMM backend on CPU' next, this Jetson's "
            "CTranslate2 wheel doesn't support CPU inference for this model."
        )
        return self._transcribe_with_cpu_fallback(samples, sample_rate)

    def _transcribe_with_cpu_fallback(self, samples: np.ndarray,
                                      sample_rate: int) -> TranscriptionResult:
        """
        Build a CPU-only Whisper model on first OOM, cache it, and run on CPU.

        On Jetson 8GB this is a last-ditch path. CPU compute_types depend on
        what BLAS the CTranslate2 wheel was built against — on aarch64 stock
        wheels often don't ship a SGEMM backend, in which case all of these
        will fail and we re-raise.
        """
        if not hasattr(self, "_cpu_model") or self._cpu_model is None:
            log.info("Building Whisper %s CPU fallback...", self._model_size)
            last_err = None
            for ct in ("int8_float32", "int16", "float32"):
                try:
                    self._cpu_model = WhisperModel(
                        self._model_size, device="cpu", compute_type=ct,
                    )
                    log.info("Whisper CPU fallback ready (compute_type=%s).", ct)
                    break
                except Exception as e:
                    log.warning("CPU compute_type=%s failed: %s", ct, e)
                    last_err = e
            else:
                self._cpu_model = None
                raise RuntimeError(
                    f"All CPU compute_types failed for Whisper fallback. "
                    f"Last error: {last_err}"
                )

        gpu_model = self._model
        self._model = self._cpu_model
        try:
            return self._transcribe_audio(samples, sample_rate)
        finally:
            self._model = gpu_model

    def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe an audio file to text.

        Accepts any format ffmpeg can read: WAV, MP3, M4A, FLAC, OGG, etc.
        faster-whisper handles format conversion internally via ffmpeg.
        """
        return self._transcribe_audio(file_path)

    def _transcribe_audio(self, audio_input, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Core transcription — accepts a file path (str) or numpy array (float32).

        faster-whisper's model.transcribe() natively handles both:
          - str/Path: reads from disk (uses ffmpeg, supports any audio format)
          - numpy array: processes directly in memory (zero I/O, fastest path)

        For real-time voice input, numpy is always preferred — it skips the
        temp file write + read + unlink that the file path requires.
        """
        start = time.time()

        # Language setting: None = auto-detect, else force
        language = None if self._language == "auto" else self._language

        segments, info = self._model.transcribe(
            audio_input,
            language=language,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            # Initial prompt biases the decoder toward Hindi/Hinglish vocabulary.
            # This is NOT a system prompt — it's prepended to the decoder's context
            # so the model "expects" Hindi words and produces them more accurately.
            initial_prompt=self._initial_prompt,
            # VAD parameters tuned for voice commands (short utterances):
            vad_parameters=dict(
                min_silence_duration_ms=300,   # 300ms silence = end of utterance
                speech_pad_ms=200,             # pad speech segments by 200ms
            ) if self._vad_filter else None,
        )

        # Collect all segments into full text
        full_text = ""
        segment_count = 0
        for segment in segments:
            full_text += segment.text
            segment_count += 1

        full_text = full_text.strip()
        latency = time.time() - start

        detected_lang = info.language or "unknown"
        confidence = info.language_probability or 0.0

        log.info(
            'Transcribed (%s, %.0f%% confident, %.2fs): "%s"',
            detected_lang,
            confidence * 100,
            latency,
            full_text[:80],
        )

        return TranscriptionResult(
            text=full_text,
            language=detected_lang,
            confidence=confidence,
            latency=latency,
        )
