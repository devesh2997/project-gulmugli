#!/usr/bin/env python3
"""
sync_google_album.py — download every photo from a Google Photos shared album
into a local directory, preserving capture-date EXIF and ordering.

## Why this exists

Google killed the Photos Library API for reading user-owned photos in
March 2025 — third-party apps can no longer enumerate or fetch photos
from a user's library. The one capability that still works is fetching
PUBLICLY-SHARED ALBUMS via the share-page URL. This tool uses that.

The share-page HTML embeds an `AF_initDataCallback({key:'ds:1', ...})`
JavaScript block whose `data` array contains every photo's ID, thumbnail
URL, dimensions, and capture timestamp. We parse the block, then for
each photo fetch the full-resolution original via `?=d` on the
`lh3.googleusercontent.com/pw/...` thumbnail URL.

`=d` returns the byte-identical original (EXIF preserved). Sized
variants like `=w2048` re-encode and strip most EXIF.

## What this is NOT

Not a full Google Photos client. Not auth-aware. Cannot see private
albums. Cannot read captions/comments from Google's UI (those are not
in the share-page JSON). Cannot follow album updates in real time —
you re-run the sync to pick up new photos.

## Output

The sync writes:

  <output_dir>/
    001-2025-02-09.jpg          ← chronologically-numbered files
    002-2025-02-09.jpg              with capture date in the name
    003-2025-02-12.jpg
    ...
    manifest.json               ← every photo's metadata (id, timestamp,
                                  dimensions, filename) — used by the
                                  caption generator and curation tools

The 001 / 002 / ... prefix means `ls` lists in chronological order.
The chronological order is OLDEST-FIRST (start of the story).

## Idempotency

Running the sync twice is safe. Files that already exist on disk with
the right photo ID are skipped — only new photos are downloaded. To
force a re-download of everything, pass `--force` or delete the output
directory.

## Run

  python tools/sync_google_album.py "https://photos.app.goo.gl/<id>"
  python tools/sync_google_album.py --url <url> --output <dir>
  python tools/sync_google_album.py --url <url> --limit 5         # test
  python tools/sync_google_album.py --url <url> --dry-run         # plan
  python tools/sync_google_album.py --url <url> --force           # re-fetch
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class Photo:
    """One photo in the album."""

    photo_id: str               # Google's stable ID, used for de-dup on re-sync
    thumbnail_url: str          # the lh3.googleusercontent.com/pw/... URL
    width: int | None
    height: int | None
    capture_ts_ms: int | None   # millis since epoch from Google's metadata
    capture_dt: str | None      # ISO 8601 string for human reading

    @property
    def full_url(self) -> str:
        """Full-resolution download URL — appends =d to get the original
        bytes (EXIF preserved)."""
        return self.thumbnail_url + "=d"


def resolve_short_link(short_url: str) -> str:
    """
    Resolve a photos.app.goo.gl/<id> short link to its real
    photos.google.com/share/... destination.

    Mechanism quirk: the photos.app.goo.gl host serves the Firebase
    DurableDeepLink HTML landing page MOST of the time, but on certain
    requests (HTTP/2 HEAD with the right load-balancer routing) returns
    a clean 302 Location header. The behavior is non-deterministic — we
    retry up to 5 times.

    If retries all fail, raises RuntimeError with instructions for the
    user to paste the long photos.google.com/share/... URL directly.

    Returns the resolved URL, or the input unchanged if it isn't a
    short link.
    """
    if "photos.app.goo.gl" not in short_url:
        return short_url

    if not shutil.which("curl"):
        raise RuntimeError(
            "curl is required to resolve photos.app.goo.gl short links. "
            "Install: brew install curl  (or sudo apt install curl)"
        )

    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-sI",          # silent + headers only
                    "--http2",      # 302 only fires on HTTP/2
                    "-A",
                    UA,
                    short_url,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            time.sleep(1)
            continue

        if result.returncode != 0:
            time.sleep(1)
            continue

        # Find Location header (case-insensitive — HTTP/2 lowercases).
        for line in result.stdout.splitlines():
            if line.lower().startswith("location:"):
                loc = line.split(":", 1)[1].strip()
                if "photos.google.com/share" in loc:
                    return loc

        # No Location this time. Try again — the redirect is flaky.
        time.sleep(0.5)

    # All retries failed. The short link is a Firebase Dynamic Link that
    # only resolves via the JS SDK in a real browser, and the HTTP/2
    # 302 path isn't firing today. Tell the user how to bypass this.
    raise RuntimeError(
        "Could not resolve photos.app.goo.gl short link via HTTP — "
        "Google's Firebase Dynamic Link redirect is intermittent.\n\n"
        "Workaround: open the album in Google Photos on the desktop "
        "web (https://photos.google.com), then copy the URL from the "
        "browser address bar — it'll look like:\n"
        "  https://photos.google.com/share/AF1Q.../?key=...\n\n"
        "Pass that URL to this tool instead."
    )


def fetch_share_page(share_url: str) -> str:
    """
    Resolve a photos.app.goo.gl short link → photos.google.com/share/...
    URL, then fetch the full HTML page that contains the photo data.
    """
    resolved = resolve_short_link(share_url)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    r = s.get(resolved, timeout=30)
    r.raise_for_status()
    return r.text


def parse_album_html(html: str) -> tuple[str, list[Photo]]:
    """
    Extract the album title and photo list from the share-page HTML.

    Album metadata lives in two `AF_initDataCallback({key:'ds:N', ...})`
    JavaScript blocks. ds:1 has the photo array; the page <title> tag has
    the album name.
    """
    # Album title (best-effort — falls back to "Album" if not present).
    title_m = re.search(r"<title>([^<]+?)(?:\s*-\s*Google Photos)?</title>", html)
    album_title = title_m.group(1).strip() if title_m else "Album"

    # ds:1 data — the photo grid.
    m = re.search(
        r"AF_initDataCallback\(\{key:\s*'ds:1'.*?data:(\[.*?\]), sideChannel:",
        html,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError(
            "Could not locate the photo data block in the share page. "
            "Google may have changed the HTML structure — share the page "
            "HTML and we can update the parser."
        )

    data = json.loads(m.group(1))
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        raise RuntimeError("Photo data block is structured unexpectedly")

    raw_photos: list[Any] = data[1]

    photos: list[Photo] = []
    for p in raw_photos:
        try:
            photo_id = p[0]
            url_info = p[1] or []
            thumbnail_url = url_info[0] if url_info else None
            width = url_info[1] if len(url_info) > 1 else None
            height = url_info[2] if len(url_info) > 2 else None
            ts_ms = p[2] if len(p) > 2 else None
            ts_iso = (
                datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                if ts_ms
                else None
            )
            if not photo_id or not thumbnail_url:
                continue
            photos.append(
                Photo(
                    photo_id=photo_id,
                    thumbnail_url=thumbnail_url,
                    width=width,
                    height=height,
                    capture_ts_ms=ts_ms,
                    capture_dt=ts_iso,
                )
            )
        except (IndexError, TypeError, ValueError):
            # Robust skip — Google occasionally adds malformed entries
            # (test photos, deleted-but-still-listed items). Don't crash.
            continue

    return album_title, photos


def chronological_sort(photos: list[Photo]) -> list[Photo]:
    """
    Order photos OLDEST-FIRST so the resulting filenames sort the same way
    a chronological story does. Photos with no timestamp go to the end
    (rare — usually screenshots / synthetic images).
    """
    def key(p: Photo) -> tuple[int, int]:
        # First sort group: dated (0) vs undated (1) — undated goes last.
        # Second key: timestamp itself (or 0 for undated).
        return (0 if p.capture_ts_ms else 1, p.capture_ts_ms or 0)

    return sorted(photos, key=key)


def filename_for(index: int, photo: Photo) -> str:
    """
    Generate a filename like '001-2025-02-09.jpg'.

    Index pads to 3 digits (supports up to 999 photos cleanly; the format
    still works for 1000+ — just becomes 4 digits and sorts correctly).
    Date format is YYYY-MM-DD so the filenames sort chronologically even
    if the index field gets out of sync.
    """
    if photo.capture_dt:
        date_part = photo.capture_dt[:10]  # YYYY-MM-DD
    else:
        date_part = "undated"
    return f"{index:03d}-{date_part}.jpg"


def existing_manifest(manifest_path: Path) -> dict[str, str]:
    """Return a {photo_id: filename} map from an existing manifest, if any."""
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
        photos = data.get("photos", [])
        return {p["photo_id"]: p["filename"] for p in photos if "photo_id" in p}
    except (json.JSONDecodeError, KeyError):
        return {}


def download_photo(
    photo: Photo, dest: Path, session: requests.Session, max_attempts: int = 3
) -> tuple[bool, str | None]:
    """
    Download one photo to `dest`. Returns (success, error_message).

    Atomic write via .part suffix so an interrupted run doesn't leave a
    partial JPG that the next sync mistakes for a complete download.
    """
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, max_attempts + 1):
        try:
            r = session.get(photo.full_url, timeout=60, stream=True)
            r.raise_for_status()
            with open(part, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
            part.replace(dest)
            return True, None
        except (requests.RequestException, OSError) as e:
            if attempt < max_attempts:
                time.sleep(min(2 ** attempt, 10))  # exponential backoff
                continue
            return False, str(e)
    return False, "unknown"


def write_manifest(
    manifest_path: Path,
    album_title: str,
    share_url: str,
    photos: list[Photo],
    filenames: dict[str, str],
) -> None:
    """
    Save the manifest.json. Includes:
      - album metadata (title, source URL, sync timestamp)
      - every photo's full metadata + the local filename
    """
    payload = {
        "album_title": album_title,
        "source_url": share_url,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "total": len(photos),
        "photos": [
            {
                **asdict(p),
                "filename": filenames.get(p.photo_id),
            }
            for p in photos
        ],
    }
    # Atomic write via tmp file + rename so a crash mid-write doesn't
    # corrupt the manifest.
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp.replace(manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync a Google Photos shared album to a local folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Google Photos share URL (photos.app.goo.gl/... or "
        "photos.google.com/share/...).",
    )
    parser.add_argument(
        "--url",
        dest="url_flag",
        help="Alternate way to pass the share URL.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="events/astha-birthday/media/photos",
        help="Output directory (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        help="Download only the first N photos (chronological). Useful "
        "for quick tests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be downloaded, don't actually fetch.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download every photo even if it's already on disk.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Number of parallel downloads (default 8).",
    )
    args = parser.parse_args()

    share_url = args.url or args.url_flag
    if not share_url:
        parser.error("Pass a Google Photos share URL")

    # Resolve output directory. If it's a relative path, anchor it to the
    # assistant root (this tool lives in tools/, repo root is one level up).
    here = Path(__file__).resolve().parent.parent
    output = Path(args.output)
    if not output.is_absolute():
        output = here / output

    print(f"== sync_google_album.py ==")
    print(f"Source:   {share_url}")
    print(f"Output:   {output}")
    print()

    print("Fetching share page...")
    html = fetch_share_page(share_url)
    print(f"  {len(html):,} bytes")

    print("Parsing photo list...")
    album_title, photos = parse_album_html(html)
    print(f"  Album:    {album_title!r}")
    print(f"  Photos:   {len(photos)} found")

    photos = chronological_sort(photos)
    if args.limit:
        photos = photos[: args.limit]
        print(f"  Limited to first {args.limit} for this run")

    # Date range readout.
    dated = [p for p in photos if p.capture_dt]
    if dated:
        print(
            f"  Range:    {dated[0].capture_dt[:10]} → "
            f"{dated[-1].capture_dt[:10]}"
        )
    print()

    if args.dry_run:
        print("=== DRY RUN — first 20 photos ===")
        for i, p in enumerate(photos[:20], 1):
            fname = filename_for(i, p)
            print(f"  {fname}  {p.width}x{p.height}  {p.photo_id[:30]}...")
        if len(photos) > 20:
            print(f"  ... and {len(photos) - 20} more")
        return 0

    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"

    # Idempotency: read existing manifest to map photo_id → existing filename.
    prior = existing_manifest(manifest_path) if not args.force else {}

    filenames: dict[str, str] = {}
    to_download: list[tuple[int, Photo, Path]] = []
    for i, p in enumerate(photos, 1):
        fname = filename_for(i, p)
        dest = output / fname
        filenames[p.photo_id] = fname

        # If the photo's already on disk by ID, reuse it (rename if the
        # chronological index shifted because new photos were added before
        # it).
        existing = prior.get(p.photo_id)
        if existing and (output / existing).exists():
            if existing != fname:
                (output / existing).rename(dest)
            continue

        if dest.exists() and not args.force:
            # File exists but isn't in the manifest — preserve it; the
            # manifest write below will pick it up.
            continue

        to_download.append((i, p, dest))

    print(
        f"  {len(photos) - len(to_download)} already on disk, "
        f"{len(to_download)} to download"
    )
    if not to_download:
        write_manifest(manifest_path, album_title, share_url, photos, filenames)
        print("Done. Manifest updated.")
        return 0

    # Concurrent download with a small thread pool. Google's CDN handles
    # 8 parallel streams comfortably; bump if your bandwidth allows.
    session = requests.Session()
    session.headers["User-Agent"] = UA

    total = len(to_download)
    failures: list[tuple[Photo, str]] = []
    completed = 0

    def _do(item: tuple[int, Photo, Path]) -> tuple[Photo, bool, str | None]:
        _, p, dest = item
        ok, err = download_photo(p, dest, session)
        return p, ok, err

    print(f"\nDownloading {total} photos at concurrency={args.concurrency}...")
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as ex:
        for fut in concurrent.futures.as_completed(
            ex.submit(_do, item) for item in to_download
        ):
            p, ok, err = fut.result()
            completed += 1
            elapsed = time.time() - start
            rate = completed / max(elapsed, 0.001)
            eta = (total - completed) / max(rate, 0.001)
            if not ok:
                failures.append((p, err or "?"))
                status = "✗"
            else:
                status = "✓"
            sys.stdout.write(
                f"\r  [{completed:>3d}/{total}] {status} "
                f"{rate:.1f}/s  ETA {int(eta)}s   "
            )
            sys.stdout.flush()

    sys.stdout.write("\n")
    write_manifest(manifest_path, album_title, share_url, photos, filenames)

    elapsed = time.time() - start
    ok_count = total - len(failures)
    print(f"\nDownloaded {ok_count}/{total} in {elapsed:.0f}s.")
    if failures:
        print(f"\n{len(failures)} FAILED — retry by re-running the script:")
        for p, err in failures[:5]:
            print(f"  {p.photo_id[:40]} — {err}")
        if len(failures) > 5:
            print(f"  ... and {len(failures) - 5} more")

    print(f"\nManifest: {manifest_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
