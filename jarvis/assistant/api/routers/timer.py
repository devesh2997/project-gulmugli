"""
Timer endpoints — set/cancel timers, list active timers.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, TimerRequest
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.timer")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/timer", response_model=IntentResponse)
def timer_action(
    req: TimerRequest,
    assistant: dict = Depends(get_assistant),
):
    """Set or cancel a timer."""
    params = {"action": req.action}
    if req.duration is not None:
        params["duration"] = req.duration
    if req.label is not None:
        params["label"] = req.label
    if req.cancel_id is not None:
        params["cancel_type"] = req.cancel_id

    intent = Intent(name="timer", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Timer action failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/timers")
def list_timers(assistant: dict = Depends(get_assistant)):
    """List all active timers."""
    face_ui = assistant.get("face_ui")
    timers = getattr(face_ui, "_active_timers", None) if face_ui else None
    if not timers:
        return []
    # Return a snapshot (shallow copy) to avoid races with FaceUI's thread.
    return list(timers)
