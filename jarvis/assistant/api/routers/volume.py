"""
Volume endpoints — get/set system volume.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, VolumeRequest, VolumeResponse
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.volume")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/volume", response_model=IntentResponse)
def set_volume(
    req: VolumeRequest,
    assistant: dict = Depends(get_assistant),
):
    """Set system volume (0-100)."""
    intent = Intent(
        name="volume",
        params={"level": str(req.level)},
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Volume set failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/volume", response_model=VolumeResponse)
def get_volume(assistant: dict = Depends(get_assistant)):
    """Get current volume level."""
    face_ui = assistant.get("face_ui")
    level = getattr(face_ui, "_volume", 50) if face_ui else 50
    return VolumeResponse(level=level)
