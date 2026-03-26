"""
OpenWakeWord provider — neural wake word detection.

OpenWakeWord runs a small neural network (~1-2MB per wake word model) that
processes 80ms audio chunks and outputs a confidence score for each registered
wake word. It ships with pre-trained models including "hey_jarvis", and
supports custom-trained models for any phrase.

How it works (the ML bit):
    The library uses a two-stage architecture:
    1. Feature extraction — a frozen encoder (based on Google's audio
       embedding model) converts raw audio into mel-spectrogram features.
       This runs once and is shared across all wake word models.
    2. Per-word classifier — a tiny ONNX model (~500KB) takes those features
       and outputs a 0-1 confidence score for its specific wake word.

    Because the feature extractor is shared and the per-word classifiers are
    tiny, running 5 wake words costs barely more than running 1.

How this provider uses it:
    - A background thread continuously reads 80ms chunks from the mic
    - Each chunk is fed to all loaded wake word models simultaneously
    - When any model's confidence exceeds the threshold, we fire the callback
    - The callback includes WHICH wake word triggered, so the main loop can
      switch personalities accordingly
    - While recording a command (pause_listening), we keep reading the mic
      but skip predictions — this prevents self-triggering on TTS output

Audio format:
    - 16kHz sample rate, mono, int16 — same as faster-whisper
    - Chunk size: 1280 samples = 80ms (OpenWakeWord's native frame size)
"""

import threading
import time
from typing import Callable, Optional

from core.config import config
from core.logger import get_logger
from core.interfaces import WakeWordProvider, WakeWordDetection
from core.registry import register

log = get_logger("wake.oww")

# ── Guard import ────────────────────────────────────────────────
try:
    from openwakeword.model import Model as OWWModel
    import openwakeword
    HAS_OWW = True
except ImportError:
    HAS_OWW = False

try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except (ImportError, OSError):
    HAS_AUDIO = False


# ── Constants ───────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280       # 80ms at 16kHz — OpenWakeWord's native frame size
CHANNELS = 1


