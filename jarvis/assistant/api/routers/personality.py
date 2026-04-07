"""
Personality endpoints — list, get active, switch.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import (
    IntentResponse,
    PersonalityInfo,
    PersonalityListResponse,
    PersonalitySwitchRequest,
)
from core.interfaces import Intent
from core.intent_handler import handle_intent
from core.logger import get_logger
from core.personality import personality_manager

log = get_logger("api.personality")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/personalities", response_model=PersonalityListResponse)
def list_personalities():
    """List all available personalities and the active one."""
    active = personality_manager.active
    profiles = [
        PersonalityInfo(
            id=p.id,
            display_name=p.display_name,
            description=p.description,
            avatar_type=p.avatar_type,
        )
        for p in personality_manager.list()
    ]
    return PersonalityListResponse(active=active.id, personalities=profiles)


@router.get("/api/personality/active", response_model=PersonalityInfo)
def active_personality():
    """Get the currently active personality."""
    p = personality_manager.active
    return PersonalityInfo(
        id=p.id,
        display_name=p.display_name,
        description=p.description,
        avatar_type=p.avatar_type,
    )


@router.post("/api/personality/switch", response_model=IntentResponse)
def switch_personality(
    req: PersonalitySwitchRequest,
    assistant: dict = Depends(get_assistant),
):
    """Switch the active personality."""
    intent = Intent(
        name="switch_personality",
        params={"personality": req.personality},
        response="",
    )
    try:
        response = handle_intent(assistant, intent)
        return IntentResponse(ok=True, response=response or "")
    except Exception as e:
        log.warning("Personality switch failed: %s", e)
        return IntentResponse(ok=False, error=str(e))
