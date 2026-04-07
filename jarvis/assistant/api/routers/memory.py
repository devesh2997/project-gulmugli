"""
Memory endpoints — recall interactions and get stats.
"""

from fastapi import APIRouter, Depends, Query

from api.auth import verify_token
from api.deps import get_assistant
from api.schemas import MemoryRecallResponse, MemoryStatsResponse
from core.logger import get_logger

log = get_logger("api.memory")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/memory/recall", response_model=MemoryRecallResponse)
def memory_recall(
    q: str = Query(..., min_length=1, description="Search query for memory recall."),
    assistant: dict = Depends(get_assistant),
):
    """Search interaction history."""
    memory = assistant.get("memory")
    if not memory:
        return MemoryRecallResponse(memories=[])

    try:
        memories = memory.recall(q)
        return MemoryRecallResponse(memories=memories or [])
    except Exception as e:
        log.warning("Memory recall failed: %s", e)
        return MemoryRecallResponse(memories=[])


@router.get("/api/memory/stats", response_model=MemoryStatsResponse)
def memory_stats(assistant: dict = Depends(get_assistant)):
    """Get interaction statistics."""
    memory = assistant.get("memory")
    if not memory:
        return MemoryStatsResponse()

    try:
        stats = memory.get_stats()
        if isinstance(stats, dict):
            return MemoryStatsResponse(
                total_interactions=stats.get("total_interactions", 0),
                stats=stats,
            )
        return MemoryStatsResponse()
    except Exception as e:
        log.warning("Memory stats failed: %s", e)
        return MemoryStatsResponse()
