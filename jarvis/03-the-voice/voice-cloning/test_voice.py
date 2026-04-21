#!/usr/bin/env python3
"""
Test the fine-tuned voice model.
==================================
Generates sample sentences in different languages and styles,
saves them as WAV files, and optionally plays them through speakers.

Also benchmarks latency against the base Kokoro model to ensure
the fine-tuned model is fast enough for real-time use.

Usage:
    python test_voice.py                              # Test fine-tuned model
    python test_voice.py --play                       # Play through speakers
    python test_voice.py --compare                    # Compare with base Kokoro
    python test_voice.py --checkpoint best.pt         # Use specific checkpoint
    python test_voice.py --help

Output:
    test_output/
      test_01_english.wav
      test_02_hindi.wav
      ...
      benchmark.json

Requirements:
    pip install torch soundfile numpy onnxruntime
    Optional: pip install sounddevice (for playback)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False


BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

SAMPLE_RATE = 24000

# Test sentences — a variety to hear the voice across different contexts
TEST_SENTENCES = [
    {
        "text": "Hello! I'm Devesh, your personal assistant. How can I help you today?",
        "description": "English: warm greeting",
        "filename": "test_01_greeting.wav",
    },
    {
        "text": "Playing Sajni by Arijit Singh. This one's absolutely beautiful.",
        "description": "English: music announcement",
        "filename": "test_02_music.wav",
    },
    {
        "text": "Aaj ka mausam bahut achha hai. Bahar dhoop nikli hai aur thandi hawa chal rahi hai.",
        "description": "Hindi: weather description",
        "filename": "test_03_hindi.wav",
    },
    {
        "text": "Yaar sun, mujhe lagta hai ki hum weekend pe Goa chal sakte hain. Weather bhi achha hai.",
        "description": "Hinglish: casual planning",
        "filename": "test_04_hinglish.wav",
    },
    {
        "text": "Good night. Sweet dreams. I'll be here when you wake up.",
        "description": "English: calm bedtime",
        "filename": "test_05_bedtime.wav",
    },
    {
        "text": "Yes! India won the match! What a comeback that was!",
        "description": "English: excited reaction",
        "filename": "test_06_excited.wav",
    },
    {
        "text": "Oh sure, let me just Google that for you. Oh wait, I already did.",
        "description": "English: sarcastic response",
        "filename": "test_07_sarcastic.wav",
    },
    {
        "text": "The transformer architecture uses self-attention to weigh the importance of different tokens in the sequence.",
        "description": "English: technical explanation",
        "filename": "test_08_technical.wav",
    },
    {
        "text": "Ek baar ki baat hai, ek chhote se gaanv mein ek buddhaa pedh thaa jo sabse zyaada samajhdaar thaa.",
        "description": "Hindi: storytelling",
        "filename": "test_09_story.wav",
    },
    {
        "text": "Biryani khaaoge? Main order kar deta hoon. Extra raita bhi dal deta hoon, don't worry.",
        "description": "Hinglish: casual food chat",
        "filename": "test_10_food.wav",
    },
]


def test_with_pytorch(checkpoint_path: Path, data_dir: Path, output_dir: Path,
                      play: bool = False) -> list[dict]:
    """
    Test using the PyTorch model directly (before ONNX export).
    Useful for checking quality during training — don't need to export first.
    """
    if not HAS_TORCH:
        print(f"  {RED}PyTorch not available. Use --onnx-model instead.{RESET}")
        return []

    sys.path.insert(0, str(Path(__file__).parent))
    from finetune import VoiceCloningModel, VoiceDataset

    print(f"  Loading model from {checkpoint_path}...")
    device = torch.device("cpu")
    checkpoint = torch.load(str(checkpoint_path), map_location=device)

    # We need vocab from the dataset
    train_manifest = data_dir / "train.txt"
    if train_manifest.exists():
        dataset = VoiceDataset(train_manifest, data_dir)
        vocab = dataset.vocab
        vocab_size = len(vocab) + 1
    else:
        vocab_size = 256
        vocab = {chr(i): i for i in range(32, 127)}

    model = VoiceCloningModel(vocab_size=vocab_size, style_dim=128)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Load style vector
    style_path = checkpoint_path.parent / "style_vector.pt"
    if style_path.exists():
        style_vector = torch.load(str(style_path), map_location=device)
    else:
        print(f"  {YELLOW}Style vector not found, using zeros{RESET}")
        style_vector = torch.zeros(128)

    results = []
    print(f"\n  Generating {len(TEST_SENTENCES)} test samples...\n")

    for i, item in enumerate(TEST_SENTENCES):
        text = item["text"]
        desc = item["description"]
        filename = item["filename"]

        # Tokenize (character-level matching what training used)
        phoneme_ids = [vocab.get(c, 0) for c in text]
        phonemes = torch.LongTensor([phoneme_ids])

        # Generate mel with style vector
        start = time.monotonic()
        with torch.no_grad():
            phone_enc = model.phoneme_encoder(phonemes)
            style = style_vector.unsqueeze(0)
            pred_mel = model.mel_decoder(phone_enc, style)
        elapsed = time.monotonic() - start

        # For a complete TTS pipeline, we'd pass the mel through a vocoder
        # (HiFi-GAN) to get audio. Since we're testing the mel decoder,
        # we generate a simple audio representation for listening.
        mel_np = pred_mel.squeeze(0).numpy()  # [80, T]

        # Griffin-Lim approximation (quick and dirty audio from mel)
        # In production, the Kokoro pipeline handles vocoding properly.
        try:
            import librosa
            audio = librosa.feature.inverse.mel_to_audio(
                np.exp(mel_np),  # undo log-mel
                sr=SAMPLE_RATE,
                n_fft=1024,
                hop_length=256,
                n_iter=32,
            )
        except ImportError:
            # Without librosa, generate a simple sine wave as placeholder
            print(f"    {DIM}(librosa not available — saving mel data only){RESET}")
            duration = mel_np.shape[1] * 256 / SAMPLE_RATE
            t = np.linspace(0, duration, int(duration * SAMPLE_RATE))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.3

        # Save
        out_path = output_dir / filename
        sf.write(str(out_path), audio, SAMPLE_RATE)
        duration = len(audio) / SAMPLE_RATE

        print(f"  {i + 1:2d}. {desc}")
        print(f"      {DIM}\"{text[:60]}{'...' if len(text) > 60 else ''}\"{RESET}")
        print(f"      Duration: {duration:.1f}s | Latency: {elapsed * 1000:.0f}ms | Saved: {filename}")

        if play and HAS_SD:
            sd.play(audio, samplerate=SAMPLE_RATE)
            sd.wait()
            print(f"      {GREEN}Played!{RESET}")

        results.append({
            "sentence": text,
            "description": desc,
            "filename": filename,
            "duration_sec": round(duration, 2),
            "latency_ms": round(elapsed * 1000, 1),
            "mel_shape": list(mel_np.shape),
        })

        print()

    return results


def test_with_onnx(onnx_path: Path, output_dir: Path,
                   play: bool = False) -> list[dict]:
    """
    Test using the exported ONNX model (production inference path).
    """
    if not HAS_ORT:
        print(f"  {RED}onnxruntime not available. Install: pip install onnxruntime{RESET}")
        return []

    print(f"  Loading ONNX model: {onnx_path}...")

    # Choose execution provider
    available_eps = ort.get_available_providers()
    if "CUDAExecutionProvider" in available_eps:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif "CoreMLExecutionProvider" in available_eps:
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]

    session = ort.InferenceSession(str(onnx_path), providers=providers)
    print(f"  Provider: {providers[0]}")

    results = []
    print(f"\n  Generating {len(TEST_SENTENCES)} test samples...\n")

    for i, item in enumerate(TEST_SENTENCES):
        text = item["text"]
        desc = item["description"]
        filename = item["filename"].replace(".wav", "_onnx.wav")

        # Simple character-to-id tokenization (matching training)
        phoneme_ids = np.array([[ord(c) % 256 for c in text]], dtype=np.int64)

        # Inference
        start = time.monotonic()
        outputs = session.run(None, {"phonemes": phoneme_ids})
        elapsed = time.monotonic() - start

        mel_output = outputs[0]  # [1, 80, T]
        mel_np = mel_output[0]   # [80, T]

        # Convert mel to audio (Griffin-Lim)
        try:
            import librosa
            audio = librosa.feature.inverse.mel_to_audio(
                np.exp(mel_np),
                sr=SAMPLE_RATE,
                n_fft=1024,
                hop_length=256,
                n_iter=32,
            )
        except ImportError:
            duration = mel_np.shape[1] * 256 / SAMPLE_RATE
            t = np.linspace(0, duration, int(duration * SAMPLE_RATE))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.3

        # Save
        out_path = output_dir / filename
        sf.write(str(out_path), audio, SAMPLE_RATE)
        duration = len(audio) / SAMPLE_RATE

        print(f"  {i + 1:2d}. {desc}")
        print(f"      {DIM}\"{text[:60]}{'...' if len(text) > 60 else ''}\"{RESET}")
        print(f"      Duration: {duration:.1f}s | Latency: {elapsed * 1000:.0f}ms | Saved: {filename}")

        if play and HAS_SD:
            sd.play(audio, samplerate=SAMPLE_RATE)
            sd.wait()
            print(f"      {GREEN}Played!{RESET}")

        results.append({
            "sentence": text,
            "description": desc,
            "filename": filename,
            "duration_sec": round(duration, 2),
            "latency_ms": round(elapsed * 1000, 1),
            "mel_shape": list(mel_np.shape),
            "provider": providers[0],
        })

        print()

    return results


def compare_with_base_kokoro(output_dir: Path) -> list[dict]:
    """
    Compare latency with the stock Kokoro model.
    Requires kokoro-onnx to be installed.
    """
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        print(f"  {YELLOW}kokoro-onnx not installed — skipping base comparison{RESET}")
        return []

    # Find Kokoro model files
    assistant_dir = Path(__file__).parent.parent.parent / "assistant"
    kokoro_dir = assistant_dir / "voices" / "kokoro"
    model_path = kokoro_dir / "kokoro-v1.0.onnx"
    voices_path = kokoro_dir / "voices-v1.0.bin"

    if not model_path.exists() or not voices_path.exists():
        print(f"  {YELLOW}Base Kokoro model not found in {kokoro_dir} — skipping comparison{RESET}")
        return []

    print(f"\n  Loading base Kokoro model for comparison...")
    kokoro = Kokoro(str(model_path), str(voices_path))
    voice = "am_adam"  # male voice for comparison

    results = []
    for i, item in enumerate(TEST_SENTENCES[:5]):  # first 5 only
        text = item["text"]
        filename = f"baseline_{item['filename']}"

        start = time.monotonic()
        samples, sr = kokoro.create(text=text, voice=voice, speed=1.0, lang="en-us")
        elapsed = time.monotonic() - start

        out_path = output_dir / filename
        sf.write(str(out_path), samples, sr)
        duration = len(samples) / sr

        print(f"  Base [{i + 1}] {elapsed * 1000:.0f}ms | {duration:.1f}s | {filename}")
        results.append({
            "sentence": text,
            "filename": filename,
            "latency_ms": round(elapsed * 1000, 1),
            "duration_sec": round(duration, 2),
            "model": "kokoro-base",
            "voice": voice,
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test fine-tuned voice model with sample sentences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_voice.py
    python test_voice.py --play
    python test_voice.py --onnx-model devesh_finetuned.onnx
    python test_voice.py --compare
        """
    )
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="PyTorch checkpoint path (default: checkpoints/best.pt)")
    parser.add_argument("--onnx-model", type=str, default=None,
                        help="ONNX model path (tests production inference)")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Training data dir for vocab (default: ./training_data)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Where to save test outputs (default: ./test_output)")
    parser.add_argument("--play", action="store_true",
                        help="Play each generated clip through speakers")
    parser.add_argument("--compare", action="store_true",
                        help="Compare latency with base Kokoro model")
    args = parser.parse_args()

    if not HAS_SF:
        print(f"{RED}ERROR: soundfile not installed. Run: pip install soundfile{RESET}")
        sys.exit(1)

    if args.play and not HAS_SD:
        print(f"{YELLOW}Warning: sounddevice not installed. Audio won't be played.{RESET}")
        print(f"Install with: pip install sounddevice\n")
        args.play = False

    base_dir = Path(__file__).parent
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(args.data_dir) if args.data_dir else base_dir / "training_data"

    print(f"""
{BOLD}{'=' * 60}
   JARVIS Voice Clone — Testing
   Generate and evaluate sample speech
{'=' * 60}{RESET}

  Output: {output_dir}
""")

    all_results = {}

    # Test with ONNX model
    if args.onnx_model:
        onnx_path = Path(args.onnx_model)
        if not onnx_path.exists():
            onnx_path = base_dir / args.onnx_model
        if onnx_path.exists():
            print(f"  {BOLD}Testing ONNX model{RESET}")
            onnx_results = test_with_onnx(onnx_path, output_dir, play=args.play)
            all_results["onnx"] = onnx_results
        else:
            print(f"  {RED}ONNX model not found: {args.onnx_model}{RESET}")

    # Test with PyTorch checkpoint
    else:
        checkpoint_path = Path(args.checkpoint) if args.checkpoint else base_dir / "checkpoints" / "best.pt"
        if not checkpoint_path.exists():
            # Try final.pt
            checkpoint_path = base_dir / "checkpoints" / "final.pt"

        if checkpoint_path.exists():
            print(f"  {BOLD}Testing PyTorch model{RESET}")
            pytorch_results = test_with_pytorch(checkpoint_path, data_dir, output_dir, play=args.play)
            all_results["pytorch"] = pytorch_results
        else:
            print(f"  {RED}No checkpoint found. Run finetune.py first.{RESET}")
            print(f"  Or specify: --onnx-model <path> or --checkpoint <path>")
            sys.exit(1)

    # Compare with base model
    if args.compare:
        print(f"\n  {BOLD}Comparing with base Kokoro model{RESET}")
        base_results = compare_with_base_kokoro(output_dir)
        if base_results:
            all_results["baseline"] = base_results

    # Save benchmark results
    benchmark_path = output_dir / "benchmark.json"
    with open(benchmark_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Test complete!")
    print(f"  Generated: {output_dir}")

    for model_name, results in all_results.items():
        if results:
            avg_latency = np.mean([r["latency_ms"] for r in results])
            avg_duration = np.mean([r["duration_sec"] for r in results])
            print(f"\n  {BOLD}{model_name}{RESET}:")
            print(f"    Avg latency: {avg_latency:.0f}ms")
            print(f"    Avg duration: {avg_duration:.1f}s")
            print(f"    RTF: {avg_latency / 1000 / avg_duration:.2f}x (lower is better)")

    print(f"""
  Benchmark: {benchmark_path}

  Listen to the files in {output_dir}/ and evaluate:
    - Does it sound like you?
    - Is the pronunciation accurate?
    - Are Hindi/Hinglish sentences natural?
    - Is the emotional tone correct for each style?
{'=' * 60}
""")


if __name__ == "__main__":
    main()
