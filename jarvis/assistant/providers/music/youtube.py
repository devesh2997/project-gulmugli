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
from concurrent.futures import ThreadPoolExecutor, as_completed

from ytmusicapi import YTMusic

from core.interfaces import MusicProvider, SongResult
from core.registry import register
from core.config import config
from core.logger import get_logger

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

    def play(self, song: SongResult) -> bool:
        # Stop any existing playback
        self.stop()

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

    def resume(self) -> None:
        self._send_mpv_command({"command": ["set_property", "pause", False]})

    def stop(self) -> None:
        if self._mpv_process:
            try:
                self._mpv_process.terminate()
                self._mpv_process.wait(timeout=3)
            except Exception:
                self._mpv_process.kill()
            self._mpv_process = None

        # Clean up socket
        if os.path.exists(self.ipc_socket):
            os.remove(self.ipc_socket)

    def skip(self) -> None:
        self._send_mpv_command({"command": ["playlist-next"]})

    def set_volume(self, level: int) -> None:
        level = max(0, min(100, level))
        self._send_mpv_command({"command": ["set_property", "volume", level]})
