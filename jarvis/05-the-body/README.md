# Module 5: The Body — Hardware, Jetson Setup & Enclosure

**What this is:** The physical build — setting up the Jetson, connecting peripherals, pairing Bluetooth, building the enclosure, and porting everything from Mac to hardware.

**Why it matters:** This is where JARVIS goes from a cool Mac script to a real physical object your girlfriend can interact with. The enclosure and LEDs are the wow factor.

**Time estimate:** 8–10 hours across Weeks 5–6

**Prerequisites:** Modules 1–4 should be complete. You should have working code on your Mac before touching hardware.

**Buy trigger:** Only start purchasing hardware AFTER you've completed Modules 1–4 and are confident in the software. The one exception is the Wipro smart bulb (buy early for Module 4).

---

## What You'll Learn

1. Jetson Orin Nano Super setup (JetPack, NVMe, CUDA)
2. Porting Python code from Mac to ARM Linux
3. PipeWire & Bluetooth audio configuration
4. ReSpeaker mic array setup on Linux
5. GPIO & NeoPixel LED control
6. Enclosure design and fabrication

---

## 5.1 — Hardware Purchase Checklist

**Only buy when you've completed the Mac-based modules and are ready to build.**

Reference the shopping list in `JARVIS_Project_Plan.md` for exact links and prices.

