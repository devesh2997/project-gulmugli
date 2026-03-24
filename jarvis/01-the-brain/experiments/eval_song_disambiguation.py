"""
Song Disambiguation Eval v2 — Tests the FULL pipeline, not just the LLM.

The previous eval tested whether the LLM produced the exact right movie name.
That was the wrong test. What matters is: does the user hear the right song?

Pipeline:  User input → LLM enriches query → YouTube Music search → Result

This eval tests:
  1. Did the LLM classify intent correctly? (should be music_play)
  2. Did the LLM enrich the query beyond the bare input? (added artist/context?)
  3. Does the enriched query find the RIGHT SONG on YouTube Music? (the real test)

None of the test songs appear in the system prompt examples.

Usage:
    python eval_song_disambiguation.py                         # default: llama3.2:3b
    python eval_song_disambiguation.py qwen2.5:3b              # specific model
    python eval_song_disambiguation.py llama3.2:3b qwen2.5:3b  # compare
"""

import requests
import json
import sys
import time
import os

# ─── Colours ─────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


# ─── Test Cases ──────────────────────────────────────────────
# NONE of these songs appear as examples in the system prompt.
# expected_song and expected_artist are checked against YouTube Music's
# top result — case-insensitive substring match.

TEST_CASES = [
    # ── Hindi songs (known artists) ──────────────────────────
    {
        "input": "Channa Mereya",
        "expected_song": "Channa Mereya",
        "expected_artist": "Arijit Singh",
        "description": "Hindi: Arijit hit from ADHM",
    },
    {
        "input": "Kun Faya Kun",
        "expected_song": "Kun Faya Kun",
        "expected_artist": "A.R. Rahman",
        "description": "Hindi: AR Rahman classic from Rockstar",
    },
    {
        "input": "Gerua",
        "expected_song": "Gerua",
        "expected_artist": "Arijit Singh",
        "description": "Hindi: Dilwale hit",
    },
    {
        "input": "Hawayein",
        "expected_song": "Hawayein",
        "expected_artist": "Arijit Singh",
        "description": "Hindi: Jab Harry Met Sejal",
    },
    {
        "input": "Sajni",
        "expected_song": "Sajni",
        "expected_artist": "Arijit Singh",
        "description": "Hindi: Laapata Ladies — the original use case",
    },

    # ── English songs (must NOT get Hindi artists) ───────────
    {
        "input": "Blinding Lights",
        "expected_song": "Blinding Lights",
        "expected_artist": "Weeknd",
        "description": "English: The Weeknd megahit — should NOT add Arijit Singh",
    },
    {
        "input": "Fix You",
        "expected_song": "Fix You",
        "expected_artist": "Coldplay",
        "description": "English: Coldplay classic",
    },
    {
        "input": "Someone Like You",
        "expected_song": "Someone Like You",
        "expected_artist": "Adele",
        "description": "English: Adele — not in favorites but very famous",
    },
    {
        "input": "Bohemian Rhapsody",
        "expected_song": "Bohemian Rhapsody",
        "expected_artist": "Queen",
        "description": "English: Queen — universally known, tests non-favorite artist",
    },
    {
        "input": "Viva La Vida",
        "expected_song": "Viva La Vida",
        "expected_artist": "Coldplay",
        "description": "English: Coldplay — favorite artist",
    },

    # ── Hindi songs by non-favorite artists ──────────────────
    {
        "input": "Bekhayali",
        "expected_song": "Bekhayali",
        "expected_artist": None,  # Sachet Tandon — not famous enough for LLM to know
        "description": "Hindi: Kabir Singh — not by a favorite artist",
    },
    {
        "input": "Kala Chashma",
        "expected_song": "Kala Chashma",
        "expected_artist": None,  # Badshah/Neha Kakkar
        "description": "Hindi: party hit — not by a favorite artist",
    },

    # ── Vague/mood requests ──────────────────────────────────
    {
        "input": "kuch romantic sa bajao",
        "expected_song": None,
        "expected_artist": None,
        "min_query_words": 2,
        "description": "Hindi mood: should produce genre + language keywords",
    },
    {
        "input": "play something chill in English",
        "expected_song": None,
        "expected_artist": None,
        "min_query_words": 2,
        "description": "English mood: should NOT add Hindi artists",
    },

    # ── Edge: single word ────────────────────────────────────
    {
        "input": "Dil",
        "expected_song": None,
        "expected_artist": None,
        "min_query_words": 2,
        "description": "Single Hindi word — must add context",
    },
]


