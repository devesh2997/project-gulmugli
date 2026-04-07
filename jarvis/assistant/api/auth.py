"""
Authentication for the companion app API.

Currently DISABLED for development. All endpoints are open.
Auth will be re-enabled before deployment (see TODO below).

When re-enabled:
- V1 uses a simple static bearer token stored in config.yaml
- Token is auto-generated (UUID4) on first startup if the config field is empty
- REST: Authorization: Bearer <token> header
- WebSocket: ?token=<token> query parameter

TODO: Re-enable auth before deployment by setting api.auth_enabled: true
      in config.yaml. All the plumbing is here, just bypassed.
"""

import uuid

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import config
from core.logger import get_logger

log = get_logger("api.auth")

_security = HTTPBearer(auto_error=False)

# ── Token management ────────────────────────────────────────────

_api_token: str = ""


def _auth_enabled() -> bool:
    """Check if auth is enabled in config. Defaults to False during dev."""
    return config.get("api", {}).get("auth_enabled", False)


def get_api_token() -> str:
    """
    Get or generate the API token.

    Reads from config.yaml → api.token. If empty, generates a UUID4
    and logs it so the user can copy it into the Flutter app.
    """
    global _api_token

    if _api_token:
        return _api_token

    configured = config.get("api", {}).get("token", "")
    if configured:
        _api_token = configured
    else:
        _api_token = str(uuid.uuid4())
        if _auth_enabled():
            log.info(
                "No API token configured. Generated token for this session:\n"
                "  %s\n"
                "  Add this to config.yaml under api.token to persist it.",
                _api_token,
            )

    return _api_token


# ── FastAPI dependencies ────────────────────────────────────────

def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> str | None:
    """
    Verify the bearer token on REST endpoints.

    When auth is disabled (dev mode): always passes, returns None.
    When auth is enabled: raises 401 if token is missing or wrong.
    """
    if not _auth_enabled():
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API token.",
        )

    token = get_api_token()
    if credentials.credentials != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )
    return credentials.credentials


def verify_ws_token(token: str = Query(default="")) -> str | None:
    """
    Verify the token on WebSocket connections.

    When auth is disabled (dev mode): always passes.
    When auth is enabled: rejects if token is missing or wrong.
    """
    if not _auth_enabled():
        return None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API token.",
        )

    expected = get_api_token()
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API token.",
        )
    return token
