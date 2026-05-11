#!/usr/bin/env python3
"""
scaffold_captions.py — generate a starter `captions.yaml` from a synced
Google Photos album manifest.

## What this is

The Yaadein slideshow needs more than just images — it needs CAPTIONS
written in your voice. A great slideshow has structure (chapters), an
arc (beginning to end), and personal touches (specific memories, jokes,
nicknames). This scaffold builds the SHAPE of that file. You fill in
the words.

## How it works

1. Reads `manifest.json` produced by sync_google_album.py.
2. Detects natural chapter breaks using >14-day gaps in capture date.
3. Emits a `captions.yaml` with:
     - top-level "chapters" section (you fill in the title)
     - per-photo entry: file, date, chapter index, caption (empty),
       skip flag, highlight flag

You then either:
  (a) Hand-edit captions.yaml in your editor, OR
  (b) Run `tools/generate_captions.py` to have an LLM populate them
     based on visible content + chapter context (you provide voice
     samples + names + events as inputs to that tool).

Either way, the iteration loop is: edit → preview → repeat.

## Run

  python tools/scaffold_captions.py
  python tools/scaffold_captions.py --gap-days 7    # tighter chapter splits
  python tools/scaffold_captions.py --force         # overwrite existing
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# Don't let PyYAML alphabetize keys — preserve insertion order in dicts.
# We want chapter/photo entries to remain in chronological order in the
# output file so a human editor reads them in story order.
class OrderedDumper(yaml.SafeDumper):
    pass


def _represent_dict_order(self, data):
    return self.represent_mapping("tag:yaml.org,2002:map", data.items())


OrderedDumper.add_representer(OrderedDict, _represent_dict_order)


@dataclass
class ChapterRange:
    index: int                       # 1, 2, 3, ...
    start_iso: str                   # YYYY-MM-DD
    end_iso: str                     # YYYY-MM-DD
    photo_count: int
    suggested_title: str             # auto-derived stub for the user to edit


def detect_chapters(
    photos: list[dict[str, Any]],
    gap_days: int = 14,
) -> list[ChapterRange]:
    """
    Cluster photos into chapters by date gaps. A gap of >gap_days between
    consecutive photos starts a new chapter.

    Returns a list of ChapterRange. Each photo's eventual chapter index is
    derived by linear scan over this list.
    """
    dated = [p for p in photos if p.get("capture_ts_ms")]
    dated.sort(key=lambda p: p["capture_ts_ms"])

    if not dated:
        return []

    chapters: list[ChapterRange] = []
    current_start = 0
    gap_ms = gap_days * 24 * 3600 * 1000

    for i in range(1, len(dated)):
        if dated[i]["capture_ts_ms"] - dated[i - 1]["capture_ts_ms"] > gap_ms:
            chapters.append(_make_chapter(len(chapters) + 1, dated[current_start:i]))
            current_start = i
    chapters.append(_make_chapter(len(chapters) + 1, dated[current_start:]))

    return chapters


def _make_chapter(index: int, photos: list[dict[str, Any]]) -> ChapterRange:
    """Construct a ChapterRange with a suggested title stub."""
    start_iso = photos[0]["capture_dt"][:10]
    end_iso = photos[-1]["capture_dt"][:10]
    count = len(photos)
    if start_iso == end_iso:
        # Single day — likely a specific event.
        if count > 20:
            title = f"[edit] Big day — {start_iso}"
        else:
            title = f"[edit] One day — {start_iso}"
    elif count > 25:
        title = f"[edit] The trip — {start_iso} to {end_iso}"
    elif count <= 5:
        title = f"[edit] Quiet days — {start_iso} to {end_iso}"
    else:
        title = f"[edit] {start_iso} to {end_iso}"
    return ChapterRange(
        index=index,
        start_iso=start_iso,
        end_iso=end_iso,
        photo_count=count,
        suggested_title=title,
    )


def assign_chapter(photo_ts_ms: int | None, chapters: list[ChapterRange]) -> int:
    """Map a photo's timestamp back to a 1-based chapter index."""
    if not photo_ts_ms:
        return 0
    dt = datetime.fromtimestamp(photo_ts_ms / 1000, tz=timezone.utc)
    iso = dt.strftime("%Y-%m-%d")
    for c in chapters:
        if c.start_iso <= iso <= c.end_iso:
            return c.index
    return 0  # photo with timestamp outside any chapter (shouldn't happen)


