"""
Tests for Phase 2.4 — memory event tagging + year-over-year recall.

Exercises the round-trip: log an interaction with tags, retrieve it via
find_by_tag and find_event_memories, and confirm rows that pre-date the
v2 schema migration still load (nullable tags_json).
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.interfaces import Interaction  # noqa: E402
from providers.memory.sqlite import SQLiteMemoryProvider  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────


def _new_provider(tmp: Path) -> SQLiteMemoryProvider:
    """Constructor uses a tempdir-scoped DB path."""
    return SQLiteMemoryProvider(db_path=str(tmp / "memory.db"))


def _log(provider: SQLiteMemoryProvider, text: str, tags: list[str] | None = None) -> int:
    intr = Interaction(
        user_id="default",
        input_text=text,
        intents=[],
        responses=["ok"],
        tags=tags or [],
    )
    return provider.log_interaction(intr)


# ── Tests ────────────────────────────────────────────────────────────


def test_log_interaction_persists_tags():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        _log(prov, "happy birthday", tags=["event:astha-birthday", "year:2026"])
        recent = prov.get_recent(limit=1)
        assert len(recent) == 1
        assert recent[0].raw["tags"] == ["event:astha-birthday", "year:2026"]


def test_find_by_tag_returns_matching_rows():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        _log(prov, "birthday line", tags=["event:astha-birthday", "year:2026"])
        _log(prov, "regular day", tags=[])
        _log(prov, "diwali line", tags=["event:diwali", "year:2026"])
        bday = prov.find_by_tag("event:astha-birthday")
        assert len(bday) == 1
        assert "birthday line" in bday[0].raw["input_text"]


def test_find_by_tag_does_not_partial_match_across_tag_boundaries():
    """The wrapping in JSON quotes prevents `event:x` matching `event:xyz`."""
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        _log(prov, "a", tags=["event:astha-birthday"])
        _log(prov, "b", tags=["event:astha-birthday-extended"])  # similar prefix
        # Querying the shorter tag should NOT pick up the longer one.
        a = prov.find_by_tag("event:astha-birthday")
        # Both contain the substring `event:astha-birthday` — the JSON-quoted
        # match would only be `"event:astha-birthday"` exactly. Only one row
        # has that exact stored quote.
        ids = {m.raw["id"] for m in a}
        assert len(ids) == 1


def test_find_event_memories_filters_by_event_and_year():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        _log(prov, "2026 birthday", tags=["event:astha-birthday", "year:2026"])
        _log(prov, "2027 birthday", tags=["event:astha-birthday", "year:2027"])
        _log(prov, "diwali 2026", tags=["event:diwali", "year:2026"])
        got_2026 = prov.find_event_memories(event_id="astha-birthday", year=2026)
        assert len(got_2026) == 1
        assert "2026 birthday" in got_2026[0].raw["input_text"]
        got_2027 = prov.find_event_memories(event_id="astha-birthday", year=2027)
        assert len(got_2027) == 1


def test_find_by_tag_returns_empty_list_on_miss():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        _log(prov, "untagged", tags=[])
        assert prov.find_by_tag("event:nope") == []


def test_log_without_tags_attribute_back_compat():
    """Older callers that don't pass tags=... must still work — default is []."""
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = _new_provider(Path(tmp_str))
        # Construct without tags — exercises the dataclass default_factory.
        intr = Interaction(
            user_id="default",
            input_text="legacy entry",
            intents=[],
            responses=["ok"],
        )
        prov.log_interaction(intr)
        recent = prov.get_recent(limit=1)
        assert recent[0].raw["tags"] == []


def test_pre_migration_rows_load_with_empty_tags():
    """
    Simulate a row that pre-dates the v2 migration: insert with NULL
    in tags_json. _row_to_memory must surface tags=[] not crash.

    We write through the provider's own connection (not a fresh
    sqlite3.connect) because WAL mode + the provider's persistent
    handle would deadlock against a second writer otherwise.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        prov = _new_provider(tmp)
        # Insert directly via the provider's own connection.
        prov._conn.execute(
            """
            INSERT INTO interactions
                (timestamp, user_id, input_text, intents_json,
                 responses_json, outcome, feedback, tags_json)
            VALUES ('2026-01-01T00:00:00', 'default', 'legacy', '[]',
                    '["ok"]', 'success', NULL, NULL)
            """
        )
        prov._conn.commit()
        recent = prov.get_recent(limit=10)
        legacy = [m for m in recent if m.raw["input_text"] == "legacy"]
        assert len(legacy) == 1
        assert legacy[0].raw["tags"] == []


def test_migration_idempotent_on_existing_db():
    """
    Constructing the provider twice on the same DB must not blow up
    when the v2 migration already added the column. The first provider
    is closed before the second to avoid the WAL-write-lock conflict
    that would happen with two persistent connections to the same file.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        prov1 = _new_provider(tmp)
        # Close the first one's connection so the second can claim the WAL.
        if prov1._conn is not None:
            prov1._conn.close()
            prov1._conn = None
        # Second construction → must NOT raise (column already exists).
        prov2 = _new_provider(tmp)
        # Sanity round-trip on the second instance.
        _log(prov2, "round-trip", tags=["x"])
        assert len(prov2.find_by_tag("x")) == 1


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_memory_event_recall_tests() -> dict:
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
    s = run_memory_event_recall_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} memory_event_recall tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
