# Voice Cloning Pipeline for JARVIS

Clone your voice so the "Devesh" personality sounds like you. Uses StyleTTS2/Kokoro architecture with transfer learning from the pre-trained Kokoro model.

## How it works

The pipeline has 6 steps:

```
Record → Transcribe → Prepare → Fine-tune → Export → Deploy
```

**Record** your voice reading 200+ prompts (15-30 minutes of audio). **Transcribe** with Whisper to get accurate text. **Prepare** normalizes audio, generates phonemes, creates train/val splits. **Fine-tune** adapts the StyleTTS2 style encoder + decoder to your voice (freezes the text encoder so it doesn't forget language). **Export** to ONNX for fast inference. **Deploy** by copying into the assistant's voices directory.

Total time: ~2 hours recording + 1-2 hours training on GPU.

## Prerequisites

```bash
# System dependencies
brew install espeak-ng          # macOS
# sudo apt install espeak-ng    # Linux/Jetson

# Python dependencies
pip install -r requirements.txt

# PyTorch (install separately for your platform)
# macOS:
pip install torch torchaudio
# CUDA (Jetson/desktop GPU):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Step-by-Step

### 1. Record your voice

```bash
python record_voice.py
```

Interactive session: shows prompts, records your voice, auto-trims silence. Covers English, Hindi, Hinglish across multiple emotional styles (calm, excited, sarcastic, storytelling, technical, etc.).

- 200+ prompts, 5-15 seconds each
- Aim for 15-30 minutes total
- Skip/re-record any prompt
- Progress auto-saves (resume with `--resume`)
- Preview all prompts: `python record_voice.py --list-prompts`

Output: `recordings/clip_XXXX_style_lang.wav`

### 2. Transcribe recordings

```bash
python transcribe.py
```

Uses faster-whisper to transcribe every clip. Compares against the original prompts and flags mismatches (you may have ad-libbed or misspoken).

- Uses the `medium` model by default (good for Hindi)
- Supports CUDA and CPU
- Generates `metadata.csv` for the next step

Output: `recordings/metadata.csv`, `recordings/alignment_report.txt`

### 3. Prepare training data

```bash
python prepare_data.py
```

Normalizes audio, generates phonemes, creates train/val manifests.

- Peak normalization to -1 dB
- Resamples to 24kHz mono
- Splits clips longer than 15s
- 90/10 train/val split
- Phoneme generation via espeak-ng (falls back to raw text if unavailable)

Output: `training_data/wavs/`, `training_data/train.txt`, `training_data/val.txt`

### 4. Fine-tune the model

```bash
# On Mac (MPS)
python finetune.py --device auto --epochs 100

# On Jetson (CUDA)
python finetune.py --device cuda --epochs 100 --batch-size 8

# Resume interrupted training
python finetune.py --resume checkpoints/epoch_0050.pt
```

Fine-tunes only the style encoder + mel decoder (text encoder is frozen). This is transfer learning: the model already knows how to speak, it just learns your voice characteristics.

Key hyperparameters:
- `--lr 1e-4` — low learning rate preserves pre-trained knowledge
- `--batch-size 4` — fits in 8GB VRAM (Jetson)
- `--grad-accum 4` — effective batch size of 16
- `--epochs 100` — small dataset needs many passes
- Saves checkpoints every 10 epochs

Output: `checkpoints/best.pt`, `checkpoints/style_vector.pt`

### 5. Export to ONNX

```bash
python export_onnx.py

# With quantization for smaller model
python export_onnx.py --quantize int8

# Auto-deploy to assistant
python export_onnx.py --deploy
```

Converts PyTorch model to ONNX with dynamic axes (handles variable-length text). Validates with ONNX Runtime. Optionally quantizes to fp16 or int8.

Output: `devesh_finetuned.onnx`, `devesh_style_vector.npy`, `devesh_voice_config.json`

### 6. Test the voice

```bash
python test_voice.py --play

# Compare with base Kokoro model
python test_voice.py --compare

# Test ONNX model directly
python test_voice.py --onnx-model devesh_finetuned.onnx --play
```

Generates 10 test sentences across English, Hindi, Hinglish and multiple styles. Listen and evaluate if it sounds like you.

Output: `test_output/*.wav`, `test_output/benchmark.json`

### 7. Deploy to the assistant

```bash
# Option A: auto-deploy with export script
python export_onnx.py --deploy

# Option B: manual
cp devesh_finetuned.onnx ../../assistant/voices/kokoro/
cp devesh_style_vector.npy ../../assistant/voices/kokoro/
cp devesh_voice_config.json ../../assistant/voices/kokoro/
```

Then update `config.yaml`:
```yaml
personalities:
  profiles:
    devesh:
      voice_provider: "kokoro"
      voice_model: "devesh_finetuned"
```

The Kokoro TTS provider will need a small update to support loading custom fine-tuned models alongside the base model. The key change is: when `voice_model` points to a custom ONNX file, load that model and use the associated style vector instead of the preset voice embeddings.

## Directory structure after completion

```
voice-cloning/
  record_voice.py          # Step 1: Record
  transcribe.py            # Step 2: Transcribe
  prepare_data.py          # Step 3: Prepare
  finetune.py              # Step 4: Train
  export_onnx.py           # Step 5: Export
  test_voice.py            # Step 6: Test
  requirements.txt         # Python dependencies
  README.md                # This file
  recordings/              # Raw recordings
    clip_0000_*.wav
    metadata.csv
    progress.json
  training_data/           # Processed data
    wavs/
    train.txt
    val.txt
    config.json
  checkpoints/             # Training checkpoints
    best.pt
    final.pt
    style_vector.pt
    loss_history.json
  test_output/             # Test results
    test_*.wav
    benchmark.json
  devesh_finetuned.onnx    # Production model
  devesh_style_vector.npy  # Voice embedding
  devesh_voice_config.json # Model config
```

## How much data do you need?

| Amount | Quality | Notes |
|--------|---------|-------|
| 5 min | Poor | Barely captures your voice. Good for testing the pipeline. |
| 15 min | Decent | Recognizably you, but may sound flat on some emotions. |
| 30 min | Good | Natural across most styles. This is the target. |
| 60 min | Great | Captures nuances, emotional range, code-switching. |

The 200+ prompts in `record_voice.py` produce roughly 20-30 minutes of audio depending on your speaking pace.

## Troubleshooting

**Mic not detected**: Check `python -c "import sounddevice; print(sounddevice.query_devices())"` and ensure your mic is the default input.

**espeak-ng not found**: Install the system package (`brew install espeak-ng` on Mac, `sudo apt install espeak-ng` on Linux). The pipeline falls back to raw text if unavailable, but phonemes produce better results.

**Out of memory during training**: Reduce `--batch-size` to 2 or 1. Increase `--grad-accum` to compensate (e.g., batch_size=2, grad_accum=8 for effective batch of 16).

**Training loss not decreasing**: Try lowering `--lr` to 5e-5. If it plateaus, the model may need more data — record more prompts.

**ONNX export fails**: Ensure PyTorch and ONNX versions are compatible. Try `--opset 14` (lower opset for wider compatibility).

**MPS errors on Mac**: Some PyTorch ops aren't fully supported on MPS yet. If training crashes, try `--device cpu` (slower but reliable).
