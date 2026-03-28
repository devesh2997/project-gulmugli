"""
Reminder manager — persistent reminders with background checking.

Stores reminders as JSON in data/reminders.json. A background thread
checks every 30 seconds for due reminders and fires a callback when
one triggers. Supports one-shot and repeating (daily/weekly/monthly)
reminders.

Usage:
    manager = ReminderManager(on_fire=my_callback)
    manager.start()
    manager.add("Call mom", remind_at=datetime(...))
    manager.add("Take medicine", remind_at=datetime(...), repeat="daily")
"""

import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from core.logger import get_logger

log = get_logger("reminder.manager")

# ── Storage path ──────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_REMINDERS_FILE = _DATA_DIR / "reminders.json"


def _now() -> datetime:
    """Current local time, truncated to seconds."""
    return datetime.now().replace(microsecond=0)


class ReminderManager:
    """
    Persistent reminder system with background checking.

    Args:
        on_fire: Callback invoked when a reminder is due.
                 Signature: on_fire(reminder_dict) where reminder_dict has
                 id, text, remind_at, repeat, created_at, active.
    """

    def __init__(self, on_fire: Optional[Callable] = None):
        self._on_fire = on_fire
        self._reminders: list[dict] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Ensure data directory exists
        _DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load persisted reminders
        self._load()

    # ── Public API ────────────────────────────────────────────────

    def add(self, text: str, remind_at: datetime,
            repeat: str = "none") -> dict:
        """
        Add a new reminder.

        Args:
            text: What to remind about ("call mom", "take medicine")
            remind_at: When to fire the reminder (local datetime)
            repeat: "none", "daily", "weekly", "monthly"

        Returns:
            The created reminder dict.
        """
        reminder = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "remind_at": remind_at.isoformat(),
            "repeat": repeat if repeat in ("none", "daily", "weekly", "monthly") else "none",
            "created_at": _now().isoformat(),
            "active": True,
        }
        with self._lock:
            self._reminders.append(reminder)
            self._save()
        log.info("Reminder added: '%s' at %s (repeat=%s, id=%s)",
                 text, remind_at.strftime("%Y-%m-%d %H:%M"), repeat, reminder["id"])
        return reminder

    def cancel(self, reminder_id: str) -> bool:
        """
        Cancel (deactivate) a reminder by its ID.

        Returns True if found and cancelled, False if not found.
        """
        with self._lock:
            for r in self._reminders:
                if r["id"] == reminder_id and r["active"]:
                    r["active"] = False
                    self._save()
                    log.info("Reminder cancelled: %s ('%s')", reminder_id, r["text"])
                    return True
        return False

    def snooze(self, reminder_id: str, minutes: int = 15) -> Optional[dict]:
        """
        Snooze a reminder by pushing its remind_at forward.

        Returns the updated reminder dict, or None if not found.
        """
        with self._lock:
            for r in self._reminders:
                if r["id"] == reminder_id:
                    new_time = _now() + timedelta(minutes=minutes)
                    r["remind_at"] = new_time.isoformat()
                    r["active"] = True
                    self._save()
                    log.info("Reminder snoozed: %s → %s (+%dmin)",
                             reminder_id, new_time.strftime("%H:%M"), minutes)
                    return dict(r)
        return None

    def list_active(self) -> list[dict]:
        """Return all active reminders, sorted by remind_at."""
        with self._lock:
            active = [dict(r) for r in self._reminders if r["active"]]
        active.sort(key=lambda r: r["remind_at"])
        return active

    def list_upcoming(self, hours: int = 24) -> list[dict]:
        """Return active reminders due within the next N hours."""
        cutoff = (_now() + timedelta(hours=hours)).isoformat()
        return [r for r in self.list_active() if r["remind_at"] <= cutoff]

    def cancel_by_text(self, search_text: str) -> Optional[dict]:
        """
        Cancel the first active reminder whose text contains search_text.

        Case-insensitive partial match. Returns the cancelled reminder or None.
        """
        search_lower = search_text.lower()
        with self._lock:
            for r in self._reminders:
                if r["active"] and search_lower in r["text"].lower():
                    r["active"] = False
                    self._save()
                    log.info("Reminder cancelled by text match: '%s' (id=%s)", r["text"], r["id"])
                    return dict(r)
        return None

    # ── Background checker ────────────────────────────────────────

    def start(self) -> None:
        """Start the background reminder checker thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._checker_loop,
            name="reminder-checker",
            daemon=True,
        )
        self._thread.start()
        log.info("Reminder checker started (%d active reminders).",
                 len(self.list_active()))

    def stop(self) -> None:
        """Stop the background checker."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        log.info("Reminder checker stopped.")

    def _checker_loop(self) -> None:
        """Check for due reminders every 30 seconds."""
        while not self._stop_event.is_set():
            try:
                self._check_due()
            except Exception as e:
                log.error("Reminder checker error: %s", e)
            self._stop_event.wait(30)

    def _check_due(self) -> None:
        """Fire any reminders that are past due."""
        now = _now()
        now_iso = now.isoformat()

        with self._lock:
            fired = []
            for r in self._reminders:
                if not r["active"]:
                    continue
                if r["remind_at"] <= now_iso:
                    fired.append(r)

            for r in fired:
                log.info("Reminder fired: '%s' (id=%s)", r["text"], r["id"])

                # Handle repeat
                if r["repeat"] == "none":
                    r["active"] = False
                elif r["repeat"] == "daily":
                    next_time = datetime.fromisoformat(r["remind_at"]) + timedelta(days=1)
                    r["remind_at"] = next_time.isoformat()
                elif r["repeat"] == "weekly":
                    next_time = datetime.fromisoformat(r["remind_at"]) + timedelta(weeks=1)
                    r["remind_at"] = next_time.isoformat()
                elif r["repeat"] == "monthly":
                    dt = datetime.fromisoformat(r["remind_at"])
                    month = dt.month + 1
                    year = dt.year
                    if month > 12:
                        month = 1
                        year += 1
                    # Clamp day to valid range for the new month
                    import calendar
                    max_day = calendar.monthrange(year, month)[1]
                    day = min(dt.day, max_day)
                    next_time = dt.replace(year=year, month=month, day=day)
                    r["remind_at"] = next_time.isoformat()

            if fired:
                self._save()

        # Fire callbacks outside the lock to avoid deadlocks
        for r in fired:
            if self._on_fire:
                try:
                    self._on_fire(dict(r))
                except Exception as e:
                    log.error("Reminder callback error for '%s': %s", r["text"], e)

    # ── Persistence ───────────────────────────────────────────────

    def _load(self) -> None:
        """Load reminders from JSON file."""
        if not _REMINDERS_FILE.exists():
            self._reminders = []
            return
        try:
            data = json.loads(_REMINDERS_FILE.read_text())
            self._reminders = data if isinstance(data, list) else []
            log.debug("Loaded %d reminders from disk.", len(self._reminders))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Could not load reminders: %s. Starting fresh.", e)
            self._reminders = []

    def _save(self) -> None:
        """Save reminders to JSON file. Must be called with _lock held."""
        try:
            _REMINDERS_FILE.write_text(
                json.dumps(self._reminders, indent=2, ensure_ascii=False)
            )
        except OSError as e:
            log.error("Could not save reminders: %s", e)


