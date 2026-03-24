# jarvis/assistant/ — Core Codebase

This is the actual runnable assistant. Everything else in `jarvis/` is learning material, experiments, and notes. This directory is the product.

## Architecture: Provider Pattern

Every capability is an abstract interface (`core/interfaces.py`) with swappable implementations registered via decorators (`core/registry.py`). Config.yaml picks which implementation to use. Adding a new provider = new file + `@register` decorator + one config line.

```
core/
  interfaces.py    — ABC for every provider type (BrainProvider, MusicProvider, etc.)
  registry.py      — @register("brain", "ollama") maps config names to classes
  config.py        — Loads config.yaml once at import time, singleton `config` dict
  logger.py        — Centralized logging, reads debug.log_level from config
  personality.py   — PersonalityManager, loads profiles from config, tracks active personality

providers/
  brain/ollama.py     — Ollama LLM: intent classification + query enrichment
  music/youtube.py    — YouTube Music search + mpv playback via IPC socket
  lights/tuya.py      — Tuya/Wipro smart light control via tinytuya
  ears/               — (empty, faster-whisper planned)
  voice/              — (empty, Piper TTS planned)
  wake_word/          — (empty, OpenWakeWord planned)

main.py               — Entry point, wires providers, handles intents, runs text loop
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

## Known issues / tech debt

- **Eval framework outdated**: `eval_song_disambiguation.py` still uses old single-LLM-call approach, needs updating for the separated 3-step pipeline
- **AudioOutputProvider not implemented**: Volume currently routes through mpv. Interface is defined in interfaces.py.
- **Chat responses use full LLM call**: For a voice assistant, these should be shorter/faster. May need a separate lighter model or prompt.
- **No error recovery in text loop**: If Ollama is down, the assistant crashes instead of gracefully degrading.
- **mpv IPC socket path**: Uses `tempfile.gettempdir()` which is platform-safe, but untested on Jetson.
