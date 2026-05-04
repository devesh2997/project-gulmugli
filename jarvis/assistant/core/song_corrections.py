"""
Song-query corrections — Hindi/Bollywood/Pakistani/Punjabi catalog.

Two services this module provides:

1. **STT mishear correction** (`correct_title`)
   Whisper transcribes Hindi proper nouns badly — "Kesariya" becomes
   "kesriya" or "kesariya", "Heeriye" becomes "hayriye" or "heriye",
   "Sajni" becomes "sajney". A short rapidfuzz pass against a curated
   canonical-titles list catches these before they hit YouTube. Without
   this, "play hayriye" can match a Turkish folk song titled
   "Fıldır Fıldır Hayriye" — an actual failure observed in production.

2. **Enrichment hints** (`enrichment_hint`)
   Some songs lose YouTube popularity ranking to remixes / covers / same-
   titled remakes:
     - "Pasoori" (Coke Studio Pakistan, Ali Sethi+Shae Gill) loses to
       "Pasoori Nu" (a 2023 Bollywood remake — totally different song).
     - "Tu Jhoom" original (Naseebo Lal+Abida Parveen) loses to many covers.
     - "Lover" (Diljit Dosanjh) collides with Taylor Swift's same-titled track.
     - Numeric-titled songs ("295" by Sidhu Moose Wala) confuse YT search.
   For these we provide an explicit enrichment override that includes the
   correct artist and (when relevant) origin context like "Coke Studio".

These tables are intentionally small and curated — every entry has an
observed user-impact reason. Adding hundreds of canonical titles would
slow the rapidfuzz pass without proportional benefit. Add to either
table when a real query lands wrong.

The matching is case-insensitive and operates on whitespace-trimmed input.
"""

from __future__ import annotations

from typing import Optional


# ── Canonical Bollywood/Pakistani/Punjabi titles ─────────────────────
# Used by `correct_title()` to fix STT mishears. Each entry is the
# correctly-spelled title; rapidfuzz finds the closest match above a
# similarity threshold.
#
# Curated for songs we actually expect users to ask for. NOT comprehensive.
# Order/duplication doesn't matter. All entries are looked up case-insensitively.

CANONICAL_TITLES: list[str] = [
    # ── Arijit Singh hits (massive overlap with user requests) ──
    "Sajni", "Channa Mereya", "Hawayein", "Gerua", "Tum Hi Ho",
    "Kesariya", "Apna Bana Le", "Apna Bana Le Piya", "Phir Bhi Tumko Chaahunga",
    "Tera Yaar Hoon Main", "Khairiyat", "Kabira", "Tum Mile",
    "Janam Janam", "Ae Dil Hai Mushkil", "Pal Pal Dil Ke Paas",
    "Tum Kya Mile", "Bedardeya", "O Bedardeya", "Jhoome Jo Pathaan",
    "Heeriye", "Sun Le Zara", "Lut Gaye", "Tum Hi Aana",
    "Pasoori Nu", "Tum Tak", "Wajah Tum Ho", "Hamari Adhuri Kahani",
    "Kun Faya Kun", "Pal", "Sun Raha Hai", "Sunn Raha Hai",
    "Phir Bhi Tumko", "Janam Janam Ka Saath",

    # ── Coke Studio / Pakistani originals (these we explicitly want) ──
    "Pasoori", "Tu Jhoom", "Tu Hai Kahaan",
    "Faasle", "Tu Hai Tu", "Tera Woh Pyar", "Aayi Aayi", "Aaye Aaye",

    # ── Punjabi crossover ──
    "295", "Brown Munde", "Old Skool", "Born to Shine", "Lover",
    "G.O.A.T.", "Goat", "Sidhu Moose Wala", "AP Dhillon",
    "Excuses", "Insane", "Lover Diljit",

    # ── Indie ──
    "Husn", "Husn Anuv Jain", "Mishri", "Antariksh", "Rangaa",
    "Pari", "Choo Lo", "Aaftaab", "Choo Lo Local Train", "Firefly",

    # ── Classic Bollywood ──
    "Tujhe Dekha", "Kuch Kuch Hota Hai", "Pehla Nasha",
    "Vande Mataram", "Saathiya", "Mitwa", "Senorita",

    # ── English staples (also misheard sometimes) ──
    "Blinding Lights", "Fix You", "Yellow", "Someone Like You",
    "Shape of You", "Perfect", "Photograph",
]