def build_captions_yaml(
    manifest: dict[str, Any],
    chapters: list[ChapterRange],
) -> OrderedDict:
    """Construct the captions.yaml document."""

    # ── Top-level metadata
    doc: OrderedDict = OrderedDict()
    doc["album"] = manifest.get("album_title", "Album")
    doc["source_url"] = manifest.get("source_url", "")
    doc["synced_at"] = manifest.get("synced_at", "")
    doc["total_photos"] = len(manifest.get("photos", []))

    # ── Chapters section
    doc["chapters"] = OrderedDict()
    for c in chapters:
        chapter_meta = OrderedDict()
        chapter_meta["title"] = c.suggested_title
        chapter_meta["date_range"] = f"{c.start_iso} → {c.end_iso}"
        chapter_meta["photo_count"] = c.photo_count
        # Per-chapter caption: shown as a section header in the slideshow
        # (or used as the LLM prompt context when generating per-photo
        # captions). Leave empty — user fills in.
        chapter_meta["intro_caption"] = ""
        doc["chapters"][f"chapter_{c.index}"] = chapter_meta

    # ── Per-photo entries (preserves chronological order from manifest)
    photos_sorted = sorted(
        [p for p in manifest["photos"] if p.get("filename")],
        key=lambda p: (p.get("capture_ts_ms") or 0),
    )
    doc["photos"] = []
    for p in photos_sorted:
        entry: OrderedDict = OrderedDict()
        entry["file"] = p["filename"]
        entry["date"] = p["capture_dt"][:10] if p.get("capture_dt") else "undated"
        entry["chapter"] = assign_chapter(p.get("capture_ts_ms"), chapters)
        entry["caption"] = ""        # user fills in (or LLM)
        entry["skip"] = False        # set True to omit from slideshow
        entry["highlight"] = False   # set True to add visual emphasis
        doc["photos"].append(entry)

    return doc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a captions.yaml from a synced album manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--manifest",
        default="events/astha-birthday/media/photos/manifest.json",
        help="Path to the manifest produced by sync_google_album.py.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="events/astha-birthday/media/captions.yaml",
        help="Output file path.",
    )
    parser.add_argument(
        "--gap-days",
        type=int,
        default=14,
        help="A gap of more than this many days starts a new chapter "
        "(default 14).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing captions.yaml. Otherwise the tool "
        "refuses (so we don't lose user edits).",
    )
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = here / manifest_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = here / output_path

    if not manifest_path.exists():
        print(
            f"ERROR: manifest not found at {manifest_path}.\n"
            f"Run sync_google_album.py first.",
            file=sys.stderr,
        )
        return 1

    if output_path.exists() and not args.force:
        print(
            f"ERROR: {output_path} already exists. Re-run with --force "
            f"to overwrite (you'll lose any caption edits).",
            file=sys.stderr,
        )
        return 1

    manifest = json.loads(manifest_path.read_text())
    chapters = detect_chapters(manifest["photos"], gap_days=args.gap_days)
    doc = build_captions_yaml(manifest, chapters)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(doc, Dumper=OrderedDumper, sort_keys=False, allow_unicode=True)
    )

    print(f"== scaffold_captions.py ==")
    print(f"Manifest: {manifest_path}")
    print(f"Photos:   {len(manifest['photos'])}")
    print(f"Chapters: {len(chapters)}  (gap threshold: {args.gap_days} days)")
    print(f"Output:   {output_path}")
    print()
    print("Detected chapters:")
    for c in chapters:
        span = c.start_iso if c.start_iso == c.end_iso else f"{c.start_iso} → {c.end_iso}"
        print(f"  Chapter {c.index:>2d}: {span:30s}  {c.photo_count:>3d} photos")
    print()
    print("Next steps:")
    print("  1. Open captions.yaml. For each chapter, replace the [edit]")
    print("     placeholder title with what actually happened (e.g.")
    print("     'Wedding day' or 'Goa trip with the squad').")
    print("  2. Either fill caption: \"\" lines yourself, OR run")
    print("     tools/generate_captions.py (once we have voice samples")
    print("     and an LLM configured) to populate the stubs.")
    print("  3. Preview with tools/preview_yaadein.py (TODO).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
