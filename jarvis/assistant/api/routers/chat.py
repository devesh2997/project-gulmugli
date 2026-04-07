"""
Chat endpoint — send text through the full pipeline.

POST /api/chat runs the full classify → execute → respond pipeline,
the same path as typing text in the dashboard or speaking to the assistant.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import ChatRequest, IntentResponse
from core.logger import get_logger
from core.pipeline import process_input

log = get_logger("api.chat")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/chat", response_model=IntentResponse)
def chat(
    req: ChatRequest,
    assistant: dict = Depends(get_assistant),
):
    """
    Send text through the full assistant pipeline.

    This is the equivalent of typing in the dashboard's text input.
    The text goes through LLM classification → intent execution → response.
    Returns the spoken response text.

    Note: This is synchronous and can take several seconds (LLM inference).
    For fire-and-forget, use the WebSocket text_input action instead.
    """
    try:
        # process_input returns (response_text, was_interrupted) tuple
        result = process_input(assistant, req.text)
        if isinstance(result, tuple):
            response = result[0] or ""
        else:
            response = result or ""
        return IntentResponse(ok=True, response=response)
    except Exception as e:
        log.warning("Chat processing failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