# ── Whisper-specific mishears (phonetic fallbacks) ──────────────────
# rapidfuzz ratio is character-distance based — it fails on mishears
# where Whisper changes the vowels but the word "sounds" right
# (heeriye → hayriye scores ~71). For these we keep an explicit
# substitution table. Add entries when you observe a real mishear in
# logs or evals. Always lowercase, exact-match on the misheard form.
_WHISPER_MISHEARS: dict[str, str] = {
    # Heeriye family (Jasleen Royal / Arijit Singh, 2023)
    "hayriye": "Heeriye", "heriye": "Heeriye", "hariye": "Heeriye",
    "heereye": "Heeriye",

    # Kesariya family (Brahmastra, 2022) — already covered by ratio,
    # but pin them anyway for confidence.
    "kesriya": "Kesariya", "kesriah": "Kesariya",

    # Sajni family — partial_ratio catches sajney, but pin variants.
    "sajney": "Sajni", "sajny": "Sajni",

    # Pasoori — Whisper hears the trailing "i" wrong sometimes.
    "pasori": "Pasoori", "pasoory": "Pasoori",

    # Channa Mereya
    "chana mereya": "Channa Mereya", "channa meraya": "Channa Mereya",

    # Apna Bana Le
    "apnabanale": "Apna Bana Le", "apna bana lay": "Apna Bana Le",
}


# ── Enrichment hints — force a specific enrichment for known cases ────
# Maps a normalized "trigger phrase" (lowercase, stripped) to the
# preferred enriched search query. This is checked BEFORE the LLM
# enrichment runs — when a hint matches, we use the hint and skip
# the LLM call entirely.
#
# Use these only for songs where the LLM enrichment systematically
# picks the wrong version OR where a remix/cover dominates YT
# popularity over the original the user almost certainly wants.

_ENRICHMENT_HINTS: dict[str, str] = {
    # ─ Coke Studio Pakistan originals (vs Bollywood remakes) ─
    "pasoori": "Pasoori Ali Sethi Shae Gill Coke Studio",
    "play pasoori": "Pasoori Ali Sethi Shae Gill Coke Studio",
    "tu jhoom": "Tu Jhoom Naseebo Lal Abida Parveen Coke Studio",
    "play tu jhoom": "Tu Jhoom Naseebo Lal Abida Parveen Coke Studio",
    "tu hai kahaan": "Tu Hai Kahaan AUR band",
    "play tu hai kahaan": "Tu Hai Kahaan AUR band",
    "faasle": "Faasle AUR band",

    # ─ Artist-name collisions ─
    "lover by diljit": "Lover Diljit Dosanjh",
    "lover diljit": "Lover Diljit Dosanjh",
    "diljit lover": "Lover Diljit Dosanjh",

    # ─ Numeric song names that confuse YT search ─
    "295": "295 Sidhu Moose Wala",
    "295 by sidhu": "295 Sidhu Moose Wala",
    "sidhu 295": "295 Sidhu Moose Wala",
    "sidhu ka 295": "295 Sidhu Moose Wala",

    # ─ Sajni — Jal The Band 2003 hit shares title with Arijit's
    #   Laapataa Ladies (2024). Arijit's is the one users want by 2026.
    #   Force the artist into enrichment so the dual search agrees.
    "sajni": "Sajni Arijit Singh Laapataa Ladies",
    "play sajni": "Sajni Arijit Singh Laapataa Ladies",
    "sajni bajao": "Sajni Arijit Singh Laapataa Ladies",
}


# ── Title normalization helpers ──────────────────────────────────────

def _normalize(s: str) -> str:
    """Lowercase, collapse whitespace. Used as the matching key."""
    return " ".join(s.lower().split())


