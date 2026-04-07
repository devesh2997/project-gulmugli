"""
Ambient sound endpoints — start/stop ambient sounds, list available sounds.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import AmbientRequest, IntentResponse
from core.config import config
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.ambient")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/ambient", response_model=IntentResponse)
def ambient_action(
    req: AmbientRequest,
    assistant: dict = Depends(get_assistant),
):
    """Start or stop ambient sounds."""
    params = {"action": req.action}
    if req.sound is not None:
        params["sound"] = req.sound
    if req.volume is not None:
        params["volume"] = req.volume

    intent = Intent(name="ambient", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Ambient action failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/ambient/sounds")
def list_ambient_sounds():
    """List available ambient sounds from config."""
    return config.get("ambient", {}).get("sounds", {})
