"""
Filler + error pre-synthesized audio clips (per-personality, per-language cache).

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

## Language-aware fillers

A filler in the wrong language is jarring — a Hindi speaker getting an
English "Mm-hmm" before her Hindi reply, or an English speaker getting
"Haan" before an English reply. Since STT has already produced the
transcript by the time we pick a filler, we detect the user's language
(Devanagari script or romanized-Hindi markers like "kya", "hai",
"yaar") and pick a same-language clip. Each personality keeps both
English and Hindi/Hinglish phrase pools so it can sound natural to
either kind of user without breaking character.

## Two caches

`_FILLER_CACHE` — short acknowledgment clips ("One moment.", "Mm,")
played BEFORE the answer to mask LLM latency.

`_ERROR_CACHE` — apologetic clips played WHEN the pipeline fails
after STT succeeded. Ensures the user gets audible feedback on
failure instead of silence. Errors especially MUST match the user's
language — a Hindi user shouldn't get an English error she may not
parse, and vice versa.

Both are personality-and-language-keyed and lazy-built — first request
for a given personality triggers synthesis of all language buckets at
once. Subsequent requests hit the cache.
"""

from __future__ import annotations

import random
import re
import threading

from core.logger import get_logger

log = get_logger("api.voice.filler")


# Cache shape: {personality_id: {lang: [wav_bytes, ...]}}
_FILLER_CACHE: dict[str, dict[str, list[bytes]]] = {}
_ERROR_CACHE: dict[str, dict[str, list[bytes]]] = {}
_FILLER_LOCK = threading.Lock()


# ── Phrase pools ────────────────────────────────────────────────────
# Each personality has BOTH "en" and "hi" pools. The "hi" pool covers
# Hindi and Hinglish users — Hinglish is just Hindi with English nouns,
# so a Hinglish-flavoured filler ("Ek sec.", "Haan haan.") works for
# both. We keep clips short — they're meant to feel like a beat of
# thought, not a sentence.

_FILLER_PHRASES: dict[str, dict[str, list[str]]] = {
    "jarvis": {
        "en": ["Mm-hmm.", "One moment.", "Let me see."],
        "hi": ["Haan.", "Ek second.", "Dekhta hoon."],
    },
    "devesh": {
        "en": ["Yeah.", "One sec.", "Let me think."],
        "hi": ["Haan.", "Ek second.", "Sochne do."],
    },
    "chandler": {
        # Sarcasm in Hinglish lands fine — Chandler keeps his beats.
        "en": ["Riiiight.", "Could I be...", "Oh, *that*."],
        "hi": ["Acha, theek hai.", "Ek minute, yaar.", "Haan haan."],
    },
    "girlfriend": {
        "en": ["Mmhm,", "One sec babe.", "Hmm,"],
        "hi": ["Hmm,", "Ek minute,", "Haan jaan,"],
    },
    "_default": {
        "en": ["Mm,", "One moment.", "Let me think."],
        "hi": ["Haan,", "Ek second.", "Sochne do."],
    },
}

_ERROR_PHRASES: dict[str, dict[str, list[str]]] = {
    "jarvis": {
        "en": ["Sorry, I'm having trouble. Please try again.",
               "Something went wrong on my end. Could you repeat that?"],
        "hi": ["Maaf karo, kuch problem ho gayi. Phir se bolo.",
               "Mujhe samajh nahi aaya. Dobara bolenge?"],
    },
    "devesh": {
        "en": ["Sorry yaar, something broke. Try again?",
               "Hmm, didn't catch that. One more time?"],
        "hi": ["Yaar, kuch gadbad ho gayi. Phir try karo.",
               "Mujhe samajh nahi aya. Dobara bolo?"],
    },
    "chandler": {
        "en": ["Could this BE any more broken? Try again?",
               "Well, that didn't work. One more time?"],
        "hi": ["Yeh toh bilkul nahi chala. Phir bolo?",
               "Acha, yeh fail ho gaya. Ek baar aur?"],
    },
    "girlfriend": {
        "en": ["Oops, something broke. Try again babe?",
               "Hmm, that didn't work. Say it again?"],
        "hi": ["Arey, kuch problem hui. Phir bolo na?",
               "Hmm, samajh nahi aaya. Dobara bolo?"],
    },
    "_default": {
        "en": ["Sorry, something went wrong. Please try again.",
               "I had a problem. Could you say that again?"],
        "hi": ["Maaf karo, kuch problem ho gayi. Phir bolo.",
               "Kuch gadbad hui. Dobara bolenge?"],
    },
}


# ── Language detection ──────────────────────────────────────────────
# Cheap heuristic: Devanagari script → "hi" instantly. Otherwise look
# for romanized Hindi marker tokens (function words and common verbs/
# particles that don't appear in English). One strong marker is
# enough — Hinglish often has just a couple of Hindi words sprinkled
# in, but that signals the user is comfortable receiving Hindi.

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