def correct_title(query: str, threshold: int = 78) -> str:
    """
    Best-effort STT correction for Hindi/Bollywood/Pakistani/Punjabi titles.

    Three-stage match (cheap → expensive):

      1. Direct lookup against `_WHISPER_MISHEARS` for known mishears
         where Whisper changes the vowels but the word "sounds" right
         (e.g. "hayriye" → "Heeriye"). Phonetic mishears can score very
         low on Levenshtein ratio (~71) so character-distance scoring
         alone won't catch them.

      2. `rapidfuzz.fuzz.partial_ratio` against the canonical-titles
         list. partial_ratio handles short Hindi titles where one extra
         vowel changes the score badly under plain ratio (e.g. "sajney"
         vs "Sajni" scores 73 with ratio but 89 with partial_ratio).

      3. If neither matches, return the query unchanged. This is the
         safe default — we'd rather send a slightly mistranscribed
         query to YT than aggressively rewrite to something the user
         didn't say.

    threshold=78 was chosen empirically against the observed mishears
    in the song eval. Lower would risk mapping "Lover" to a similar-
    looking Bollywood title.

    Multi-word queries with > 4 words are passed through untouched —
    they're already specific enough that fuzzy correction on the whole
    string would be misleading. Common voice queries are 1-3 words.
    """
    if not query:
        return query
    q = query.strip()
    if not q:
        return query

    # Stage 1: direct mishear lookup
    direct = _WHISPER_MISHEARS.get(q.lower())
    if direct:
        return direct

    # Stage 1b: exact match against the canonical catalog. Prevents
    # "Pasoori" from being upgraded to "Pasoori Nu" by partial_ratio
    # (substring containment scores 100 even though they're different
    # songs). If the user says a canonical title verbatim, return it
    # as-is — enrichment hints handle the artist disambiguation later.
    q_lower = q.lower()
    for canonical in CANONICAL_TITLES:
        if canonical.lower() == q_lower:
            return canonical

    # Don't fuzzy-match very short queries — "hi", "go", "do" — partial_ratio
    # would map any of these to the longest containing title (e.g. "hi" → "Tum
    # Hi Ho" scores 100). 4 chars is the empirical floor that excludes those
    # but keeps 4-char Hindi proper nouns ("Pari", "Husn", "Rang") matchable.
    if len(q) < 4:
        return query

    # Don't fuzzy-match long queries — too risky to rewrite e.g.
    # "play that Anuv Jain song about love" to a single canonical title.
    if len(q.split()) > 4:
        return query

    # If the user already named an artist or movie via a connector word,
    # they've supplied enough context — don't rewrite the song name and
    # lose that context. e.g. "Husn by Anuv Jain" must NOT collapse to
    # "Husn" because we'd lose the disambiguating artist; "Lover by
    # Diljit" must NOT collapse to "Lover" or we'd lose the artist hint
    # that distinguishes from Taylor Swift's same-titled song. Same for
    # numeric song references ("295 by Sidhu", "Sidhu ka 295").
    artist_markers = (" by ", " ka ", " ki ", " ke ", " from ", " wala ")
    if any(m in f" {q.lower()} " for m in artist_markers):
        return query

    # Stage 2: rapidfuzz partial_ratio
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return query

    match = process.extractOne(
        q.lower(), [t.lower() for t in CANONICAL_TITLES],
        scorer=fuzz.partial_ratio, score_cutoff=threshold,
    )
    if match is None:
        return query
    matched_lower, score, idx = match
    return CANONICAL_TITLES[idx]


def enrichment_hint(raw_query: str) -> Optional[str]:
    """
    Return a hardcoded enrichment override for known-difficult queries,
    or None if no override applies.

    Lookup is case-insensitive on whitespace-normalized input. Add to
    `_ENRICHMENT_HINTS` above when a real user query lands on the
    wrong song version after the standard LLM enrichment.

    The caller (typically `OllamaBrainProvider.enrich_query`) should
    check this BEFORE making an LLM call — when a hint matches we save
    a 1-2s enrichment LLM call AND get a more reliable result.
    """
    if not raw_query:
        return None
    key = _normalize(raw_query)
    if key in _ENRICHMENT_HINTS:
        return _ENRICHMENT_HINTS[key]
    return None