def call_ollama(model: str, user_input: str, endpoint: str = "http://localhost:11434") -> dict:
    """Call Ollama with the assistant's actual system prompt."""
    # Import the real system prompt builder
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "assistant"))
    try:
        from providers.brain.ollama import _build_system_prompt
        system_prompt = _build_system_prompt()
    except Exception as e:
        print(f"  {RED}Could not load system prompt: {e}{RESET}")
        system_prompt = "Classify requests as JSON. Add artist names to music queries."
    finally:
        if sys.path[0].endswith("assistant"):
            sys.path.pop(0)

    payload = {
        "model": model,
        "prompt": user_input,
        "system": system_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3},
    }

    start = time.time()
    resp = requests.post(f"{endpoint}/api/generate", json=payload)
    latency = time.time() - start

    data = resp.json()
    text = data.get("response", "").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"error": "json_parse_failed", "raw": text}

    eval_count = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 1)
    tok_per_sec = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0

    return {
        "parsed": parsed,
        "latency": latency,
        "tok_per_sec": tok_per_sec,
    }


def search_youtube_music(query: str) -> dict | None:
    """Search YouTube Music and return the top result."""
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()
        results = ytm.search(query, filter="songs", limit=1)
        if results:
            r = results[0]
            return {
                "title": r.get("title", ""),
                "artist": ", ".join(a["name"] for a in r.get("artists", [])),
                "videoId": r.get("videoId", ""),
            }
    except Exception as e:
        return {"error": str(e)}
    return None


def evaluate(tc: dict, llm_result: dict, yt_result: dict | None) -> dict:
    """Evaluate a single test case across the full pipeline."""
    parsed = llm_result["parsed"]
    query = parsed.get("params", {}).get("query", "")
    intent = parsed.get("intent", "")

    checks = {
        "intent_correct": intent == "music_play",
        "query": query,
        "query_enriched": len(query.split()) > len(tc["input"].split()),
        "yt_title": "",
        "yt_artist": "",
        "song_found": False,
        "artist_found": False,
    }

    # Check min_query_words if specified
    if "min_query_words" in tc:
        checks["query_enriched"] = len(query.split()) >= tc["min_query_words"]

    if yt_result and "error" not in yt_result:
        checks["yt_title"] = yt_result.get("title", "")
        checks["yt_artist"] = yt_result.get("artist", "")

        # Did YouTube Music find the right song?
        if tc["expected_song"]:
            checks["song_found"] = tc["expected_song"].lower() in checks["yt_title"].lower()
        else:
            checks["song_found"] = True  # no specific song expected

        # Did it find the right artist?
        if tc["expected_artist"]:
            checks["artist_found"] = tc["expected_artist"].lower() in checks["yt_artist"].lower()
        else:
            checks["artist_found"] = True  # no specific artist expected

    # Overall: intent correct + enriched + right song on YouTube
    checks["passed"] = (
        checks["intent_correct"]
        and checks["query_enriched"]
        and checks["song_found"]
        and checks["artist_found"]
    )

    return checks


