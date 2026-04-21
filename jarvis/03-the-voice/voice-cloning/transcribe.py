#!/usr/bin/env python3
"""
Auto-transcribe recorded voice clips using faster-whisper.
============================================================
Takes the WAV files from record_voice.py, transcribes each one,
and produces a metadata.csv that the training pipeline needs.

Also validates alignment: flags clips where the Whisper transcript
doesn't match the original prompt (you may have misspoken or
improvised, which is fine — but the training data should have
accurate transcripts).

Usage:
    python transcribe.py                                  # Use default recordings dir
    python transcribe.py --recordings-dir ./my_recordings
    python transcribe.py --model-size medium              # Whisper model size
    python transcribe.py --help

Output:
    recordings/metadata.csv — filename|transcript|duration|language
    recordings/alignment_report.txt — clips with mismatched transcripts

Requirements:
    pip install faster-whisper
"""

import argparse
import csv
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


# ═══════════════════════════════════════════════════════════════
# Prompt lookup — maps filenames back to original prompts
# ═══════════════════════════════════════════════════════════════

def load_original_prompts() -> dict[int, str]:
    """
    Import prompts from record_voice.py and build an index→text map.
    This lets us compare Whisper's transcript against what you were asked to say.
    """
    try:
        # Import from sibling module
        sys.path.insert(0, str(Path(__file__).parent))
        from record_voice import PROMPTS
        return {i: p["text"] for i, p in enumerate(PROMPTS)}
    except ImportError:
        return {}


def extract_clip_index(filename: str) -> int | None:
    """
    Extract the prompt index from a filename like 'clip_0042_casual_en.wav'.
    Returns 42, or None if the filename doesn't match the pattern.
    """
    parts = filename.replace(".wav", "").split("_")
    if len(parts) >= 2 and parts[0] == "clip":
        try:
            return int(parts[1])
        except ValueError:
            pass
    return None


