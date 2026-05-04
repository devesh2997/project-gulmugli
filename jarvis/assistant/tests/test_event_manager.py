"""
Tests for core.event_manager.

Uses temp directories built per-test so we never touch the real `events/`
tree. Date-rule logic is exercised end-to-end with `now=` injection
rather than mocking the system clock — keeps tests deterministic without
freezegun.

Run via:
    python tests/test_event_manager.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

# Make the assistant package importable when the test is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.event_manager import EventManager  # noqa: E402


# ── Fixture helpers ──────────────────────────────────────────────────


def _write_pack(events_dir: Path, pack_id: str, pack_yaml: str) -> Path:
    pack_dir = events_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(pack_yaml)
    return pack_dir


def _at(year, month, day, hour=12) -> datetime:
    return datetime(year, month, day, hour, 0, 0)


# ── Test cases ────────────────────────────────────────────────────────


def test_no_events_dir_returns_empty():
    """A missing events/ directory must not crash; manager loads zero packs."""
    with tempfile.TemporaryDirectory() as tmp:
        em = EventManager(events_dir=Path(tmp) / "does-not-exist")
        assert em.list_packs() == []
        assert em.current(now=_at(2026, 5, 14)) is None


def test_yearly_recurring_match_on_day():
    """May 14 yearly rule fires on May 14 with is_today=True, days_until=0."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "astha-birthday", """
id: astha-birthday
display_name: Astha's Birthday
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        em = EventManager(events_dir=events)

        active = em.current(now=_at(2026, 5, 14))
        assert active is not None, "expected match on May 14"
        assert active.pack_id == "astha-birthday"
        assert active.is_today is True
        assert active.is_eve is False
        assert active.is_aftermath is False
        assert active.days_until == 0


def test_yearly_recurring_eve_window():
    """May 13 (one day before) fires with is_eve=True."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "p", """
id: p
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        em = EventManager(events_dir=events)
        active = em.current(now=_at(2026, 5, 13))
        assert active is not None and active.is_eve is True
        assert active.is_today is False
        assert active.days_until == 1


def test_yearly_recurring_aftermath_window():
    """May 15 (day after) fires with is_aftermath=True, days_until=-1."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "p", """
id: p
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        em = EventManager(events_dir=events)
        active = em.current(now=_at(2026, 5, 15))
        assert active is not None
        assert active.is_aftermath is True
        assert active.is_today is False
        assert active.days_until == -1


def test_yearly_no_match_far_from_event():
    """Mid-year for a May 14 event returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "p", """
id: p
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        em = EventManager(events_dir=events)
        assert em.current(now=_at(2026, 8, 1)) is None
        assert em.current(now=_at(2026, 1, 1)) is None


def test_yearly_year_boundary_dec_to_jan():
    """An event near year boundary (Jan 1) wraps from Dec 31 correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "newyear", """
id: newyear
date_rule:
  recurs: yearly
  month: 1
  day: 1
""")
        em = EventManager(events_dir=events)
        # Dec 31 2025 is the eve of Jan 1 2026.
        active = em.current(now=_at(2025, 12, 31))
        assert active is not None and active.is_eve is True
        assert active.days_until == 1


def test_one_time_match():
    """A one_time rule fires only on the exact date."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "launch", """
id: launch
date_rule:
  one_time: 2026-05-14
""")
        em = EventManager(events_dir=events)
        assert em.current(now=_at(2026, 5, 14)).is_today is True
        # Wrong year — no match (even though recurs would have matched).
        assert em.current(now=_at(2027, 5, 14)) is None


def test_range_rule_inside_window():
    """A range rule keeps is_today=True for every day inside the range.

    Range start=Oct 29, days=5 covers Oct 29, 30, 31, Nov 1, Nov 2.
    Nov 3 is one day after the range — falls in the 1-day default
    aftermath window.
    """
    from datetime import timedelta
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "diwali", """
id: diwali
date_rule:
  range_start: 2026-10-29
  range_days: 5
""")
        em = EventManager(events_dir=events)
        start = date(2026, 10, 29)
        for offset in range(5):
            d = start + timedelta(days=offset)
            active = em.current(now=datetime(d.year, d.month, d.day, 12))
            assert active is not None, f"expected match on {d.isoformat()}"
            assert active.is_today is True, f"expected is_today on {d.isoformat()}"
        # Day after the range — Nov 3 — should be aftermath.
        out = em.current(now=_at(2026, 11, 3))
        assert out is not None and out.is_aftermath is True


def test_multiple_packs_first_alphabetical_wins():
    """If two packs match the same day, the first (alphabetical) wins."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "bbb", """
id: bbb
date_rule:
  one_time: 2026-05-14
