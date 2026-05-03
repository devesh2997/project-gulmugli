"""
mac_client.py — pure mic+speaker bridge for the JARVIS Jetson.

The Mac contributes ZERO inference. All STT, intent classification, LLM,
and TTS happen on the Jetson. The Mac just captures audio bytes and plays
audio bytes back. This is the right design to measure REAL production
latency — what the appliance will actually feel like once the ReSpeaker
mic and speaker are wired into the Jetson.

  ┌────────────────┐                          ┌─────────────────┐
  │     Mac        │                          │     Jetson      │
  │  ─────────────►│  POST /api/voice         │ STT (Whisper)   │
  │   mic capture  │                          │   ↓             │
  │                │       (WAV bytes)        │ pipeline        │
  │                │                          │   ↓             │
  │   speaker play│◄──── audio response ─────│ TTS (Kokoro)    │
  │  ◄─────────────│       + text + timings   │                 │
  └────────────────┘                          └─────────────────┘

Modes:
  --text          plain text REPL hitting /api/chat (no audio)
  --voice         press-to-talk: ENTER to start, ENTER to stop
  --voice --auto  auto-stop after silence (VAD)

Usage:
  export JARVIS_TOKEN=a8c5824c-1723-4b18-80f8-274386b0c1fc
  export JARVIS_HOST=http://192.168.1.8:8766
  python clients/mac_client.py --voice
"""

import argparse
import base64
import io
import json
import os
import sys
import tempfile
import threading
import time
import wave

DEFAULT_HOST = os.environ.get("JARVIS_HOST", "http://192.168.1.8:8766")
DEFAULT_TOKEN = os.environ.get("JARVIS_TOKEN", "")

VOICE_RECORD_RATE = 16000
VOICE_RECORD_CHANNELS = 1


# ────────────────────────────────────────────────────────────────────────────
#  HTTP — Jetson API
# ────────────────────────────────────────────────────────────────────────────

def http_get(url, token, timeout=5):
    import urllib.request
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _classify_connection_error(exc) -> tuple[str, str]:
    """
    Turn a raw connection error into (kind, friendly_message). Three buckets:
      - "host_down"  : ConnectionRefused / no route — Jetson is off or wrong IP
      - "auth"       : 401/403 — token is wrong or stale
      - "timeout"    : connect or read timeout — Jetson is slow / overloaded
      - "other"      : something else; show the raw error
    """
    import socket
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return ("auth",
                    f"HTTP {exc.code}: API token rejected. Token might be stale "
                    f"(JARVIS regenerates one on each restart). Get the current token:\n"
                    f"  ssh devesh@<jetson-ip> 'grep \"API token\" /tmp/jarvis.log | tail -1'")
        return ("other", f"HTTP {exc.code}: {exc.reason}")

    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            return ("host_down",
                    "Connection refused. JARVIS isn't running or isn't listening on "
                    "this port. Check on the Jetson:\n"
                    "  ssh devesh@<jetson-ip> 'ss -tnlp | grep 8766'\n"
                    "If empty, restart JARVIS:\n"
                    "  ssh devesh@<jetson-ip> '/tmp/start_jarvis.sh'")
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return ("timeout",
                    "Connection timed out. The Jetson is reachable on the network "
                    "but isn't responding to /api/system/status within the timeout. "
                    "JARVIS may be wedged or overloaded. Try restarting it.")
        # OSError 65 (no route to host) or similar
        if hasattr(reason, "errno"):
            if reason.errno in (51, 65, 113):  # ENETUNREACH, EHOSTUNREACH variants
                return ("host_down",
                        f"No route to host. The Jetson appears to be off, "
                        f"on a different network, or the IP changed. "
                        f"Check: ping <jetson-ip>")
        return ("other", str(reason))

    if isinstance(exc, (TimeoutError,)):
        return ("timeout", "Request timed out.")

    return ("other", f"{type(exc).__name__}: {exc}")


