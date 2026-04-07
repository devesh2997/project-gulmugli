"""
Story mode endpoint — start, continue, or stop interactive stories.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, StoryRequest
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.story")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/story", response_model=IntentResponse)
def story_action(
    req: StoryRequest,
    assistant: dict = Depends(get_assistant),
):
    """Control story mode — start, continue, or stop."""
    params = {"action": req.action}
    if req.genre is not None:
        params["genre"] = req.genre
    if req.topic is not None:
        params["topic"] = req.topic

    intent = Intent(name="story", params=params, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Story action failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