@register("wake_word", "openwakeword")
class OpenWakeWordProvider(WakeWordProvider):
    """
    Wake word detection via OpenWakeWord.

    Supports multiple simultaneous wake words, each optionally mapped to a
    personality. The system wake word (from config.assistant.wake_word) always
    activates without switching personality. Per-personality wake words switch
    to that personality before recording the command.

    Config:
        wake_word:
          provider: "openwakeword"
          sensitivity: 0.5
          cooldown: 2.0         # seconds between detections (prevents rapid re-trigger)
          custom_models: []     # paths to custom .onnx/.tflite models
    """

    def __init__(self, **kwargs):
        if not HAS_OWW:
            raise ImportError(
                "openwakeword not installed. Install with: "
                "pip install openwakeword"
            )
        if not HAS_AUDIO:
            raise ImportError(
                "sounddevice not available. Install with: "
                "pip install sounddevice (requires PortAudio)"
            )

        ww_cfg = config.get("wake_word", {})
        self._sensitivity = ww_cfg.get("sensitivity", 0.5)
        self._cooldown = ww_cfg.get("cooldown", 2.0)
        self._custom_models = ww_cfg.get("custom_models", [])

        # Wake word → personality ID mapping (populated by register_wake_words)
        self._word_to_personality: dict[str, str] = {}

        # Model name → wake word phrase mapping
        # OpenWakeWord uses model names like "hey_jarvis" internally,
        # but we expose them as "hey jarvis" (with spaces) to the user.
        self._model_to_word: dict[str, str] = {}

        # State
        self._model: Optional[OWWModel] = None
        self._callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._mic_released = threading.Event()  # signaled when mic is actually closed
        self._resume_event = threading.Event()   # signaled to tell listener to reopen mic
        self._last_detection_time = 0.0

        # Download pre-trained models on first use (they're cached after that)
        try:
            openwakeword.utils.download_models()
        except Exception as e:
            log.debug("Model download check: %s (may already be cached)", e)

    def register_wake_words(self, wake_words: dict[str, str]) -> None:
        """
        Register wake words and their personality mappings.

        Args:
            wake_words: {"hey jarvis": "jarvis", "hey devesh": "devesh", ...}
        """
        self._word_to_personality = dict(wake_words)

        # Build the model-name mapping.
        # OpenWakeWord's built-in model names use underscores: "hey_jarvis"
        # We accept both "hey jarvis" and "hey_jarvis" from config.
        for phrase in wake_words:
            model_name = phrase.lower().replace(" ", "_")
            self._model_to_word[model_name] = phrase

        log.info(
            "Registered %d wake word(s): %s",
            len(wake_words),
            ", ".join(f'"{w}" → {p or "(system)"}' for w, p in wake_words.items()),
        )

        # Load the OWW model with the requested wake words.
        # Built-in models are referenced by name; custom models by file path.
        model_names = list(self._model_to_word.keys())
        custom_paths = [p for p in self._custom_models if p]

        try:
            if custom_paths:
                self._model = OWWModel(
                    wakeword_models=custom_paths,
                    inference_framework="onnx",
                )
            else:
                # Load all built-in models — they're tiny, and OWW filters
                # predictions to only the models we care about.
                self._model = OWWModel(inference_framework="onnx")

            loaded = list(self._model.models.keys()) if self._model.models else []
            log.info("OpenWakeWord models loaded: %s", loaded)

            # Verify our requested models are available
            for model_name in model_names:
                if model_name not in loaded:
                    log.warning(
                        'Wake word model "%s" not found in loaded models. '
                        "Available: %s. You may need to train a custom model.",
                        model_name, loaded,
                    )
        except Exception as e:
            log.error("Failed to load OpenWakeWord models: %s", e)
            raise

    def start_listening(self, callback: Callable) -> None:
        """Start wake word detection in a background thread."""
        if self._running:
            log.warning("Already listening. Call stop_listening() first.")
            return
        if self._model is None:
            raise RuntimeError("No wake words registered. Call register_wake_words() first.")

        self._callback = callback
        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="wake-word-listener",
            daemon=True,  # dies when main thread exits
        )
        self._thread.start()
        log.info("Wake word detection started (sensitivity=%.2f).", self._sensitivity)

    def stop_listening(self) -> None:
        """Stop wake word detection and clean up."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._callback = None
        log.info("Wake word detection stopped.")

    def pause_listening(self) -> None:
        """
        Pause detection AND release the microphone.

        On macOS (and some ALSA configs), only one InputStream can read from
        the mic at a time. So we can't just suppress predictions — we need to
        actually close the audio stream so record_smart() can open its own.

        This method blocks until the listener thread confirms the mic is closed.
        """
        self._mic_released.clear()
        self._paused = True
        # Wait for the listener thread to actually close the stream
        # (up to 1 second — should happen within one 80ms chunk cycle)
        if not self._mic_released.wait(timeout=1.0):
            log.warning("Mic release timed out — recording may conflict.")
        if self._model:
            self._model.reset()
        log.debug("Wake word detection paused (mic released).")

    def resume_listening(self) -> None:
        """Resume detection — signal the listener thread to reopen the mic."""
        self._paused = False
        self._resume_event.set()
        if self._model:
            self._model.reset()
        log.debug("Wake word detection resuming...")

    def _listen_loop(self) -> None:
        """
        Background loop: open mic → read chunks → predict → fire callback.

        Handles pause/resume by fully closing and reopening the mic stream.
        On macOS, only one InputStream can read from the mic at a time, so
        we MUST release it when the main thread needs the mic for recording.

        The loop:
          1. Open mic stream
          2. Read 80ms chunks and run predictions
          3. When paused: close stream, signal mic_released, wait for resume
          4. When resumed: reopen stream, continue predictions
          5. When stopped: close stream, exit thread
        """
        try:
            while self._running:
                # Open a fresh mic stream
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                )
                stream.start()
                log.debug("Mic stream opened for wake word detection.")

                _debug_counter = 0

                try:
                    while self._running and not self._paused:
                        # Read one chunk from mic
                        data, overflowed = stream.read(CHUNK_SIZE)
                        if overflowed:
                            log.debug("Audio overflow — chunk dropped.")
                            continue

                        # Feed audio to model.
                        # sounddevice returns shape (CHUNK_SIZE, 1) for mono —
                        # OpenWakeWord expects a flat 1D int16 array.
                        audio = np.array(data, dtype=np.int16).flatten()
                        predictions = self._model.predict(audio)

                        # Periodic debug: show top scores every ~2.5s (32 chunks)
                        _debug_counter += 1
                        if _debug_counter % 32 == 0:
                            relevant = {
                                k: f"{v:.3f}" for k, v in predictions.items()
                                if k in self._model_to_word and v > 0.01
                            }
                            if relevant:
                                log.debug("Wake word scores: %s", relevant)

                        # Check each wake word model
                        for model_name, confidence in predictions.items():
                            if confidence < self._sensitivity:
                                continue

                            if model_name not in self._model_to_word:
                                continue

                            # Cooldown: prevent rapid re-triggering
                            now = time.time()
                            if now - self._last_detection_time < self._cooldown:
                                continue
                            self._last_detection_time = now

                            phrase = self._model_to_word[model_name]
                            personality_id = self._word_to_personality.get(phrase, "")

                            detection = WakeWordDetection(
                                wake_word=phrase,
                                confidence=confidence,
                                personality_id=personality_id,
                            )

                            log.info(
                                'Wake word detected: "%s" (%.0f%% confident%s)',
                                phrase,
                                confidence * 100,
                                f", → {personality_id}" if personality_id else "",
                            )

                            self._model.reset()

                            if self._callback:
                                try:
                                    self._callback(detection)
                                except Exception as e:
                                    log.error("Wake word callback error: %s", e)
                finally:
                    # Always close the stream — whether paused, stopped, or error
                    stream.stop()
                    stream.close()
                    log.debug("Mic stream closed.")

                # If we exited because of pause, signal that mic is released
                # and wait for resume
                if self._paused and self._running:
                    self._mic_released.set()  # tell main thread mic is free
                    self._resume_event.clear()
                    log.debug("Waiting for resume signal...")
                    # Wait for resume or stop
                    while self._paused and self._running:
                        if self._resume_event.wait(timeout=0.1):
                            break
                    self._resume_event.clear()
                    if self._running:
                        log.debug("Resuming wake word detection...")

        except Exception as e:
            if self._running:
                log.error("Wake word listener crashed: %s", e)
            self._running = False