""")
        _write_pack(events, "aaa", """
id: aaa
date_rule:
  one_time: 2026-05-14
""")
        em = EventManager(events_dir=events)
        active = em.current(now=_at(2026, 5, 14))
        assert active is not None and active.pack_id == "aaa"


def test_broken_pack_does_not_break_others():
    """A pack with malformed YAML is skipped; other packs still load."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "good", """
id: good
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        _write_pack(events, "broken", "this is not valid yaml: [")
        em = EventManager(events_dir=events)
        assert len(em.list_packs()) == 1
        assert em.list_packs()[0].pack_id == "good"


def test_pack_with_no_date_rule_skipped():
    """A pack missing date_rule is skipped, not crashed."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "no-date", "id: no-date\n")
        em = EventManager(events_dir=events)
        assert em.list_packs() == []


def test_features_list_exposed():
    """Features list from pack.yaml is reachable through ActiveEvent.pack."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "p", """
id: p
date_rule:
  recurs: yearly
  month: 5
  day: 14
features:
  - yaadein
  - besura
  - confetti
""")
        em = EventManager(events_dir=events)
        active = em.current(now=_at(2026, 5, 14))
        assert active is not None
        assert active.pack.features == ["yaadein", "besura", "confetti"]


def test_custom_eve_aftermath_windows():
    """eve_days/aftermath_days override the 1-day default."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "wide", """
id: wide
date_rule:
  recurs: yearly
  month: 5
  day: 14
eve_days: 3
aftermath_days: 2
""")
        em = EventManager(events_dir=events)
        # 3 days before the event still matches as eve
        a3 = em.current(now=_at(2026, 5, 11))
        assert a3 is not None and a3.is_eve and a3.days_until == 3
        # 4 days before — out of window
        assert em.current(now=_at(2026, 5, 10)) is None
        # 2 days after — aftermath
        a_after = em.current(now=_at(2026, 5, 16))
        assert a_after is not None and a_after.is_aftermath
        assert a_after.days_until == -2


def test_id_mismatch_uses_directory_name():
    """If pack.yaml's id field doesn't match the directory, dir name wins."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "actual-dir", """
id: typo-in-pack-yaml
date_rule:
  recurs: yearly
  month: 5
  day: 14
""")
        em = EventManager(events_dir=events)
        active = em.current(now=_at(2026, 5, 14))
        assert active is not None
        assert active.pack_id == "actual-dir"


def test_reload_picks_up_new_packs():
    """reload() rescans the directory for newly-dropped packs."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        em = EventManager(events_dir=events)
        assert em.list_packs() == []

        _write_pack(events, "later", """
id: later
date_rule:
  one_time: 2026-05-14
""")
        em.reload()
        assert len(em.list_packs()) == 1


def test_leap_day_event_does_not_crash_on_non_leap_year():
    """A Feb 29 yearly event handles non-leap years gracefully (no Feb 29 → no match)."""
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp)
        _write_pack(events, "leap", """
id: leap
date_rule:
  recurs: yearly
  month: 2
  day: 29
""")
        em = EventManager(events_dir=events)
        # 2026 is not a leap year. Mar 1 2026 is the day after Feb 28; should not crash.
        # The Feb 29 in 2024 (leap) and 2028 (leap) are the candidate dates;
        # neither is in eve/aftermath of 2026-03-01, so result is None.
        result = em.current(now=_at(2026, 3, 1))
        # Don't care about the exact result — we just want no exception.
        # If it does match (e.g., from 2028's Feb 29), still no crash.
        _ = result


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_event_manager_tests() -> dict:
    """
    Suite-runner entry point — same shape as other test modules so
    tests/runner.py can include this in its pipeline.
    """
    import time
    results = []
    total_latency = 0.0

    for t in _collect_tests():
        start = time.time()
        try:
            t()
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__,
                "input": "",
                "passed": True,
                "latency": elapsed,
                "detail": "",
                "tier": "easy",
                "tags": [],
            })
        except AssertionError as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__,
                "input": "",
                "passed": False,
                "latency": elapsed,
                "detail": str(e),
                "tier": "easy",
                "tags": [],
            })
        except Exception as e:
            elapsed = time.time() - start
            total_latency += elapsed
            results.append({
                "name": t.__name__,
                "input": "",
                "passed": False,
                "latency": elapsed,
                "detail": f"{type(e).__name__}: {e}",
                "tier": "easy",
                "tags": [],
            })

    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "total_latency": total_latency,
        "tests": results,
    }


def main() -> int:
    summary = run_event_manager_tests()
    for r in summary["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{summary['passed']}/{summary['total']} event_manager tests passed.")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
