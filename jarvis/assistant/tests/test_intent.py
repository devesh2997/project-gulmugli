"""
Intent classification test suite.

Tests that the LLM correctly classifies user inputs into the right intent type
with correct parameters, across English, Hindi, and Hinglish inputs.

IMPORTANT: Test inputs must NOT overlap with examples in the system prompt.
The system prompt has "Sajni", "Channa Mereya", "Starboy", etc. — we test
with DIFFERENT songs/commands so we're measuring generalization, not memorization.
"""

import time
from core.logger import get_logger

log = get_logger("tests.intent")


# Each test: (input, expected_intent, param_checks, description)
# param_checks is a dict of {param_name: expected_value_or_callable}
# Use a callable for fuzzy matching: lambda v: "sajni" in v.lower()

INTENT_TESTS = [
    # ── Music Play ──────────────────────────────────────────
    # NOTE: Bare song names without a verb (e.g., just "Tum Hi Ho") are NOT
    # expected to classify as music_play. The user should say "play X" or "X bajao"
    # to express music intent. This is by design — avoids accidental playback.

    # Indie / non-mainstream music requests
    {
        "input": "play Husn by Anuv Jain",
        "intent": "music_play",
        "params": {"query": lambda v: "husn" in v.lower()},
        "desc": "Indian indie song with artist",
    },
    {
        "input": "Choo Lo laga do The Local Train wala",
        "intent": "music_play",
        "params": {"query": lambda v: "choo lo" in v.lower() or "local train" in v.lower()},
        "desc": "Indie rock song in Hinglish",
    },
    {
        "input": "play something by Prateek Kuhad",
        "intent": "music_play",
        "params": {"query": lambda v: "prateek" in v.lower() or "kuhad" in v.lower()},
        "desc": "Indie artist request",
    },
    {
        "input": "kuch lo-fi type bajao yaar",
        "intent": "music_play",
        "params": {"query": lambda v: "lo-fi" in v.lower() or "lofi" in v.lower()},
        "desc": "Hinglish mood request (lo-fi genre)",
    },
    {
        "input": "play Do I Wanna Know",
        "intent": "music_play",
        "params": {"query": lambda v: "wanna know" in v.lower()},
        "desc": "Alt rock song (Arctic Monkeys) — conversational title",
    },
    {
        "input": "When Chai Met Toast ka Firefly laga do",
        "intent": "music_play",
        "params": {"query": lambda v: "firefly" in v.lower() or "chai" in v.lower()},
        "desc": "Kerala indie-folk band specific song in Hinglish",
    },

    # ── Music Control ───────────────────────────────────────
    {
        "input": "pause the music",
        "intent": "music_control",
        "params": {"action": "pause"},
        "desc": "Pause in English",
    },
    {
        "input": "gaana rok do",
        "intent": "music_control",
        "params": {"action": lambda v: v in ("pause", "stop")},
        "desc": "Pause/stop in Hindi",
    },
    {
        "input": "next song please",
        "intent": "music_control",
        "params": {"action": "skip"},
        "desc": "Skip in English",
    },

    # ── Volume ──────────────────────────────────────────────
    {
        "input": "volume 40",
        "intent": "volume",
        "params": {"level": lambda v: str(v).strip('%') == "40"},
        "desc": "Explicit volume level",
    },
    {
        "input": "awaaz kam karo",
        "intent": "volume",
        "params": {"level": lambda v: int(str(v).strip('%')) < 50},
        "desc": "Volume down in Hindi",
    },

    # ── Light Control ───────────────────────────────────────
    {
        "input": "turn off the lights",
        "intent": "light_control",
        "params": {"action": "off"},
        "desc": "Lights off in English",
    },
    {
        "input": "light ka colour green karo",
        "intent": "light_control",
        "params": {"action": "color", "value": lambda v: "green" in v.lower()},
        "desc": "Color in Hinglish",
    },
    {
        "input": "study mode laga do",
        "intent": "light_control",
        "params": {"action": "scene", "value": lambda v: "study" in v.lower()},
        "desc": "Scene in Hinglish",
    },
    {
        "input": "brightness 30 percent",
        "intent": "light_control",
        "params": {"action": "brightness"},
        "desc": "Brightness in English",
    },

    # ── Switch Personality ──────────────────────────────────
    {
        "input": "switch to Chandler mode",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "chandler" in v.lower()},
        "desc": "Personality switch English",
    },
    {
        "input": "Devesh ban ja",
        "intent": "switch_personality",
        "params": {"personality": lambda v: "devesh" in v.lower()},
        "desc": "Personality switch Hindi",
    },

    # ── Chat ────────────────────────────────────────────────
    {
        "input": "tell me a joke",
        "intent": "chat",
        "params": {},
        "desc": "Chat — joke request",
    },
    {
        "input": "what is machine learning",
        "intent": "chat",
        "params": {},
        "desc": "Chat — knowledge question (should NOT be knowledge_search)",
    },
    {
        "input": "tell me a bedtime story about a dragon",
        "intent": "chat",
        "params": {},
        "desc": "Chat — story request (single intent, NOT double chat)",
    },

    # ── System ──────────────────────────────────────────────
    {
        "input": "what time is it",
        "intent": "system",
        "params": {"action": "time"},
        "desc": "System time English",
    },
    {
        "input": "aaj kya date hai",
        "intent": "system",
        "params": {"action": "date"},
        "desc": "System date Hindi",
    },

    # ── Memory ──────────────────────────────────────────────
    {
        "input": "what songs did I play today",
        "intent": "memory_recall",
        "params": {"query": lambda v: len(v) > 0},
        "desc": "Memory recall English",
    },
    {
        "input": "kitna yaad hai tujhe",
        "intent": "memory_stats",
        "params": {},
        "desc": "Memory stats Hindi",
    },

    # ── Knowledge Search ────────────────────────────────────
    {
        "input": "who is the current prime minister of UK",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "prime minister" in v.lower() or "uk" in v.lower()},
        "desc": "Knowledge — current affairs English",
    },
    {
        "input": "aaj India mein kya news hai",
        "intent": "knowledge_search",
        "params": {"query": lambda v: "india" in v.lower() or "news" in v.lower()},
        "desc": "Knowledge — news Hindi",
    },

    # ── Command Chaining ────────────────────────────────────
    {
        "input": "play Husn and set lights to warm white",
        "intent": ["music_play", "light_control"],
        "params": {},
        "desc": "Chained: indie song + lights",
    },
    {
        "input": "stop music and turn off lights",
        "intent": ["music_control", "light_control"],
        "params": {},
        "desc": "Chained: stop + lights off",
    },
]


