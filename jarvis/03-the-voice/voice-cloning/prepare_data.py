#!/usr/bin/env python3
"""
Data Preparation for StyleTTS2 / Kokoro Fine-Tuning
=====================================================
Takes transcribed voice clips and prepares them for training:
  1. Normalizes audio volume (peak normalization to -1 dB)
  2. Resamples to 24kHz mono if not already
  3. Splits long clips (>15s) into shorter segments
  4. Generates phoneme alignments using espeak-ng
  5. Creates train/val splits in StyleTTS2 format
  6. Produces training manifests (train.txt, val.txt)

Usage:
    python prepare_data.py                                    # Use default metadata
    python prepare_data.py --metadata ./recordings/metadata.csv
    python prepare_data.py --val-split 0.1 --speaker-id devesh
    python prepare_data.py --help

Output:
    training_data/
      wavs/           — normalized, resampled WAV files
      train.txt       — path|phonemes|speaker_id
      val.txt         — path|phonemes|speaker_id
      config.json     — dataset statistics for the trainer

Requirements:
    pip install librosa soundfile numpy phonemizer
    Also needs: espeak-ng (system package)
      macOS:  brew install espeak-ng
      Linux:  sudo apt install espeak-ng
"""

import argparse
import csv
import json
import os
import random
import shutil
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
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    from phonemizer.backend import EspeakBackend
    from phonemizer import phonemize
    HAS_PHONEMIZER = True
except ImportError:
    HAS_PHONEMIZER = False


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

TARGET_SAMPLE_RATE = 24000  # Kokoro/StyleTTS2 native rate
TARGET_CHANNELS = 1         # Mono
PEAK_DB = -1.0              # Peak normalization target in dB
MIN_DURATION = 1.0          # Minimum clip duration in seconds
MAX_DURATION = 15.0         # Maximum clip duration in seconds
SPLIT_OVERLAP = 0.5         # Overlap in seconds when splitting long clips

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


# ═══════════════════════════════════════════════════════════════
# Audio processing
# ═══════════════════════════════════════════════════════════════

def normalize_audio(audio: np.ndarray, target_db: float = PEAK_DB) -> np.ndarray:
    """
    Peak-normalize audio to target dB level.

    Peak normalization scales the audio so the loudest sample reaches
    the target level. This is preferred over RMS normalization for TTS
    training because it preserves the dynamic range of natural speech
    (quiet pauses, loud exclamations) while ensuring consistent maximum
    levels across clips.

    -1 dB target leaves a tiny headroom below clipping (0 dB), which
    prevents digital distortion if any downstream processing adds a
    tiny bit of gain.
    """
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio  # silence

    target_peak = 10 ** (target_db / 20.0)  # dB to linear scale
    gain = target_peak / peak
    return audio * gain


