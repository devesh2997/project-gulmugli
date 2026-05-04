"""
Event endpoints — exposes the event manager's state to the dashboard
and the Flutter companion app.

## Endpoints

  GET /api/events/current
      Unauthenticated. Returns the active event for today, or null.
      Polled by the dashboard's `useEventTheme` hook every 60 seconds
      so the UI flips palette automatically when an event becomes
      active. Unauth on purpose — the data is non-sensitive (just
      "today is birthday true/false") and the dashboard is a kiosk.

  GET /api/events/{pack_id}/theme/tokens
      Unauthenticated. Streams the pack's `theme/tokens.json` file as
      JSON. The dashboard fetches this when an event becomes active and
      merges the tokens into its design-token tree.

  GET /api/events/{pack_id}/theme/avatar
      Unauthenticated. Streams the pack's `theme/avatar.json` (avatar
      accessories — party hat, etc.) Same purpose as theme/tokens.

  POST /api/events/trigger
      Authenticated. The Flutter app's "🎁 Launch surprise" button hits
      this. Body: {} (the active event is implied — we trigger whatever
      is active today). Returns 409 if no event is active today.
      Voice intent (Phase 0.5a) goes through a different path — directly
      calls event_manager rather than re-entering the API.

## Why is this NOT in routers/system.py?

System endpoints are about the assistant itself (uptime, current
personality, time). Events are a domain of their own — themes, packs,
triggers, content. Keeping them separate avoids one big router file
and gives us room to add more event-related endpoints (list_packs,
seed_memory, etc.) without bloating system.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from api.auth import verify_token
from core.event_manager import ActiveEvent, get_event_manager
from core.logger import get_logger

log = get_logger("api.events")

router = APIRouter(prefix="/api/events", tags=["events"])


# ── /api/events/current ──────────────────────────────────────────────


def _serialize_active(active: ActiveEvent) -> dict:
    """
    Convert ActiveEvent into the JSON shape the dashboard consumes.

    `theme_url` and `avatar_url` point at the static-content endpoints
    below so the client doesn't need to know the on-disk layout.
    """
    pack = active.pack
    return {
        "event_id": active.pack_id,
        "display_name": pack.display_name,
        "days_until": active.days_until,
        "is_today": active.is_today,
        "is_eve": active.is_eve,
        "is_aftermath": active.is_aftermath,
        "features": pack.features,
        "trigger": pack.trigger_config,
        # Phase 1.2 will replace this with persisted trigger state.
        # For now we always report false — the dashboard treats this
        # as "the date matches but nobody has fired the surprise yet."
        "is_triggered": False,
        "theme_url": f"/api/events/{active.pack_id}/theme/tokens",
        "avatar_url": f"/api/events/{active.pack_id}/theme/avatar",
    }


@router.get("/current")
def get_current_event() -> Any:
    """
    Return today's active event, or null. Unauthenticated on purpose —
    the dashboard polls this without a token.
    """
    em = get_event_manager()
    active = em.current()
    if active is None:
        return JSONResponse(content=None)
    return _serialize_active(active)


# ── /api/events/{pack_id}/theme/* ─────────────────────────────────────


def _resolve_pack_dir(pack_id: str) -> Path:
    """
    Look up the pack's on-disk directory. Returns 404 if the id doesn't
    match any loaded pack — never lets the caller traverse the filesystem
    via path injection (we look up via the registry, not by path concat).
    """
    em = get_event_manager()
    for p in em.list_packs():
        if p.pack_id == pack_id:
            return p.pack_dir
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"event pack '{pack_id}' not found")


def _serve_theme_file(pack_id: str, filename: str) -> Any:
    """
    Common helper: read a file from `<pack>/theme/<filename>` and return
    its JSON contents. 404s cleanly if the pack or file doesn't exist;
    500s with a logged error if the file is malformed JSON.
    """
    pack_dir = _resolve_pack_dir(pack_id)
    theme_file = pack_dir / "theme" / filename
    if not theme_file.is_file():
        # Not a 500 — it's reasonable for a pack to omit theme/avatar.json
        # if it doesn't customize the avatar. Return an empty object so
        # the client can merge unconditionally.
        return JSONResponse(content={})
    try:
        with theme_file.open() as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except json.JSONDecodeError as e:
        log.error("malformed theme file %s: %s", theme_file, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"theme file is not valid JSON: {filename}",
        )


@router.get("/{pack_id}/theme/tokens")
def get_theme_tokens(pack_id: str) -> Any:
    """Stream `<pack>/theme/tokens.json`. Empty object if missing."""
    return _serve_theme_file(pack_id, "tokens.json")


@router.get("/{pack_id}/theme/avatar")
def get_theme_avatar(pack_id: str) -> Any:
    """Stream `<pack>/theme/avatar.json`. Empty object if missing."""
    return _serve_theme_file(pack_id, "avatar.json")


# ── POST /api/events/trigger ─────────────────────────────────────────

# In-memory trigger state. Phase 1.2 will replace this with a persisted
# JSON file (so a server restart on the day-of doesn't lose the trigger).
# For Phase 0 we just need the API surface so the dashboard hook and the
# Flutter button can wire up; the actual launch sequence is Phase 1.
_triggered_packs: set[str] = set()


@router.post("/trigger", dependencies=[Depends(verify_token)])
def trigger_event() -> Any:
    """
    Manually fire the active event's launch sequence.

    Idempotent in spirit — calling twice on the same active event just
    re-runs the trigger (the launch sequence handler decides whether to
    actually re-run or to no-op).

    409 if no event is active today. The Flutter app should hide the
    button when `is_today=false`, but we double-check server-side.
    """
    em = get_event_manager()
    active = em.current()
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no event is active today",
        )

    _triggered_packs.add(active.pack_id)
    log.info("event triggered: pack_id=%s", active.pack_id)

    # Phase 1.1 will plug in the actual intro_runner here. For now we
    # just log + acknowledge — the dashboard's `is_triggered` poll will
    # flip true once we wire that up properly.
    # TODO(roadmap 1.1): invoke intro_runner.run(active.pack_dir / first_year_only.intro_script)

    return {
        "ok": True,
        "event_id": active.pack_id,
        "message": "trigger recorded; launch sequence engine wires in Phase 1.1",
    }
