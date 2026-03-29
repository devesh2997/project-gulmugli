"""
Ambient sound provider — looping background sounds for sleep and relaxation.

Plays ambient audio (rain, white noise, ocean, fireplace, etc.) via mpv in a
separate process, independent of music playback. Registers as the AMBIENT
channel in AudioFocusManager (priority 0 — lowest, ducks for everything).

Sound sources: YouTube searches for long ambient tracks. Each sound name maps
to a YouTube search query configured in config.yaml. mpv plays the first
result with --loop=inf for continuous looping.

Usage:
    ambient = AmbientSoundProvider()
    ambient.play("rain")
    ambient.set_volume(25)
    ambient.stop()
"""

import os
import shutil
import subprocess
import tempfile
import threading

from core.config import config
from core.logger import get_logger
from core.audio_focus import AudioFocusManager, AudioChannel

log = get_logger("ambient.sounds")


# Default sound → YouTube search query mapping.
# Override via config.yaml → ambient.sounds
DEFAULT_SOUNDS = {
    "rain": "rain ambient sleep 10 hours",
    "ocean": "ocean waves ambient sleep 10 hours",
    "thunderstorm": "thunderstorm ambient sleep 10 hours",
    "white_noise": "white noise 10 hours",
    "pink_noise": "pink noise 10 hours",
    "brown_noise": "brown noise 10 hours",
    "fireplace": "fireplace crackling ambient 10 hours",
    "forest": "forest birds ambient 10 hours",
    "birds": "morning birds singing ambient",
    "wind": "wind blowing ambient sleep",
    "cafe": "coffee shop ambient noise 10 hours",
    "fan": "fan noise ambient sleep 10 hours",
}


