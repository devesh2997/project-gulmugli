# Project Gulmugli — JARVIS Voice Assistant

A locally-running AI voice assistant, built as a birthday gift (deadline: May 14, 2026). The core goal is to beat Alexa at song disambiguation for Hindi/English/Hinglish music, while also controlling smart lights and having conversational AI with multiple personalities.

## Who is building this

ET (Devesh) — experienced full-stack developer, new to AI/ML and hardware. **Do NOT explain software engineering concepts** (HTTP, async, classes, etc.). **DO explain AI/ML and hardware concepts in depth** (quantization, attention, GPIO, Bluetooth protocols, etc.). See `jarvis/GUIDELINES.md` for the full rules.

## Architecture principles

- **No hardcoded names** — assistant name, model, provider, everything comes from `config.yaml`
- **Unopinionated on models/libraries/platforms** — every component is swappable via the provider pattern
- **Config-driven** — change one line in config.yaml, no code changes needed
- **Multi-platform from day one** — must run on MacBook (dev), Jetson Orin Nano (primary target), and Raspberry Pi (fallback). See "Hardware portability" section below.

## Project structure

```
project-gulmugli/
├── jarvis/                        # All project content
│   ├── GUIDELINES.md              # ET's learning rules (READ THIS)
│   ├── ROADMAP.md                 # Week-by-week timeline, deadline May 14
│   ├── 01-the-brain/              # LLM + intent routing (experiments, evals)
│   ├── 02-the-ears/               # Wake word + speech-to-text (not started)
│   ├── 03-the-voice/              # Text-to-speech (not started)
│   ├── 04-the-hands/              # Music, lights, actions (experiments)
│   ├── 05-the-body/               # Hardware setup + enclosure (not started)
│   ├── 06-the-soul/               # Integration + personality (not started)
│   ├── 07-presentation/           # Demo prep for birthday reveal
│   └── assistant/                 # THE ACTUAL CODEBASE (see assistant/CLAUDE.md)
│       ├── config.yaml            # All configuration (gitignored — has secrets)
│       ├── config.example.yaml    # Template with redacted secrets
│       ├── main.py                # Entry point, intent handling loop
│       ├── core/                  # Interfaces, config, registry, logger, personality
│       └── providers/             # Swappable implementations (brain, music, lights, etc.)
```

## Key technical decisions (already made)

- **LLM**: Ollama running locally, currently llama3.2:3b. Model is a config value, not a commitment.
- **Intent classification**: 3-step separated pipeline: Classification (extract raw params) → Enrichment (add artist if confident) → Dual YouTube Music search (enriched + raw query, raw wins on mismatch). This beats Alexa for Hindi song disambiguation.
- **Music**: ytmusicapi (no API key needed) + mpv for playback via IPC socket
- **Lights**: Tuya protocol via tinytuya for Wipro IoT bulbs
- **Personalities**: Multiple switchable personalities (Jarvis, Devesh, Chandler, etc.) — tone injected into system prompt, voice model per personality, optional per-personality music preferences
- **Logging**: Python logging module, level controlled by `config.yaml debug.log_level`, goes to stderr. User-facing output (assistant speech) goes to stdout via print().

## Hardware portability rules

This assistant MUST run on three platforms with zero code changes — only config differs:

| Platform | Role | GPU | RAM | LLM strategy |
|----------|------|-----|-----|--------------|
| MacBook (Apple Silicon) | Development + testing | Metal (MPS) | 16-32 GB | Ollama, larger models OK |
| Jetson Orin Nano | Primary deployment target | CUDA (Ampere) | 8 GB shared | Ollama or llama.cpp, 3B quantized |
| Raspberry Pi 4/5 | Low-cost fallback | None (CPU only) | 4-8 GB | Smallest models, or offload to server |

**Every line of code must follow these rules:**

