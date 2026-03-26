"""
Pre-filter test suite.

Tests that the keyword pre-filter correctly catches obvious commands
and returns None for ambiguous inputs that should go to the LLM.

Two critical properties:
1. No false positives — if the pre-filter matches, it MUST be correct.
   A wrong pre-filter result bypasses the LLM entirely = wrong action.
2. False negatives are fine — the LLM catches anything the pre-filter misses.
"""

import time
from core.prefilter import prefilter_intent
from core.logger import get_logger

log = get_logger("tests.prefilter")


PREFILTER_TESTS = [
    # ── Should match (instant resolution) ─────────────────
    # Music control
    {"input": "pause", "expect_intent": "music_control", "expect_param": ("action", "pause"),
     "desc": "Bare 'pause' → music_control.pause"},
    {"input": "pause the music", "expect_intent": "music_control", "expect_param": ("action", "pause"),
     "desc": "Pause the music → music_control.pause"},
    {"input": "stop", "expect_intent": "music_control", "expect_param": ("action", "stop"),
     "desc": "Bare 'stop' → music_control.stop"},
    {"input": "gaana rok do", "expect_intent": "music_control", "expect_param": ("action", "stop"),
     "desc": "Hindi stop → music_control.stop"},
    {"input": "skip", "expect_intent": "music_control", "expect_param": ("action", "skip"),
     "desc": "Bare 'skip' → music_control.skip"},
    {"input": "next song", "expect_intent": "music_control", "expect_param": ("action", "skip"),
     "desc": "Next song → music_control.skip"},
    {"input": "skip this one", "expect_intent": "music_control", "expect_param": ("action", "skip"),
     "desc": "Skip this one → music_control.skip"},
    {"input": "dusra gaana", "expect_intent": "music_control", "expect_param": ("action", "skip"),
     "desc": "Hindi skip → music_control.skip"},

    # Volume
    {"input": "volume 50", "expect_intent": "volume", "expect_param": ("level", "50"),
     "desc": "Volume 50 → volume.50"},
    {"input": "volume 100", "expect_intent": "volume", "expect_param": ("level", "100"),
     "desc": "Volume 100 → volume.100"},
    {"input": "volume up", "expect_intent": "volume", "expect_param": ("level", "80"),
     "desc": "Volume up → volume.80"},
    {"input": "awaaz kam karo", "expect_intent": "volume", "expect_param": ("level", "30"),
     "desc": "Hindi volume down → volume.30"},
    {"input": "mute", "expect_intent": "volume", "expect_param": ("level", "0"),
     "desc": "Mute → volume.0"},

    # Lights
    {"input": "lights off", "expect_intent": "light_control", "expect_param": ("action", "off"),
     "desc": "Lights off → light_control.off"},
    {"input": "turn off the lights", "expect_intent": "light_control", "expect_param": ("action", "off"),
     "desc": "Turn off the lights → light_control.off"},
    {"input": "batti band karo", "expect_intent": "light_control", "expect_param": ("action", "off"),
     "desc": "Hindi lights off → light_control.off"},
    {"input": "lights on", "expect_intent": "light_control", "expect_param": ("action", "on"),
     "desc": "Lights on → light_control.on"},
    {"input": "turn on the lights", "expect_intent": "light_control", "expect_param": ("action", "on"),
     "desc": "Turn on the lights → light_control.on"},

    # System
    {"input": "what time is it", "expect_intent": "system", "expect_param": ("action", "time"),
     "desc": "What time is it → system.time"},
    {"input": "what's the date", "expect_intent": "system", "expect_param": ("action", "date"),
     "desc": "What's the date → system.date"},

    # ── Should NOT match (must return None → fall to LLM) ──
    {"input": "play Husn by Anuv Jain", "expect_intent": None, "expect_param": None,
     "desc": "Music play request → should NOT match (needs LLM)"},
    {"input": "study mode laga do", "expect_intent": None, "expect_param": None,
     "desc": "Light scene → should NOT match (needs LLM for scene parsing)"},
    {"input": "tell me a joke", "expect_intent": None, "expect_param": None,
     "desc": "Chat → should NOT match"},
    {"input": "switch to Chandler mode", "expect_intent": None, "expect_param": None,
     "desc": "Personality switch → should NOT match"},
    {"input": "play Tum Hi Ho and set lights to purple", "expect_intent": None, "expect_param": None,
     "desc": "Chained command → should NOT match (too complex for pre-filter)"},
    {"input": "kuch sad sa bajao", "expect_intent": None, "expect_param": None,
     "desc": "Mood-based music → should NOT match"},
    {"input": "who is the PM of India", "expect_intent": None, "expect_param": None,
     "desc": "Knowledge search → should NOT match"},
    {"input": "brightness 30 percent", "expect_intent": None, "expect_param": None,
     "desc": "Brightness with value → should NOT match (needs LLM for value parsing)"},
]


def run_prefilter_tests() -> dict:
    """Run all pre-filter tests."""
    results = []
    total_latency = 0

    for test_case in PREFILTER_TESTS:
        user_input = test_case["input"]
        expected_intent = test_case["expect_intent"]
        expected_param = test_case["expect_param"]
        desc = test_case["desc"]

        start = time.time()
        try:
            result = prefilter_intent(user_input)
            latency = time.time() - start
            total_latency += latency

            if expected_intent is None:
                # Should NOT have matched
                passed = result is None
                detail = "" if passed else f"Should be None, got {result[0].name}"
            else:
                # Should have matched
                if result is None:
                    passed = False
                    detail = f"Expected {expected_intent}, got None (no match)"
                else:
                    actual_intent = result[0].name
                    passed = actual_intent == expected_intent
                    detail = "" if passed else f"Expected {expected_intent}, got {actual_intent}"

                    # Check param if specified
                    if passed and expected_param:
                        param_name, param_val = expected_param
                        actual_val = result[0].params.get(param_name, "")
                        if str(actual_val) != str(param_val):
                            passed = False
                            detail = f"Param {param_name}: expected '{param_val}', got '{actual_val}'"

        except Exception as e:
            latency = time.time() - start
            total_latency += latency
            passed = False
            detail = f"Exception: {e}"

        # Convert to milliseconds for display (pre-filter should be <1ms)
        latency_ms = latency * 1000
        status = "PASS" if passed else "FAIL"
        log.info("[%s] %s (%.2fms) %s", status, desc, latency_ms, detail if not passed else "")

        results.append({
            "name": desc,
            "input": user_input,
            "passed": passed,
            "latency": latency,
            "detail": detail,
        })

    passed_count = sum(1 for r in results if r["passed"])

    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
    }