def _wait_for_server(host: str, token: str, timeout: float = 10.0) -> bool:
    """
    Probe /api/system/status with retry-and-backoff. Returns True if the
    server responds within `timeout` seconds, False otherwise. On failure,
    prints a friendly diagnosis (one of: host down, auth, timeout, other)
    so the user knows what to fix without parsing a stacktrace.

    Used instead of a single http_get on startup so that brief network
    blips, mid-restart races, and "Jetson booting up" cases recover
    automatically rather than failing the user immediately.
    """
    deadline = time.time() + timeout
    attempt = 0
    last_kind = ""
    last_msg = ""
    while time.time() < deadline:
        attempt += 1
        try:
            s = http_get(f"{host}/api/system/status", token, timeout=3)
            sys.stderr.write(
                f"[mac_client] connected to {s.get('name','?')} v{s.get('version','?')}, "
                f"personality={s.get('personality','?')}, "
                f"uptime={s.get('uptime_seconds','?')}s\n"
            )
            return True
        except Exception as e:
            kind, msg = _classify_connection_error(e)
            last_kind, last_msg = kind, msg
            # Auth errors don't get better with retries — stop immediately
            if kind == "auth":
                sys.stderr.write(f"\nERROR: {msg}\n\n")
                return False
            # On the first failure, tell the user we're retrying — they may
            # have just started JARVIS and want to know we're waiting.
            if attempt == 1:
                sys.stderr.write(
                    f"\n[mac_client] Couldn't reach {host} ({kind}). "
                    f"Retrying for up to {timeout:.0f}s...\n"
                )
            # Exponential-ish backoff: 0.3, 0.6, 1.2, 2.4, ...
            time.sleep(min(2.5, 0.3 * (2 ** min(attempt - 1, 4))))

    # Exhausted retries — final friendly message
    sys.stderr.write(
        f"\nERROR: can't reach {host} after {attempt} attempts ({timeout:.0f}s).\n"
        f"  Diagnosis: {last_kind}\n"
        f"  {last_msg}\n\n"
    )
    return False