Order of purchase (stagger to avoid buying things you don't need):

| Order | Item | When to Buy | Why Wait |
|-------|------|-------------|----------|
| 1 | Wipro Smart Bulb | Week 2 (for Module 4) | Cheap, needed for software testing |
| 2 | Jetson Orin Nano Super + NVMe + Charger | Week 4 (after Mac prototyping done) | Expensive, make sure you need it |
| 3 | ReSpeaker Mic Array v3.0 | Week 4 (order with Jetson) | Needs Jetson to test |
| 4 | Bluetooth speaker (if needed) | Week 4 | May already own one |
| 5 | Cables, jumper wires, HDMI | Week 4 (order with Jetson) | Cheap, bundle shipping |
| 6 | NeoPixel LED strip | Week 5 | Only after enclosure design finalized |
| 7 | Enclosure materials (acrylic) | Week 5–6 | Last — design depends on everything fitting |
| 8 | IR transmitter module (e.g., IR LED + TSOP38238 receiver) | After Jetson setup | For controlling AC, TV, and other IR devices. GPIO-driven, needs Jetson to test |

---

## 5.2 — Jetson First Boot

```bash
# 1. Flash JetPack 6.x to NVMe SSD
#    Use NVIDIA SDK Manager on a separate Ubuntu machine
#    OR buy the VERGEENO bundle with pre-flashed NVMe

# 2. First boot setup
#    Connect: HDMI monitor, USB keyboard/mouse, Ethernet (recommended)
#    Power on → follow Ubuntu setup wizard

# 3. Verify CUDA works
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available())"

# 4. System update
sudo apt update && sudo apt upgrade -y

# 5. Install essentials
sudo apt install -y python3-pip git mpv portaudio19-dev bluetooth bluez
pip install --break-system-packages faster-whisper piper-tts ytmusicapi \
    tinytuya openwakeword sounddevice numpy requests
```

### First sanity check — run Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
ollama run qwen2.5:3b "Hello, I am running on a Jetson. How fast am I?"
```

**Note the speed.** It should be significantly faster than your Mac for LLM inference because of the GPU.

---

## 5.3 — Bluetooth Speaker Setup

```bash
# Install PipeWire (replaces PulseAudio)
sudo apt install -y pipewire-audio pipewire-pulse wireplumber \
    libspa-0.2-bluetooth

# Remove PulseAudio if present
sudo apt remove -y pulseaudio pulseaudio-module-bluetooth

# Enable PipeWire
systemctl --user enable pipewire pipewire-pulse wireplumber
systemctl --user start pipewire pipewire-pulse wireplumber

# Pair Bluetooth speaker
bluetoothctl
> power on
> agent on
> scan on
# Wait for your speaker to appear (e.g., JBL Flip 6)
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit

# Verify it's the default output
pw-cli list-objects | grep -i bluetooth

# Test audio
speaker-test -c 2  # Should hear through BT speaker
```

**Create auto-reconnect script** — save as `scripts/bt_reconnect.sh`:

```bash
#!/bin/bash
SPEAKER_MAC="XX:XX:XX:XX:XX:XX"
while true; do
    if ! bluetoothctl info $SPEAKER_MAC | grep -q "Connected: yes"; then
        echo "Reconnecting Bluetooth speaker..."
        bluetoothctl connect $SPEAKER_MAC
    fi
    sleep 10
done
```

---

## 5.4 — ReSpeaker Mic Array Setup

```bash
# The ReSpeaker v3.0 is USB plug-and-play on Linux
# Plug it in and verify detection:
arecord -l
# Should show something like "USB PnP Sound Device"

# Test recording
arecord -D plughw:1,0 -f S16_LE -r 16000 -d 5 test.wav
aplay test.wav  # Play back through BT speaker

# If you see the device, all your Module 2 code works as-is
# (just make sure sounddevice uses the right input device)
```

```python
# Find the right device index for sounddevice
import sounddevice as sd
print(sd.query_devices())
# Look for "ReSpeaker" or "USB PnP" — note the index
# Set it: sd.default.device = [INPUT_INDEX, OUTPUT_INDEX]
```

---

## 5.5 — Port Mac Code to Jetson

Your code from Modules 1–4 is designed to be portable. Here's what changes:

| Component | Mac | Jetson |
|-----------|-----|--------|
| Ollama | CPU inference | GPU inference (automatic) |
| faster-whisper | `device="cpu"` | `device="cuda"` |
| Piper TTS | Same | Same |
| Audio playback | `afplay` | `pw-play` or sounddevice |
| mpv | Same | Same |
| tinytuya | Same | Same (same network) |
| sounddevice input | Mac mic | ReSpeaker device index |

The main change in code:

```python
# Change in stt.py
# Mac:   WhisperModel("medium", device="cpu", compute_type="int8")
# Jetson: WhisperModel("medium", device="cuda", compute_type="float16")
```

**Exercise:** Copy your Module 1–4 experiment code to the Jetson. Run each piece. Note what breaks and fix it. Track issues in `notes/porting-issues.md`.

---

## 5.6 — LED Feedback (NeoPixel Strip)

The NeoPixel strip gives visual feedback — makes JARVIS feel alive.

```python
# This runs on Jetson only (needs GPIO access)
# Install: pip install rpi_ws281x adafruit-circuitpython-neopixel

import board
import neopixel
import time

# Setup — adjust pin and LED count for your strip
NUM_LEDS = 30  # Number of LEDs on your strip
PIN = board.D18  # GPIO pin (check your Jetson pinout)

strip = neopixel.NeoPixel(PIN, NUM_LEDS, brightness=0.3, auto_write=True)

def set_state(state: str):
    """Set LED strip to reflect assistant state."""
    colors = {
        "idle": (10, 10, 20),         # Dim blue — standby
        "listening": (0, 50, 255),     # Bright blue — I hear you
        "thinking": (255, 100, 0),     # Orange pulse — processing
        "speaking": (0, 255, 50),      # Green — responding
        "error": (255, 0, 0),          # Red — something went wrong
        "music": (128, 0, 255),        # Purple — music playing
    }
    color = colors.get(state, (255, 255, 255))
    strip.fill(color)

# Demo all states
for state in ["idle", "listening", "thinking", "speaking", "music", "error"]:
    print(f"State: {state}")
    set_state(state)
    time.sleep(2)

strip.fill((0, 0, 0))  # Off
```

---

## 5.7 — Enclosure Design

**Start designing in Week 5, build in Week 6.**

Approach: Cylindrical or hexagonal form factor.

```
        ┌─────────────────┐
        │  ReSpeaker Mic   │  ← LED ring visible on top
        │  (sits on top)   │
        ├─────────────────┤
        │                 │
        │  NeoPixel strip │  ← Visible through translucent band
        │  (around middle)│
        │                 │
        │  Jetson Orin    │  ← Inside, hidden or visible through
        │  Nano Super     │     smoked acrylic
        │                 │
        │  Ventilation    │  ← Cut geometric patterns for airflow
        │  slots          │
        └─────────────────┘
            Power cable
```

**Design options:** See Section 3.6 of `JARVIS_Project_Plan.md` for three enclosure approaches (laser-cut acrylic, 3D printed, or repurposed).

**Exercise:** Sketch 3 different enclosure ideas on paper. Measure the Jetson board dimensions (100mm x 79mm for Orin Nano). Plan where every component fits. Take photos of your sketches and save in `designs/`.

---

## Checkpoint — You're Ready When:

- [ ] Jetson boots and runs JetPack
- [ ] Ollama runs Qwen 2.5 3B with noticeable GPU speedup
- [ ] Bluetooth speaker is paired and plays audio
- [ ] ReSpeaker mic is detected and records clear audio
- [ ] All Module 1–4 code runs on Jetson
- [ ] NeoPixel LEDs work and look good
- [ ] Enclosure design is finalized and materials ordered

---

## Files You Should Have Created

```
05-the-body/
├── research/
│   └── jetson-setup-notes.md
├── designs/
│   ├── enclosure-sketch-1.jpg
│   ├── enclosure-sketch-2.jpg
│   └── final-design-measurements.md
├── notes/
│   └── porting-issues.md
└── README.md (this file)
```
