"""
Tests for core.trigger_state — persistence + idempotency + corrupt
file recovery + atomic write.

Each test uses a fresh temp dir so there's no cross-contamination.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trigger_state import TriggerStateStore  # noqa: E402


# ── Tests ─────────────────────────────────────────────────────────────


def test_fresh_store_reports_not_triggered():
    with tempfile.TemporaryDirectory() as tmp:
        store = TriggerStateStore(path=Path(tmp) / "triggers.json")
        assert store.is_triggered("astha-birthday") is False


def test_mark_then_query_returns_true():
    with tempfile.TemporaryDirectory() as tmp:
        store = TriggerStateStore(path=Path(tmp) / "triggers.json")
        was_fresh = store.mark_triggered("astha-birthday", year=2026)
        assert was_fresh is True
        assert store.is_triggered("astha-birthday", year=2026) is True


def test_mark_idempotent_returns_false_second_time():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "triggers.json"
        store = TriggerStateStore(path=path)
        assert store.mark_triggered("p", year=2026) is True
        assert store.mark_triggered("p", year=2026) is False
        # File contents reflect a SINGLE entry, not two.
        data = json.loads(path.read_text())
        assert "p" in data and len(data["p"]) == 1


def test_year_keyed_storage_independent():
    with tempfile.TemporaryDirectory() as tmp:
        store = TriggerStateStore(path=Path(tmp) / "triggers.json")
        store.mark_triggered("p", year=2026)
        # Different year should report not triggered.
        assert store.is_triggered("p", year=2027) is False
        store.mark_triggered("p", year=2027)
        # Both years now true.
        assert store.is_triggered("p", year=2026)
        assert store.is_triggered("p", year=2027)


def test_state_persists_across_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "triggers.json"
        store_a = TriggerStateStore(path=path)
        store_a.mark_triggered("astha-birthday", year=2026)
        # Simulate a process restart by creating a fresh store from disk.
        store_b = TriggerStateStore(path=path)
        assert store_b.is_triggered("astha-birthday", year=2026) is True


def test_first_triggered_at_returns_iso_datetime():
    with tempfile.TemporaryDirectory() as tmp:
        store = TriggerStateStore(path=Path(tmp) / "triggers.json")
        when = datetime(2026, 5, 14, 22, 18, 33).astimezone()
        store.mark_triggered("p", year=2026, when=when)
        got = store.first_triggered_at("p", year=2026)
        assert got is not None
        assert got.year == 2026 and got.month == 5 and got.day == 14


def test_reset_returns_true_when_state_cleared():
    with tempfile.TemporaryDirectory() as tmp:
        store = TriggerStateStore(path=Path(tmp) / "triggers.json")
        store.mark_triggered("p", year=2026)
        assert store.reset("p", year=2026) is True
        assert store.is_triggered("p", year=2026) is False
        # Idempotent reset.
        assert store.reset("p", year=2026) is False


def test_corrupt_file_starts_fresh_and_renames_old():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "triggers.json"
        path.write_text("{not json")
        store = TriggerStateStore(path=path)
        # Started fresh:
        assert store.is_triggered("anything") is False
        # The bad file got renamed.
        bad = path.with_suffix(path.suffix + ".bad")
        assert bad.is_file()


def test_atomic_write_via_temp_file():
    """
    The persist path uses os.replace() which is atomic on POSIX. Verify
    the on-disk file is valid JSON after a write — no half-written state.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "triggers.json"
        store = TriggerStateStore(path=path)
        store.mark_triggered("p1", year=2026)
        store.mark_triggered("p2", year=2026)
        # Read back as JSON — must parse cleanly.
        data = json.loads(path.read_text())
        assert "p1" in data and "p2" in data


def test_string_year_keys_in_loaded_file():
    """JSON only supports string keys; verify we accept them on load."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "triggers.json"
        # Write a hand-crafted file with string year keys.
        path.write_text(json.dumps({
            "astha-birthday": {"2026": "2026-05-14T00:00:00+05:30"}
        }))
        store = TriggerStateStore(path=path)
        assert store.is_triggered("astha-birthday", year=2026)
        # int year arg works, value is just stringified for lookup.
        assert store.is_triggered("astha-birthday", year=int("2026"))


def test_creates_parent_directory_on_first_persist():
    """Even if `data/` doesn't exist yet, persisting creates it."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nested" / "dirs" / "triggers.json"
        assert not path.parent.exists()
        store = TriggerStateStore(path=path)
        store.mark_triggered("p", year=2026)
        assert path.is_file()


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_trigger_state_tests() -> dict:
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
    s = run_trigger_state_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} trigger_state tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