# ── Time parsing ──────────────────────────────────────────────────
# Parses natural language time expressions into datetime objects.

import re


def parse_reminder_time(time_str: str, date_str: str = "today") -> Optional[datetime]:
    """
    Parse a human-friendly time + date into a datetime.

    Args:
        time_str: "5pm", "5:30pm", "17:00", "in 2 hours", "in 30 minutes"
        date_str: "today", "tomorrow", "2026-03-28"

    Returns:
        A datetime object, or None if parsing fails.
    """
    now = _now()

    # ── Relative time: "in X hours/minutes" ───────────────────────
    m = re.match(r"in\s+(\d+)\s+(hour|hr|minute|min)s?", time_str.lower().strip())
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit in ("hour", "hr"):
            return now + timedelta(hours=amount)
        else:
            return now + timedelta(minutes=amount)

    # ── Absolute time: "5pm", "5:30pm", "17:00", "7:30am" ────────
    hour, minute = None, 0

    # 12-hour: "5pm", "5:30pm", "10am", "11:30am"
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_str.lower().strip())
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

    # 24-hour: "17:00", "09:30"
    if hour is None:
        m = re.match(r"(\d{1,2}):(\d{2})", time_str.strip())
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2))

    # Named times
    if hour is None:
        named = {
            "morning": (9, 0), "subah": (9, 0),
            "afternoon": (14, 0), "dopahar": (14, 0),
            "evening": (18, 0), "shaam": (18, 0),
            "night": (21, 0), "raat": (21, 0),
        }
        key = time_str.lower().strip()
        if key in named:
            hour, minute = named[key]

    if hour is None:
        return None

    # ── Date resolution ───────────────────────────────────────────
    date_lower = date_str.lower().strip()

    if date_lower == "today" or date_lower == "aaj":
        target_date = now.date()
    elif date_lower in ("tomorrow", "kal"):
        target_date = (now + timedelta(days=1)).date()
    else:
        # Try ISO date
        try:
            target_date = datetime.strptime(date_lower, "%Y-%m-%d").date()
        except ValueError:
            target_date = now.date()

    result = datetime(target_date.year, target_date.month, target_date.day, hour, minute)

    # If the time has already passed today, push to tomorrow
    # (only when date_str is "today" / not explicitly set)
    if date_lower in ("today", "aaj") and result <= now:
        result += timedelta(days=1)

    return result
