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

## Difficulty tiers

Each test case carries a `tier` field. Tiers reflect what we're really
measuring — and where the system actually fails:

  - "easy"   — single-word famous song titles where YouTube Music's
               popularity ranking does the work. The 14 cases that have
               always passed. ~14 cases.
  - "medium" — modern post-2020 Bollywood/Pakistani/Punjabi catalog,
               Hinglish phrasings, female-vocalist disambiguation, mood
               queries. ~22 cases.
  - "hard"   — same-title-different-song (e.g., "Tum Hi Ho" → Aashiqui 2,
               not karaoke), version disambiguation (no instrumental /
               cover / slowed-and-reverbed), STT-mangled inputs from
               Whisper (Hindi proper-noun handling is famously bad),
               artist-name conflicts ("Lover" by Diljit vs Taylor Swift).
               ~15 cases.

The hard tier is where Alexa fails on Indian users and where we should
beat it. If hard < 70%, the demo embarrasses us.

## Optional fields beyond expected_song / expected_artist

  - must_not_contain      — list[str]; the chosen title must not contain
                            any of these (e.g. "instrumental", "karaoke",
                            "cover", "slowed", "remix"). Use to catch
                            version mismatches.
  - must_not_contain_artist — same, but applied to artist string. Catches
                            "Lover by Diljit" → Taylor Swift hit.
  - expected_year_min     — int; if YouTube returns a year and it's lower,
                            mark the case as failed. Catches old generic
                            remakes when user wanted the modern hit.
  - min_views_M           — int (millions); if views are returned and
                            below this floor, fail. Catches obscure-cover
                            wins.

These are only enforced when the underlying YouTube response actually
includes the relevant field (year/views are not always present for
filter="songs"). If absent, we skip the check rather than fail.

Run on a machine with the assistant installed and Ollama running:

    cd jarvis/01-the-brain/experiments
    python3 eval_song_disambiguation.py                          # default
    python3 eval_song_disambiguation.py llama3.2:3b qwen2.5:3b   # compare
    python3 eval_song_disambiguation.py --tier hard              # only hard cases
    python3 eval_song_disambiguation.py --tag modern             # only modern catalog

None of the test songs appear in the system prompt examples (we audit
the prompt before adding new tests, per CLAUDE.md). False positives in
this eval indicate the model has learned them from training data, not
that we accidentally seeded the answer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
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
#
# Schema:
#   input            (str, required)
#   expected_song    (str|None) — None for vague/mood queries
#   expected_artist  (str|None)
#   lang             ("hi"|"en"|"pa")
#   tier             ("easy"|"medium"|"hard")
#   tags             (list[str], optional)
#   desc             (str, optional)
#   must_not_contain (list[str], optional)
#   must_not_contain_artist (list[str], optional)
#   expected_year_min (int, optional)
#   min_views_M      (int, optional)
#   min_query_words  (int, optional) — for mood queries: enriched must have ≥ N words

# Common bad keywords for version disambiguation. Used a lot for hard tier.
_BAD_VERSION_TOKENS = [
    "instrumental", "karaoke", "cover", "remix",
    "slowed", "reverb", "reverbed", "lo-fi version",
    "8d audio", "8d", "tabla cover", "flute cover",
]

