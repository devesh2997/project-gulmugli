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
from core.trigger_state import get_trigger_store

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
    triggered = get_trigger_store().is_triggered(active.pack_id)
    return {
        "event_id": active.pack_id,
        "display_name": pack.display_name,
        "days_until": active.days_until,
        "is_today": active.is_today,
        "is_eve": active.is_eve,
        "is_aftermath": active.is_aftermath,
        "features": pack.features,
        "trigger": pack.trigger_config,
        # Persisted across server restart via core.trigger_state.
        "is_triggered": triggered,
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

@router.post("/trigger", dependencies=[Depends(verify_token)])
def trigger_event() -> Any:
    """
    Manually fire the active event's launch sequence.

    Two side effects:
      1. Persist `is_triggered = true` for this pack/year via
         core.trigger_state. Survives a Jetson restart on the day-of.
      2. Run the intro script if the pack defines one (best-effort —
         the runner won't crash the API if a step fails).

    Idempotent: a re-trigger marks the persisted flag (no-op if already
    set) and re-runs the intro script. Some packs may want a different
    re-trigger behavior (e.g., skip the script the second time); that's
    handled inside the intro runner / pack logic, not here.

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

    store = get_trigger_store()
    was_fresh = store.mark_triggered(active.pack_id)
    log.info(
        "event triggered: pack_id=%s fresh=%s",
        active.pack_id, was_fresh,
    )

    # Run the intro script if the pack has one. Don't block the API
    # response on the script's full duration — kick it off in a daemon
    # thread and return immediately. The script is best-effort and
    # logs its own progress.
    fy = active.pack.raw.get("first_year_only") or {}
    script_rel = fy.get("intro_script") if isinstance(fy, dict) else None
    if isinstance(script_rel, str) and script_rel:
        from threading import Thread
        from core.intro_runner import IntroContext, IntroRunner

        def _run_intro():
            try:
                # The API-layer trigger doesn't have access to the live
                # voice_router/face_ui here. They live on app.state.assistant
                # — the FastAPI startup wiring stores them. Pull from request
                # state if available; otherwise the runner gracefully no-ops
                # the speak/dashboard steps.
                # TODO: pass assistant context through to the trigger endpoint
                #       so intro_runner has voice_router + face_ui.
                ctx = IntroContext(
                    pack_dir=active.pack_dir,
                    voice_router=None,
                    face_ui=None,
                    template_vars={
                        "event_name": active.pack.display_name,
                        "pack_id": active.pack_id,
                    },
                )
                IntroRunner(active.pack_dir / script_rel).run(ctx)
            except Exception as e:
                log.warning("trigger: intro_runner failed: %s", e)

        Thread(target=_run_intro, name="intro-runner", daemon=True).start()

    return {
        "ok": True,
        "event_id": active.pack_id,
        "is_triggered": True,
        "freshly_triggered": was_fresh,
    }


@router.get("/health")
def events_health() -> Any:
    """
    Diagnostic snapshot of the event-pack subsystem. Unauthenticated
    so the dashboard / dev can introspect without a token. Surfaces:

      - All loaded packs (id + display_name + features count)
      - The currently-active pack (or null)
      - Per-pack triggered state for the current year

    Used by the dashboard's "what's wired up" debug panel and by
    Phase 6.1 dress-rehearsal scripts to verify state at a glance.
    """
    from datetime import datetime
    em = get_event_manager()
    store = get_trigger_store()
    year = datetime.now().year

    packs_summary = []
    for p in em.list_packs():
        packs_summary.append({
            "pack_id": p.pack_id,
            "display_name": p.display_name,
            "feature_count": len(p.features),
            "auto_midnight": bool(p.trigger_config.get("auto_midnight", False)),
            "is_triggered_this_year": store.is_triggered(p.pack_id, year=year),
        })

    active = em.current()
    active_summary = None
    if active is not None:
        active_summary = {
            "pack_id": active.pack_id,
            "is_today": active.is_today,
            "is_eve": active.is_eve,
            "is_aftermath": active.is_aftermath,
            "days_until": active.days_until,
        }

    return {
        "year": year,
        "active": active_summary,
        "packs": packs_summary,
    }


@router.post("/{pack_id}/reset", dependencies=[Depends(verify_token)])
def reset_event_trigger(pack_id: str) -> Any:
    """
    Clear the persisted trigger state for a pack. Useful for testing
    and for a hypothetical "reset to pre-launch" admin action. Returns
    200 with `was_set` indicating whether state actually changed.
    """
    store = get_trigger_store()
    was_set = store.reset(pack_id)
    log.info("trigger reset: pack_id=%s was_set=%s", pack_id, was_set)
    return {"ok": True, "pack_id": pack_id, "was_set": was_set}
