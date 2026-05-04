"""
Tests for the explicit memory_log intent handler.

These exercise:
  - Writing logged text + the right tags via SQLite memory provider
  - Empty payload falls back to original_input
  - Provider-missing path returns the polite fallback message
  - Logged entries surface via find_by_tag('memory_log')
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.interfaces import Intent  # noqa: E402
from core.intent_handler import _handle_memory_log  # noqa: E402
from providers.memory.sqlite import SQLiteMemoryProvider  # noqa: E402


def _make_assistant(memory) -> dict:
    return {
        "memory": memory,
        "brain": MagicMock(),
        "voice_router": MagicMock(),
        "face_ui": MagicMock(),
    }


def test_writes_to_memory_with_log_tag():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = SQLiteMemoryProvider(db_path=str(Path(tmp_str) / "m.db"))
        assistant = _make_assistant(prov)
        intent = Intent(
            name="memory_log",
            params={"text": "Astha loves biryani"},
            response="",
            confidence=1.0,
            meta={"original_input": "remember that Astha loves biryani"},
        )
        spoken = _handle_memory_log(assistant, intent)
        assert spoken and "Yaad rakh liya" in spoken

        # Verify the row landed with the right tags.
        rows = prov.find_by_tag("memory_log")
        assert len(rows) == 1
        assert rows[0].raw["input_text"] == "Astha loves biryani"
        tags = rows[0].raw["tags"]
        assert "memory_log" in tags
        assert "user_logged" in tags


def test_empty_payload_falls_back_to_original_input():
    with tempfile.TemporaryDirectory() as tmp_str:
        prov = SQLiteMemoryProvider(db_path=str(Path(tmp_str) / "m.db"))
        assistant = _make_assistant(prov)
        # Classifier left text empty; original_input is in meta.
        intent = Intent(
            name="memory_log",
            params={"text": ""},
            response="",
            meta={"original_input": "remember the kitchen tap is leaking"},
        )
        spoken = _handle_memory_log(assistant, intent)
        assert spoken
        rows = prov.find_by_tag("memory_log")
        assert len(rows) == 1
        # The full original input got stored (not just the trigger phrase).
        assert "kitchen tap" in rows[0].raw["input_text"]


def test_no_memory_provider_returns_polite_fallback():
    intent = Intent(name="memory_log", params={"text": "x"}, response="", meta={})
    spoken = _handle_memory_log({"memory": None}, intent)
    assert spoken
    assert "memory" in spoken.lower() or "yaad" in spoken.lower()


def test_log_failure_does_not_crash_caller():
    """If log_interaction raises, the handler returns a polite error."""
    bad_provider = MagicMock()
    bad_provider.log_interaction.side_effect = RuntimeError("disk full")
    intent = Intent(
        name="memory_log",
        params={"text": "test"},
        response="",
        meta={"original_input": "remember test"},
    )
    spoken = _handle_memory_log({"memory": bad_provider}, intent)
    # Must be a string, not None or an exception.
    assert isinstance(spoken, str) and len(spoken) > 0


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_memory_log_tests() -> dict:
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
    s = run_memory_log_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} memory_log tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
