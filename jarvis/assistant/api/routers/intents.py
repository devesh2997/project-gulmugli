"""
Unified intent endpoint — submit any intent directly.

POST /api/intents — bypasses LLM classification, constructs an Intent
object and routes through handle_intent(). This is the low-level API
that the convenience endpoints (music, lights, etc.) are sugar over.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentRequest, IntentResponse
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.intents")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/intents", response_model=IntentResponse)
def submit_intent(
    req: IntentRequest,
    assistant: dict = Depends(get_assistant),
):
    """
    Submit a raw intent for execution.

    This skips LLM classification — the intent name and params are
    provided directly. Useful for the app's dedicated control buttons
    (play, pause, lights on, etc.) where classification is unnecessary.
    """
    intent = Intent(
        name=req.name,
        params=req.params,
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Intent execution failed: %s — %s", req.name, e)
        return IntentResponse(ok=False, error=str(e))
