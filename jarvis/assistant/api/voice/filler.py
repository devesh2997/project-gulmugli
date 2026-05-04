"""
Filler + error pre-synthesized audio clips (per-personality cache).

## Why

Even with TTFA pinned at ~3s, that's 3 seconds of dead air after the
user stops speaking. The brain reads "...delay..." as "the assistant
didn't hear me / is broken / will respond eventually." Playing a tiny
acknowledgment clip ("Hmm,", "Let me think.", "One sec.") IMMEDIATELY
after end-of-speech — well before the LLM has produced a token, let
alone synthesized audio — drops perceived TTFA to ~150 ms (just the
STT cost). The actual answer plays right after, sounding like a
natural pause for thought.

This is what Alexa / Google / Siri do under the hood. Implementation
cost: pre-synth a small set per personality at startup, cache as raw
WAV bytes, ship one as the very first audio_chunk before the main
pipeline runs.

## Two caches

`_FILLER_CACHE` — short acknowledgment clips ("One moment.", "Mm,")
played BEFORE the answer to mask LLM latency.

`_ERROR_CACHE` — apologetic clips played WHEN the pipeline fails
after STT succeeded. Ensures the user gets audible feedback on
failure instead of silence.

Both are personality-keyed and lazy-built — first request for a
given personality triggers the synthesis. Subsequent requests hit
the cache.
"""

from __future__ import annotations

import random
import threading

from core.logger import get_logger

log = get_logger("api.voice.filler")


_FILLER_CACHE: dict[str, list[bytes]] = {}  # personality_id → list of WAVs
_ERROR_CACHE: dict[str, list[bytes]] = {}
_FILLER_LOCK = threading.Lock()

_FILLER_PHRASES = {
    "jarvis":     ["Mm-hmm.", "One moment.", "Let me see."],
    "devesh":     ["Haan.", "Ek second.", "Sochne do."],
    "chandler":   ["Riiiight.", "Could I be...", "Oh, *that*."],
    "girlfriend": ["Mmhm,", "One sec babe.", "Hmm,"],
    "_default":   ["Mm,", "One moment.", "Let me think."],
}

_ERROR_PHRASES = {
    "jarvis":     ["Sorry, I'm having trouble. Please try again.",
                   "Something went wrong on my end. Could you repeat that?"],
    "devesh":     ["Yaar, kuch gadbad ho gayi. Phir try karo.",
                   "Mujhe samajh nahi aya. Dobara bolo?"],
    "chandler":   ["Could this BE any more broken? Try again?",
                   "Well, that didn't work. One more time?"],
    "girlfriend": ["Oops, something broke. Try again babe?",
                   "Hmm, that didn't work. Say it again?"],
    "_default":   ["Sorry, something went wrong. Please try again.",
                   "I had a problem. Could you say that again?"],
}


def ensure_filler_for(voice_router, personality) -> None:
    """
    Lazy-build the filler clip cache for the given personality on first
    use. Keeps startup fast (one personality might be 1-3 seconds of TTS
    work; we don't want to do all of them up front).

    Filler clips are synthesized with the same provider that handles the
    personality's normal speech, so the voice character matches.
    """
    if not voice_router or personality is None:
        return
    pid = personality.id
    with _FILLER_LOCK:
        if pid in _FILLER_CACHE:
            return  # already built
        # Mark immediately so concurrent requests don't all try to build.
        _FILLER_CACHE[pid] = []

    phrases = _FILLER_PHRASES.get(pid, _FILLER_PHRASES["_default"])
    wavs: list[bytes] = []
    for phrase in phrases:
        try:
            wav = voice_router.speak(phrase, personality)
            if wav:
                wavs.append(wav)
        except Exception as e:
            log.warning("Filler synth for '%s' (personality=%s) failed: %s",
                        phrase, pid, e)
    with _FILLER_LOCK:
        _FILLER_CACHE[pid] = wavs
    log.info("Filler cache built for '%s': %d clips", pid, len(wavs))


def pick_filler_wav(personality_id: str) -> bytes | None:
    """Return a random filler WAV for the given personality, or None if none cached."""
    with _FILLER_LOCK:
        wavs = _FILLER_CACHE.get(personality_id) or _FILLER_CACHE.get("_default", [])
    return random.choice(wavs) if wavs else None


def ensure_error_audio_for(voice_router, personality) -> None:
    """Lazy-build the error-clip cache for the given personality."""
    if not voice_router or personality is None:
        return
    pid = personality.id
    with _FILLER_LOCK:
        if pid in _ERROR_CACHE:
            return
        _ERROR_CACHE[pid] = []

    phrases = _ERROR_PHRASES.get(pid, _ERROR_PHRASES["_default"])
    wavs: list[bytes] = []
    for phrase in phrases:
        try:
            wav = voice_router.speak(phrase, personality)
            if wav:
                wavs.append(wav)
        except Exception as e:
            log.warning("Error-audio synth for '%s' failed: %s", phrase, e)
    with _FILLER_LOCK:
        _ERROR_CACHE[pid] = wavs


def pick_error_wav(personality_id: str) -> bytes | None:
    """Return a random error WAV for the given personality, or None if none cached."""
    with _FILLER_LOCK:
        wavs = _ERROR_CACHE.get(personality_id) or _ERROR_CACHE.get("_default", [])
    return random.choice(wavs) if wavs else None
