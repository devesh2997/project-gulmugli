"""
Custom Playlist — load and iterate through a hand-curated event playlist.

## Why this exists

Event packs ship with a curated music playlist that auto-queues when the
event triggers. For Astha's birthday, this is her favorite Bollywood
romantic songs + classic birthday tracks ("Tum Jiyo Hazaaron Saal", "Baar
Baar Din Ye Aaye"). The user can override at any time by speaking a
specific song request — that's normal music_play behavior. The playlist
just provides the *default* background curation.

## Schema

`events/<pack>/media/songs/playlist.yaml`:

    songs:
      - youtube_search: "Tum Jiyo Hazaaron Saal"
      - youtube_search: "Baar Baar Din Ye Aaye"
      - youtube_search: "Sajni Arijit Singh"
    shuffle: true
    loop: true

Each entry has `youtube_search`: the query to feed into the music
provider's `search()`. The first result is what plays.

`shuffle`: if true, the next-song picker draws randomly (no repeats
until the pool is exhausted) rather than walking the list in order.

`loop`: if true, the list restarts after the last song.

## Architecture: thin wrapper, music provider does the work

This module deliberately doesn't talk to YouTube Music or mpv — the
existing `MusicProvider.search()` + `play()` are unchanged. We just
maintain the queue position and hand out `next_query()` strings that
the caller feeds into the provider.

That keeps the playlist logic testable without a YouTube round-trip,
and decouples it from the music backend (works the same with any
future provider — Spotify, local files, etc.).
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from core.logger import get_logger

log = get_logger("custom_playlist")


# ── Public types ────────────────────────────────────────────────────


@dataclass
class CustomPlaylist:
    """
    A loaded playlist with iteration state. Thread-safe — `next_query()`
    is safe to call concurrently with `reload()` (the lock guards the
    cursor update).
    """

    queries: list[str] = field(default_factory=list)
    shuffle: bool = False
    loop: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cursor: int = 0
    _shuffle_pool: list[int] = field(default_factory=list, repr=False)

    @property
    def is_empty(self) -> bool:
        return not self.queries

    def reset(self) -> None:
        """Reset iteration cursor to the start of the playlist."""
        with self._lock:
            self._cursor = 0
            self._shuffle_pool = []

    def next_query(self) -> Optional[str]:
        """
        Return the next song query, or None if the playlist is exhausted
        and `loop` is False. Advances the cursor.

        Shuffle: maintains an internal random-order pool that's
        re-shuffled on exhaustion (so we cycle through every song
        before any repeats).
        """
        with self._lock:
            if not self.queries:
                return None
            if self.shuffle:
                if not self._shuffle_pool:
                    if self._cursor > 0 and not self.loop:
                        # First pool exhausted, no loop → done.
                        return None
                    self._shuffle_pool = list(range(len(self.queries)))
                    random.shuffle(self._shuffle_pool)
                idx = self._shuffle_pool.pop()
                self._cursor += 1
                return self.queries[idx]
            else:
                if self._cursor >= len(self.queries):
                    if not self.loop:
                        return None
                    self._cursor = 0
                q = self.queries[self._cursor]
                self._cursor += 1
                return q


# ── Loading ─────────────────────────────────────────────────────────


def load_playlist(path: Path) -> CustomPlaylist:
    """
    Parse playlist.yaml. On any failure (missing file, bad YAML, wrong
    shape) returns an EMPTY playlist with a logged warning rather than
    raising — the caller's flow ("trigger fired, queue background music")
    should never crash because content is missing.
    """
    if not path.is_file():
        log.warning("custom_playlist: not found at %s", path)
        return CustomPlaylist()

    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log.warning("custom_playlist: YAML parse error in %s: %s", path, e)
        return CustomPlaylist()

    if not isinstance(data, dict):
        log.warning("custom_playlist: %s top-level must be a mapping", path)
        return CustomPlaylist()

    raw_songs = data.get("songs") or []
    if not isinstance(raw_songs, list):
        log.warning("custom_playlist: `songs:` must be a list")
        return CustomPlaylist()

    queries: list[str] = []
    for i, entry in enumerate(raw_songs):
        if not isinstance(entry, dict):
            log.warning("custom_playlist: skip entry %d (not a dict)", i)
            continue
        q = entry.get("youtube_search")
        if isinstance(q, str) and q.strip():
            queries.append(q.strip())
        else:
            log.warning("custom_playlist: skip entry %d (missing youtube_search)", i)

    return CustomPlaylist(
        queries=queries,
        shuffle=bool(data.get("shuffle", False)),
        loop=bool(data.get("loop", True)),
    )


# ── Convenience: play the first song now ────────────────────────────


def play_first(
    playlist: CustomPlaylist,
    music_provider,
    *,
    video: bool = False,
) -> Optional[str]:
    """
    Search for the first song in the playlist and play it. Returns the
    title that played (for spoken acknowledgement) or None on any
    failure. Best-effort — search misses, network errors, or unloaded
    providers all log + return None rather than raising.

    The caller is responsible for queueing subsequent songs (e.g., via
    `music_provider.register_on_ended(...)`). This module doesn't wire
    that up because it's coupled to the provider's specific callback
    signature.
    """
    if music_provider is None:
        log.info("custom_playlist: no music_provider — skipping")
        return None
    query = playlist.next_query()
    if query is None:
        log.info("custom_playlist: queue empty")
        return None
    try:
        results = music_provider.search(query, limit=1)
    except Exception as e:
        log.warning("custom_playlist: search failed for %r: %s", query, e)
        return None
    if not results:
        log.warning("custom_playlist: no results for %r", query)
        return None
    song = results[0]
    try:
        ok = music_provider.play(song, video=video)
    except Exception as e:
        log.warning("custom_playlist: play failed for %r: %s", song.title, e)
        return None
    if not ok:
        return None
    return song.title
