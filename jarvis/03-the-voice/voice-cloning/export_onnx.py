#!/usr/bin/env python3
"""
Export fine-tuned StyleTTS2 model to ONNX for production inference.
===================================================================
Converts the best PyTorch checkpoint to ONNX format, which is what
the Kokoro TTS provider uses at runtime (via onnxruntime).

Why ONNX?
  - No PyTorch dependency at inference time (lighter install)
  - ONNX Runtime supports CUDA EP (Jetson), CoreML EP (Mac), CPU EP (Pi)
  - Model optimizations: graph fusion, constant folding, quantization
  - Consistent performance across platforms

The exported ONNX model replaces the stock Kokoro model for the
Devesh personality. Other personalities continue using the default model.

Usage:
    python export_onnx.py                                     # Use best checkpoint
    python export_onnx.py --checkpoint checkpoints/epoch_100.pt
    python export_onnx.py --output devesh_voice.onnx
    python export_onnx.py --quantize int8                     # Smaller model
    python export_onnx.py --help

Output:
    devesh_finetuned.onnx          — exported model
    devesh_style_vector.npy        — your voice embedding (loaded at inference)
    devesh_voice_config.json       — config for the Kokoro TTS provider

Requirements:
    pip install torch onnx onnxruntime numpy
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import onnx
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

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


def main():
    parser = argparse.ArgumentParser(
        description="Export fine-tuned voice model to ONNX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python export_onnx.py
    python export_onnx.py --checkpoint checkpoints/best.pt
    python export_onnx.py --output ~/voices/devesh.onnx
    python export_onnx.py --quantize int8 --deploy
        """
    )
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to PyTorch checkpoint (default: checkpoints/best.pt)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output ONNX file path (default: devesh_finetuned.onnx)")
    parser.add_argument("--style-vector", type=str, default=None,
                        help="Path to style vector (default: checkpoints/style_vector.pt)")
    parser.add_argument("--quantize", type=str, choices=["none", "fp16", "int8"], default="none",
                        help="Post-export quantization (default: none)")
    parser.add_argument("--opset", type=int, default=17,
                        help="ONNX opset version (default: 17)")
    parser.add_argument("--deploy", action="store_true",
                        help="Copy output to assistant/voices/kokoro/ for immediate use")
    parser.add_argument("--validate", action="store_true", default=True,
                        help="Run validation after export (default: True)")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Training data dir (for vocab info, default: ./training_data)")
    args = parser.parse_args()

    if not HAS_TORCH:
        print(f"{RED}ERROR: PyTorch not installed. Run: pip install torch{RESET}")
        sys.exit(1)

    base_dir = Path(__file__).parent
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else base_dir / "checkpoints" / "best.pt"
    style_vector_path = Path(args.style_vector) if args.style_vector else base_dir / "checkpoints" / "style_vector.pt"
    data_dir = Path(args.data_dir) if args.data_dir else base_dir / "training_data"
    output_path = Path(args.output) if args.output else base_dir / "devesh_finetuned.onnx"

    if not checkpoint_path.exists():
        print(f"{RED}ERROR: Checkpoint not found: {checkpoint_path}{RESET}")
        print("Run finetune.py first.")
        sys.exit(1)

    print(f"""
{BOLD}{'=' * 60}
   JARVIS Voice Clone — ONNX Export
   Convert fine-tuned model to production format
{'=' * 60}{RESET}

  Checkpoint:    {checkpoint_path}
  Style vector:  {style_vector_path}
  Output:        {output_path}
  Quantize:      {args.quantize}
  Opset:         {args.opset}
""")

    # Load checkpoint
    print("  Loading checkpoint...")
    device = torch.device("cpu")  # Export always on CPU for compatibility
    checkpoint = torch.load(str(checkpoint_path), map_location=device)

    # Reconstruct model
    # We need to know the vocab size — try loading from training config
    config_path = data_dir / "config.json"
    vocab_size = 256  # default fallback
    if config_path.exists():
        with open(config_path) as f:
            data_config = json.load(f)
        # Vocab size isn't in config.json currently, so we use default
        # In a production setup, the vocab would be saved during prepare_data.py

    # Import the model class
    sys.path.insert(0, str(base_dir))
    from finetune import VoiceCloningModel

    model = VoiceCloningModel(vocab_size=vocab_size, style_dim=128)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    epoch = checkpoint.get("epoch", "?")
    loss = checkpoint.get("loss", "?")
    print(f"  Loaded model from epoch {epoch} (loss: {loss})")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Load style vector
    if style_vector_path.exists():
        style_vector = torch.load(str(style_vector_path), map_location=device)
        print(f"  Style vector: {style_vector.shape} (dim={style_vector.shape[0]})")
    else:
        print(f"  {YELLOW}Warning: Style vector not found. Generating dummy.{RESET}")
        style_vector = torch.zeros(128)

    # Create wrapper model for ONNX export
    # ONNX needs a single forward pass, so we create a wrapper that takes
    # phonemes as input and outputs mel spectrograms, using the pre-computed
    # style vector (your voice embedding) as a fixed parameter.
    class OnnxInferenceModel(torch.nn.Module):
        """Wrapper for ONNX export — bakes in the style vector."""

        def __init__(self, base_model, style_vec):
            super().__init__()
            self.phoneme_encoder = base_model.phoneme_encoder
            self.mel_decoder = base_model.mel_decoder
            # Register style vector as a buffer (constant in the graph)
            self.register_buffer("style", style_vec.unsqueeze(0))

        def forward(self, phonemes: torch.Tensor) -> torch.Tensor:
            """
            phonemes: [1, L] → mel: [1, 80, T]
            The style vector is baked in — no need to pass it at inference.
            """
            phone_enc = self.phoneme_encoder(phonemes)
            # Expand style to batch size (always 1 for inference)
            style = self.style.expand(phonemes.shape[0], -1)
            mel = self.mel_decoder(phone_enc, style)
            return mel

    export_model = OnnxInferenceModel(model, style_vector)
    export_model.eval()

    # Create dummy input for tracing
    dummy_phonemes = torch.randint(1, vocab_size, (1, 50))  # batch=1, seq_len=50

    # Export to ONNX
    print(f"\n  Exporting to ONNX (opset {args.opset})...")
    try:
        torch.onnx.export(
            export_model,
            (dummy_phonemes,),
            str(output_path),
            export_params=True,
            opset_version=args.opset,
            do_constant_folding=True,
            input_names=["phonemes"],
            output_names=["mel_spectrogram"],
            dynamic_axes={
                "phonemes": {0: "batch_size", 1: "sequence_length"},
                "mel_spectrogram": {0: "batch_size", 2: "mel_length"},
            },
        )
        print(f"  {GREEN}ONNX export successful!{RESET}")
    except Exception as e:
        print(f"  {RED}ONNX export failed: {e}{RESET}")
        sys.exit(1)

    # Check model size
    onnx_size = output_path.stat().st_size / (1024 * 1024)
    print(f"  Model size: {onnx_size:.1f} MB")

    # Validate ONNX model
    if args.validate and HAS_ONNX:
        print(f"\n  Validating ONNX model...")
        try:
            onnx_model = onnx.load(str(output_path))
            onnx.checker.check_model(onnx_model)
            print(f"  {GREEN}ONNX validation passed!{RESET}")
        except Exception as e:
            print(f"  {YELLOW}ONNX validation warning: {e}{RESET}")

    # Test inference with ONNX Runtime
    if args.validate and HAS_ORT:
        print(f"\n  Testing ONNX Runtime inference...")
        try:
            # Choose the best available EP
            available_eps = ort.get_available_providers()
            if "CUDAExecutionProvider" in available_eps:
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            elif "CoreMLExecutionProvider" in available_eps:
                providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
            else:
                providers = ["CPUExecutionProvider"]

            session = ort.InferenceSession(str(output_path), providers=providers)

            # Run inference
            test_input = np.random.randint(1, vocab_size, (1, 30)).astype(np.int64)

            import time
            start = time.monotonic()
            outputs = session.run(None, {"phonemes": test_input})
            elapsed = time.monotonic() - start

            mel_output = outputs[0]
            print(f"  Input:  phonemes shape {test_input.shape}")
            print(f"  Output: mel shape {mel_output.shape}")
            print(f"  Latency: {elapsed * 1000:.1f}ms")
            print(f"  Provider: {providers[0]}")
            print(f"  {GREEN}ONNX Runtime inference OK!{RESET}")
        except Exception as e:
            print(f"  {YELLOW}ONNX Runtime test failed: {e}{RESET}")
            print(f"  The model may still work — test with test_voice.py")

    # Post-export quantization
    if args.quantize != "none":
        print(f"\n  Applying {args.quantize} quantization...")
        try:
            if args.quantize == "fp16":
                from onnxruntime.transformers import float16
                fp16_model = float16.convert_float_to_float16(
                    onnx.load(str(output_path)),
                    keep_io_types=True,
                )
                quant_path = output_path.with_suffix(f".fp16.onnx")
                onnx.save(fp16_model, str(quant_path))
                quant_size = quant_path.stat().st_size / (1024 * 1024)
                print(f"  {GREEN}FP16 model: {quant_path.name} ({quant_size:.1f} MB){RESET}")

            elif args.quantize == "int8":
                from onnxruntime.quantization import quantize_dynamic, QuantType
                quant_path = output_path.with_suffix(f".int8.onnx")
                quantize_dynamic(
                    str(output_path),
                    str(quant_path),
                    weight_type=QuantType.QInt8,
                )
                quant_size = quant_path.stat().st_size / (1024 * 1024)
                print(f"  {GREEN}INT8 model: {quant_path.name} ({quant_size:.1f} MB){RESET}")

        except ImportError:
            print(f"  {YELLOW}Quantization requires: pip install onnxruntime[quantization]{RESET}")
        except Exception as e:
            print(f"  {YELLOW}Quantization failed: {e}{RESET}")

    # Save style vector as numpy (for inference without PyTorch)
    style_npy_path = output_path.with_name("devesh_style_vector.npy")
    np.save(str(style_npy_path), style_vector.numpy())
    print(f"\n  Style vector: {style_npy_path}")

    # Save voice config
    voice_config = {
        "voice_id": "devesh_finetuned",
        "display_name": "Devesh (Fine-tuned)",
        "model_file": output_path.name,
        "style_vector_file": style_npy_path.name,
        "sample_rate": 24000,
        "mel_channels": 80,
        "style_dim": 128,
        "source_checkpoint": str(checkpoint_path.name),
        "source_epoch": epoch,
        "source_loss": float(loss) if isinstance(loss, (int, float)) else None,
        "quantized_variants": [],
    }
    config_out = output_path.with_name("devesh_voice_config.json")
    with open(config_out, "w") as f:
        json.dump(voice_config, f, indent=2)
    print(f"  Voice config: {config_out}")

    # Deploy to assistant voices directory
    if args.deploy:
        voices_dir = base_dir.parent.parent / "assistant" / "voices" / "kokoro"
        if voices_dir.exists():
            print(f"\n  Deploying to {voices_dir}...")
            shutil.copy2(str(output_path), str(voices_dir / output_path.name))
            shutil.copy2(str(style_npy_path), str(voices_dir / style_npy_path.name))
            shutil.copy2(str(config_out), str(voices_dir / config_out.name))
            print(f"  {GREEN}Deployed! Update config.yaml:{RESET}")
            print(f"    personalities.profiles.devesh.voice_model: \"devesh_finetuned\"")
        else:
            print(f"\n  {YELLOW}Voices dir not found: {voices_dir}{RESET}")
            print(f"  Manually copy files to your Kokoro voices directory.")

    print(f"""
{'=' * 60}
  Export complete!

  Files:
    {output_path}        — ONNX model
    {style_npy_path}     — voice embedding
    {config_out}         — voice config

  To use in the assistant:
    1. Copy files to jarvis/assistant/voices/kokoro/
    2. Update config.yaml:
       personalities:
         profiles:
           devesh:
             voice_provider: "kokoro"
             voice_model: "devesh_finetuned"
    3. The Kokoro provider will need a small update to load
       custom ONNX models (see README.md for details)

  Or test first: python test_voice.py
{'=' * 60}
""")


if __name__ == "__main__":
    main()
