# Eval Baseline — 2026-05-04 (Jetson, llama3.2:3b)

First run after expanding both test suites. Captures real production behavior
with **JARVIS auto-start newly enabled** + the Jetson's Ollama warming
`llama3.2:3b` from cold cache. Both runs ran on the Jetson against the
production config — same model, same system prompt, same provider chain
the assistant uses for live voice.

## TL;DR

| Suite | Score | Notes |
|---|---|---|
| **test_intent** (90 cases) | **40/90 (44%)** | Reveals model conformance issues — hallucinated intent names dominate failures |
| **eval_song_disambiguation** (50 cases) | **41/50 (82%)** | Pipeline holds up well; specific weak spots in Coke Studio Pakistan + Whisper-style mishears |

The hard-tier song eval scored **88%** — better than easy — because the
new same-title and version-filter cases hit the dual-search architecture's
strengths exactly. That's the test working: it flagged the truly weak
catalog (Pakistani CS, numeric song names) cleanly.

## Intent classification — 40/90

### Per-tier
| Tier | Pass | Total | % |
|---|---|---|---|
| easy   | 11 | 28 | 39% |
| medium | 16 | 31 | 52% |
| hard   | 13 | 31 | 42% |

**Why medium > easy here**: most "easy" cases test intent names (`weather`,
`system`, `ambient`, `chat`, `memory_stats`) the model has decided to invent
better-sounding aliases for (`weather_report`, `time`, `sound_play`,
`joke_teller`, `memory_recall`). Medium-tier cases are mostly about input
phrasing, where the model handles wider phrasings reasonably.

### Failure mode breakdown
| Failure mode | Count | Notes |
|---|---|---|
| **Hallucinated intent name** | 28 | Model invents names not in the 17-intent schema |
| **Param mismatch** | 10 | `dim` for brightness, `next` for skip, `adjust` for brightness |
| **`chat` fallback** | 4 | Long inputs the model gives up on |
| **Chain missing intent** | 5 | 3-step chains lose the last intent |
| **Exception (str params)** | 2 | Model returned malformed JSON — runner now catches gracefully |

### The hallucinated-intent zoo (real outputs, sampled)
```
joke_teller         time            time_zone           date_time
goodnight           weather_report  sound_play          sound_effect
news                bollywood_quiz  movie_awards        movie_start
mode_change         change_personality  switch_channel  story (when expected chat)
play_with_dog       celebrity_guess sports_scoreboard   activity
encyclopedia        oscar_winner    timer (when reminder expected)
```

The model is treating `## Intents` as **suggestions, not a strict enum**.
Every example you can imagine — `joke_teller` for "tell me a joke" instead
of `chat`, `weather_report` instead of `weather`, `time_zone` for "what
time is it in NY" instead of `system` — is the model trying to be helpful
by inventing a more-specific intent name.

### The clear fix (separate change, not done in this commit)

Add a strict enum constraint to the classification system prompt:

```
CRITICAL: the "intent" field MUST be EXACTLY ONE of these 17 strings —
no synonyms, no abbreviations, no inventions:
music_play, music_control, volume, light_control, switch_personality,
chat, system, weather, knowledge_search, memory_recall, memory_stats,
sleep, quiz, youtube_search, reminder, story, timer, ambient.

If the request doesn't fit any of these, use "chat".
```

I expect this single change to recover most of the 28 hallucinated-name
failures, lifting the score into the 70s. Worth A/B testing before the
demo. We should bench the prompt-cache cost first — adding ~50 tokens
to the system prompt costs ~50 tokens of warm-cache time.

### What's actually correct that we're flagging as fail
A few cases the model handled defensibly but our schema disagreed:
- `next song please` → action=`next` (model literal; schema demands `skip`)
- `lights at twenty percent` → action=`dim` (model defensible; schema demands `brightness`)
- `remind me in two hours` → `timer` (model arguably correct — duration-based)
- `kitna yaad hai tujhe` → `memory_recall` (model arguably correct — adjacent intent)

Either tighten the prompt's action enum or accept synonyms in the test.
For now I'm leaving them as fails because the user-experience consistency
matters: handlers need a single canonical action name to dispatch on.

## Song disambiguation — 41/50

### Per-tier
| Tier | Pass | Total | % |
|---|---|---|---|
| easy   | 12 | 14 | 86% |
| medium | 14 | 19 | 74% |
| **hard** | **15** | **17** | **88%** |

