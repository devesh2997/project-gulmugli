"""
Event Manager — single brain that knows whether today is a special day.

## What this module does

The assistant supports "event packs" — bundles of features, themes, and
media that auto-activate on certain dates. Astha's birthday (May 14) is
the canonical one; future packs include Diwali, Christmas, Devesh's
birthday, etc. Each pack lives in `events/<pack_id>/` and declares its
date rule in `pack.yaml`.

This module loads every pack at startup, computes which one (if any) is
"active" for today, and exposes a small read-only API so the rest of the
codebase doesn't have to know how date rules work.

The dashboard's `useEventTheme` hook polls `/api/events/current` and
flips the UI palette when an event is active. The intent classifier's
`event_trigger` handler reads from this module to fire the launch
sequence. Future packs slot in by dropping a directory into `events/`.

## Date rules supported

Each `pack.yaml` declares a `date_rule:` block with one of:

  - `recurs: yearly` + `month: M` + `day: D`
        Astha's birthday: every May 14, forever.

  - `one_time: YYYY-MM-DD`
        A specific date once. Useful for event packs tied to a milestone
        year (e.g., a one-time anniversary surprise).

  - `range_start: YYYY-MM-DD` + `range_days: N`
        N consecutive days starting from the given date. Renews per year
        if `recurs: yearly` is also set; otherwise one-time.

Lunar-calendar packs (Diwali, Eid) are deferred — they need a year-by-year
lookup table; not in scope for the May 14 launch.

## Eve / aftermath windows

Each `ActiveEvent` exposes `is_eve` (day before) and `is_aftermath` (day
after) flags so packs can ramp up / wind down their UI without sharp
edges. By default these are 1-day windows; a pack can override with
`eve_days:` and `aftermath_days:` in pack.yaml.

## Why this is config-driven, not hard-coded

Adding the next event pack (Diwali, your birthday, anniversary) should be
a directory drop, not a code change. Every assumption that varies between
packs lives in `pack.yaml`; this module's job is purely to interpret
those assumptions.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from core.logger import get_logger

log = get_logger("event_manager")


# ── Defaults ──────────────────────────────────────────────────────────

# `events/` directory — found relative to assistant root (this module is
# in core/, so events/ is at ../events/).
_DEFAULT_EVENTS_DIR = Path(__file__).resolve().parent.parent / "events"

# How wide the eve / aftermath windows are by default. A pack can override
# in its pack.yaml.
_DEFAULT_EVE_DAYS = 1
_DEFAULT_AFTERMATH_DAYS = 1


# ── Public types ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Pack:
    """
    A loaded event pack. Immutable — the manager rebuilds these on
    `reload()`, never mutates in place.
    """
    pack_id: str
    display_name: str
    pack_dir: Path
    date_rule: dict        # raw dict from pack.yaml; interpreted in `_match`
    eve_days: int
    aftermath_days: int
    raw: dict              # full pack.yaml contents — features list,
                           # trigger config, etc., consumed by other modules

    @property
    def features(self) -> list[str]:
        """Feature names this pack enables. Empty list if absent."""
        f = self.raw.get("features")
        return f if isinstance(f, list) else []

    @property
    def trigger_config(self) -> dict:
        """The `trigger:` block from pack.yaml. Empty dict if absent."""
        t = self.raw.get("trigger")
        return t if isinstance(t, dict) else {}


@dataclass(frozen=True)
class ActiveEvent:
    """
    The result of `EventManager.current()` when something matches today.

    `days_until` is non-negative inside the eve window, zero on the day
    itself, negative inside the aftermath window. Use `is_today` to gate
    "show theme now" logic; use `is_eve` / `is_aftermath` to ramp up /
    wind down softly.
    """
    pack_id: str
    pack_dir: Path
    days_until: int
    is_today: bool
    is_eve: bool
    is_aftermath: bool
    pack: Pack = field(repr=False)


# ── EventManager ──────────────────────────────────────────────────────

class EventManager:
    """
    Loads packs from disk and answers "what's happening today?" queries.

    Thread-safe for the read path (`current`, `list_packs`). `reload`
    locks the underlying list while it rebuilds.
    """

    def __init__(self, events_dir: Optional[Path] = None):
        self._events_dir = Path(events_dir) if events_dir else _DEFAULT_EVENTS_DIR
        self._packs: list[Pack] = []
        self._lock = threading.Lock()
        self.reload()

    # ── Public API ──────────────────────────────────────────────────

    def reload(self) -> None:
        """
        Rescan the events directory and rebuild the in-memory pack list.

        Called once at construction; can be called again to pick up
        newly-dropped packs without restarting the assistant. Failures
        on individual packs are logged and skipped — one bad pack does
        not break the rest.
        """
        new_packs: list[Pack] = []

        if not self._events_dir.is_dir():
            log.info("No events directory at %s — event system inactive.",
                     self._events_dir)
            with self._lock:
                self._packs = []
            return

        for child in sorted(self._events_dir.iterdir()):
            if not child.is_dir():
                continue
            pack_yaml = child / "pack.yaml"
            if not pack_yaml.is_file():
                # Not every directory under events/ is a pack — skip silently.
                continue
            try:
                pack = _load_pack(child, pack_yaml)
                new_packs.append(pack)
            except Exception as e:
                # Don't let one broken pack take down the whole system.
                log.warning("Skipping pack at %s: %s", child, e)

        with self._lock:
            self._packs = new_packs

        log.info("Loaded %d event pack(s): %s",
                 len(new_packs),
                 [p.pack_id for p in new_packs])

    def list_packs(self) -> list[Pack]:
        """Read-only snapshot of all loaded packs."""
        with self._lock:
            return list(self._packs)

    def current(self, now: Optional[datetime] = None) -> Optional[ActiveEvent]:
        """
        Compute the active event for `now` (default: real time).

        Returns:
            ActiveEvent if any pack's date rule matches today (or the
            eve / aftermath window). Otherwise None.

        If multiple packs match the same day (e.g., overlapping ranges),
        the first by pack_id (alphabetical) wins. We log a warning when
        this happens so the user can adjust their date rules.
        """
        ref = (now or datetime.now()).date()
        with self._lock:
            packs = list(self._packs)

        matches: list[tuple[Pack, int, bool, bool, bool]] = []
        for pack in packs:
            m = _match(pack, ref)
            if m is not None:
                days_until, is_today, is_eve, is_aftermath = m
                matches.append((pack, days_until, is_today, is_eve, is_aftermath))

        if not matches:
            return None

        if len(matches) > 1:
            log.warning(
                "Multiple event packs match %s: %s. Using first (alphabetical) "
                "by pack_id.",
                ref.isoformat(),
                [m[0].pack_id for m in matches],
            )
            matches.sort(key=lambda m: m[0].pack_id)

        pack, days_until, is_today, is_eve, is_aftermath = matches[0]
        return ActiveEvent(
            pack_id=pack.pack_id,
            pack_dir=pack.pack_dir,
            days_until=days_until,
            is_today=is_today,
            is_eve=is_eve,
            is_aftermath=is_aftermath,
            pack=pack,
        )


# ── Loading helpers ──────────────────────────────────────────────────

def _load_pack(pack_dir: Path, pack_yaml: Path) -> Pack:
    """
    Parse a single pack.yaml. Raises on schema problems — caller is
    responsible for catching and logging.
    """
    with pack_yaml.open() as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"pack.yaml must be a mapping at top level, got {type(raw).__name__}")

    pack_id = raw.get("id")
    if not pack_id or not isinstance(pack_id, str):
        raise ValueError("pack.yaml missing required field 'id' (string)")

    if pack_id != pack_dir.name:
        # Soft mismatch — warn but don't reject. Could be intentional during
        # a rename. Use the directory name as the canonical id since that's
        # what the filesystem uses.
        log.warning(
            "Pack at %s declares id=%r but directory is %r. Using directory name.",
            pack_dir, pack_id, pack_dir.name,
        )
        pack_id = pack_dir.name

    date_rule = raw.get("date_rule")
    if not isinstance(date_rule, dict):
        raise ValueError(f"pack {pack_id}: missing or invalid 'date_rule' block")

    return Pack(
        pack_id=pack_id,
        display_name=raw.get("display_name", pack_id),
        pack_dir=pack_dir,
        date_rule=date_rule,
        eve_days=int(raw.get("eve_days", _DEFAULT_EVE_DAYS)),
        aftermath_days=int(raw.get("aftermath_days", _DEFAULT_AFTERMATH_DAYS)),
        raw=raw,
    )


# ── Date-rule matching ────────────────────────────────────────────────

def _match(pack: Pack, ref: date) -> Optional[tuple[int, bool, bool, bool]]:
    """
    Decide whether `ref` falls inside this pack's window.

    Returns (days_until, is_today, is_eve, is_aftermath) on a match, or
    None on miss.

    `days_until` is positive in the eve window, zero on the day itself,
    negative in the aftermath window — so it's always the signed
    difference (target_date - ref).

    For range rules, "the day itself" is treated as the entire range:
    is_today=True any day inside [start, start+days-1], days_until is
    measured against the start of the range.
    """
    rule = pack.date_rule
    eve = pack.eve_days
    aftermath = pack.aftermath_days

    # ── Recurring yearly (single day) ─────────────────────────────────
    if rule.get("recurs") == "yearly" and "month" in rule and "day" in rule:
        return _match_yearly_single(int(rule["month"]), int(rule["day"]),
                                    ref, eve, aftermath)

    # ── One-time single date ──────────────────────────────────────────
    if "one_time" in rule:
        target = _parse_iso_date(rule["one_time"])
        if target is None:
            log.warning("pack %s: invalid one_time date %r", pack.pack_id,
                        rule["one_time"])
            return None
        return _match_single_date(target, ref, eve, aftermath)

    # ── Range (recurring or one-time) ─────────────────────────────────
    if "range_start" in rule and "range_days" in rule:
        start = _parse_iso_date(rule["range_start"])
        days = int(rule["range_days"])
        if start is None or days <= 0:
            log.warning("pack %s: invalid range rule", pack.pack_id)
            return None
        is_yearly = rule.get("recurs") == "yearly"
        return _match_range(start, days, is_yearly, ref, eve, aftermath)

    log.warning("pack %s: date_rule did not match any known rule type: %r",
                pack.pack_id, rule)
    return None


def _match_yearly_single(month: int, day: int, ref: date,
                         eve: int, aftermath: int
                         ) -> Optional[tuple[int, bool, bool, bool]]:
    """
    Yearly recurring single-date rule. Picks the closest occurrence —
    last year's, this year's, or next year's, whichever the ref falls
    nearest to inside the [-aftermath, +eve] window.
    """
    candidates = []
    for year_offset in (-1, 0, 1):
        target = _safe_date(ref.year + year_offset, month, day)
        if target is None:
            continue
        m = _match_single_date(target, ref, eve, aftermath)
        if m is not None:
            candidates.append(m)

    if not candidates:
        return None

    # Prefer the one with the smallest absolute days-from-target.
    return min(candidates, key=lambda c: abs(c[0]))


def _match_single_date(target: date, ref: date, eve: int, aftermath: int
                       ) -> Optional[tuple[int, bool, bool, bool]]:
    """One-time single-date matcher. Same logic for both rule types."""
    days_until = (target - ref).days
    if -aftermath <= days_until <= eve:
        return (
            days_until,
            days_until == 0,
            0 < days_until <= eve,
            -aftermath <= days_until < 0,
        )
    return None


def _match_range(start: date, days: int, is_yearly: bool, ref: date,
                 eve: int, aftermath: int
                 ) -> Optional[tuple[int, bool, bool, bool]]:
    """
    Range-rule matcher. The whole [start, start+days-1] window counts as
    is_today=True so that themes stay on for the full festival period.
    """
    candidates_start_dates = [start]
    if is_yearly:
        for year_offset in (-1, 1):
            shifted = _safe_date(start.year + year_offset, start.month, start.day)
            if shifted is not None:
                candidates_start_dates.append(shifted)

    for s in candidates_start_dates:
        end = s + timedelta(days=days - 1)
        # Inside the range proper.
        if s <= ref <= end:
            days_until = (s - ref).days   # always <= 0 for this branch
            return (days_until, True, False, False)
        # Eve window: ref is before s, within `eve` days.
        days_until = (s - ref).days
        if 0 < days_until <= eve:
            return (days_until, False, True, False)
        # Aftermath window: ref is after `end`, within `aftermath` days.
        days_after_end = (ref - end).days
        if 0 < days_after_end <= aftermath:
            return (-(days_after_end), False, False, True)

    return None


# ── Tiny date utils ───────────────────────────────────────────────────

def _parse_iso_date(value) -> Optional[date]:
    """Accept either a `date` (PyYAML auto-parses ISO dates) or a string."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    """Return date(year, month, day) or None for invalid combos (Feb 29)."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ── Module singleton ─────────────────────────────────────────────────

# Lazy singleton — created on first access so tests can construct their
# own EventManager pointing at a temp directory without this one loading
# the real `events/` tree at import time.
_default: Optional[EventManager] = None
_default_lock = threading.Lock()


def get_event_manager() -> EventManager:
    """Lazy singleton accessor for the default events/ directory."""
    global _default
    with _default_lock:
        if _default is None:
            _default = EventManager()
        return _default