1. **No platform-specific imports at module level.** If you need a platform-specific library (e.g., `jetson.gpio`, `RPi.GPIO`, `CoreAudio`), import it inside the function/method that uses it and handle `ImportError` gracefully. The assistant must start up on any platform even if a hardware library is missing.

2. **No hardcoded paths.** Use `pathlib.Path`, `tempfile.gettempdir()`, and config values. Never assume `/tmp`, `~/`, or macOS-specific paths. The mpv IPC socket already does this correctly.

3. **Audio abstraction is mandatory.** Mac uses CoreAudio/system default. Jetson uses ALSA/PulseAudio. Pi uses ALSA. All audio output (music, TTS, alerts) must go through the `AudioOutputProvider` interface — never call system audio APIs directly from music/voice code.

4. **GPU detection must be automatic.** For LLM inference, TTS, and STT: detect available acceleration at startup (CUDA → Metal → CPU) and configure accordingly. The user should never need to manually set "device: cuda" vs "device: mps" — `config.yaml` has `device: "auto"` as default.

5. **External process commands must be platform-checked.** `mpv`, `aplay`, `pactl`, `amixer` — check availability before calling. Use `shutil.which()` not hardcoded paths. Provide clear error messages when a dependency is missing, with platform-specific install instructions.

6. **Network assumptions = zero.** The assistant is local-first. Don't assume internet for core features. YouTube Music search needs internet, but LLM inference, TTS, STT, wake word, and lights are all local. If internet is down, music fails gracefully but everything else keeps working.

7. **Config.yaml `hardware.platform` field.** Set to `"auto"` by default (auto-detect via `platform.system()`, checking for Jetson via `/etc/nv_tegra_release`, Pi via `/proc/device-tree/model`). Can be forced in config for testing.

8. **Dependencies in requirements.txt must be cross-platform.** If a library is platform-specific (e.g., `tinytuya` is fine everywhere, but `jetson-gpio` is Jetson-only), mark it as optional and handle its absence. Use extras in setup: `pip install jarvis[jetson]`, `pip install jarvis[pi]`.

## Secrets — DO NOT COMMIT

These are gitignored but be aware:
- `jarvis/assistant/config.yaml` — has Tuya device IDs, local keys, IP addresses
- `jarvis/01-the-brain/experiments/tinytuya.json` — Tuya API keys
- `jarvis/01-the-brain/experiments/devices.json` — device keys
- `jarvis/01-the-brain/experiments/snapshot.json` — device data
- `jarvis/01-the-brain/experiments/tuya-raw.json` — raw Tuya API response

## Current state (as of March 25, 2026)

### Working
- Intent classification with command chaining ("play Sajni and set lights to red")
- Song disambiguation pipeline (classification → enrichment → dual search)
- Music playback via YouTube Music + mpv
- Light control via Tuya (on/off, color, brightness, scenes)
- Personality system (4 profiles, voice-command switching)
- Structured logging with color-coded terminal output
- Text-mode interactive loop

### Not started
- Speech-to-text (02-the-ears) — faster-whisper planned
- Text-to-speech (03-the-voice) — Piper TTS planned
- Wake word detection — OpenWakeWord planned
- AudioOutputProvider — interface defined, no implementation
- Hardware setup (05-the-body) — Jetson Orin Nano planned
- Speaker recognition for auto personality switching

## Running the assistant

```bash
cd jarvis/assistant
python main.py --text    # text mode (Mac simulation)
```

Requires: Ollama running locally (`ollama serve`), `config.yaml` in place.

## Eval framework

Song disambiguation evals live in `jarvis/01-the-brain/experiments/eval_song_disambiguation.py`. Results in `jarvis/01-the-brain/notes/eval-results/`. The eval tests the full pipeline (LLM enrichment → YouTube search → correct song?) against a baseline (raw input → YouTube, no LLM). Current scores: Llama 3.2:3b 93%, Qwen 2.5:3b 87%.

**Important**: The eval still uses the old single-LLM-call approach and needs updating for the separated pipeline.