class AmbientSoundProvider:
    """
    Background ambient sound player.

    Runs mpv in a separate process (distinct IPC socket from music) with
    --loop=inf for continuous looping. Integrates with AudioFocusManager
    so ambient audio ducks or pauses when TTS/music need the output device.
    """

    def __init__(self):
        ambient_cfg = config.get("ambient", {})
        self._default_volume = ambient_cfg.get("default_volume", 30)
        self._volume = self._default_volume

        # Merge default sounds with config overrides
        self._sounds = dict(DEFAULT_SOUNDS)
        self._sounds.update(ambient_cfg.get("sounds", {}))

        # mpv process state
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._current_sound: str | None = None
        self._ipc_socket = os.path.join(
            tempfile.gettempdir(), "assistant-ambient-mpv-socket"
        )

        # Register with AudioFocusManager as lowest priority channel.
        # Ambient sounds should duck/pause for everything — music, TTS, alerts.
        focus = AudioFocusManager.instance()
        focus.register_channel(
            AudioChannel.AMBIENT,
            on_duck=self._focus_duck,
            on_restore=self._focus_restore,
            on_pause=self._focus_pause,
            on_resume=self._focus_resume,
            on_get_volume=self._focus_get_volume,
        )

        log.info(
            "AmbientSoundProvider ready — %d sounds available, default volume %d%%",
            len(self._sounds), self._default_volume,
        )

    # ── Public API ─────────────────────────────────────────────────

    def play(self, sound_name: str) -> bool:
        """
        Start playing an ambient sound by name.

        If already playing a different sound, stops the current one first.
        Searches YouTube for the sound query and plays via mpv with --loop=inf.

        Returns True if playback started successfully.
        """
        sound_name = sound_name.strip().lower().replace(" ", "_")

        # Fuzzy match: "rain sounds" → "rain", "white noise" → "white_noise"
        if sound_name not in self._sounds:
            # Try partial match
            for key in self._sounds:
                if sound_name.startswith(key) or key.startswith(sound_name):
                    sound_name = key
                    break
            else:
                log.warning("Unknown ambient sound: '%s'. Available: %s",
                            sound_name, ", ".join(self._sounds.keys()))
                return False

        query = self._sounds[sound_name]

        # Stop current ambient if playing
        if self._current_sound:
            self.stop()

        # Check mpv availability
        if not shutil.which("mpv"):
            log.error("mpv not found. Cannot play ambient sounds.")
            return False

        # Search YouTube for the ambient track
        try:
            url = self._search_youtube(query)
            if not url:
                log.warning("No YouTube results for ambient query: '%s'", query)
                return False
        except Exception as e:
            log.error("YouTube search failed for ambient: %s", e)
            return False

        # Start mpv with loop and low volume
        with self._lock:
            try:
                # Clean up stale socket
                if os.path.exists(self._ipc_socket):
                    try:
                        os.remove(self._ipc_socket)
                    except OSError:
                        pass

                cmd = [
                    "mpv",
                    url,
                    "--no-video",
                    "--loop=inf",
                    f"--volume={self._volume}",
                    f"--input-ipc-server={self._ipc_socket}",
                    "--really-quiet",
                ]

                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_sound = sound_name

                # Mark channel as active for AudioFocusManager
                AudioFocusManager.instance().set_channel_active(
                    AudioChannel.AMBIENT, True
                )

                log.info("Ambient playing: '%s' (query: '%s') at %d%%",
                         sound_name, query, self._volume)
                return True

            except Exception as e:
                log.error("Failed to start ambient mpv: %s", e)
                self._process = None
                self._current_sound = None
                return False

    def stop(self) -> None:
        """Stop ambient playback and release resources."""
        with self._lock:
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                except Exception:
                    pass
                self._process = None

            self._current_sound = None

            # Clean up IPC socket
            if os.path.exists(self._ipc_socket):
                try:
                    os.remove(self._ipc_socket)
                except OSError:
                    pass

            # Mark channel as inactive
            AudioFocusManager.instance().set_channel_active(
                AudioChannel.AMBIENT, False
            )

            log.info("Ambient stopped.")

    def set_volume(self, level: int) -> None:
        """Set ambient volume (0-100)."""
        level = max(0, min(100, level))
        self._volume = level
        self._send_mpv_command({"command": ["set_property", "volume", level]})
        log.debug("Ambient volume set to %d%%", level)

    def list_sounds(self) -> list[str]:
        """Return list of available ambient sound names."""
        return sorted(self._sounds.keys())

    def is_playing(self) -> bool:
        """Check if ambient audio is currently playing."""
        return (
            self._process is not None
            and self._process.poll() is None
        )

    def get_state(self) -> dict:
        """Return current ambient state for dashboard sync."""
        return {
            "active": self.is_playing(),
            "sound": self._current_sound or "",
            "volume": self._volume,
        }

    # ── AudioFocusManager callbacks ────────────────────────────────

    def _focus_duck(self, level: int) -> None:
        """Duck ambient volume when higher-priority audio needs focus."""
        self._send_mpv_command({"command": ["set_property", "volume", level]})

    def _focus_restore(self, level: int) -> None:
        """Restore ambient volume after higher-priority audio releases focus."""
        self._send_mpv_command({"command": ["set_property", "volume", level]})

    def _focus_pause(self) -> None:
        """Pause ambient for higher-priority audio (macOS, ALSA)."""
        self._send_mpv_command({"command": ["set_property", "pause", True]})

    def _focus_resume(self) -> None:
        """Resume ambient after higher-priority audio releases (macOS, ALSA)."""
        self._send_mpv_command({"command": ["set_property", "pause", False]})

    def _focus_get_volume(self) -> int:
        """Return current ambient volume for AudioFocusManager."""
        return self._volume

    # ── Internal ───────────────────────────────────────────────────

    def _send_mpv_command(self, command: dict) -> None:
        """Send a JSON IPC command to the ambient mpv process."""
        if not os.path.exists(self._ipc_socket):
            return

        import json
        import socket

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(self._ipc_socket)
            payload = json.dumps(command) + "\n"
            sock.sendall(payload.encode())
            sock.close()
        except Exception:
            pass  # mpv not ready or socket gone — non-critical

    def _search_youtube(self, query: str) -> str | None:
        """
        Search YouTube for an ambient track and return the best URL.

        Uses ytmusicapi if available (same as music provider), falls back
        to yt-dlp search for URL extraction.
        """
        # Try ytmusicapi first (already installed for music provider)
        try:
            from ytmusicapi import YTMusic
            yt = YTMusic()
            results = yt.search(query, filter="songs", limit=1)
            if results:
                video_id = results[0].get("videoId")
                if video_id:
                    return f"https://music.youtube.com/watch?v={video_id}"
        except Exception:
            pass

        # Fallback: yt-dlp search
        if shutil.which("yt-dlp"):
            try:
                result = subprocess.run(
                    ["yt-dlp", "--get-url", "--no-playlist", "-f", "bestaudio",
                     f"ytsearch1:{query}"],
                    capture_output=True, text=True, timeout=15,
                )
                url = result.stdout.strip()
                if url and url.startswith("http"):
                    return url
            except Exception:
                pass

        # Last fallback: let mpv handle the search directly
        return f"ytdl://ytsearch1:{query}"
