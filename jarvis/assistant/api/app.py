"""
FastAPI application factory + server launcher.

The API server runs in a daemon thread alongside the main assistant loop,
exactly like FaceUI does in ui/server.py. It exposes REST endpoints and
a WebSocket for the Flutter companion app.

Usage (from main.py):
    from api.app import create_api, start_api_server
    api_app = create_api(assistant)
    start_api_server(api_app, host="0.0.0.0", port=8766)
"""

import threading
from contextlib import asynccontextmanager
from typing import Optional

from core.logger import get_logger

log = get_logger("api.server")

# ── Guard imports ────────────────────────────────────────────────
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import uvicorn
    HAS_UVICORN = True
except ImportError:
    HAS_UVICORN = False


def create_api(assistant: dict) -> Optional["FastAPI"]:
    """
    Build the FastAPI application with all routers mounted.

    Args:
        assistant: The provider dict built by build_assistant() in main.py.
                   Stored on app.state so routes can access it via Depends.

    Returns:
        FastAPI app instance, or None if dependencies are missing.
    """
    if not HAS_FASTAPI:
        log.info(
            "API server disabled — fastapi not installed. "
            "Install with: pip install fastapi uvicorn[standard]"
        )
        return None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("API server starting up.")
        yield
        log.info("API server shutting down.")

    app = FastAPI(
        title="JARVIS Companion API",
        description="Local API for the JARVIS voice assistant companion app.",
        version="1.0.0",
        lifespan=lifespan,
        # Serve docs at /api/docs (not root /docs)
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Store the assistant dict so routes can access it.
    app.state.assistant = assistant

    # CORS — allow all origins for LAN use.
    # The app runs on phones on the same network; restrictive CORS
    # would only cause headaches with zero security benefit on LAN.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Mount routers ────────────────────────────────────────
    from api.routers.system import router as system_router
    app.include_router(system_router, tags=["system"])

    from api.ws import router as ws_router
    app.include_router(ws_router, tags=["websocket"])

    from api.routers.intents import router as intents_router
    from api.routers.music import router as music_router
    from api.routers.lights import router as lights_router
    from api.routers.volume import router as volume_router
    from api.routers.personality import router as personality_router
    from api.routers.chat import router as chat_router
    app.include_router(intents_router, tags=["intents"])
    app.include_router(music_router, tags=["music"])
    app.include_router(lights_router, tags=["lights"])
    app.include_router(volume_router, tags=["volume"])
    app.include_router(personality_router, tags=["personality"])
    app.include_router(chat_router, tags=["chat"])

    # ── Phase 3 routers ──────────────────────────────────────
    from api.routers.weather import router as weather_router
    from api.routers.quiz import router as quiz_router
    from api.routers.timer import router as timer_router
    from api.routers.reminder import router as reminder_router
    from api.routers.memory import router as memory_router
    from api.routers.knowledge import router as knowledge_router
    from api.routers.story import router as story_router
    from api.routers.ambient import router as ambient_router
    from api.routers.settings import router as settings_router
    from api.routers.audio import router as audio_router
    app.include_router(weather_router, tags=["weather"])
    app.include_router(quiz_router, tags=["quiz"])
    app.include_router(timer_router, tags=["timer"])
    app.include_router(reminder_router, tags=["reminder"])
    app.include_router(memory_router, tags=["memory"])
    app.include_router(knowledge_router, tags=["knowledge"])
    app.include_router(story_router, tags=["story"])
    app.include_router(ambient_router, tags=["ambient"])
    app.include_router(settings_router, tags=["settings"])
    app.include_router(audio_router, tags=["audio"])

    return app


def start_api_server(app: "FastAPI", host: str = "0.0.0.0", port: int = 8766) -> Optional[threading.Thread]:
    """
    Run the FastAPI app in a background daemon thread via uvicorn.

    Same pattern as FaceUI._run_server() — daemon thread with its own
    event loop, silently skipped if dependencies are missing, never
    blocks the main assistant startup.

    Args:
        app:  FastAPI instance from create_api().
        host: Bind address. "0.0.0.0" to accept LAN connections.
        port: HTTP port. Default 8766 (FaceUI uses 8765).

    Returns:
        The background thread, or None if uvicorn is missing.
    """
    if not app:
        return None

    if not HAS_UVICORN:
        log.info(
            "API server disabled — uvicorn not installed. "
            "Install with: pip install uvicorn[standard]"
        )
        return None

    def _run():
        try:
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level="warning",
                # Disable uvicorn's default access log — we use our own logger
                access_log=False,
            )
        except OSError as e:
            log.warning("API server failed to start: %s (port %d in use?)", e, port)
        except Exception as e:
            log.error("API server error: %s", e)

    thread = threading.Thread(
        target=_run,
        name="api-server",
        daemon=True,
    )
    thread.start()

    # Log the token so the user knows how to connect.
    from api.auth import get_api_token
    token = get_api_token()
    log.info("API server ready at http://%s:%d", host, port)
    log.info("API docs at http://localhost:%d/api/docs", port)
    log.info("API token: %s", token)

    return thread
