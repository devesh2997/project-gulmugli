"""
Portable audio-file playback helper.

## Why this module exists

Several features need to play arbitrary WAV/MP3 files:
  - Phase 1 intro_runner (the launch sequence's recorded voice clips)
  - Phase 2 besura ("sing for me" — pre-recorded singing)
  - Phase 2 voice memos
  - Phase 3 sorry mode
  - Phase 4 joke laugh-clips

The existing audio path through `voice_router` is for synthesizing new
TTS — it doesn't take an arbitrary WAV file. The music provider takes
URLs, not local files. So we need a thin helper that picks the right
platform tool and plays a file.

## What it does

Detects which command-line player is available on the host
(`afplay` on macOS, `paplay`/`aplay`/`mpv` on Linux/Jetson) and uses
it via subprocess. Falls back gracefully if none are found —
returns False, logs a warning, never crashes the caller.

## What it deliberately does NOT do

  - Real-time audio focus / ducking — that's the AudioOutputProvider's
    job. If you want intro audio to duck music, call audio_focus.duck()
    before calling this.
  - Streaming playback — these are short pre-recorded clips. Files
    are played to completion (or abort on cancel), no chunked streaming.
  - Format conversion — WAV is preferred; MP3 works on platforms with
    a player that supports it (afplay, paplay both do).

## Cross-platform notes

  - macOS: `afplay` ships with the OS. Plays WAV/MP3/M4A. No flags needed.
  - Linux/Jetson with PulseAudio (the default on JetPack): `paplay` is
    the right call — it goes through the system mixer, respects volume
    settings, plays alongside other audio.
  - Linux without PulseAudio: `aplay` is the ALSA-direct option.
  - Last-resort fallback: `mpv --no-video --really-quiet`. Many systems
    have it (we use it for music).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger("audio_playback")


# ── Player discovery ────────────────────────────────────────────────

def _detect_player() -> Optional[tuple[str, list[str]]]:
    """
    Return (executable, base_args) for the best available player, or
    None if nothing is found.

    We prefer system-mixer-aware players (afplay, paplay) over direct
    hardware players (aplay) so background music keeps working when
    we play a clip on top.

    Order:
      1. afplay   — macOS native
      2. paplay   — PulseAudio (Linux/Jetson default)
      3. aplay    — ALSA direct (Linux fallback)
      4. mpv      — universal fallback
    """
    # afplay (macOS) — no special flags
    if shutil.which("afplay"):
        return ("afplay", [])
    # paplay (PulseAudio) — `--volume=65536` is 100%; we leave default
    # so user's system volume applies.
    if shutil.which("paplay"):
        return ("paplay", [])
    # aplay (ALSA) — `-q` keeps it quiet on stderr
    if shutil.which("aplay"):
        return ("aplay", ["-q"])
    # mpv — universal fallback. --no-terminal silences its UI;
    # --really-quiet drops log output; --no-video forces audio-only.
    if shutil.which("mpv"):
        return ("mpv", ["--no-terminal", "--really-quiet", "--no-video"])
    return None


# Cache the result — player set doesn't change at runtime, and detection
# spawns up to 4 subprocess.which calls. Resolved once on first use.
_cached_player: Optional[tuple[str, list[str]]] = None
_cache_lock = threading.Lock()


def _get_player() -> Optional[tuple[str, list[str]]]:
    global _cached_player
    with _cache_lock:
        if _cached_player is None:
            _cached_player = _detect_player()
            if _cached_player is None:
                log.warning(
                    "No audio player found on this system. "
                    "Tried: afplay, paplay, aplay, mpv. Audio-file "
                    "playback features will silently no-op until one is installed."
                )
            else:
                log.info("Audio playback player: %s", _cached_player[0])
        return _cached_player


# ── Public API ──────────────────────────────────────────────────────

def play_file(
    path: str | Path,
    *,
    blocking: bool = True,
    timeout_s: float = 120.0,
) -> bool:
    """
    Play an audio file via the best available system player.

    Args:
        path: WAV / MP3 / M4A file. Absolute or relative — relative is
              resolved against the current working directory, so callers
              should pass absolute paths.
        blocking: If True (default), wait for playback to finish before
                  returning. If False, fire-and-forget — the player
                  process is started and detached. Useful for "play
                  background ambience while other code runs."
        timeout_s: Maximum wall-clock seconds to wait when blocking=True.
                   A 30-second clip should never take 120s; the cap is a
                   safety net for hung subprocess. 0 = no timeout.

    Returns:
        True on success (or successful start in non-blocking mode),
        False on any failure — missing file, missing player, subprocess
        error. Errors are LOGGED, never raised — caller can chain calls
        without try/except wrappers.
    """
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        log.warning("Audio file not found: %s", file_path)
        return False

    player = _get_player()
    if player is None:
        # Already logged once at first detection.
        return False

    cmd = [player[0], *player[1], str(file_path)]

    try:
        if blocking:
            kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if timeout_s > 0:
                kwargs["timeout"] = timeout_s
            result = subprocess.run(cmd, **kwargs)  # type: ignore[arg-type]
            ok = result.returncode == 0
            if not ok:
                log.warning(
                    "Audio playback exited %d for %s",
                    result.returncode, file_path.name,
                )
            return ok
        else:
            # Fire-and-forget. The Popen handle goes out of scope, but
            # the process keeps running. Reaping happens on next OS
            # signal cycle — fine for our use case.
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
    except subprocess.TimeoutExpired:
        log.warning("Audio playback timed out after %.1fs for %s",
                    timeout_s, file_path.name)
        return False
    except FileNotFoundError as e:
        # Player vanished between detection and call — rare but possible.
        log.warning("Audio player binary missing: %s", e)
        return False
    except Exception as e:
        log.warning("Audio playback failed for %s: %s", file_path.name, e)
        return False


def is_available() -> bool:
    """True if any audio player is detectable on this host."""
    return _get_player() is not None