# Word-boundary set of romanized-Hindi markers. These were chosen to
# avoid English false positives:
#   - "hai" only matches as a whole word (not inside "hair", "haiti")
#   - "do" is excluded — too common in English ("do it")
#   - "kar" / "ho" / "se" / "ka" / "ke" / "ki" appear in many
#     transliterated Hindi sentences; included.
#
# A few intentional exclusions to avoid English false positives:
#   - "the"  — English article (collides with Hindi past-tense plural "the")
#   - "boss" — English word (also used in Hinglish, but too common in English)
#   - "do"   — English verb (used in Hindi too: "do it" vs "kar do")
#   - "main" — English noun (collides with Hindi "I"; we keep "mai" only)
#   - "is"   — English copula (collides nothing here; just listing common
#              traps for future maintainers)
_HI_MARKERS = {
    # auxiliaries and copulas
    "hai", "hain", "tha", "thi",
    # questions
    "kya", "kyun", "kyon", "kaise", "kaisi", "kaisa",
    "kahaan", "kahan", "kab", "kaun", "kitna", "kitni",
    # negation / affirmation
    "nahi", "nahin", "haan", "ji",
    # imperatives common in commands
    "karo", "kar", "kiya", "raha", "rahi", "rahe",
    "lagao", "lagado", "bajao", "sunao", "chalao",
    "bana", "banao", "batao", "dikhao", "khol",
    # quantifiers / particles
    "thoda", "bahut", "kuch", "sab",
    "abhi", "phir", "fir", "ab", "yeh", "wo", "woh",
    # vocatives / pronouns / common Hinglish flavour words
    "yaar", "bhai", "didi", "bhaiya",
    "mujhe", "tujhe", "mera", "tera", "uska", "humein",
    "tumhe", "tum", "mai", "tu",
    # connectives
    "aur", "ya", "magar", "lekin", "kyunki",
    # very common verb forms
    "hoga", "hogi", "gaya", "gayi", "gaye",
    # food/light/music words people commonly mix in
    "gaana", "gaane", "roshni", "batti",
}

_WORD_RE = re.compile(r"[a-zA-Z]+")


def detect_lang(text: str | None) -> str:
    """
    Return "hi" if the text looks Hindi/Hinglish, else "en".

    Hinglish is bucketed as "hi" for filler/error purposes — a user
    who said "thoda volume kam karo" is perfectly comfortable hearing
    "Ek second." back as the filler.
    """
    if not text:
        return "en"
    # Devanagari → definitely Hindi.
    if _DEVANAGARI_RE.search(text):
        return "hi"
    # Romanized check: lowercase, tokenize on word boundaries, look for
    # any marker. One match is enough — short utterances ("haan",
    # "kya?") deserve a Hindi filler too.
    lowered = text.lower()
    for tok in _WORD_RE.findall(lowered):
        if tok in _HI_MARKERS:
            return "hi"
    return "en"


# ── Cache builders ──────────────────────────────────────────────────


def _synth_pool(voice_router, personality, phrases: list[str]) -> list[bytes]:
    """Synthesize a list of phrases through the voice router; skip any that fail."""
    wavs: list[bytes] = []
    for phrase in phrases:
        try:
            wav = voice_router.speak(phrase, personality)
            if wav:
                wavs.append(wav)
        except Exception as e:
            log.warning("TTS synth for '%s' (personality=%s) failed: %s",
                        phrase, personality.id, e)
    return wavs


def ensure_filler_for(voice_router, personality) -> None:
    """
    Lazy-build the filler clip cache for the given personality on first
    use. Builds BOTH the English and Hindi pools at once — the cost is
    a few hundred ms of TTS at startup-per-personality, and avoids a
    second cold-cache moment when the user switches language mid-session.
    """
    if not voice_router or personality is None:
        return
    pid = personality.id
    with _FILLER_LOCK:
        if pid in _FILLER_CACHE:
            return  # already built
        # Mark immediately so concurrent requests don't all try to build.
        _FILLER_CACHE[pid] = {}

    phrase_map = _FILLER_PHRASES.get(pid, _FILLER_PHRASES["_default"])
    built: dict[str, list[bytes]] = {}
    for lang, phrases in phrase_map.items():
        built[lang] = _synth_pool(voice_router, personality, phrases)

    with _FILLER_LOCK:
        _FILLER_CACHE[pid] = built
    log.info(
        "Filler cache built for '%s': %s",
        pid,
        ", ".join(f"{lang}={len(wavs)}" for lang, wavs in built.items()),
    )


def pick_filler_wav(personality_id: str, user_text: str | None = None) -> bytes | None:
    """
    Return a random filler WAV for the given personality and the user's
    detected language, or None if nothing is cached.

    `user_text` is the STT transcript — pass it in so we can pick a
    same-language filler. If omitted (e.g. STT failed and we have no
    transcript), defaults to English.
    """
    lang = detect_lang(user_text)
    with _FILLER_LOCK:
        per_pid = _FILLER_CACHE.get(personality_id) or _FILLER_CACHE.get("_default", {})
        wavs = per_pid.get(lang) or per_pid.get("en") or []
        # Last-ditch fallback: any language we have.
        if not wavs:
            for v in per_pid.values():
                if v:
                    wavs = v
                    break
    return random.choice(wavs) if wavs else None


def ensure_error_audio_for(voice_router, personality) -> None:
    """Lazy-build the error-clip cache for the given personality (all languages)."""
    if not voice_router or personality is None:
        return
    pid = personality.id
    with _FILLER_LOCK:
        if pid in _ERROR_CACHE:
            return
        _ERROR_CACHE[pid] = {}

    phrase_map = _ERROR_PHRASES.get(pid, _ERROR_PHRASES["_default"])
    built: dict[str, list[bytes]] = {}
    for lang, phrases in phrase_map.items():
        built[lang] = _synth_pool(voice_router, personality, phrases)

    with _FILLER_LOCK:
        _ERROR_CACHE[pid] = built


def pick_error_wav(personality_id: str, user_text: str | None = None) -> bytes | None:
    """
    Return a random error WAV for the given personality and the user's
    detected language, or None if nothing is cached.

    Errors especially MUST match the user's language — a Hindi user
    shouldn't get an English error she may not parse.
    """
    lang = detect_lang(user_text)
    with _FILLER_LOCK:
        per_pid = _ERROR_CACHE.get(personality_id) or _ERROR_CACHE.get("_default", {})
        wavs = per_pid.get(lang) or per_pid.get("en") or []
        if not wavs:
            for v in per_pid.values():
                if v:
                    wavs = v
                    break
    return random.choice(wavs) if wavs else None
