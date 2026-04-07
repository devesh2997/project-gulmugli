"""
Knowledge search endpoint — web search through the intent system.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, KnowledgeSearchRequest
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.knowledge")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/knowledge/search", response_model=IntentResponse)
def knowledge_search(
    req: KnowledgeSearchRequest,
    assistant: dict = Depends(get_assistant),
):
    """Search the web for current information."""
    intent = Intent(
        name="knowledge_search",
        params={"query": req.query},
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Knowledge search failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
