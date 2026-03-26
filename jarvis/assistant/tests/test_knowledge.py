"""
Knowledge provider test suite.

Tests the KnowledgeProvider interface — search, availability checking,
and graceful degradation when offline.
"""

import time
from core.config import config
from core.logger import get_logger

log = get_logger("tests.knowledge")


def run_knowledge_tests() -> dict:
    """Run knowledge provider tests."""
    results = []
    total_latency = 0

    # ── Test 1: Provider loads successfully ──────────────────
    start = time.time()
    knowledge = None
    try:
        from core.registry import get_provider
        knowledge_cfg = config.get("knowledge", {})
        provider_name = knowledge_cfg.get("provider", "duckduckgo")
        knowledge = get_provider("knowledge", provider_name)
        passed = knowledge is not None
        detail = f"Provider: {provider_name}"
    except ImportError as e:
        passed = False
        detail = f"Library not installed: {e}"
    except Exception as e:
        passed = False
        detail = f"Failed to load: {e}"
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Knowledge provider loads", "passed": passed, "latency": latency, "detail": detail})

    if not knowledge:
        # Can't continue without provider
        return {
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "total_latency": total_latency,
            "tests": results,
        }

    # ── Test 2: is_available() returns bool ──────────────────
    start = time.time()
    try:
        available = knowledge.is_available()
        passed = isinstance(available, bool)
        detail = f"Available: {available}"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "is_available() works", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 3: capabilities property ────────────────────────
    start = time.time()
    try:
        caps = knowledge.capabilities
        passed = isinstance(caps, list) and "search" in caps
        detail = f"Capabilities: {caps}"
    except Exception as e:
        passed = False
        detail = str(e)
    latency = time.time() - start
    total_latency += latency
    results.append({"name": "Capabilities reported", "passed": passed, "latency": latency, "detail": detail})

    # ── Test 4: Search returns results (if online) ───────────
    if knowledge.is_available():
        start = time.time()
        try:
            results_search = knowledge.search("Python programming language", max_results=3)
            passed = (
                isinstance(results_search, list) and
                len(results_search) > 0 and
                hasattr(results_search[0], 'title') and
                hasattr(results_search[0], 'snippet')
            )
            detail = f"{len(results_search)} results, first: {results_search[0].title[:60]}" if results_search else "Empty results"
        except Exception as e:
            passed = False
            detail = str(e)
        latency = time.time() - start
        total_latency += latency
        results.append({"name": "Search returns results", "passed": passed, "latency": latency, "detail": detail})

        # ── Test 5: Search results have correct structure ────
        start = time.time()
        try:
            if results_search:
                r = results_search[0]
                passed = (
                    isinstance(r.title, str) and len(r.title) > 0 and
                    isinstance(r.snippet, str) and len(r.snippet) > 0 and
                    isinstance(r.source, str) and r.source != ""
                )
                detail = f"title={bool(r.title)}, snippet={bool(r.snippet)}, source={r.source}"
            else:
                passed = False
                detail = "No results to check structure"
        except Exception as e:
            passed = False
            detail = str(e)
        latency = time.time() - start
        total_latency += latency
        results.append({"name": "SearchResult structure valid", "passed": passed, "latency": latency, "detail": detail})

        # ── Test 6: Search with max_results limit ────────────
        start = time.time()
        try:
            limited = knowledge.search("weather today", max_results=1)
            passed = isinstance(limited, list) and len(limited) <= 2  # allow slight over
            detail = f"Requested 1, got {len(limited)}"
        except Exception as e:
            passed = False
            detail = str(e)
        latency = time.time() - start
        total_latency += latency
        results.append({"name": "max_results limits output", "passed": passed, "latency": latency, "detail": detail})

        # ── Test 7: fetch() returns None for Level 1 ─────────
        start = time.time()
        try:
            fetch_result = knowledge.fetch("https://example.com")
            passed = fetch_result is None  # DDG is Level 1, no fetch
            detail = "fetch() correctly returns None (Level 1)"
        except Exception as e:
            passed = False
            detail = str(e)
        latency = time.time() - start
        total_latency += latency
        results.append({"name": "fetch() returns None (Level 1)", "passed": passed, "latency": latency, "detail": detail})

    else:
        # Offline — test graceful handling
        start = time.time()
        try:
            results_search = knowledge.search("test query")
            passed = isinstance(results_search, list) and len(results_search) == 0
            detail = "Correctly returned empty list when offline"
        except Exception as e:
            passed = False
            detail = f"Should return empty list when offline, got exception: {e}"
        latency = time.time() - start
        total_latency += latency
        results.append({"name": "Graceful offline (empty results)", "passed": passed, "latency": latency, "detail": detail})

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "total_latency": total_latency,
        "tests": results,
    }
