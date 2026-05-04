"""
Voice Memos — pre-recorded spoken letters from Devesh, surfaced on demand.

## What this is

Different from the singing playback (`besura`): voice memos are SPOKEN
letters. Recorded once, listened to many times. Astha asks "Vesper,
Devesh ne kya chhoda hai mere liye?" or "Vesper, agar main udaas hoon"
and the matching memo plays.

## Schema

`events/<pack>/media/voice_memos/memos.yaml`:

    memos:
      - file: birthday_letter.wav
        title: "Birthday letter"
        tags: [birthday, default]
        available_from: "2026-05-14"   # only playable on or after this date
      - file: when_you_are_sad.wav
        title: "When you're sad"
        tags: [sad, comfort]
        available_from: null            # always available
      - file: just_because.wav
        title: "Just because"
        tags: [random, love]

Fields per memo:
  - file: path relative to the memos directory (or absolute)
  - title: human-readable label, used in "what did Devesh leave?" listings
  - tags: list of strings; querying by tag returns matching memos
  - available_from: ISO date string. The memo is silent before that
    date, then becomes playable forever after. None = always available.

## Lookup behavior

Two API surfaces:

  pick_by_tag(tag, today=None) → Memo | None
    Picks one memo whose tags contain the requested tag AND whose
    available_from has passed. If multiple match, prefers ones with
    the `default` tag, then random.

  list_available(today=None) → list[Memo]
    All memos whose available_from has passed. For "Vesper, kya kya
    chhoda hai" listings.

  play(memo, ctx) → bool
    Resolves the file (relative to bank dir) and plays via
    core.audio_playback. Best-effort.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml

from core.audio_playback import play_file
from core.logger import get_logger

log = get_logger("voice_memos")


# ── Public types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Memo:
    file: str
    title: str
    tags: tuple[str, ...]
    available_from: Optional[date] = None  # None = always available


@dataclass
class MemoContext:
    """Runtime hooks supplied by the caller."""
    bank_dir: Optional[Path] = None
    """Resolves relative `file` paths. None = treat as absolute only."""


# ── Engine ──────────────────────────────────────────────────────────


class VoiceMemoLibrary:
    """
    Loads memos from a YAML bank and answers lookup queries.

    Thread-safe: reads return a snapshot; reload rebuilds atomically.
    """

    def __init__(self, bank_path: Path):
        self._bank_path = Path(bank_path)
        self._memos: list[Memo] = []
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> int:
        new = _load_bank(self._bank_path)
        with self._lock:
            self._memos = new
        log.info("voice_memos: %d memo(s) loaded from %s",
                 len(new), self._bank_path.name)
        return len(new)

    def list_available(self, today: Optional[date] = None) -> list[Memo]:
        today = today or date.today()
        with self._lock:
            return [m for m in self._memos if _is_available(m, today)]

    def list_all(self) -> list[Memo]:
        with self._lock:
            return list(self._memos)

    def pick_by_tag(self, tag: str, today: Optional[date] = None) -> Optional[Memo]:
        today = today or date.today()
        wanted = tag.lower().strip()
        with self._lock:
            pool = [m for m in self._memos
                    if _is_available(m, today)
                    and wanted in {t.lower() for t in m.tags}]
        if not pool:
            return None
        # Prefer memos tagged "default" within the pool.
        defaults = [m for m in pool if "default" in {t.lower() for t in m.tags}]
        if defaults:
            return random.choice(defaults)
        return random.choice(pool)

    def pick_default(self, today: Optional[date] = None) -> Optional[Memo]:
        """Pick the 'default' memo (or random if none tagged default)."""
        today = today or date.today()
        with self._lock:
            available = [m for m in self._memos if _is_available(m, today)]
        if not available:
            return None
        defaults = [m for m in available if "default" in {t.lower() for t in m.tags}]
        return random.choice(defaults) if defaults else random.choice(available)


# ── Playback ─────────────────────────────────────────────────────────


def play_memo(memo: Memo, ctx: MemoContext) -> bool:
    """Resolve the memo's file and play it. Returns True on success."""
    p = Path(memo.file)
    if not p.is_absolute() and ctx.bank_dir is not None:
        p = ctx.bank_dir / p
    if not p.is_file():
        log.warning("voice_memos: file missing: %s", p)
        return False
    return play_file(p, blocking=True)


# ── Helpers ─────────────────────────────────────────────────────────


def _is_available(memo: Memo, today: date) -> bool:
    if memo.available_from is None:
        return True
    return today >= memo.available_from


def _load_bank(path: Path) -> list[Memo]:
    if not path.is_file():
        log.warning("voice_memos: bank not found at %s", path)
        return []
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log.warning("voice_memos: YAML parse error in %s: %s", path, e)
        return []
    if not isinstance(data, dict):
        log.warning("voice_memos: top-level must be a mapping")
        return []
    raw_memos = data.get("memos") or []
    if not isinstance(raw_memos, list):
        return []
    memos: list[Memo] = []
    for i, raw in enumerate(raw_memos):
        try:
            m = _parse_memo(raw)
            if m is not None:
                memos.append(m)
        except Exception as e:
            log.warning("voice_memos: skip memo %d: %s", i, e)
    return memos


def _parse_memo(raw: Any) -> Optional[Memo]:
    if not isinstance(raw, dict):
        raise ValueError("memo must be a dict")
    file = raw.get("file")
    if not isinstance(file, str) or not file:
        raise ValueError("missing file")
    title = raw.get("title")
    if not isinstance(title, str):
        title = file
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    avail = raw.get("available_from")
    avail_date: Optional[date] = None
    if isinstance(avail, date):
        avail_date = avail
    elif isinstance(avail, str):
        try:
            avail_date = date.fromisoformat(avail)
        except ValueError:
            log.warning("voice_memos: invalid available_from %r — treating as always-available", avail)
    return Memo(
        file=file,
        title=title,
        tags=tuple(str(t) for t in tags),
        available_from=avail_date,
    )
