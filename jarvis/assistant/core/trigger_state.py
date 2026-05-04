"""
Trigger state — persistent record of which event packs have been
manually fired this year.

## Why this exists

For 2026, Astha's birthday pack triggers manually (cake-cutting at
midnight needs no tech competition). The dashboard's confetti + theme
flip only fire AFTER the trigger lands, not at 12:00 AM. That state
needs to survive an accidental Jetson restart on the day-of — without
this, restarting the service mid-day would silently roll back the
celebration to "not yet triggered" and the theme would revert.

## State shape

A small JSON file at `data/event_triggers.json`:

    {
      "astha-birthday": {
        "2026": "2026-05-14T22:18:33+05:30",
        "2027": "2027-05-14T19:42:01+05:30"
      },
      "diwali": {
        "2026": "2026-10-29T19:00:00+05:30"
      }
    }

Keyed by pack_id then by year (string ISO year). Value is the
ISO-8601 timestamp of the first trigger. Subsequent triggers in the
same year are no-ops (idempotent).

## Why year-keyed and not "have we ever triggered"

A pack can recur. Astha's birthday triggers once per year, not once
ever. Year keys make the "did we trigger THIS year's instance" query
trivial and avoid the Jan 1 problem (no need to reset state at year
rollover).

## Concurrency

A threading.Lock guards the in-memory cache. File reads/writes are
short and infrequent (once on read, once on trigger). Atomic writes
via tempfile + rename so a crash mid-write can't leave a corrupt
state file.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from core.logger import get_logger

log = get_logger("trigger_state")


# ── Defaults ────────────────────────────────────────────────────────

# State lives in the assistant's data dir alongside the SQLite memory
# DB. Module-relative so the path is the same on Mac and Jetson.
_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "event_triggers.json"
)


# ── Store ───────────────────────────────────────────────────────────


class TriggerStateStore:
    """
    Thread-safe load + persist for the trigger state JSON file.

    Usage:
        store = TriggerStateStore()
        if not store.is_triggered("astha-birthday"):
            ...   # show pre-launch state
        store.mark_triggered("astha-birthday")
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else _DEFAULT_PATH
        self._lock = threading.Lock()
        # Cache shape: {pack_id: {year_str: iso_timestamp}}
        self._cache: Dict[str, Dict[str, str]] = self._load()

    # ── Public API ─────────────────────────────────────────────

    def is_triggered(self, pack_id: str, year: Optional[int] = None) -> bool:
        """
        True if `pack_id` has been triggered for the given year (default:
        current year). Safe to call before/after construction.
        """
        if year is None:
            year = datetime.now().year
        with self._lock:
            packs = self._cache.get(pack_id, {})
            return str(year) in packs

    def mark_triggered(
        self, pack_id: str, year: Optional[int] = None,
        when: Optional[datetime] = None,
    ) -> bool:
        """
        Record `pack_id` as triggered for the given year. Idempotent —
        if already triggered for that year, this returns False without
        rewriting the file.

        Returns True on a fresh write, False on idempotent no-op.
        """
        if year is None:
            year = datetime.now().year
        if when is None:
            when = datetime.now().astimezone()

        with self._lock:
            packs = self._cache.setdefault(pack_id, {})
            year_str = str(year)
            if year_str in packs:
                return False
            packs[year_str] = when.isoformat()
            try:
                self._persist_locked()
            except Exception as e:
                # Don't let a disk error roll back the in-memory mark —
                # the user's trigger fired, the celebration must continue
                # even if persistence fails. Worst case: a restart loses
                # the state. Log it loudly so the user can investigate.
                log.error(
                    "trigger_state: persist failed for %s/%s: %s. "
                    "In-memory state is correct; a restart will lose it.",
                    pack_id, year_str, e,
                )
            return True

    def reset(self, pack_id: str, year: Optional[int] = None) -> bool:
        """
        Forget that a pack was triggered (testing aid; user-facing
        "reset to pre-launch" flow could use this too). Returns True
        if state changed.
        """
        if year is None:
            year = datetime.now().year
        with self._lock:
            packs = self._cache.get(pack_id, {})
            year_str = str(year)
            if year_str not in packs:
                return False
            del packs[year_str]
            if not packs:
                self._cache.pop(pack_id, None)
            try:
                self._persist_locked()
            except Exception as e:
                log.error("trigger_state: persist failed during reset: %s", e)
            return True

    def first_triggered_at(self, pack_id: str, year: Optional[int] = None
                           ) -> Optional[datetime]:
        """ISO-parsed timestamp of the first trigger, or None if not triggered."""
        if year is None:
            year = datetime.now().year
        with self._lock:
            iso = self._cache.get(pack_id, {}).get(str(year))
        if iso is None:
            return None
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None

    # ── Persistence ────────────────────────────────────────────

    def _load(self) -> Dict[str, Dict[str, str]]:
        if not self._path.is_file():
            return {}
        try:
            with self._path.open() as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            # Corrupt or missing — start fresh; preserve the bad file
            # for forensics by renaming it to .bad-<timestamp>.
            log.warning(
                "trigger_state: %s unreadable (%s) — starting fresh; "
                "old file preserved as %s.bad",
                self._path, e, self._path,
            )
            try:
                self._path.rename(
                    self._path.with_suffix(self._path.suffix + ".bad")
                )
            except Exception:
                pass
            return {}

        # Defensive: enforce the {pack_id: {year_str: timestamp_str}} shape.
        if not isinstance(data, dict):
            log.warning("trigger_state: top-level value is not a dict; ignoring")
            return {}
        cleaned: Dict[str, Dict[str, str]] = {}
        for pid, years in data.items():
            if isinstance(pid, str) and isinstance(years, dict):
                cleaned[pid] = {
                    str(y): str(t) for y, t in years.items()
                    if isinstance(y, (int, str)) and isinstance(t, str)
                }
        return cleaned

    def _persist_locked(self) -> None:
        """
        Atomic write: serialize, write to a temp file in the SAME
        directory as the target, fsync, rename. Caller must hold _lock.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # tempfile in same dir so rename() is atomic on POSIX.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".event_triggers.", suffix=".json.tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            # Best-effort cleanup of the temp file.
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise


# ── Module singleton ────────────────────────────────────────────────

_default: Optional[TriggerStateStore] = None
_default_lock = threading.Lock()


def get_trigger_store() -> TriggerStateStore:
    """Lazy singleton accessor."""
    global _default
    with _default_lock:
        if _default is None:
            _default = TriggerStateStore()
        return _default
