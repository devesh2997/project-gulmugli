---
name: Session handoff — read first
description: Latest session state. Read this at the start of any new session to know what's done, what's paused, and what's likely next.
type: handoff
---

# JARVIS — Session Handoff (April 2026)

## Status snapshot

| Component | State |
|-----------|-------|
| Backend (Python, FastAPI + FaceUI WebSocket) | ✅ Working. Ports 8765 + 8766. |
| React dashboard | ✅ Working. Vite on port 5173. |
| Flutter companion app | ✅ Built. Runs on Android emulator (Nothing_4a) and Mac. Auth disabled in dev mode. |
| Voice cloning pipeline | ⏸️ **PAUSED** — Devesh recorded 29/214 clips (~1.8 min). EarPods, 29.6 dB SNR, "GOOD ENOUGH." Resume with `--resume`. |
| Jetson Orin Nano | ✅ Hardware received. Setup guide written (`jarvis/05-the-body/JETSON_SETUP.md`). Not yet flashed. |
| Other peripherals | 🛒 Shopping list ready (`HARDWARE_SHOPPING_LIST.md` + `JARVIS_SHOPPING_GUIDE.html`). NOT YET PURCHASED: NVMe 2280 SSD, 19V 5.5×2.5mm power supply, DP→HDMI adapter, 40mm 5V fan, ReSpeaker mic, Waveshare 5.5" AMOLED. |

## Repo state

- All committed and pushed to `main` (last commit: `9ac093c`)
- Branch is clean
- Voice recordings + training data are gitignored (personal data)
- Flutter app's `pubspec.lock`, `.dart_tool/`, etc. gitignored

## Known live issues (not bugs in code, environment-related)

1. **Audio device conflict on Mac** — wake word listener and TTS playback fight over EarPods (PortAudio `-9986` error). Workaround: System Settings → Sound → set Output to "MacBook Pro Speakers", keep Input as EarPods. Real fix: doesn't matter, will be on Jetson with separate USB mic + speaker.
2. **Slow inference on Mac** — 37 tok/s with verbose responses ≈ 20s round-trip. On Jetson with CUDA + INT4 quantization, expected ~3-5s. Not blocking.
3. **`hey_devesh` and `hey_chandler` wake words not loaded** — only `hey_jarvis` works (only built-in OpenWakeWord model). Custom wake word training is a future task.

## What's likely next (in priority order)

1. **Set up the Jetson Orin Nano** once peripherals arrive (NVMe + power + cooling fan + DP→HDMI adapter). Follow `jarvis/05-the-body/JETSON_SETUP.md` — 8-phase guide is ready.
2. **Resume voice cloning** — Devesh has 185 more prompts to record (~30-40 minutes more recording time). After that: transcribe → prepare → finetune → export → deploy.
3. **Order missing peripherals** — Sector 14 Gurgaon walk-in or Robocraze online (ReSpeaker + AMOLED touchscreen).
4. **Tighten LLM system prompts** — responses are too verbose, taking 15-20s. Edit `providers/brain/ollama.py` to enforce shorter replies.
5. **Custom wake words** — train OpenWakeWord on "Hey Devesh" / "Hey Chandler" / etc. for personality-specific activation.

## How to bring services up

```bash
# Backend (auto-detects wake word + mic mode)
cd /Users/devesh/Projects/project-gulmugli/jarvis/assistant
source /Users/devesh/Projects/project-gulmugli/.venv/bin/activate
python main.py

# Dashboard (probably still running on 5173)
cd /Users/devesh/Projects/project-gulmugli/jarvis/assistant/dashboard
pnpm dev

# Flutter app on Android emulator
cd /Users/devesh/Projects/project-gulmugli/app
AUDIO_INPUT_DEVICE="earpods" /Users/devesh/Projects/project-gulmugli/.venv/bin/python jarvis/03-the-voice/voice-cloning/record_voice.py --resume
```

## Important files for next agent

- `/Users/devesh/Projects/project-gulmugli/jarvis/CLAUDE.md` — module structure
- `/Users/devesh/Projects/project-gulmugli/jarvis/assistant/CLAUDE.md` — codebase patterns (provider model, intent pipeline)
- `/Users/devesh/Projects/project-gulmugli/CLAUDE.md` — top-level (hardware portability rules)
- `/Users/devesh/Projects/project-gulmugli/jarvis/05-the-body/JETSON_SETUP.md` — Jetson deployment guide
- `/Users/devesh/Projects/project-gulmugli/jarvis/05-the-body/HARDWARE_SHOPPING_LIST.md` — peripherals list

## Communication style reminders

Devesh is a senior dev — skip software engineering basics. **DO** explain AI/hardware deeply (quantization, KV cache, mel spectrograms, GPIO, audio device routing). **DON'T** explain HTTP/async/classes/dataclasses.

He pushes back on over-confident answers and stale data — verify with web searches before quoting prices or specs. Was off by ~3x on SSD prices in last session because of stale cached estimates.
