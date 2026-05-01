---
name: Voice cloning training — DEFERRED (in progress)
description: Audio recording in progress — Devesh has recorded 29/214 clips (~1.8 min of 30+ min target). PROMPT HIM to resume with `--resume` flag when he asks to "work on audio" or "voice training" again.
type: project
---

## Current state (paused mid-recording)

**Progress as of last session:**
- ✅ Audio quality check passed (29.6 dB SNR with EarPods, "GOOD ENOUGH" verdict)
- ✅ Recording session started — **29 clips recorded** so far (~1.8 minutes of audio)
- ⏸️ **Paused** — Devesh wants to come back to it later. He'll continue from clip 30.
- File location: `jarvis/03-the-voice/voice-cloning/recordings/`
- Progress file: `recordings/progress.json` (handles resume automatically)

**Resume command (when he comes back):**
```bash
cd /Users/devesh/Projects/project-gulmugli
AUDIO_INPUT_DEVICE="earpods" /Users/devesh/Projects/project-gulmugli/.venv/bin/python jarvis/03-the-voice/voice-cloning/record_voice.py --resume
```

The complete voice cloning pipeline is built and committed at `jarvis/03-the-voice/voice-cloning/`. Recording is the only step that needs human time.

## What exists (already done)

**8 scripts in `jarvis/03-the-voice/voice-cloning/`:**

1. **`check_audio_quality.py`** — quick 12-second test recording that analyzes:
   - Background noise floor (want < -40dB)
   - Speech level (not too quiet, not clipping)
   - SNR (want > 25dB)
   - Clipping detection
   - Dynamic range (catches monotone speech)
   - Plays back so user can hear themselves
   - Pass/fail verdict with fix suggestions

2. **`record_voice.py`** — interactive recording studio with 214 prompts across:
   - 15 emotional styles (assistant, casual, excited, calm, sarcastic, storytelling, technical, etc.)
   - 3 languages (English 157, Hindi 28, Hinglish 29)
   - Auto-silence detection, silence trimming, mic calibration, progress tracking with JSON save/resume

3. **`transcribe.py`** — faster-whisper auto-transcription + alignment validation

4. **`prepare_data.py`** — audio normalization, phoneme generation, train/val split

5. **`finetune.py`** — StyleTTS2 transfer learning from Kokoro base. Freezes text encoder, trains style encoder + decoder. Supports CUDA/MPS/CPU.

6. **`export_onnx.py`** — PyTorch → ONNX with dynamic axes, optional quantization

7. **`test_voice.py`** — benchmark against stock Kokoro, latency comparison

8. **`README.md`** — step-by-step guide

## Decisions already made

- **StyleTTS2 fine-tuning** chosen over RVC, XTTS, full TTS training because:
  - Same architecture as Kokoro (already in production)
  - Zero extra inference cost (~100-200ms on Jetson, same as base)
  - Best quality-to-effort ratio
  - 2-3 hours of recording → near-identical voice clone

- **Latency budget on Jetson** validated:
  - Total user-stops-talking → first word: ~4 seconds (comparable to Alexa/Google)
  - Fine-tuned voice runs at same speed as base Kokoro

## What Devesh needs to do (NEXT TIME)

**Step 1**: Run quality check FIRST — don't waste hours recording bad audio:
```bash
cd jarvis/03-the-voice/voice-cloning
python check_audio_quality.py
```

If it says 🎉 PERFECT or 👍 GOOD ENOUGH → proceed.
If it flags issues → fix mic/room and re-run.

**Step 2**: Full recording session (2-3 hours total, can split across multiple sessions):
```bash
python record_voice.py
```

**Step 3**: Process and train:
```bash
python transcribe.py
python prepare_data.py
python finetune.py --device cuda --epochs 100  # On Jetson
python export_onnx.py
python test_voice.py --play
```

**Step 4**: Deploy — copy ONNX to `jarvis/assistant/voices/kokoro/devesh_finetuned.onnx`, update `config.yaml` to set Devesh personality `voice_model: "devesh_finetuned"`.

## How to resurface this

When Devesh says any of these, REMIND HIM about the quality check first:
- "Let's work on audio training"
- "Let's clone my voice"
- "Let's start recording"
- "Voice training"
- Anything related to audio recording / voice cloning / StyleTTS2

Tell him: "Before recording 2-3 hours, run `python check_audio_quality.py` first to verify your mic setup. We built it specifically so you don't waste time on unusable audio."