def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Compute normalized string similarity between two texts.
    Returns 0.0 (completely different) to 1.0 (identical).
    Uses SequenceMatcher which handles insertions, deletions, and substitutions.
    """
    a = text_a.lower().strip()
    b = text_b.lower().strip()
    return SequenceMatcher(None, a, b).ratio()


# ═══════════════════════════════════════════════════════════════
# Main transcription pipeline
# ═══════════════════════════════════════════════════════════════

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe recorded voice clips using faster-whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python transcribe.py
    python transcribe.py --recordings-dir ./my_recordings
    python transcribe.py --model-size large-v3 --device cuda
        """
    )
    parser.add_argument("--recordings-dir", type=str, default=None,
                        help="Directory with WAV files (default: ./recordings)")
    parser.add_argument("--model-size", type=str, default="medium",
                        help="Whisper model size: tiny, base, small, medium, large-v3 (default: medium)")
    parser.add_argument("--device", type=str, default="auto",
                        help="Device: auto, cpu, cuda (default: auto)")
    parser.add_argument("--language", type=str, default=None,
                        help="Force language (e.g., 'en', 'hi'). Default: auto-detect")
    parser.add_argument("--alignment-threshold", type=float, default=0.6,
                        help="Similarity threshold for flagging misaligned transcripts (0-1, default: 0.6)")
    parser.add_argument("--output-csv", type=str, default=None,
                        help="Output CSV path (default: recordings/metadata.csv)")
    args = parser.parse_args()

    # Check dependencies
    if not HAS_SF:
        print("ERROR: soundfile not installed. Run: pip install soundfile")
        sys.exit(1)
    if not HAS_WHISPER:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")
        sys.exit(1)

    # Resolve paths
    recordings_dir = Path(args.recordings_dir) if args.recordings_dir else Path(__file__).parent / "recordings"
    if not recordings_dir.exists():
        print(f"ERROR: Recordings directory not found: {recordings_dir}")
        print("Run record_voice.py first to create recordings.")
        sys.exit(1)

    wav_files = sorted(recordings_dir.glob("clip_*.wav"))
    if not wav_files:
        print(f"ERROR: No clip_*.wav files found in {recordings_dir}")
        sys.exit(1)

    output_csv = Path(args.output_csv) if args.output_csv else recordings_dir / "metadata.csv"
    alignment_report = recordings_dir / "alignment_report.txt"

    print(f"""
{BOLD}{'=' * 60}
   JARVIS Voice Transcriber
   Powered by faster-whisper ({args.model_size})
{'=' * 60}{RESET}

  Recordings: {recordings_dir}
  WAV files:  {len(wav_files)}
  Output:     {output_csv}
""")

    # Load original prompts for alignment check
    original_prompts = load_original_prompts()
    if original_prompts:
        print(f"  Loaded {len(original_prompts)} original prompts for alignment checking.")
    else:
        print(f"  {YELLOW}Warning: Could not load original prompts. Alignment checking disabled.{RESET}")

    # Detect device
    device = args.device
    compute_type = "float16"
    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
                compute_type = "int8"
        except ImportError:
            device = "cpu"
            compute_type = "int8"
    elif device == "cpu":
        compute_type = "int8"

    print(f"  Device: {device} ({compute_type})")
    print(f"\n  Loading Whisper {args.model_size}...")

    start_time = time.monotonic()
    model = WhisperModel(args.model_size, device=device, compute_type=compute_type)
    load_time = time.monotonic() - start_time
    print(f"  Model loaded in {load_time:.1f}s\n")

    # Transcribe all files
    results = []
    misaligned = []
    total_audio_duration = 0.0

    for i, wav_path in enumerate(wav_files):
        filename = wav_path.name
        clip_idx = extract_clip_index(filename)

        # Get audio duration
        info = sf.info(str(wav_path))
        duration = info.duration
        total_audio_duration += duration

        # Transcribe
        t0 = time.monotonic()
        segments, info_result = model.transcribe(
            str(wav_path),
            language=args.language,
            beam_size=5,
            word_timestamps=False,
            vad_filter=True,
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.monotonic() - t0

        detected_lang = info_result.language if hasattr(info_result, "language") else "?"
        lang_prob = info_result.language_probability if hasattr(info_result, "language_probability") else 0.0

        # Alignment check
        alignment_status = ""
        if clip_idx is not None and clip_idx in original_prompts:
            original = original_prompts[clip_idx]
            similarity = compute_similarity(transcript, original)
            if similarity < args.alignment_threshold:
                alignment_status = f" {YELLOW}[MISMATCH {similarity:.0%}]{RESET}"
                misaligned.append({
                    "filename": filename,
                    "original": original,
                    "transcript": transcript,
                    "similarity": similarity,
                })
            else:
                alignment_status = f" {GREEN}[OK {similarity:.0%}]{RESET}"

        results.append({
            "filename": filename,
            "transcript": transcript,
            "duration": round(duration, 2),
            "language": detected_lang,
        })

        # Progress
        pct = (i + 1) / len(wav_files) * 100
        print(f"  [{i + 1:3d}/{len(wav_files)}] {pct:5.1f}% | {filename} ({duration:.1f}s, {elapsed:.1f}s){alignment_status}")

        # Truncate long transcripts in display
        display_text = transcript[:80] + "..." if len(transcript) > 80 else transcript
        print(f"           {DIM}\"{display_text}\"{RESET}")

    # Write metadata.csv
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(["filename", "transcript", "duration", "language"])
        for r in results:
            writer.writerow([r["filename"], r["transcript"], r["duration"], r["language"]])

    # Write alignment report
    if misaligned:
        with open(alignment_report, "w", encoding="utf-8") as f:
            f.write("Alignment Report — Mismatched Transcripts\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Threshold: {args.alignment_threshold:.0%} similarity\n")
            f.write(f"Flagged: {len(misaligned)} / {len(results)} clips\n\n")
            for m in misaligned:
                f.write(f"File: {m['filename']} (similarity: {m['similarity']:.0%})\n")
                f.write(f"  Prompt:     \"{m['original']}\"\n")
                f.write(f"  Transcript: \"{m['transcript']}\"\n\n")

    # Summary
    total_time = time.monotonic() - start_time
    print(f"""
{'=' * 60}
  Transcription complete!

  Clips processed:  {len(results)}
  Total audio:      {total_audio_duration / 60:.1f} minutes
  Processing time:  {total_time:.1f}s ({total_audio_duration / total_time:.1f}x realtime)
  Output:           {output_csv}
""")

    if misaligned:
        print(f"  {YELLOW}Misaligned clips: {len(misaligned)}{RESET}")
        print(f"  Review: {alignment_report}")
        print(f"  These clips may have ad-libbed text — re-record or use the Whisper transcript.")
    else:
        print(f"  {GREEN}All clips aligned with original prompts!{RESET}")

    print(f"""
  Next step: python prepare_data.py --metadata {output_csv}
{'=' * 60}
""")


if __name__ == "__main__":
    main()
