---
name: Voice cloning training — DEFERRED
description: Audio recording + StyleTTS2 fine-tuning pipeline is built but Devesh hasn't recorded yet. PROMPT HIM about quality check + recording when he asks to "work on audio" or "voice training" again.
type: project
---

## Current state (deferred)

The complete voice cloning pipeline is built and committed at `jarvis/03-the-voice/voice-cloning/`. Everything is ready — Devesh just hasn't recorded the training audio yet because he doesn't have time right now.

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
