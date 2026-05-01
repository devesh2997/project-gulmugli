"""
Audio Quality Check — non-interactive version.

Same checks as check_audio_quality.py but uses timed countdowns instead of
ENTER prompts. So it can be run from a non-interactive shell.

Records:
  - 3 seconds of silence (noise floor)
  - 12 seconds of speech (read the prompt aloud when "RECORDING" appears)
"""

import sys
import time
import wave
import math
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 24000
CHANNELS = 1
DURATION = 12
OUTPUT_DIR = Path(__file__).parent / "quality_check"
OUTPUT_DIR.mkdir(exist_ok=True)

# Force a specific input device by substring match (case-insensitive).
# Set via env var: AUDIO_INPUT_DEVICE="earpods"  or "macbook"  or ""
import os
PREFERRED_DEVICE_HINT = os.environ.get("AUDIO_INPUT_DEVICE", "").lower()


def beep(freq=880, duration=0.15, volume=0.3):
    """Play a sine-wave beep through the default output device."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = (np.sin(2 * np.pi * freq * t) * volume).astype(np.float32)
    try:
        sd.play(tone, SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass


def pick_input_device():
    """Pick input device by env var hint, else default."""
    devices = sd.query_devices()
    if PREFERRED_DEVICE_HINT:
        for i, d in enumerate(devices):
            if (d["max_input_channels"] > 0
                    and PREFERRED_DEVICE_HINT in d["name"].lower()):
                return i, d["name"]
    default = sd.query_devices(kind="input")
    return None, default["name"]


def main():
    print("=" * 60, flush=True)
    print("  AUDIO QUALITY CHECK (auto + audio cues)", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    print("WHAT YOU'LL HEAR:", flush=True)
    print("  • 1 long BEEP  → Silence test starting (stay quiet 3s)", flush=True)
    print("  • 2 short BEEPS → SPEAK NOW for 12s, read this aloud:", flush=True)
    print(flush=True)
    print('     "Hey, so I\'ve been working on this voice assistant project.', flush=True)
    print('      It\'s called Jarvis, and the idea is that it runs completely', flush=True)
    print('      locally on a Jetson Orin Nano. Pretty cool, right?"', flush=True)
    print(flush=True)
    print("  • 1 long BEEP  → Recording done. Analysis follows.", flush=True)
    print(flush=True)

    # Device selection
    device_idx, device_name = pick_input_device()
    print(f"Input device: {device_name}", flush=True)
    print(flush=True)

    if device_idx is not None:
        sd.default.device = (device_idx, None)

    print("Available input devices for reference:", flush=True)
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            marker = "  <-- USING" if (device_idx is None and d["name"] == device_name) or i == device_idx else ""
            print(f"  [{i}] {d['name']}{marker}", flush=True)
    print(flush=True)
    print("Starting in 5 seconds — get ready...", flush=True)
    time.sleep(5)

    # ── Phase 1: Silence (long beep) ──
    print("\n🔔 SILENCE TEST — stay quiet (3s)", flush=True)
    beep(440, 0.4)  # long low beep
    silence = sd.rec(int(3 * SAMPLE_RATE),
                     samplerate=SAMPLE_RATE,
                     channels=CHANNELS,
                     dtype="float32")
    sd.wait()
    silence = silence.flatten()

    # Brief pause between phases
    time.sleep(1.5)

    # ── Phase 2: Speech (announce paragraph aloud, then beep) ──
    PROMPT_TEXT = (
        "Hey, so I've been working on this voice assistant project. "
        "It's called Jarvis, and the idea is that it runs completely "
        "locally on a Jetson Orin Nano. Pretty cool, right?"
    )
    print("\n📢 Now I'll read the paragraph aloud — listen, then repeat it after the two beeps.", flush=True)
    print(f'\n   "{PROMPT_TEXT}"\n', flush=True)
    # Use macOS `say` to read the paragraph through the speakers/EarPods
    import subprocess
    try:
        # `-r 180` is a comfortable reading speed
        subprocess.run(["say", "-r", "180", PROMPT_TEXT], timeout=15)
    except Exception:
        pass
    time.sleep(0.5)

    print(f"🔔🔔 SPEAK NOW — repeat the paragraph ({DURATION}s)", flush=True)
    beep(880, 0.12)
    time.sleep(0.08)
    beep(880, 0.12)
    speech = sd.rec(int(DURATION * SAMPLE_RATE),
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32")
    sd.wait()
    speech = speech.flatten()

    # End signal
    beep(440, 0.4)
    print("\n✓ Recording done. Analyzing...", flush=True)
    print(flush=True)

    # ── Analysis ──
    print("=" * 60, flush=True)
    print("  ANALYSIS", flush=True)
    print("=" * 60, flush=True)

    issues = []
    warnings = []

    # Noise floor
    noise_rms = np.sqrt(np.mean(silence ** 2))
    noise_db = 20 * math.log10(max(noise_rms, 1e-10))
    print(f"\n[1] Background noise: {noise_db:.1f} dB", flush=True)
    if noise_db > -30:
        issues.append(f"Very high background noise ({noise_db:.1f} dB)")
        print(f"    ❌ TOO NOISY", flush=True)
    elif noise_db > -40:
        warnings.append(f"Moderate background noise ({noise_db:.1f} dB)")
        print(f"    ⚠️  MODERATE — acceptable but could be quieter", flush=True)
    else:
        print(f"    ✅ EXCELLENT", flush=True)

    # Speech level
    speech_rms = np.sqrt(np.mean(speech ** 2))
    speech_db = 20 * math.log10(max(speech_rms, 1e-10))
    speech_peak = np.max(np.abs(speech))
    speech_peak_db = 20 * math.log10(max(speech_peak, 1e-10))
    print(f"\n[2] Speech level: RMS {speech_db:.1f} dB | Peak {speech_peak_db:.1f} dB", flush=True)
    if speech_db < -35:
        issues.append("Speech too quiet — move closer to mic")
        print(f"    ❌ TOO QUIET", flush=True)
    elif speech_db < -25:
        warnings.append("Speech a bit quiet")
        print(f"    ⚠️  A BIT QUIET", flush=True)
    else:
        print(f"    ✅ GOOD", flush=True)

    # SNR
    snr = speech_db - noise_db
    print(f"\n[3] Signal-to-noise ratio: {snr:.1f} dB", flush=True)
    if snr < 15:
        issues.append(f"Poor SNR ({snr:.1f} dB)")
        print(f"    ❌ POOR — speech and noise too close", flush=True)
    elif snr < 25:
        warnings.append(f"Moderate SNR ({snr:.1f} dB)")
        print(f"    ⚠️  ACCEPTABLE", flush=True)
    else:
        print(f"    ✅ EXCELLENT", flush=True)

    # Clipping
    clipped = np.sum(np.abs(speech) > 0.98)
    clip_pct = (clipped / len(speech)) * 100
    print(f"\n[4] Clipping: {clipped} samples ({clip_pct:.3f}%)", flush=True)
    if clip_pct > 0.1:
        issues.append("Significant clipping — reduce mic volume or distance")
        print(f"    ❌ CLIPPING", flush=True)
    elif clip_pct > 0.01:
        warnings.append("Minor clipping detected")
        print(f"    ⚠️  MINOR", flush=True)
    else:
        print(f"    ✅ NONE", flush=True)

    # DC Offset
    dc = np.mean(speech)
    print(f"\n[5] DC offset: {dc:.6f}", flush=True)
    if abs(dc) > 0.01:
        warnings.append("DC offset present")
        print(f"    ⚠️  SLIGHT — fixable in preprocessing", flush=True)
    else:
        print(f"    ✅ CLEAN", flush=True)

    # Dynamic range
    frame_size = int(0.025 * SAMPLE_RATE)
    hop = int(0.01 * SAMPLE_RATE)
    energies = []
    for i in range(0, len(speech) - frame_size, hop):
        frame = speech[i:i + frame_size]
        e = np.sqrt(np.mean(frame ** 2))
        if e > noise_rms * 2:
            energies.append(20 * math.log10(max(e, 1e-10)))
    if energies:
        rng = max(energies) - min(energies)
        print(f"\n[6] Dynamic range: {rng:.1f} dB", flush=True)
        if rng < 10:
            warnings.append("Speech is very monotone")
            print(f"    ⚠️  MONOTONE — vary your delivery", flush=True)
        else:
            print(f"    ✅ NATURAL", flush=True)

    # Save WAV
    speech_int16 = (speech * 32767).astype(np.int16)
    filepath = OUTPUT_DIR / "quality_check.wav"
    with wave.open(str(filepath), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(speech_int16.tobytes())
    print(f"\nSaved: {filepath}", flush=True)

    # Summary
    print("\n" + "=" * 60, flush=True)
    if not issues and not warnings:
        print("  🎉 PERFECT — ready to record full session", flush=True)
    elif not issues:
        print("  👍 GOOD ENOUGH — minor warnings only:", flush=True)
        for w in warnings:
            print(f"     ⚠️  {w}", flush=True)
        print("  You can proceed with recording.", flush=True)
    else:
        print("  🛑 FIX BEFORE RECORDING:", flush=True)
        for i in issues:
            print(f"     ❌ {i}", flush=True)
        if warnings:
            print("  Also:", flush=True)
            for w in warnings:
                print(f"     ⚠️  {w}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
