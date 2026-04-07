"""
Settings endpoints — read and update assistant configuration.
"""

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.schemas import SettingUpdateRequest, SettingUpdateResponse
from core.config_manager import config_manager
from core.logger import get_logger

log = get_logger("api.settings")

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/settings")
def get_settings():
    """Get all configurable settings."""
    try:
        return config_manager.get_settings()
    except Exception as e:
        log.warning("Failed to get settings: %s", e)
        return {}


@router.post("/api/settings", response_model=SettingUpdateResponse)
def update_setting(req: SettingUpdateRequest):
    """Update a single configuration value."""
    try:
        result = config_manager.update(req.path, req.value)
        if isinstance(result, dict) and result.get("ok"):
            return SettingUpdateResponse(ok=True, path=req.path)
        error = result.get("message", "Update failed.") if isinstance(result, dict) else "Update failed."
        return SettingUpdateResponse(ok=False, path=req.path, error=error)
    except Exception as e:
        log.warning("Setting update failed: %s", e)
        return SettingUpdateResponse(ok=False, path=req.path, error=str(e))
