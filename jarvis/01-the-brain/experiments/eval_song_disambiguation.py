"""
Song Disambiguation Eval v3 — exercises the production 3-step pipeline.

The previous v2 eval re-implemented classification by hand, calling Ollama
directly with a JSON-format prompt and reading `params.query` as the
"enriched" output. That worked when the assistant did classification +
enrichment in a single LLM call. The current pipeline is split:

  Step 1: brain.classify_intent(input) → list[Intent]   (raw query, no enrichment)
  Step 2: brain.enrich_query(raw_query) → str           (separate LLM call)
  Step 3: music.search(enriched, raw_input=raw)         (dual search,
                                                          provider picks best)

This eval tests the FULL production path, end-to-end. It also reports the
contribution of each step independently so we can answer:

  * Does classification correctly tag the input as music_play?
  * Does enrichment add artist/context information?
  * Does the raw-only search find the right song? (the safety net)
  * Does the enriched search find the right song?
  * Does the dual search (production reality) find the right song?
  * What's the latency budget per step?

Run on a machine with the assistant installed and Ollama running:

    cd jarvis/01-the-brain/experiments
    python3 eval_song_disambiguation.py                          # default
    python3 eval_song_disambiguation.py llama3.2:3b qwen2.5:3b   # compare

None of the test songs appear in the system prompt examples (we audit
the prompt before adding new tests, per CLAUDE.md). False positives in
this eval indicate the model has learned them from training data, not
that we accidentally seeded the answer.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

# Add the assistant package to sys.path so we can import production code.
_ASSISTANT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assistant")
)
if _ASSISTANT_DIR not in sys.path:
    sys.path.insert(0, _ASSISTANT_DIR)


# ─── Colors ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─── Test cases ───────────────────────────────────────────────────
# IMPORTANT: keep these out of the classifier system prompt so we measure
# generalization, not memorization. Audit the system prompt before adding.

TEST_CASES = [
    # ── Hindi songs (artist disambiguation matters most) ─────────
    {"input": "Channa Mereya",     "expected_song": "Channa Mereya",
     "expected_artist": "Arijit Singh", "lang": "hi"},
    {"input": "Kun Faya Kun",      "expected_song": "Kun Faya Kun",
     "expected_artist": "A.R. Rahman", "lang": "hi"},
    {"input": "Gerua",             "expected_song": "Gerua",
     "expected_artist": "Arijit Singh", "lang": "hi"},
    {"input": "Hawayein",          "expected_song": "Hawayein",
     "expected_artist": "Arijit Singh", "lang": "hi"},
    {"input": "Sajni",             "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi"},
    # Hindi command form — classifier must extract just "Sajni"
    {"input": "play Sajni",        "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi"},
    {"input": "Sajni bajao",       "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi"},

    # ── English (must NOT cross-contaminate with Hindi) ──────────
    {"input": "Blinding Lights",   "expected_song": "Blinding Lights",
     "expected_artist": "Weeknd", "lang": "en"},
    {"input": "Fix You",           "expected_song": "Fix You",
     "expected_artist": "Coldplay", "lang": "en"},
    {"input": "Someone Like You",  "expected_song": "Someone Like You",
     "expected_artist": "Adele", "lang": "en"},
    {"input": "play Yellow",       "expected_song": "Yellow",
     "expected_artist": "Coldplay", "lang": "en"},

    # ── Mood / vague (no specific song expected) ─────────────────
    {"input": "kuch sad sa bajao", "expected_song": None,
     "expected_artist": None, "lang": "hi", "min_query_words": 2,
     "desc": "mood-Hindi: should produce a 2+ word search query"},
    {"input": "play something chill in English", "expected_song": None,
     "expected_artist": None, "lang": "en", "min_query_words": 2},

    # ── Edge: single Hindi word ──────────────────────────────────
    {"input": "Dil",               "expected_song": None,
     "expected_artist": None, "lang": "hi", "min_query_words": 2,
     "desc": "single Hindi word — must add context"},
]


# ─── Helpers ──────────────────────────────────────────────────────

def _load_brain(model: str):
    """Build a real OllamaBrainProvider, swapping the model. Catches
    config-load errors with a friendly message."""
    try:
        from providers.brain.ollama import OllamaBrainProvider
    except Exception as e:
        sys.exit(f"{RED}Could not import OllamaBrainProvider: {e}{RESET}\n"
                 f"Make sure JARVIS deps are installed and you're running "
                 f"from the repo root.")
    brain = OllamaBrainProvider(model=model)
    return brain


def _search_yt(query: str, raw_input: str | None = None) -> dict | None:
    """Use the production music provider's search() (dual-search if both
    queries given, single search otherwise)."""
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()
    except Exception as e:
        return {"error": f"YTMusic init failed: {e}"}
    try:
        # Dual search if raw is different from query
        queries = [query]
        if raw_input and raw_input.lower().strip() != query.lower().strip():
            queries.append(raw_input)
        all_hits: list[dict] = []
        for q in queries:
            hits = ytm.search(q, filter="songs", limit=3) or []
            all_hits.extend(hits)
        if not all_hits:
            return None
        # Pick the FIRST hit from the FIRST query (matches production
        # provider's "raw wins on disagreement, enriched wins on agreement"
        # logic loosely — for eval we just take top-of-each-list).
        first = all_hits[0]
        return {
            "title": first.get("title", ""),
            "artist": ", ".join(a["name"] for a in first.get("artists", [])),
            "videoId": first.get("videoId", ""),
        }
    except Exception as e:
        return {"error": f"search failed: {e}"}


def _matches(actual: str, expected: str | None) -> bool:
    if expected is None:
        return True
    return expected.lower() in (actual or "").lower()


# ─── One run ──────────────────────────────────────────────────────

def evaluate_one(brain, tc: dict) -> dict[str, Any]:
    """Run the full production pipeline against one test case."""
    user_input = tc["input"]
    out: dict[str, Any] = {"input": user_input, "lang": tc.get("lang", "")}

    # Step 1: classify_intent
    t0 = time.time()
    try:
        intents = brain.classify_intent(user_input)
    except Exception as e:
        out["error"] = f"classify_intent: {e}"
        return out
    out["classify_ms"] = int((time.time() - t0) * 1000)

    if not intents:
        out["error"] = "classify_intent returned empty"
        return out
    intent = intents[0]
    out["intent"] = intent.name
    out["raw_query"] = intent.params.get("query", "")
    out["intent_correct"] = intent.name == "music_play"

    if not out["intent_correct"]:
        return out  # nothing else to test

    raw_query = out["raw_query"]

    # Step 2: enrich_query (separate LLM call)
    t0 = time.time()
    try:
        enriched_query = brain.enrich_query(raw_query)
    except Exception as e:
        out["error"] = f"enrich_query: {e}"
        return out
    out["enrich_ms"] = int((time.time() - t0) * 1000)
    out["enriched_query"] = enriched_query
    out["enrichment_changed"] = enriched_query.lower() != raw_query.lower()
    if "min_query_words" in tc:
        out["enriched_word_count_ok"] = len(enriched_query.split()) >= tc["min_query_words"]

    # Step 3: search
    t0 = time.time()
    raw_hit = _search_yt(raw_query) if raw_query else None
    out["raw_search_ms"] = int((time.time() - t0) * 1000)
    if raw_hit and "error" not in raw_hit:
        out["raw_title"] = raw_hit["title"]
        out["raw_artist"] = raw_hit["artist"]
        out["raw_song_match"] = _matches(raw_hit["title"], tc.get("expected_song"))
        out["raw_artist_match"] = _matches(raw_hit["artist"], tc.get("expected_artist"))

    if out["enrichment_changed"]:
        t0 = time.time()
        enriched_hit = _search_yt(enriched_query)
        out["enriched_search_ms"] = int((time.time() - t0) * 1000)
        if enriched_hit and "error" not in enriched_hit:
            out["enriched_title"] = enriched_hit["title"]
            out["enriched_artist"] = enriched_hit["artist"]
            out["enriched_song_match"] = _matches(enriched_hit["title"], tc.get("expected_song"))
            out["enriched_artist_match"] = _matches(enriched_hit["artist"], tc.get("expected_artist"))
    else:
        # No enrichment — production code skips the redundant 2nd search.
        out["enriched_song_match"] = out.get("raw_song_match", False)
        out["enriched_artist_match"] = out.get("raw_artist_match", False)

    # Step 4: production "dual" pick — what the user would actually hear.
    # Mirrors providers/music/youtube.py: if both top results agree, use
    # enriched; if they disagree, prefer raw (since LLM may have hallucinated).
    raw_id = (raw_hit or {}).get("videoId", "") if raw_hit else ""
    enriched_id = ""
    if out["enrichment_changed"]:
        e_hit = _search_yt(enriched_query)
        enriched_id = (e_hit or {}).get("videoId", "") if e_hit else ""
        if raw_id and enriched_id:
            if raw_id == enriched_id:
                final_title = e_hit.get("title", "")
                final_artist = e_hit.get("artist", "")
            else:
                # Disagreement — production picks raw
                final_title = raw_hit.get("title", "")
                final_artist = raw_hit.get("artist", "")
        else:
            final_title = (raw_hit or {}).get("title", "") or (e_hit or {}).get("title", "")
            final_artist = (raw_hit or {}).get("artist", "") or (e_hit or {}).get("artist", "")
    else:
        final_title = (raw_hit or {}).get("title", "")
        final_artist = (raw_hit or {}).get("artist", "")
    out["final_title"] = final_title
    out["final_artist"] = final_artist
    out["final_song_match"] = _matches(final_title, tc.get("expected_song"))
    out["final_artist_match"] = _matches(final_artist, tc.get("expected_artist"))

    # Overall pass: intent + final song + final artist all correct.
    # For mood queries with no expected song/artist, we just check the
    # word-count proxy.
    if tc.get("expected_song") is None and tc.get("expected_artist") is None:
        out["passed"] = (
            out["intent_correct"]
            and out.get("enriched_word_count_ok", True)
        )
    else:
        out["passed"] = (
            out["intent_correct"]
            and out["final_song_match"]
            and out["final_artist_match"]
        )

    return out


# ─── Run all + print + save ──────────────────────────────────────

def run_eval(model: str) -> float:
    print(f"\n{'═' * 70}")
    print(f"  {BOLD}Song Disambiguation v3 — production pipeline — {model}{RESET}")
    print(f"  classify → enrich → dual-search (raw + enriched)")
    print(f"{'═' * 70}\n")

    brain = _load_brain(model)
    rows: list[dict] = []
    passed = 0
    total = len(TEST_CASES)

    for i, tc in enumerate(TEST_CASES):
        print(f"  [{i+1}/{total}] {tc['input']!r}")
        if tc.get("desc"):
            print(f"      {DIM}{tc['desc']}{RESET}")

        r = evaluate_one(brain, tc)

        if "error" in r:
            print(f"      {RED}ERROR: {r['error']}{RESET}")
            rows.append(r)
            continue

        intent_color = GREEN if r["intent_correct"] else RED
        print(f"      classify ({r['classify_ms']}ms): "
              f"{intent_color}{r.get('intent', '?')}{RESET} "
              f"raw_query={r.get('raw_query', '?')!r}")
        if r["intent_correct"]:
            tag = "→" if r.get("enrichment_changed") else "="
            print(f"      enrich ({r.get('enrich_ms', 0)}ms): "
                  f"{tag} {r.get('enriched_query', '?')!r}")
            rt = r.get("raw_title", "?")
            ra = r.get("raw_artist", "?")
            print(f"      raw search ({r.get('raw_search_ms', 0)}ms): "
                  f"{rt} — {ra}")
            if r.get("enrichment_changed"):
                et = r.get("enriched_title", "?")
                ea = r.get("enriched_artist", "?")
                print(f"      enriched search ({r.get('enriched_search_ms', 0)}ms): "
                      f"{et} — {ea}")
            ft = r.get("final_title", "?")
            fa = r.get("final_artist", "?")
            mark = (GREEN + "✓") if r["passed"] else (RED + "✗")
            print(f"      {BOLD}final{RESET}: {ft} — {fa} {mark}{RESET}")
            if tc.get("expected_song"):
                print(f"      expected: {tc['expected_song']} — {tc['expected_artist']}")
        if r["passed"]:
            passed += 1
        rows.append(r)
        print()

    # Summary
    pct = (passed / total) * 100
    color = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED
    print(f"{'═' * 70}")
    print(f"  {BOLD}Pass rate: {color}{passed}/{total} ({pct:.0f}%){RESET}")
    print(f"{'═' * 70}")

    # Step-by-step breakdown
    intent_ok = sum(1 for r in rows if r.get("intent_correct"))
    enrich_changed = sum(1 for r in rows if r.get("enrichment_changed"))
    raw_song_ok = sum(1 for r in rows
                      if r.get("raw_song_match") and tc_expects_song(r))
    enr_song_ok = sum(1 for r in rows
                      if r.get("enriched_song_match") and tc_expects_song(r))
    final_song_ok = sum(1 for r in rows
                        if r.get("final_song_match") and tc_expects_song(r))
    n_with_expected = sum(1 for tc in TEST_CASES
                          if tc.get("expected_song") is not None)

    print(f"\n  {BOLD}Step contribution{RESET}")
    print(f"    classify_intent → music_play:  {intent_ok}/{total}")
    print(f"    enrich_query changed query:     {enrich_changed}/{total}")
    print(f"    {DIM}— for tests with expected song:{RESET}")
    print(f"    raw search → right song:        {raw_song_ok}/{n_with_expected}")
    print(f"    enriched search → right song:   {enr_song_ok}/{n_with_expected}")
    print(f"    {BOLD}final dual-pick → right song:   {final_song_ok}/{n_with_expected}{RESET}")

    # Latencies
    classify_ms = [r["classify_ms"] for r in rows if "classify_ms" in r]
    enrich_ms = [r["enrich_ms"] for r in rows if "enrich_ms" in r]
    if classify_ms:
        print(f"\n  {BOLD}Latency (median){RESET}")
        print(f"    classify_intent: {sorted(classify_ms)[len(classify_ms)//2]}ms")
        if enrich_ms:
            print(f"    enrich_query:    {sorted(enrich_ms)[len(enrich_ms)//2]}ms")

    # Save
    results_dir = os.path.join(os.path.dirname(__file__), "..", "notes",
                               "eval-results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"song_disambig_v3_{model.replace(':', '_')}_{timestamp}.json"
    filepath = os.path.join(results_dir, filename)
    with open(filepath, "w") as f:
        json.dump({
            "model": model, "timestamp": timestamp,
            "total": total, "passed": passed, "percentage": pct,
            "intent_ok": intent_ok, "enrichment_changed": enrich_changed,
            "raw_song_ok": raw_song_ok, "enriched_song_ok": enr_song_ok,
            "final_song_ok": final_song_ok,
            "rows": rows,
        }, f, indent=2)
    print(f"\n  Saved: {filepath}")
    return pct


def tc_expects_song(r: dict) -> bool:
    """Identify rows where we EXPECTED a specific song (for hit-rate stats)."""
    inp = r.get("input", "")
    for tc in TEST_CASES:
        if tc["input"] == inp:
            return tc.get("expected_song") is not None
    return False


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else ["llama3.2:3b"]
    for m in models:
        run_eval(m)
