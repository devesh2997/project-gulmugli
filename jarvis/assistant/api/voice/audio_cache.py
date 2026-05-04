"""
Out-of-band audio cache for the streaming voice endpoint.

## Why

The streaming endpoint (`/api/voice/stream`) emits Server-Sent Events.
Each event is a JSON line. Embedding a base64-encoded WAV inside an
`audio_chunk` SSE event works syntactically, but SSE multiplexes
everything onto one TCP stream — a single 300-600 KB base64 blob in
flight blocks the head of line. While that big chunk is being sent,
the next `response_text` event the server already produced sits in
the kernel send buffer behind it. Symptom on the Mac client: text
events flow in real time, but audio for the same sentence and any
subsequent events show up several seconds late.

## Fix

Server caches each WAV in memory under a random `chunk_id`, emits a
tiny `audio_chunk` event (just `chunk_id` + `url` + `index` +
`sentence`), and serves the bytes from a separate GET endpoint
(`/api/voice/audio/{chunk_id}`). The Mac client fires off a parallel
HTTP fetch as soon as it sees the URL. SSE stream stays small and
head-of-line-clean; audio transfers run in parallel TCP streams; each
event reaches the client within ~10 ms of being yielded.

## Lifecycle

- Single-fetch: an entry is removed from the cache the first time it's
  read. Reasonable since the streaming client downloads each chunk
  exactly once and queues it for playback.
- TTL eviction: lazy on every insert. Sweeps entries older than
  `_AUDIO_CACHE_TTL` seconds. Worst case (client crashes mid-stream
  and never fetches) is bounded growth: ~5 chunks/request × ~600 KB
  × TTL window.

The stand-alone `synth_worker` in voice.py also has a 60-second idle
timeout that prevents the upstream worker thread from leaking when a
client disconnects mid-stream — those two protections together cap
the disconnect leak at well under a minute of memory churn.
"""

from __future__ import annotations

import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from api.auth import verify_token


# Module-level cache. Key: chunk_id (uuid hex). Value: (wav_bytes, insert_time).
_AUDIO_CACHE: dict[str, tuple[bytes, float]] = {}
_AUDIO_CACHE_LOCK = threading.Lock()
_AUDIO_CACHE_TTL = 300.0   # 5 minutes; aggressive enough to not leak, generous
                            # enough that no legitimate fetch fails.


def put(wav: bytes) -> str:
    """
    Store WAV bytes, return a chunk_id. Evicts entries older than TTL.

    The eviction sweep is O(n) on the cache size, which is fine because
    n stays small (<50 entries even under heavy use; typical request has
    3-5 chunks).
    """
    chunk_id = uuid.uuid4().hex
    now = time.time()
    cutoff = now - _AUDIO_CACHE_TTL
    with _AUDIO_CACHE_LOCK:
        stale = [k for k, (_, t) in _AUDIO_CACHE.items() if t < cutoff]
        for k in stale:
            _AUDIO_CACHE.pop(k, None)
        _AUDIO_CACHE[chunk_id] = (wav, now)
    return chunk_id


def pop(chunk_id: str) -> bytes | None:
    """Retrieve WAV bytes by chunk_id. Single-fetch: removes after read."""
    with _AUDIO_CACHE_LOCK:
        entry = _AUDIO_CACHE.pop(chunk_id, None)
    return entry[0] if entry else None


# ── Backwards-compat aliases for code that imports the underscore-private names
# (the api/routers/voice.py refactor still uses these names internally for now,
# and tests/test_api_smoke.py imports `_audio_cache_put` directly).
_audio_cache_put = put
_audio_cache_pop = pop


# ── FastAPI route ───────────────────────────────────────────────────
# Mounted under the same auth dep as the rest of /api/voice/*.

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/voice/audio/{chunk_id}")
async def get_audio_chunk(chunk_id: str):
    """
    Fetch a synthesized WAV by chunk_id (issued via /api/voice/stream's
    `audio_chunk` SSE event). Each chunk is single-fetch — once retrieved
    it's removed from the cache.
    """
    wav = pop(chunk_id)
    if wav is None:
        raise HTTPException(
            status_code=404,
            detail=f"audio chunk '{chunk_id}' not found (already fetched, "
                   "or expired after 5 minutes)",
        )
    return Response(content=wav, media_type="audio/wav")
