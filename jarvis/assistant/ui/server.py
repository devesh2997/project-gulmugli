"""
Face UI WebSocket server — pushes assistant state to the browser UI.

This is a tiny async WebSocket server that the face.html UI connects to.
The assistant's main loop calls FaceUI.set_state(), .set_personality(), etc.,
and this server broadcasts those changes to all connected browser clients.

Usage:
    face_ui = FaceUI(port=8765)
    face_ui.start()  # starts WebSocket server in background thread

    # From anywhere in the assistant:
    face_ui.set_state("listening")
    face_ui.set_personality("devesh")
    face_ui.show_transcript("Play Sajni", role="user")

Architecture:
    - The WebSocket server runs in a background thread with its own asyncio event loop
    - State updates are thread-safe (queued via asyncio.run_coroutine_threadsafe)
    - Multiple browser clients can connect simultaneously (all get the same state)
    - If no browser is connected, state updates are silently dropped (no-op)
    - If the server fails to start (port in use, etc.), the assistant keeps running
      — the face UI is purely cosmetic, never blocks core functionality
"""

import asyncio
import json
import threading
from typing import Optional

from core.logger import get_logger

log = get_logger("ui.face")

# ── Guard import ────────────────────────────────────────────────
try:
    import websockets
    from websockets.server import serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class FaceUI:
    """
    Bridge between the assistant's main loop and the browser face UI.

    Thread-safe: call set_state / set_personality / show_transcript from any thread.
    """

    def __init__(self, port: int = 8765):
        self._port = port
        self._clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._current_state = "idle"
        self._current_personality = "jarvis"

    @property
    def available(self) -> bool:
        """Whether the WebSocket library is installed."""
        return HAS_WEBSOCKETS

    def start(self) -> None:
        """Start the WebSocket server in a background thread."""
        if not HAS_WEBSOCKETS:
            log.info(
                "Face UI disabled — websockets not installed. "
                "Install with: pip install websockets"
            )
            return

        self._thread = threading.Thread(
            target=self._run_server,
            name="face-ui-server",
            daemon=True,
        )
        self._thread.start()
        log.info("Face UI server starting on ws://localhost:%d", self._port)

    def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
        log.info("Face UI server stopped.")

    # ── Public API (thread-safe) ────────────────────────────────

    def set_state(self, state: str) -> None:
        """
        Update the face UI state.

        Valid states: idle, listening, thinking, speaking, sleeping
        """
        self._current_state = state
        self._broadcast({"type": "state", "state": state})

    def set_personality(self, personality_id: str) -> None:
        """Switch the face UI to a different personality's appearance."""
        self._current_personality = personality_id
        self._broadcast({"type": "personality", "id": personality_id})

    def show_transcript(self, text: str, role: str = "assistant") -> None:
        """
        Show a transcript bubble on the face UI.

        Args:
            text: The text to display
            role: "user" (what the user said) or "assistant" (response)
        """
        self._broadcast({"type": "transcript", "text": text, "role": role})

    # ── Internal ────────────────────────────────────────────────

    def _broadcast(self, message: dict) -> None:
        """Send a message to all connected browser clients."""
        if not self._loop or not self._clients:
            return
        data = json.dumps(message)
        asyncio.run_coroutine_threadsafe(
            self._send_to_all(data),
            self._loop,
        )

    async def _send_to_all(self, data: str) -> None:
        """Async broadcast to all connected WebSocket clients."""
        if not self._clients:
            return
        # Send to all clients, remove any that have disconnected
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(data)
            except Exception:
                disconnected.add(client)
        self._clients -= disconnected

    async def _handle_client(self, websocket) -> None:
        """Handle a new browser client connection."""
        self._clients.add(websocket)
        log.debug("Face UI client connected (%d total).", len(self._clients))

        # Send current state so newly connected clients are in sync
        try:
            await websocket.send(json.dumps({
                "type": "state", "state": self._current_state,
            }))
            await websocket.send(json.dumps({
                "type": "personality", "id": self._current_personality,
            }))
        except Exception:
            pass

        try:
            # Keep connection alive — we don't expect messages FROM the browser,
            # but websockets requires us to consume the connection
            async for _ in websocket:
                pass
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)
            log.debug("Face UI client disconnected (%d remaining).", len(self._clients))

    def _run_server(self) -> None:
        """Background thread: runs the async WebSocket server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            server = self._loop.run_until_complete(
                serve(self._handle_client, "0.0.0.0", self._port)
            )
            log.info("Face UI ready at ws://localhost:%d", self._port)
            log.info(
                "Open ui/face.html in a browser (or http://localhost:%d if served).",
                self._port,
            )
            self._loop.run_forever()
        except OSError as e:
            log.warning("Face UI server failed to start: %s (port %d in use?)", e, self._port)
        except Exception as e:
            log.error("Face UI server error: %s", e)
        finally:
            self._loop.close()
