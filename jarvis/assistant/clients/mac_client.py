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


def record_vad(silence_seconds: float = 1.5, max_seconds: float = 12.0) -> bytes:
    """Auto-stop after silence_seconds of silence. Returns WAV bytes."""
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


def voice_loop(host: str, token: str, no_play: bool, auto: bool):
    print(f"\nJARVIS @ {host}  (voice mode — Mac mic, Jetson brain, Mac speaker)")
    print("Ctrl+C to exit.\n")
    while True:
        try:
            wav = record_vad() if auto else record_push_to_talk()
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
    p.add_argument("--auto", action="store_true", help="with --voice: VAD silence-stop instead of press-to-talk")
    p.add_argument("--no-play", action="store_true", help="don't play the TTS audio response (text only)")
    p.add_argument("--host", default=DEFAULT_HOST, help="JARVIS host (default $JARVIS_HOST or http://192.168.1.8:8766)")
    p.add_argument("--token", default=DEFAULT_TOKEN, help="API token (default $JARVIS_TOKEN)")
    args = p.parse_args()

    if not args.token:
        sys.stderr.write("ERROR: no API token. Set $JARVIS_TOKEN or pass --token. "
                         "Get the current token with:\n"
                         "  ssh devesh@192.168.1.8 'grep \"API token\" /tmp/jarvis.log | tail -1'\n")
        sys.exit(2)

    try:
        s = http_get(f"{args.host}/api/system/status", args.token)
        sys.stderr.write(
            f"[mac_client] connected to {s.get('name','?')} v{s.get('version','?')}, "
            f"personality={s.get('personality','?')}, uptime={s.get('uptime_seconds','?')}s\n"
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: can't reach {args.host}: {e}\n")
        sys.exit(1)

    try:
        if args.voice:
            voice_loop(args.host, args.token, args.no_play, args.auto)
        else:
            text_loop(args.host, args.token)
    finally:
        stop_playback()


if __name__ == "__main__":
    main()
