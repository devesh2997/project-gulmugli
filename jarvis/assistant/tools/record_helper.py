#!/usr/bin/env python3
"""
record_helper.py — interactive voice-recording helper for the
Phase 7.1 user-content task.

The pack expects ~6 named recordings from Devesh:
  - devesh_intro.wav         (~30s, the launch sequence intro)
  - birthday_letter.wav      (~60s, played from voice memo library)
  - when_you_are_sad.wav     (~45s, sorry-mode memo)
  - happy_birthday.wav       (the birthday song with her name)
  - quiz_reveal.wav          (final answer to the birthday quiz)
  - 1+ besura clips          (his singing — the "Mera Man Kehne Laga"
                              tradition from project_ag)
  - 1+ sorry-mode memos      (varied apology phrasings)

This tool:
  1. Lists each slot, shows its target path + suggested script
  2. Lets you press Enter → record (Ctrl-C to stop) → review
  3. Saves to the right filename
  4. Lets you re-record if you don't like the take

Uses ffmpeg (already installed on most Macs via Homebrew). Falls back
to sox if ffmpeg is missing. Both are checked at startup.

## Usage

    cd jarvis/assistant
    python tools/record_helper.py
    python tools/record_helper.py --slot intro    # jump to one slot
    python tools/record_helper.py --list          # show targets only
    python tools/record_helper.py --device 0      # pick a specific mic input

## Audio device picker

On Mac, default input is whatever System Settings → Sound says. To
list available inputs:

    ffmpeg -f avfoundation -list_devices true -i ""

Pass the input index via --device (default: 0).

## Recording quality

44.1 kHz mono, 16-bit PCM WAV — matches the typical voice memo
quality and decodes fine through any audio path on Jetson.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = PROJECT_ROOT / "events" / "astha-birthday"


# ── Slot manifest ────────────────────────────────────────────────────


# Each slot: (key, path-relative-to-pack-dir, default-duration-s, script)
SLOTS = [
    (
        "intro",
        "media/sounds/devesh_intro.wav",
        35,
        """\
A warm 30-second intro played the moment you trigger the surprise.
Suggested arc:
  - Start: "Astha. Happy birthday."
  - Middle: "I'm Vesper. Devesh has been building me for months —
    for you. He'll explain in a minute, but first…"
  - End: a beat of silence, then Vesper's TTS picks up.
Aim for warm and unhurried. Imperfect > polished.
""",
    ),
    (
        "birthday_letter",
        "media/voice_memos/birthday_letter.wav",
        60,
        """\
A spoken letter accessed via "Vesper, Devesh ne kuch chhoda hai."
What you might say in a 1-minute voice note. No format pressure —
just talk. The fact that it's YOUR voice is what lands.
""",
    ),
    (
        "when_you_are_sad",
        "media/voice_memos/when_you_are_sad.wav",
        45,
        """\
The fallback memo for sorry-mode and "agar main udaas hoon" lookups.
Soft, comforting, specific. ~45 seconds.
""",
    ),
    (
        "happy_birthday",
        "media/songs/happy_birthday.wav",
        20,
        """\
Sing happy birthday with Astha's name. ~15-20 seconds. project_ag
heritage: imperfect singing > polished anything.
""",
    ),
    (
        "quiz_reveal",
        "media/sounds/quiz_reveal.wav",
        30,
        """\
The final reveal answer to the birthday quiz: your favorite memory
of her this year. ~20-30 seconds. Played at the end of the quiz
with intro line "Aur ab ek aakhri cheez. Devesh ne yeh special
message chhoda."
""",
    ),
    (
        "besura_1",
        "media/besura/song_1.wav",
        90,
        """\
Devesh sings a song. project_ag had "Mera Man Kehne Laga" — pick
something with personal meaning, not technical perfection. ~1-2
minutes. The /api/yaadein/list endpoint will surface this on
demand via "Vesper, sing for me."
""",
    ),
    (
        "sorry_memo_1",
        "media/sorry/sorry_1.wav",
        25,
        """\
