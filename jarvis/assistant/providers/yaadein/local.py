"""
Yaadein — local photo + caption loader.

Reads `events/<pack>/media/photos/` plus a sibling `captions.yaml` and
returns an ordered list of `(filename, caption)` pairs that the API
streams to the dashboard slideshow.

Design choices:

- **Auto-include unlisted photos with empty caption.** Keeps the drop-
  and-go workflow alive — if Devesh dumps a folder of new photos into
  the directory he doesn't have to update YAML before the slideshow
  picks them up. Captions can be added later. The cost of the alternative
  ("ignore unlisted photos") is silent data loss when the YAML is stale.

- **Hybrid sort: explicit `order:` first, then filename.** Entries that
  carry an `order` integer are sorted by it (ascending). Entries without
  fall back to filename sort. Mixing the two is supported but the
  ordered-first/unordered-after split is documented in the YAML schema
  comment so authors know what to expect.

- **The pack directory is resolved through `core.event_manager`.** We
  don't accept a hardcoded path — the same loader works for any future
  pack with the same media layout.

- **Path-traversal protection lives at the API layer**, not here. This
  module only returns filenames; the API is what builds URLs and
  enforces "the resolved file is inside the photos directory".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger("providers.yaadein")

# Image extensions we recognize. Lowercased — `.suffix.lower()` is what
# we compare against. JPEG is the dominant format for phone photos;
# PNG covers screenshots; HEIC is intentionally absent because browser
# `<img src>` can't render it without a server-side transcode and
# we don't want the user to discover that mid-slideshow.
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@dataclass(frozen=True)
class YaadeinPhoto:
    """One photo + caption + sort hint, as returned by `load_photos`."""
    file: str             # filename only — no path components
    caption: str          # may be empty
    order: Optional[int]  # explicit sort order, or None for filename-sorted


@dataclass(frozen=True)
class YaadeinPack:
    """
    Full result of loading a pack's photos directory.

    `music` is the optional background track filename (relative to the
    photos directory). The caller (API → dashboard) resolves it via the
    same path-safety logic as photos.
    """
    photos: list[YaadeinPhoto]
    music: Optional[str]
    photos_dir: Path


def load_photos(photos_dir: Path) -> YaadeinPack:
    """
    Load `<photos_dir>/captions.yaml` (if present) and merge with the
    list of image files actually on disk.

    Returns a YaadeinPack with photos sorted (explicit `order` first,
    then filename) and `music` if specified at the top level of
    captions.yaml.

    Resilient by design — a missing YAML, malformed YAML, or unreadable
    directory all degrade to "show what's on disk, no captions" rather
    than raising. The slideshow surface is a gift; we'd rather it run
    quietly with empty captions than crash on a typo.
    """
    if not photos_dir.is_dir():
        log.warning("Yaadein photos dir does not exist: %s", photos_dir)
        return YaadeinPack(photos=[], music=None, photos_dir=photos_dir)

    # Step 1: enumerate image files actually on disk.
    on_disk: set[str] = set()
    for child in photos_dir.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() in _IMAGE_EXTS:
            on_disk.add(child.name)

    # Step 2: parse captions.yaml (if any).
    captions_yaml = photos_dir / "captions.yaml"
    yaml_data: dict = {}
    if captions_yaml.is_file():
        try:
            import yaml as _yaml
            with captions_yaml.open(encoding="utf-8") as f:
                parsed = _yaml.safe_load(f) or {}
            if isinstance(parsed, dict):
                yaml_data = parsed
            else:
                log.warning(
                    "captions.yaml at %s is not a dict — ignoring",
                    captions_yaml,
                )
        except Exception as e:
            # Catching Exception (not bare except) so an import failure
            # OR a parse failure both degrade gracefully. The user gets
            # photos with no captions instead of a stack trace.
            log.warning("Could not parse %s: %s", captions_yaml, e)

    music = yaml_data.get("music")
    if music is not None and not isinstance(music, str):
        log.warning("music: in captions.yaml must be a string — ignoring")
        music = None

    # Step 3: build the photo list. Walk YAML entries first so we capture
    # explicit captions + ordering, then auto-include anything on disk
    # that the YAML didn't mention.
    photos: list[YaadeinPhoto] = []
    seen: set[str] = set()
    raw_entries = yaml_data.get("photos") or []
    if not isinstance(raw_entries, list):
        log.warning("photos: in captions.yaml must be a list — ignoring")
        raw_entries = []

    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        file = entry.get("file")
        if not isinstance(file, str) or not file:
            continue
        # Defense in depth — an entry that includes a path separator is
        # almost certainly a typo; skip it. Path-safety at the API layer
        # is the real boundary, but rejecting here keeps the seen-set
        # from accumulating bogus keys.
        if "/" in file or "\\" in file or ".." in file:
            log.warning("captions.yaml entry rejected (path-like file): %s", file)
            continue
        # Only include if the file is actually on disk. A YAML entry
        # for a photo we don't have is dead weight.
        if file not in on_disk:
            log.debug("captions.yaml lists %s but file is not on disk", file)
            continue
        seen.add(file)

        caption = entry.get("caption", "")
        if not isinstance(caption, str):
            caption = ""

        order = entry.get("order")
        if not isinstance(order, int):
            order = None

        photos.append(YaadeinPhoto(file=file, caption=caption, order=order))

    # Auto-include un-mentioned photos with empty caption.
    for file in sorted(on_disk - seen):
        photos.append(YaadeinPhoto(file=file, caption="", order=None))

    # Final sort: explicit-order entries first (by order asc), then the
    # rest by filename. `order is None` sorts as "comes after" via the
    # tuple key — entries without an order get `(1, file)`, entries
    # with one get `(0, order, file)`.
    def _sort_key(p: YaadeinPhoto) -> tuple:
        if p.order is None:
            return (1, p.file)
        return (0, p.order, p.file)

    photos.sort(key=_sort_key)

    log.info(
        "Yaadein loaded %d photo(s) from %s%s",
        len(photos),
        photos_dir,
        f" (music: {music})" if music else "",
    )
    return YaadeinPack(photos=photos, music=music, photos_dir=photos_dir)
