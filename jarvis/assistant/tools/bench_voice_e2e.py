#!/usr/bin/env python3
"""
bench_voice_e2e.py — automated end-to-end TTFA benchmark for /api/voice/stream.

Generates WAV files via macOS `say`, posts them to the streaming endpoint,
measures both server-reported and client-perceived latency. Designed to run
without a human holding a microphone, so we can iterate on the pipeline and
produce reproducible metrics.

What this measures:
  - server first_audio_ms: when the server emitted its first audio_chunk SSE
  - client first_audio_announced: when the SSE event ARRIVED at the client
  - client first_audio_fetched: when the actual WAV bytes were downloaded
                                (the moment we could actually start playback)

  The third number is the real perceived TTFA — that's what the user hears
  unless we get fancy with playback streaming. The gap between announced
  and fetched tells us how much the audio transport is hurting us.

Usage:
  # Quick — one query, default chat-fast prompt
  python tools/bench_voice_e2e.py

  # Multi-run benchmark
  python tools/bench_voice_e2e.py --runs 5

  # Stress test — many queries, mixed types
  python tools/bench_voice_e2e.py --suite all

  # Custom queries
  python tools/bench_voice_e2e.py --query "what is photosynthesis" --runs 3

Env:
  JARVIS_HOST  default http://192.168.1.8:8766
  JARVIS_TOKEN required
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_HOST = os.environ.get("JARVIS_HOST", "http://192.168.1.8:8766")
TOKEN = os.environ.get("JARVIS_TOKEN", "")


# ─── Audio synthesis (macOS `say`) ──────────────────────────────────────

def synthesize_query(text: str, cache_dir: Path) -> Path:
    """Use macOS `say` to make a 16 kHz mono WAV of the spoken query."""
    safe = "".join(c if c.isalnum() else "_" for c in text)[:60]
    wav_path = cache_dir / f"q_{safe}.wav"
    if wav_path.exists() and wav_path.stat().st_size > 1024:
        return wav_path
    aiff_path = wav_path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-o", str(aiff_path), text],
        check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
         str(aiff_path), str(wav_path)],
        check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    aiff_path.unlink(missing_ok=True)
    return wav_path


# ─── SSE streaming client ────────────────────────────────────────────────

@dataclass
class RunResult:
    query: str
    transcribed: str = ""
    response_text: str = ""
    server_stt_ms: float = 0
    server_first_token_ms: float = 0
    server_first_audio_ms: float = 0
    server_total_ms: float = 0
    # ANY first audio reaching the client (filler or answer)
    client_first_audio_announced_ms: float = 0
    client_first_audio_fetched_ms: float = 0
    # First ANSWER audio (skipping filler) — what the user perceives as
    # "the assistant got my actual question"
    client_first_answer_announced_ms: float = 0
    client_first_answer_fetched_ms: float = 0
    client_total_ms: float = 0
    audio_chunks: int = 0
    audio_bytes_total: int = 0
    had_filler: bool = False
    sse_event_arrival_ms: list[float] = field(default_factory=list)
    error: str = ""


def run_query(host: str, token: str, wav_path: Path,
              warmup: bool = False, play: bool = False) -> RunResult:
    """
    Send a query via SSE and measure both announce time and fetch time
    for the FIRST audio chunk in PARALLEL — i.e. exactly the way the real
    Mac client does it. The first-fetch happens on a background thread
    immediately when the audio_chunk event arrives; we only block waiting
    for it after the SSE stream completes.

    If `play=True`, fetched audio chunks are played on the Mac via afplay
    in order. This is so the user can hear what the bench is doing —
    matters because the Jetson has no speaker and the user's earphones
    are plugged into this same Mac.
    """
    import queue as _q
    import requests
    from concurrent.futures import ThreadPoolExecutor

    result = RunResult(query=wav_path.stem)
    wav_bytes = wav_path.read_bytes()

    t0 = time.time()
    try:
        resp = requests.post(
            f"{host}/api/voice/stream",
            files={"audio": ("speech.wav", wav_bytes, "audio/wav")},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
                "Accept-Encoding": "identity",
            },
            stream=True,
            timeout=180,
        )
        resp.raise_for_status()
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        return result

    fetch_pool = ThreadPoolExecutor(max_workers=4)
    first_fetch_future = None
    play_queue = _q.Queue() if play else None
    play_thread = None

    if play:
        # Background worker plays each fetched WAV in arrival order via
        # macOS afplay. The user hears every test the bench runs.
        import threading
        def _play_worker():
            while True:
                item = play_queue.get()
                if item is None:
                    return
                wav = item
                f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                f.write(wav)
                f.close()
                try:
                    subprocess.run(
                        ["afplay", f.name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False,
                    )
                except Exception:
                    pass
                Path(f.name).unlink(missing_ok=True)
        play_thread = threading.Thread(target=_play_worker, daemon=True,
                                       name="bench-afplay")
        play_thread.start()

    def fetch_chunk(url: str, then_play: bool = False) -> tuple[bytes, float]:
        """Returns (bytes, fetch_completion_time_offset)."""
        full = url if url.startswith("http") else f"{host}{url}"
        r = requests.get(
            full,
            headers={"Authorization": f"Bearer {token}",
                     "Accept-Encoding": "identity"},
            timeout=30,
        )
        r.raise_for_status()
        elapsed = time.time() - t0
        if then_play and play_queue is not None:
            play_queue.put(r.content)
        return (r.content, elapsed)

    event_name = None
    data_lines: list[str] = []
    first_audio_chunk_id: Optional[str] = None

    try:
        for raw in resp.iter_lines(chunk_size=8192, decode_unicode=True):
            if raw is None:
                continue
            if raw == "":
                if event_name and data_lines:
                    try:
                        payload = json.loads("\n".join(data_lines))
                    except Exception:
                        payload = {}
                    t = time.time() - t0
                    result.sse_event_arrival_ms.append(t * 1000)

                    if event_name == "transcribed":
                        result.transcribed = payload.get("text", "")
                        result.server_stt_ms = payload.get("stt_ms", 0)
                    elif event_name == "response_text":
                        result.response_text += payload.get("text", "") + " "
                    elif event_name == "audio_chunk":
                        idx = payload.get("index", 0)
                        is_filler = (idx == -1)
                        if is_filler:
                            result.had_filler = True
                        else:
                            result.audio_chunks += 1
                        url = payload.get("url")
                        # Track FIRST audio (any kind, incl. filler) — perceived TTFA
                        if first_audio_chunk_id is None:
                            first_audio_chunk_id = payload.get("chunk_id")
                            result.client_first_audio_announced_ms = t * 1000
                            if url and not warmup:
                                first_fetch_future = fetch_pool.submit(
                                    fetch_chunk, url, then_play=play,
                                )
                        # Track FIRST ANSWER audio (skip filler) — engineering
                        # metric for how fast the actual answer is generated
                        elif (not is_filler
                              and result.client_first_answer_announced_ms == 0):
                            result.client_first_answer_announced_ms = t * 1000
                            if url and not warmup:
                                # Fire fetch in parallel so we know when this
                                # answer chunk's bytes arrived
                                ans_fut = fetch_pool.submit(
                                    fetch_chunk, url, then_play=play,
                                )
                                # We'll record fetch completion below
                                if not hasattr(run_query, "_answer_futures"):
                                    pass
                                # Stash on result to await later
                                result._first_answer_future = ans_fut  # type: ignore
                        elif url and play:
                            fetch_pool.submit(fetch_chunk, url, then_play=True)
                        bytes_ = payload.get("bytes", 0) or 0
                        result.audio_bytes_total += bytes_
                    elif event_name == "done":
                        timings = payload.get("timings", {}) or {}
                        result.server_first_token_ms = timings.get("first_token_ms", 0)
                        result.server_first_audio_ms = timings.get("first_audio_ms", 0)
                        result.server_total_ms = timings.get("total_ms", 0)
                        result.client_total_ms = t * 1000
                    elif event_name == "error":
                        result.error = payload.get("message", str(payload))
                event_name = None
                data_lines = []
                continue
            s = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
            if s.startswith("event:"):
                event_name = s[6:].strip()
            elif s.startswith("data:"):
                data_lines.append(s[5:].lstrip())

        # Wait for the first-chunk fetch (filler or real audio) to complete
        if first_fetch_future is not None:
            try:
                _, fetch_t = first_fetch_future.result(timeout=30)
                result.client_first_audio_fetched_ms = fetch_t * 1000
            except Exception as e:
                result.error = (result.error + f"; fetch failed: {e}").strip("; ")
        # Wait for the first ANSWER chunk fetch if filler was sent
        ans_fut = getattr(result, "_first_answer_future", None)
        if ans_fut is not None:
            try:
                _, fetch_t = ans_fut.result(timeout=30)
                result.client_first_answer_fetched_ms = fetch_t * 1000
            except Exception:
                pass
    finally:
        # Wait for the fetch_pool to drain its queue before shutting down,
        # otherwise late audio_chunks fired off via fetch_pool.submit() from
        # the SSE loop don't get a chance to play.
        fetch_pool.shutdown(wait=True)
        # Tell the play worker to drain and exit
        if play_queue is not None:
            play_queue.put(None)
        if play_thread is not None:
            play_thread.join(timeout=60)

    return result


# ─── Test suites ─────────────────────────────────────────────────────────

CHAT_QUERIES = [
    "what is the speed of light",
    "who invented the telephone",
    "how does photosynthesis work",
    "explain quantum computing in simple terms",
    "tell me about black holes",
]

PREFILTER_QUERIES = [
    "lights off",
    "lights on",
    "volume up",
    "pause",
    "stop the music",
]

SYSTEM_QUERIES = [
    "what time is it",
    "what is the time right now",  # currently misses prefilter
    "what's the date",
]


def format_summary(label: str, results: list[RunResult]) -> str:
    """
    Pretty-print a summary table for a batch of runs.

    The headline metric is `audible_ttfa` — wall-clock seconds from request
    send until the WAV bytes were fully downloaded by the client. That's
    when the user would actually hear audio (afplay startup is ~50ms on
    top, immaterial). It's what we should optimize against.

    The other timings are subsidiary diagnostics:
      announced_ttfa: when the server told the client "audio is ready"
                      (SSE event arrival). Tells us how fast the control
                      plane is.
      server_ttfa:    when the server yielded the audio_chunk SSE event.
                      Pure server-side cost (STT + LLM + TTS).
      fetch_overhead: audible_ttfa - announced_ttfa = HTTP GET transit
                      time for the audio body. Should be sub-second on
                      a healthy LAN.
    """
    successful = [r for r in results if not r.error]
    errored = [r for r in results if r.error]

    lines = [f"\n=== {label} (n={len(results)}, ok={len(successful)}, err={len(errored)}) ==="]
    if successful:
        audible = [r.client_first_audio_fetched_ms / 1000 for r in successful
                   if r.client_first_audio_fetched_ms > 0]
        announced = [r.client_first_audio_announced_ms / 1000 for r in successful
                     if r.client_first_audio_announced_ms > 0]
        server_ttfa = [r.server_first_audio_ms / 1000 for r in successful
                       if r.server_first_audio_ms > 0]
        # Answer-only metrics (skips filler so we see real backend latency)
        answer_audible = [r.client_first_answer_fetched_ms / 1000 for r in successful
                          if r.client_first_answer_fetched_ms > 0]
        # Per-run fetch overhead (audio body GET transit)
        fetch_overhead = [
            (r.client_first_audio_fetched_ms - r.client_first_audio_announced_ms) / 1000
            for r in successful
            if r.client_first_audio_fetched_ms > 0 and r.client_first_audio_announced_ms > 0
        ]
        n_filler = sum(1 for r in successful if r.had_filler)

        def stats(name, vals):
            if not vals:
                return f"  {name}: (no data)"
            vals = sorted(vals)
            return (f"  {name}: "
                    f"p50={statistics.median(vals):.2f}s  "
                    f"p95={vals[min(len(vals)-1, int(len(vals)*0.95))]:.2f}s  "
                    f"min={vals[0]:.2f}s  max={vals[-1]:.2f}s  "
                    f"n={len(vals)}")

        lines.append("  ── headline ───────────────────────────────────────")
        lines.append(stats("USER TTFA (audible)        ", audible))
        if n_filler > 0:
            lines.append(f"  (filler audio fired in {n_filler}/{len(successful)} runs)")
            lines.append(stats("    ↳ first ANSWER audible ", answer_audible))
        lines.append("  ── breakdown ──────────────────────────────────────")
        lines.append(stats("  server first_audio       ", server_ttfa))
        lines.append(stats("  SSE event arrival        ", announced))
        lines.append(stats("  GET audio body transit   ", fetch_overhead))

        # Per-query detail
        lines.append("\n  per-query:")
        for r in successful:
            audible_t = r.client_first_audio_fetched_ms / 1000
            transit = (r.client_first_audio_fetched_ms - r.client_first_audio_announced_ms) / 1000
            lines.append(
                f"    [{r.query[:40]:40s}] "
                f"audible={audible_t:5.2f}s  "
                f"(server={r.server_first_audio_ms/1000:5.2f}s + "
                f"sse={(r.client_first_audio_announced_ms - r.server_first_audio_ms)/1000:+5.2f}s + "
                f"transit={transit:+5.2f}s)  "
                f"chunks={r.audio_chunks}  "
                f"{r.audio_bytes_total/1024:.0f}KB"
            )
            if r.transcribed and r.transcribed.lower() not in r.query.lower().replace("_", " "):
                lines.append(f"      transcribed: {r.transcribed!r}")
            if r.response_text:
                lines.append(f"      response: {r.response_text[:80]!r}")

    for r in errored:
        lines.append(f"  [ERR {r.query[:40]:40s}] {r.error}")

    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Voice E2E benchmark")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--token", default=TOKEN)
    ap.add_argument("--runs", type=int, default=3, help="Runs per query")
    ap.add_argument("--query", default=None, help="Single query (overrides suite)")
    ap.add_argument("--suite", choices=["chat", "prefilter", "system", "all"],
                    default="chat", help="Which query set to test")
    ap.add_argument("--warmup", action="store_true",
                    help="Run a warmup query first; don't include it in stats")
    ap.add_argument("--play", action="store_true",
                    help="Play audio responses on this Mac via afplay so the "
                         "user can hear what the bench is doing")
    args = ap.parse_args()

    if not args.token:
        sys.stderr.write("ERROR: set JARVIS_TOKEN or pass --token\n")
        sys.exit(2)

    cache = Path(tempfile.gettempdir()) / "jarvis_bench_audio"
    cache.mkdir(exist_ok=True)

    if args.query:
        queries = [args.query]
    elif args.suite == "all":
        queries = CHAT_QUERIES + PREFILTER_QUERIES + SYSTEM_QUERIES
    elif args.suite == "chat":
        queries = CHAT_QUERIES
    elif args.suite == "prefilter":
        queries = PREFILTER_QUERIES
    elif args.suite == "system":
        queries = SYSTEM_QUERIES

    # Warmup
    if args.warmup:
        sys.stderr.write("warming up...\n")
        wav = synthesize_query("hello", cache)
        run_query(args.host, args.token, wav, warmup=True)

    results: list[RunResult] = []
    for q in queries:
        wav = synthesize_query(q, cache)
        for i in range(args.runs):
            sys.stderr.write(f"[{q[:40]:40s}] run {i+1}/{args.runs} ... ")
            sys.stderr.flush()
            r = run_query(args.host, args.token, wav, play=args.play)
            results.append(r)
            if r.error:
                sys.stderr.write(f"ERR {r.error}\n")
            else:
                sys.stderr.write(
                    f"announce {r.client_first_audio_announced_ms/1000:.2f}s  "
                    f"fetch {r.client_first_audio_fetched_ms/1000:.2f}s\n"
                )

    print(format_summary("E2E benchmark", results))


if __name__ == "__main__":
    main()