A sorry-mode memo (~20-30s). Vesper plays this when Astha says
"sorry shona" or "naraz mat ho." Optional but recommended.
""",
    ),
]


# ── Output helpers ──────────────────────────────────────────────────


def _hr() -> None:
    print(f"{DIM}{'─' * 60}{RESET}")


def _bold(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


# ── Recording engine ────────────────────────────────────────────────


def find_recorder() -> tuple[str, list[str]] | None:
    """Pick ffmpeg or sox depending on availability. Returns (cmd, base_args)."""
    if shutil.which("ffmpeg"):
        # avfoundation is the macOS input; alsa is Linux. Auto-detect.
        if sys.platform == "darwin":
            return ("ffmpeg", ["-f", "avfoundation", "-i", ":0", "-y"])
        else:
            return ("ffmpeg", ["-f", "alsa", "-i", "default", "-y"])
    if shutil.which("sox"):
        return ("rec", [])  # sox installs as `rec`
    return None


def record_clip(
    target: Path,
    duration_s: int,
    device_idx: int = 0,
) -> bool:
    """
    Record audio to target. Blocks until duration or Ctrl-C.
    Returns True on success, False on failure.
    """
    rec = find_recorder()
    if rec is None:
        print(f"{RED}No audio recorder found. Install ffmpeg or sox.{RESET}",
              file=sys.stderr)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd_name, base_args = rec
    if cmd_name == "ffmpeg":
        cmd = [
            "ffmpeg",
        ]
        if sys.platform == "darwin":
            # Override the device index in :0 to whatever the user picked.
            cmd += ["-f", "avfoundation", "-i", f":{device_idx}", "-y"]
        else:
            cmd += base_args
        cmd += [
            "-ar", "44100", "-ac", "1",
            "-t", str(duration_s),
            "-acodec", "pcm_s16le",
            str(target),
        ]
    else:
        # sox `rec`
        cmd = ["rec", "-q", "-r", "44100", "-c", "1", "-b", "16",
               str(target), "trim", "0", str(duration_s)]

    print(f"{GREEN}🔴 Recording {duration_s}s to {target.name}…{RESET}")
    print(f"{DIM}(Ctrl-C to stop early){RESET}")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped early. File still saved.{RESET}")
        return target.is_file() and target.stat().st_size > 0
    if proc.returncode != 0:
        print(f"{RED}Recorder exited with code {proc.returncode}.{RESET}")
        return False
    if not target.is_file() or target.stat().st_size == 0:
        print(f"{RED}Output file is empty.{RESET}")
        return False
    return True


def play_clip(target: Path) -> None:
    """Best-effort playback of a recorded clip via afplay/mpv."""
    if shutil.which("afplay"):
        subprocess.run(["afplay", str(target)])
    elif shutil.which("paplay"):
        subprocess.run(["paplay", str(target)])
    elif shutil.which("mpv"):
        subprocess.run(["mpv", "--no-terminal", "--no-video", str(target)])
    else:
        print(f"{YELLOW}No playback tool found — clip is at: {target}{RESET}")


# ── Modes ───────────────────────────────────────────────────────────


def mode_list() -> None:
    print(f"\n{_bold('Recording slots')}\n")
    for key, rel, dur, _ in SLOTS:
        target = PACK_DIR / rel
        marker = (
            f"{GREEN}✓ recorded{RESET}" if target.is_file()
            else f"{RED}— missing{RESET}"
        )
        print(f"  {marker:25s} {key:18s} {dur:>3}s   {DIM}{rel}{RESET}")
    print()


def mode_record(slot_filter: Optional[str], device_idx: int) -> int:
    rec = find_recorder()
    if rec is None:
        print(f"{RED}No recorder available. Install ffmpeg (`brew install ffmpeg`) "
              f"or sox.{RESET}", file=sys.stderr)
        return 2

    slots = SLOTS
    if slot_filter:
        slots = [s for s in SLOTS if slot_filter in s[0]]
        if not slots:
            print(f"{RED}No slot matches {slot_filter!r}{RESET}", file=sys.stderr)
            return 2

    print(f"\n{_bold('🎤 Voice recording session')}")
    print(f"{DIM}Mic input: device {device_idx} (use --device N to switch).{RESET}")
    print(f"{DIM}Per slot: read script → press Enter → record → review → keep or redo.{RESET}\n")

    for key, rel, dur, script in slots:
        target = PACK_DIR / rel
        _hr()
        print(f"{_bold(key)}  {DIM}→ {rel}{RESET}")
        print(f"{DIM}{'-' * 5} script {'-' * 5}{RESET}")
        print(script)
        if target.is_file():
            print(f"{YELLOW}Already recorded ({target.stat().st_size // 1024} KB).{RESET}")
            choice = input("Re-record? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                continue

        while True:
            input(f"{GREEN}Press Enter to start recording…{RESET}")
            ok = record_clip(target, duration_s=dur, device_idx=device_idx)
            if not ok:
                print(f"{RED}Recording failed. Skipping this slot.{RESET}")
                break

            print(f"{GREEN}✓ Saved.{RESET} Playing back…")
            play_clip(target)
            choice = input(
                f"\n  [k] keep it  [r] redo  [s] skip → "
            ).strip().lower()
            if choice == "r":
                continue
            if choice == "s":
                # Delete the rejected take.
                try:
                    target.unlink()
                except Exception:
                    pass
                break
            # default = keep
            print(f"{GREEN}Kept.{RESET}\n")
            break

    print(f"\n{GREEN}Done.{RESET} Run `python tools/check_content.py` to see remaining slots.\n")
    return 0


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true",
                   help="Print all slots and their status, then exit")
    p.add_argument("--slot", metavar="KEY",
                   help="Record only the slot whose key contains this string")
    p.add_argument("--device", type=int, default=0,
                   help="Audio input device index (Mac avfoundation). "
                        "List devices via `ffmpeg -f avfoundation -list_devices true -i \"\"`")
    args = p.parse_args()

    if args.list:
        mode_list()
        return 0
    return mode_record(slot_filter=args.slot, device_idx=args.device)


if __name__ == "__main__":
    sys.exit(main())
