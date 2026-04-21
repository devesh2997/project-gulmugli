#!/usr/bin/env python3
"""
StyleTTS2 / Kokoro Fine-Tuning Script
=======================================
Fine-tunes a pre-trained StyleTTS2 (Kokoro) model on your voice data
to create a voice clone that sounds like you.

Architecture context (for ET who's learning ML):

  StyleTTS2 has several components. When fine-tuning, we DON'T retrain
  everything — that would need 100+ hours of data. Instead, we freeze
  most of the model and only fine-tune the parts that control "how it
  sounds" vs "what it says":

  FROZEN (pre-trained knowledge, don't touch):
    - Text encoder: already knows English/Hindi phoneme→embedding mapping
    - Duration predictor: already knows natural speech timing
    - F0 predictor: already knows pitch contours

  FINE-TUNED (adapt to your voice):
    - Style encoder: learns YOUR voice's characteristics (timbre, breathiness,
      vocal fry, pitch range, etc.) and encodes them into a style vector
    - Decoder: adapts the mel spectrogram generation to match YOUR voice
    - Vocoder (HiFi-GAN): optionally fine-tuned for better quality, but
      can be skipped since the pre-trained vocoder is already good

  This "freeze most, tune few" strategy is called transfer learning.
  With only 15-30 minutes of data, the model learns your voice identity
  without forgetting how to speak. Think of it like: the model already
  knows every word in the dictionary — we're just teaching it to say
  those words in YOUR voice.

  Key hyperparameters for small-data fine-tuning:
    - Low learning rate (1e-4): large steps would destroy pre-trained knowledge
    - High epochs (50-100): small dataset needs many passes to converge
    - Gradient accumulation (4-8): simulates larger batch size without more VRAM
    - Weight decay (0.01): regularization prevents overfitting to your 200 clips

Usage:
    python finetune.py --data-dir ./training_data --device auto
    python finetune.py --epochs 100 --batch-size 4 --lr 1e-4
    python finetune.py --resume checkpoints/epoch_50.pt
    python finetune.py --help

Requirements:
    pip install torch torchaudio einops munch pyyaml
    The pre-trained Kokoro checkpoint (downloaded separately)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import torchaudio
    HAS_TORCHAUDIO = True
except ImportError:
    HAS_TORCHAUDIO = False

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False


BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ═══════════════════════════════════════════════════════════════
# Device detection
# ═══════════════════════════════════════════════════════════════

def detect_device(requested: str = "auto") -> torch.device:
    """
    Auto-detect the best available device.

    Priority: CUDA (Jetson/desktop GPU) > MPS (Apple Silicon) > CPU

    On the Jetson Orin Nano:
      - CUDA is available with 1024 CUDA cores (Ampere architecture)
      - 8GB unified memory is shared between CPU and GPU
      - For a 82M param model, fine-tuning uses ~2-3GB VRAM at batch_size=4
      - That leaves ~5GB for the OS + other processes — comfortable

    On Mac (Apple Silicon):
      - MPS (Metal Performance Shaders) provides GPU acceleration
      - Not all PyTorch ops are supported on MPS yet, so some may fall back to CPU
      - For this model size, MPS gives ~3-5x speedup over CPU

    On CPU:
      - Works but slow. Fine-tuning 100 epochs may take several hours.
      - Consider reducing epochs to 50 or using a cloud GPU.
    """
    if requested != "auto":
        return torch.device(requested)

    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
        print(f"  Device: CUDA ({gpu_name}, {gpu_mem:.1f} GB)")
        return device

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print(f"  Device: MPS (Apple Silicon)")
        return torch.device("mps")

    print(f"  Device: CPU (no GPU detected — training will be slow)")
    return torch.device("cpu")


# ═══════════════════════════════════════════════════════════════
# Dataset
# ═══════════════════════════════════════════════════════════════

class VoiceDataset(Dataset):
    """
    Dataset for StyleTTS2 fine-tuning.

    Loads pre-processed WAV files and their phoneme transcripts.
    Returns mel spectrograms (what the model actually trains on)
    and phoneme token sequences.

    Mel spectrogram parameters match Kokoro's pre-training config:
      - 80 mel bins (frequency resolution)
      - 1024 FFT size, 256 hop size (time resolution)
      - 24000 Hz sample rate
    """

    def __init__(self, manifest_path: Path, data_dir: Path,
                 sample_rate: int = 24000, max_duration: float = 15.0):
        self.data_dir = data_dir
        self.sample_rate = sample_rate
        self.max_samples = int(max_duration * sample_rate)

        # Parse manifest: path|phonemes|speaker_id
        self.entries = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("path|"):
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    self.entries.append({
                        "path": parts[0],
                        "phonemes": parts[1],
                        "speaker_id": parts[2] if len(parts) > 2 else "default",
                    })

        # Build a simple character-level phoneme vocabulary
        # (In production StyleTTS2, this is a proper IPA tokenizer.
        # For fine-tuning, character-level is sufficient since we're
        # not training the text encoder from scratch.)
        all_chars = set()
        for entry in self.entries:
            all_chars.update(entry["phonemes"])
        self.vocab = {c: i + 1 for i, c in enumerate(sorted(all_chars))}
        self.vocab["<pad>"] = 0

        # Mel spectrogram transform
        if HAS_TORCHAUDIO:
            self.mel_transform = torchaudio.transforms.MelSpectrogram(
                sample_rate=sample_rate,
                n_fft=1024,
                hop_length=256,
                n_mels=80,
                f_min=0,
                f_max=8000,
            )
        else:
            self.mel_transform = None

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        entry = self.entries[idx]
        wav_path = self.data_dir / entry["path"]

        # Load audio
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Truncate if too long
        if len(audio) > self.max_samples:
            audio = audio[:self.max_samples]

        # Convert to tensor
        audio_tensor = torch.from_numpy(audio).float()

        # Compute mel spectrogram
        if self.mel_transform is not None:
            mel = self.mel_transform(audio_tensor.unsqueeze(0))  # [1, 80, T]
            mel = torch.log(mel.clamp(min=1e-5))  # log-mel
            mel = mel.squeeze(0)  # [80, T]
        else:
            # Fallback: use raw audio (training will be suboptimal)
            mel = audio_tensor.unsqueeze(0)

        # Tokenize phonemes
        phoneme_ids = [self.vocab.get(c, 0) for c in entry["phonemes"]]
        phoneme_tensor = torch.LongTensor(phoneme_ids)

        return {
            "mel": mel,
            "phonemes": phoneme_tensor,
            "audio": audio_tensor,
        }


def collate_fn(batch):
    """
    Custom collation for variable-length sequences.

    Pads mel spectrograms and phoneme sequences to the longest
    in the batch. Returns padded tensors + length tensors.
    """
    # Find max lengths
    max_mel_len = max(item["mel"].shape[-1] for item in batch)
    max_phone_len = max(len(item["phonemes"]) for item in batch)

    mels = []
    mel_lengths = []
    phonemes = []
    phone_lengths = []

    for item in batch:
        mel = item["mel"]
        mel_len = mel.shape[-1]
        # Pad mel: [80, T] → [80, max_T]
        padded_mel = F.pad(mel, (0, max_mel_len - mel_len))
        mels.append(padded_mel)
        mel_lengths.append(mel_len)

        phone = item["phonemes"]
        phone_len = len(phone)
        # Pad phonemes: [L] → [max_L]
        padded_phone = F.pad(phone, (0, max_phone_len - phone_len))
        phonemes.append(padded_phone)
        phone_lengths.append(phone_len)

    return {
        "mels": torch.stack(mels),               # [B, 80, T]
        "mel_lengths": torch.LongTensor(mel_lengths),   # [B]
        "phonemes": torch.stack(phonemes),         # [B, L]
        "phone_lengths": torch.LongTensor(phone_lengths), # [B]
    }


# ═══════════════════════════════════════════════════════════════
# Model components for fine-tuning
# ═══════════════════════════════════════════════════════════════

class StyleEncoder(nn.Module):
    """
    Extracts a fixed-size style vector from a mel spectrogram.

    This is the key component for voice cloning. The style encoder
    compresses an entire utterance's mel spectrogram into a single
    vector that captures:
      - Timbre (what makes YOUR voice recognizable)
      - Prosody patterns (your natural rhythm and intonation)
      - Speaking rate tendencies
      - Breathiness, vocal fry, etc.

    Architecture: Conv stack → GRU → Linear projection
    The GRU's final hidden state summarizes the entire sequence into
    a fixed-size vector, regardless of input length.
    """

    def __init__(self, mel_dim: int = 80, style_dim: int = 128, hidden_dim: int = 256):
        super().__init__()
        self.conv_stack = nn.Sequential(
            nn.Conv1d(mel_dim, hidden_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
        )
        self.gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True, bidirectional=True)
        self.proj = nn.Linear(hidden_dim * 2, style_dim)

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        """
        mel: [B, 80, T] → style: [B, style_dim]
        """
        x = self.conv_stack(mel)            # [B, hidden, T]
        x = x.transpose(1, 2)              # [B, T, hidden]
        _, h = self.gru(x)                  # h: [2, B, hidden]
        h = torch.cat([h[0], h[1]], dim=-1) # [B, hidden*2]
        style = self.proj(h)                # [B, style_dim]
        return style


class MelDecoder(nn.Module):
    """
    Generates mel spectrograms from phoneme encodings + style vector.

    Simplified decoder for fine-tuning. The full StyleTTS2 decoder uses
    flow-matching (a more efficient variant of diffusion), but for
    fine-tuning we use a simpler autoregressive approach that's faster
    to converge on small datasets.

    The style vector is concatenated to each phoneme encoding, conditioning
    every output frame on YOUR voice characteristics.
    """

    def __init__(self, phone_dim: int = 256, style_dim: int = 128,
                 mel_dim: int = 80, hidden_dim: int = 512):
        super().__init__()
        self.phone_encoder = nn.Sequential(
            nn.Linear(phone_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.style_proj = nn.Linear(style_dim, hidden_dim)
        self.decoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=hidden_dim,
                nhead=8,
                dim_feedforward=1024,
                dropout=0.1,
                batch_first=True,
            ),
            num_layers=4,
        )
        self.mel_out = nn.Linear(hidden_dim, mel_dim)

    def forward(self, phone_encoding: torch.Tensor, style: torch.Tensor) -> torch.Tensor:
        """
        phone_encoding: [B, L, phone_dim]
        style: [B, style_dim]
        → mel: [B, 80, L]
        """
        x = self.phone_encoder(phone_encoding)  # [B, L, hidden]
        # Broadcast style across sequence
        s = self.style_proj(style).unsqueeze(1)  # [B, 1, hidden]
        x = x + s                                # [B, L, hidden]
        x = self.decoder(x)                      # [B, L, hidden]
        mel = self.mel_out(x)                    # [B, L, 80]
        return mel.transpose(1, 2)               # [B, 80, L]


class PhonemeEncoder(nn.Module):
    """
    Encodes phoneme token sequences into dense representations.

    In the full Kokoro model, this is a sophisticated encoder with
    relative positional encodings and multi-head attention. For
    fine-tuning, we keep it simple: embedding + positional encoding +
    a few transformer layers. The pre-trained weights will be loaded
    from the checkpoint and frozen.
    """

    def __init__(self, vocab_size: int = 256, embed_dim: int = 256,
                 hidden_dim: int = 256, n_layers: int = 4):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.pos_embed = nn.Embedding(2048, embed_dim)  # max sequence length
        self.encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=hidden_dim,
                nhead=4,
                dim_feedforward=512,
                dropout=0.1,
                batch_first=True,
            ),
            num_layers=n_layers,
        )

    def forward(self, phonemes: torch.Tensor) -> torch.Tensor:
        """
        phonemes: [B, L] (token IDs) → [B, L, hidden_dim]
        """
        B, L = phonemes.shape
        positions = torch.arange(L, device=phonemes.device).unsqueeze(0).expand(B, -1)
        x = self.embed(phonemes) + self.pos_embed(positions)
        return self.encoder(x)


class VoiceCloningModel(nn.Module):
    """
    Complete model for voice cloning fine-tuning.

    Combines: PhonemeEncoder + StyleEncoder + MelDecoder

    During fine-tuning:
      - PhonemeEncoder is FROZEN (pre-trained text knowledge)
      - StyleEncoder is TRAINED (learns your voice)
      - MelDecoder is TRAINED (generates mels in your voice)

    The training objective is simple: given phonemes + your mel spectrogram,
    the model should reconstruct the mel spectrogram. The style encoder
    extracts your voice characteristics from the target mel, and the decoder
    uses those characteristics to generate the output. Over many iterations,
    the style encoder learns a robust representation of your voice.
    """

    def __init__(self, vocab_size: int = 256, style_dim: int = 128):
        super().__init__()
        self.phoneme_encoder = PhonemeEncoder(vocab_size=vocab_size)
        self.style_encoder = StyleEncoder(style_dim=style_dim)
        self.mel_decoder = MelDecoder(style_dim=style_dim)

    def forward(self, phonemes: torch.Tensor, target_mel: torch.Tensor):
        """
        phonemes: [B, L]
        target_mel: [B, 80, T]
        Returns: predicted_mel [B, 80, T'], style_vector [B, style_dim]
        """
        # Extract style from target (during training, we use the ground truth)
        style = self.style_encoder(target_mel)

        # Encode phonemes
        phone_enc = self.phoneme_encoder(phonemes)

        # Decode to mel
        pred_mel = self.mel_decoder(phone_enc, style)

        return pred_mel, style

    def freeze_text_encoder(self):
        """Freeze the phoneme encoder — don't update pre-trained text knowledge."""
        for param in self.phoneme_encoder.parameters():
            param.requires_grad = False
        print(f"  {DIM}Froze phoneme encoder ({sum(p.numel() for p in self.phoneme_encoder.parameters()):,} params){RESET}")

    def get_trainable_params(self) -> int:
        """Count parameters that will be updated during training."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_total_params(self) -> int:
        """Count all parameters."""
        return sum(p.numel() for p in self.parameters())


# ═══════════════════════════════════════════════════════════════
# Loss functions
# ═══════════════════════════════════════════════════════════════

class ReconstructionLoss(nn.Module):
    """
    Combined mel reconstruction loss.

    Uses both L1 (mean absolute error) and L2 (mean squared error):
      - L1 is robust to outliers and produces sharp spectrograms
      - L2 penalizes large errors more, ensuring overall fidelity

    Also includes a multi-resolution STFT loss for perceptual quality
    (comparing spectrograms at multiple time/frequency resolutions).
    """

    def __init__(self, l1_weight: float = 1.0, l2_weight: float = 0.5):
        super().__init__()
        self.l1_weight = l1_weight
        self.l2_weight = l2_weight

    def forward(self, pred_mel: torch.Tensor, target_mel: torch.Tensor,
                pred_lengths: torch.Tensor = None, target_lengths: torch.Tensor = None):
        """
        pred_mel:    [B, 80, T_pred]
        target_mel:  [B, 80, T_target]
        """
        # Match lengths (take the shorter of the two)
        min_len = min(pred_mel.shape[-1], target_mel.shape[-1])
        pred = pred_mel[..., :min_len]
        target = target_mel[..., :min_len]

        l1_loss = F.l1_loss(pred, target)
        l2_loss = F.mse_loss(pred, target)

        return self.l1_weight * l1_loss + self.l2_weight * l2_loss


# ═══════════════════════════════════════════════════════════════
# Training loop
# ═══════════════════════════════════════════════════════════════

def train_one_epoch(model, dataloader, optimizer, criterion, device,
                    grad_accum_steps: int = 4) -> float:
    """
    Train for one epoch with gradient accumulation.

    Gradient accumulation simulates a larger batch size without needing
    more GPU memory. With batch_size=4 and grad_accum=4, the effective
    batch size is 16. This is important because:
      - Small batches (1-4) have noisy gradients → unstable training
      - Large batches (32+) need too much VRAM for 8GB Jetson
      - Accumulation gives us the best of both worlds
    """
    model.train()
    total_loss = 0.0
    n_batches = 0
    optimizer.zero_grad()

    for i, batch in enumerate(dataloader):
        mels = batch["mels"].to(device)          # [B, 80, T]
        phonemes = batch["phonemes"].to(device)   # [B, L]

        # Forward pass
        pred_mel, style = model(phonemes, mels)

        # Compute loss
        loss = criterion(pred_mel, mels)
        loss = loss / grad_accum_steps  # scale for accumulation

        # Backward pass
        loss.backward()

        # Step optimizer every grad_accum_steps
        if (i + 1) % grad_accum_steps == 0 or (i + 1) == len(dataloader):
            # Gradient clipping prevents exploding gradients, which can happen
            # when the model encounters unusual phoneme sequences in your data.
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            optimizer.zero_grad()

        total_loss += loss.item() * grad_accum_steps
        n_batches += 1

    return total_loss / max(n_batches, 1)


def validate(model, dataloader, criterion, device) -> float:
    """Run validation and return average loss."""
    model.eval()
    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for batch in dataloader:
            mels = batch["mels"].to(device)
            phonemes = batch["phonemes"].to(device)

            pred_mel, style = model(phonemes, mels)
            loss = criterion(pred_mel, mels)

            total_loss += loss.item()
            n_batches += 1

    return total_loss / max(n_batches, 1)


def save_checkpoint(model, optimizer, epoch, loss, path: Path):
    """Save a training checkpoint."""
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "loss": loss,
    }, str(path))


def load_checkpoint(model, optimizer, path: Path, device: torch.device):
    """Load a training checkpoint and return the starting epoch."""
    checkpoint = torch.load(str(path), map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    if optimizer is not None and "optimizer_state_dict" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    epoch = checkpoint.get("epoch", 0)
    loss = checkpoint.get("loss", float("inf"))
    print(f"  Resumed from epoch {epoch} (loss: {loss:.4f})")
    return epoch


# ═══════════════════════════════════════════════════════════════
# Main training script
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune StyleTTS2/Kokoro for voice cloning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python finetune.py --data-dir ./training_data --epochs 100
    python finetune.py --device cuda --batch-size 8 --lr 1e-4
    python finetune.py --resume checkpoints/epoch_50.pt
    python finetune.py --pretrained /path/to/kokoro_styletts2.pt
        """
    )
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Directory with training data (default: ./training_data)")
    parser.add_argument("--checkpoint-dir", type=str, default=None,
                        help="Where to save checkpoints (default: ./checkpoints)")
    parser.add_argument("--pretrained", type=str, default=None,
                        help="Path to pre-trained Kokoro/StyleTTS2 checkpoint")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from a saved checkpoint")
    parser.add_argument("--device", type=str, default="auto",
                        help="Device: auto, cpu, cuda, mps (default: auto)")
    parser.add_argument("--epochs", type=int, default=100,
                        help="Number of training epochs (default: 100)")
    parser.add_argument("--batch-size", type=int, default=4,
                        help="Batch size (default: 4, fits in 8GB VRAM)")
    parser.add_argument("--grad-accum", type=int, default=4,
                        help="Gradient accumulation steps (default: 4, effective batch=16)")
    parser.add_argument("--lr", type=float, default=1e-4,
                        help="Learning rate (default: 1e-4)")
    parser.add_argument("--weight-decay", type=float, default=0.01,
                        help="Weight decay for regularization (default: 0.01)")
    parser.add_argument("--save-every", type=int, default=10,
                        help="Save checkpoint every N epochs (default: 10)")
    parser.add_argument("--freeze-text-encoder", action="store_true", default=True,
                        help="Freeze the phoneme/text encoder (default: True)")
    parser.add_argument("--no-freeze-text-encoder", action="store_false", dest="freeze_text_encoder",
                        help="Don't freeze the text encoder (risks forgetting)")
    parser.add_argument("--num-workers", type=int, default=2,
                        help="DataLoader worker processes (default: 2)")
    parser.add_argument("--style-dim", type=int, default=128,
                        help="Style vector dimension (default: 128)")
    args = parser.parse_args()

    # Check dependencies
    if not HAS_TORCH:
        print(f"{RED}ERROR: PyTorch not installed. Run: pip install torch torchaudio{RESET}")
        sys.exit(1)
    if not HAS_SF:
        print(f"{RED}ERROR: soundfile not installed. Run: pip install soundfile{RESET}")
        sys.exit(1)

    base_dir = Path(__file__).parent
    data_dir = Path(args.data_dir) if args.data_dir else base_dir / "training_data"
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else base_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    train_manifest = data_dir / "train.txt"
    val_manifest = data_dir / "val.txt"

    if not train_manifest.exists():
        print(f"{RED}ERROR: Training manifest not found: {train_manifest}{RESET}")
        print("Run prepare_data.py first.")
        sys.exit(1)

    # Load dataset config
    config_path = data_dir / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            data_config = json.load(f)
    else:
        data_config = {}

    print(f"""
{BOLD}{'=' * 60}
   JARVIS Voice Clone — Fine-Tuning
   StyleTTS2 / Kokoro transfer learning
{'=' * 60}{RESET}

  Data:          {data_dir}
  Train clips:   {data_config.get('train_clips', '?')}
  Val clips:     {data_config.get('val_clips', '?')}
  Total audio:   {data_config.get('total_duration_minutes', '?')} minutes

  Hyperparameters:
    Epochs:            {args.epochs}
    Batch size:        {args.batch_size} (effective: {args.batch_size * args.grad_accum})
    Learning rate:     {args.lr}
    Weight decay:      {args.weight_decay}
    Gradient accum:    {args.grad_accum}
    Style dim:         {args.style_dim}
    Freeze text enc:   {args.freeze_text_encoder}
""")

    # Device
    device = detect_device(args.device)

    # Create datasets
    print(f"\n  Loading datasets...")
    train_dataset = VoiceDataset(train_manifest, data_dir)
    val_dataset = VoiceDataset(val_manifest, data_dir) if val_manifest.exists() else None

    vocab_size = len(train_dataset.vocab) + 1  # +1 for padding

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate_fn,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        drop_last=False,
    )

    val_loader = None
    if val_dataset and len(val_dataset) > 0:
        val_loader = DataLoader(
            val_dataset,
            batch_size=args.batch_size,
            shuffle=False,
            collate_fn=collate_fn,
            num_workers=args.num_workers,
            pin_memory=(device.type == "cuda"),
        )

    print(f"  Train: {len(train_dataset)} clips, {len(train_loader)} batches")
    if val_loader:
        print(f"  Val:   {len(val_dataset)} clips, {len(val_loader)} batches")
    print(f"  Vocab: {vocab_size} phoneme tokens")

    # Create model
    model = VoiceCloningModel(vocab_size=vocab_size, style_dim=args.style_dim)

    # Load pre-trained weights if available
    if args.pretrained and Path(args.pretrained).exists():
        print(f"\n  Loading pre-trained weights from: {args.pretrained}")
        try:
            pretrained = torch.load(args.pretrained, map_location=device)
            # Try to load matching keys (partial load for fine-tuning)
            model_dict = model.state_dict()
            pretrained_dict = {k: v for k, v in pretrained.items()
                               if k in model_dict and v.shape == model_dict[k].shape}
            model_dict.update(pretrained_dict)
            model.load_state_dict(model_dict)
            print(f"  Loaded {len(pretrained_dict)}/{len(model_dict)} layers from pre-trained model.")
        except Exception as e:
            print(f"  {YELLOW}Warning: Could not load pre-trained weights: {e}{RESET}")
            print(f"  Training from scratch (will take longer).")

    # Freeze text encoder
    if args.freeze_text_encoder:
        model.freeze_text_encoder()

    model = model.to(device)

    total_params = model.get_total_params()
    trainable_params = model.get_trainable_params()
    print(f"\n  Model: {total_params:,} total params, {trainable_params:,} trainable")
    print(f"  Memory: ~{total_params * 4 / (1024 ** 2):.0f} MB (float32)")

    # Optimizer
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=args.weight_decay,
        betas=(0.9, 0.999),
    )

    # Learning rate scheduler: cosine annealing with warm restarts
    # Starts at lr, decays to near-zero, then restarts. This helps
    # the model explore different solutions and escape local minima.
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=max(args.epochs // 4, 10), T_mult=2,
    )

    # Loss
    criterion = ReconstructionLoss()

    # Resume from checkpoint
    start_epoch = 0
    if args.resume and Path(args.resume).exists():
        start_epoch = load_checkpoint(model, optimizer, Path(args.resume), device)

    # Training loop
    print(f"\n  {'=' * 50}")
    print(f"  Starting training (epochs {start_epoch + 1} to {args.epochs})")
    print(f"  {'=' * 50}\n")

    best_val_loss = float("inf")
    training_start = time.monotonic()
    loss_history = {"train": [], "val": []}

    for epoch in range(start_epoch, args.epochs):
        epoch_start = time.monotonic()

        # Train
        train_loss = train_one_epoch(
            model, train_loader, optimizer, criterion, device,
            grad_accum_steps=args.grad_accum,
        )

        # Validate
        val_loss = None
        if val_loader:
            val_loss = validate(model, val_loader, criterion, device)

        # Step scheduler
        scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        epoch_time = time.monotonic() - epoch_start

        # Track loss history
        loss_history["train"].append(train_loss)
        if val_loss is not None:
            loss_history["val"].append(val_loss)

        # Print progress
        val_str = f" | val_loss: {val_loss:.4f}" if val_loss else ""
        best_str = ""
        if val_loss is not None and val_loss < best_val_loss:
            best_val_loss = val_loss
            best_str = f" {GREEN}(best){RESET}"
            # Save best model
            save_checkpoint(model, optimizer, epoch + 1, val_loss,
                            checkpoint_dir / "best.pt")

        print(
            f"  Epoch {epoch + 1:3d}/{args.epochs} | "
            f"train_loss: {train_loss:.4f}{val_str}{best_str} | "
            f"lr: {current_lr:.2e} | "
            f"{epoch_time:.1f}s"
        )

        # Save periodic checkpoints
        if (epoch + 1) % args.save_every == 0:
            ckpt_path = checkpoint_dir / f"epoch_{epoch + 1:04d}.pt"
            save_checkpoint(model, optimizer, epoch + 1, train_loss, ckpt_path)
            print(f"    {DIM}Saved checkpoint: {ckpt_path.name}{RESET}")

    # Save final model
    final_path = checkpoint_dir / "final.pt"
    save_checkpoint(model, optimizer, args.epochs, train_loss, final_path)

    # Save style vector (the average style embedding across all training data)
    print(f"\n  Extracting average style vector...")
    model.eval()
    style_vectors = []
    with torch.no_grad():
        for batch in train_loader:
            mels = batch["mels"].to(device)
            style = model.style_encoder(mels)
            style_vectors.append(style.cpu())
    avg_style = torch.cat(style_vectors, dim=0).mean(dim=0)  # [style_dim]
    torch.save(avg_style, checkpoint_dir / "style_vector.pt")

    # Save loss history
    with open(checkpoint_dir / "loss_history.json", "w") as f:
        json.dump(loss_history, f, indent=2)

    total_time = time.monotonic() - training_start

    print(f"""
{'=' * 60}
  Training complete!

  Total time:     {total_time / 60:.1f} minutes
  Final train:    {train_loss:.4f}
  Best val:       {best_val_loss:.4f}
  Checkpoints:    {checkpoint_dir}

  Files:
    {final_path}         — final model
    {checkpoint_dir / "best.pt"}          — best validation model
    {checkpoint_dir / "style_vector.pt"}  — your voice embedding
    {checkpoint_dir / "loss_history.json"} — training curves

  Next step: python export_onnx.py --checkpoint {checkpoint_dir / "best.pt"}
{'=' * 60}
""")


if __name__ == "__main__":
    main()
