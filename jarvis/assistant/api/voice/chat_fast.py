"""
Heuristic chat fast-path + sentence-boundary detection for the streaming
voice endpoint.

## Fast-path heuristic (`is_obvious_chat`)

For obviously-chat questions (open-ended factual / explanation prompts),
we skip the classifier entirely and stream a chat reply directly. This
saves the JSON-mode penalty (Ollama's grammar-constrained decoding is
~2× slower than free generation) AND skips the second LLM round-trip
that would otherwise run for chat intents.

This runs AFTER the regex prefilter — so "what time is it", "what's the
weather", "tell me a story", etc. are already routed to their proper
handlers via prefilter and never reach this check. We only catch the
residual "what is the speed of light" / "explain quantum computing"
class of questions.

Conservative by design: false negatives are fine (the classifier still
runs), false positives = a "play song X" command misrouted to chat,
which would be a silent failure. So we anchor on opener phrases that
are vanishingly unlikely to ever start a command, AND apply a
belt-and-suspenders action-verb guard to reject anything that contains
a command verb.

The contract is locked in by `tests/test_api_smoke.py::test_is_obvious_chat_classifications`.

## First-chunk boundary (`find_first_chunk_boundary`)

The streaming TTS worker emits one WAV per sentence — but waiting for
a full sentence to complete adds 0.5-2s to TTFA. To shave that, we
emit the first chunk EARLIER at any natural prosodic break: sentence
end, or a comma/dash/colon after at least N words. After the user is
already hearing audio, we revert to whole-sentence emission to keep
prosody natural.

We deliberately do NOT emit on raw word-count fallback because Kokoro/
Piper prosody breaks audibly when a chunk ends mid-clause. The win
from cutting 0.3s off TTFA isn't worth the audio glitch.

For LLM responses without internal commas (which is common with short
replies), `find_first_chunk_boundary` returns -1 and the caller falls
back to whole-sentence emission — same TTFA as before, no regression.
"""

from __future__ import annotations

import re


# Sentence end: punctuation followed by whitespace, plus Hindi danda (।).
_SENTENCE_END_RE = re.compile(r"(?<=[.!?;:।])\s+")

# Sub-sentence emit boundary — clause break (comma/dash/colon/semicolon).
# Used only for the FIRST chunk in a chat-fast turn to shave TTFA.
_CLAUSE_BREAK_RE = re.compile(r"(?<=[,—:;])\s+")


def find_first_chunk_boundary(text: str, min_words: int = 5) -> int:
    """
    Find a NATURAL position to flush the FIRST audio chunk early.

    Returns the index AFTER the boundary character (so text[:idx] is the
    chunk to emit). Returns -1 if no good boundary yet.

    Strategy: emit only at natural prosodic breaks — sentence end or
    comma/dash/colon after at least `min_words` words. We deliberately
    do NOT emit on raw word-count fallback because TTS prosody breaks
    audibly when a chunk ends mid-clause.
    """
    words = text.split()
    if len(words) < min_words:
        return -1

    # 1. Sentence end
    matches = list(_SENTENCE_END_RE.finditer(text))
    if matches:
        return matches[0].end()

    # 2. Clause break (comma/em-dash/colon/semicolon) after min_words
    for m in _CLAUSE_BREAK_RE.finditer(text):
        prefix = text[: m.start()].split()
        if len(prefix) >= min_words:
            return m.end()

    return -1


# ── Heuristic chat-fast classifier ─────────────────────────────────────

_CHAT_HEURISTIC_RE = re.compile(
    r"^("
    r"what\s+(is|are|was|were|does|do|did|will|would|kind|type|color|colour)\b"
    r"|what's\s+(the|a|an)\b"
    r"|how\s+(do|does|did|can|would|should|long|tall|big|small|much|many|far|fast|come)\b"
    r"|why\s+(is|are|was|were|do|does|did|don't|doesn't|can't|would|should)\b"
    r"|who\s+(is|was|were|are|invented|discovered|wrote|made|created|painted|composed)\b"
    r"|when\s+(is|was|were|did|does|do|will|would)\b"
    r"|where\s+(is|are|was|were|did|does|do|will)\b"
    r"|tell\s+me\s+(about|something\s+about|more\s+about)\b"
    r"|explain\s+(to\s+me\s+)?\w+"
    r"|describe\s+\w+"
    r"|define\s+\w+"
    r"|do\s+you\s+know\s+(what|how|why|who|when|where|about)\b"
    r"|can\s+you\s+(tell|explain|describe)\b"
    r")",
    re.IGNORECASE,
)


# Belt-and-suspenders verb guard — even if the heuristic regex matches,
# the presence of an action verb anywhere disqualifies (since the user
# may have typed "what is play sajni" — match on "what is" but reject
# because of "play").
_ACTION_VERBS_RE = re.compile(
    r"\b(play|baja|bajao|chala|chalao|laga|lagao|stop|pause|skip|next|"
    r"on|off|set|turn|switch|mute|unmute|increase|decrease|brighten|dim|"
    r"open|close|search\s+for|search\s+youtube|remind|set\s+a?\s*timer|"
    r"alarm|wake\s+me|change|switch\s+to)\b",
    re.IGNORECASE,
)


def is_obvious_chat(text: str) -> bool:
    """Return True for questions that are clearly chat — no command verbs."""
    cleaned = text.strip()
    if not cleaned:
        return False
    # Reject inputs that contain explicit action verbs even if they start with
    # a chat-y opener. Belt-and-suspenders.
    if _ACTION_VERBS_RE.search(cleaned):
        return False
    return bool(_CHAT_HEURISTIC_RE.match(cleaned))
