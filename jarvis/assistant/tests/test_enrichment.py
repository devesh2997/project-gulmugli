"""
Query enrichment test suite.

Tests that the LLM correctly enriches vague song queries with artist names
when it should, and leaves them unchanged when it shouldn't.

IMPORTANT: These songs must NOT appear in the enrichment prompt examples.
The prompt uses "Sajni", "Channa Mereya", "Starboy", "Bohemian Rhapsody" —
we test with different songs to measure real generalization.

Mix includes: Indian indie, Bollywood deep cuts, international indie/alt,
ambiguous titles, and mood/vague queries that should NOT be enriched.
"""

import time
from core.logger import get_logger

log = get_logger("tests.enrichment")


# (raw_query, expected_artist_substring, should_enrich, description)
ENRICHMENT_TESTS = [
    # ── Indian Indie — tests real generalization beyond Bollywood ──
    {
        "input": "Husn",
        "expected_in_result": "anuv",
        "should_enrich": True,
        "desc": "Husn → should add Anuv Jain (indie, not Bollywood)",
    },
    {
        "input": "Baarishein",
        "expected_in_result": "anuv",
        "should_enrich": True,
        "desc": "Baarishein → should add Anuv Jain (his debut, 200M+ streams)",
    },
    {
        "input": "Choo Lo",
        "expected_in_result": "local train",
        "should_enrich": True,
        "desc": "Choo Lo → should add The Local Train (indie rock band)",
    },
    {
        "input": "Khoj",
        "expected_in_result": "chai",
        "should_enrich": True,
        "desc": "Khoj → should add When Chai Met Toast (Kerala indie-folk)",
    },

    # ── Bollywood but NOT the usual suspects ──
    {
        "input": "Kun Faya Kun",
        "expected_in_result": "rahman",
        "should_enrich": True,
        "desc": "Kun Faya Kun → should add A.R. Rahman (Rockstar, not generic)",
    },
    {
        "input": "Gerua",
        "expected_in_result": "arijit",
        "should_enrich": True,
        "desc": "Gerua → should add Arijit Singh (from Dilwale, NOT Dum Maaro Dum)",
    },
    {
        "input": "Ilahi",
        "expected_in_result": lambda enriched: "arijit" in enriched or "mohit" in enriched,
        "should_enrich": True,
        "desc": "Ilahi → should add artist (Yeh Jawaani Hai Deewani — Mohit Chauhan or Arijit)",
    },

    # ── International indie/alt — not top-40 obvious ──
    {
        "input": "Do I Wanna Know",
        "expected_in_result": "arctic",
        "should_enrich": True,
        "desc": "Do I Wanna Know → should add Arctic Monkeys (alt rock)",
    },
    {
        "input": "Creep",
        "expected_in_result": "radiohead",
        "should_enrich": True,
        "desc": "Creep → should add Radiohead (classic alt, ambiguous title)",
    },
    {
        "input": "Electric Feel",
        "expected_in_result": "mgmt",
        "should_enrich": True,
        "desc": "Electric Feel → should add MGMT (indie classic)",
    },

    # ── Should NOT enrich — mood, vague, or artist-only ──
    {
        "input": "When Chai Met Toast",
        "expected_in_result": None,
        "should_enrich": False,
        "desc": "Artist-only (indie band) → should stay as-is",
    },
    {
        "input": "lo-fi beats for studying",
        "expected_in_result": None,
        "should_enrich": False,
        "desc": "Vague mood → should NOT enrich",
        "fuzzy_check": lambda raw, enriched: "lo-fi" in enriched.lower() or "lofi" in enriched.lower(),
    },
    {
        "input": "soft acoustic indie vibes",
        "expected_in_result": None,
        "should_enrich": False,
        "desc": "Genre mood query → should NOT enrich",
        "fuzzy_check": lambda raw, enriched: "acoustic" in enriched.lower() or "indie" in enriched.lower(),
    },
    {
        "input": "Prateek Kuhad",
        "expected_in_result": None,
        "should_enrich": False,
        "desc": "Artist-only (Indian indie) → should stay as-is",
    },
]


def run_enrichment_tests(brain) -> dict:
    """Run all enrichment tests."""
    results = []
    total_latency = 0

    for test_case in ENRICHMENT_TESTS:
        raw_query = test_case["input"]
        expected_in = test_case["expected_in_result"]
        should_enrich = test_case["should_enrich"]
        desc = test_case["desc"]

        start = time.time()
        try:
            enriched = brain.enrich_query(raw_query)
            latency = time.time() - start
            total_latency += latency

            if should_enrich:
                # Should have added something
                was_enriched = enriched.lower() != raw_query.lower()
                if callable(expected_in):
                    has_expected = expected_in(enriched.lower())
                elif expected_in:
                    has_expected = expected_in.lower() in enriched.lower()
                else:
                    has_expected = True
                passed = was_enriched and has_expected
                if not passed:
                    if not was_enriched:
                        detail = f"Not enriched: '{enriched}' (expected artist addition)"
                    else:
                        detail = f"Enriched to '{enriched}' but missing '{expected_in}'"
                else:
                    detail = f"→ '{enriched}'"
            else:
                # Should NOT have changed much (artist-only or mood queries)
                # Use custom fuzzy_check if provided, otherwise check core words
                fuzzy_fn = test_case.get("fuzzy_check")
                if fuzzy_fn:
                    passed = fuzzy_fn(raw_query, enriched)
                else:
                    core_words = raw_query.lower().split()[:2]
                    passed = all(w in enriched.lower() for w in core_words)
                detail = f"→ '{enriched}'" if passed else f"Mangled: '{enriched}'"

        except Exception as e:
            latency = time.time() - start
            total_latency += latency
            passed = False
            detail = f"Exception: {e}"

        status = "PASS" if passed else "FAIL"
        log.info("[%s] %s (%.2fs) %s", status, desc, latency, detail if not passed else "")

        results.append({
            "name": desc,
            "input": raw_query,
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
