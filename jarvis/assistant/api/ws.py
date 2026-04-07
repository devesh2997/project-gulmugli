"""
WebSocket endpoint for the companion app.

Bridges FaceUI's state broadcasts to Flutter clients over the API port.
This runs on port 8766 (same as REST), separate from the dashboard's
raw WebSocket on port 8765.

Flow:
  1. Flutter connects: ws://host:8766/ws?token=<token>
  2. On connect: send full state snapshot (same data FaceUI sends to new browser clients)
  3. FaceUI broadcasts → forwarded here → sent to all Flutter clients
  4. Flutter sends actions → routed through handle_ui_action() (same path as dashboard)

The WebSocket manager registers itself as an external listener on FaceUI
(via face_ui.add_listener). This is purely additive — the React dashboard
on port 8765 is completely unaffected.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query

from api.auth import get_api_token
from core.logger import get_logger

log = get_logger("api.ws")

router = APIRouter()


class WebSocketManager:
    """
    Manages Flutter WebSocket clients and forwards FaceUI broadcasts.

    Thread-safe: forward_broadcast() is called from FaceUI's thread,
    messages are queued to the asyncio event loop for delivery.
    """

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio event loop (called from the first WebSocket connection)."""
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def forward_broadcast(self, message: dict) -> None:
        """
        Called by FaceUI._broadcast() via the external listener hook.

        This runs in FaceUI's WebSocket thread. We queue the message
        to our own asyncio loop for delivery to Flutter clients.
        """
        if not self._clients or not self._loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._send_to_all(message),
                self._loop,
            )
        except RuntimeError:
            # Loop closed or not running
            pass

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new Flutter client and send the state snapshot."""
        await websocket.accept()
        self._clients.add(websocket)

        # Capture the event loop on first connection
        if not self._loop:
            self._loop = asyncio.get_running_loop()

        log.debug("App client connected (%d total).", len(self._clients))

        # Send full state snapshot so the app is immediately in sync
        face_ui = self._get_face_ui(websocket)
        if face_ui:
            for msg in face_ui.get_state_snapshot():
                try:
                    await websocket.send_json(msg)
                except Exception:
                    break

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client."""
        self._clients.discard(websocket)
        log.debug("App client disconnected (%d remaining).", len(self._clients))

    async def _send_to_all(self, message: dict) -> None:
        """Send a message to all connected Flutter clients."""
        if not self._clients:
            return
        data = json.dumps(message)
        # Iterate a snapshot to avoid RuntimeError if the set is modified
        # during iteration (connect/disconnect from another coroutine).
        disconnected = set()
        for client in list(self._clients):
            try:
                await client.send_text(data)
            except Exception:
                disconnected.add(client)
        self._clients -= disconnected

    def _get_face_ui(self, websocket: WebSocket):
        """Get the FaceUI instance from the app state."""
        try:
            assistant = websocket.app.state.assistant
            return assistant.get("face_ui")
        except Exception:
            return None


# Module-level singleton — shared between the router and app.py
ws_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for the companion app.

    Receives real-time state updates (forwarded from FaceUI) and
    accepts action messages from the Flutter app.

    Auth: token passed as query parameter (skipped when auth is disabled).
    """
    from api.auth import _auth_enabled

    if _auth_enabled():
        expected = get_api_token()
        if token != expected:
            await websocket.close(code=4003, reason="Invalid token")
            return

    await ws_manager.connect(websocket)

    try:
        # Listen for actions from the Flutter app
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if "action" in data:
                    log.debug("App action received: %s", data.get("action"))
                    # Route through the same handler as the dashboard
                    face_ui = ws_manager._get_face_ui(websocket)
                    if face_ui and face_ui.on_action:
                        face_ui.on_action(data)
                elif data.get("type") == "gesture":
                    log.debug("App gesture received: %s", data.get("gesture"))
                    face_ui = ws_manager._get_face_ui(websocket)
                    if face_ui and face_ui.on_action:
                        face_ui.on_action(data)
            except json.JSONDecodeError:
                log.debug("Invalid JSON from app: %s", raw[:100])
            except Exception as e:
                log.warning("Error handling app action: %s", e)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)
