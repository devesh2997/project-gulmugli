"""
Audio override store — persistent user pin for output/input device.

## Why this exists

The dashboard exposes a "switch audio device" UI. When the user picks a
specific output (e.g., "force Marshall Willen II") or input (e.g.,
"always use the USB mic"), that choice must survive process restarts.
Without persistence, every Jetson restart would silently drop the pin
back to the priority-list default, which is confusing in practice —
"why did my speaker keep flipping back?".

This store mirrors `core/trigger_state.py`: a tiny JSON-backed cache,
thread-safe, atomic writes via tempfile + rename, tolerant of corrupt
files (warn + treat as empty).

## State shape

A small JSON file at `data/audio_override.json`:

    {
      "output": "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink",
      "input": null,
      "updated_at": "2026-05-11T22:45:00Z"
    }

`output` and `input` are PulseAudio sink/source names. `null` means
"no override on this side — fall through to the priority list".

## Why this isn't part of config.yaml

Config is hand-edited; this is dashboard-edited. We don't want the
user's runtime pin to commute back into the example config (which gets
committed to git and copied to new machines). Keeping the override in
a separate runtime-state file keeps the two concerns clean.

## Concurrency

A threading.Lock guards the in-memory cache. File reads/writes are
short and infrequent (once on read, once on user click). Atomic writes
via tempfile + rename so a crash mid-write can't leave a corrupt state
file.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger("audio_override")


# ── Defaults ────────────────────────────────────────────────────────

# State lives in the assistant's data dir alongside event_triggers.json
# and the SQLite memory DB. Module-relative so the path is the same on
# Mac and Jetson.
_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "audio_override.json"
)


# ── Store ───────────────────────────────────────────────────────────


class AudioOverrideStore:
    """
    Thread-safe load + persist for the audio override JSON file.

    Usage:
        store = AudioOverrideStore()
        current = store.get()                  # {"output": ..., "input": ...}
        store.set_output("bluez_sink.AA...")   # pin output
        store.set_input(None)                  # clear input pin
        store.clear_all()                      # forget both pins
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else _DEFAULT_PATH
        self._lock = threading.Lock()
        self._cache: dict = self._load()

    # ── Public API ──────────────────────────────────────────────

    def get(self) -> dict:
        """
        Snapshot of the current override. Always returns a dict with
        both `output` and `input` keys (either may be None).
        """
        with self._lock:
            return {
                "output": self._cache.get("output"),
                "input": self._cache.get("input"),
            }

    def set_output(self, device_name: Optional[str]) -> None:
        """Pin the output device by PA sink name. None clears the pin."""
        self._set("output", device_name)

    def set_input(self, device_name: Optional[str]) -> None:
        """Pin the input device by PA source name. None clears the pin."""
        self._set("input", device_name)

    def clear_all(self) -> None:
        """Forget both output and input overrides."""
        with self._lock:
            self._cache["output"] = None
            self._cache["input"] = None
            self._cache["updated_at"] = _now_iso()
            try:
                self._persist_locked()
            except Exception as e:
                log.error("audio_override: persist failed during clear_all: %s", e)

    # ── Internal ────────────────────────────────────────────────

    def _set(self, side: str, value: Optional[str]) -> None:
        """Shared setter for output/input. None clears that side."""
        # Empty string is treated as None (defensive — dashboards
        # sometimes send "" for "no value").
        if value is not None and not str(value).strip():
            value = None
        with self._lock:
            self._cache[side] = value
            self._cache["updated_at"] = _now_iso()
            try:
                self._persist_locked()
            except Exception as e:
                log.error(
                    "audio_override: persist failed for %s=%r: %s. "
                    "In-memory state is correct; a restart will lose it.",
                    side, value, e,
                )

    # ── Persistence ─────────────────────────────────────────────

    def _load(self) -> dict:
        if not self._path.is_file():
            return {"output": None, "input": None, "updated_at": None}
        try:
            with self._path.open() as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            # Corrupt or unreadable — warn loudly and start fresh.
            # Preserve the bad file by renaming it for forensics.
            log.warning(
                "audio_override: %s unreadable (%s) — starting fresh; "
                "old file preserved as %s.bad",
                self._path, e, self._path,
            )
            try:
                self._path.rename(
                    self._path.with_suffix(self._path.suffix + ".bad")
                )
            except Exception:
                pass
            return {"output": None, "input": None, "updated_at": None}

        if not isinstance(data, dict):
            log.warning(
                "audio_override: top-level value is not a dict; ignoring"
            )
            return {"output": None, "input": None, "updated_at": None}

        # Defensive shape enforcement — accept str|None for output/input,
        # everything else becomes None.
        def _clean(v):
            if v is None:
                return None
            if isinstance(v, str) and v.strip():
                return v
            return None

        return {
            "output": _clean(data.get("output")),
            "input": _clean(data.get("input")),
            "updated_at": data.get("updated_at"),
        }

    def _persist_locked(self) -> None:
        """
        Atomic write: serialize, write to a temp file in the SAME
        directory as the target, fsync, rename. Caller must hold _lock.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # tempfile in same dir so rename() is atomic on POSIX.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".audio_override.", suffix=".json.tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise


def _now_iso() -> str:
    """UTC ISO-8601 with Z suffix — same shape used by trigger_state."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Module singleton ────────────────────────────────────────────────

_default: Optional[AudioOverrideStore] = None
_default_lock = threading.Lock()


def get_audio_override_store() -> AudioOverrideStore:
    """Lazy singleton accessor."""
    global _default
    with _default_lock:
        if _default is None:
            _default = AudioOverrideStore()
        return _default