### Per-tag highlights (sorted by case count, % of cases passed)
| Tag | Passed | Total | % | Insight |
|---|---|---|---|---|
| modern (post-2020) | 16 | 21 | 76% | Catalog after model training cutoff — works fine via dual search |
| same-title | 5 | 5 | **100%** | Version disambiguation logic works |
| version-filter | 5 | 5 | **100%** | `must_not_contain` catches karaoke / instrumental / slowed |
| polite | 3 | 3 | 100% | (intent suite) |
| stt-artifact (song eval) | 3 | 5 | 60% | Whisper Hindi mishears mostly recoverable; "hayriye" disastrously matches Turkish |
| **coke-studio** | **0** | **3** | **0%** | Pakistani Coke Studio originals lose to Bollywood remixes on YouTube |
| **pakistani** | **0** | **3** | **0%** | Same songs as coke-studio — Pasoori, Tu Jhoom, Tu Hai Kahaan |
| punjabi | 2 | 4 | 50% | Numeric song names ("295") confuse classifier |
| hinglish | 4 | 6 | 67% | Mostly fine; trips on Hinglish + numeric ("Sidhu ka 295 lagao") |

### The 9 song failures
| Tier | Input | What we got | Why |
|---|---|---|---|
| easy | `play Sajni` | Sajni — Jal The Band (2003 Pakistan) | Two real songs share title; Jal beat Arijit on raw search popularity at the moment |
| easy | `Dil` | misclassified as `song_search` | Hallucinated intent for single Hindi word |
| medium | `play Pasoori` | Pasoori Nu (Bollywood remake) | Hindi remake outranks Coke Studio original on YT |
| medium | `Pasoori bajao yaar` | Pasoori Nu | same as above |
| medium | `play Tu Jhoom` | Cover by Shelly Khatri Taluja | Original Naseebo Lal version lower-ranked |
| medium | `play Tu Hai Kahaan` | "Tu Kahaan Hai" by Zubeen Garg (different song) | Word-order matters; YT matched a different title |
| medium | `play 295 by Sidhu` | "Eyes on Me" — Sidhu Moose Wala | Numeric "295" confused YT search |
| hard | `play hayriye` | Fıldır Fıldır Hayriye — Ata Demirer (Turkish) | Whisper mishear matched a Turkish song name |
| hard | `Sidhu ka 295 lagao` | misclassified as `music_control` | "295" interpreted as a control level |

### What the failures imply for production fixes (post-test)
1. **Coke Studio bias** — when query is a known CS Pakistan song, force enrichment to include "Coke Studio Pakistan" or "Ali Sethi". 0/3 → could be 3/3 with a small static list.
2. **Numeric song names** — when classification produces a query that's mostly digits, also try `<artist> <number>` enrichment.
3. **Hindi-name STT correction** — pre-classification fuzzy-match against known Bollywood title list (rapidfuzz ratio ≥ 85). Catches "hayriye"→"Heeriye", "kesriya"→"Kesariya".
4. **Sajni disambiguation** — when YouTube returns two results with identical title and >5x view ratio, prefer the higher-viewed.

## Latency (Jetson, llama3.2:3b on CUDA)

Median per call:
- `classify_intent`: 4.6s — cold-ish; KV cache should make this ~1.5s after first
- `enrich_query`: 1.9s
- YouTube search: 1.4s

The intent eval clocks 90 calls × ~5s = 7.5min total. Steady-state per-call
latency is dominated by the classify call (~5s). Worth profiling whether
the prompt cache is actually hot during sequential evals — the warm-up
shot at the start might not survive the inter-test churn.

## Files

- Intent results: `jarvis/assistant/tests/results/20260504_172539.json`
- Song results: `jarvis/01-the-brain/notes/eval-results/song_disambig_v3_llama3.2_3b_20260504_172441.json`

## Next steps (in priority order)

1. **Tighten classifier system prompt** with strict intent enum (the
   "CRITICAL" block above). Run intent suite again, compare. If we hit
   ≥70%, ship.
2. **Add Coke Studio + Pakistani-music hint** to the enrichment prompt.
   Test against the 3 currently-failing CS cases.
3. **Hindi-title fuzzy correction** using rapidfuzz against a curated
   list of ~500 popular Bollywood/Pakistani/Punjabi titles. STT
   recovery layer.
4. **Action-name accept-list** — let `dim` map to `brightness`, `next`
   map to `skip` either in the prompt or in the post-classify
   normalization in `core/intent_handler.py`.
