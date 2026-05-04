"""
Event Scheduler — background day-rollover watcher that auto-fires
event triggers on the day-of for packs with `trigger.auto_midnight: true`.

## What it does

Every `poll_interval_s` (default 60s), checks whether the system date
has rolled over since the last poll. On rollover, asks event_manager
whether today's date matches an active pack with auto_midnight=True
that has NOT already been triggered this year — if so, calls the
caller-supplied `on_trigger(active_event)` callback.

## Why polling, not absolute alarm

Two reasons:
  1. **System clock changes.** NTP corrections, manual `date -s` from
     a developer, sleep/wake cycles on laptops — an absolute
     "wake up at 00:00" alarm misfires when the clock jumps. Polling
     compares the *last seen date* against the *current date* and
     fires on transition — robust to any clock movement.
  2. **Service restart on event day.** If the assistant was running
     at 11:55 PM May 13, restarted at 11:58 PM May 13 (mid-deploy),
     and continues running through midnight — the scheduler must
     STILL fire at the rollover. Polling-with-baseline catches this;
     a "schedule absolute timer" approach loses the alarm at restart.

## Idempotency

The scheduler defers to `core.trigger_state.is_triggered()` before
firing — so a manual trigger earlier in the day, OR a previous
auto-fire that successfully recorded state, both prevent re-firing.

## Year-1 behavior

For 2026 (Astha's birthday), `pack.yaml → trigger.auto_midnight: false`
— so the scheduler observes the rollover, sees auto_midnight is off,
and does nothing. Manual trigger remains the only path. The scheduler
exists primarily for 2027+ when the user can opt in to auto-fire.

## Threading

Runs in a single daemon thread. Calling `start()` twice is a no-op
(returns early if already running). `stop()` is idempotent.

If `on_trigger` raises, the scheduler logs and keeps polling — a
buggy launch sequence shouldn't kill the watcher.
"""

from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Callable, Optional

from core.logger import get_logger

log = get_logger("event_scheduler")


class EventScheduler:
    """
    Background daemon thread that auto-fires event triggers at
    midnight rollover for packs with auto_midnight=True.

    Caller responsibilities:
      - Construct with an `on_trigger(active_event)` callback that
        actually runs the launch sequence (e.g., calls
        intent_handler._handle_event_trigger via a synthetic Intent,
        or directly invokes intro_runner).
      - Call `start()` once after the assistant is fully wired up.
      - Call `stop()` on shutdown.
    """

    def __init__(
        self,
        on_trigger: Callable[[object], None],
        poll_interval_s: int = 60,
    ):
        self._on_trigger = on_trigger
        self._poll_interval_s = poll_interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Date the scheduler last observed. Initialized lazily on first
        # tick so a same-day startup doesn't immediately re-fire.
        self._last_seen_date: Optional[date] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return  # already running
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, name="event-scheduler", daemon=True,
            )
            self._thread.start()
        log.info("event_scheduler: started (poll=%ds)", self._poll_interval_s)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self._poll_interval_s + 2.0)
        log.info("event_scheduler: stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Internal ────────────────────────────────────────────────

    def _loop(self) -> None:
        # Imports inside the loop to keep startup-order coupling loose.
        from core.event_manager import get_event_manager
        from core.trigger_state import get_trigger_store

        # Baseline: the date when the scheduler started. This prevents
        # a startup-on-event-day from auto-firing immediately
        # (the manual trigger or earlier auto-fire is the source of truth).
        self._last_seen_date = date.today()

        while not self._stop.wait(self._poll_interval_s):
            try:
                self._tick(get_event_manager(), get_trigger_store())
            except Exception as e:
                log.warning("event_scheduler tick failed: %s", e)

    def _tick(self, em, store) -> None:
        """One poll iteration. Extracted for testability."""
        today = date.today()
        if self._last_seen_date is None:
            self._last_seen_date = today
            return

        if today == self._last_seen_date:
            return  # no day rollover yet

        # Day rolled over. Update the baseline IMMEDIATELY so a slow
        # on_trigger callback doesn't cause us to re-evaluate the same
        # rollover on the next tick.
        prev = self._last_seen_date
        self._last_seen_date = today
        log.info("event_scheduler: day rollover %s → %s", prev, today)

        active = em.current(now=datetime.now())
        if active is None or not active.is_today:
            return

        # Per-pack opt-in: the trigger.auto_midnight flag in pack.yaml.
        pack_cfg = active.pack.trigger_config or {}
        if not pack_cfg.get("auto_midnight", False):
            log.info(
                "event_scheduler: pack %s is active today but auto_midnight is off — skipping",
                active.pack_id,
            )
            return

        # Don't double-fire if this pack was already triggered this year
        # (via manual phrase / app button / a prior auto-fire that we missed).
        if store.is_triggered(active.pack_id, year=today.year):
            log.info(
                "event_scheduler: pack %s already triggered for %d — skipping",
                active.pack_id, today.year,
            )
            return

        log.info("event_scheduler: AUTO-FIRING pack %s for %d",
                 active.pack_id, today.year)
        try:
            self._on_trigger(active)
        except Exception as e:
            log.error("event_scheduler: on_trigger failed: %s", e)
