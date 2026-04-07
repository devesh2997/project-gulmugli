"""
Quiz endpoints — start, answer, hint, quit, score.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import IntentResponse, QuizAnswerRequest, QuizStartRequest
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger

log = get_logger("api.quiz")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/api/quiz/start", response_model=IntentResponse)
def quiz_start(
    req: QuizStartRequest,
    assistant: dict = Depends(get_assistant),
):
    """Start a new quiz session."""
    intent = Intent(
        name="quiz",
        params={
            "action": "start",
            "category": req.category,
            "difficulty": req.difficulty,
            "num_questions": req.num_questions,
        },
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Quiz start failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/quiz/answer", response_model=IntentResponse)
def quiz_answer(
    req: QuizAnswerRequest,
    assistant: dict = Depends(get_assistant),
):
    """Submit an answer to the current quiz question."""
    intent = Intent(
        name="quiz",
        params={"action": "answer", "answer": req.answer},
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Quiz answer failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/quiz/hint", response_model=IntentResponse)
def quiz_hint(assistant: dict = Depends(get_assistant)):
    """Request a hint for the current quiz question."""
    intent = Intent(name="quiz", params={"action": "hint"}, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Quiz hint failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.post("/api/quiz/quit", response_model=IntentResponse)
def quiz_quit(assistant: dict = Depends(get_assistant)):
    """Quit the current quiz session."""
    intent = Intent(name="quiz", params={"action": "quit"}, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Quiz quit failed: %s", e)
        return IntentResponse(ok=False, error=str(e))


@router.get("/api/quiz/score", response_model=IntentResponse)
def quiz_score(assistant: dict = Depends(get_assistant)):
    """Get the current quiz score."""
    intent = Intent(name="quiz", params={"action": "score"}, response="")
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Quiz score failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
