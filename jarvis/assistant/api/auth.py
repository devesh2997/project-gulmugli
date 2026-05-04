"""
Authentication for the companion app API.

V1 mechanism — single bearer token.
- Token is read from config.yaml → api.token (persistent), or auto-generated
  (UUID4) at first startup and logged loudly so the user can copy it into
  the Flutter app's connect screen.
- REST: Authorization: Bearer <token> header
- WebSocket: ?token=<token> query parameter
- Auth is **enabled by default** (`api.auth_enabled: true`). This is a
  LAN-only product but the API binds to 0.0.0.0:8766; on any non-trusted
  network (Airbnb / friend's WiFi / cafe) every endpoint is reachable
  from any peer on the same SSID, including `/api/settings` which can
  mutate config.yaml. Without auth, that's an unprotected admin surface.
- For local development on a fully trusted single-host LAN, set
  `auth_enabled: false` in config.yaml (the dev's own Mac running the
  Mac client + the Jetson on the same router behind NAT). Don't ship
  this default flipped.

A first-run token is generated AND printed loudly even when auth is on
so the Flutter pairing flow has something to ingest. Scrape from
journalctl: `grep "API token" /tmp/jarvis.log | tail -1`.
"""

import threading
import uuid

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import config
from core.logger import get_logger

log = get_logger("api.auth")

_security = HTTPBearer(auto_error=False)

# ── Token management ────────────────────────────────────────────

_api_token: str = ""
# Lazy-init can race in a multi-threaded app server: two concurrent
# requests both see _api_token == "" and both generate different UUIDs;
# whichever loses the assignment race causes the other request's token
# to silently become invalid. Guard the lazy init under a lock.
_api_token_lock = threading.Lock()


def _auth_enabled() -> bool:
    """
    Check if auth is enabled in config.

    Defaults to **True** — see module docstring. A local dev who explicitly
    wants auth off must set `api.auth_enabled: false` in config.yaml.
    """
    return config.get("api", {}).get("auth_enabled", True)


def get_api_token() -> str:
    """
    Get or generate the API token.

    Reads from config.yaml → api.token. If empty, generates a UUID4
    and logs it so the user can copy it into the Flutter app.
    """
    global _api_token

    if _api_token:
        return _api_token

    with _api_token_lock:
        # Double-check under lock — another thread may have set this
        # between the unlocked early-return above and acquiring the lock.
        if _api_token:
            return _api_token

        configured = config.get("api", {}).get("token", "")
        if configured:
            _api_token = configured
        else:
            _api_token = str(uuid.uuid4())
            # Always log the generated token loudly so the Flutter app's
            # one-time pairing flow has something to scrape, regardless
            # of whether auth is currently enforced. The token is for
            # LAN clients on a trusted network; it's not a secret in the
            # production-security sense.
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
