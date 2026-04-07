"""
Light control endpoints — on/off, color, brightness, scenes, device listing.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import (
    IntentResponse,
    LightControlRequest,
    LightDeviceResponse,
    LightStateResponse,
)
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.lights")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/lights/control", response_model=IntentResponse)
def light_control(
    req: LightControlRequest,
    assistant: dict = Depends(get_assistant),
):
    """Control lights — on, off, color, brightness, or scene."""
    params = {"action": req.action}
    if req.value is not None:
        params["value"] = req.value
    if req.device is not None:
        params["device_name"] = req.device

    intent = Intent(name="light_control", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Light control failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/lights/state", response_model=LightStateResponse)
def light_state(assistant: dict = Depends(get_assistant)):
    """Get current light state."""
    face_ui = assistant.get("face_ui")
    # Snapshot to avoid TOCTOU — _lights could become None between check and use.
    lights_data = getattr(face_ui, "_lights", None) if face_ui else None
    if lights_data:
        try:
            return LightStateResponse(**lights_data)
        except Exception:
            # Unexpected keys in _lights dict — fall through to default
            pass
    return LightStateResponse(on=False)


@router.get("/api/lights/devices", response_model=list[LightDeviceResponse])
def light_devices(assistant: dict = Depends(get_assistant)):
    """List all configured light devices."""
    lights = assistant.get("lights")
    if not lights:
        return []
    try:
        devices = lights.list_devices()
        return [LightDeviceResponse(**d) for d in devices]
    except Exception as e:
        log.warning("Failed to list light devices: %s", e)
        return []
