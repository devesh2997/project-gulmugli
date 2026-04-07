"""
System endpoints — health check, status, time.

GET /api/status      — unauthenticated health check (for discovery)
GET /api/system/status — full system status (authenticated)
GET /api/system/time   — current time/date
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import HealthResponse, SystemStatusResponse, TimeResponse
from core.config import config
from core.personality import personality_manager

router = APIRouter()

# Track when the API started so we can report uptime.
_start_time = time.monotonic()


@router.get("/api/status", response_model=HealthResponse)
def health_check():
    """
    Unauthenticated health check.

    Used by mDNS discovery and the Flutter app's connection flow
    to verify the server is reachable before prompting for a token.
    """
    name = config.get("assistant", {}).get("name", "Jarvis")
    return HealthResponse(status="ok", name=name)


@router.get(
    "/api/system/status",
    response_model=SystemStatusResponse,
    dependencies=[Depends(verify_token)],
)
def system_status(assistant: dict = Depends(get_assistant)):
    """Full system status — requires authentication."""
    name = config.get("assistant", {}).get("name", "Jarvis")

    face_ui = assistant.get("face_ui")
    # Snapshot FaceUI attributes to avoid TOCTOU races — these could change
    # mid-access from FaceUI's thread.
    state = getattr(face_ui, "_current_state", "unknown") if face_ui else "unknown"
    sleep_mode = getattr(face_ui, "_sleep_mode", False) if face_ui else False
    volume = getattr(face_ui, "_volume", 50) if face_ui else 50
    now_playing = getattr(face_ui, "_now_playing", None) if face_ui else None
    music_paused = getattr(face_ui, "_music_paused", False) if face_ui else False

    active = personality_manager.active
    music_playing = bool(now_playing) and not music_paused

    return SystemStatusResponse(
        name=name,
        state=state,
        personality=active.id,
        personality_display_name=active.display_name,
        sleep_mode=sleep_mode,
        music_playing=music_playing,
        volume=volume,
        uptime_seconds=round(time.monotonic() - _start_time, 1),
    )


@router.get(
    "/api/system/time",
    response_model=TimeResponse,
    dependencies=[Depends(verify_token)],
)
def system_time():
    """Current time, date, day of week, and timezone."""
    now = datetime.now()
    tz = datetime.now(timezone.utc).astimezone().tzname() or "UTC"
    return TimeResponse(
        time=now.strftime("%H:%M:%S"),
        date=now.strftime("%Y-%m-%d"),
        day=now.strftime("%A"),
        timezone=tz,
    )
