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

Caption schema (current)
------------------------

Each YAML entry may carry:

  - file:            (required) filename in the photos dir
  - caption_manual:  user-typed override; wins over caption_ai. Special
                     sentinel `<NO_CAPTION>` forces an empty caption
                     (intentionally silent slide).
  - caption_ai:      AI-suggested caption; used when caption_manual is blank.
  - caption:         LEGACY field. Used only when both _manual and _ai
                     are missing. Kept for back-compat with older YAMLs.
  - keep:            (bool) curator opted this photo IN
  - highlight:       (bool) curator wants this slide to linger longer
  - skip:            (bool) curator opted this photo OUT — never include
  - order:           (int) explicit sort order; lower = earlier

Curation modes
--------------

`load_photos(..., only_curated=False)` (default, back-compat):
  - skip:true entries are excluded
  - everything else on disk OR in YAML is included
  - undecided entries (no keep/highlight/skip) get logged at debug

`load_photos(..., only_curated=True)` (production slideshow):
  - skip:true → excluded
  - keep:true OR highlight:true → included
  - undecided → excluded
  - photos on disk but NOT in YAML at all → still included with empty
    caption (the drop-and-go affordance survives even in curated mode;
    if you really want a closed slideshow, don't drop files in)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from core.logger import get_logger

log = get_logger("providers.yaadein")

# Image extensions we recognize. Lowercased — `.suffix.lower()` is what
# we compare against. JPEG is the dominant format for phone photos;
# PNG covers screenshots; HEIC is intentionally absent because browser
# `<img src>` can't render it without a server-side transcode and
# we don't want the user to discover that mid-slideshow.
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Sentinel: a curator typed this into caption_manual when they want a
# slide to display silently (no caption overlay). Empty-string in
# caption_manual is treated as "not filled in yet, fall back to AI."
_NO_CAPTION_SENTINEL = "<NO_CAPTION>"

CaptionSource = Literal["manual", "ai", "legacy", "none"]


@dataclass(frozen=True)
class YaadeinPhoto:
    """One photo + caption + sort hint, as returned by `load_photos`."""
    file: str                       # filename only — no path components
    caption: str                    # the EFFECTIVE caption the slideshow shows
    order: Optional[int]            # explicit sort order, or None for filename-sorted
    caption_source: CaptionSource = "none"  # which field the caption came from
    highlight: bool = False         # curator wants this slide to linger


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


def _resolve_caption(entry: dict) -> tuple[str, CaptionSource]:
    """
    Pick the effective caption string from a YAML entry, with the
    precedence: caption_manual > caption_ai > caption (legacy).

    Returns (caption_text, source). `caption_manual == "<NO_CAPTION>"`
    is a sentinel for "intentionally silent" → returns ("", "manual").
    """
    manual_raw = entry.get("caption_manual")
    manual = manual_raw.strip() if isinstance(manual_raw, str) else ""

    if manual == _NO_CAPTION_SENTINEL:
        return ("", "manual")
    if manual:
        return (manual, "manual")

    ai = entry.get("caption_ai")
    if isinstance(ai, str) and ai.strip():
        return (ai, "ai")

    legacy = entry.get("caption")
    if isinstance(legacy, str) and legacy:
        return (legacy, "legacy")

    return ("", "none")


def load_photos(photos_dir: Path, *, only_curated: bool = False) -> YaadeinPack:
    """
    Load `<photos_dir>/captions.yaml` (if present) and merge with the
    list of image files actually on disk.

    Returns a YaadeinPack with photos sorted (explicit `order` first,
    then filename) and `music` if specified at the top level of
    captions.yaml.

    `only_curated`:
      - False (default): legacy/permissive behavior. Include everything
        not explicitly `skip:true`. Undecided entries are kept with
        empty captions so older YAMLs that pre-date the keep/highlight
        flags still light up the slideshow.
      - True: production-slideshow behavior. Include only entries with
        `keep:true` or `highlight:true`. Undecided entries are excluded.
        Files on disk that have no YAML entry at all are still auto-
        included with empty captions (drop-and-go affordance).

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
    #
    # Two locations are searched, in this priority:
    #   1. `<photos_dir>/../captions.yaml`  (new schema, lives in media/)
    #   2. `<photos_dir>/captions.yaml`     (legacy, lived inside photos/)
    # The migration moved the YAML one level up so the photos directory
    # stays purely image files. We prefer the new location when both
    # exist (the legacy file is then a leftover stub).
    sibling_yaml = photos_dir.parent / "captions.yaml"
    in_dir_yaml = photos_dir / "captions.yaml"
    if sibling_yaml.is_file():
        captions_yaml = sibling_yaml
    else:
        captions_yaml = in_dir_yaml
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

    n_skipped = 0
    n_undecided = 0

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

        keep = entry.get("keep") is True
        highlight = entry.get("highlight") is True
        skip = entry.get("skip") is True

        # `skip` is a hard NO regardless of mode — once the curator has
        # said "this photo doesn't belong in the slideshow", we honor it.
        if skip:
            seen.add(file)  # mark seen so it doesn't get auto-re-included
            n_skipped += 1
            continue

        if only_curated:
            # Production mode: ONLY include explicit keep/highlight.
            if not (keep or highlight):
                seen.add(file)
                n_undecided += 1
                continue
        else:
            # Legacy mode: include everything except `skip`. Log undecided
            # entries so curators have a debug breadcrumb showing which
            # photos are still waiting on a keep/skip decision.
            if not (keep or highlight):
                log.debug(
                    "captions.yaml entry %s is undecided (no keep/skip/highlight) — "
                    "including with permissive defaults",
                    file,
                )

        seen.add(file)

        caption, caption_source = _resolve_caption(entry)

        order = entry.get("order")
        if not isinstance(order, int):
            order = None

        photos.append(YaadeinPhoto(
            file=file,
            caption=caption,
            order=order,
            caption_source=caption_source,
            highlight=highlight,
        ))

    # Auto-include un-mentioned photos with empty caption. This applies
    # in BOTH modes: a fresh drop of files in the photos dir shouldn't
    # require a YAML edit to surface, even in curated mode. The cost is
    # tiny (empty captions) and the alternative (silent invisible files)
    # is a worse failure mode for a one-shot birthday gift.
    for file in sorted(on_disk - seen):
        photos.append(YaadeinPhoto(
            file=file,
            caption="",
            order=None,
            caption_source="none",
            highlight=False,
        ))

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
        "Yaadein loaded %d photo(s) from %s%s%s%s",
        len(photos),
        photos_dir,
        f" (music: {music})" if music else "",
        f" [curated mode, {n_undecided} undecided excluded]" if only_curated else "",
        f" [{n_skipped} skip:true excluded]" if n_skipped else "",
    )
    return YaadeinPack(photos=photos, music=music, photos_dir=photos_dir)
