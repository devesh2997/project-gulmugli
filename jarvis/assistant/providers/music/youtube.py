"""
YouTube Music provider.

Uses ytmusicapi for search and mpv for playback.
No API key needed for search. No rate limits for reasonable usage.
Knows every song on YouTube Music — including ones uploaded today.

To swap to Spotify:
  - Create providers/music/spotify.py
  - Implement MusicProvider using spotipy
  - Register with @register("music", "spotify")
  - Set music.provider: "spotify" in config.yaml
"""

import subprocess
import json
import os
import platform
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ytmusicapi import YTMusic

from core.interfaces import MusicProvider, SongResult
from core.registry import register
from core.config import config
from core.logger import get_logger
from core.audio_focus import AudioFocusManager, AudioChannel

log = get_logger("music.youtube")


@register("music", "youtube_music")
class YouTubeMusicProvider(MusicProvider):
    """YouTube Music search + mpv playback."""

    def __init__(self, **kwargs):
        music_config = config.get("music", {})
        self.ytm = YTMusic()
        self.default_limit = music_config.get("search_results", 5)
        self.auto_play_first = music_config.get("auto_play_first", True)
        self.player = music_config.get("player", "mpv")

        # mpv IPC socket for controlling playback — platform-safe temp directory
        self.ipc_socket = os.path.join(tempfile.gettempdir(), "assistant-mpv-socket")
        self._mpv_process = None
        self._last_song: SongResult | None = None
        self._paused: bool = False
        self._current_video_id: str | None = None

        # Serializes concurrent play() calls so rapid invocations don't
        # collide on the IPC socket (e.g., "play X" followed immediately by "play Y").
        self._play_lock = threading.Lock()

        # Callback registered by main.py — fired when mpv exits naturally (song ends).
        self._on_ended_callback = None

        # Background thread that watches mpv's process lifetime.
        self._monitor_thread: threading.Thread | None = None

        # Kill any orphaned mpv from previous sessions on startup
        self.stop()

        # Register with AudioFocusManager so TTS can duck/pause us
        focus = AudioFocusManager.instance()
        focus.register_channel(
            AudioChannel.MUSIC,
            on_duck=self._focus_duck,
            on_restore=self._focus_restore,
            on_pause=self._focus_pause,
            on_resume=self._focus_resume,
            on_get_volume=self._focus_get_volume,
        )

    def search(self, query: str, limit: int = None, raw_input: str = None) -> list[SongResult]:
        """
        Search YouTube Music with dual-search strategy.

        Always runs TWO searches:
          1. The LLM-enriched query  (e.g. "Sajni Arijit Singh")
          2. The user's raw input    (e.g. "Play sajni")

        Then picks the better result. This is the safety net for when the
        LLM adds a wrong artist or mangles the song name — YouTube Music's
        own popularity ranking often handles bare queries better than a
        hallucinated enrichment.

        The cost is one extra API call per music_play intent. ytmusicapi
        calls are fast (~100-200ms) and have no rate limit for reasonable use.
        """
        limit = limit or self.default_limit

        # If no raw_input, or raw and enriched are the same query, single search
        if not raw_input or raw_input.strip().lower() == query.strip().lower():
            return self._raw_search(query, limit)

        # Dual search: run BOTH searches in parallel to halve the wait.
        # Each ytmusicapi call takes ~100-200ms (network I/O bound), so
        # running them concurrently saves ~100-200ms per music request.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="yt-search") as pool:
            future_enriched = pool.submit(self._raw_search, query, limit)
            future_raw = pool.submit(self._raw_search, raw_input, limit)

        enriched_results = future_enriched.result()
        raw_results = future_raw.result()

        # If one search failed, return the other
        if not enriched_results:
            return raw_results
        if not raw_results:
            return enriched_results

        # Both returned results — pick the better one.
        if enriched_results[0].uri == raw_results[0].uri:
            log.debug('Both searches agree: "%s"', enriched_results[0].title)
            return enriched_results

        # Different songs — merge and deduplicate, raw results first.
        log.warning("Search mismatch: enriched \"%s\" → \"%s\", raw \"%s\" → \"%s\". Using raw result.",
                     query, enriched_results[0].title, raw_input, raw_results[0].title)

        seen_ids = set()
        merged = []
        for result in raw_results + enriched_results:
            if result.uri not in seen_ids:
                seen_ids.add(result.uri)
                merged.append(result)
        return merged[:limit]

    def _raw_search(self, query: str, limit: int) -> list[SongResult]:
        """Execute a single YouTube Music search and return SongResults."""
        results = self.ytm.search(query, filter="songs", limit=limit)

        return [
            SongResult(
                title=r.get("title", ""),
                artist=", ".join(a["name"] for a in r.get("artists", [])),
                album=r.get("album", {}).get("name", "") if r.get("album") else "",
                duration=r.get("duration", ""),
                uri=r.get("videoId", ""),
                source="youtube_music",
            )
            for r in results
        ]

    @property
    def current_video_id(self) -> str | None:
        """The YouTube videoId when playing in video mode, None otherwise."""
        return self._current_video_id

    def is_playing(self) -> bool:
        """True if mpv is running and has not exited."""
        return self._mpv_process is not None and self._mpv_process.poll() is None

    def register_on_ended(self, callback) -> None:
        """
        Register a callback that fires when playback ends naturally
        (mpv exits on its own — song finished, stream error, etc.).
        main.py uses this to clear the dashboard's now-playing state.
        """
        self._on_ended_callback = callback

    def _start_monitor(self) -> None:
        """Spawn a daemon thread that polls mpv's process status every 500ms."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return  # already monitoring

        def _watch():
            proc = self._mpv_process
            if proc is None:
                return
            while proc.poll() is None:
                import time
                time.sleep(0.5)
            # mpv exited naturally (song ended, stream finished, etc.)
            self._playback_ended()

        self._monitor_thread = threading.Thread(
            target=_watch, name="mpv-monitor", daemon=True,
        )
        self._monitor_thread.start()

    def _playback_ended(self) -> None:
        """Clean up after mpv exits on its own (not via stop())."""
        log.debug("mpv process exited — playback ended naturally.")
        self._mpv_process = None
        self._current_video_id = None
        self._paused = False

        # Clean up socket file
        if os.path.exists(self.ipc_socket):
            try:
                os.remove(self.ipc_socket)
            except OSError:
                pass

        AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, False)

        # Notify main.py so the dashboard clears now-playing
        if self._on_ended_callback:
            try:
                self._on_ended_callback()
            except Exception as e:
                log.warning("on_ended callback failed: %s", e)

    def play(self, song: SongResult, video: bool = False) -> bool:
        with self._play_lock:
            # Stop any existing playback
            self.stop()

            self._last_song = song
            self._paused = False

            # Always store video_id so the dashboard can display the video thumbnail.
            # In video mode the dashboard iframe handles both audio and video;
            # in normal mode mpv handles audio and the dashboard shows a mini thumbnail.
            self._current_video_id = song.uri

            if video:
                log.info('Video mode — dashboard will play videoId=%s', song.uri)
                AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, True)
                return True

            url = f"https://www.youtube.com/watch?v={song.uri}"

            # mpv with:
            #   --no-video: audio only (we're a voice assistant, not a TV)
            #   --input-ipc-server: creates a socket we can send commands to (pause, skip, volume)
            #   --really-quiet: no terminal spam
            try:
                self._mpv_process = subprocess.Popen(
                    [
                        self.player,
                        "--no-video",
                        f"--input-ipc-server={self.ipc_socket}",
                        "--really-quiet",
                        url,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, True)
                self._start_monitor()
                return True
            except FileNotFoundError:
                install_hint = {
                    "Darwin": "brew install mpv",
                    "Linux": "sudo apt-get install mpv",
                }.get(platform.system(), "install mpv from https://mpv.io")
                log.error("'%s' not found. Install it: %s", self.player, install_hint)
                return False
            except Exception as e:
                log.error("Failed to start playback: %s", e)
                return False

    def _send_mpv_command(self, command: dict) -> None:
        """Send a command to mpv via IPC socket."""
        if not os.path.exists(self.ipc_socket):
            return
        try:
            import socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(self.ipc_socket)
                sock.send(json.dumps(command).encode() + b"\n")
            finally:
                sock.close()
        except Exception:
            pass

    def pause(self) -> None:
        self._send_mpv_command({"command": ["set_property", "pause", True]})
        self._paused = True
        AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, False)

    def resume(self) -> None:
        # If mpv is still alive and was paused by the user, just unpause
        if self.is_playing() and self._paused:
            self._send_mpv_command({"command": ["set_property", "pause", False]})
            self._paused = False
            AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, True)
            return

        # If mpv is alive but NOT paused, it's already playing — do nothing
        if self.is_playing() and not self._paused:
            log.debug("Already playing — ignoring resume.")
            return

        # mpv died (e.g. song ended, crash) but we remember the last song — replay it
        if self._last_song:
            log.info('Resuming last song: "%s" by %s', self._last_song.title, self._last_song.artist)
            self.play(self._last_song)  # play() calls stop() internally, prevents duplicates
            return

        log.debug("Nothing to resume — no paused track or last song.")

    def stop(self) -> None:
        AudioFocusManager.instance().set_channel_active(AudioChannel.MUSIC, False)
        self._current_video_id = None

        # Kill the process we spawned this session
        if self._mpv_process:
            try:
                self._mpv_process.terminate()
                self._mpv_process.wait(timeout=3)
            except Exception:
                try:
                    self._mpv_process.kill()
                except Exception:
                    pass
            self._mpv_process = None

        # Also kill any orphaned mpv processes using our IPC socket.
        # These can accumulate from previous assistant sessions that crashed
        # or were killed without proper cleanup. Without this, stop()/play()
        # will fight with zombie processes over the socket.
        try:
            import signal
            result = subprocess.run(
                ["pgrep", "-f", f"mpv.*{os.path.basename(self.ipc_socket)}"],
                capture_output=True, text=True,
            )
            for pid_str in result.stdout.strip().split("\n"):
                if pid_str.strip():
                    try:
                        os.kill(int(pid_str.strip()), signal.SIGTERM)
                    except (ProcessLookupError, ValueError):
                        pass
        except FileNotFoundError:
            # pgrep not available on this platform — skip orphan cleanup
            pass

        # Clean up socket
        if os.path.exists(self.ipc_socket):
            try:
                os.remove(self.ipc_socket)
            except OSError:
                pass

    def skip(self) -> None:
        self._send_mpv_command({"command": ["playlist-next"]})

    def seek(self, position: float) -> None:
        """Seek to an absolute position in seconds."""
        if not self.is_playing():
            log.warning("seek() called but mpv is not running — ignoring.")
            return
        self._send_mpv_command({"command": ["set_property", "time-pos", position]})

    def set_volume(self, level: int) -> None:
        if not self.is_playing():
            log.warning("set_volume() called but mpv is not running — ignoring.")
            return
        level = max(0, min(100, level))
        self._send_mpv_command({"command": ["set_property", "volume", level]})

    def get_playback_position(self) -> dict | None:
        """
        Query mpv for current playback position and duration.

        Returns dict with "position" and "duration" (seconds), or None if
        nothing is playing or mpv isn't reachable.
        """
        position = self._query_mpv_property("time-pos")
        duration = self._query_mpv_property("duration")
        if position is not None and duration is not None:
            return {"position": position, "duration": duration}
        return None

    def _query_mpv_property(self, prop: str):
        """Query a single property from mpv via IPC. Returns the value or None."""
        if not os.path.exists(self.ipc_socket):
            return None
        try:
            import socket as sock_mod
            s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
            s.settimeout(0.5)
            try:
                s.connect(self.ipc_socket)
                cmd = json.dumps({"command": ["get_property", prop]}) + "\n"
                s.send(cmd.encode())
                data = s.recv(4096).decode()
                resp = json.loads(data.split("\n")[0])
                if resp.get("error") == "success":
                    return resp.get("data")
            finally:
                s.close()
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────────
    # Audio Focus callbacks
    # ──────────────────────────────────────────────────────────────

    def _focus_duck(self, level: int) -> None:
        """Called by AudioFocusManager: lower mpv volume for ducking."""
        self._send_mpv_command({"command": ["set_property", "volume", level]})

    def _focus_restore(self, level: int) -> None:
        """Called by AudioFocusManager: restore mpv volume after ducking."""
        self._send_mpv_command({"command": ["set_property", "volume", level]})

    def _focus_pause(self) -> None:
        """
        Called by AudioFocusManager: pause mpv for higher-priority audio.

        CRITICAL: Does NOT set self._paused. This is a system-initiated pause,
        not a user pause. The distinction matters in _focus_resume().
        """
        self._send_mpv_command({"command": ["set_property", "pause", True]})

    def _focus_resume(self) -> None:
        """
        Called by AudioFocusManager: resume mpv after higher-priority audio ends.

        CRITICAL: Only resumes if the user had NOT paused music themselves.
        If the user said "pause", self._paused is True, and we respect that
        — the music stays paused even after TTS finishes.
        """
        if self._paused:
            log.debug("Focus resume skipped — user had paused music.")
            return
        self._send_mpv_command({"command": ["set_property", "pause", False]})

    def _focus_get_volume(self) -> int:
        """Called by AudioFocusManager: query current mpv volume."""
        vol = self._query_mpv_property("volume")
        return int(vol) if vol is not None else 100
