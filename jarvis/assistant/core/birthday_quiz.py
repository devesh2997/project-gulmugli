"""
Birthday Quiz Engine — playful "how well does Vesper know us" quiz with a
heartfelt recorded reveal at the end.

## Background

Phase 5.4 of the birthday roadmap. The existing `providers/quiz/trivia.py`
is a *general* LLM-generated trivia quiz; this is a *birthday-specific*,
hand-curated quiz about Astha — different domain, different shape. We
keep them as parallel features rather than overloading the trivia
provider with a "birthday mode" branch:

  - Trivia is LLM-generated, infinite, scored on accuracy.
  - Birthday quiz is YAML-curated, finite (5 questions), and exists to
    set up the recorded reveal at the end.

Both can coexist; the user picks via voice phrasing.

## Three pieces

  Question
    Frozen dataclass — id, question text, expected answers,
    on_correct/on_wrong replies, tags.

  QuizSession
    Per-conversation state. Holds the chosen question list, the
    current index, and the running score. Created by start_session().

  BirthdayQuizEngine
    Loads the YAML once at startup. Vends QuizSessions on demand
    via start_session(). Stateless across sessions — multiple sessions
    in one process are safe.

## Reveal

run_reveal(ctx) speaks the intro, plays the recorded audio if it exists,
falls back to TTS-on-text if the file is missing (recording is a Phase
7.1 task, so this *will* miss until then), then speaks the outro.

## File layout

Default quiz pack: `events/astha-birthday/quiz/about_us.yaml`

This engine loads that file regardless of whether the birthday event is
"active" — the quiz is a year-round mini-app, not gated on a date.
The path is configurable via the constructor for tests.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from core.audio_playback import play_file
from core.logger import get_logger

log = get_logger("birthday_quiz")


# ── Defaults ────────────────────────────────────────────────────────

# Default quiz pack — year-round, always loaded from the astha-birthday
# pack since this mode is hers.
_DEFAULT_PACK = (
    Path(__file__).resolve().parent.parent
    / "events" / "astha-birthday" / "quiz" / "about_us.yaml"
)


# ── Public types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Question:
    """One parsed quiz question. Frozen — engine rebuilds the list on reload()."""

    id: str
    question: str
    expected_answers: tuple[str, ...]   # case-insensitive contains-match
    on_correct: str
    on_wrong: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinalReveal:
    """The end-of-quiz reveal. Always present (with fallbacks) after load."""

    intro: str
    audio_file: Optional[str] = None
    fallback_text: Optional[str] = None
    outro: Optional[str] = None


@dataclass
class QuizContext:
    """Runtime hooks supplied by the caller — same shape as JokeContext."""

    voice_router: Optional[Any] = None
    """Used for TTS. None = engine logs the text and no-ops audio."""

    bank_dir: Optional[Path] = None
    """Resolves relative `audio_file` paths in the reveal. None = treat as absolute only."""

    sleep_fn: Any = field(default=None)
    """
    Override `time.sleep` for tests. None means use real sleep. Critical
    for testability — without it, reveal tests would idle for real beats.
    """


@dataclass
class AnswerResult:
    """What `judge_answer` returns."""

    correct: bool
    response: str   # the on_correct or on_wrong text from YAML
    question_id: str = ""


@dataclass
class QuizResult:
    """Summary returned by `run_reveal` and friends."""

    delivered: bool
    detail: str = ""   # "ok" | "no_voice" | "exception: ..."


# ── Session ─────────────────────────────────────────────────────────


class QuizSession:
    """
    A single run of the quiz. Holds the chosen question list + cursor.
    Not thread-safe — one session is meant to be driven by one
    conversation thread (the voice handler). Multiple parallel
    sessions get separate QuizSession instances.
    """

    def __init__(
        self,
        questions: list[Question],
        final_reveal: FinalReveal,
    ):
        self._questions = list(questions)
        self._final_reveal = final_reveal
        self._index = 0
        self._correct_count = 0
        self._answered_ids: list[str] = []   # in ask order

    # ── Question stepping ─────────────────────────────────────

    @property
    def total(self) -> int:
        return len(self._questions)

    @property
    def asked(self) -> int:
        """How many have been .next_question()'d so far."""
        return self._index

    def next_question(self) -> Optional[Question]:
        """
        Return the next question. Returns None when the list is
        exhausted (caller should then run the reveal).
        """
        if self._index >= len(self._questions):
            return None
        q = self._questions[self._index]
        self._index += 1
        return q

    def current_question(self) -> Optional[Question]:
        """The most recently returned question (for judge_answer context)."""
        if self._index == 0:
            return None
        return self._questions[self._index - 1]

    # ── Judging ────────────────────────────────────────────────

    def judge_answer(self, text: str) -> AnswerResult:
        """
        Score the user's text against the current question's
        `expected_answers`. Case-insensitive contains-match — any
        expected substring appearing inside `text` counts as correct.

        If there's no current question (e.g., judge before the first
        next_question), returns a wrong-result with empty response.
        """
        q = self.current_question()
        if q is None:
            return AnswerResult(correct=False, response="", question_id="")

        haystack = (text or "").strip().lower()
        is_correct = False
        if haystack:
            for needle in q.expected_answers:
                n = (needle or "").strip().lower()
                if n and n in haystack:
                    is_correct = True
                    break

        if is_correct:
            self._correct_count += 1
        self._answered_ids.append(q.id)

        return AnswerResult(
            correct=is_correct,
            response=q.on_correct if is_correct else q.on_wrong,
            question_id=q.id,
        )

    # ── Score & reveal ────────────────────────────────────────

    def score(self) -> int:
        """Number of correctly-answered questions so far."""
        return self._correct_count

    def is_done(self) -> bool:
        return self._index >= len(self._questions)

    def run_reveal(self, ctx: QuizContext) -> QuizResult:
        """
        Speak the intro, play the audio (or TTS the fallback text),
        speak the outro. Best-effort — never raises; mirrors the
        astha_jokes / intro_runner contract.
        """
        try:
            return self._run_reveal_inner(ctx)
        except Exception as e:
            log.warning("birthday_quiz: reveal failed: %s", e)
            return QuizResult(False, f"exception: {type(e).__name__}: {e}")

    def _run_reveal_inner(self, ctx: QuizContext) -> QuizResult:
        reveal = self._final_reveal
        spoke_anything = False

        # Intro line.
        if reveal.intro:
            if self._say(reveal.intro, ctx):
                spoke_anything = True

        # Audio file if present + readable; else fallback text.
        played_audio = False
        if reveal.audio_file:
            audio_path = Path(reveal.audio_file)
            if not audio_path.is_absolute() and ctx.bank_dir is not None:
                audio_path = ctx.bank_dir / audio_path
            if audio_path.is_file():
                played_audio = play_file(audio_path, blocking=True)
                if not played_audio:
                    log.warning(
                        "birthday_quiz: reveal audio failed to play: %s",
                        audio_path,
                    )
            else:
                log.info(
                    "birthday_quiz: reveal audio missing — falling back to text: %s",
                    audio_path,
                )

        if not played_audio and reveal.fallback_text:
            if self._say(reveal.fallback_text, ctx):
                spoke_anything = True

        # Short beat before the outro lands.
        self._sleep(0.5, ctx)

        # Outro.
        if reveal.outro:
            if self._say(reveal.outro, ctx):
                spoke_anything = True

        return QuizResult(
            delivered=True,
            detail="ok" if spoke_anything or played_audio else "no_voice",
        )

    # ── Delivery primitives (mirrors astha_jokes._say / _sleep) ──

    def _say(self, text: str, ctx: QuizContext) -> bool:
        """
        Speak one chunk through the voice_router. Returns True on
        attempted delivery, False if no voice path.
        """
        if ctx.voice_router is None:
            log.info("birthday_quiz: would say %r (no voice_router)", text[:60])
            return False
        say = getattr(ctx.voice_router, "say", None)
        if callable(say):
            try:
                say(text)
            except Exception as e:
                log.warning("birthday_quiz: voice_router.say failed: %s", e)
                return False
            return True
        speak = getattr(ctx.voice_router, "speak", None)
        if callable(speak):
            try:
                wav = speak(text)
            except Exception as e:
                log.warning("birthday_quiz: voice_router.speak failed: %s", e)
                return False
            if wav:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(wav)
                    tmp = f.name
                play_file(tmp, blocking=True)
                try:
                    Path(tmp).unlink(missing_ok=True)
                except Exception:
                    pass
            return True
        log.warning("birthday_quiz: voice_router has no .say or .speak — skipping")
        return False

    def _sleep(self, seconds: float, ctx: QuizContext) -> None:
        fn = ctx.sleep_fn or time.sleep
        if seconds > 0:
            try:
                fn(seconds)
            except Exception as e:
                log.warning("birthday_quiz: sleep_fn failed: %s", e)


