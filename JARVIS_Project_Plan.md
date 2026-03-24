# Project JARVIS — Local AI Voice Assistant

*A smart, locally-powered voice assistant that's smarter than Alexa, runs entirely on your hardware, and looks damn good doing it.*

**Author:** ET | **Date:** March 2026 | **Status:** Planning

---

## 1. Project Overview

JARVIS is a privacy-first, locally-running AI voice assistant built on an NVIDIA Jetson Orin Nano Super. It combines a local LLM for intelligent conversation, smart music playback across platforms, IoT device control for Wipro smart lights, Bluetooth audio output, and a sleek cyberpunk-inspired enclosure — all without sending a single byte to the cloud for core functionality.

### Core Capabilities

1. **Smart Music Playback** — Voice-activated music across YouTube Music and Spotify. Understands vague requests like "play that sad Coldplay song" or "play something upbeat for coding."
2. **IoT Light Control** — Full control of Wipro smart bulbs (on/off, brightness, color) via local Tuya protocol.
3. **Bluetooth Speaker Output** — High-quality audio routed to any Bluetooth speaker via PipeWire.
4. **Conversational AI** — Talk to a local LLM naturally, with voice in and voice out.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        JARVIS SYSTEM                            │
│                                                                 │
│  ┌──────────┐    ┌────────────┐    ┌──────────────────────┐     │
│  │ Mic Array │───▶│ Wake Word  │───▶│  Speech-to-Text      │     │
│  │ ReSpeaker │    │ OpenWake   │    │  (faster-whisper)    │     │
│  └──────────┘    │ Word       │    └──────────┬───────────┘     │
│                  └────────────┘               │                 │
│                                               ▼                 │
│                                    ┌──────────────────────┐     │
│                                    │   Intent Router      │     │
│                                    │   (LLM-powered)      │     │
│                                    └──┬───┬───┬───┬───────┘     │
│                                       │   │   │   │             │
│                       ┌───────────────┘   │   │   └──────┐      │
│                       ▼                   ▼   ▼          ▼      │
│              ┌──────────────┐  ┌──────┐ ┌────────┐ ┌─────────┐  │
│              │ Music Engine │  │ IoT  │ │  Chat  │ │ System  │  │
│              │ yt-music /   │  │Tuya  │ │  LLM   │ │ Control │  │
│              │ Spotify      │  │      │ │        │ │         │  │
│              └──────┬───────┘  └──┬───┘ └───┬────┘ └────┬────┘  │
│                     │             │         │           │        │
│                     ▼             ▼         ▼           ▼        │
│              ┌──────────────────────────────────────────────┐    │
│              │          Response Generator (LLM)            │    │
│              └─────────────────┬────────────────────────────┘    │
│                                │                                │
│                                ▼                                │
│                     ┌───────────────────┐                       │
│                     │   Text-to-Speech  │                       │
│                     │   (Piper TTS)     │                       │
│                     └────────┬──────────┘                       │
│                              │                                  │
│                              ▼                                  │
│                     ┌───────────────────┐                       │
│                     │  Bluetooth Audio  │                       │
│                     │  (PipeWire)       │──▶ 🔊 BT Speaker     │
│                     └───────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Audio Pipeline Flow

```
Mic → Wake Word Detection (always listening, low CPU)
  → Audio Capture (records until silence detected)
    → STT (transcribe speech to text)
      → Intent Classification (LLM determines: music / lights / chat / system)
        → Action Execution (play song, change light, generate answer)
          → TTS (convert response to speech)
            → Bluetooth Speaker Output
```

---

## 3. Hardware — Bill of Materials

### 3.1 Compute Board: NVIDIA Jetson Orin Nano Super Developer Kit

