"""
Music endpoints — play, control, search, now playing.

These are convenience wrappers over the intent system. Each endpoint
constructs an Intent and routes through handle_intent(), exactly like
handle_ui_action() does in ui/actions.py.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import (
    IntentResponse,
    MusicControlRequest,
    MusicPlayRequest,
    MusicSeekRequest,
    NowPlayingResponse,
)
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.music")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/music/play", response_model=IntentResponse)
def music_play(
    req: MusicPlayRequest,
    assistant: dict = Depends(get_assistant),
):
    """Search and play a song."""
    params = {"query": req.query}
    if req.with_video:
        params["with_video"] = True

    intent = Intent(name="music_play", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Music play failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/music/control", response_model=IntentResponse)
def music_control(
    req: MusicControlRequest,
    assistant: dict = Depends(get_assistant),
):
    """Pause, resume, stop, or skip."""
    intent = Intent(
        name="music_control",
        params={"action": req.action},
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Music control failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/music/seek", response_model=IntentResponse)
def music_seek(
    req: MusicSeekRequest,
    assistant: dict = Depends(get_assistant),
):
    """Seek to a position in the current track."""
    music = assistant.get("music")
    if not music or not hasattr(music, "seek"):
        return IntentResponse(ok=False, error="Music provider not available.")
    try:
        music.seek(req.position)
        # Update dashboard state — snapshot _now_playing to avoid race
        face_ui = assistant.get("face_ui")
        now_playing = getattr(face_ui, "_now_playing", None) if face_ui else None
        if face_ui and now_playing:
            now_playing["position"] = req.position
            face_ui.set_now_playing(now_playing)
        return IntentResponse(ok=True, response="")
    except Exception as e:
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/music/now-playing", response_model=NowPlayingResponse)
def now_playing(assistant: dict = Depends(get_assistant)):
    """Get current playback state."""
    face_ui = assistant.get("face_ui")
    # Snapshot to avoid TOCTOU — _now_playing could become None between check and use.
    data = getattr(face_ui, "_now_playing", None) if face_ui else None
    if not data:
        return NowPlayingResponse(playing=False)

    paused = getattr(face_ui, "_music_paused", False)
    return NowPlayingResponse(
        playing=True,
        paused=paused,
        title=data.get("title"),
        artist=data.get("artist"),
        album=data.get("album"),
        duration=data.get("duration"),
        position=data.get("position"),
        art_url=data.get("art_url"),
        video_id=data.get("video_id"),
    )
