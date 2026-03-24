# jarvis/ — Module Structure & Learning Context

This directory contains both the runnable assistant (`assistant/`) and the learning/experimentation modules (`01-07`). The numbered modules are ET's learning journey — each has experiments, notes, and a README that explains AI/hardware concepts in depth.

## Read GUIDELINES.md first

`GUIDELINES.md` defines how to communicate with ET. The short version: explain AI and hardware deeply, skip software engineering explanations entirely. ET is a senior dev who doesn't need to be told what `requests.post()` does, but does need to understand what quantization does to model quality.

## Module map

| Module | Status | What's inside |
|--------|--------|---------------|
| 01-the-brain | Active | LLM experiments, eval framework, intent routing research. `experiments/eval_song_disambiguation.py` is the main eval. `notes/eval-results/` has benchmark JSON files. |
| 02-the-ears | Not started | Will be faster-whisper for STT, OpenWakeWord for wake word |
| 03-the-voice | Not started | Will be Piper TTS |
| 04-the-hands | Partially done | `experiments/test_music_playback.py` (5/5 tests pass), `test_wipro_light.py` for Tuya bulb |
| 05-the-body | Not started | Hardware: Jetson Orin Nano, ReSpeaker mic, NeoPixel LEDs, enclosure |
| 06-the-soul | Not started | Full integration, auto-start, personality prompt engineering |
| 07-presentation | Planned | Demo scripts for birthday reveal |
| **assistant/** | **Active** | **The actual codebase. See `assistant/CLAUDE.md` for details.** |

## Timeline

Deadline is May 14, 2026 (girlfriend's birthday). See `ROADMAP.md` for the week-by-week plan. Currently in Week 1 territory — brain + music + lights working on Mac, personalities added. Next major milestones: ears (STT), voice (TTS), then full Mac prototype before ordering hardware.

## Experiments directory pattern

Each numbered module has `experiments/` for throwaway test scripts and `notes/` for results. Experiments import from each other freely and don't follow the provider pattern — they're for learning and proving concepts. The clean, production versions of everything go in `assistant/`.

## Key files in 01-the-brain/experiments/

- `eval_song_disambiguation.py` — Tests the song disambiguation pipeline (LLM enrichment → YouTube search → correct song?). **Currently outdated** — still uses old single-LLM approach, needs updating for the 3-step separated pipeline.
- `eval_framework.py` — Generic eval runner for intent classification
- `intent_router.py` — Early prototype of intent routing (superseded by `assistant/providers/brain/ollama.py`)
- `my_test_cases.py` — Test cases for intent classification benchmarks
- `song_search_proof.py` — Proof that YouTube Music's popularity ranking is the strongest disambiguation signal
- `tinytuya.json`, `devices.json`, `snapshot.json`, `tuya-raw.json` — Tuya device data (**SECRETS, gitignored**)

## Hardware targets

The assistant must run on all three platforms with zero code changes (config-only differences):

- **MacBook (Apple Silicon)** — development machine. Ollama for LLM, Metal/MPS for GPU acceleration, system audio. This is where all coding and testing happens first.
- **Jetson Orin Nano** — primary deployment target. CUDA GPU, 8GB shared RAM, ALSA/PulseAudio. Runs 3B quantized models at ~30 tok/s. This is where it'll live as the birthday gift.
- **Raspberry Pi 4/5** — low-cost fallback. CPU-only, 4-8GB RAM. Smallest models only, or offload inference to a server. Good for lights-only or remote-speaker setups.

See `assistant/CLAUDE.md` for the concrete coding patterns (conditional imports, path handling, platform detection, command availability checks). The root `CLAUDE.md` has the full portability rules that every contributor must follow.

Key principle: **05-the-body** module handles hardware-specific setup and testing. The `assistant/` codebase itself should be hardware-agnostic — all platform differences are isolated in providers and config.

## What's been learned so far (key insights for any AI agent continuing this work)

1. **3B models hallucinate confidently** — they'll say "Gerua is from Dum Maaro Dum" when it's actually from Dilwale. Never trust a 3B model's movie/artist attributions. That's why enrichment is separated from classification.

2. **YouTube Music's popularity ranking is the best disambiguator** — searching "Sajni" returns the correct Arijit Singh version (202M views) as result #1. The LLM enrichment is a nice-to-have, but the raw YouTube search is the safety net.

3. **Dual search catches LLM mistakes** — the LLM enriched "sajni" to "Saajan Arijit Singh" (wrong song name), but the raw search for "sajni" still found the right song.

4. **Command chaining needs clean separation** — "play sajni with volume 10" was passing the full sentence as the music query. Fixed by separating classification (extracts clean "Sajni" as query) from the volume intent.

5. **Volume is a system concern, not a music concern** — "volume down" applies to music, TTS, and alerts. AudioOutputProvider interface is defined but not implemented yet.

6. **The eval must not test what's in the prompt** — ET caught that eval songs were hardcoded in the system prompt examples. All eval songs must be different from prompt examples.
