"""
Tests for the Angry-Astha "kya hua → kuch nahi" prefilter shortcut.

This is a personality-gated shortcut: it only fires when the
`astha_angry` personality is currently active. Tests verify both
branches (gated off in default personality, gated on after switch)
plus a few negation cases that should NOT match the regex.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prefilter import prefilter_intent  # noqa: E402


# ── Test cases ────────────────────────────────────────────────────────


def _switch_personality(pid: str) -> None:
    """
    Helper: flip the active personality. Each test that needs a
    specific personality calls this in setup; we restore to "jarvis"
    in teardown so suites stay isolated.
    """
    from core.personality import personality_manager
    personality_manager.switch(pid)


def _restore_default() -> None:
    _switch_personality("jarvis")


def test_kya_hua_in_default_personality_no_match():
    """In `jarvis` personality (default), 'kya hua' MUST fall through."""
    _restore_default()
    result = prefilter_intent("kya hua")
    assert result is None, f"expected None in default personality, got {result}"


def test_kya_hua_in_astha_angry_returns_shortcut():
    """In `astha_angry`, 'kya hua' fires the hardcoded 'Kuch nahi.' reply."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("kya hua")
        assert result is not None, "expected match in astha_angry personality"
        assert len(result) == 1
        intent = result[0]
        assert intent.name == "chat"
        assert intent.response == "Kuch nahi."
        assert intent.meta.get("shortcut") == "astha_angry_kya_hua"
    finally:
        _restore_default()


def test_kya_hua_uppercase_matches():
    """The regex is case-insensitive."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("Kya Hua")
        assert result is not None
        assert result[0].response == "Kuch nahi."
    finally:
        _restore_default()


def test_kya_hua_with_question_mark_matches():
    """Trailing question marks are stripped by the prefilter pre-clean."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("kya hua?")
        assert result is not None
        assert result[0].response == "Kuch nahi."
    finally:
        _restore_default()


def test_kya_hua_hai_does_not_match():
    """The regex anchors on 'kya hua' alone — adding 'hai' or other
    suffixes should fall through to the LLM. Otherwise 'kya hua hai
    music ko' would silently classify as the easter egg."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("kya hua hai")
        assert result is None, f"expected fallthrough on extended phrase, got {result}"
    finally:
        _restore_default()


def test_kya_hua_with_extra_words_does_not_match():
    """Extra context invalidates the shortcut — the gag only works
    on the bare two-word phrase."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("astha kya hua tujhe")
        assert result is None
    finally:
        _restore_default()


def test_unrelated_input_in_astha_angry_falls_through():
    """Other inputs in astha_angry mode should still go to the LLM."""
    try:
        _switch_personality("astha_angry")
        result = prefilter_intent("what time is it")
        # Should match the system shortcut, not the kya-hua one.
        assert result is not None
        assert result[0].name == "system"
    finally:
        _restore_default()


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_astha_angry_prefilter_tests() -> dict:
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
    s = run_astha_angry_prefilter_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} astha_angry_prefilter tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
