"""
Personality system test suite.

Tests personality switching, tone injection into prompts, and that
the active personality correctly influences LLM responses.
"""

import time
from core.personality import personality_manager
from core.logger import get_logger

log = get_logger("tests.personality")


def run_personality_tests(brain) -> dict:
    """Run personality system tests."""
    results = []
    total_latency = 0

    # ── Test 1: Default personality loads correctly ──────────
    start = time.time()
    try:
        p = personality_manager.active
        passed = p is not None and p.id != ""
        detail = f"Active: {p.id} ({p.display_name})" if passed else "No active personality"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Default personality loaded", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 2: List all personalities ───────────────────────
    start = time.time()
    try:
        all_p = personality_manager.list()
        passed = len(all_p) >= 2  # should have at least jarvis + devesh
        detail = f"{len(all_p)} personalities: {[p.id for p in all_p]}"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Multiple personalities exist", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 3: Switch personality ───────────────────────────
    original_id = personality_manager.active.id
    start = time.time()
    try:
        # Find a personality that isn't the current one
        targets = [p for p in personality_manager.list() if p.id != original_id]
        if targets:
            target = targets[0]
            personality_manager.switch(target.id)
            passed = personality_manager.active.id == target.id
            detail = f"Switched to {target.id}" if passed else f"Switch failed, still {personality_manager.active.id}"
        else:
            passed = False
            detail = "No other personalities to switch to"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Switch personality", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 4: Switch back to original ──────────────────────
    start = time.time()
    try:
        personality_manager.switch(original_id)
        passed = personality_manager.active.id == original_id
        detail = f"Back to {original_id}" if passed else f"Failed, at {personality_manager.active.id}"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Switch back to original", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 5: Personality tone influences chat response ────
    start = time.time()
    try:
        # Switch to chandler (sarcastic) if available, else use any non-default
        chandler = None
        for p in personality_manager.list():
            if p.id == "chandler":
                chandler = p
                break

        if chandler:
            personality_manager.switch("chandler")
            resp = brain.generate(
                prompt="introduce yourself in one sentence",
                system=f"You are {chandler.display_name}. {chandler.tone}\nRespond in one sentence.",
                temperature=0.7,
            )
            # Chandler should say something sarcastic or reference himself
            text_lower = resp.text.lower()
            passed = any(w in text_lower for w in [
                "chandler", "sarcas", "could", "bing", "joke", "funny",
                "humor", "awkward", "be any",
            ])
            detail = f"Response: {resp.text[:100]}"
            personality_manager.switch(original_id)
        else:
            passed = True  # skip if no chandler
            detail = "Chandler personality not configured, skipped"
    except Exception as e:
        passed = False
        detail = str(e)
        try:
            personality_manager.switch(original_id)
        except Exception:
            pass
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Personality tone influences response", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 6: Fuzzy name matching ──────────────────────────
    start = time.time()
    try:
        # Try switching with display name instead of ID
        personality_manager.switch("jarvis")  # ensure we're on jarvis first
        targets = [p for p in personality_manager.list() if p.id != "jarvis"]
        if targets:
            target = targets[0]
            # Try with display name
            personality_manager.switch(target.display_name)
            passed = personality_manager.active.id == target.id
            detail = f"Switched via display name '{target.display_name}'"
            personality_manager.switch(original_id)
        else:
            passed = True
            detail = "Only one personality, skipped"
    except Exception as e:
        passed = False
        detail = str(e)
        try:
            personality_manager.switch(original_id)
        except Exception:
            pass
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Fuzzy personality name matching", "passed": passed, "latency": latency, "detail": detail})

    # Ensure we're back to original
    try:
        personality_manager.switch(original_id)
    except Exception:
        pass

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
    }
