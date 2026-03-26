"""
Dashboard WebSocket server — bidirectional bridge between assistant and browser UI.

Pushes assistant state to the browser (state changes, transcript, now playing, etc.)
and receives actions from the browser (pause, skip, text input, light control, etc.).

Usage:
    face_ui = FaceUI(port=8765)
    face_ui.start()  # starts WebSocket server in background thread

    # Push state to browser:
    face_ui.set_state("listening")
    face_ui.set_personality("devesh")
    face_ui.show_transcript("Play Sajni", role="user")
    face_ui.set_now_playing({"title": "Husn", "artist": "Anuv Jain"})

    # Handle actions from browser:
    face_ui.on_action = lambda action: handle_intent(assistant, action)

Architecture:
    - The WebSocket server runs in a background thread with its own asyncio event loop
    - State updates are thread-safe (queued via asyncio.run_coroutine_threadsafe)
    - Multiple browser clients can connect simultaneously (all get the same state)
    - Browser clients can send actions back (JSON messages with "action" field)
    - If no browser is connected, state updates are silently dropped (no-op)
    - If the server fails to start (port in use, etc.), the assistant keeps running
      — the dashboard is purely optional, never blocks core functionality
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
        self._now_playing: Optional[dict] = None
        self._music_paused: bool = False
        self._lights: Optional[dict] = None
        self._volume: int = 50
        self._personalities: list[dict] = []

        # Callback for actions received from the browser UI.
        # Set this from main.py to route UI actions into the assistant's
        # intent handling pipeline.
        #   face_ui.on_action = lambda action: handle_ui_action(assistant, action)
        self.on_action: Optional[callable] = None

        # Stores the latest value for each CSS/animation token path so they
        # can be re-sent to clients that connect after the values were set.
        # Key: dotted path string (e.g. "animation.orb.breathe.duration")
        # Value: whatever was last passed to update_token()
        self._token_overrides: dict = {}

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

    def set_now_playing(self, data: Optional[dict]) -> None:
        """
        Update the "now playing" info on the dashboard.

        Args:
            data: Dict with title, artist, album, art_url, duration, position.
                  None to clear (nothing playing).
        """
        self._now_playing = data
        if data:
            self._music_paused = False
            self._broadcast({"type": "now_playing", "data": data, "paused": False})
        else:
            self._music_paused = False
            self._broadcast({"type": "music_stopped"})

    def set_music_paused(self, paused: bool) -> None:
        """Update the music paused/playing state on the dashboard."""
        self._music_paused = paused
        self._broadcast({"type": "music_paused", "paused": paused})

    def set_volume(self, level: int) -> None:
        """Update the volume indicator on the dashboard."""
        self._volume = level
        self._broadcast({"type": "volume", "level": level})

    def set_personalities(self, personalities: list[dict]) -> None:
        """
        Send the list of available personalities to the dashboard.

        Args:
            personalities: List of dicts with id, display_name, description.
        """
        self._personalities = personalities
        self._broadcast({"type": "personalities", "list": personalities})

    def set_lights(self, on: bool = True, color: str = "#ffffff",
                   brightness: int = 100, scene: str = None) -> None:
        """Update the light state indicator on the dashboard."""
        self._lights = {"on": on, "color": color, "brightness": brightness, "scene": scene}
        self._broadcast({
            "type": "lights",
            "on": on,
            "color": color,
            "brightness": brightness,
            "scene": scene,
        })

    def send_intents(self, intents: list[dict]) -> None:
        """
        Broadcast the current intent pipeline to all connected clients.

        Called once the assistant has classified a command so the dashboard
        can render the step-by-step progress (e.g. classification → enrichment
        → search → playback).

        Args:
            intents: List of intent dicts, e.g.
                     [{"id": "abc", "type": "music_play", "status": "pending", ...}]
        """
        self._broadcast({"type": "intents", "intents": intents})

    def update_intent(self, intent_id: str, status: str,
                      detail: Optional[str] = None) -> None:
        """
        Broadcast a status update for a single intent step.

        Args:
            intent_id: The id of the intent being updated.
            status:    New status string (e.g. "running", "done", "error").
            detail:    Optional human-readable detail string shown in the UI.
        """
        self._broadcast({
            "type": "intent_update",
            "id": intent_id,
            "status": status,
            "detail": detail,
        })

    def update_token(self, path: str, value) -> None:
        """
        Broadcast a CSS/animation token override and cache it for new clients.

        Persisted in ``self._token_overrides`` so clients that connect later
        receive the current value immediately on sync.

        Args:
            path:  Dotted token path, e.g. ``"animation.orb.breathe.duration"``.
            value: New value for the token (string, int, or float).
        """
        self._token_overrides[path] = value
        self._broadcast({"type": "token_update", "path": path, "value": value})

    def set_mood(self, mood: str) -> None:
        # TODO: v2 — broadcast mood to clients
        pass

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
        log.debug("Dashboard client connected (%d total).", len(self._clients))

        # Send current state so newly connected clients are in sync
        try:
            await websocket.send(json.dumps({
                "type": "state", "state": self._current_state,
            }))
            await websocket.send(json.dumps({
                "type": "personality", "id": self._current_personality,
            }))
            await websocket.send(json.dumps({
                "type": "volume", "level": self._volume,
            }))
            if self._personalities:
                await websocket.send(json.dumps({
                    "type": "personalities", "list": self._personalities,
                }))
            if self._now_playing:
                await websocket.send(json.dumps({
                    "type": "now_playing", "data": self._now_playing,
                    "paused": self._music_paused,
                }))
            if self._lights:
                await websocket.send(json.dumps({
                    "type": "lights", **self._lights,
                }))
            # Re-send any stored token overrides so the new client is
            # immediately in sync with the current visual state.
            for path, value in self._token_overrides.items():
                await websocket.send(json.dumps({
                    "type": "token_update", "path": path, "value": value,
                }))
        except Exception:
            pass

        try:
            # Listen for actions FROM the browser (pause, skip, text input, etc.)
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if "action" in data and self.on_action:
                        log.debug("UI action received: %s", data.get("action"))
                        # Route to the assistant's action handler
                        # This runs in the WS thread — the callback should be thread-safe
                        self.on_action(data)
                    elif data.get("type") == "gesture" and self.on_action:
                        log.debug("UI gesture received: %s", data.get("gesture"))
                        # Route gesture events using the same callback as actions
                        self.on_action(data)
                except json.JSONDecodeError:
                    log.debug("Invalid JSON from browser: %s", message[:100])
                except Exception as e:
                    log.warning("Error handling UI action: %s", e)
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)
            log.debug("Dashboard client disconnected (%d remaining).", len(self._clients))

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