# ── Engine ──────────────────────────────────────────────────────────


class BirthdayQuizEngine:
    """
    Loads questions from a YAML pack and vends QuizSessions.

    Thread-safe for the read path. Concurrent calls to `start_session`
    from multiple voice turns are safe; `reload` rebuilds atomically
    under a lock.
    """

    def __init__(self, yaml_path: Optional[Path] = None):
        self._path = Path(yaml_path) if yaml_path else _DEFAULT_PACK
        self._questions: list[Question] = []
        self._final_reveal: FinalReveal = FinalReveal(intro="")
        self._shuffle = True
        self._default_count = 5
        self._lock = threading.Lock()
        self.reload()

    # ── Public API ─────────────────────────────────────────────

    def reload(self) -> int:
        """
        Rescan the pack and rebuild the in-memory question list.
        Returns the number of questions loaded. Failures log + load 0
        rather than raising — never crash the assistant.
        """
        questions, reveal, shuffle, count = _load_pack(self._path)
        with self._lock:
            self._questions = questions
            self._final_reveal = reveal
            self._shuffle = shuffle
            self._default_count = count
        log.info(
            "birthday_quiz: %d question(s) loaded from %s (shuffle=%s, count=%d)",
            len(questions), self._path.name, shuffle, count,
        )
        return len(questions)

    def list_questions(self) -> list[Question]:
        with self._lock:
            return list(self._questions)

    @property
    def final_reveal(self) -> FinalReveal:
        with self._lock:
            return self._final_reveal

    def start_session(self, question_count: Optional[int] = None) -> QuizSession:
        """
        Create a new session. Picks `question_count` questions (or the
        pack's default if not specified), shuffled if the pack says so.

        If the bank is empty, returns a session with zero questions —
        the caller's loop will hit None on the first next_question()
        and skip straight to the reveal. We do this rather than raising
        so the user always gets *something* (the reveal still plays).
        """
        with self._lock:
            pool = list(self._questions)
            shuffle = self._shuffle
            default_count = self._default_count
            reveal = self._final_reveal

        n = question_count if question_count is not None else default_count
        if n < 0:
            n = 0

        if shuffle:
            random.shuffle(pool)
        chosen = pool[:n] if n > 0 else []

        log.info(
            "birthday_quiz: starting session with %d/%d question(s) (shuffle=%s)",
            len(chosen), len(pool), shuffle,
        )
        return QuizSession(questions=chosen, final_reveal=reveal)


