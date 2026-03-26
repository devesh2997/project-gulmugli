"""
Microphone recording utility.

Captures audio from the system microphone and returns it as WAV bytes.
Used by the main loop to record speech after wake word detection.

This module handles the platform differences:
  - Mac: Uses sounddevice (PortAudio backend, works with all Mac audio)
  - Jetson: Uses sounddevice (ALSA backend)
  - Pi: Uses sounddevice (ALSA backend)

sounddevice is cross-platform and doesn't need PyAudio (which is painful to install).

Three recording modes:
  1. Fixed duration: record for N seconds (simple fallback)
  2. Enter-to-stop: record until Enter pressed (for text+voice hybrid testing)
  3. VAD-based (smart): record until silence detected after speech
     — this is the natural one for wake word mode

VAD (Voice Activity Detection) approach:
  Energy-based — compute RMS energy of each 100ms audio chunk. When energy
  exceeds a threshold, speech has started. When it drops below for a sustained
  period (silence_timeout), recording ends. No extra dependencies needed.

  Why not silero-vad or webrtcvad?
  They're better at noisy environments, but add dependencies and latency.
  Energy-based works great for indoor voice assistant use. We can swap
  in silero-vad later via config if needed.
"""

import io
import wave
import time
import threading
import numpy as np
from core.logger import get_logger
from core.config import config

log = get_logger("mic")

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except (ImportError, OSError) as _e:
    HAS_SOUNDDEVICE = False
    sd = None
    log.debug("sounddevice not available: %s", _e)


# Recording parameters — matched to Whisper's expectations
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1         # Mono
DTYPE = "int16"      # 16-bit PCM


def check_mic_available() -> bool:
    """Check if a microphone is available on this system."""
    if not HAS_SOUNDDEVICE:
        return False
    try:
        devices = sd.query_devices()
        default_input = sd.query_devices(kind="input")
        log.debug("Default input device: %s", default_input["name"])
        return True
    except Exception as e:
        log.warning("No microphone available: %s", e)
        return False


def record_fixed(duration: float = 5.0) -> bytes:
    """
    Record audio for a fixed duration.

    Returns WAV bytes (with header), ready to pass to EarsProvider.transcribe().

    Args:
        duration: How many seconds to record (default: 5s)
    """
    if not HAS_SOUNDDEVICE:
        raise RuntimeError("sounddevice not installed. Install with: pip install sounddevice")

    log.debug("Recording %.1fs of audio...", duration)
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
    )
    sd.wait()  # Block until recording is done
    log.debug("Recording complete.")

    return _audio_to_wav_bytes(audio)


def record_smart(
    silence_timeout: float = 1.0,
    max_duration: float = 15.0,
    pre_speech_timeout: float = 5.0,
) -> bytes:
    """
    Smart recording with voice activity detection.

    Starts recording immediately, waits for speech to begin, then stops
    when the speaker goes silent. This makes conversation feel natural —
    short commands finish quickly, long sentences get as much time as needed.

    How it works:
      1. Start recording — assume user is ALREADY speaking (they just said
         the wake word and are continuing with their command)
      2. Track rolling minimum RMS to estimate ambient noise on the fly
      3. When energy stays low for silence_timeout, stop recording
      4. Safety cap: always stop at max_duration regardless

    Why no calibration period?
      After a wake word, the user is typically mid-sentence: "Hey Jarvis,
      play Sajni". If we spend 300ms calibrating on "play Sa-", we measure
      speech as ambient noise and set the threshold absurdly high. Instead,
      we use a rolling minimum approach: track the lowest RMS seen and set
      the speech threshold relative to that. The minimum naturally converges
      to ambient noise within a few seconds.

    Args:
        silence_timeout: Seconds of silence after speech before stopping (default: 1.0s)
        max_duration: Maximum recording time in seconds (safety cap, default: 15s)
        pre_speech_timeout: Seconds to wait for speech before giving up (default: 5s)

    Returns:
        WAV bytes, or empty bytes if no speech detected.
    """
    if not HAS_SOUNDDEVICE:
        raise RuntimeError("sounddevice not installed. Install with: pip install sounddevice")

    frames = []
    speech_started = False
    last_speech_time = 0.0
    start_time = time.time()
    done = threading.Event()

    # Fixed threshold: RMS below this = silence, above = speech.
    # For int16 audio at 16kHz from a typical laptop/USB mic:
    #   Silence: RMS ~30-150
    #   Soft speech / breaths: RMS ~150-400
    #   Normal speech: RMS ~400-5000
    #   Loud speech: RMS ~3000-15000
    #
    # 150 catches soft speech and breathing pauses don't count as silence.
    # If you get false triggers from room noise, raise to 200-300.
    # Tune via config: ears.vad_threshold
    threshold = config.get("ears", {}).get("vad_threshold", 150)

    # 100ms chunks at 16kHz = 1600 samples per chunk
    chunk_samples = int(SAMPLE_RATE * 0.1)

    def callback(indata, frame_count, time_info, status):
        nonlocal speech_started, last_speech_time

        if status:
            log.warning("Audio callback status: %s", status)

        frames.append(indata.copy())
        elapsed = time.time() - start_time

        # Compute RMS energy of this chunk
        audio_chunk = indata[:, 0] if indata.ndim > 1 else indata
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))

        # Is this chunk speech or silence?
        is_speech = rms > threshold

        if is_speech:
            if not speech_started:
                speech_started = True
                log.debug("Speech detected (rms=%.0f, threshold=%.0f)", rms, threshold)
            last_speech_time = time.time()

        # Check stopping conditions
        now = time.time()

        # Max duration reached
        if elapsed >= max_duration:
            log.debug("Max duration reached (%.1fs)", max_duration)
            done.set()
            return

        # No speech detected within pre_speech_timeout
        if not speech_started and elapsed >= pre_speech_timeout:
            log.debug("No speech detected after %.1fs", pre_speech_timeout)
            done.set()
            return

        # Speech started but silence for too long → done
        if speech_started and (now - last_speech_time) >= silence_timeout:
            log.debug(
                "End of speech (%.1fs silence, recorded %.1fs total)",
                now - last_speech_time,
                elapsed,
            )
            done.set()
            return

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
        blocksize=chunk_samples,
    )

    with stream:
        # Wait for the callback to signal done, or max_duration + buffer
        done.wait(timeout=max_duration + 1.0)

    if not frames:
        log.warning("No audio recorded.")
        return b""

    audio = np.concatenate(frames, axis=0)
    duration = len(audio) / SAMPLE_RATE
    log.debug("Smart recording: %.1fs captured (speech_started=%s)", duration, speech_started)

    if not speech_started:
        return b""

    return _audio_to_wav_bytes(audio)


