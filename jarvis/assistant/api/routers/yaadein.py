"""
Yaadein API — list + serve memory-slideshow photos.

Endpoints
---------

  GET /api/yaadein/list
      Auth-protected. Returns the active event's photo list:

        {
          "pack_id": "astha-birthday",
          "display_name": "Astha's Birthday",
          "music_url": "/api/yaadein/music"  | null,
          "photos": [
            {"photo_url": "/api/yaadein/photo/001.jpg",
             "caption":   "Yahaan se sab shuru hua 😇"},
            ...
          ]
        }

      404s if there's no active event today (i.e., the loader has no
      pack to point at). The dashboard reads this once at slideshow
      start; auth-on means a same-WiFi peer can't enumerate photos.

  GET /api/yaadein/photo/{filename}
      Auth-protected. Streams the photo file as image bytes with a
      content-type guess. Path-traversal-safe — `..`, absolute paths,
      and any filename whose resolved path escapes the photos directory
      get a 400. Filenames not on disk get a 404.

  GET /api/yaadein/music
      Auth-protected. Streams the optional background track if
      captions.yaml had a `music:` field. 404 otherwise. Implemented
      as a separate URL (vs embedding in the list response) so the
      browser's HTMLAudioElement can stream it directly with the same
      auth bearer.

Path-traversal hardening
------------------------

The hard rule: a request for `/api/yaadein/photo/<X>` MUST end up
serving a file whose absolute, resolved path is *strictly* inside the
pack's photos directory. The defense is layered:

  1. Strip path components — `urllib.parse` doesn't help here because
     FastAPI gives us the raw path segment. We reject anything that
     contains `..`, `/`, `\\`, or starts with a dot-dot.
  2. Resolve via `Path(photos_dir / filename).resolve()`. This
     normalizes `.` / `..` references and follows symlinks.
  3. Compare the resolved path against `photos_dir.resolve()` using
     `is_relative_to` (Python 3.9+) — if the resolved file isn't
     beneath the resolved root, reject with 400.

Three checks because each catches a class the others miss:
  - String check rejects obvious junk fast (no FS calls).
  - resolve() handles `..` and symlinks.
  - is_relative_to is the final boundary in case resolve() returns a
    path that bypasses the prefix string (e.g., `/foo` vs `/foobar`).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from api.auth import verify_token
from core.event_manager import ActiveEvent, get_event_manager
from core.logger import get_logger
from providers.yaadein.local import YaadeinPack, load_photos

log = get_logger("api.yaadein")

router = APIRouter(prefix="/api/yaadein", tags=["yaadein"])


# ── Helpers ──────────────────────────────────────────────────────────


def _active_pack_or_404() -> ActiveEvent:
    """
    Look up today's active event. 404 if none — the slideshow has no
    pack to stream from.

    Note: we don't cross-check that the pack's `features` list contains
    "yaadein" — every pack in this codebase that ships photos opts into
    the slideshow implicitly. If that ever changes, gate here.
    """
    em = get_event_manager()
    active = em.current()
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active event — yaadein slideshow has no pack",
        )
    return active


def _photos_dir_for(active: ActiveEvent) -> Path:
    """The conventional photos location inside a pack."""
    return active.pack_dir / "media" / "photos"


def _load_pack_or_empty(active: ActiveEvent) -> YaadeinPack:
    """Load the pack's photos via the provider, with logging on miss."""
    photos_dir = _photos_dir_for(active)
    return load_photos(photos_dir)


def _safe_resolve(photos_dir: Path, filename: str) -> Path:
    """
    Resolve a user-supplied filename to an absolute path under `photos_dir`,
    raising HTTPException(400) on any traversal attempt.

    See the module docstring for the layered-defense rationale.
    """
    # Layer 1: cheap string-level rejections.
    if not filename:
        raise HTTPException(status_code=400, detail="empty filename")
    if (
        ".." in filename
        or filename.startswith("/")
        or filename.startswith("\\")
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
    ):
        # The startswith(".") catches `.gitkeep` style hidden files too —
        # which is fine, we don't want to serve dotfiles even if they're
        # inside the directory.
        raise HTTPException(status_code=400, detail="invalid filename")

    # Layer 2 + 3: resolve and confirm containment.
    base = photos_dir.resolve()
    target = (photos_dir / filename).resolve()
    try:
        if not target.is_relative_to(base):
            raise HTTPException(status_code=400, detail="path escapes photos directory")
    except AttributeError:
        # Python < 3.9 fallback — the project targets 3.9+ but defensive
        # coding never hurts on a path-safety check.
        if not str(target).startswith(str(base) + "/") and str(target) != str(base):
            raise HTTPException(status_code=400, detail="path escapes photos directory")

    return target


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/list", dependencies=[Depends(verify_token)])
def list_photos() -> Any:
    """
    Return the slideshow manifest for the active event. See module
    docstring for the response shape.
    """
    active = _active_pack_or_404()
    pack = _load_pack_or_empty(active)

    photos_payload = [
        {
            "photo_url": f"/api/yaadein/photo/{p.file}",
            "caption": p.caption,
        }
        for p in pack.photos
    ]

    body = {
        "pack_id": active.pack_id,
        "display_name": active.pack.display_name,
        # Music URL only emitted when the pack actually has one. The
        # frontend treats `null` as "no background music" without a
        # second round-trip.
        "music_url": "/api/yaadein/music" if pack.music else None,
        "photos": photos_payload,
    }
    return JSONResponse(content=body)


@router.get("/photo/{filename}", dependencies=[Depends(verify_token)])
def get_photo(filename: str) -> Any:
    """
    Serve a photo by filename. Path-traversal-safe (see module docstring).
    """
    active = _active_pack_or_404()
    photos_dir = _photos_dir_for(active)

    target = _safe_resolve(photos_dir, filename)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="photo not found")

    # FileResponse handles streaming + range requests automatically.
    # We pass an explicit media_type so browsers don't have to guess.
    media_type, _ = mimetypes.guess_type(str(target))
    if not media_type:
        media_type = "application/octet-stream"
    return FileResponse(path=str(target), media_type=media_type)


@router.get("/music", dependencies=[Depends(verify_token)])
def get_music() -> Any:
    """
    Serve the slideshow's background music file, if any. Same path-
    safety rules as photos.
    """
    active = _active_pack_or_404()
    pack = _load_pack_or_empty(active)
    if not pack.music:
        raise HTTPException(status_code=404, detail="no slideshow music configured")

    photos_dir = _photos_dir_for(active)
    target = _safe_resolve(photos_dir, pack.music)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="music file not found on disk")

    media_type, _ = mimetypes.guess_type(str(target))
    if not media_type:
        media_type = "audio/mpeg"
    return FileResponse(path=str(target), media_type=media_type)


# Optional helper exposed for tests (unauthenticated function — auth
# enforcement is per-route via Depends, not at module scope).
__all__ = ["router"]
