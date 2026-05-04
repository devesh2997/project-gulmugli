"""
Dispatch-table integrity tests.

Catches a whole class of bugs: "I added an intent to _VALID_INTENTS in
ollama.py, wrote a description block, added test cases — but forgot
to wire a handler in core/intent_handler.py's _DISPATCH dict." The
classifier accepts the intent → dispatch falls through to "I'm not
sure" → confusing UX, hard to spot in logs.

Each test in here is a static cross-reference check between the two
sources of truth. Pure-import, no Ollama, runs in <100ms.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Tests ────────────────────────────────────────────────────────────


def test_every_valid_intent_has_a_handler():
    """
    _VALID_INTENTS is the classifier's allow-list; _DISPATCH is the
    runtime executor. They MUST be the same set, modulo a small allow-
    list of intents that are intentionally dispatched indirectly
    (e.g., parsed but routed through a context-specific code path).
    """
    from providers.brain.ollama import _VALID_INTENTS
    from core.intent_handler import _DISPATCH

    # Intents that may legitimately not appear in _DISPATCH because
    # they're handled out-of-band. Empty for now; expand only with a
    # comment explaining WHY a particular intent skips dispatch.
    EXEMPT: set[str] = set()

    valid = set(_VALID_INTENTS)
    dispatched = set(_DISPATCH.keys())

    missing_handlers = (valid - dispatched) - EXEMPT
    assert not missing_handlers, (
        f"Intents declared in _VALID_INTENTS but missing from _DISPATCH: "
        f"{sorted(missing_handlers)}. Either add a _handle_<name> in "
        f"core/intent_handler.py and a row in _DISPATCH, or add the "
        f"intent to the EXEMPT set in test_intent_dispatch.py with a "
        f"reason."
    )


def test_no_orphan_handlers_in_dispatch():
    """
    Reverse of the above — every handler in _DISPATCH should also be in
    _VALID_INTENTS. An orphan means we have a handler the classifier
    can never select (dead code, or someone removed an intent and
    forgot the handler).
    """
    from providers.brain.ollama import _VALID_INTENTS
    from core.intent_handler import _DISPATCH

    valid = set(_VALID_INTENTS)
    dispatched = set(_DISPATCH.keys())

    # `video_control` is dispatched but doesn't have to be a classifier
    # intent — it's invoked indirectly by video_music in some flows.
    # Document that exemption here.
    EXEMPT_HANDLERS: set[str] = {"video_control"}

    orphans = (dispatched - valid) - EXEMPT_HANDLERS
    assert not orphans, (
        f"Handlers in _DISPATCH that aren't in _VALID_INTENTS: "
        f"{sorted(orphans)}. Either add the intent name to "
        f"_VALID_INTENTS, or add to EXEMPT_HANDLERS with a reason."
    )


def test_dispatch_handlers_are_callable():
    """Defensive: every dispatch entry must point at a callable."""
    from core.intent_handler import _DISPATCH
    bad = [name for name, fn in _DISPATCH.items() if not callable(fn)]
    assert not bad, f"Non-callable dispatch entries: {bad}"


def test_intent_schema_enum_matches_valid_intents():
    """
    The JSON schema enforced on Ollama's structured output uses the
    enum from _VALID_INTENTS. If the two ever drift, the model could
    return a name we have no handler for. Verify the round-trip.
    """
    from providers.brain.ollama import _INTENT_SCHEMA, _VALID_INTENTS
    schema_enum = (
        _INTENT_SCHEMA["properties"]["intents"]
        ["items"]["properties"]["intent"]["enum"]
    )
    assert list(schema_enum) == list(_VALID_INTENTS), (
        "_INTENT_SCHEMA enum drifted from _VALID_INTENTS. "
        "If you added an intent, you may need to rebuild the schema."
    )


# ── Test runner integration ──────────────────────────────────────────


def _collect_tests():
    return [obj for name, obj in globals().items()
            if name.startswith("test_") and callable(obj)]


def run_intent_dispatch_tests() -> dict:
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
    s = run_intent_dispatch_tests()
    for r in s["tests"]:
        marker = "PASS" if r["passed"] else "FAIL"
        suffix = f": {r['detail']}" if r["detail"] else ""
        print(f"  [{marker}] {r['name']}{suffix}")
    print(f"\n{s['passed']}/{s['total']} intent_dispatch tests passed.")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