def record_until_stop() -> tuple[bytes, threading.Event]:
    """
    Record audio until the stop event is set.

    Returns (wav_bytes, stop_event). The caller is responsible for
    setting the stop_event from another thread (e.g., when Enter
    is pressed or VAD detects silence).

    Usage:
        wav_bytes, stop = record_until_stop()
        # ... in another thread:
        stop.set()
    """
    if not HAS_SOUNDDEVICE:
        raise RuntimeError("sounddevice not installed. Install with: pip install sounddevice")

    stop_event = threading.Event()
    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            log.warning("Audio callback status: %s", status)
        frames.append(indata.copy())

    max_duration = config.get("ears", {}).get("max_record_seconds", 10)

    log.debug("Recording (max %ds, set stop_event to end)...", max_duration)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
        blocksize=int(SAMPLE_RATE * 0.1),  # 100ms blocks
    )

    with stream:
        # Wait for stop signal or timeout
        stop_event.wait(timeout=max_duration)

    if not frames:
        log.warning("No audio recorded.")
        return b"", stop_event

    audio = np.concatenate(frames, axis=0)
    duration = len(audio) / SAMPLE_RATE
    log.debug("Recorded %.1fs of audio.", duration)

    return _audio_to_wav_bytes(audio), stop_event


def record_with_enter_to_stop() -> bytes:
    """
    Record audio, stop when Enter is pressed.

    This is the v1 approach for Mac text+voice hybrid mode:
    the user presses Enter to start talking, then Enter again to stop.
    Simple but effective for testing.
    """
    if not HAS_SOUNDDEVICE:
        raise RuntimeError("sounddevice not installed. Install with: pip install sounddevice")

    frames = []
    stop_event = threading.Event()

    def callback(indata, frame_count, time_info, status):
        if status:
            log.warning("Audio callback status: %s", status)
        if not stop_event.is_set():
            frames.append(indata.copy())

    max_duration = config.get("ears", {}).get("max_record_seconds", 10)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
        blocksize=int(SAMPLE_RATE * 0.1),  # 100ms blocks
    )

    with stream:
        try:
            input()  # Block until Enter pressed
        except EOFError:
            pass
        # Signal the callback to stop collecting frames BEFORE the stream closes.
        # threading.Event.is_set() is thread-safe — no lock needed.
        stop_event.set()

    if not frames:
        log.warning("No audio recorded.")
        return b""

    audio = np.concatenate(frames, axis=0)

    # Enforce max duration
    max_samples = int(max_duration * SAMPLE_RATE)
    if len(audio) > max_samples:
        audio = audio[:max_samples]

    duration = len(audio) / SAMPLE_RATE
    log.debug("Recorded %.1fs of audio.", duration)

    return _audio_to_wav_bytes(audio)


def _audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    """Convert a numpy audio array to WAV file bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