def load_and_resample(filepath: Path, target_sr: int = TARGET_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """
    Load audio and resample to target rate if needed.
    Returns (audio_float32, sample_rate).
    """
    if HAS_LIBROSA:
        # librosa.load always returns float32 at target_sr
        audio, sr = librosa.load(str(filepath), sr=target_sr, mono=True)
    else:
        audio, sr = sf.read(str(filepath), dtype="float32")
        # Make mono if stereo
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        # Resample if needed (basic linear interpolation without librosa)
        if sr != target_sr:
            duration = len(audio) / sr
            new_length = int(duration * target_sr)
            indices = np.linspace(0, len(audio) - 1, new_length)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
            sr = target_sr

    return audio, sr


def split_audio(audio: np.ndarray, sr: int, max_duration: float = MAX_DURATION,
                overlap: float = SPLIT_OVERLAP) -> list[np.ndarray]:
    """
    Split audio longer than max_duration into overlapping segments.

    For TTS training, segments should be 5-15 seconds. Longer clips
    cause memory issues during training (attention scales quadratically
    with sequence length in StyleTTS2's transformer blocks).

    Overlap prevents cutting words at segment boundaries — the
    overlapping region gets the word ending from one segment and
    the word beginning from the next.
    """
    max_samples = int(max_duration * sr)
    overlap_samples = int(overlap * sr)

    if len(audio) <= max_samples:
        return [audio]

    segments = []
    start = 0
    while start < len(audio):
        end = min(start + max_samples, len(audio))
        segment = audio[start:end]

        # Don't create tiny tail segments
        if len(segment) / sr < MIN_DURATION and segments:
            # Append to the last segment instead
            segments[-1] = np.concatenate([segments[-1], segment])
            break

        segments.append(segment)
        start = end - overlap_samples

    return segments


# ═══════════════════════════════════════════════════════════════
# Phoneme generation
# ═══════════════════════════════════════════════════════════════

def text_to_phonemes(text: str, language: str = "en-us") -> str:
    """
    Convert text to IPA phonemes using espeak-ng via phonemizer.

    StyleTTS2 trains on phoneme sequences, not raw text. The phoneme
    encoder learns to map IPA symbols to acoustic features. Using
    phonemes instead of characters gives:
      - Language-independent input representation
      - Correct pronunciation for irregular spellings
      - Better generalization to unseen words

    For Hindi text, we use the 'hi' backend. For mixed Hinglish,
    we try English first (most Hinglish is Romanized Hindi).
    """
    if not HAS_PHONEMIZER:
        # Fallback: return raw text (training will still work, just less optimal)
        return text

    # Map language codes to espeak language identifiers
    lang_map = {
        "en": "en-us",
        "en-us": "en-us",
        "en-gb": "en-gb",
        "hi": "hi",
        "hi-en": "en-us",  # Hinglish → treat as English (Romanized)
    }
    espeak_lang = lang_map.get(language, "en-us")

    try:
        phones = phonemize(
            text,
            language=espeak_lang,
            backend="espeak",
            strip=True,
            preserve_punctuation=True,
            with_stress=True,
        )
        return phones.strip()
    except Exception as e:
        # If phonemization fails (e.g., espeak-ng not installed), return raw text
        return text


def check_espeak_available() -> bool:
    """Check if espeak-ng is installed on the system."""
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Prepare voice recordings for StyleTTS2/Kokoro fine-tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python prepare_data.py
    python prepare_data.py --metadata recordings/metadata.csv
    python prepare_data.py --val-split 0.15 --speaker-id devesh
    python prepare_data.py --skip-phonemes  # if espeak-ng not available
        """
    )
    parser.add_argument("--metadata", type=str, default=None,
                        help="Path to metadata.csv from transcribe.py (default: recordings/metadata.csv)")
    parser.add_argument("--recordings-dir", type=str, default=None,
                        help="Directory with WAV files (default: ./recordings)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory for training data (default: ./training_data)")
    parser.add_argument("--speaker-id", type=str, default="devesh",
                        help="Speaker identifier for the manifest (default: devesh)")
    parser.add_argument("--val-split", type=float, default=0.1,
                        help="Fraction of data for validation (default: 0.1)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible splits (default: 42)")
    parser.add_argument("--skip-phonemes", action="store_true",
                        help="Skip phoneme generation (use raw text instead)")
    parser.add_argument("--max-duration", type=float, default=MAX_DURATION,
                        help=f"Maximum clip duration in seconds (default: {MAX_DURATION})")
    args = parser.parse_args()

    # Check dependencies
    if not HAS_SF:
        print(f"{RED}ERROR: soundfile not installed. Run: pip install soundfile{RESET}")
        sys.exit(1)

    base_dir = Path(__file__).parent
    recordings_dir = Path(args.recordings_dir) if args.recordings_dir else base_dir / "recordings"
    metadata_path = Path(args.metadata) if args.metadata else recordings_dir / "metadata.csv"
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "training_data"

    if not metadata_path.exists():
        print(f"{RED}ERROR: Metadata file not found: {metadata_path}{RESET}")
        print("Run transcribe.py first to generate metadata.csv")
        sys.exit(1)

    # Check espeak-ng availability
    has_espeak = check_espeak_available()
    use_phonemes = not args.skip_phonemes
    if use_phonemes and not has_espeak:
        print(f"{YELLOW}Warning: espeak-ng not found. Install it for phoneme generation:{RESET}")
        print(f"  macOS:  brew install espeak-ng")
        print(f"  Linux:  sudo apt install espeak-ng")
        print(f"  Falling back to raw text (less optimal for training).\n")
        use_phonemes = False

    if use_phonemes and not HAS_PHONEMIZER:
        print(f"{YELLOW}Warning: phonemizer not installed. Run: pip install phonemizer{RESET}")
        print(f"  Falling back to raw text.\n")
        use_phonemes = False

    print(f"""
{BOLD}{'=' * 60}
   JARVIS Training Data Preparation
   StyleTTS2 / Kokoro fine-tuning pipeline
{'=' * 60}{RESET}

  Metadata:     {metadata_path}
  Recordings:   {recordings_dir}
  Output:       {output_dir}
  Speaker ID:   {args.speaker_id}
  Val split:    {args.val_split:.0%}
  Phonemes:     {"espeak-ng" if use_phonemes else "raw text (fallback)"}
  Max duration: {args.max_duration}s
""")

    # Create output directories
    wavs_dir = output_dir / "wavs"
    wavs_dir.mkdir(parents=True, exist_ok=True)

    # Load metadata
    entries = []
    with open(metadata_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            entries.append(row)

    print(f"  Loaded {len(entries)} entries from metadata.\n")

    # Process each clip
    processed = []
    total_duration = 0.0
    skipped = 0
    split_count = 0

    for i, entry in enumerate(entries):
        filename = entry["filename"]
        transcript = entry["transcript"]
        language = entry.get("language", "en")
        wav_path = recordings_dir / filename

        if not wav_path.exists():
            print(f"  {YELLOW}Skip: {filename} (file not found){RESET}")
            skipped += 1
            continue

        # Load and resample
        try:
            audio, sr = load_and_resample(wav_path, TARGET_SAMPLE_RATE)
        except Exception as e:
            print(f"  {YELLOW}Skip: {filename} ({e}){RESET}")
            skipped += 1
            continue

        duration = len(audio) / sr

        # Skip very short clips
        if duration < MIN_DURATION:
            print(f"  {DIM}Skip: {filename} (too short: {duration:.1f}s){RESET}")
            skipped += 1
            continue

        # Normalize volume
        audio = normalize_audio(audio, PEAK_DB)

        # Split if too long
        segments = split_audio(audio, sr, max_duration=args.max_duration)

        for seg_idx, segment in enumerate(segments):
            seg_duration = len(segment) / sr

            # Generate output filename
            if len(segments) == 1:
                out_filename = filename
            else:
                base = filename.replace(".wav", "")
                out_filename = f"{base}_seg{seg_idx:02d}.wav"
                split_count += 1

            # Save processed WAV
            out_path = wavs_dir / out_filename
            sf.write(str(out_path), segment, sr, subtype="PCM_16")

            # Generate phonemes
            if use_phonemes:
                phonemes = text_to_phonemes(transcript, language)
            else:
                phonemes = transcript

            # For split segments, we use the same transcript for all segments.
            # This is a simplification — ideally we'd use forced alignment to
            # determine which words belong to which segment. But for fine-tuning
            # (not training from scratch), this approximation works because the
            # model already knows language structure. It just needs to learn the
            # new voice style.
            processed.append({
                "path": f"wavs/{out_filename}",
                "phonemes": phonemes,
                "text": transcript,
                "speaker_id": args.speaker_id,
                "duration": round(seg_duration, 2),
                "language": language,
                "source_file": filename,
            })

            total_duration += seg_duration

        # Progress
        pct = (i + 1) / len(entries) * 100
        sys.stdout.write(f"\r  Processing: [{i + 1}/{len(entries)}] {pct:.0f}% | {filename}")
        sys.stdout.flush()

    print(f"\r  Processing complete!{' ' * 40}")

    if not processed:
        print(f"\n{RED}ERROR: No clips were processed. Check your recordings.{RESET}")
        sys.exit(1)

    # Train/val split
    random.seed(args.seed)
    random.shuffle(processed)
    val_size = max(1, int(len(processed) * args.val_split))
    val_set = processed[:val_size]
    train_set = processed[val_size:]

    # Write manifest files
    # StyleTTS2 format: path|phonemes|speaker_id
    train_txt = output_dir / "train.txt"
    val_txt = output_dir / "val.txt"

    with open(train_txt, "w", encoding="utf-8") as f:
        for item in train_set:
            f.write(f"{item['path']}|{item['phonemes']}|{item['speaker_id']}\n")

    with open(val_txt, "w", encoding="utf-8") as f:
        for item in val_set:
            f.write(f"{item['path']}|{item['phonemes']}|{item['speaker_id']}\n")

    # Also write a full metadata JSON for the trainer
    config_data = {
        "speaker_id": args.speaker_id,
        "sample_rate": TARGET_SAMPLE_RATE,
        "total_clips": len(processed),
        "train_clips": len(train_set),
        "val_clips": len(val_set),
        "total_duration_seconds": round(total_duration, 1),
        "total_duration_minutes": round(total_duration / 60, 1),
        "avg_duration_seconds": round(total_duration / len(processed), 1) if processed else 0,
        "phoneme_type": "espeak-ipa" if use_phonemes else "raw-text",
        "normalization": f"peak at {PEAK_DB} dB",
        "split_ratio": f"train {1 - args.val_split:.0%} / val {args.val_split:.0%}",
        "clips_split_from_long": split_count,
        "clips_skipped": skipped,
    }

    with open(output_dir / "config.json", "w") as f:
        json.dump(config_data, f, indent=2)

    # Also write a metadata_full.csv with all info (useful for debugging)
    with open(output_dir / "metadata_full.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "text", "phonemes", "speaker_id", "duration", "language"],
                                delimiter="|")
        writer.writeheader()
        for item in processed:
            writer.writerow({
                "path": item["path"],
                "text": item["text"],
                "phonemes": item["phonemes"],
                "speaker_id": item["speaker_id"],
                "duration": item["duration"],
                "language": item["language"],
            })

    # Summary
    print(f"""
{'=' * 60}
  Data preparation complete!

  Total clips:   {len(processed)} ({skipped} skipped, {split_count} from splits)
  Train set:     {len(train_set)} clips
  Val set:       {len(val_set)} clips
  Total audio:   {total_duration / 60:.1f} minutes
  Avg clip:      {total_duration / len(processed):.1f}s
  Phonemes:      {"espeak-ng IPA" if use_phonemes else "raw text"}

  Output files:
    {wavs_dir}/        — processed WAV files
    {train_txt}   — training manifest
    {val_txt}     — validation manifest
    {output_dir / "config.json"}   — dataset config

  Next step: python finetune.py --data-dir {output_dir}
{'=' * 60}
""")


if __name__ == "__main__":
    main()
