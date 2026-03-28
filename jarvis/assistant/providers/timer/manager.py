"""
Timer and alarm manager — background scheduling with persistent alarms.

Timers are ephemeral (lost on restart). Alarms persist to JSON and survive restarts.
A background thread checks every second for expired timers/alarms and fires callbacks.

Usage:
    manager = TimerManager(on_fire=my_callback)
    manager.start()

    manager.set_timer(300, label="Pasta")        # 5-minute timer
    manager.set_alarm("07:00", label="Wake up", repeat="daily")
    manager.snooze(alarm_id, minutes=5)
    manager.cancel(timer_id)
    manager.list_active()
"""

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from core.logger import get_logger

log = get_logger("timer.manager")


# ── Data structures ───────────────────────────────────────────

class TimerEntry:
    """A single timer or alarm entry."""

    def __init__(
        self,
        entry_type: str,  # "timer" or "alarm"
        target_time: float,  # unix timestamp when it fires
        label: str = "",
        repeat: str = "none",  # "none", "daily", "weekdays"
        entry_id: str = "",
        active: bool = True,
        original_time_str: str = "",  # for alarms: "07:00" — used for rescheduling
    ):
        self.id = entry_id or str(uuid.uuid4())[:8]
        self.type = entry_type
        self.target_time = target_time
        self.label = label
        self.repeat = repeat
        self.active = active
        self.original_time_str = original_time_str
        self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "target_time": self.target_time,
            "label": self.label,
            "repeat": self.repeat,
            "active": self.active,
            "original_time_str": self.original_time_str,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimerEntry":
        entry = cls(
            entry_type=d["type"],
            target_time=d["target_time"],
            label=d.get("label", ""),
            repeat=d.get("repeat", "none"),
            entry_id=d["id"],
            active=d.get("active", True),
            original_time_str=d.get("original_time_str", ""),
        )
        entry.created_at = d.get("created_at", time.time())
        return entry

    @property
    def remaining_seconds(self) -> float:
        return max(0, self.target_time - time.time())

    @property
    def is_expired(self) -> bool:
        return self.active and time.time() >= self.target_time

    def __repr__(self) -> str:
        dt = datetime.fromtimestamp(self.target_time).strftime("%H:%M:%S")
        return f"<{self.type} id={self.id} label={self.label!r} at={dt} active={self.active}>"


# ── Timer Manager ──────────────────────────────────────────────

