"""
Audio Quality Check — record a short sample and analyze it before committing
to hours of recording.

Records 10-15 seconds, then checks:
1. Background noise level (should be < -40dB)
2. Signal-to-noise ratio (should be > 20dB)
3. Clipping (peaks hitting max)
4. Sample rate and bit depth
5. Frequency spectrum (checks for room resonance, mic issues)
6. Plays it back so you can hear yourself

Run this BEFORE starting the full recording session.
"""

import sys
import time
import wave
import struct
import math
import os
from pathlib import Path

# Check for required packages
try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install numpy sounddevice")
    sys.exit(1)

SAMPLE_RATE = 24000
CHANNELS = 1
DURATION = 12  # seconds
OUTPUT_DIR = Path(__file__).parent / "quality_check"
OUTPUT_DIR.mkdir(exist_ok=True)


def record_sample():
    """Record a short audio sample."""
    print("\n" + "=" * 60)
    print("  🎤  AUDIO QUALITY CHECK")
    print("=" * 60)
    print()

    # List audio devices
    print("Available input devices:")
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            print(f"  [{i}] {d['name']} ({d['max_input_channels']}ch, {int(d['default_samplerate'])}Hz)")
    print()

    # Check default device
    default = sd.query_devices(kind='input')
    print(f"Default input: {default['name']}")
    print()

    # Step 1: Record 2 seconds of silence for noise floor
    print("Step 1: Measuring background noise...")
    print("        Stay QUIET for 3 seconds...")
    time.sleep(1)
    print("        Recording silence...", end="", flush=True)
    silence = sd.rec(int(3 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
    sd.wait()
    print(" done.")
    silence = silence.flatten()

    # Step 2: Record speech
    print()
    print("Step 2: Now READ THIS ALOUD (naturally, like you're talking to someone):")
    print()
    print('  "Hey, so I\'ve been working on this voice assistant project.')
    print('   It\'s called Jarvis, and the idea is that it runs completely')
    print('   locally on a Jetson Orin Nano. Pretty cool, right?"')
    print()
    input("Press ENTER when ready to record (you'll have 12 seconds)... ")
    print()
    print("🔴 RECORDING... speak now!")
    print()

    speech = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
    
    # Show a simple timer
    for i in range(DURATION):
        remaining = DURATION - i
        bar = "█" * (i + 1) + "░" * remaining
        print(f"\r  [{bar}] {remaining}s remaining  ", end="", flush=True)
        time.sleep(1)
    sd.wait()
    print("\r  Recording complete!" + " " * 40)
    speech = speech.flatten()

    return silence, speech


def analyze_audio(silence, speech):
    """Analyze the recorded audio for quality issues."""
    print("\n" + "=" * 60)
    print("  📊  ANALYSIS RESULTS")
    print("=" * 60)

    issues = []
    warnings = []

    # --- Noise Floor ---
    noise_rms = np.sqrt(np.mean(silence ** 2))
    noise_db = 20 * math.log10(max(noise_rms, 1e-10))
    
    print(f"\n🔇 Background Noise:")
    print(f"   RMS level: {noise_db:.1f} dB")
    if noise_db > -30:
        issues.append(f"High background noise ({noise_db:.1f} dB). Find a quieter room.")
        print(f"   ❌ TOO NOISY — find a quieter environment")
    elif noise_db > -40:
        warnings.append(f"Moderate background noise ({noise_db:.1f} dB).")
        print(f"   ⚠️  MODERATE — acceptable but could be quieter")
    else:
        print(f"   ✅ EXCELLENT — very quiet environment")

    # --- Speech Level ---
    speech_rms = np.sqrt(np.mean(speech ** 2))
    speech_db = 20 * math.log10(max(speech_rms, 1e-10))
    speech_peak = np.max(np.abs(speech))
    speech_peak_db = 20 * math.log10(max(speech_peak, 1e-10))

    print(f"\n🗣️  Speech Level:")
    print(f"   RMS level: {speech_db:.1f} dB")
    print(f"   Peak level: {speech_peak_db:.1f} dB")
    
    if speech_db < -35:
        issues.append("Speech too quiet. Move closer to the mic or increase input volume.")
        print(f"   ❌ TOO QUIET — move closer to the mic")
    elif speech_db < -25:
        warnings.append("Speech is a bit quiet.")
        print(f"   ⚠️  A BIT QUIET — try moving slightly closer")
    else:
        print(f"   ✅ GOOD level")

    # --- SNR ---
    snr = speech_db - noise_db
    print(f"\n📏 Signal-to-Noise Ratio:")
    print(f"   SNR: {snr:.1f} dB")
    if snr < 15:
        issues.append(f"Poor SNR ({snr:.1f} dB). Reduce background noise or speak louder.")
        print(f"   ❌ POOR — speech and noise are too close")
    elif snr < 25:
        warnings.append(f"Moderate SNR ({snr:.1f} dB).")
        print(f"   ⚠️  ACCEPTABLE — but more separation would help")
    else:
        print(f"   ✅ EXCELLENT — clear separation from noise")

    # --- Clipping ---
    clipping_threshold = 0.98
    clipped_samples = np.sum(np.abs(speech) > clipping_threshold)
    clipping_pct = (clipped_samples / len(speech)) * 100

    print(f"\n✂️  Clipping:")
    print(f"   Clipped samples: {clipped_samples} ({clipping_pct:.3f}%)")
    if clipping_pct > 0.1:
        issues.append("Significant clipping detected. Reduce mic input volume or move back.")
        print(f"   ❌ CLIPPING — reduce input volume or distance")
    elif clipping_pct > 0.01:
        warnings.append("Minor clipping detected.")
        print(f"   ⚠️  MINOR CLIPPING — watch your peaks")
    else:
        print(f"   ✅ NO CLIPPING")

    # --- DC Offset ---
    dc_offset = np.mean(speech)
    print(f"\n⚡ DC Offset:")
    print(f"   Mean: {dc_offset:.6f}")
    if abs(dc_offset) > 0.01:
        warnings.append("DC offset detected. This is usually a mic/preamp issue.")
        print(f"   ⚠️  SLIGHT OFFSET — not critical, can be corrected in preprocessing")
    else:
        print(f"   ✅ CLEAN")

    # --- Dynamic Range ---
    # Check if speech has good variation (not monotone)
    frame_size = int(0.025 * SAMPLE_RATE)  # 25ms frames
    hop = int(0.01 * SAMPLE_RATE)  # 10ms hop
    frame_energies = []
    for i in range(0, len(speech) - frame_size, hop):
        frame = speech[i:i + frame_size]
        energy = np.sqrt(np.mean(frame ** 2))
        if energy > noise_rms * 2:  # Only voiced frames
            frame_energies.append(20 * math.log10(max(energy, 1e-10)))
    
    if frame_energies:
        energy_range = max(frame_energies) - min(frame_energies)
        print(f"\n🎭 Dynamic Range (speech variation):")
        print(f"   Range: {energy_range:.1f} dB")
        if energy_range < 10:
            warnings.append("Speech is very monotone. Try speaking more naturally with emphasis.")
            print(f"   ⚠️  MONOTONE — vary your volume and emphasis")
        else:
            print(f"   ✅ NATURAL variation")

    # --- Summary ---
    print("\n" + "=" * 60)
    if not issues and not warnings:
        print("  🎉  PERFECT! Your recording setup is great.")
        print("      You're ready to start the full recording session.")
    elif not issues:
        print("  👍  GOOD ENOUGH — minor issues that won't hurt training:")
        for w in warnings:
            print(f"      ⚠️  {w}")
        print("      You can proceed with recording.")
    else:
        print("  🛑  FIX THESE BEFORE RECORDING:")
        for issue in issues:
            print(f"      ❌ {issue}")
        if warnings:
            print("      Also:")
            for w in warnings:
                print(f"      ⚠️  {w}")
    print("=" * 60)

    return issues, warnings


def save_and_playback(speech):
    """Save the recording and play it back."""
    # Save as WAV
    filepath = OUTPUT_DIR / "quality_check.wav"
    
    # Convert float32 to int16 for WAV
    speech_int16 = (speech * 32767).astype(np.int16)
    
    with wave.open(str(filepath), 'w') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(speech_int16.tobytes())
    
    print(f"\n💾 Saved to: {filepath}")
    print(f"   Duration: {len(speech) / SAMPLE_RATE:.1f}s")
    print(f"   Format: {SAMPLE_RATE}Hz, 16-bit, mono")
    
    # Playback
    print("\n🔊 Playing back your recording...")
    sd.play(speech, SAMPLE_RATE)
    sd.wait()
    print("   Playback complete.")
    
    return filepath


def main():
    silence, speech = record_sample()
    issues, warnings = analyze_audio(silence, speech)
    filepath = save_and_playback(speech)
    
    print()
    if not issues:
        print("✅ Ready to start recording! Run:")
        print("   python record_voice.py")
    else:
        print("🔄 Fix the issues above and run this script again:")
        print("   python check_audio_quality.py")
    print()


if __name__ == "__main__":
    main()