# ── Loading ─────────────────────────────────────────────────────────


def _load_pack(
    path: Path,
) -> tuple[list[Question], FinalReveal, bool, int]:
    """
    Parse the YAML pack. Returns (questions, final_reveal, shuffle, count).
    Bad questions are logged and skipped — one malformed entry does not
    break the rest. Missing file → empty pack with a default reveal so
    the engine still vends sessions cleanly.
    """
    empty_reveal = FinalReveal(intro="")
    if not path.is_file():
        log.warning("birthday_quiz: pack file not found: %s", path)
        return [], empty_reveal, True, 5

    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log.warning("birthday_quiz: YAML parse error in %s: %s", path, e)
        return [], empty_reveal, True, 5
    except OSError as e:
        log.warning("birthday_quiz: failed to open %s: %s", path, e)
        return [], empty_reveal, True, 5

    if not isinstance(data, dict):
        log.warning(
            "birthday_quiz: pack must be a mapping at top level, got %s",
            type(data).__name__,
        )
        return [], empty_reveal, True, 5

    shuffle = bool(data.get("shuffle_questions", True))
    count_raw = data.get("question_count", 5)
    try:
        count = int(count_raw)
    except (TypeError, ValueError):
        count = 5

    raw_qs = data.get("questions") or []
    if not isinstance(raw_qs, list):
        log.warning(
            "birthday_quiz: questions must be a list, got %s",
            type(raw_qs).__name__,
        )
        raw_qs = []

    questions: list[Question] = []
    for i, raw in enumerate(raw_qs):
        try:
            q = _parse_question(raw)
            if q is not None:
                questions.append(q)
        except Exception as e:
            log.warning("birthday_quiz: skipping question at index %d: %s", i, e)

    reveal = _parse_reveal(data.get("final_reveal"))

    return questions, reveal, shuffle, count


def _parse_question(raw: Any) -> Optional[Question]:
    if not isinstance(raw, dict):
        raise ValueError(f"question must be a dict, got {type(raw).__name__}")
    qid = raw.get("id")
    if not isinstance(qid, str) or not qid:
        raise ValueError("missing id")
    text = raw.get("question")
    if not isinstance(text, str) or not text:
        raise ValueError("missing question text")
    expected = raw.get("expected_answers") or []
    if not isinstance(expected, list):
        raise ValueError("expected_answers must be a list")
    expected_clean = tuple(
        str(e).strip() for e in expected if isinstance(e, (str, int, float)) and str(e).strip()
    )
    if not expected_clean:
        raise ValueError("expected_answers must be non-empty")

    on_correct = raw.get("on_correct") or ""
    on_wrong = raw.get("on_wrong") or ""
    if not isinstance(on_correct, str):
        on_correct = ""
    if not isinstance(on_wrong, str):
        on_wrong = ""

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tag_tuple = tuple(str(t) for t in tags if t is not None)

    return Question(
        id=qid,
        question=text,
        expected_answers=expected_clean,
        on_correct=on_correct,
        on_wrong=on_wrong,
        tags=tag_tuple,
    )


def _parse_reveal(raw: Any) -> FinalReveal:
    """Lenient — every field is optional. Missing reveal block is fine."""
    if not isinstance(raw, dict):
        return FinalReveal(intro="")

    def _str(key: str) -> Optional[str]:
        v = raw.get(key)
        if isinstance(v, str) and v.strip():
            return v
        return None

    return FinalReveal(
        intro=_str("intro") or "",
        audio_file=_str("audio_file"),
        fallback_text=_str("fallback_text"),
        outro=_str("outro"),
    )


# ── Singleton ───────────────────────────────────────────────────────

_default: Optional[BirthdayQuizEngine] = None
_default_lock = threading.Lock()


def get_birthday_quiz_engine() -> BirthdayQuizEngine:
    """Lazy singleton accessor for the default birthday quiz pack."""
    global _default
    with _default_lock:
        if _default is None:
            _default = BirthdayQuizEngine()
        return _default