class TimerManager:
    """
    Manages timers and alarms with a background tick thread.

    Args:
        on_fire: Callback when a timer/alarm fires. Receives the TimerEntry.
        data_dir: Directory for persisting alarms.json. Defaults to assistant/data/.
    """

    def __init__(
        self,
        on_fire: Optional[Callable[[TimerEntry], None]] = None,
        data_dir: Optional[Path] = None,
    ):
        self._entries: dict[str, TimerEntry] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_fire = on_fire

        # Persistence path
        self._data_dir = data_dir or (Path(__file__).parent.parent.parent / "data")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._alarms_file = self._data_dir / "alarms.json"

        # Load persisted alarms
        self._load_alarms()

    def start(self) -> None:
        """Start the background tick thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._tick_loop,
            name="timer-manager",
            daemon=True,
        )
        self._thread.start()
        log.info("TimerManager started. %d alarms loaded.", self._count_alarms())

    def stop(self) -> None:
        """Stop the background tick thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        log.info("TimerManager stopped.")

    # ── Public API ──────────────────────────────────────────────

    def set_timer(self, duration_seconds: int, label: str = "") -> TimerEntry:
        """
        Set a countdown timer.

        Args:
            duration_seconds: How many seconds until the timer fires.
            label: Optional label ("Pasta", "Eggs", etc.)

        Returns:
            The created TimerEntry.
        """
        target = time.time() + duration_seconds
        entry = TimerEntry(
            entry_type="timer",
            target_time=target,
            label=label or "Timer",
        )

        with self._lock:
            self._entries[entry.id] = entry

        log.info("Timer set: %s (%ds, fires at %s)",
                 entry.label, duration_seconds,
                 datetime.fromtimestamp(target).strftime("%H:%M:%S"))
        return entry

    def set_alarm(
        self,
        time_str: str,
        label: str = "",
        repeat: str = "none",
    ) -> TimerEntry:
        """
        Set an alarm for a specific time.

        Args:
            time_str: Time in HH:MM format (24h). If the time has passed today,
                      schedules for tomorrow.
            label: Optional label ("Wake up", "Medicine", etc.)
            repeat: "none" (one-time), "daily", or "weekdays" (Mon-Fri).

        Returns:
            The created TimerEntry.
        """
        target = self._parse_alarm_time(time_str)
        entry = TimerEntry(
            entry_type="alarm",
            target_time=target,
            label=label or "Alarm",
            repeat=repeat,
            original_time_str=time_str,
        )

        with self._lock:
            self._entries[entry.id] = entry
            self._save_alarms()

        log.info("Alarm set: %s at %s (repeat=%s)",
                 entry.label, time_str, repeat)
        return entry

    def cancel(self, entry_id: str) -> Optional[TimerEntry]:
        """
        Cancel a timer or alarm by ID.

        Also accepts partial ID matches and type-based cancellation:
        - "timer" cancels the most recent active timer
        - "alarm" cancels the most recent active alarm

        Returns the cancelled entry, or None if not found.
        """
        with self._lock:
            # Direct ID match
            if entry_id in self._entries:
                entry = self._entries.pop(entry_id)
                entry.active = False
                self._save_alarms()
                log.info("Cancelled: %s", entry)
                return entry

            # Partial ID match
            for eid, entry in list(self._entries.items()):
                if eid.startswith(entry_id) and entry.active:
                    removed = self._entries.pop(eid)
                    removed.active = False
                    self._save_alarms()
                    log.info("Cancelled (partial match): %s", removed)
                    return removed

            # Type-based: "timer" or "alarm" cancels the most recent of that type
            if entry_id in ("timer", "alarm"):
                candidates = [
                    e for e in self._entries.values()
                    if e.type == entry_id and e.active
                ]
                if candidates:
                    # Cancel the one firing soonest
                    target = min(candidates, key=lambda e: e.target_time)
                    removed = self._entries.pop(target.id)
                    removed.active = False
                    self._save_alarms()
                    log.info("Cancelled most recent %s: %s", entry_id, removed)
                    return removed

        log.warning("Cancel failed: no entry matching '%s'", entry_id)
        return None

    def snooze(self, entry_id: str, minutes: int = 5) -> Optional[TimerEntry]:
        """
        Snooze an alarm by pushing its target time forward.

        Args:
            entry_id: The alarm ID to snooze. Also accepts "alarm" to snooze
                      the most recently fired/upcoming alarm.
            minutes: How many minutes to snooze (default 5).

        Returns:
            The snoozed entry, or None if not found.
        """
        with self._lock:
            entry = self._entries.get(entry_id)

            # Fall back to type-based match
            if not entry and entry_id == "alarm":
                alarms = [
                    e for e in self._entries.values()
                    if e.type == "alarm"
                ]
                if alarms:
                    entry = min(alarms, key=lambda e: abs(e.target_time - time.time()))

            if not entry:
                log.warning("Snooze failed: no entry matching '%s'", entry_id)
                return None

            entry.target_time = time.time() + (minutes * 60)
            entry.active = True
            self._save_alarms()

        log.info("Snoozed %s for %d minutes", entry.label, minutes)
        return entry

    def list_active(self) -> list[dict]:
        """Return all active timers and alarms as dicts."""
        with self._lock:
            return [
                {**e.to_dict(), "remaining_seconds": e.remaining_seconds}
                for e in self._entries.values()
                if e.active
            ]

    def get_entry(self, entry_id: str) -> Optional[TimerEntry]:
        """Get a specific entry by ID."""
        return self._entries.get(entry_id)

    # ── Background tick loop ────────────────────────────────────

    def _tick_loop(self) -> None:
        """Runs every second, checks for expired timers/alarms."""
        while self._running:
            try:
                self._check_expired()
            except Exception as e:
                log.error("Timer tick error: %s", e)
            time.sleep(1.0)

    def _check_expired(self) -> None:
        """Check all entries and fire any that have expired."""
        fired = []
        with self._lock:
            for entry in list(self._entries.values()):
                if entry.is_expired:
                    fired.append(entry)
                    entry.active = False

                    # Handle repeating alarms
                    if entry.type == "alarm" and entry.repeat != "none":
                        next_entry = self._reschedule_alarm(entry)
                        if next_entry:
                            self._entries[next_entry.id] = next_entry

                    # Remove one-time entries
                    if entry.type == "timer" or entry.repeat == "none":
                        del self._entries[entry.id]

            if fired:
                self._save_alarms()

        # Fire callbacks outside the lock to avoid deadlocks
        for entry in fired:
            log.info("FIRED: %s", entry)
            if self._on_fire:
                try:
                    self._on_fire(entry)
                except Exception as e:
                    log.error("Timer fire callback error: %s", e)

    def _reschedule_alarm(self, entry: TimerEntry) -> Optional[TimerEntry]:
        """Create the next occurrence of a repeating alarm."""
        if not entry.original_time_str:
            return None

        now = datetime.now()
        hour, minute = map(int, entry.original_time_str.split(":"))

        if entry.repeat == "daily":
            # Next day at the same time
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            next_dt += timedelta(days=1)
        elif entry.repeat == "weekdays":
            # Next weekday at the same time
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            next_dt += timedelta(days=1)
            # Skip to Monday if it's Friday/Saturday
            while next_dt.weekday() >= 5:  # 5=Saturday, 6=Sunday
                next_dt += timedelta(days=1)
        else:
            return None

        new_entry = TimerEntry(
            entry_type="alarm",
            target_time=next_dt.timestamp(),
            label=entry.label,
            repeat=entry.repeat,
            original_time_str=entry.original_time_str,
        )
        log.info("Rescheduled alarm: %s → %s", entry.label, next_dt.strftime("%Y-%m-%d %H:%M"))
        return new_entry

    # ── Alarm time parsing ──────────────────────────────────────

    @staticmethod
    def _parse_alarm_time(time_str: str) -> float:
        """
        Parse HH:MM to a unix timestamp. If the time has already passed today,
        schedule for tomorrow.
        """
        now = datetime.now()
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.timestamp()

    # ── Persistence ─────────────────────────────────────────────

    def _save_alarms(self) -> None:
        """Persist alarms (not timers) to JSON. Must be called under self._lock."""
        alarms = [
            e.to_dict() for e in self._entries.values()
            if e.type == "alarm"
        ]
        try:
            self._alarms_file.write_text(json.dumps(alarms, indent=2))
        except Exception as e:
            log.error("Failed to save alarms: %s", e)

    def _load_alarms(self) -> None:
        """Load persisted alarms from JSON."""
        if not self._alarms_file.exists():
            return
        try:
            data = json.loads(self._alarms_file.read_text())
            now = time.time()
            for d in data:
                entry = TimerEntry.from_dict(d)
                # Skip expired one-time alarms
                if entry.repeat == "none" and entry.target_time < now:
                    continue
                # Reschedule expired repeating alarms
                if entry.target_time < now and entry.repeat != "none":
                    rescheduled = self._reschedule_alarm(entry)
                    if rescheduled:
                        self._entries[rescheduled.id] = rescheduled
                    continue
                self._entries[entry.id] = entry
            log.debug("Loaded %d alarms from %s", len(self._entries), self._alarms_file)
        except Exception as e:
            log.warning("Failed to load alarms: %s", e)

    def _count_alarms(self) -> int:
        return sum(1 for e in self._entries.values() if e.type == "alarm")
