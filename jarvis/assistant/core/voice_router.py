"""
VoiceRouter — smart per-personality TTS provider routing with fallback.

Problem it solves:
    main.py used to load a single VoiceProvider (e.g., Piper). But each personality
    may need a different provider — Jarvis wants Piper (fast), Devesh wants XTTS
    (voice cloning). Passing "devesh" to Piper crashes; passing "en_US-lessac-medium"
    to XTTS doesn't make sense.

How it works:
    1. On init, tries to load every voice provider that's registered (Piper, XTTS, etc.)
    2. Each personality declares which provider it wants (voice_provider in config)
    3. When speak() is called, the router picks the right provider for the active personality
    4. If that provider isn't available, falls back gracefully:
         preferred provider → piper (fast fallback) → text-only (no crash)

Fallback chain (most preferred → least):
    personality.voice_provider (e.g., "xtts")
    → "piper" (always the safe fallback — fast, CPU-only, no heavy deps)
    → None (text-only mode, voice disabled)

Config:
    voice:
      enabled: true           # master switch — set to false to disable all TTS
      fallback_provider: "piper"  # what to fall back to when preferred unavailable

    personalities:
      profiles:
        jarvis:
          voice_provider: "piper"            # fast, pre-built voice
          voice_model: "en_US-lessac-medium"
        devesh:
          voice_provider: "xtts"             # voice cloning
          voice_model: "devesh"              # → voices/xtts/devesh.wav
        chandler:
          voice_provider: "xtts"
          voice_model: "chandler"

Usage:
    from core.voice_router import voice_router

    # Speaks using the active personality's preferred provider
    voice_router.speak_to_device("Hello!", personality)

    # Or get raw audio bytes
    audio = voice_router.speak("Hello!", personality)
"""

import re
import time
import threading
from queue import Queue
from core.config import config
from core.interfaces import Personality, VoiceProvider
from core.registry import get_provider, list_providers
from core.logger import get_logger
from core.audio_focus import AudioFocusManager, AudioChannel

log = get_logger("voice.router")