def run_intent_tests(brain) -> dict:
    """Run all intent classification tests."""
    results = []
    total_latency = 0

    for test_case in INTENT_TESTS:
        user_input = test_case["input"]
        expected_intent = test_case["intent"]
        param_checks = test_case["params"]
        desc = test_case["desc"]

        start = time.time()
        try:
            intents = brain.classify_intent(user_input)
            latency = time.time() - start
            total_latency += latency

            # Check intent type
            if isinstance(expected_intent, list):
                # Chained: check all expected intents are present
                actual_names = [i.name for i in intents]
                passed = all(e in actual_names for e in expected_intent)
                detail = f"expected {expected_intent}, got {actual_names}" if not passed else ""
            else:
                # Single intent
                actual_name = intents[0].name if intents else "none"
                actual_params = intents[0].params if intents else {}
                passed = actual_name == expected_intent

                # Check parameters if intent matches
                if passed and param_checks:
                    for param_name, expected_val in param_checks.items():
                        actual_val = actual_params.get(param_name, "")
                        if callable(expected_val):
                            if not expected_val(actual_val):
                                passed = False
                                detail = f"param '{param_name}' check failed: got '{actual_val}'"
                                break
                        elif str(actual_val).lower() != str(expected_val).lower():
                            passed = False
                            detail = f"param '{param_name}': expected '{expected_val}', got '{actual_val}'"
                            break
                    else:
                        detail = ""
                elif not passed:
                    detail = f"expected '{expected_intent}', got '{actual_name}'"
                    # Include params for debugging
                    if intents:
                        detail += f" (params: {intents[0].params})"
                else:
                    detail = ""

                # Extra check: story/joke should NOT be double-chat
                if expected_intent == "chat" and len(intents) > 1:
                    all_chat = all(i.name == "chat" for i in intents)
                    if all_chat:
                        # The defensive merge should have caught this,
                        # but flag it as a warning
                        detail = "Multiple chat intents returned (merger should have caught this)"

        except Exception as e:
            latency = time.time() - start
            total_latency += latency
            passed = False
            detail = f"Exception: {e}"

        status = "PASS" if passed else "FAIL"
        log.info("[%s] %s — %s (%.2fs)", status, desc, user_input[:40], latency)
        if not passed:
            log.warning("  → %s", detail)

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