| Spec | Detail |
|------|--------|
| **AI Performance** | 67 TOPS |
| **GPU** | 1024-core NVIDIA Ampere with 32 Tensor Cores |
| **CPU** | 6-core Arm Cortex-A78AE |
| **RAM** | 8GB LPDDR5 |
| **Storage** | NVMe M.2 slot (SSD not included) |
| **Price** | ~₹34,679 |
| **Where to Buy** | [Robu.in](https://robu.in/product/nvidia-jetson-orin-nano-super-developer-kit/) or [Amazon.in](https://www.amazon.in/NVIDIA-Jetson-Orin-Nano-Developer/dp/B0BZJTQ5YP) |

**Why Jetson over Raspberry Pi 5?** The GPU acceleration is the killer feature. Llama 3.2 3B runs at ~30 tokens/sec on the Jetson (vs. 4-6 tokens/sec on Pi 5). This means sub-second response latency for the LLM — the difference between a snappy assistant and an awkward pause.

### 3.2 Microphone — Three Options (Pick One)

#### Recommended: ReSpeaker Mic Array v3.0 — ₹7,499

| Spec | Detail |
|------|--------|
| **Type** | Circular 4-mic far-field array |
| **Range** | Up to 5 meters voice detection |
| **Chip** | XMOS XVF-3000 (onboard DSP) |
| **Features** | Noise suppression, beamforming, echo cancellation, 12 programmable RGB LEDs |
| **Interface** | USB (plug and play on Linux) |
| **Where to Buy** | [Robocraze — ₹7,499](https://robocraze.com/products/respeaker-mic-array-v3-0-with-4-mic-array-and-xvf3000-voice-processor-seeed-studio) or [ThinkRobotics](https://thinkrobotics.com/products/respeaker-mic-array-v3-0) |

**Why this mic?** The built-in LED ring doubles as a status indicator (listening, processing, speaking) — great for the "cool factor." The 4-mic beamforming means it picks up your voice accurately even with music playing from the Bluetooth speaker.

**AVOID Amazon.in for this product** — third-party sellers list the older v2.0 at ₹18,000, which is massively inflated. Buy from Robocraze or ThinkRobotics instead.

#### Budget Option: USB Conference Mic (TONOR TM20) — ~₹3,000

| Spec | Detail |
|------|--------|
| **Type** | Single-element omnidirectional |
| **Range** | Up to 3 meters (10 feet) |
| **Features** | 360° pickup, mute button, plug-and-play USB |
| **Where to Buy** | [TONOR TM20 on Amazon.in — ~₹2,999](https://www.amazon.in/TONOR-Conference-Microphone-Omnidirectional-TM20/dp/B08NDB5NWP) |

No beamforming or LED ring, but perfectly functional in a quiet room. You'd add a separate NeoPixel ring for visual feedback.

#### DIY Option: INMP441 MEMS Mic Modules — ₹300 each

| Spec | Detail |
|------|--------|
| **Type** | I2S MEMS digital microphone |
| **Interface** | I2S (wired to Jetson GPIO, NOT USB) |
| **Where to Buy** | [Robu.in — ~₹300](https://robu.in/product/inmp441-mems-high-precision-omnidirectional-microphone-module-i2s/) or [Amazon.in — ~₹299](https://www.amazon.in/inmp441/s?k=inmp441) |

Buy 2–4 of these and wire them to the Jetson's I2S pins to build a custom mic array. Cheapest route but requires soldering and software-level beamforming. Only for hardware enthusiasts.

### 3.3 Storage: NVMe SSD

| Spec | Detail |
|------|--------|
| **Type** | M.2 2230 or 2242 NVMe SSD |
| **Capacity** | 256GB (enough for OS + all models) |
| **Where to Buy** | Amazon.in — search "M.2 2230 NVMe SSD" |
| **Est. Price** | ~₹2,500–4,000 |

The Jetson's microSD slot works but NVMe is significantly faster for loading LLM models into memory.

### 3.4 Bluetooth Speaker

You likely already have a good Bluetooth speaker. Any A2DP-capable Bluetooth speaker works. If buying new, look for something with:

- Bluetooth 5.0+ (lower latency)
- AptX or LDAC codec support (PipeWire supports these)
- Good bass response for music playback

**Budget pick:** JBL Flip 5/6 (~₹8,000–12,000 on Amazon.in) — excellent sound, Bluetooth 5.1, USB-C charging.

### 3.5 Power Supply

| Spec | Detail |
|------|--------|
| **Type** | USB-C PD, 20V/3A (60W) |
| **Note** | The Jetson Orin Nano Dev Kit needs a proper USB-C PD adapter, NOT a phone charger |
| **Where to Buy** | Amazon.in — search "65W USB-C PD charger" |
| **Est. Price** | ~₹1,500–2,500 |

### 3.6 Enclosure — Making It Look Cool

This is where your assistant goes from "exposed circuit board on a desk" to "Iron Man's workshop." Here are three tiers:

#### Option A: Cyberpunk Transparent Case (Recommended)

A clear acrylic or smoked transparent case that shows off the Jetson board, with RGB LED accents. The ReSpeaker's LED ring sits on top as the "eye."

- **Approach:** Get a custom acrylic case laser-cut from a local Gurgaon fabrication shop (search "laser cutting service near me" on Google Maps — there are several in Udyog Vihar / Sector 18).
- **Design:** Hexagonal or cylindrical form factor, ~15cm diameter, with ventilation slots cut in a geometric pattern. The ReSpeaker mic array sits on top (visible LED ring), Jetson board inside (visible through smoked acrylic).
- **LED Accents:** Add a WS2812B (NeoPixel) LED strip around the base, controlled via Jetson GPIO. Reacts to voice activity — pulses when listening, glows when thinking, flashes on response.
- **Materials cost:** ~₹800–1,500 for acrylic + ₹300 for NeoPixel strip.
- **Where to buy NeoPixel strip:** [Robu.in](https://robu.in) or Amazon.in — search "WS2812B LED strip."

#### Option B: 3D Printed Designer Enclosure

If you have access to a 3D printer (or use a service like [Protocraft.in](https://protocraft.in) or any Gurgaon-based 3D printing service):

- **Design inspiration:** Look up "smart speaker enclosure" or "voice assistant housing" on [Thingiverse](https://www.thingiverse.com) or [Printables](https://www.printables.com).
- **Material:** PLA or PETG in matte black with accent lighting slots.
- **Cool factor:** Design a "floating orb" where the mic array sits on a thin stem above the base unit.
- **Cost:** ~₹1,000–3,000 for 3D printing service.

#### Option C: Repurposed Premium Enclosure

- Buy a high-end desk lamp enclosure or cylindrical Bluetooth speaker housing and gut it.
- Mount the Jetson inside, mic array on top.
- The cheapest "looks premium" route.

### 3.7 Miscellaneous

| Item | Purpose | Est. Price | Source |
|------|---------|-----------|--------|
| USB-C to USB-A cable | Connect ReSpeaker to Jetson | ₹200 | Amazon.in |
| Ethernet cable (optional) | More reliable than WiFi for setup | ₹150 | Amazon.in |
| Heatsink/fan (if not included) | Thermal management | ₹500 | Robu.in |
| WS2812B NeoPixel strip (1m) | Ambient LED lighting | ₹300 | Robu.in / Amazon.in |
| Jumper wires | GPIO connections for LEDs | ₹100 | Robu.in |
| Micro HDMI to HDMI cable | Initial setup/debugging | ₹300 | Amazon.in |

### 3.8 Total Budget Estimate (Verified March 2026)

| Category | Est. Cost (₹) | Source |
|----------|---------------|--------|
| Jetson Orin Nano Super | 34,679 | Robu.in (incl. GST) |
| ReSpeaker Mic Array v3.0 | 7,499 | Robocraze (NOT Amazon) |
| NVMe SSD 256GB (M.2 2230) | 2,500–4,000 | Amazon.in |
| Power Supply (65W USB-C PD) | 1,599–3,549 | Flipkart / Amazon.in |
| Enclosure + LEDs | 1,500–2,000 | Local + Amazon.in |
| Bluetooth Speaker (JBL Flip 6) | 13,999 | Flipkart |
| Miscellaneous (cables, etc.) | 700–1,000 | Amazon.in / Robu.in |
| **TOTAL (all new)** | **~₹62,000–67,000** | |
| **TOTAL (with VERGEENO bundle, skip SSD + charger)** | **~₹58,000–62,000** | |
| **TOTAL (already have BT speaker)** | **~₹48,000–53,000** | |

*Prices verified from Amazon.in, Flipkart, and Robu.in as of March 2026. Actual prices may vary slightly based on seller, availability, and ongoing sales.*

---

## 4. Software Stack

### 4.1 Operating System

**JetPack 6.x (Ubuntu 22.04 based)** — NVIDIA's official OS for Jetson. Comes pre-configured with CUDA, cuDNN, TensorRT, and all the GPU acceleration libraries you need.

```bash
# Flash JetPack to NVMe SSD using NVIDIA SDK Manager
# (Run on a separate Ubuntu x86 machine, connect Jetson via USB)
```

### 4.2 Component Breakdown

| Component | Tool | Why This One |
|-----------|------|-------------|
| **LLM** | Ollama + Qwen 2.5 3B (Q4) | 30+ tok/sec on Jetson GPU. Best-in-class function calling & JSON output. ~2GB model size. Tested on Jetson Orin Nano. |
| **Speech-to-Text** | faster-whisper (medium model) | GPU-accelerated on Jetson. Accurate for Indian English accents. ~1.5GB model. |
| **Text-to-Speech** | Piper TTS | Sub-100ms latency. Multiple voice options. Lightweight. |
| **Wake Word** | OpenWakeWord | Open-source, custom trainable. Run your own "Hey Jarvis" wake word. |
| **Music (YouTube)** | ytmusicapi | No API restrictions. Cookie-based auth. Full search/play capability. |
| **Music (Spotify)** | spotipy | Works in dev mode (25 users max). Requires Spotify Premium. |
| **IoT Control** | tinytuya | Local LAN control of Wipro/Tuya bulbs. No cloud needed. |
| **Bluetooth Audio** | PipeWire | Modern codec support (AptX, LDAC). Stable BT audio. |
| **LED Control** | rpi_ws281x / Jetson.GPIO + neopixel | Ambient LED reactions via NeoPixel strip. |

### 4.3 LLM — The Brain

The LLM serves dual purpose: (a) **intent classification** to figure out what the user wants, and (b) **conversation** for general Q&A.

**Why Qwen 2.5 3B over Llama 3.2 3B?** Qwen 2.5 is specifically trained for function calling and structured JSON output — exactly what the intent router needs. It reliably returns clean JSON with intent classification, while Llama sometimes drifts or wraps output in markdown. Both are ~2GB quantized and run at similar speeds on the Jetson, but Qwen wins on tool-use reliability. Other contenders considered: Phi-4-mini (3.8B, best reasoning but slightly larger), Gemma 3 4B (edge-optimized but has reported Jetson Nano Super compatibility issues), DeepSeek R1 8B (great reasoning but too large for 8GB shared RAM).

```
User says: "Play that sad Coldplay song from the movie about space"

LLM processes:
→ Intent: MUSIC_PLAY
→ Artist: Coldplay
→ Mood: sad
→ Context clue: "movie about space" → likely "Interstellar" → song is probably "Atlas"
→ Action: Search "Coldplay Atlas" on YouTube Music / Spotify
```

**Model setup:**

```bash
# Install Ollama (has native Jetson/ARM support)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model (quantized to 4-bit for speed)
ollama pull qwen2.5:3b

# Test it
ollama run qwen2.5:3b "What Coldplay song is associated with the movie Interstellar?"
```

**System prompt for intent routing:**

```
You are JARVIS, a smart voice assistant. Given the user's spoken request,
classify the intent and extract parameters.

Respond ONLY with valid JSON in this format:
{
  "intent": "music_play" | "music_control" | "light_control" | "chat" | "system",
  "params": {
    // For music_play: {"query": "search terms", "platform": "youtube|spotify|any"}
    // For music_control: {"action": "pause|resume|skip|volume_up|volume_down"}
    // For light_control: {"action": "on|off|brightness|color", "value": "..."}
    // For chat: {"message": "the user's question"}
    // For system: {"action": "time|weather|alarm|..."}
  },
  "response": "Brief spoken acknowledgment"
}
```

### 4.4 Speech-to-Text — The Ears

```bash
# Install faster-whisper with CUDA support
pip install faster-whisper --break-system-packages

# Or build whisper.cpp for maximum performance
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make GGML_CUDA=1  # Enable CUDA for Jetson GPU
```

**Python integration:**

```python
from faster_whisper import WhisperModel

# Load model once at startup (stays in GPU memory)
model = WhisperModel("medium", device="cuda", compute_type="float16")

def transcribe(audio_path: str) -> str:
    segments, info = model.transcribe(audio_path, language="en")
    return " ".join(segment.text for segment in segments)
```

### 4.5 Text-to-Speech — The Voice

```bash
# Install Piper TTS
pip install piper-tts --break-system-packages

# Download a voice model (try "amy" for a natural English voice)
# Models: https://github.com/rhasspy/piper/blob/master/VOICES.md
```

```python
import subprocess

def speak(text: str, output_path: str = "/tmp/response.wav"):
    subprocess.run([
        "piper",
        "--model", "/path/to/en_US-amy-medium.onnx",
        "--output_file", output_path
    ], input=text.encode(), check=True)

    # Play via PipeWire (routes to Bluetooth speaker)
    subprocess.run(["pw-play", output_path], check=True)
```

### 4.6 Wake Word — The Trigger

```bash
pip install openwakeword --break-system-packages
```

```python
from openwakeword.model import Model
import pyaudio
import numpy as np

# Load wake word model
oww_model = Model(
    wakeword_models=["hey_jarvis"],  # Train custom model or use built-in
    inference_framework="onnx"
)

# Continuous listening loop
audio = pyaudio.PyAudio()
stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=1280)

while True:
    audio_data = np.frombuffer(stream.read(1280), dtype=np.int16)
    prediction = oww_model.predict(audio_data)

    if prediction["hey_jarvis"] > 0.5:  # Confidence threshold
        print("Wake word detected! Listening...")
        # → Trigger audio capture → STT → LLM pipeline
```

### 4.7 Music Engine — Smart Playback

```bash
pip install ytmusicapi spotipy --break-system-packages
```

**YouTube Music (primary — no restrictions):**

```python
from ytmusicapi import YTMusic

# One-time setup: authenticate with browser cookies
# ytmusicapi oauth  (follow prompts)
ytm = YTMusic("oauth.json")

def search_and_play(query: str):
    results = ytm.search(query, filter="songs", limit=5)
    if results:
        video_id = results[0]["videoId"]
        title = results[0]["title"]
        artist = results[0]["artists"][0]["name"]

        # Stream audio via mpv (supports YouTube URLs)
        url = f"https://music.youtube.com/watch?v={video_id}"
        subprocess.Popen(["mpv", "--no-video", url])

        return f"Playing {title} by {artist}"
```

**Spotify (secondary — requires Premium):**

```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    redirect_uri="http://localhost:8888/callback",
    scope="user-modify-playback-state user-read-playback-state"
))

def spotify_play(query: str):
    results = sp.search(q=query, type="track", limit=5)
    if results["tracks"]["items"]:
        track = results["tracks"]["items"][0]
        sp.start_playback(uris=[track["uri"]])
        return f"Playing {track['name']} by {track['artists'][0]['name']}"
```

**Smart Song Resolution (LLM-powered):**

The real magic is using the LLM to interpret vague requests before searching:

```python
def resolve_song_query(user_request: str) -> str:
    """Use LLM to convert vague request into a searchable query."""
    prompt = f"""The user said: "{user_request}"

    Convert this into the best possible search query for a music platform.
    Consider: song titles, artist names, movie soundtracks, lyrics, moods, genres.

    Examples:
    - "that song that goes na na na na" → "Hey Jude Beatles"
    - "play something for a rainy day" → "rainy day playlist chill"
    - "the Coldplay song from Interstellar" → "Atlas Coldplay"

    Return ONLY the search query, nothing else."""

    response = ollama.generate(model="qwen2.5:3b", prompt=prompt)
    return response["response"].strip()
```

### 4.8 IoT — Wipro Light Control

Wipro smart bulbs use the Tuya protocol. Control them entirely over your local network.

**One-time setup to get device credentials:**

```bash
pip install tinytuya --break-system-packages

# Run the wizard (needs Tuya IoT Platform account — free)
python -m tinytuya wizard
# Follow prompts: enter API key from iot.tuya.com
# This scans your network and finds all Wipro/Tuya devices
```

**Control code:**

```python
import tinytuya

# Initialize device (values from wizard output)
light = tinytuya.BulbDevice(
    dev_id="DEVICE_ID",
    address="192.168.1.XXX",  # Local IP
    local_key="LOCAL_KEY",
    version=3.3
)

def control_light(action: str, value=None):
    if action == "on":
        light.turn_on()
        return "Light turned on"
    elif action == "off":
        light.turn_off()
        return "Light turned off"
    elif action == "brightness":
        # Tuya brightness: 10-1000
        brightness = int(float(value) / 100 * 1000)
        light.set_brightness(brightness)
        return f"Brightness set to {value}%"
    elif action == "color":
        # Map color names to RGB
        colors = {
            "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
            "warm": (255, 180, 100), "cool": (200, 220, 255),
            "purple": (128, 0, 128), "orange": (255, 165, 0),
            "pink": (255, 105, 180),
        }
        rgb = colors.get(value.lower(), (255, 255, 255))
        light.set_colour(*rgb)
        return f"Light color set to {value}"
```

### 4.9 Bluetooth Audio — PipeWire Setup

```bash
# Install PipeWire and Bluetooth support
sudo apt install pipewire-audio pipewire-pulse wireplumber libspa-0.2-bluetooth

# Remove PulseAudio if present (conflicts)
sudo apt remove pulseaudio pulseaudio-module-bluetooth

# Enable PipeWire
systemctl --user enable pipewire pipewire-pulse wireplumber
systemctl --user start pipewire pipewire-pulse wireplumber

# Pair your Bluetooth speaker
bluetoothctl
> power on
> scan on
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit

# Verify audio routing
pw-cli list-objects | grep -i bluetooth
```

**Auto-reconnect script (add to systemd service):**

```python
import subprocess
import time

SPEAKER_MAC = "XX:XX:XX:XX:XX:XX"

def ensure_bt_connected():
    result = subprocess.run(
        ["bluetoothctl", "info", SPEAKER_MAC],
        capture_output=True, text=True
    )
    if "Connected: no" in result.stdout:
        subprocess.run(["bluetoothctl", "connect", SPEAKER_MAC])
        time.sleep(2)
```

### 4.10 LED Ring — Visual Feedback

Use the ReSpeaker's built-in LED ring AND an optional NeoPixel strip for ambient effects.

```python
# ReSpeaker LED control via USB HID
import usb.core
import usb.util

RESPEAKER_VENDOR_ID = 0x2886
RESPEAKER_PRODUCT_ID = 0x0018

class LEDController:
    """Control ReSpeaker mic array LED ring."""

    COLORS = {
        "listening": (0, 0, 255),      # Blue — I hear you
        "thinking": (255, 165, 0),     # Orange — processing
        "speaking": (0, 255, 0),       # Green — responding
        "error": (255, 0, 0),          # Red — something went wrong
        "idle": (10, 10, 10),          # Dim white — standby
    }

    def set_state(self, state: str):
        color = self.COLORS.get(state, (255, 255, 255))
        # Set LED ring color via USB HID commands
        # (Implementation depends on ReSpeaker firmware version)
```

---

## 5. Software Architecture — Project Structure

```
jarvis/
├── main.py                 # Entry point — orchestrates the pipeline
├── config.yaml             # All configuration (device IPs, model paths, etc.)
├── requirements.txt        # Python dependencies
│
├── audio/
│   ├── wake_word.py        # OpenWakeWord listener (always-on)
│   ├── recorder.py         # Captures audio after wake word (VAD-based)
│   ├── stt.py              # faster-whisper transcription
│   └── tts.py              # Piper TTS + PipeWire playback
│
├── brain/
│   ├── llm.py              # Ollama client wrapper
│   ├── intent_router.py    # Classifies intent from transcribed text
│   └── prompts.py          # System prompts for different modes
│
├── skills/
│   ├── music.py            # YouTube Music + Spotify playback
│   ├── lights.py           # Wipro/Tuya light control via tinytuya
│   ├── chat.py             # General conversation handler
│   └── system.py           # Time, weather, alarms, etc.
│
├── hardware/
│   ├── led_ring.py         # ReSpeaker LED control
│   ├── neopixel.py         # Ambient NeoPixel LED strip
│   └── bluetooth.py        # BT speaker connection management
│
├── services/
│   ├── jarvis_service.py   # systemd service wrapper (auto-start on boot)
│   └── bt_reconnect.py     # Bluetooth auto-reconnect daemon
│
└── scripts/
    ├── setup.sh            # One-shot system setup
    ├── train_wakeword.py   # Custom wake word training
    └── tuya_setup.py       # Tuya device discovery wizard
```

### Main Loop (main.py)

```python
import asyncio
from audio.wake_word import WakeWordDetector
from audio.recorder import AudioRecorder
from audio.stt import SpeechToText
from audio.tts import TextToSpeech
from brain.intent_router import IntentRouter
from skills.music import MusicPlayer
from skills.lights import LightController
from skills.chat import ChatHandler
from hardware.led_ring import LEDController

class Jarvis:
    def __init__(self):
        self.wake_word = WakeWordDetector()
        self.recorder = AudioRecorder()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.router = IntentRouter()
        self.music = MusicPlayer()
        self.lights = LightController()
        self.chat = ChatHandler()
        self.leds = LEDController()

    async def run(self):
        print("JARVIS initialized. Listening for wake word...")
        self.leds.set_state("idle")

        while True:
            # Step 1: Wait for wake word
            await self.wake_word.listen()
            self.leds.set_state("listening")

            # Step 2: Record user speech (until silence)
            audio = await self.recorder.record()
            self.leds.set_state("thinking")

            # Step 3: Transcribe
            text = await self.stt.transcribe(audio)
            print(f"User said: {text}")

            # Step 4: Route intent
            intent = await self.router.classify(text)

            # Step 5: Execute action
            response = await self.execute(intent)

            # Step 6: Speak response
            self.leds.set_state("speaking")
            await self.tts.speak(response)
            self.leds.set_state("idle")

    async def execute(self, intent):
        match intent["intent"]:
            case "music_play":
                return await self.music.play(intent["params"]["query"],
                                              intent["params"].get("platform", "any"))
            case "music_control":
                return await self.music.control(intent["params"]["action"])
            case "light_control":
                return self.lights.control(intent["params"]["action"],
                                           intent["params"].get("value"))
            case "chat":
                return await self.chat.respond(intent["params"]["message"])
            case _:
                return "I'm not sure how to help with that."

if __name__ == "__main__":
    jarvis = Jarvis()
    asyncio.run(jarvis.run())
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1–2)

**Goal:** Get the Jetson running with basic voice I/O.

1. **Flash JetPack** on the NVMe SSD using NVIDIA SDK Manager.
2. **Install core packages:** Python 3.10+, pip, git, PipeWire.
3. **Set up Ollama** and pull Llama 3.2 3B. Verify it runs and responds.
4. **Set up faster-whisper** with CUDA. Test transcription accuracy.
5. **Set up Piper TTS**. Test audio output via speaker (wired first, then BT).
6. **Pair Bluetooth speaker** via PipeWire. Verify stable audio playback.

**Milestone:** You can type a question → LLM answers → TTS speaks it through BT speaker.

### Phase 2: Voice Pipeline (Week 3)

**Goal:** Full voice-in, voice-out conversation.

1. **Connect ReSpeaker** mic array. Verify it's detected (`arecord -l`).
2. **Implement wake word** detection with OpenWakeWord (use built-in "hey jarvis" or train custom).
3. **Implement voice activity detection** (VAD) — record after wake word, stop on silence.
4. **Wire it all together:** Wake word → Record → STT → LLM → TTS → Speaker.
5. **Tune sensitivity:** Adjust wake word threshold, silence detection timing, mic gain.

**Milestone:** Say "Hey Jarvis, what's the weather like?" → Hear a spoken answer.

### Phase 3: Skills — Music (Week 4)

**Goal:** Smart music playback.

1. **Set up ytmusicapi** with OAuth authentication.
2. **Install mpv** for audio streaming (`sudo apt install mpv`).
3. **Implement music search and play** via YouTube Music.
4. **Implement LLM-powered query resolution** (vague request → precise search).
5. **Add playback controls:** pause, resume, skip, volume.
6. **(Optional) Set up Spotify** via spotipy if you have Premium.

**Milestone:** Say "Play that Daft Punk song from the Tron movie" → Hear "Derezzed" playing.

### Phase 4: Skills — IoT (Week 4–5)

**Goal:** Wipro light control.

1. **Create Tuya IoT Platform account** at [iot.tuya.com](https://iot.tuya.com) (free tier).
2. **Run tinytuya wizard** to discover devices and get local keys.
3. **Implement light control** functions (on/off/brightness/color).
4. **Wire to intent router** so voice commands trigger light actions.
5. **Add scene support:** "movie mode" (dim warm), "focus mode" (bright cool), etc.

**Milestone:** Say "Jarvis, set the lights to blue at 50%" → Lights change.

### Phase 5: Polish & Enclosure (Week 5–6)

**Goal:** Make it look and feel like a finished product.

1. **LED feedback:** Implement LED ring states (idle/listening/thinking/speaking).
2. **Add NeoPixel ambient strip** — reacts to music, voice, or just looks cool.
3. **Build/order enclosure** (laser-cut acrylic or 3D printed).
4. **Assemble everything** inside the enclosure with proper cable management.
5. **Create systemd service** so JARVIS auto-starts on boot.
6. **Add Bluetooth auto-reconnect** daemon.
7. **Error handling and recovery** — graceful fallbacks for all failure modes.

**Milestone:** Power on → JARVIS starts automatically → LED ring glows → Ready for commands.

### Phase 6: Refinement (Ongoing)

- **Train a custom wake word** that matches your preference.
- **Add more skills:** timer/alarm, weather (via open-meteo API), news briefing, calendar.
- **Conversation memory:** Store recent interactions for context-aware follow-ups.
- **Multi-room support:** Add a second device via Wyoming protocol + Home Assistant.
- **Web dashboard:** Simple Flask/FastAPI UI to configure settings, view logs.

---

## 7. Key Technical Gotchas

### Memory Management
The Jetson has 8GB shared between CPU and GPU. Budget carefully:
- Llama 3.2 3B Q4: ~2GB
- faster-whisper medium: ~1.5GB
- Piper TTS: ~200MB
- OS + services: ~1.5GB
- **Headroom:** ~2.8GB

Add 8GB swap on the NVMe just in case:
```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Streaming Architecture
**Never load models per-request.** Keep Ollama, faster-whisper, and Piper running as persistent processes/servers. The startup cost for loading models is 5-15 seconds — unacceptable for a voice assistant.

### Spotify API Limitations (2026)
Spotify's API is now heavily restricted for hobby projects. Development mode caps at 25 users and requires active Premium. YouTube Music via ytmusicapi has no such restrictions and should be your primary music backend.

### Piper TTS Archival
Piper TTS was archived on GitHub in October 2025. It still works perfectly, but download all voice models now and store them locally so you don't depend on the repo staying available.

### Indian English Accent
faster-whisper's medium model handles Indian English well. If accuracy is poor, try the "large-v3" model (costs more GPU RAM but significantly better for accented English).

---

## 8. Shopping List — Quick Order Guide (Verified March 2026)

Here's exactly what to order, with direct buy links and verified prices for Gurgaon delivery:

| # | Item | Buy Link | Verified ₹ | Notes |
|---|------|----------|-----------|-------|
| 1 | NVIDIA Jetson Orin Nano Super Dev Kit | [Robu.in](https://robu.in/product/nvidia-jetson-orin-nano-super-developer-kit/) / [Amazon.in](https://www.amazon.in/NVIDIA-Jetson-Orin-Nano-Developer/dp/B0BZJTQ5YP) | ₹34,679 | Robu.in price incl. GST. Also check [VERGEENO bundle with 250GB NVMe + charger](https://www.amazon.in/VERGEENO-Development-Storage-Jetpack-Included/dp/B0DR28HRCP) on Amazon |
| 2 | ReSpeaker Mic Array v3.0 (4-mic, USB) | [Robocraze — ₹7,499](https://robocraze.com/products/respeaker-mic-array-v3-0-with-4-mic-array-and-xvf3000-voice-processor-seeed-studio) / [ThinkRobotics](https://thinkrobotics.com/products/respeaker-mic-array-v3-0) | ₹7,499 | **DO NOT buy from Amazon.in** (inflated to ₹18,000). Budget alt: [TONOR TM20 USB Mic — ~₹2,999](https://www.amazon.in/TONOR-Conference-Microphone-Omnidirectional-TM20/dp/B08NDB5NWP) |
| 3 | NVMe SSD 256GB (M.2 2230) | [EVM 256GB on Amazon.in](https://www.amazon.in/EVM-256GB-M-2-NVMe-Internal/dp/B0D47LD32L) / [Transcend 256GB](https://www.amazon.in/Transcend-256GB-Flash-Warranty-TS256GMTE300S/dp/B0BTDPXWPC) / [GAMERKING 256GB](https://www.amazon.in/GAMERKING-256GB-M-2-2230-PCIe/dp/B0BXKZQM5M) | ₹2,500–4,000 | EVM ~₹3,500. Skip if you buy the VERGEENO Jetson bundle (includes 250GB NVMe) |
| 4 | 65W USB-C PD Charger | [LAPCARE 65W on Flipkart](https://www.flipkart.com/lapcare-65w-61w-usb-type-c-power-adapter-charger-apple-macbook-pro-lenovo-asus-acer-dell-xiaomi-air-huawei-matebook-hp-spectre-thinkpad-any-other-laptops-61-w/p/itm43ff253cb6fa5) / [Belkin 65W on Amazon.in](https://www.amazon.in/Belkin-Charger-Technology-Compact-MacBook/dp/B0BCNQCWHS) | ₹1,599–3,549 | LAPCARE is budget pick (₹1,599). Belkin is premium (₹3,549). Skip if buying VERGEENO bundle (includes charger) |
| 5 | Micro HDMI to HDMI cable | [PiBOX India 1.5m on Amazon.in](https://www.amazon.in/India-Adapter-Ethernet-Compatible-Raspberry/dp/B08PW6W54V) / [UPORT 1.8m](https://www.amazon.in/UPORT-Meters-Connect-Projector-Monitor/dp/B0CYGKBKFS) | ₹250–400 | Any 4K-capable micro HDMI cable works |
| 6 | USB-C to USB-A cable | [Amazon.in search](https://www.amazon.in/s?k=usb+c+to+usb+a+cable) | ₹150–300 | For connecting ReSpeaker to Jetson |
| 7 | WS2812B NeoPixel LED strip (1m, 60 LEDs) | [Amazon.in](https://www.amazon.in/WS2812B-Individually-Addressable-Pixel-Strip/dp/B0BQ4HW4X5) / [Flipkart](https://www.flipkart.com/jse-neo-pixel-led-strip-1mtr-60leds-mtr-ws2812b-arduino-projects-non-waterproof-light/p/itm46a14532949c4) / [Robu.in](https://robu.in/product-tag/ws2812b/) | ₹300–500 | Get the non-waterproof 60 LED/m variant |
| 8 | Jumper wires (male-female, 40 pack) | [Robu.in](https://robu.in/product/male-to-female-jumper-wires-40pcs-20cm/) | ₹50–100 | 20cm length is ideal |
| 9 | Smoked acrylic sheets (for enclosure) | Local Gurgaon shop* | ₹800–1,500 | See note below |
| 10 | JBL Flip 6 Bluetooth Speaker (optional) | [Flipkart](https://www.flipkart.com/jbl-flip-6-12hr-playtime-customize-audio-app-ip67-rating-portable-30-w-bluetooth-laptop-desktop-speaker/p/itmad738772bc282) / [Amazon.in](https://www.amazon.in/JBL-Bluetooth-Dustproof-PartyBoost-Personalization/dp/B09V7WS4PP) | ₹13,999 | JBL Flip 5 is ₹11,999 on Flipkart if budget is tight. Skip if you already have a BT speaker |

**Pro tip — VERGEENO Bundle:** The [VERGEENO Jetson Orin Nano Super bundle](https://www.amazon.in/VERGEENO-Development-Storage-Jetpack-Included/dp/B0DR28HRCP) on Amazon.in includes the Jetson + 250GB NVMe + Power Adapter pre-installed, saving you items #3 and #4. Check the bundle price vs buying separately.

*\*For acrylic enclosure: search Google Maps for "laser cutting service Gurgaon" — Udyog Vihar Phase 1 has several fabrication shops that can cut custom designs from your DXF file within 1-2 days.*

---

## 9. Useful Resources & References

**Hardware:**
- [Jetson Orin Nano Getting Started](https://developer.nvidia.com/embedded/learn/get-started-jetson-orin-nano-devkit)
- [ReSpeaker USB Mic Array Wiki](https://wiki.seeedstudio.com/ReSpeaker_Mic_Array_v2.0/)

**Software:**
- [Ollama — Local LLM server](https://ollama.com)
- [faster-whisper — GPU-accelerated STT](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS — Local text-to-speech](https://github.com/rhasspy/piper)
- [OpenWakeWord — Custom wake words](https://github.com/dscripka/openWakeWord)
- [ytmusicapi — YouTube Music API](https://github.com/sigma67/ytmusicapi)
- [spotipy — Spotify API](https://github.com/spotipy-dev/spotipy)
- [tinytuya — Local Tuya/Wipro control](https://github.com/jasonacox/tinytuya)
- [PipeWire — Modern Linux audio](https://pipewire.org)

**Enclosure Inspiration:**
- [Thingiverse — Smart speaker enclosures](https://www.thingiverse.com/search?q=smart+speaker)
- [Printables — Voice assistant housings](https://www.printables.com/search/models?q=voice+assistant)

**Community:**
- [my-light — Wipro bulb control example](https://github.com/dinesh-it/my-light)
- [Home Assistant Voice — Wyoming protocol](https://www.home-assistant.io/voice_control/)
- [r/JetsonNano on Reddit](https://www.reddit.com/r/JetsonNano/)

---

*Happy building, ET. Let's make JARVIS real.* 🤖