class VoiceRouter:
    """
    Routes TTS requests to the right provider based on personality config.

    Loads available providers lazily on first use. Maintains a provider cache
    so we don't re-instantiate on every call.
    """

    def __init__(self):
        voice_cfg = config.get("voice", {})

        # Master switch
        self._enabled = voice_cfg.get("enabled", True)

        # Which provider to fall back to when the preferred one fails
        self._fallback_name = voice_cfg.get("fallback_provider", "kokoro")

        # Default voice for each provider — used when falling back to a provider
        # whose voice_model namespace doesn't match the personality's.
        # e.g., personality has voice_model "devesh" (XTTS ref WAV) but fallback
        # is Kokoro, which needs "af_heart" or "hm_omega".
        self._fallback_voices = voice_cfg.get("fallback_voices", {
            "kokoro": "af_heart",
            "piper": voice_cfg.get("model", "en_US-lessac-medium"),
            "edge": "en-US-AriaNeural",
        })

        # Cache of instantiated providers: {"piper": PiperVoiceProvider, "kokoro": KokoroVoiceProvider}
        self._providers: dict[str, VoiceProvider] = {}

        # Track which providers failed to load (so we don't retry every call)
        self._failed: set[str] = set()

        if not self._enabled:
            log.info("Voice disabled (voice.enabled = false). All TTS will be skipped.")
            return

        # Pre-discover which voice providers are registered (but don't instantiate yet)
        registered = list_providers("voice").get("voice", [])
        log.info("Registered voice providers: %s", registered)

    @property
    def enabled(self) -> bool:
        """Whether voice output is enabled at all."""
        return self._enabled

    def _get_provider(self, name: str) -> VoiceProvider | None:
        """
        Get a provider by name, instantiating on first access.

        Returns None if the provider can't be loaded (missing deps, etc.)
        """
        if name in self._providers:
            return self._providers[name]

        if name in self._failed:
            return None  # Already tried and failed, don't retry

        try:
            log.debug('Loading voice provider: "%s"', name)
            provider = get_provider("voice", name)
            self._providers[name] = provider
            log.info('Voice provider "%s" loaded successfully.', name)
            return provider
        except Exception as e:
            self._failed.add(name)
            log.warning('Voice provider "%s" failed to load: %s', name, e)
            return None

    def _resolve_provider(self, personality: Personality) -> tuple[VoiceProvider | None, str]:
        """
        Resolve which provider + voice_model to use for a personality.

        Returns (provider, voice_model) or (None, "") if nothing works.

        Fallback chain:
          1. personality.voice_provider (if set)
          2. fallback_provider from config (default: "piper")
          3. Any provider that's loaded (last resort)
          4. None (text-only)
        """
        preferred_name = getattr(personality, "voice_provider", "") or ""
        voice_model = personality.voice_model

        # Step 1: Try the personality's preferred provider
        if preferred_name:
            provider = self._get_provider(preferred_name)
            if provider:
                return provider, voice_model

            log.warning(
                'Personality "%s" wants provider "%s" but it\'s unavailable. '
                'Falling back to "%s".',
                personality.display_name, preferred_name, self._fallback_name,
            )

        # Step 2: Try the fallback provider
        if self._fallback_name and self._fallback_name != preferred_name:
            provider = self._get_provider(self._fallback_name)
            if provider:
                # Use personality's fallback_voice if set (e.g., "hm_omega" for
                # Devesh on Kokoro), otherwise use the provider's global default.
                fallback_model = (
                    personality.fallback_voice
                    or self._fallback_voices.get(self._fallback_name, "")
                )
                log.debug(
                    'Using fallback provider "%s" with voice "%s" (instead of "%s").',
                    self._fallback_name, fallback_model, voice_model,
                )
                return provider, fallback_model

        # Step 3: Try any loaded provider as last resort
        for name, provider in self._providers.items():
            fallback_model = (
                personality.fallback_voice
                or self._fallback_voices.get(name, "")
            )
            log.warning('Last resort: using "%s" provider with voice "%s".', name, fallback_model)
            return provider, fallback_model

        # Step 4: Nothing works
        log.warning("No voice providers available. Responses will be text-only.")
        return None, ""

    def speak(self, text: str, personality: Personality) -> bytes | None:
        """
        Synthesize text using the appropriate provider for this personality.

        Returns WAV bytes, or None if voice is disabled/unavailable.
        """
        if not self._enabled:
            return None

        provider, voice_model = self._resolve_provider(personality)
        if provider is None:
            return None

        try:
            start = time.monotonic()
            audio = provider.speak(text, voice_model=voice_model)
            elapsed = time.monotonic() - start
            log.debug(
                'TTS: "%s" (%.2fs, provider=%s, model=%s)',
                text[:50], elapsed, type(provider).__name__, voice_model,
            )
            return audio
        except Exception as e:
            log.error("TTS speak() failed: %s", e)
            return None

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """
        Split text into speakable sentence chunks.

        Splits on sentence-ending punctuation (. ! ? ; :) followed by whitespace,
        plus Hindi danda (।). Keeps short fragments together to avoid choppy output.
        Minimum chunk size: 20 chars (avoids synthesizing tiny fragments like "OK.").
        """
        # Split on sentence boundaries — period/exclaim/question followed by space
        raw = re.split(r'(?<=[.!?;:।])\s+', text.strip())

        # Merge short fragments with the next sentence
        sentences = []
        buffer = ""
        for part in raw:
            if buffer:
                buffer += " " + part
            else:
                buffer = part
            if len(buffer) >= 20:
                sentences.append(buffer)
                buffer = ""
        if buffer:
            if sentences:
                sentences[-1] += " " + buffer  # append remainder to last
            else:
                sentences.append(buffer)

        return sentences or [text]

    def speak_to_device(self, text: str, personality: Personality,
                        interrupt_event=None) -> bool:
        """
        Synthesize and play through speakers with sentence-level streaming.

        For short text (1 sentence), this is identical to direct speak_to_device.
        For longer text (stories, explanations), it splits into sentences and
        overlaps synthesis with playback:

          Sentence 1: [synthesize][  play  ]
          Sentence 2:      [synthesize][  play  ]
          Sentence 3:           [synthesize][  play  ]

        The user hears the first sentence while subsequent sentences are being
        synthesized in a background thread. This cuts perceived latency by 60-80%
        for multi-sentence responses.

        Returns True if all playback completed, False if interrupted.
        """
        if not self._enabled:
            return False

        provider, voice_model = self._resolve_provider(personality)
        if provider is None:
            return False

        # Acquire audio focus for the ENTIRE multi-sentence utterance.
        # This ducks/pauses music ONCE, not per sentence — no chatter.
        focus = AudioFocusManager.instance()
        focus.acquire(AudioChannel.TTS)

        try:
            sentences = self._split_sentences(text)
            start = time.monotonic()

            # For single sentences, use the simple direct path (no threading overhead)
            if len(sentences) <= 1:
                return self._speak_single(provider, voice_model, text, interrupt_event, start)

            # Multi-sentence streaming: producer synthesizes ahead, consumer plays
            log.debug(
                'Streaming TTS: %d sentences, provider=%s',
                len(sentences), type(provider).__name__,
            )

            # Queue holds WAV bytes; None = sentinel (no more sentences)
            audio_queue: Queue = Queue(maxsize=2)  # buffer at most 2 sentences ahead
            synth_error = [None]  # mutable container for error from synth thread

            def synthesize_ahead():
                """Background thread: synthesize sentences and push to queue."""
                for i, sentence in enumerate(sentences):
                    if interrupt_event and interrupt_event.is_set():
                        break
                    try:
                        wav_bytes = provider.speak(sentence, voice_model=voice_model)
                        audio_queue.put(wav_bytes)
                    except Exception as e:
                        log.warning("TTS synthesis failed for sentence %d: %s", i, e)
                        synth_error[0] = e
                        break
                audio_queue.put(None)  # sentinel: done

            synth_thread = threading.Thread(
                target=synthesize_ahead, name="tts-synth", daemon=True,
            )
            synth_thread.start()

            # Main thread: play audio as it arrives from the queue
            from providers.voice.piper_tts import _play_wav_bytes

            completed = True
            while True:
                wav_bytes = audio_queue.get()
                if wav_bytes is None:
                    break  # all sentences done

                try:
                    if not _play_wav_bytes(wav_bytes, interrupt_event=interrupt_event):
                        completed = False
                        break  # interrupted
                except Exception as e:
                    # PortAudio can fail if the audio device is busy (e.g., mpv playing music).
                    # Log and skip this sentence rather than crashing the entire pipeline.
                    log.warning("Audio playback failed (device busy?): %s", e)
                    completed = False
                    break

            synth_thread.join(timeout=2.0)

            elapsed = time.monotonic() - start
            if completed:
                log.debug('Spoke %d sentences (%.2fs total).', len(sentences), elapsed)
            else:
                log.info('Speech interrupted after %.2fs.', elapsed)

            return completed
        finally:
            focus.release(AudioChannel.TTS)

    def _speak_single(self, provider, voice_model, text, interrupt_event, start) -> bool:
        """Speak a single sentence — no threading overhead."""
        try:
            try:
                completed = provider.speak_to_device(
                    text, voice_model=voice_model, interrupt_event=interrupt_event,
                )
            except Exception as audio_err:
                log.warning("Audio playback failed (device busy?): %s", audio_err)
                return False
            elapsed = time.monotonic() - start
            if completed:
                log.debug(
                    'Spoke: "%s" (%.2fs, provider=%s)',
                    text[:50], elapsed, type(provider).__name__,
                )
            else:
                log.info('Speech interrupted after %.2fs: "%s"', elapsed, text[:50])
            return completed
        except Exception as e:
            log.warning("TTS speak_to_device() failed with %s: %s", type(provider).__name__, e)

            # Try fallback
            preferred_name = getattr(provider, "__class__", type(provider)).__name__
            fallback = self._get_provider(self._fallback_name)
            if fallback and fallback is not provider:
                try:
                    fallback_model = self._fallback_voices.get(self._fallback_name, "")
                    log.info('Retrying with fallback provider "%s".', self._fallback_name)
                    return fallback.speak_to_device(
                        text, voice_model=fallback_model,
                        interrupt_event=interrupt_event,
                    )
                except Exception as e2:
                    log.error("Fallback TTS also failed: %s", e2)

            return False

    def list_all_voices(self) -> dict[str, list[str]]:
        """List available voices across all loaded providers."""
        result = {}
        for name, provider in self._providers.items():
            try:
                result[name] = provider.list_voices()
            except Exception:
                result[name] = []
        return result
