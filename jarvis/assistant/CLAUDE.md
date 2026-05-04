# jarvis/assistant/ — Core Codebase

This is the actual runnable assistant. Everything else in `jarvis/` is learning material, experiments, and notes. This directory is the product.

## Architecture: Provider Pattern

Every capability is an abstract interface (`core/interfaces.py`) with swappable implementations registered via decorators (`core/registry.py`). Config.yaml picks which implementation to use. Adding a new provider = new file + `@register` decorator + one config line.

```
core/
  interfaces.py    — ABC for every provider type (BrainProvider, MusicProvider, KnowledgeProvider, etc.)
  registry.py      — @register("brain", "ollama") maps config names to classes
  config.py        — Loads config.yaml once at import time, singleton `config` dict
  logger.py        — Centralized logging, reads debug.log_level from config
  personality.py   — PersonalityManager, loads profiles from config, tracks active personality
  voice_router.py  — Personality→voice provider routing + streaming TTS with interrupt support
  mic.py           — Microphone input with VAD-based auto-stop recording

providers/
  brain/ollama.py         — Ollama LLM: intent classification + query enrichment
  music/youtube.py        — YouTube Music search + mpv playback via IPC socket
  lights/tuya.py          — Tuya/Wipro smart light control via tinytuya
  ears/faster_whisper.py  — CTranslate2-optimized Whisper for local STT
  voice/piper_tts.py      — Piper TTS (CPU-only, English, ultra-fast)
  voice/kokoro_tts.py     — Kokoro TTS (82M params, Hindi support, preset voices)
  voice/edge_tts.py       — Microsoft Edge TTS (cloud-based, zero local resources)
  voice/xtts.py           — Coqui XTTS (voice cloning from reference WAV)
  wake_word/openwakeword.py — OpenWakeWord for always-on activation phrase detection
  memory/sqlite.py        — SQLite-backed interaction logging and recall
  knowledge/duckduckgo.py — DuckDuckGo web search for current events (no API key)

main.py               — Entry point, wires providers, handles intents, runs text/voice/wake word loop
config.yaml            — ALL configuration (gitignored, has secrets)
config.example.yaml    — Safe template with redacted values
```

## The Intent Pipeline (most important to understand)

This is a 3-step separated pipeline, evolved through many iterations to beat Alexa:

**Step 1: Classification** (`ollama.py → classify_intent()`)
- LLM extracts intents + raw params from user input
- Returns `list[Intent]` for chaining ("play Sajni and set lights to red" → 2 intents)
- The LLM MUST NOT modify song names — "play Sajni" → query: "Sajni", not "Sajni Arijit Singh"
- Personality tone is injected into the system prompt so responses match character

**Step 2: Enrichment** (`ollama.py → enrich_query()`)
- Separate LLM call, only for music_play intents
- Adds artist name if confident: "Sajni" → "Sajni Arijit Singh"
- Uses per-personality music preferences if available, else global config
- Lower temperature (0.2) for conservative enrichment