def run_eval(model: str):
    """Run full pipeline eval."""
    print(f"\n{'═' * 70}")
    print(f"  {BOLD}Song Disambiguation v2 — Full Pipeline — {model}{RESET}")
    print(f"  Tests: LLM enrichment → YouTube Music search → correct song?")
    print(f"{'═' * 70}\n")

    results = []
    passed = 0
    total = len(TEST_CASES)

    for i, tc in enumerate(TEST_CASES):
        print(f"  [{i+1}/{total}] \"{tc['input']}\"")
        print(f"    {DIM}{tc['description']}{RESET}")

        # Step 1: LLM
        llm_result = call_ollama(model, tc["input"])
        query = llm_result["parsed"].get("params", {}).get("query", "")
        print(f"    LLM query: \"{query}\"")

        # Step 2: YouTube Music search with the LLM's enriched query
        yt_result = search_youtube_music(query) if query else None

        if yt_result and "error" not in yt_result:
            print(f"    YT result: \"{yt_result['title']}\" — {yt_result['artist']}")
        else:
            print(f"    {RED}YT search failed{RESET}")

        # Step 3: Evaluate
        checks = evaluate(tc, llm_result, yt_result)

        status_parts = []
        if not checks["intent_correct"]:
            status_parts.append(f"{RED}wrong intent{RESET}")
        if not checks["query_enriched"]:
            status_parts.append(f"{RED}not enriched{RESET}")
        if not checks["song_found"]:
            expected = tc.get("expected_song", "?")
            status_parts.append(f"{RED}wrong song (wanted: {expected}){RESET}")
        if not checks["artist_found"]:
            expected = tc.get("expected_artist", "?")
            status_parts.append(f"{RED}wrong artist (wanted: {expected}){RESET}")

        if checks["passed"]:
            print(f"    {GREEN}✓ PASS{RESET} ({llm_result['latency']:.1f}s)")
            passed += 1
        else:
            print(f"    {RED}✗ FAIL: {', '.join(status_parts)}{RESET}")

        print()

        results.append({
            "input": tc["input"],
            "description": tc["description"],
            "expected_song": tc.get("expected_song"),
            "expected_artist": tc.get("expected_artist"),
            "llm_query": query,
            "yt_title": checks.get("yt_title", ""),
            "yt_artist": checks.get("yt_artist", ""),
            "intent_correct": checks["intent_correct"],
            "query_enriched": checks["query_enriched"],
            "song_found": checks["song_found"],
            "artist_found": checks["artist_found"],
            "passed": checks["passed"],
            "latency": llm_result["latency"],
        })

    # Summary
    pct = (passed / total) * 100
    color = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED
    print(f"{'═' * 70}")
    print(f"  {BOLD}Results: {color}{passed}/{total} passed ({pct:.0f}%){RESET}")
    print(f"{'═' * 70}")

    # Breakdown: enrichment vs final accuracy
    enriched = sum(1 for r in results if r["query_enriched"])
    song_correct = sum(1 for r in results if r["song_found"])
    artist_correct = sum(1 for r in results if r["artist_found"])
    print(f"  Query enriched:       {enriched}/{total} ({enriched/total*100:.0f}%)")
    print(f"  Correct song on YT:   {song_correct}/{total} ({song_correct/total*100:.0f}%)")
    print(f"  Correct artist on YT: {artist_correct}/{total} ({artist_correct/total*100:.0f}%)")

    # Also show: what if we searched with the RAW input (no LLM enrichment)?
    print(f"\n  {BOLD}Baseline: raw input → YouTube Music (no LLM){RESET}")
    baseline_song = 0
    baseline_artist = 0
    for tc in TEST_CASES:
        if tc.get("expected_song") is None and tc.get("expected_artist") is None:
            continue
        raw_result = search_youtube_music(tc["input"])
        if raw_result and "error" not in raw_result:
            if tc.get("expected_song") and tc["expected_song"].lower() in raw_result["title"].lower():
                baseline_song += 1
            elif not tc.get("expected_song"):
                baseline_song += 1
            if tc.get("expected_artist") and tc["expected_artist"].lower() in raw_result["artist"].lower():
                baseline_artist += 1
            elif not tc.get("expected_artist"):
                baseline_artist += 1
            print(f"    \"{tc['input']}\" → \"{raw_result['title']}\" — {raw_result['artist']}")

    print(f"  Baseline correct song:   {baseline_song}/{total}")
    print(f"  Baseline correct artist: {baseline_artist}/{total}")
    print(f"\n  {CYAN}LLM enrichment {'helps' if song_correct > baseline_song else 'does not help'} vs raw search.{RESET}")

    # Save
    results_dir = os.path.join(os.path.dirname(__file__), "..", "notes", "eval-results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"song_disambig_v2_{model.replace(':', '_')}_{timestamp}.json"
    filepath = os.path.join(results_dir, filename)

    with open(filepath, "w") as f:
        json.dump({
            "model": model,
            "timestamp": timestamp,
            "total": total,
            "passed": passed,
            "percentage": pct,
            "enriched": enriched,
            "song_correct": song_correct,
            "artist_correct": artist_correct,
            "results": results,
        }, f, indent=2)

    print(f"\n  Results saved to: {filepath}")
    return pct


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else ["llama3.2:3b"]
    for model in models:
        run_eval(model)
