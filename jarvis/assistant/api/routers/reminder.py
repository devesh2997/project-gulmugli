"""
Reminder endpoints — set/cancel reminders, list active reminders.
"""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, ReminderRequest
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.reminder")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/reminder", response_model=IntentResponse)
def reminder_action(
    req: ReminderRequest,
    assistant: dict = Depends(get_assistant),
):
    """Set or cancel a reminder."""
    params = {"action": req.action}
    if req.text is not None:
        params["text"] = req.text
    if req.time is not None:
        params["time"] = req.time
    if req.cancel_id is not None:
        params["cancel_id"] = req.cancel_id

    intent = Intent(name="reminder", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Reminder action failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/reminders")
def list_reminders(assistant: dict = Depends(get_assistant)):
    """List all active reminders."""
    face_ui = assistant.get("face_ui")
    reminders = getattr(face_ui, "_reminders", None) if face_ui else None
    if not reminders:
        return []
    # Return a snapshot (shallow copy) to avoid races with FaceUI's thread.
    return list(reminders)


@router.delete("/api/reminder/{reminder_id}", response_model=IntentResponse)
def cancel_reminder(
    reminder_id: str,
    assistant: dict = Depends(get_assistant),
):
    """Cancel a specific reminder by ID."""
    reminder_manager = assistant.get("reminder_manager")
    if not reminder_manager:
        return IntentResponse(ok=False, error="Reminder manager not available.")

    try:
        reminder_manager.cancel(reminder_id)
        # Update face_ui state — atomic replacement instead of in-place mutation
        # to avoid races with FaceUI's thread reading the list.
        face_ui = assistant.get("face_ui")
        if face_ui and hasattr(face_ui, "_reminders"):
            current = getattr(face_ui, "_reminders", [])
            face_ui._reminders = [
                r for r in current
                if r.get("id") != reminder_id
            ]
        return IntentResponse(ok=True, response=f"Reminder {reminder_id} cancelled.")
    except Exception as e:
        log.warning("Reminder cancel failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
