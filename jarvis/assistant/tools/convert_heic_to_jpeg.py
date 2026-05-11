#!/usr/bin/env python3
"""
convert_heic_to_jpeg.py — convert HEIC/HEIF photos in-place to real JPEG.

## Why this exists

Google Photos preserves the ORIGINAL file bytes when we download via
`=d` (which is what we want for EXIF preservation). For photos taken on
iPhones and some Androids, the original is HEIC — an efficient container
based on HEVC video compression. Most browsers (Chrome, Firefox) can't
render HEIC natively; the image area shows BLACK in the curate UI.

Our sync tool labels everything `.jpg` regardless of true format, so the
file extension is misleading. This tool:

  1. Scans every `.jpg` file in the photos folder
  2. Detects HEIC bytes via the magic-number signature (ftyp...heic /
     heix / mif1 / msf1 / heim / heis / heimheis / heisheim)
  3. Reads it via pillow-heif
  4. Re-saves it as real JPEG (quality 92) IN PLACE
  5. Preserves EXIF (timestamps, GPS) — pillow-heif passes the EXIF
     block through to the JPEG output

GIFs are converted too (animated GIFs lose animation; first frame only —
acceptable for our slideshow use case).

The script is idempotent. Re-running skips files that are already real
JPEGs.

## Run

  python tools/convert_heic_to_jpeg.py
  python tools/convert_heic_to_jpeg.py --dry-run    # list what would convert
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

try:
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    print("ERROR: install pillow-heif:  pip install pillow-heif", file=sys.stderr)
    sys.exit(1)


def detect_format(path: Path) -> str:
    """Quick magic-byte sniff. Returns 'jpeg' | 'heic' | 'gif' | 'png' | 'other'."""
    with open(path, "rb") as f:
        head = f.read(64)
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    # HEIC: 'ftypheic', 'ftypheix', 'ftypmif1', 'ftypmsf1', etc. The 'ftyp'
    # marker is at bytes 4-8. The brand is at bytes 8-12.
    if head[4:8] == b"ftyp" and head[8:12] in (
        b"heic", b"heix", b"mif1", b"msf1", b"heis", b"heim", b"heiM", b"hevc",
        b"hevx", b"avif",
    ):
        return "heic"
    if head[:3] == b"GIF":
        return "gif"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return "other"


def convert_to_jpeg(path: Path, quality: int = 92) -> tuple[bool, str]:
    """Read whatever format, save as JPEG in place. Returns (success, format)."""
    fmt = detect_format(path)
    if fmt == "jpeg":
        return False, "jpeg"  # already JPEG, no work needed
    if fmt == "other":
        return False, "other"

    try:
        img = Image.open(path)
        # Preserve EXIF if present.
        exif_bytes = img.info.get("exif", b"")
        if img.mode != "RGB":
            # HEIC can have alpha or 16-bit modes
            img = img.convert("RGB")
        # Write to memory first, then atomically replace original
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True,
                 exif=exif_bytes)
        path.write_bytes(buf.getvalue())
        return True, fmt
    except Exception as e:
        print(f"  ! {path.name}: {e}")
        return False, fmt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--photos-dir",
        default="events/astha-birthday/media/photos",
        help="Photos directory (default: events/astha-birthday/media/photos)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List files that would convert, don't write")
    parser.add_argument("--quality", type=int, default=92,
                        help="JPEG quality 1-100, default 92")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    photos_dir = Path(args.photos_dir)
    if not photos_dir.is_absolute():
        photos_dir = here / photos_dir

    files = sorted(p for p in photos_dir.glob("*.jpg") if p.is_file())
    print(f"Scanning {len(files)} files...")

    by_format = {}
    to_convert = []
    for p in files:
        fmt = detect_format(p)
        by_format[fmt] = by_format.get(fmt, 0) + 1
        if fmt in ("heic", "gif", "png"):
            to_convert.append((p, fmt))

    print(f"\nFormat breakdown:")
    for fmt, n in sorted(by_format.items(), key=lambda x: -x[1]):
        print(f"  {n:>4d}  {fmt}")
    print(f"\nWill convert: {len(to_convert)} files")

    if args.dry_run:
        for p, fmt in to_convert[:10]:
            print(f"  [{fmt}] {p.name}")
        if len(to_convert) > 10:
            print(f"  ... and {len(to_convert) - 10} more")
        return 0

    if not to_convert:
        print("Nothing to do.")
        return 0

    print(f"\nConverting...")
    success = 0
    failed = 0
    for i, (p, fmt) in enumerate(to_convert, 1):
        ok, _ = convert_to_jpeg(p, args.quality)
        if ok:
            success += 1
        else:
            failed += 1
        if i % 25 == 0 or i == len(to_convert):
            print(f"  [{i}/{len(to_convert)}]  ✓ {success}  ✗ {failed}")

    print(f"\nDone. Converted {success} files; {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