def http_post_json(url, body, token, timeout=120):
    import urllib.request, urllib.error
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return time.time() - t0, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return time.time() - t0, {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return time.time() - t0, {"ok": False, "error": f"{type(e).__name__}: {e}"}


def http_post_audio(url, wav_bytes, token, timeout=180):
    """POST audio as multipart/form-data with field name 'audio'."""
    import urllib.request, urllib.error
    boundary = "----JarvisVoice" + str(int(time.time()*1000))
    body_parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="audio"; filename="speech.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        wav_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return time.time() - t0, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return time.time() - t0, {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return time.time() - t0, {"ok": False, "error": f"{type(e).__name__}: {e}"}


def http_post_audio_stream(url, wav_bytes, token, timeout=180):
    """
    POST audio to a Server-Sent-Events endpoint and yield (event, data, t_offset)
    tuples as they arrive. `t_offset` is seconds since the request was sent —
    useful for measuring time-to-first-audio without trusting server timestamps.

    Why `requests` and not stdlib urllib: urllib's HTTPResponse.readline() does
    not actually stream over chunked-transfer-encoded responses on some platforms.
    On macOS specifically, audio_chunk events (~600KB base64) get buffered until
    the connection closes — turning a 2.5s server-side TTFA into a 23s client-side
    TTFA. `requests` with iter_lines() does honor real-time chunking.
    """
    try:
        import requests
    except ImportError:
        # Fallback to urllib (broken streaming, but at least it works after the
        # response completes). Tell the user to install requests.
        import sys
        sys.stderr.write(
            "\n[mac_client] WARNING: 'requests' not installed — SSE will buffer "
            "until end-of-stream. Install for real-time streaming:\n"
            "  pip install requests\n\n"
        )
        yield from _http_post_audio_stream_urllib(url, wav_bytes, token, timeout)
        return

    t0 = time.time()
    try:
        resp = requests.post(
            url,
            files={"audio": ("speech.wav", wav_bytes, "audio/wav")},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
                # Disable gzip — uvicorn doesn't compress streaming responses
                # but urllib3 sends Accept-Encoding: gzip,deflate by default
                # and an over-eager proxy could decide to compress, which
                # would then buffer until enough data accumulated.
                "Accept-Encoding": "identity",
            },
            stream=True,
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        yield ("error", {"message": f"{type(e).__name__}: {e}"}, 0)
        return

    # SSE record: one or more `field: value\n` lines, terminated by a blank line.
    # chunk_size=8192 is the sweet spot — large enough that each socket recv()
    # returns lots of data (cheap), small enough that we don't wait minutes
    # before iter_lines yields the first line. Default 512 also works; what
    # we MUST avoid is chunk_size=1, which does a syscall per byte and turns
    # every 600KB audio_chunk into 600k recv() calls = ~13s of pure syscall
    # overhead per chunk on macOS.
    event_name = None
    data_lines: list[str] = []
    for raw in resp.iter_lines(chunk_size=8192, decode_unicode=True):
        # iter_lines strips the line ending. An empty string => blank line => end of event.
        if raw is None:
            continue
        s = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        if s == "":
            if event_name and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except Exception:
                    payload = {"raw": "\n".join(data_lines)}
                yield (event_name, payload, time.time() - t0)
            event_name = None
            data_lines = []
            continue
        if s.startswith("event:"):
            event_name = s[6:].strip()
        elif s.startswith("data:"):
            data_lines.append(s[5:].lstrip())


def _http_post_audio_stream_urllib(url, wav_bytes, token, timeout=180):
    """Fallback urllib-based streaming consumer (buffers — keeps the client
    runnable even without `requests` installed, but won't show real TTFA)."""
    import urllib.request, urllib.error
    boundary = "----JarvisVoiceStream" + str(int(time.time()*1000))
    body_parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="audio"; filename="speech.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        wav_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        yield ("error", {"message": f"HTTP {e.code}: {e.read().decode()[:200]}"}, 0)
        return
    except Exception as e:
        yield ("error", {"message": f"{type(e).__name__}: {e}"}, 0)
        return

    event_name = None
    data_lines: list[str] = []
    while True:
        line = resp.readline()
        if not line:
            break
        s = line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
        if s == "":
            if event_name and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except Exception:
                    payload = {"raw": "\n".join(data_lines)}
                yield (event_name, payload, time.time() - t0)
            event_name = None
            data_lines = []
            continue
        if s.startswith("event:"):
            event_name = s[6:].strip()
        elif s.startswith("data:"):
            data_lines.append(s[5:].lstrip())


# ────────────────────────────────────────────────────────────────────────────
#  Mic capture (Mac, lazy import)
# ────────────────────────────────────────────────────────────────────────────

def _record_chunks_to_wav(chunks, rate=VOICE_RECORD_RATE) -> bytes:
    """Concatenate float32 frames and write a WAV file in memory."""
    import numpy as np
    audio = np.concatenate(chunks).flatten()
    pcm16 = (audio * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm16)
    return buf.getvalue()


def record_push_to_talk() -> bytes:
    """ENTER to start, ENTER to stop. Returns WAV bytes."""
    import sounddevice as sd

    sys.stderr.write("\n[mic] press ENTER to start recording, ENTER again to stop\n")
    sys.stderr.flush()
    input("> ready ... ")

    chunks = []
    stream = sd.InputStream(
        samplerate=VOICE_RECORD_RATE,
        channels=VOICE_RECORD_CHANNELS,
        dtype="float32",
        blocksize=int(VOICE_RECORD_RATE * 0.1),
    )
    stream.start()

    sys.stderr.write("● recording (press ENTER to stop) ...")
    sys.stderr.flush()

    stop = threading.Event()
    def waiter():
        input()
        stop.set()
    threading.Thread(target=waiter, daemon=True).start()

    while not stop.is_set():
        block, _ = stream.read(int(VOICE_RECORD_RATE * 0.1))
        chunks.append(block)

    stream.stop()
    stream.close()
    duration = sum(len(c) for c in chunks) / VOICE_RECORD_RATE
    sys.stderr.write(f" stopped ({duration:.1f}s captured)\n")
    return _record_chunks_to_wav(chunks)


def record_vad(silence_seconds: float = 0.7, max_seconds: float = 12.0) -> bytes:
    """
    Auto-stop after silence_seconds of silence. Returns WAV bytes.

    Default 700ms matches the production voice-assistant range (Alexa ~600ms,
    Google ~700ms, Siri ~800ms — research from LiveKit's voice latency blog).
    Earlier this was 1500ms which added ~800ms of dead-air at end-of-speech
    on every turn — invisible to a watch-the-bench developer but very
    noticeable in real conversation.

    Tradeoff: shorter silence threshold = lower latency, but risks cutting
    off the user mid-thought. 700ms is the published industry sweet spot
    for natural-pace English speech. Configurable per-call for users who
    speak with longer natural pauses (older speakers, second-language
    speakers, dictation-style usage).
    """
    import numpy as np
    import sounddevice as sd

    rms_threshold = 0.005
    frame_ms = 50
    frame_samples = int(VOICE_RECORD_RATE * frame_ms / 1000)
    silence_frames_needed = int(silence_seconds * 1000 / frame_ms)
    max_frames = int(max_seconds * 1000 / frame_ms)

    sys.stderr.write(f"\n● listening (auto-stop after {silence_seconds}s silence)...\n")
    sys.stderr.flush()

    chunks = []
    silent_streak = 0
    saw_voice = False

    with sd.InputStream(samplerate=VOICE_RECORD_RATE, channels=1, dtype="float32",
                       blocksize=frame_samples) as stream:
        for _ in range(max_frames):
            block, _ = stream.read(frame_samples)
            chunks.append(block)
            rms = float(np.sqrt(np.mean(block**2)))
            if rms > rms_threshold:
                if not saw_voice:
                    sys.stderr.write("  (voice)\n")
                saw_voice = True
                silent_streak = 0
            else:
                silent_streak += 1
            if saw_voice and silent_streak >= silence_frames_needed:
                break

    duration = sum(len(c) for c in chunks) / VOICE_RECORD_RATE
    sys.stderr.write(f"  stopped ({duration:.1f}s captured)\n")
    return _record_chunks_to_wav(chunks)


# ────────────────────────────────────────────────────────────────────────────
#  Audio playback (Mac, lazy import)
# ────────────────────────────────────────────────────────────────────────────

class _PlaybackState:
    process = None  # subprocess.Popen, if afplay is running

PB = _PlaybackState()


def stop_playback():
    if PB.process is not None and PB.process.poll() is None:
        PB.process.terminate()
        try:
            PB.process.wait(timeout=0.5)
        except Exception:
            PB.process.kill()
    PB.process = None


def play_wav_bytes(wav_bytes: bytes):
    """Play a WAV file using macOS `afplay`. Non-blocking."""
    import subprocess
    if not wav_bytes:
        return
    stop_playback()
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    f.write(wav_bytes)
    f.close()
    PB.process = subprocess.Popen(
        ["afplay", f.name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# ─── Streaming playback queue (SSE consumer) ────────────────────────────
#
# When the SSE stream tells us about an audio_chunk, the actual WAV bytes
# are fetched out-of-band via a parallel HTTP GET. We enqueue *Future*-
# like placeholders into the playback queue in the order the server
# emitted them; the worker waits on each future before playing, so audio
# plays in sentence order even if a later GET completes first. This
# decouples the SSE control stream (small text events, always real-time)
# from audio transport (large binary, can run in parallel TCP streams).

class _StreamPlayState:
    queue = None
    thread = None
    stop_flag = None
    started = False
    fetch_pool = None

SP = _StreamPlayState()


def stream_play_start():
    """Spawn a worker thread that plays WAVs from a queue, in order."""
    import queue as _q
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    SP.queue = _q.Queue()
    SP.stop_flag = threading.Event()
    SP.started = True
    # 4 parallel fetches is plenty — most responses have ≤4 sentences and
    # the bottleneck is wifi bandwidth, not the connection limit.
    SP.fetch_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audio-fetch")

    def _worker():
        while not SP.stop_flag.is_set():
            try:
                item = SP.queue.get(timeout=0.2)
            except _q.Empty:
                continue
            if item is None:
                return
            # `item` is either raw bytes (legacy) or a Future yielding bytes.
            if hasattr(item, "result"):
                try:
                    wav = item.result(timeout=30)
                except Exception as e:
                    sys.stderr.write(f"\n  [audio fetch failed] {e}\n")
                    continue
            else:
                wav = item
            if not wav:
                continue
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            f.write(wav)
            f.close()
            # afplay blocks until the file finishes — perfect for sequential
            # sentence playback. Each new sentence queues up and starts as
            # soon as the previous one ends, so the listener hears one
            # continuous response.
            try:
                subprocess.run(
                    ["afplay", f.name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
            try:
                os.unlink(f.name)
            except Exception:
                pass

    SP.thread = threading.Thread(target=_worker, name="afplay-worker", daemon=True)
    SP.thread.start()


def stream_play_enqueue(wav: bytes):
    """Enqueue raw WAV bytes (legacy path, no out-of-band fetch)."""
    if SP.queue is not None and wav:
        SP.queue.put(wav)


def stream_play_enqueue_future(future):
    """Enqueue a Future that will resolve to WAV bytes (out-of-band path)."""
    if SP.queue is not None and future is not None:
        SP.queue.put(future)


def fetch_audio_async(url: str, token: str):
    """
    Submit a parallel HTTP GET for an audio chunk. Returns a Future that
    yields the raw WAV bytes when the fetch completes.
    """
    if SP.fetch_pool is None:
        return None

    def _fetch():
        try:
            import requests
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "audio/wav",
                         "Accept-Encoding": "identity"},
                timeout=30,
            )
            r.raise_for_status()
            return r.content
        except Exception as e:
            raise RuntimeError(f"audio fetch {url} failed: {e}")

    return SP.fetch_pool.submit(_fetch)


def stream_play_stop(wait: bool = True):
    """Tell the worker to drain the queue and exit."""
    if SP.queue is not None:
        SP.queue.put(None)
    if wait and SP.thread is not None:
        SP.thread.join(timeout=30)
    if SP.fetch_pool is not None:
        SP.fetch_pool.shutdown(wait=False, cancel_futures=True)
    SP.queue = None
    SP.thread = None
    SP.fetch_pool = None
    SP.started = False


# ────────────────────────────────────────────────────────────────────────────
#  REPL loops
# ────────────────────────────────────────────────────────────────────────────

def render_chat_reply(reply: dict) -> str:
    if not reply.get("ok", True):
        return f"[error] {reply.get('error', '?')}"
    return reply.get("response") or reply.get("message") or ""


def text_loop(host: str, token: str):
    print(f"\nJARVIS @ {host}  (text mode — no audio)")
    print("Type a message, or 'quit' to exit.\n")
    while True:
        try:
            text = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text.lower() in {"quit", "exit", "bye"}:
            return
        wall, reply = http_post_json(f"{host}/api/chat", {"text": text}, token)
        print(f"jarvis ◂ {render_chat_reply(reply)}")
        print(f"        ({wall:.2f}s)\n")


def voice_loop_stream(host: str, token: str, no_play: bool, auto: bool,
                      silence_seconds: float = 0.7):
    """
    Streaming voice loop: hits /api/voice/stream and plays each sentence as
    its audio arrives, instead of waiting for the full reply.

    Time-to-first-audio is the metric that matters for "feels responsive".
    On the same Jetson + same query, this loop hears the first word ~10s
    sooner than the non-streaming /api/voice loop because:
      - the LLM response field starts streaming as soon as the classifier
        emits its first sentence (instead of waiting for the full JSON)
      - Kokoro starts synthesizing that sentence while the LLM is still
        generating the next one
      - the WAV reaches the Mac mid-stream and `afplay` starts immediately
    """
    print(f"\nJARVIS @ {host}  (voice mode — STREAMING)")
    print("Mac mic → Jetson STT/LLM/TTS → SSE → Mac speaker, sentence-by-sentence.")
    print("Ctrl+C to exit.\n")
    while True:
        try:
            wav = record_vad(silence_seconds=silence_seconds) if auto else record_push_to_talk()
        except (EOFError, KeyboardInterrupt):
            print()
            stop_playback()
            stream_play_stop(wait=False)
            return

        if len(wav) < 4096:
            sys.stderr.write("(too short)\n")
            continue

        sys.stderr.write(f"  uploading {len(wav)/1024:.1f} KB to {host}/api/voice/stream ...\n")
        sys.stderr.flush()

        # Fresh playback queue per turn so a previous turn's tail can't bleed in
        if not no_play:
            stream_play_start()

        first_audio_wall = None
        first_token_server_ms = None
        sent_count = 0
        transcribed = ""
        wall_start = time.time()

        # Iterate the SSE stream defensively — if the Jetson goes down or
        # restarts mid-conversation, we don't want to crash the whole loop.
        # Catch the connection error, classify it, tell the user clearly,
        # and loop back to the next prompt instead of dying.
        sse_iter = http_post_audio_stream(
            f"{host}/api/voice/stream", wav, token,
        )
        try:
            event_iter = iter(sse_iter)
        except Exception as e:
            sys.stderr.write(f"\n  [error] couldn't open SSE stream: {e}\n")
            if not no_play:
                stream_play_stop(wait=False)
            continue

        try:
            while True:
                try:
                    event, data, t_off = next(event_iter)
                except StopIteration:
                    break
                except (KeyboardInterrupt, EOFError):
                    raise
                except Exception as e:
                    kind, msg = _classify_connection_error(e) if hasattr(
                        sys.modules[__name__], "_classify_connection_error"
                    ) else ("other", str(e))
                    sys.stderr.write(
                        f"\n  [error] connection lost mid-turn ({kind}): {msg}\n"
                        f"  Will retry on next prompt.\n"
                    )
                    break

                if event == "transcribed":
                    transcribed = data.get("text", "")
                    print(f"\nyou ▸ {transcribed}")
                    sys.stderr.write(
                        f"  [stt] {data.get('stt_ms', 0):.0f}ms "
                        f"(\"{transcribed[:60]}\")\n"
                    )
                elif event == "response_text":
                    txt = data.get("text", "")
                    if sent_count == 0:
                        print("jarvis ◂ ", end="", flush=True)
                    print(txt, end=" ", flush=True)
                    sent_count += 1
                elif event == "audio_chunk":
                    # Two paths for forward/backward compat:
                    #   - new server: `url` (+ chunk_id) — fetch out-of-band
                    #   - old server: `wav_b64` — decode inline
                    if not no_play:
                        if first_audio_wall is None:
                            first_audio_wall = t_off
                            sys.stderr.write(
                                f"\n  ▶ first audio (announced) at {first_audio_wall:.2f}s "
                                f"(sentence {data.get('index', 0)}, "
                                f"{data.get('bytes', '?')} bytes)\n"
                            )
                        url = data.get("url")
                        if url:
                            full_url = url if url.startswith("http") else f"{host}{url}"
                            future = fetch_audio_async(full_url, token)
                            stream_play_enqueue_future(future)
                        else:
                            wav_b64 = data.get("wav_b64")
                            if wav_b64:
                                stream_play_enqueue(base64.b64decode(wav_b64))
                elif event == "done":
                    print()
                    t = data.get("timings", {}) or {}
                    wall = time.time() - wall_start
                    msg = (
                        f"  [done] wall {wall:.2f}s | "
                        f"stt {t.get('stt_ms', 0):.0f}ms | "
                        f"first_token {t.get('first_token_ms', 0):.0f}ms | "
                        f"first_audio {t.get('first_audio_ms', 0):.0f}ms | "
                        f"total {t.get('total_ms', 0):.0f}ms"
                    )
                    sys.stderr.write(msg + "\n")
                    if first_audio_wall is not None:
                        sys.stderr.write(
                            f"  [client] first audio (Mac wall): {first_audio_wall:.2f}s\n"
                        )
                elif event == "error":
                    print(f"\n  [error] {data.get('message', data)}")
        except (KeyboardInterrupt, EOFError):
            sys.stderr.write("\n[interrupted]\n")
            stop_playback()
            stream_play_stop(wait=False)
            return

        # Wait for queued audio to finish playing before next prompt
        if not no_play:
            stream_play_stop(wait=True)
        print()


def voice_loop(host: str, token: str, no_play: bool, auto: bool,
               silence_seconds: float = 0.7):
    print(f"\nJARVIS @ {host}  (voice mode — Mac mic, Jetson brain, Mac speaker)")
    print("Ctrl+C to exit.\n")
    while True:
        try:
            wav = record_vad(silence_seconds=silence_seconds) if auto else record_push_to_talk()
        except (EOFError, KeyboardInterrupt):
            print()
            stop_playback()
            return

        if len(wav) < 4096:
            sys.stderr.write("(too short)\n")
            continue

        sys.stderr.write(f"  uploading {len(wav)/1024:.1f} KB to {host}/api/voice ...\n")
        sys.stderr.flush()

        wall, resp = http_post_audio(f"{host}/api/voice", wav, token)
        if not resp.get("ok"):
            print(f"  [error] {resp.get('error', resp)}\n")
            continue

        timings = resp.get("timings") or {}
        stt = timings.get("stt_ms", 0)
        pipe = timings.get("pipeline_ms", 0)
        tts = timings.get("tts_ms", 0)
        total_server = timings.get("total_ms", 0)
        net = max(0, wall * 1000 - total_server)

        print(f"\nyou ▸ {resp.get('transcribed', '(silence)')}")
        print(f"jarvis ◂ {resp.get('response', '')}")
        print(
            f"        wall {wall:.2f}s = "
            f"stt {stt:.0f}ms + pipeline {pipe:.0f}ms + tts {tts:.0f}ms + net+upload {net:.0f}ms"
        )

        audio_b64 = resp.get("audio_b64")
        if audio_b64 and not no_play:
            audio_wav = base64.b64decode(audio_b64)
            sys.stderr.write(f"  ▶ playing {len(audio_wav)/1024:.1f} KB\n")
            play_wav_bytes(audio_wav)
        elif not audio_b64:
            sys.stderr.write("  (no audio in response — TTS may be disabled)\n")
        print()


# ────────────────────────────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Mac mic+speaker bridge to JARVIS Jetson.")
    p.add_argument("--text", action="store_true", help="text REPL via /api/chat (no audio)")
    p.add_argument("--voice", action="store_true", help="voice mode: Mac mic+speaker bridged to /api/voice")
    p.add_argument("--stream", action="store_true",
                   help="with --voice: use SSE /api/voice/stream and play each sentence as it arrives "
                        "(much lower time-to-first-audio)")
    p.add_argument("--auto", action="store_true", help="with --voice: VAD silence-stop instead of press-to-talk")
    p.add_argument("--silence", type=float, default=0.7,
                   help="with --voice --auto: seconds of silence before auto-stop "
                        "(default 0.7s, matches Alexa/Google/Siri range; raise to "
                        "1.0-1.5 if you naturally pause mid-sentence)")
    p.add_argument("--no-play", action="store_true", help="don't play the TTS audio response (text only)")
    p.add_argument("--host", default=DEFAULT_HOST, help="JARVIS host (default $JARVIS_HOST or http://192.168.1.8:8766)")
    p.add_argument("--token", default=DEFAULT_TOKEN, help="API token (default $JARVIS_TOKEN)")
    args = p.parse_args()

    if not args.token:
        sys.stderr.write("ERROR: no API token. Set $JARVIS_TOKEN or pass --token. "
                         "Get the current token with:\n"
                         "  ssh devesh@192.168.1.8 'grep \"API token\" /tmp/jarvis.log | tail -1'\n")
        sys.exit(2)

    # Connection pre-flight with retry + friendly errors. When the Jetson is
    # off (power outage, reboot, etc.) we wait up to ~10 seconds for it to
    # come back rather than failing immediately, and we tell the user which
    # specific failure mode they're seeing rather than a raw stacktrace.
    if not _wait_for_server(args.host, args.token, timeout=10.0):
        sys.exit(1)

    try:
        if args.voice:
            if args.stream:
                voice_loop_stream(args.host, args.token, args.no_play,
                                  args.auto, silence_seconds=args.silence)
            else:
                voice_loop(args.host, args.token, args.no_play,
                           args.auto, silence_seconds=args.silence)
        else:
            text_loop(args.host, args.token)
    finally:
        stop_playback()
        if SP.started:
            stream_play_stop(wait=False)


if __name__ == "__main__":
    main()
