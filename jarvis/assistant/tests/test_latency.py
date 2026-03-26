"""
Latency benchmark suite.

Measures the raw speed of each stage in the critical path.
These aren't pass/fail — they track performance over time so you can
spot regressions after code changes or model swaps.

The thresholds are targets for perceived real-time interaction:
  - Classification: <2s on Mac, <3s on Jetson (including model inference)
  - Enrichment: <1.5s (shorter prompt, lower temperature)
  - Chat generation: <3s for short responses
  - Overall: The user shouldn't wait more than ~5s from speaking to hearing a response
"""

import time
from core.logger import get_logger
from core.personality import personality_manager

log = get_logger("tests.latency")

# Thresholds in seconds — these are aspirational targets.
# Tests "pass" if under threshold, but latency data is tracked regardless.
THRESHOLDS = {
    "prefilter_batch": 0.01,      # 20 pre-filter checks should be <10ms total
    "classify_simple": 3.0,       # single simple intent
    "classify_hinglish": 3.5,     # Hinglish input (might be harder)
    "classify_chained": 4.0,      # multi-intent (more output tokens)
    "enrich_known": 2.0,          # enriching a known song
    "enrich_unknown": 2.0,        # enriching an unknown query
    "chat_short": 4.0,            # short chat response
    "chat_medium": 6.0,           # medium chat response
    "generate_raw": 3.0,          # raw LLM generate call
}


def run_latency_tests(brain) -> dict:
    """Run latency benchmarks."""
    results = []
    total_latency = 0

    # Pre-filter speed test — run 20 commands through the pre-filter
    from core.prefilter import prefilter_intent
    prefilter_inputs = [
        "pause", "stop", "skip", "next song", "volume 50", "volume up",
        "mute", "lights off", "lights on", "what time is it",
        "pause the music", "gaana rok do", "dusra gaana", "awaaz kam karo",
        "turn off the lights", "batti band karo", "what's the date",
        "volume down", "turn on the lights", "volume 30",
    ]

    benchmarks = [
        {
            "name": "prefilter_batch",
            "desc": "Pre-filter: 20 commands (should be <10ms total)",
            "fn": lambda: [prefilter_intent(inp) for inp in prefilter_inputs],
        },
        {
            "name": "classify_simple",
            "desc": "Classify: simple English command",
            "fn": lambda: brain.classify_intent("play some music"),
        },
        {
            "name": "classify_hinglish",
            "desc": "Classify: Hinglish command",
            "fn": lambda: brain.classify_intent("light ka colour laal karo aur gaana bajao"),
        },
        {
            "name": "classify_chained",
            "desc": "Classify: chained command",
            "fn": lambda: brain.classify_intent("play Tum Hi Ho volume 50 and set lights to romantic"),
        },
        {
            "name": "enrich_known",
            "desc": "Enrich: well-known song",
            "fn": lambda: brain.enrich_query("Tum Hi Ho"),
        },
        {
            "name": "enrich_unknown",
            "desc": "Enrich: vague mood query",
            "fn": lambda: brain.enrich_query("something chill and relaxing"),
        },
        {
            "name": "chat_short",
            "desc": "Chat: short response",
            "fn": lambda: brain.generate(
                prompt="what is 2 + 2",
                system=f"You are {personality_manager.active.display_name}. Answer in one sentence.",
                temperature=0.7,
            ),
        },
        {
            "name": "chat_medium",
            "desc": "Chat: medium response",
            "fn": lambda: brain.generate(
                prompt="tell me something interesting about space",
                system=f"You are {personality_manager.active.display_name}. Keep it to 2-3 sentences.",
                temperature=0.7,
            ),
        },
        {
            "name": "generate_raw",
            "desc": "Generate: raw LLM call (no system prompt)",
            "fn": lambda: brain.generate(
                prompt="Hello",
                temperature=0.3,
            ),
        },
    ]

    for bench in benchmarks:
        name = bench["name"]
        desc = bench["desc"]
        threshold = THRESHOLDS.get(name, 5.0)

        start = time.time()
        try:
            result = bench["fn"]()
            latency = time.time() - start
            passed = latency < threshold

            # Extract tokens/sec if available
            tok_sec = ""
            if hasattr(result, 'tokens_per_second'):
                tok_sec = f" ({result.tokens_per_second:.1f} tok/s)"
            elif isinstance(result, list) and result and hasattr(result[0], 'meta'):
                tps = result[0].meta.get('tok_per_sec', 0)
                tok_sec = f" ({tps:.1f} tok/s)"

            detail = f"{latency:.3f}s (threshold: {threshold}s){tok_sec}"

        except Exception as e:
            latency = time.time() - start
            passed = False
            detail = f"Exception: {e}"

        total_latency += latency

        status = "PASS" if passed else "SLOW"
        log.info("[%s] %s — %.3fs (threshold: %.1fs)", status, desc, latency, threshold)

        results.append({
            "name": desc,
            "passed": passed,
            "latency": latency,
            "detail": detail,
            "threshold": threshold,
        })

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
    }
