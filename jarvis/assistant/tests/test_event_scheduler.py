"""
Tests for core.event_scheduler.

Strategy: drive the scheduler's _tick() directly with mocked
event_manager + trigger_store so we don't sleep through 60-second
polls. This tests the rollover logic in isolation.
"""

from __future__ import annotations

import sys
import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.event_scheduler import EventScheduler  # noqa: E402


def _make_em(active_pack_id: str | None,
             auto_midnight: bool = False,
             is_today: bool = True) -> MagicMock:
    """Build a mock event_manager whose current() returns a configurable ActiveEvent."""
    em = MagicMock()
    if active_pack_id is None:
        em.current.return_value = None
        return em
    pack = MagicMock()
    pack.trigger_config = {"auto_midnight": auto_midnight}
    active = MagicMock()
    active.pack_id = active_pack_id
    active.pack = pack
    active.is_today = is_today
    em.current.return_value = active
    return em


def _make_store(triggered: bool = False) -> MagicMock:
    store = MagicMock()
    store.is_triggered.return_value = triggered
    return store


# ── Tests ────────────────────────────────────────────────────────────


def test_no_rollover_does_not_fire():
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    sched._last_seen_date = date.today()  # baseline = today

    em = _make_em("astha-birthday", auto_midnight=True)
    store = _make_store(triggered=False)

    sched._tick(em, store)
    assert fired == []


def test_baseline_initializes_on_first_tick_with_no_baseline():
    """If _last_seen_date is None, the first tick just records baseline."""
    sched = EventScheduler(on_trigger=lambda a: None)
    assert sched._last_seen_date is None
    em = _make_em("astha-birthday", auto_midnight=True)
    store = _make_store()
    sched._tick(em, store)
    assert sched._last_seen_date == date.today()


def test_rollover_with_auto_midnight_off_does_not_fire():
    """Even on rollover, auto_midnight=False packs are skipped."""
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    # Set baseline to yesterday so today is a "rollover."
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em("astha-birthday", auto_midnight=False)
    store = _make_store()

    sched._tick(em, store)
    assert fired == []


def test_rollover_with_auto_midnight_on_fires():
    """Day rollover + auto_midnight=True + not yet triggered → fires."""
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em("astha-birthday", auto_midnight=True)
    store = _make_store(triggered=False)

    sched._tick(em, store)
    assert len(fired) == 1
    assert fired[0].pack_id == "astha-birthday"


def test_rollover_skipped_if_already_triggered_this_year():
    """If trigger_state already records this year's trigger, scheduler defers."""
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em("astha-birthday", auto_midnight=True)
    store = _make_store(triggered=True)  # ← already triggered

    sched._tick(em, store)
    assert fired == []


def test_rollover_with_no_active_event_does_not_fire():
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em(None)  # current() returns None
    store = _make_store()

    sched._tick(em, store)
    assert fired == []


def test_rollover_with_eve_or_aftermath_does_not_fire():
    """Auto-midnight only fires on the day-of, not the eve or aftermath."""
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em("astha-birthday", auto_midnight=True, is_today=False)
    store = _make_store()

    sched._tick(em, store)
    assert fired == []


def test_on_trigger_exception_does_not_propagate():
    """A buggy on_trigger callback must not break the scheduler."""
    def bad_callback(active):
        raise RuntimeError("boom")
    sched = EventScheduler(on_trigger=bad_callback)
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em("astha-birthday", auto_midnight=True)
    store = _make_store()

    # Must not raise.
    sched._tick(em, store)
    # Baseline still updated even though callback failed.
    assert sched._last_seen_date == date.today()


def test_baseline_advances_after_rollover_check():
    """After observing a rollover, _last_seen_date must equal today."""
    fired: list = []
    sched = EventScheduler(on_trigger=lambda a: fired.append(a))
    from datetime import timedelta
    sched._last_seen_date = date.today() - timedelta(days=1)

    em = _make_em(None)
    store = _make_store()
    sched._tick(em, store)
    assert sched._last_seen_date == date.today()


def test_start_stop_lifecycle():
    """start() / stop() returns cleanly without errors."""
    sched = EventScheduler(on_trigger=lambda a: None, poll_interval_s=1)
    sched.start()
    assert sched.is_running()
    # Double-start is a no-op.
    sched.start()
    sched.stop()
    assert not sched.is_running()
    # Double-stop is a no-op.
    sched.stop()


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_event_scheduler_tests() -> dict:
    results = []
    total_latency = 0.0
    for t in _collect_tests():
        start = time.time()
        try:
            t()
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": True,
                "latency": elapsed, "detail": "", "tier": "easy", "tags": [],
            })
        except AssertionError as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed, "detail": str(e),
                "tier": "easy", "tags": [],
            })
        except Exception as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__, "input": "", "passed": False,
                "latency": elapsed,
                "detail": f"{type(e).__name__}: {e}",
                "tier": "easy", "tags": [],
            })
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results), "passed": passed,
        "total_latency": total_latency, "tests": results,
    }


def main() -> int:
    s = run_event_scheduler_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} event_scheduler tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
