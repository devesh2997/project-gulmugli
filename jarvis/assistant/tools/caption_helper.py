#!/usr/bin/env python3
"""
caption_helper.py — interactive captioning for the Yaadein photo bank.

The Phase 7.2 user-content task is to write a caption per photo in
the project_ag voice (Hinglish, specific memories, emoji). With 30-50
photos, that's the slowest content step. This tool walks them in
order, prompts you per photo, and writes back to captions.yaml as you
go (so quitting mid-session doesn't lose work).

## Usage

    cd jarvis/assistant
    python tools/caption_helper.py

    # Skip ahead to a specific photo (useful if you stopped mid-list):
    python tools/caption_helper.py --start 010.jpg

    # Just review what you've written so far:
    python tools/caption_helper.py --review

## Workflow

For each photo:
  1. Tool prints the photo's filename + opens it (Preview on Mac)
  2. You type a caption (or hit Enter to skip / paste from notes)
  3. Tool writes captions.yaml after every entry (so Ctrl-C is safe)
  4. Repeat for the next photo

Tip: if you have notes elsewhere (Notes.app / Apple Mail with old
WhatsApp captions), keep them open in another window. Paste lines
without retyping.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHOTOS_DIR = PROJECT_ROOT / "events" / "astha-birthday" / "media" / "photos"
CAPTIONS_PATH = PHOTOS_DIR / "captions.yaml"


# ── Image discovery ────────────────────────────────────────────────


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def list_photo_files() -> list[Path]:
    if not PHOTOS_DIR.is_dir():
        return []
    return sorted(
        p for p in PHOTOS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


# ── captions.yaml round-trip ───────────────────────────────────────


def load_captions() -> dict:
    """Returns the loaded YAML (or a freshly initialized dict)."""
    if not CAPTIONS_PATH.is_file():
        return {"music": None, "photos": []}
    try:
        with CAPTIONS_PATH.open() as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"{RED}Could not parse captions.yaml: {e}{RESET}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        data = {"photos": [], "music": None}
    data.setdefault("photos", [])
    return data


def save_captions(data: dict) -> None:
    """Atomic write — temp file in same dir + rename."""
    import os
    tmp = CAPTIONS_PATH.with_suffix(".yaml.tmp")
    with tmp.open("w") as f:
        yaml.safe_dump(
            data, f, sort_keys=False, allow_unicode=True, width=88,
        )
    os.replace(tmp, CAPTIONS_PATH)


def existing_caption_for(data: dict, filename: str) -> Optional[str]:
    """Return the existing caption text for `filename`, or None."""
    for entry in data.get("photos", []):
        if isinstance(entry, dict) and entry.get("file") == filename:
            return entry.get("caption")
    return None


def upsert_caption(data: dict, filename: str, caption: str, order: int) -> None:
    photos = data.setdefault("photos", [])
    for i, entry in enumerate(photos):
        if isinstance(entry, dict) and entry.get("file") == filename:
            entry["caption"] = caption
            entry["order"] = order
            return
    photos.append({"file": filename, "caption": caption, "order": order})


# ── Open a photo in Preview / system viewer ─────────────────────────


def open_photo(path: Path) -> None:
    """
    Best-effort: open the photo in a system viewer so the user can see
    what they're captioning. Mac uses `open`, Linux uses `xdg-open`.
    Failures are silent — captioning still works without this.
    """
    cmd = None
    if shutil.which("open"):
        cmd = ["open", str(path)]
    elif shutil.which("xdg-open"):
        cmd = ["xdg-open", str(path)]
    if cmd:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


# ── Modes ──────────────────────────────────────────────────────────


def mode_review(data: dict) -> None:
    photos = data.get("photos") or []
    if not photos:
        print("No captions written yet.")
        return
    print(f"\n{BOLD}Captions so far ({len(photos)}){RESET}\n")
    for entry in photos:
        if not isinstance(entry, dict):
            continue
        cap = entry.get("caption", "").strip()
        if not cap:
            cap = f"{DIM}(empty){RESET}"
        print(f"  {entry.get('order', '?'):>3}  {entry.get('file'):20s}  {cap}")
    print()


def mode_caption(start: Optional[str]) -> int:
    photos = list_photo_files()
    if not photos:
        print(f"{RED}No photos in {PHOTOS_DIR}{RESET}", file=sys.stderr)
        print(f"{DIM}Drop *.jpg / *.png files there first.{RESET}", file=sys.stderr)
        return 2

    data = load_captions()

    # Optional --start: skip ahead to a specific filename.
    if start:
        try:
            idx = next(i for i, p in enumerate(photos) if p.name == start)
            photos = photos[idx:]
        except StopIteration:
            print(f"{RED}--start file not found: {start}{RESET}", file=sys.stderr)
            return 2

    print(f"\n{BOLD}🖼  Yaadein captioning — {len(photos)} photo(s) left{RESET}")
    print(f"{DIM}Type a caption per photo. Empty Enter = skip. Ctrl-C anytime — your work is saved each turn.{RESET}\n")

    captioned_this_session = 0
    for i, photo in enumerate(photos, start=1):
        existing = existing_caption_for(data, photo.name)
        order_num = list_photo_files().index(photo) + 1   # absolute order in folder

        # Header.
        print(f"{BOLD}[{i}/{len(photos)}] {photo.name}{RESET}"
              + (f" {DIM}(order {order_num}){RESET}"))
        if existing:
            print(f"  {DIM}existing: {existing}{RESET}")

        open_photo(photo)
        try:
            cap = input(f"  caption {YELLOW}>{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Saved up to here. Resume with: python tools/caption_helper.py --start {photo.name}{RESET}")
            return 0

        cap = cap.strip()
        if not cap:
            # Empty input → skip without overwriting.
            continue

        upsert_caption(data, photo.name, cap, order_num)
        save_captions(data)
        captioned_this_session += 1

    print(f"\n{GREEN}Done. {captioned_this_session} caption(s) written this session.{RESET}")
    print(f"{DIM}Reviewable via: python tools/caption_helper.py --review{RESET}\n")
    return 0


# ── Main ───────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", metavar="FILENAME",
                   help="Skip ahead to this filename in the photo list")
    p.add_argument("--review", action="store_true",
                   help="Just print what's been captioned so far and exit")
    args = p.parse_args()

    data = load_captions()

    if args.review:
        mode_review(data)
        return 0
    return mode_caption(start=args.start)


if __name__ == "__main__":
    sys.exit(main())