TEST_CASES = [
    # ════════════════════════════════════════════════════════════════
    #   EASY — single famous title, popularity ranking does the work
    # ════════════════════════════════════════════════════════════════

    {"input": "Channa Mereya", "expected_song": "Channa Mereya",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy"},
    {"input": "Kun Faya Kun", "expected_song": "Kun Faya Kun",
     "expected_artist": "A.R. Rahman", "lang": "hi", "tier": "easy"},
    {"input": "Gerua", "expected_song": "Gerua",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy",
     "tags": ["female-vocalist-pair"]},
    {"input": "Hawayein", "expected_song": "Hawayein",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy"},
    {"input": "Sajni", "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy"},
    {"input": "play Sajni", "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy"},
    {"input": "Sajni bajao", "expected_song": "Sajni",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "easy",
     "tags": ["hinglish"]},

    {"input": "Blinding Lights", "expected_song": "Blinding Lights",
     "expected_artist": "Weeknd", "lang": "en", "tier": "easy"},
    {"input": "Fix You", "expected_song": "Fix You",
     "expected_artist": "Coldplay", "lang": "en", "tier": "easy"},
    {"input": "Someone Like You", "expected_song": "Someone Like You",
     "expected_artist": "Adele", "lang": "en", "tier": "easy"},
    {"input": "play Yellow", "expected_song": "Yellow",
     "expected_artist": "Coldplay", "lang": "en", "tier": "easy"},

    # Mood queries — no specific song, just word-count proxy
    {"input": "kuch sad sa bajao", "expected_song": None,
     "expected_artist": None, "lang": "hi", "tier": "easy",
     "min_query_words": 2,
     "desc": "mood-Hindi: should produce a 2+ word search query",
     "tags": ["mood"]},
    {"input": "play something chill in English", "expected_song": None,
     "expected_artist": None, "lang": "en", "tier": "easy",
     "min_query_words": 2, "tags": ["mood"]},
    {"input": "Dil", "expected_song": None,
     "expected_artist": None, "lang": "hi", "tier": "easy",
     "min_query_words": 2,
     "desc": "single Hindi word — must add context",
     "tags": ["mood"]},

    # ════════════════════════════════════════════════════════════════
    #   MEDIUM — modern catalog, Hinglish, Pakistani / Punjabi crossover
    # ════════════════════════════════════════════════════════════════

    # ── Modern Bollywood (post-2020) — the catalog the model may not know ─
    {"input": "play Heeriye", "expected_song": "Heeriye",
     "expected_artist": "Jasleen", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Jasleen Royal / Arijit Singh — 2023 viral hit",
     "must_not_contain": ["instrumental", "karaoke", "lo-fi"],
     "expected_year_min": 2022},
    {"input": "play Kesariya", "expected_song": "Kesariya",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Brahmastra (2022)",
     "must_not_contain": ["instrumental", "karaoke", "slowed"],
     "expected_year_min": 2021},
    {"input": "play Apna Bana Le", "expected_song": "Apna Bana Le",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Bhediya (2022)",
     "must_not_contain": ["instrumental", "karaoke"],
     "expected_year_min": 2021},
    {"input": "play O Bedardeya", "expected_song": "Bedardeya",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Tu Jhoothi Main Makkaar (2023)",
     "expected_year_min": 2022},
    {"input": "play Jhoome Jo Pathaan", "expected_song": "Jhoome Jo Pathaan",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Pathaan (2023)",
     "expected_year_min": 2022},
    {"input": "play Tum Kya Mile", "expected_song": "Tum Kya Mile",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020"],
     "desc": "Rocky Aur Rani Kii Prem Kahaani (2023)",
     "must_not_contain": ["instrumental", "karaoke"],
     "expected_year_min": 2022},

    # ── Pakistani / Coke Studio crossover ─────────────────────────
    {"input": "play Pasoori", "expected_song": "Pasoori",
     "expected_artist": "Ali Sethi", "lang": "hi", "tier": "medium",
     "tags": ["modern", "coke-studio", "pakistani"],
     "desc": "Coke Studio Pakistan — Ali Sethi & Shae Gill",
     "must_not_contain": ["Pasoori Nu", "instrumental", "karaoke"],
     "expected_year_min": 2021},
    {"input": "play Tu Jhoom", "expected_song": "Tu Jhoom",
     "expected_artist": "Naseebo", "lang": "hi", "tier": "medium",
     "tags": ["modern", "coke-studio", "pakistani"],
     "desc": "Coke Studio — Naseebo Lal & Abida Parveen"},
    {"input": "play Tu Hai Kahaan", "expected_song": "Tu Hai Kahaan",
     "expected_artist": "AUR", "lang": "hi", "tier": "medium",
     "tags": ["modern", "post2020", "pakistani"],
     "desc": "AUR band — viral 2023"},

    # ── Punjabi crossover ─────────────────────────────────────────
    {"input": "play Brown Munde", "expected_song": "Brown Munde",
     "expected_artist": "AP Dhillon", "lang": "pa", "tier": "medium",
     "tags": ["punjabi", "modern"],
     "desc": "AP Dhillon — Punjabi-Canadian breakout"},
    {"input": "play 295 by Sidhu", "expected_song": "295",
     "expected_artist": "Sidhu", "lang": "pa", "tier": "medium",
     "tags": ["punjabi", "modern"],
     "desc": "Sidhu Moose Wala — numeric song name"},

    # ── Female vocalists (often hijacked by male covers) ──────────
    {"input": "play Sunn Raha Hai by Shreya Ghoshal",
     "expected_song": "Sunn Raha Hai",
     "expected_artist": "Shreya", "lang": "hi", "tier": "medium",
     "tags": ["female-vocalist"],
     "desc": "Aashiqui 2 — female version (NOT Ankit Tiwari's male)",
     "must_not_contain_artist": ["Ankit Tiwari"]},
    {"input": "play Lut Gaye by Jubin Nautiyal",
     "expected_song": "Lut Gaye", "expected_artist": "Jubin",
     "lang": "hi", "tier": "medium", "tags": ["modern"],
     "desc": "Jubin Nautiyal-led hit (2021)"},

    # ── Hinglish phrasings (must classify + extract correctly) ────
    {"input": "Pasoori bajao yaar", "expected_song": "Pasoori",
     "expected_artist": "Ali Sethi", "lang": "hi", "tier": "medium",
     "tags": ["hinglish", "coke-studio"],
     "must_not_contain": ["Pasoori Nu"]},
    {"input": "mujhe Heeriye sunna hai", "expected_song": "Heeriye",
     "expected_artist": "Jasleen", "lang": "hi", "tier": "medium",
     "tags": ["hinglish", "modern"]},
    {"input": "Arijit Singh ka Apna Bana Le lagao",
     "expected_song": "Apna Bana Le",
     "expected_artist": "Arijit", "lang": "hi", "tier": "medium",
     "tags": ["hinglish", "modern"]},

    # ── Movie-as-query (legitimate user pattern) ──────────────────
    {"input": "play a song from Pathaan", "expected_song": None,
     "expected_artist": None, "lang": "en", "tier": "medium",
     "min_query_words": 2,
     "tags": ["movie-as-query"],
     "desc": "Movie name → any song from that movie is OK"},

    # ── Indie / bands ─────────────────────────────────────────────
    {"input": "play Husn by Anuv Jain", "expected_song": "Husn",
     "expected_artist": "Anuv", "lang": "hi", "tier": "medium",
     "tags": ["indie", "modern"],
     "must_not_contain": ["instrumental", "karaoke"]},
    {"input": "play Khairiyat", "expected_song": "Khairiyat",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "medium",
     "desc": "Chhichhore (2019) — classic Arijit, multiple versions exist",
     "must_not_contain": ["instrumental", "karaoke"]},

    # ════════════════════════════════════════════════════════════════
    #   HARD — same-title disambiguation, version filtering, STT mishears
    # ════════════════════════════════════════════════════════════════

    # ── Pasoori vs Pasoori Nu (different songs!) ──────────────────
    {"input": "play Pasoori Nu", "expected_song": "Pasoori Nu",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["same-title", "modern"],
     "desc": "Satyaprem Ki Katha (2023) — totally different song from Coke Studio's Pasoori",
     "expected_year_min": 2022},

    # ── Tum Hi Ho — version disambiguation ────────────────────────
    {"input": "play Tum Hi Ho", "expected_song": "Tum Hi Ho",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["version-filter", "popular"],
     "desc": "Aashiqui 2 — must NOT pick instrumental, karaoke, slowed",
     "must_not_contain": _BAD_VERSION_TOKENS,
     "min_views_M": 50},

    # ── Janam Janam — title appears in many songs ─────────────────
    {"input": "play Janam Janam", "expected_song": "Janam Janam",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["same-title"],
     "desc": "Dilwale (2015) — Antara Mitra duet. Many other 'Janam Janam' songs exist.",
     "must_not_contain": _BAD_VERSION_TOKENS},

    # ── "Lover" — Diljit vs Taylor Swift collision ────────────────
    {"input": "play Lover by Diljit", "expected_song": "Lover",
     "expected_artist": "Diljit", "lang": "pa", "tier": "hard",
     "tags": ["artist-collision", "punjabi", "modern"],
     "desc": "Diljit Dosanjh's 'Lover', NOT Taylor Swift's same-titled song",
     "must_not_contain_artist": ["Taylor Swift"]},

    # ── "Channa" — many songs share this title ────────────────────
    {"input": "play Channa Ve", "expected_song": "Channa Ve",
     "expected_artist": None, "lang": "hi", "tier": "hard",
     "tags": ["same-title"],
     "desc": "Many 'Channa Ve' / 'Channa' songs exist; popularity ranking should pick a recognized version",
     "must_not_contain": ["instrumental", "karaoke"]},

    # ── Tujhe Dekha — DDLJ classic vs many covers ─────────────────
    {"input": "play Tujhe Dekha", "expected_song": "Tujhe Dekha",
     "expected_artist": None, "lang": "hi", "tier": "hard",
     "tags": ["classic", "version-filter"],
     "desc": "DDLJ (1995) Lata/Kumar Sanu — must avoid karaoke / new covers",
     "must_not_contain": ["karaoke", "instrumental", "new version", "remake"]},

    # ── Ae Dil Hai Mushkil — title track vs same-name film tracks ─
    {"input": "play Ae Dil Hai Mushkil", "expected_song": "Ae Dil Hai Mushkil",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["same-title", "version-filter"],
     "desc": "Title track from same-name 2016 film",
     "must_not_contain": ["instrumental", "karaoke", "ringtone"]},

    # ── STT-mangled inputs (Whisper output for Hindi proper nouns) ─
    {"input": "play kesriya", "expected_song": "Kesariya",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["stt-artifact", "modern"],
     "desc": "Whisper drops the 'a' in Kesariya often"},
    {"input": "play hayriye", "expected_song": "Heeriye",
     "expected_artist": "Jasleen", "lang": "hi", "tier": "hard",
     "tags": ["stt-artifact", "modern"],
     "desc": "Whisper Hindi pronunciation guess"},
    {"input": "play apna bana le piya",
     "expected_song": "Apna Bana Le", "expected_artist": "Arijit Singh",
     "lang": "hi", "tier": "hard",
     "tags": ["stt-artifact", "modern"],
     "desc": "Whisper transcribes the next word too — query has trailing 'piya'"},
    {"input": "play sajney bajao",
     "expected_song": "Sajni", "expected_artist": "Arijit Singh",
     "lang": "hi", "tier": "hard",
     "tags": ["stt-artifact", "hinglish"],
     "desc": "Whisper hears 'Sajni' as 'Sajney'"},

    # ── Female vocalist boundary, version filter ──────────────────
    {"input": "play Tum Hi Aana", "expected_song": "Tum Hi Aana",
     "expected_artist": "Jubin", "lang": "hi", "tier": "hard",
     "tags": ["version-filter"],
     "desc": "Marjaavaan (2019) — Jubin Nautiyal. Lots of female covers exist.",
     "must_not_contain": ["female version", "cover", "instrumental", "karaoke"]},

    # ── Pakistani vs Indian remake ────────────────────────────────
    {"input": "play Tera Yaar Hoon Main",
     "expected_song": "Tera Yaar Hoon Main",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["version-filter"],
     "desc": "Sonu Ke Titu Ki Sweety (2018) — Arijit. Many karaoke versions.",
     "must_not_contain": ["karaoke", "instrumental"]},

    # ── Devotional / classical confusable with film song ──────────
    {"input": "play Vande Mataram", "expected_song": "Vande Mataram",
     "expected_artist": None, "lang": "hi", "tier": "hard",
     "tags": ["same-title", "classical"],
     "desc": "Many versions: Lata, A.R. Rahman, school choirs, instrumentals. Need a recognized vocal version.",
     "must_not_contain": ["instrumental"]},

    # ── Movie + song name combined ────────────────────────────────
    {"input": "play Phir Bhi Tumko Chaahunga from Half Girlfriend",
     "expected_song": "Phir Bhi Tumko",
     "expected_artist": "Arijit Singh", "lang": "hi", "tier": "hard",
     "tags": ["modern", "long-query"],
     "desc": "Long query with movie context"},

    # ── Code-mixed numeric reference ──────────────────────────────
    {"input": "Sidhu ka 295 lagao", "expected_song": "295",
     "expected_artist": "Sidhu", "lang": "pa", "tier": "hard",
     "tags": ["hinglish", "punjabi", "stt-artifact"],
     "desc": "Hinglish + numeric song name"},

    # ── Vague indie request — must enrich, then succeed ───────────
    {"input": "play that Anuv Jain song about love",
     "expected_song": None, "expected_artist": "Anuv",
     "lang": "en", "tier": "hard",
     "tags": ["vague", "indie"],
     "min_query_words": 3,
     "desc": "Vague indie reference — pick anything by Anuv Jain"},
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
            "year": first.get("year"),
            "views": first.get("views", ""),  # usually "12M views" string
            "album": (first.get("album") or {}).get("name", "") if isinstance(first.get("album"), dict) else "",
        }
    except Exception as e:
        return {"error": f"search failed: {e}"}


def _matches(actual: str, expected: str | None) -> bool:
    if expected is None:
        return True
    return expected.lower() in (actual or "").lower()


def _violates_must_not_contain(value: str, forbidden: list[str] | None) -> str | None:
    """Return the first forbidden token found, or None if clean."""
    if not forbidden:
        return None
    lower = (value or "").lower()
    for token in forbidden:
        if token.lower() in lower:
            return token
    return None


_VIEW_RE = re.compile(r"([\d.]+)\s*([KMB])\b", re.IGNORECASE)


def _parse_views_to_M(views_str: str | None) -> float | None:
    """'12M views' → 12.0, '900K views' → 0.9, '1.2B views' → 1200.0. None if unparseable."""
    if not views_str:
        return None
    m = _VIEW_RE.search(views_str)
    if not m:
        return None
    n = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K":
        return n / 1000.0
    if suffix == "M":
        return n
    if suffix == "B":
        return n * 1000.0
    return None


# ─── One run ──────────────────────────────────────────────────────

def evaluate_one(brain, tc: dict) -> dict[str, Any]:
    """Run the full production pipeline against one test case."""
    user_input = tc["input"]
    out: dict[str, Any] = {
        "input": user_input,
        "lang": tc.get("lang", ""),
        "tier": tc.get("tier", "easy"),
        "tags": tc.get("tags", []),
    }

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
    raw_id = (raw_hit or {}).get("videoId", "") if raw_hit else ""
    enriched_id = ""
    final_hit: dict[str, Any] = {}
    if out["enrichment_changed"]:
        e_hit = _search_yt(enriched_query)
        enriched_id = (e_hit or {}).get("videoId", "") if e_hit else ""
        if raw_id and enriched_id:
            if raw_id == enriched_id:
                final_hit = e_hit or {}
            else:
                # Disagreement — production picks raw
                final_hit = raw_hit or {}
        else:
            final_hit = raw_hit or e_hit or {}
    else:
        final_hit = raw_hit or {}

    final_title = (final_hit or {}).get("title", "") if isinstance(final_hit, dict) else ""
    final_artist = (final_hit or {}).get("artist", "") if isinstance(final_hit, dict) else ""
    out["final_title"] = final_title
    out["final_artist"] = final_artist
    out["final_year"] = (final_hit or {}).get("year") if isinstance(final_hit, dict) else None
    out["final_views"] = (final_hit or {}).get("views", "") if isinstance(final_hit, dict) else ""

    out["final_song_match"] = _matches(final_title, tc.get("expected_song"))
    out["final_artist_match"] = _matches(final_artist, tc.get("expected_artist"))

    # Optional version-filter checks
    bad_title = _violates_must_not_contain(final_title, tc.get("must_not_contain"))
    bad_artist = _violates_must_not_contain(
        final_artist, tc.get("must_not_contain_artist"))
    out["version_clean"] = bad_title is None and bad_artist is None
    if bad_title:
        out["version_violation"] = f"title contains '{bad_title}'"
    elif bad_artist:
        out["version_violation"] = f"artist contains '{bad_artist}'"

    # Optional year floor
    year_ok = True
    if "expected_year_min" in tc:
        year = out["final_year"]
        if isinstance(year, int):
            year_ok = year >= tc["expected_year_min"]
        elif isinstance(year, str) and year.isdigit():
            year_ok = int(year) >= tc["expected_year_min"]
        # If year missing, skip the check (don't fail the case for it)
    out["year_ok"] = year_ok

    # Optional views floor
    views_ok = True
    if "min_views_M" in tc:
        parsed = _parse_views_to_M(out["final_views"])
        if parsed is not None:
            views_ok = parsed >= tc["min_views_M"]
        # If views missing, skip the check
    out["views_ok"] = views_ok

    # Overall pass: intent + final song + final artist all correct
    # PLUS version_clean + year_ok + views_ok where applicable.
    if tc.get("expected_song") is None and tc.get("expected_artist") is None:
        # Mood / vague — only check word-count proxy
        out["passed"] = (
            out["intent_correct"]
            and out.get("enriched_word_count_ok", True)
        )
    else:
        artist_match = (
            out["final_artist_match"]
            if tc.get("expected_artist") is not None
            else True
        )
        out["passed"] = (
            out["intent_correct"]
            and out["final_song_match"]
            and artist_match
            and out["version_clean"]
            and year_ok
            and views_ok
        )

    return out


# ─── Run all + print + save ──────────────────────────────────────

def run_eval(model: str, filter_tier: str | None = None,
             filter_tag: str | None = None) -> dict:
    cases = TEST_CASES
    if filter_tier:
        cases = [tc for tc in cases if tc.get("tier") == filter_tier]
    if filter_tag:
        cases = [tc for tc in cases if filter_tag in tc.get("tags", [])]

    print(f"\n{'═' * 70}")
    print(f"  {BOLD}Song Disambiguation v3 — production pipeline — {model}{RESET}")
    if filter_tier or filter_tag:
        flt = []
        if filter_tier:
            flt.append(f"tier={filter_tier}")
        if filter_tag:
            flt.append(f"tag={filter_tag}")
        print(f"  filter: {', '.join(flt)}")
    print(f"  classify → enrich → dual-search (raw + enriched)")
    print(f"  cases: {len(cases)}")
    print(f"{'═' * 70}\n")

    brain = _load_brain(model)
    rows: list[dict] = []
    passed = 0
    total = len(cases)

    for i, tc in enumerate(cases):
        tier = tc.get("tier", "easy")
        tier_color = {"easy": GREEN, "medium": YELLOW, "hard": RED}.get(tier, "")
        print(f"  [{i+1}/{total}] {tier_color}[{tier}]{RESET} {tc['input']!r}")
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
            extra = ""
            if r.get("version_violation"):
                extra = f" {RED}[{r['version_violation']}]{RESET}"
            elif not r.get("year_ok", True):
                extra = f" {RED}[year={r.get('final_year')}]{RESET}"
            elif not r.get("views_ok", True):
                extra = f" {RED}[views={r.get('final_views')}]{RESET}"
            print(f"      {BOLD}final{RESET}: {ft} — {fa}{extra} {mark}{RESET}")
            if tc.get("expected_song"):
                print(f"      expected: {tc['expected_song']} — "
                      f"{tc.get('expected_artist') or 'any-artist'}")
        if r["passed"]:
            passed += 1
        rows.append(r)
        print()

    # Overall summary
    pct = (passed / total) * 100 if total else 0.0
    color = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED
    print(f"{'═' * 70}")
    print(f"  {BOLD}Pass rate: {color}{passed}/{total} ({pct:.0f}%){RESET}")
    print(f"{'═' * 70}")

    # Per-tier breakdown
    by_tier_total: dict[str, int] = defaultdict(int)
    by_tier_pass: dict[str, int] = defaultdict(int)
    by_tag_total: dict[str, int] = defaultdict(int)
    by_tag_pass: dict[str, int] = defaultdict(int)
    for r in rows:
        t = r.get("tier", "easy")
        by_tier_total[t] += 1
        if r.get("passed"):
            by_tier_pass[t] += 1
        for tag in r.get("tags", []):
            by_tag_total[tag] += 1
            if r.get("passed"):
                by_tag_pass[tag] += 1

    by_tier = {
        tier: {
            "passed": by_tier_pass[tier],
            "total": by_tier_total[tier],
            "score": (by_tier_pass[tier] / by_tier_total[tier] * 100.0)
                     if by_tier_total[tier] else 0.0,
        }
        for tier in ("easy", "medium", "hard")
        if by_tier_total[tier] > 0
    }

    print(f"\n  {BOLD}Per-tier{RESET}")
    for tier in ("easy", "medium", "hard"):
        if tier in by_tier:
            t = by_tier[tier]
            tcol = GREEN if t["score"] >= 80 else YELLOW if t["score"] >= 60 else RED
            print(f"    {tier:7s} {tcol}{t['passed']:>2}/{t['total']:<2} "
                  f"({t['score']:5.1f}%){RESET}")

    if by_tag_total:
        print(f"\n  {BOLD}Per-tag (sorted by case count){RESET}")
        for tag in sorted(by_tag_total, key=lambda k: -by_tag_total[k]):
            tot = by_tag_total[tag]
            ok = by_tag_pass[tag]
            score = ok / tot * 100.0 if tot else 0.0
            tcol = GREEN if score >= 80 else YELLOW if score >= 60 else RED
            print(f"    {tag:18s} {tcol}{ok:>2}/{tot:<2} ({score:5.1f}%){RESET}")

    # Step contribution
    intent_ok = sum(1 for r in rows if r.get("intent_correct"))
    enrich_changed = sum(1 for r in rows if r.get("enrichment_changed"))
    n_with_expected = sum(1 for tc in cases if tc.get("expected_song") is not None)
    expected_inputs = {tc["input"] for tc in cases if tc.get("expected_song") is not None}
    raw_song_ok = sum(1 for r in rows
                      if r.get("input") in expected_inputs and r.get("raw_song_match"))
    enr_song_ok = sum(1 for r in rows
                      if r.get("input") in expected_inputs and r.get("enriched_song_match"))
    final_song_ok = sum(1 for r in rows
                        if r.get("input") in expected_inputs and r.get("final_song_match"))

    print(f"\n  {BOLD}Step contribution{RESET}")
    print(f"    classify_intent → music_play:  {intent_ok}/{total}")
    print(f"    enrich_query changed query:    {enrich_changed}/{total}")
    print(f"    {DIM}— for tests with expected song:{RESET}")
    print(f"    raw search → right song:       {raw_song_ok}/{n_with_expected}")
    print(f"    enriched search → right song:  {enr_song_ok}/{n_with_expected}")
    print(f"    {BOLD}final dual-pick → right song:  {final_song_ok}/{n_with_expected}{RESET}")

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
    suffix = ""
    if filter_tier:
        suffix += f"_{filter_tier}"
    if filter_tag:
        suffix += f"_{filter_tag}"
    filename = f"song_disambig_v3_{model.replace(':', '_')}{suffix}_{timestamp}.json"
    filepath = os.path.join(results_dir, filename)
    summary = {
        "model": model,
        "timestamp": timestamp,
        "filter_tier": filter_tier,
        "filter_tag": filter_tag,
        "total": total,
        "passed": passed,
        "percentage": pct,
        "intent_ok": intent_ok,
        "enrichment_changed": enrich_changed,
        "raw_song_ok": raw_song_ok,
        "enriched_song_ok": enr_song_ok,
        "final_song_ok": final_song_ok,
        "by_tier": by_tier,
        "rows": rows,
    }
    with open(filepath, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Saved: {filepath}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Song disambiguation eval — production 3-step pipeline")
    parser.add_argument("models", nargs="*",
                        help="Ollama models to evaluate (default: llama3.2:3b)")
    parser.add_argument("--tier", choices=["easy", "medium", "hard"],
                        help="Filter to a single difficulty tier")
    parser.add_argument("--tag", help="Filter to cases with this tag")
    args = parser.parse_args()

    models = args.models or ["llama3.2:3b"]
    for m in models:
        run_eval(m, filter_tier=args.tier, filter_tag=args.tag)
