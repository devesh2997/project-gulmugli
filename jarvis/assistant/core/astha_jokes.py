"""
Astha Jokes Engine — the silly-questions / pun / phasaa-do mode.

## Background

Astha is a connoisseur of stupid jokes. Some are pun questions
("Salman Khan ki shadi kab hogi? — Na jaane kab"). Some lead the
listener into a phonetic trap ("T W E... T W I... T W O...").
Some are just one-liners. The mode honors all of those — one engine
that handles three joke shapes uniformly.

Trigger is NLU-classified from natural phrasings the user picks up
from social media: "tell me jokes like Astha", "Astha-style joke
sunao", "phasaa do mujhe", "do that thing Astha does", "Astha mode".

The classifier maps any of those to a single `astha_jokes` intent;
the handler in `core/intent_handler.py` calls into this engine.

## Three joke types (matches the YAML schema)

  single_turn
    text: <delivered as one breath; pun + answer together>

  setup_then_punchline
    turns: list[str]                 spoken one at a time, pause between
    pause_between_turns_s: float     default 4.0
    punchline: str                   fired after the last setup turn
    laugh_audio: <optional path>     played after punchline

  interactive
    setup: str                       a single question
    expected_wrong: list[str]        case-insensitive contains-match
    punchline_correct: str           if user dodges the trap
    punchline_wrong: str             if user falls in
    (Phase 4.2 ships in two stages — Stage A delivers `punchline_wrong`
    unconditionally for `interactive` jokes (~95% of the time the user
    falls for the trap, and assuming a hit lands fine). Stage B will
    integrate with the voice loop for proper STT response detection.)

## What this module deliberately does NOT do

  - LISTEN for user response after a setup. That's Stage B —
    requires plumbing into the streaming voice endpoint, which has
    its own end-of-utterance lifecycle. Out of scope for the engine.
  - Generate jokes. The corpus is hand-curated YAML — that's where
    Astha's actual jokes go. The engine is a deliverer, not a writer.

## File layout

Default joke bank: `events/astha-birthday/jokes/astha_jokes.yaml`

Year-round mode: this engine loads from there regardless of whether
the birthday event is active. The path is configurable via the
constructor so future tests / packs can point at their own banks.
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

log = get_logger("astha_jokes")


# ── Defaults ────────────────────────────────────────────────────────

# Default joke bank — year-round, always loaded from the astha-birthday
# pack since this mode is hers.
_DEFAULT_BANK = (
    Path(__file__).resolve().parent.parent
    / "events" / "astha-birthday" / "jokes" / "astha_jokes.yaml"
)


# ── Public types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Joke:
    """One parsed joke. Frozen — engine rebuilds the list on reload()."""

    id: str
    type: str            # "single_turn" | "setup_then_punchline" | "interactive"
    tags: tuple[str, ...]

    # single_turn fields
    text: Optional[str] = None

    # setup_then_punchline fields
    turns: tuple[str, ...] = ()
    pause_between_turns_s: float = 4.0
    punchline: Optional[str] = None
    laugh_audio: Optional[str] = None

    # interactive fields
    setup: Optional[str] = None
    expected_wrong: tuple[str, ...] = ()
    punchline_correct: Optional[str] = None
    punchline_wrong: Optional[str] = None


@dataclass
class JokeContext:
    """Runtime hooks supplied by the caller."""

    voice_router: Optional[Any] = None
    """Used for TTS. None = engine prints the joke text and no-ops audio."""

    bank_dir: Optional[Path] = None
    """Resolves relative `laugh_audio` paths. None = treat as absolute only."""

    sleep_fn: Any = field(default=None)
    """
    Override `time.sleep` for tests. None means use real sleep. The fn must
    accept `seconds: float`. Critical for testability — without it, the
    `setup_then_punchline` test waits 4s × turns.
    """


@dataclass
class JokeResult:
    joke_id: str
    delivered: bool
    detail: str = ""   # "ok" | "no_voice" | "exception: ..."


# ── Engine ──────────────────────────────────────────────────────────


class JokeEngine:
    """
    Loads jokes from a YAML bank and delivers them on demand.

    Thread-safe for the read path. Concurrent calls to `pick_random` /
    `deliver` from multiple voice turns are safe; `reload` rebuilds
    atomically under a lock.
    """

    def __init__(self, bank_path: Optional[Path] = None):
        self._bank_path = Path(bank_path) if bank_path else _DEFAULT_BANK
        self._jokes: list[Joke] = []
        self._lock = threading.Lock()
        self.reload()

    # ── Public API ─────────────────────────────────────────────

    def reload(self) -> int:
        """
        Rescan the bank file and rebuild the in-memory joke list.
        Returns the number of jokes loaded. Failures log + load 0
        rather than raising — never crash the assistant.
        """
        new_jokes = _load_bank(self._bank_path)
        with self._lock:
            self._jokes = new_jokes
        log.info("astha_jokes: %d joke(s) loaded from %s",
                 len(new_jokes), self._bank_path.name)
        return len(new_jokes)

    def list_jokes(self) -> list[Joke]:
        with self._lock:
            return list(self._jokes)

    def pick_random(self, tags: Optional[list[str]] = None) -> Optional[Joke]:
        """
        Pick a random joke. If `tags` is given, only jokes whose tag set
        OVERLAPS with `tags` are eligible. Returns None if no jokes match
        (or the bank is empty).
        """
        with self._lock:
            pool = list(self._jokes)
        if not pool:
            return None
        if tags:
            wanted = {t.lower() for t in tags}
            pool = [j for j in pool if wanted & set(j.tags)]
            if not pool:
                return None
        return random.choice(pool)

    def deliver(self, joke: Joke, ctx: JokeContext) -> JokeResult:
        """
        Run the joke through the voice router. Returns a JokeResult
        summary; never raises — the engine's job is to deliver as
        gracefully as possible, not to bubble errors.
        """
        try:
            if joke.type == "single_turn":
                return self._deliver_single(joke, ctx)
            if joke.type == "setup_then_punchline":
                return self._deliver_setup_punchline(joke, ctx)
            if joke.type == "interactive":
                return self._deliver_interactive_stage_a(joke, ctx)
            return JokeResult(joke.id, False, f"unknown joke type {joke.type!r}")
        except Exception as e:
            log.warning("astha_jokes: delivery failed for %s: %s", joke.id, e)
            return JokeResult(joke.id, False, f"exception: {type(e).__name__}: {e}")

    # ── Delivery primitives ────────────────────────────────────

    def _say(self, text: str, ctx: JokeContext) -> bool:
        """
        Speak one chunk through the voice_router. Returns True on
        attempted delivery (best-effort), False if no voice path.
        """
        if ctx.voice_router is None:
            log.info("astha_jokes: would say %r (no voice_router)", text[:60])
            return False
        say = getattr(ctx.voice_router, "say", None)
        if callable(say):
            say(text)
            return True
        speak = getattr(ctx.voice_router, "speak", None)
        if callable(speak):
            wav = speak(text)
            if wav:
                # Best-effort playback via temp file (same pattern as
                # intro_runner).
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
        log.warning("astha_jokes: voice_router has no .say or .speak — skipping")
        return False

    def _sleep(self, seconds: float, ctx: JokeContext) -> None:
        fn = ctx.sleep_fn or time.sleep
        if seconds > 0:
            fn(seconds)

    # ── Per-type delivery ─────────────────────────────────────

    def _deliver_single(self, joke: Joke, ctx: JokeContext) -> JokeResult:
        if not joke.text:
            return JokeResult(joke.id, False, "single_turn: text missing")
        spoken = self._say(joke.text, ctx)
        return JokeResult(joke.id, True, "ok" if spoken else "no_voice")

    def _deliver_setup_punchline(self, joke: Joke, ctx: JokeContext) -> JokeResult:
        if not joke.turns:
            return JokeResult(joke.id, False, "setup_then_punchline: turns empty")
        if not joke.punchline:
            return JokeResult(joke.id, False, "setup_then_punchline: punchline missing")
        # Each setup turn, separated by the configured pause.
        for i, turn in enumerate(joke.turns):
            self._say(turn, ctx)
            # No pause AFTER the last turn — punchline lands faster.
            if i < len(joke.turns) - 1:
                self._sleep(joke.pause_between_turns_s, ctx)
        # Short beat before the punchline lands.
        self._sleep(min(joke.pause_between_turns_s, 1.5), ctx)
        self._say(joke.punchline, ctx)
        # Optional laugh audio after the reveal.
        if joke.laugh_audio:
            laugh_path = Path(joke.laugh_audio)
            if not laugh_path.is_absolute() and ctx.bank_dir is not None:
                # Joke file references are relative to the PACK root
                # (e.g. media/sounds/laugh.wav) — bank_dir points there.
                laugh_path = ctx.bank_dir / laugh_path
            if laugh_path.is_file():
                play_file(laugh_path, blocking=False)
        return JokeResult(joke.id, True, "ok")

    def _deliver_interactive_stage_a(self, joke: Joke, ctx: JokeContext) -> JokeResult:
        """
        Stage A: deliver the setup, brief pause as if waiting, then drop
        the wrong-answer punchline. ~95% of the time the user falls for
        the trap and Vesper's reaction lands; the 5% case where they
        catch it gets the same line — which is ALSO funny ("phans gaye!"
        when the user *didn't* fall for it has its own charm).

        Stage B (future): integrate with the voice endpoint to actually
        listen for the response and pick punchline_correct vs _wrong.
        """
        if not joke.setup:
            return JokeResult(joke.id, False, "interactive: setup missing")
        chosen_punchline = joke.punchline_wrong or joke.punchline_correct
        if not chosen_punchline:
            return JokeResult(joke.id, False, "interactive: no punchline defined")
        self._say(joke.setup, ctx)
        # ~3s pause as if listening for the trapped answer.
        self._sleep(3.0, ctx)
        self._say(chosen_punchline, ctx)
        return JokeResult(joke.id, True, "ok (stage A — wrong-answer punchline)")


# ── Loading ─────────────────────────────────────────────────────────


def _load_bank(path: Path) -> list[Joke]:
    """
    Parse the YAML bank into a list of Jokes. Bad entries are logged
    and skipped — one malformed joke does not break the rest.
    """
    if not path.is_file():
        log.warning("astha_jokes: bank file not found: %s", path)
        return []
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log.warning("astha_jokes: YAML parse error in %s: %s", path, e)
        return []

    if not isinstance(data, list):
        log.warning("astha_jokes: bank must be a list at top level, got %s",
                    type(data).__name__)
        return []

    jokes: list[Joke] = []
    for i, raw in enumerate(data):
        try:
            joke = _parse_joke(raw)
            if joke is not None:
                jokes.append(joke)
        except Exception as e:
            log.warning("astha_jokes: skipping joke at index %d: %s", i, e)
    return jokes


def _parse_joke(raw: Any) -> Optional[Joke]:
    if not isinstance(raw, dict):
        raise ValueError(f"joke must be a dict, got {type(raw).__name__}")
    jid = raw.get("id")
    jtype = raw.get("type")
    if not isinstance(jid, str) or not jid:
        raise ValueError("missing id")
    if jtype not in ("single_turn", "setup_then_punchline", "interactive"):
        raise ValueError(f"invalid type: {jtype!r}")

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    if jtype == "single_turn":
        text = raw.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError("single_turn missing text")
        return Joke(id=jid, type=jtype, tags=tuple(tags), text=text)

    if jtype == "setup_then_punchline":
        turns = raw.get("turns") or []
        if not isinstance(turns, list) or not turns:
            raise ValueError("setup_then_punchline needs non-empty `turns` list")
        punchline = raw.get("punchline")
        if not isinstance(punchline, str) or not punchline:
            raise ValueError("setup_then_punchline missing punchline")
        pause = float(raw.get("pause_between_turns_s", 4.0))
        laugh = raw.get("laugh_audio")
        return Joke(
            id=jid, type=jtype, tags=tuple(tags),
            turns=tuple(t for t in turns if isinstance(t, str) and t),
            pause_between_turns_s=pause,
            punchline=punchline,
            laugh_audio=laugh if isinstance(laugh, str) and laugh else None,
        )

    if jtype == "interactive":
        setup = raw.get("setup")
        if not isinstance(setup, str) or not setup:
            raise ValueError("interactive missing setup")
        expected_wrong = raw.get("expected_wrong") or []
        if not isinstance(expected_wrong, list):
            expected_wrong = []
        return Joke(
            id=jid, type=jtype, tags=tuple(tags),
            setup=setup,
            expected_wrong=tuple(
                str(w).lower() for w in expected_wrong if w is not None
            ),
            punchline_correct=raw.get("punchline_correct"),
            punchline_wrong=raw.get("punchline_wrong"),
        )

    return None  # unreachable


# ── Singleton ───────────────────────────────────────────────────────

_default: Optional[JokeEngine] = None
_default_lock = threading.Lock()


def get_joke_engine() -> JokeEngine:
    """Lazy singleton accessor for the default joke bank."""
    global _default
    with _default_lock:
        if _default is None:
            _default = JokeEngine()
        return _default
