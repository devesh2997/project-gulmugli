#!/usr/bin/env python3
"""
test_audio.py — end-to-end audio smoke test.

## Why

On the May 14 birthday-launch hardware (Marshall Willen II BT speaker +
USB conference mic on a Jetson Orin Nano), audio is the single most
fragile dependency. The wake word, voice intents, and music playback
ALL fail silently if the speaker/mic chain isn't right. This tool gives
the operator a 30-second smoke test that proves:

  Phase A. Output works
    - The right speaker is selected as the default sink.
    - A 3-second 440Hz tone is audible out of it.

  Phase B. Input works
    - The configured USB mic is recognized.
    - Recording captures real energy (live RMS bar during capture).
    - The recording can be played back through Phase A's output.

  Phase C. Summary
    - Single-glance pass/fail summary so day-of operators don't
      have to interpret subtle log output.

## Usage

    cd jarvis/assistant
    python tools/test_audio.py                       # full A + B + C
    python tools/test_audio.py --output-only         # skip mic
    python tools/test_audio.py --input-only          # skip tone
    python tools/test_audio.py --device-output NAME  # force output sink/device
    python tools/test_audio.py --device-input NAME   # force input device
    python tools/test_audio.py --debug               # show tracebacks

## Exit codes

  0 — every active phase passed
  1 — one or more phases failed (or hardware unavailable)
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import threading
import time
import traceback
import wave
from pathlib import Path

# Bring assistant/ onto the path so we can import core/* and providers/*.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config  # noqa: E402
from core.logger import get_logger  # noqa: E402

log = get_logger("tools.test_audio")


# ── Output helpers ──────────────────────────────────────────────────

_USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


GREEN = _c("\033[32m")
RED = _c("\033[31m")
YELLOW = _c("\033[33m")
CYAN = _c("\033[36m")
DIM = _c("\033[2m")
BOLD = _c("\033[1m")
RESET = _c("\033[0m")


def _say(msg: str = "") -> None:
    print(msg, flush=True)


def _ok(msg: str) -> None:
    _say(f"{GREEN}✓{RESET} {msg}")


def _warn(msg: str) -> None:
    _say(f"{YELLOW}!{RESET} {msg}")


def _err(msg: str) -> None:
    _say(f"{RED}✗ {msg}{RESET}")


def _ask_yn(prompt: str) -> bool:
    """y/n prompt that never times out. Empty → 'n' (be conservative)."""
    while True:
        ans = input(f"{prompt} [y/n] ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            return False
        _warn("Please answer y or n.")


# ── Audio provider resolution ───────────────────────────────────────


def _resolve_audio_provider_name() -> str | None:
    """
    Mirrors main._resolve_audio_provider — we duplicate it here so the
    tool runs standalone without booting the assistant. Cheap helper, no
    config dependency.
    """
    import platform as _platform
    import shutil as _shutil

    if _platform.system() == "Darwin":
        return "coreaudio"
    if _shutil.which("pactl"):
        return "pulseaudio"
    if _shutil.which("amixer"):
        return "alsa"
    return None


def _get_audio_provider():
    """Returns the AudioOutputProvider instance, or None if none works here."""
    audio_cfg = config.get("audio", {}) or {}
    name = audio_cfg.get("provider", "auto")
    if name in (None, "", "auto"):
        name = _resolve_audio_provider_name()
    if not name:
        return None

    try:
        # Importing providers triggers @register decorators.
        import providers  # noqa: F401
        from core.registry import get_provider
        prov = get_provider("audio", name)
        if prov.is_available():
            return prov
        log.debug("Audio provider %s reports is_available()=False", name)
        return None
    except Exception as e:
        log.debug("Failed to load audio provider %s: %s", name, e)
        return None


# ── Phase A: Output ─────────────────────────────────────────────────


def _make_sine_tone(freq_hz: float = 440.0, duration_s: float = 3.0,
                    samplerate: int = 44100, amplitude: float = 0.3):
    """
    Generate a sine tone as a numpy float32 array. Amplitude 0.3 (about
    -10 dBFS) is intentionally conservative — loud enough to verify
    audio, quiet enough not to startle anyone or blow a speaker on max.
    """
    import numpy as np  # local import: numpy load is ~50ms, only when needed
    t = np.linspace(0.0, duration_s, int(samplerate * duration_s), endpoint=False)
    tone = amplitude * np.sin(2.0 * np.pi * freq_hz * t).astype("float32")
    # 50ms fade-in / fade-out to avoid the click at start/end (clipping ramp)
    fade = int(0.05 * samplerate)
    if fade * 2 < len(tone):
        ramp = np.linspace(0.0, 1.0, fade, dtype="float32")
        tone[:fade] *= ramp
        tone[-fade:] *= ramp[::-1]
    return tone, samplerate


def _resolve_output_device(override: str | None):
    """
    Return a sounddevice output device index, or None to mean 'system default'.

    If override is provided, find an output device whose name contains
    it (case-insensitive). If no match, warn and fall back to default.
    """
    if not override:
        return None
    try:
        import sounddevice as sd  # type: ignore
    except (ImportError, OSError) as e:
        _err(f"sounddevice is not available: {e}")
        return None
    devices = sd.query_devices()
    needle = override.lower()
    for i, d in enumerate(devices):
        if d.get("max_output_channels", 0) > 0 and needle in d["name"].lower():
            return i
    _warn(f"No output device matched '{override}'. Falling back to system default.")
    return None


def _phase_a_output(audio_provider, override: str | None) -> bool:
    """Phase A: list outputs, expected check, play a tone, prompt y/n."""
    _say(f"\n{BOLD}── Phase A. Output ──{RESET}")

    # List the outputs the AudioOutputProvider knows about (sinks/sources).
    if audio_provider is not None:
        try:
            outputs = audio_provider.list_outputs()
        except Exception as e:
            log.debug("list_outputs() raised: %s", e)
            outputs = []
        if outputs:
            _say(f"{DIM}System audio outputs (via AudioOutputProvider):{RESET}")
            for o in outputs:
                marker = f" {GREEN}(active){RESET}" if o.get("active") else ""
                _say(f"  • {o['name']} {DIM}[{o.get('type', '?')}]{RESET}{marker}")
        else:
            _say(f"{DIM}AudioOutputProvider returned no sinks "
                 f"(or this platform has no system-level routing layer).{RESET}")
    else:
        _say(f"{DIM}No AudioOutputProvider available on this platform.{RESET}")

    # Check expected output from config.
    bt_cfg = (config.get("audio", {}) or {}).get("bluetooth", {}) or {}
    preferred_mac = bt_cfg.get("preferred_mac")
    expected_name = bt_cfg.get("device_name")
    if preferred_mac:
        label = expected_name or preferred_mac
        _say(f"\nExpected output: {BOLD}{label}{RESET} {DIM}({preferred_mac}){RESET}")
        # Convert MAC for sink name match: bluetoothd uses AA_BB_CC_DD_EE_FF in sinks.
        mac_key = preferred_mac.replace(":", "_").lower()
        active_match = False
        for o in outputs or []:
            if mac_key in o["name"].lower() and o.get("active"):
                active_match = True
                break
        if active_match:
            _ok("Expected speaker is the active sink.")
        elif outputs:
            _warn(
                "Expected speaker isn't the active sink. Voice/music will go "
                "to whatever IS active. Use `pactl set-default-sink <name>` "
                "or pair the speaker via tools/pair_bluetooth.py."
            )
    else:
        _say(f"{DIM}No `audio.bluetooth.preferred_mac` in config. "
             f"Playing through the system default output.{RESET}")

    # Sounddevice availability.
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # noqa: F401
    except (ImportError, OSError) as e:
        _err(f"sounddevice / numpy not available: {e}")
        _say(f"  Install with: {CYAN}pip install sounddevice numpy{RESET}")
        return False

    device_idx = _resolve_output_device(override)
    if device_idx is not None:
        try:
            info = sd.query_devices(device_idx)
            _say(f"Forced output device: {BOLD}{info['name']}{RESET} "
                 f"{DIM}(index {device_idx}){RESET}")
        except Exception:
            pass

    # Generate + play tone.
    _say(f"\n{CYAN}Playing a 3-second 440 Hz tone "
         f"(low-volume, with fade-in/out)...{RESET}")
    try:
        tone, sr = _make_sine_tone()
        sd.play(tone, samplerate=sr, device=device_idx, blocking=True)
    except Exception as e:
        _err(f"Couldn't play tone: {type(e).__name__}: {e}")
        return False

    heard = _ask_yn("Did you hear a 3-second tone?")
    if heard:
        _ok("Output works.")
        return True

    _err("Output did not produce audible sound.")
    _say(f"  {DIM}Things to check:")
    _say(f"  - Speaker powered on and not muted?")
    _say(f"  - BT speaker connected? Run: python tools/pair_bluetooth.py")
    _say(f"  - System volume audible? `pactl set-sink-volume @DEFAULT_SINK@ 70%`")
    _say(f"  - Right sink selected? `pactl list sinks short` shows RUNNING on the wrong one?{RESET}")
    return False


# ── Phase B: Input ──────────────────────────────────────────────────


def _list_input_devices():
    """
    Fallback to `sd.query_devices()` for input listing, since the
    AudioOutputProvider doesn't expose mic enumeration yet (a parallel
    agent is adding `list_inputs()` — when that lands we should prefer it).
    """
    try:
        import sounddevice as sd  # type: ignore
    except (ImportError, OSError):
        return []
    out = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append({
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                })
    except Exception as e:
        log.debug("query_devices failed: %s", e)
    return out


def _resolve_input_device(override: str | None):
    """
    Resolve which input device to record from.

    Priority:
      1. --device-input <NAME> override (substring, case-insensitive)
      2. config.audio.input.device_name_pattern (substring)
      3. system default
    """
    pattern = override
    if not pattern:
        in_cfg = (config.get("audio", {}) or {}).get("input", {}) or {}
        pattern = in_cfg.get("device_name_pattern")

    devices = _list_input_devices()
    if pattern:
        needle = pattern.lower()
        for d in devices:
            if needle in d["name"].lower():
                return d["index"], d["name"]
        _warn(f"No input device matched '{pattern}'. Falling back to system default.")

    # System default
    try:
        import sounddevice as sd  # type: ignore
        default = sd.query_devices(kind="input")
        return None, default["name"]
    except Exception:
        return None, "(system default)"


def _phase_b_input(audio_provider, output_override: str | None,
                   input_override: str | None) -> bool:
    """Phase B: list inputs, record 5s with live RMS bar, replay through Phase A output."""
    _say(f"\n{BOLD}── Phase B. Input ──{RESET}")

    devices = _list_input_devices()
    if not devices:
        _err("No input (microphone) devices found.")
        _say(f"  {DIM}Plug in the USB mic and re-run.{RESET}")
        return False

    _say(f"{DIM}Input devices visible to sounddevice:{RESET}")
    for d in devices:
        _say(f"  • [{d['index']}] {d['name']} {DIM}({d['channels']} ch){RESET}")

    dev_idx, dev_name = _resolve_input_device(input_override)
    _say(f"\nWill record from: {BOLD}{dev_name}{RESET}"
         + (f" {DIM}(index {dev_idx}){RESET}" if dev_idx is not None else f" {DIM}(system default){RESET}"))

    input(f"\nAbout to record {BOLD}5 seconds{RESET}. Speak loudly when prompted. "
          f"Press Enter when ready... ")

    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore
    except (ImportError, OSError) as e:
        _err(f"sounddevice / numpy not available: {e}")
        return False

    # Record in a streaming fashion so we can render the RMS bar live.
    # We use an InputStream + callback, same pattern as core/mic.py, so the
    # bar updates from the audio thread but display happens on the main thread.
    sample_rate = 16000
    duration = 5.0
    chunk_ms = 100
    chunk_samples = int(sample_rate * chunk_ms / 1000.0)

    captured: list = []
    rms_history: list[float] = []
    lock = threading.Lock()
    done = threading.Event()
    speech_seen = False

    def cb(indata, frame_count, time_info, status):
        nonlocal speech_seen
        if status:
            log.debug("Input stream status: %s", status)
        chunk = indata.copy()
        captured.append(chunk)
        flat = chunk[:, 0] if chunk.ndim > 1 else chunk
        rms = float(np.sqrt(np.mean(flat.astype("float32") ** 2)))
        with lock:
            rms_history.append(rms)
            if rms > 200:
                speech_seen = True

    _say(f"\n{CYAN}Recording...{RESET} {DIM}(speak now!){RESET}")

    try:
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=dev_idx,
            callback=cb,
            blocksize=chunk_samples,
        )
    except Exception as e:
        _err(f"Couldn't open input stream: {type(e).__name__}: {e}")
        _say(f"  {DIM}Common causes: device in use, permissions denied, "
             f"sample rate unsupported by device.{RESET}")
        return False

    # Live RMS bar — one block per ~100ms chunk. Re-uses the technique from
    # core/mic.py's record_smart() — energy-based, no extra deps.
    start = time.time()
    last_drawn = 0
    bar_chars = "▁▂▃▄▅▆▇█"
    try:
        with stream:
            while not done.is_set():
                elapsed = time.time() - start
                if elapsed >= duration:
                    break
                with lock:
                    n = len(rms_history)
                if n > last_drawn:
                    for r in rms_history[last_drawn:n]:
                        # Map RMS [0, 5000] → 0..7
                        idx = min(7, int(r / 700))
                        sys.stdout.write(bar_chars[idx])
                        sys.stdout.flush()
                    last_drawn = n
                time.sleep(0.03)
    except Exception as e:
        _err(f"\nRecording interrupted: {type(e).__name__}: {e}")
        return False
    finally:
        sys.stdout.write("\n")
        sys.stdout.flush()

    if not captured:
        _err("No audio frames captured.")
        return False

    audio = np.concatenate(captured, axis=0)
    duration_actual = len(audio) / sample_rate
    overall_rms = float(np.sqrt(np.mean(audio.astype("float32") ** 2)))

    _say(f"{DIM}Captured {duration_actual:.1f}s, overall RMS {overall_rms:.0f}, "
         f"speech_seen={speech_seen}{RESET}")

    if overall_rms < 30:
        _warn("Very low energy in the recording — mic might be muted, "
              "unplugged, or pointing the wrong way.")

    # Save to a WAV file and replay it via core.audio_playback.
    tmp = Path(tempfile.gettempdir()) / "vesper_audio_test.wav"
    try:
        with wave.open(str(tmp), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
    except Exception as e:
        _err(f"Couldn't write WAV: {e}")
        return False

    _say(f"\n{CYAN}Playing the recording back...{RESET}")
    # Prefer sounddevice playback through the same output device override so
    # we exercise the EXACT same chain as the tone. Falls back to
    # core.audio_playback (afplay/paplay) if sounddevice playback errors out.
    out_dev_idx = _resolve_output_device(output_override)
    played = False
    try:
        # WAV is int16 mono — sounddevice can play raw arrays directly.
        sd.play(audio, samplerate=sample_rate, device=out_dev_idx, blocking=True)
        played = True
    except Exception as e:
        log.debug("sd.play(raw) failed, falling back to play_file: %s", e)
        try:
            from core.audio_playback import play_file
            played = play_file(tmp, blocking=True, timeout_s=10)
        except Exception as e2:
            log.debug("play_file fallback failed: %s", e2)

    if not played:
        _err("Couldn't play the recording back.")
        return False

    heard = _ask_yn("Did you hear yourself clearly?")
    if heard:
        _ok("Input works.")
        return True

    _err("Recording wasn't clearly audible.")
    _say(f"  {DIM}Things to check:")
    _say(f"  - Mic close enough? USB conference mics expect ~50cm; lapel mics ~10cm.")
    _say(f"  - Mic gain reasonable? `pactl list sources` shows the volume.")
    _say(f"  - Recording RMS was {overall_rms:.0f} — under 50 means near-silence.")
    _say(f"  - Right input device? Re-run with --device-input <substring>.{RESET}")
    return False


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description="End-to-end audio smoke test for the Vesper assistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tools/test_audio.py\n"
            "  python tools/test_audio.py --output-only\n"
            "  python tools/test_audio.py --input-only\n"
            "  python tools/test_audio.py --device-output 'Marshall'\n"
            "  python tools/test_audio.py --device-input 'USB'\n"
        ),
    )
    p.add_argument("--output-only", action="store_true",
                   help="Skip the microphone test (Phase B).")
    p.add_argument("--input-only", action="store_true",
                   help="Skip the tone playback (Phase A).")
    p.add_argument("--device-output", metavar="NAME",
                   help="Override output device (substring, case-insensitive).")
    p.add_argument("--device-input", metavar="NAME",
                   help="Override input device (substring, case-insensitive).")
    p.add_argument("--debug", action="store_true",
                   help="Show full tracebacks on errors.")
    args = p.parse_args()

    if args.output_only and args.input_only:
        _err("--output-only and --input-only are mutually exclusive.")
        return 1

    _say(f"\n{BOLD}🎙  Vesper audio smoke test{RESET}")
    _say(f"{DIM}Run with --help for options.{RESET}")

    audio_provider = _get_audio_provider()

    output_pass = None  # None = skipped, True/False = ran
    input_pass = None

    try:
        if not args.input_only:
            output_pass = _phase_a_output(audio_provider, args.device_output)
        if not args.output_only:
            input_pass = _phase_b_input(audio_provider, args.device_output, args.device_input)
    except KeyboardInterrupt:
        _say(f"\n{YELLOW}Interrupted.{RESET}")
        return 1
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        _err(f"Unexpected error: {type(e).__name__}: {e}")
        _say(f"{DIM}(rerun with --debug for the full traceback){RESET}")
        return 1

    # Phase C: summary
    _say(f"\n{BOLD}── Summary ──{RESET}")
    if output_pass is None:
        _say(f"  {DIM}- Output: skipped (--input-only){RESET}")
    elif output_pass:
        _say(f"  {GREEN}✓{RESET} Output works")
    else:
        _say(f"  {RED}✗ Output failed{RESET}")
    if input_pass is None:
        _say(f"  {DIM}- Input:  skipped (--output-only){RESET}")
    elif input_pass:
        _say(f"  {GREEN}✓{RESET} Input works")
    else:
        _say(f"  {RED}✗ Input failed{RESET}")
    _say("")

    ran = [r for r in (output_pass, input_pass) if r is not None]
    if not ran:
        # Both phases skipped — nothing tested. That's a misuse.
        _warn("Nothing was tested. Remove --output-only / --input-only flags.")
        return 1
    return 0 if all(ran) else 1


if __name__ == "__main__":
    sys.exit(main())