**Step 3: Dual Search** (`youtube.py → search()`)
- ALWAYS runs TWO YouTube Music searches: enriched query + raw query
- If both return same videoId → use enriched results
- If different → raw results go FIRST (YouTube's popularity ranking is the strongest disambiguation signal)
- This catches LLM hallucinations — if the LLM mangles the song name, the raw search still works

### Why separated?
3B models hallucinate movie names, mangle song names ("sajni" → "saajan"), and can't distinguish between knowing something and guessing. Separating classification from enrichment means the raw query is always clean. The dual search is a safety net.

## Personality System

Personalities are defined in `config.yaml → personalities.profiles`. Each has: id, display_name, description, tone, voice_model, music_preferences.

- `personality_manager` is a singleton in `core/personality.py`
- The active personality's tone is injected into the system prompt on EVERY classify_intent() call (prompts are NOT cached)
- `switch_personality` is a classified intent like any other
- Fuzzy matching: "Devesh", "devesh", display_name all work
- Chat responses also use the personality tone as system prompt
- Per-personality music_preferences override global prefs for enrichment

Current profiles: jarvis (default), devesh, girlfriend (template), chandler

## Logging

`core/logger.py` — centralized, reads `config.yaml → debug.log_level`.

- Every module does `from core.logger import get_logger; log = get_logger("module.name")`
- Logs go to stderr (ANSI colored in terminal, auto-disabled when piped)
- DEBUG: shows module origin, raw/enriched queries, search results, intent params
- INFO: "Playing X by Y", personality switches, startup
- WARNING: search mismatches, invalid JSON from LLM, provider unavailable
- ERROR: playback failures, provider crashes
- User-facing output (assistant speech) is print() to stdout, independent of log level

## Config structure (key sections)

- `assistant.name/wake_word/personality` — identity (personality field is fallback if no personalities section)
- `brain.provider/model/endpoint/temperature` — LLM settings
- `music.provider/player/user_preferences` — music + taste for disambiguation
- `lights.provider/devices/scenes` — smart light config with device secrets
- `audio.provider/default_output/outputs` — system audio routing (interface defined, not implemented)
- `personalities.default/profiles` — personality definitions
- `debug.log_level` — controls logging verbosity

## Intent types

| Intent | Params | Handler |
|--------|--------|---------|
| music_play | query | enrich → dual search → mpv play |
| music_control | action (pause/resume/stop/skip) | mpv IPC command |
| volume | level (0-100), output | mpv volume (future: AudioOutputProvider) |
| light_control | action, value | tuya device control |
| switch_personality | personality (id or display_name) | personality_manager.switch() |
| chat | message | LLM generate with personality tone |
| system | action (time/date/weather) | built-in handlers |
| knowledge_search | query | web search → inject results → LLM summarize |
| memory_recall | query | search interaction history → LLM summarize |
| memory_stats | (none) | return interaction statistics |

## Hardware portability patterns

This code runs on MacBook, Jetson Orin Nano, and Raspberry Pi. Follow these patterns in EVERY provider:

### Platform detection (use this helper, don't roll your own)
```python
# core/platform.py (to be created)
import platform, os

def detect_platform() -> str:
    """Returns: 'mac', 'jetson', 'pi', 'linux', 'windows'"""
    system = platform.system()
    if system == "Darwin":
        return "mac"
    if os.path.exists("/etc/nv_tegra_release"):
        return "jetson"
    if os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model") as f:
            if "raspberry" in f.read().lower():
                return "pi"
    if system == "Linux":
        return "linux"
    return system.lower()

def detect_gpu() -> str:
    """Returns: 'cuda', 'mps', 'cpu'"""
    try:
        import torch
        if torch.cuda.is_available(): return "cuda"
        if torch.backends.mps.is_available(): return "mps"
    except ImportError:
        pass
    return "cpu"
```

### Conditional imports (ALWAYS do this for hardware libs)
```python
# WRONG — breaks on Mac
import RPi.GPIO as GPIO

# RIGHT — graceful fallback
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

def set_led(pin, state):
    if not HAS_GPIO:
        log.debug("GPIO not available (not running on Pi), skipping LED control")
        return
    GPIO.output(pin, state)
```

### File paths (ALWAYS use pathlib, NEVER hardcode)
```python
# WRONG
socket_path = "/tmp/mpv-socket"
config_path = "~/.config/jarvis/config.yaml"

# RIGHT
from pathlib import Path
import tempfile
socket_path = Path(tempfile.gettempdir()) / "mpv-socket"
config_path = Path(__file__).parent.parent / "config.yaml"
```

### External commands (ALWAYS check availability)
```python
# WRONG
subprocess.run(["mpv", "--version"])

# RIGHT
import shutil
if not shutil.which("mpv"):
    install_hint = {
        "mac": "brew install mpv",
        "jetson": "sudo apt install mpv",
        "pi": "sudo apt install mpv",
    }.get(detect_platform(), "install mpv from https://mpv.io")
    log.error("mpv not found. Install: %s", install_hint)
    return False
```

### Provider pattern enables platform swapping
The whole architecture is designed for this. Platform-specific code lives in providers, not core:
- Mac: `providers/audio/coreaudio.py` (future)
- Jetson: `providers/audio/alsa.py` (future)
- Pi: `providers/audio/alsa.py` (same as Jetson)
- Config picks: `audio.provider: "coreaudio"` vs `audio.provider: "alsa"`

Same for GPIO, camera, display — each gets a provider with platform-specific implementations.

## Local-first, internet-enhanced

The core design principle: everything that CAN run locally DOES run locally. Internet is a bonus, not a requirement.

**Local-only (works with zero internet):** LLM inference (Ollama), TTS (Piper, Kokoro), STT (faster-whisper), wake word (OpenWakeWord), lights (Tuya on local network), memory (SQLite), personality system.

**Internet-enhanced (activates when online, degrades gracefully when not):** YouTube Music search/playback, web search for current events (KnowledgeProvider), Edge TTS (cloud-based voice), future: RSS feeds, cloud APIs.

**The graceful degradation pattern:** Every internet-dependent provider implements `is_available()` (or try/except in `build_assistant()`). The `handle_intent()` function checks for provider existence before use and falls back to LLM-only responses. The user never sees a crash — they get "I couldn't check online for that" instead.

## Knowledge system (web search / RAG)

The KnowledgeProvider interface (`core/interfaces.py`) enables the assistant to answer questions about current events, news, and real-time information. Three capability levels:

- **Level 1 — Search:** Query → list of results with snippets. Current: DuckDuckGo (no API key).
- **Level 2 — Fetch:** Retrieve full page content from a URL. Not yet implemented.
- **Level 3 — Browse:** Navigate websites, fill forms, take actions. Future capability.

The pipeline: classifier detects `knowledge_search` intent → KnowledgeProvider.search() fetches snippets → snippets injected into LLM prompt as grounding context → LLM summarizes conversationally.

On edge hardware: max_results is kept low (3) to limit context window usage. Each result adds ~100-150 tokens. The KV cache grows linearly with input length, and on Jetson's 8GB shared memory, keeping total prompt under ~1000 tokens is important.

## Birthday-pack additions (May 5-14, 2026)

A whole "event pack" subsystem ships alongside the core assistant for
Astha's birthday and future occasion-specific surprises. Full spec
lives in [`jarvis/BIRTHDAY_ROADMAP.md`](../BIRTHDAY_ROADMAP.md).
Hardware decisions deferred — see
[`jarvis/05-the-body/HARDWARE_NOTES.md`](../05-the-body/HARDWARE_NOTES.md).

### New modules (all in `core/`)

  - `branding.py` — single source of truth for the assistant's name
    (Vesper) + protocol_id (gulmugli, stable across rebrands)
  - `event_manager.py` — date-rule based event-pack registry; reads
    `events/<pack>/pack.yaml`, answers "what's happening today?"
  - `event_scheduler.py` — daemon thread that auto-fires triggers
    at midnight rollover for packs with `trigger.auto_midnight: true`
  - `trigger_state.py` — persistent year-keyed trigger record so a
    Jetson restart on the day-of doesn't roll back the celebration
  - `intro_runner.py` — executes a YAML launch script with 5 step
    types (play_audio, dashboard_event, speak, dashboard_hint,
    start_playlist); best-effort, never crashes on a missing step
  - `audio_playback.py` — portable WAV/MP3 player (afplay → paplay
    → aplay → mpv) for any code that needs to play a local file
  - `astha_jokes.py` — joke bank engine for the silly-questions
    mode; supports single_turn, setup_then_punchline, interactive
  - `birthday_quiz.py` — finite hand-curated quiz with audio reveal
  - `voice_memos.py` — recall recorded letters by tag, with date
    gating (memos can be locked until a release date)
  - `custom_playlist.py` — playlist YAML loader with shuffle/loop

### New event-pack content tree

`events/astha-birthday/` holds all the per-pack content:
  - `pack.yaml` — date rule + features + manual trigger phrases
  - `theme/{tokens.json, avatar.json}` — dashboard CSS-var overrides
  - `first_year/intro_script.yaml` — year-1-only launch sequence
  - `media/{photos, songs, sounds, voice_memos, besura, sorry}/`
  - `jokes/astha_jokes.yaml`, `quiz/about_us.yaml`

Adding a new event pack (Diwali, anniversary, etc.) is a directory
drop — see `events/README.md`.

### New API endpoints (in `api/routers/`)

  - `events.py` — GET /current (poll-friendly), /health (diagnostic),
    /{pack}/theme/{tokens,avatar}, POST /trigger, /{pack}/reset
  - `yaadein.py` — GET /list, /photo/{filename}, /music

### New voice intents

11 new intents added this cycle (see `_VALID_INTENTS` in
`providers/brain/ollama.py`). Dispatch table in `core/intent_handler.py`
is now ~25 entries. `tests/test_intent_dispatch.py` enforces the
table-vs-enum integrity at test time.

### CLI tools

  - `tools/birthday_rehearsal.py` — May 14 launch dry-run on Mac
  - `tools/check_content.py` — audit which user-content slots are
    still placeholder before the day-of

### Test surface

16+ fast-suite test files cover the new modules:
api_smoke, imports, intent_dispatch, event_manager, intro_runner,
astha_jokes, birthday_quiz, trigger_state, astha_angry_prefilter,
custom_playlist, voice_memos, memory_event_recall, memory_log,
event_scheduler, prefilter, personality.

Run `python tests/runner.py --suite <name>` for any of them.

## Known issues / tech debt

- **Eval framework outdated**: `eval_song_disambiguation.py` still uses old single-LLM-call approach, needs updating for the separated 3-step pipeline
- **AudioOutputProvider not implemented**: Volume currently routes through mpv. Interface is defined in interfaces.py.
- **No error recovery in text loop**: If Ollama is down, the assistant crashes instead of gracefully degrading.
- **mpv IPC socket path**: Uses `tempfile.gettempdir()` which is platform-safe, but untested on Jetson.

## Streaming voice pipeline (`/api/voice/stream`)

The current state-of-the-art voice path. Adopted from research into how Home
Assistant Voice / Pipecat / LiveKit / OVOS / Willow / Rhasspy solve this same
problem. Key insights worth knowing before touching this code:

### Architecture (Jetson 8GB shared NvMap)

- **STT**: faster-whisper "tiny" on CUDA (~70MB) — small enough to leave NvMap
  headroom for the LLM. "base" or larger fragments NvMap and crashes Ollama.
- **LLM**: Ollama llama3.2:3b on CUDA, prompt-cached at startup
  (`brain.warm_up()` sends the classifier system prompt with `num_predict=1`
  so the KV cache for those 6000 tokens stays hot).
- **TTS English**: Piper `en_US-amy-low` on CPU, ~10× realtime, ~0.4s per
  sentence. Faster than Kokoro on GPU was. This is the industry pattern
  (HA Voice / Wyoming / Willow all use Piper for English).
- **TTS Hindi / cloned voices**: Kokoro on CPU, or XTTS for runtime cloning.
  Voice-clone-aware routing (`voice.py::_synth`) detects cloned-voice
  personalities and bypasses Piper for them.
- **Filler audio**: pre-synthesized `[Mm-hmm., One moment., Let me see.]` in
  the personality voice, played as the very first audio_chunk after STT.
  Drops perceived TTFA to ~600ms regardless of backend latency. Pattern from
  Pipecat's `on_function_calls_started` hook + Alexa/Siri.

### Why each piece lives where it does

- Audio body is fetched **out-of-band** via `/api/voice/audio/{chunk_id}`,
  not embedded in SSE events. SSE multiplexes everything onto one TCP stream
  — a 600KB base64 audio_chunk would head-of-line-block subsequent
  response_text events. Out-of-band fetch via parallel HTTP/2 connections
  removes this blocking.
- The SSE generator coroutine **explicitly yields** to the asyncio loop via
  `await asyncio.sleep(0)` between iterations. Without it, a long-running
  LLM stream starves parallel HTTP handlers (audio body fetches stall).
- **Prefilter intents** with hardware side-effects use a 200ms validation
  window (HA pattern from `homeassistant/helpers/intent.py`): handler runs
  in the shared `_intent_executor` thread pool, we wait 200ms, prefer the
  handler's return value if it finished, else fall back to the prefilter's
  pre-defined `response` field. Hardware actions that take longer keep
  running in the background; we do NOT speak a follow-up error 30s later
  (HA's design — by then the user has moved on).
- **VAD silence threshold** is 0.7s (was 1.5s). Industry range:
  Alexa ~600ms, Google ~700ms, Siri ~800ms.
- **`OLLAMA_KEEP_ALIVE=600`** (was -1). Models unload after 10 min idle so
  KV-cache fragmentation doesn't accumulate over hours.

### Latency targets (validated)

- **Filler perceived TTFA**: p50 0.57s, p95 0.71s
- **Real answer audible**: p50 2.65s, p95 3.0s server-side
- **Prefilter intent (hardware online)**: p50 0.5s
- **Prefilter intent (hardware offline)**: p50 0.7s — was 36s before
- **Music intent ("play X")**: 1.0s perceived ack — was ~20s before

### Things to NOT do

- Don't move Kokoro to CUDA on Jetson. Whisper CUDA + Ollama CUDA + Kokoro
  CUDA fragments NvMap and crashes Ollama after ~50 sustained requests.
- Don't put the chat-fast model on a different Ollama model than the
  classifier UNLESS `OLLAMA_MAX_LOADED_MODELS≥2` (else swap thrashing).
- Don't speak a follow-up error after a hardware action fails outside the
  validation window. HA explicitly chose this; the user has moved on by
  then and a delayed error message is worse than silent failure.
- Don't add "preemptive LLM on partial transcript" with current Whisper
  batch STT — it requires INTERIM transcript events Whisper doesn't emit.
  Wait until streaming STT migration (post-demo).

### Bench harness

`tools/bench_voice_e2e.py` synthesizes queries via macOS `say`, posts to
`/api/voice/stream`, measures both server-reported and client-perceived
TTFA. `--play` flag (off by default) plays audio through afplay. Run it
after any change touching the streaming pipeline.

### References

- Modal+Pipecat: https://modal.com/blog/low-latency-voice-bot
- LiveKit Agents: https://github.com/livekit/agents
- Pipecat: https://github.com/pipecat-ai/pipecat
- HA helpers/intent.py (200ms timeout pattern): `homeassistant/helpers/intent.py`
- OVOS Common Play (search/play decoupling): `ovos-workshop/.../common_play.py`
- Piper voice models: https://huggingface.co/rhasspy/piper-voices
