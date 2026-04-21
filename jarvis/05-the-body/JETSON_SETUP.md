# Jetson Orin Nano Super -- JARVIS Deployment Guide

**Target:** NVIDIA Jetson Orin Nano Super Developer Kit (8GB LPDDR5)
**OS:** JetPack 6.x (Ubuntu 22.04, CUDA 12.x)
**Goal:** Run the full JARVIS assistant identically to Mac -- zero code changes, config-only differences.

---

## Table of Contents

1. [Phase 1: Hardware Setup (Flash + Peripherals)](#phase-1-hardware-setup)
2. [Phase 2: System Configuration](#phase-2-system-configuration)
3. [Phase 3: Software Installation](#phase-3-software-installation)
4. [Phase 4: JARVIS Configuration](#phase-4-jarvis-configuration)
5. [Phase 5: Auto-Start on Boot](#phase-5-auto-start-on-boot)
6. [Phase 6: Display Setup](#phase-6-display-setup)
7. [Phase 7: Audio Setup](#phase-7-audio-setup)
8. [Phase 8: Performance Tuning](#phase-8-performance-tuning)
9. [Memory Budget](#memory-budget)
10. [Troubleshooting](#troubleshooting)

---

## Phase 1: Hardware Setup

### 1.1 Flash JetPack to NVMe SSD

**Why NVMe over microSD:** The Jetson can boot from microSD, but for an LLM-based assistant it is unacceptably slow. Ollama loads the model file (~2GB for llama3.2:3b Q4) from disk into RAM at startup. On microSD this takes 15-30 seconds; on NVMe it takes under 2 seconds. More importantly, the swap file (which we need -- see Phase 2) on microSD would destroy the card within months due to write amplification. NVMe has orders of magnitude better write endurance and throughput.

**What you need:**
- Jetson Orin Nano Super Developer Kit
- M.2 2230 NVMe SSD (256GB EVM or Samsung PM991)
- A host PC (Mac or Linux) with a USB-C cable
- Phillips screwdriver for the SSD mounting screw

**Install the NVMe SSD:**

The developer kit carrier board has an M.2 Key M slot on the underside. Before powering on for the first time:

1. Flip the carrier board (careful -- the heatsink assembly is heavy).
2. Locate the M.2 2230 slot. It is next to the SO-DIMM connector area, labeled J3 on the PCB silkscreen.
3. Insert the SSD at a ~30-degree angle into the connector.
4. Press down and secure with the M2 standoff screw (included with the dev kit, pre-installed at the 2230 position).
5. Flip the board back.

**Flash JetPack 6.x:**

NVIDIA provides two methods. The SDK Manager method is more reliable for NVMe boot.

**Method A: NVIDIA SDK Manager (recommended)**

1. On a host Ubuntu machine (or Ubuntu VM), install the [NVIDIA SDK Manager](https://developer.nvidia.com/sdk-manager):
   ```bash
   sudo apt install ./sdkmanager_*_amd64.deb
   ```

2. Put the Jetson into recovery mode:
   - Connect USB-C from the Jetson's flashing port (the one near the power jack) to the host.
   - Hold the recovery button (the middle button on the carrier board).
   - While holding, press and release the power button.
   - Release recovery after 2 seconds.
   - Verify on the host: `lsusb | grep NVIDIA` should show the device.

3. Launch SDK Manager, select:
   - Product: Jetson Orin Nano Super Developer Kit
   - JetPack version: 6.x (latest)
   - Storage device: **NVMe** (this is critical -- default is microSD)

4. Follow the prompts. Flash takes 15-20 minutes.

**Method B: SD card image + NVMe migration (fallback)**

If you do not have an Ubuntu host, you can flash the SD card image first, boot from it, then clone to NVMe using `rsync` and update the boot config. This is more involved and fragile -- Method A is strongly preferred.

1. Download the JetPack 6.x SD card image from [NVIDIA downloads](https://developer.nvidia.com/embedded/jetpack).
2. Flash to microSD: `sudo dd if=jetson-orin-nano.img of=/dev/sdX bs=4M status=progress`
3. Boot from microSD, then clone to NVMe and update extlinux.conf.

### 1.2 First Boot Setup

After flashing, connect:
- HDMI display (or the 5.5" AMOLED for permanent setup)
- USB keyboard + mouse (temporary, for initial config)
- Ethernet cable (faster than WiFi for package downloads)
- Power supply (the dev kit requires the official barrel jack, 19V/4.5A or USB-C PD adapter that supports 15V/3A or 20V/2.25A)

The first boot will run Ubuntu's OEM setup:
1. Select language, keyboard layout, timezone (Asia/Kolkata).
2. Create user: `jarvis` (or `devesh` -- your choice). This guide assumes `jarvis`.
3. Set a strong password.
4. Connect to WiFi if not using Ethernet.
5. After setup completes and you reach the desktop, open a terminal.

### 1.3 Enable SSH (for headless management from your Mac)

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable ssh
```

From your Mac, verify:
```bash
ssh jarvis@<jetson-ip>
```

Find the Jetson's IP with `ip addr show` or check your router's DHCP leases.

### 1.4 Connect Peripherals

| Peripheral | Port | Notes |
|-----------|------|-------|
| ReSpeaker Mic Array v3.0 | USB-A | Plug and play. Shows as USB audio device. |
| Speaker | 3.5mm jack or USB | The carrier board has a 3.5mm audio out. USB speakers also work. |
| Display (5.5" AMOLED) | HDMI | For the dashboard face UI. |

After connecting the ReSpeaker, verify:
```bash
arecord -l
# Should show "ReSpeaker" or "XMOS" as a capture device
```

---

## Phase 2: System Configuration

### 2.1 Performance Mode

The Jetson has multiple power modes. For JARVIS, you want maximum performance. The Jetson Orin Nano Super has two modes:

| Mode | Description | Power | Use case |
|------|-------------|-------|----------|
| `0` (MAXN) | All cores at max frequency, GPU at max | ~25W | **Use this** |
| `1` (15W) | Reduced CPU/GPU clocks | ~15W | Battery/thermal limited setups |

```bash
# Set MAXN mode (persists across reboots)
sudo nvpmodel -m 0

# Lock all clocks to maximum (does NOT persist -- needs to run on every boot)
sudo jetson_clocks

# Verify
sudo nvpmodel -q
# Should output: NV Power Mode: MAXN
```

**What `jetson_clocks` does under the hood:** The Jetson's CPU, GPU, and memory all have dynamic frequency scaling (like Intel SpeedStep or ARM DVFS). Under light load, the GPU might clock down to 306 MHz to save power. `jetson_clocks` pins every clock domain to its maximum frequency -- for the Orin Nano Super that is CPU at 1.5 GHz (all 6 cores), GPU at 1020 MHz, and memory at 3200 MHz. The tradeoff: ~25W constant power draw and more heat, but consistent latency for LLM inference. For a plugged-in voice assistant, this is the right choice.

### 2.2 Swap and zram Configuration

**Why this matters:** The Jetson has 8GB of LPDDR5 shared between CPU and GPU. At peak load, JARVIS uses roughly:
- Ollama (llama3.2:3b Q4_K_M): ~2.5GB GPU VRAM
- faster-whisper (small model): ~0.5GB GPU VRAM
- Python process + providers: ~0.5GB CPU RAM
- Chromium (dashboard): ~0.3GB CPU RAM
- mpv (music): ~0.1GB CPU RAM
- OS + services: ~0.8GB CPU RAM
- **Total: ~4.7GB**, leaving ~3.3GB headroom

That headroom sounds comfortable, but Linux will panic-kill processes (OOM killer) if you hit 100% with no swap. Swap provides a safety buffer for memory spikes (e.g., loading a new Ollama model, Chromium rendering a complex page).

**zram** is a Linux kernel module that creates a compressed block device in RAM. It sounds paradoxical -- "swap in RAM?" -- but the compression ratio is typically 2:1 to 3:1, so 4GB of zram effectively adds 8-12GB of virtual memory at the cost of CPU cycles for compression. On the Orin's 6-core ARM CPU, zram compression is negligible (a few microseconds per page).

**NVMe swap file** is the fallback when zram is full. NVMe is fast enough (~3000 MB/s) that occasional swap-out does not cause noticeable latency. microSD swap would be catastrophic -- do not do it.

```bash
# --- zram setup (4GB compressed, in-memory swap) ---
# JetPack 6.x comes with zram pre-configured but often too small.
# Check current config:
sudo zramctl

# If zram is not configured, or is too small:
sudo bash -c 'echo "zram" > /etc/modules-load.d/zram.conf'
sudo tee /etc/udev/rules.d/99-zram.rules << 'EOF'
KERNEL=="zram0", ATTR{disksize}="4G", ATTR{comp_algorithm}="lz4", TAG+="systemd"
EOF

# --- NVMe swap file (8GB emergency overflow) ---
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Set swappiness low so the kernel prefers zram over NVMe swap
# (higher = more willing to swap. 10 = only swap under pressure)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Verify
free -h
# Should show ~4GB zram + 8GB swap file
```

### 2.3 PulseAudio Configuration

PulseAudio ships pre-installed on JetPack 6.x. JARVIS needs it for audio ducking -- when TTS speaks, music volume drops to 20% instead of pausing. The `AudioFocusManager` in `core/audio_focus.py` auto-detects PulseAudio via `pactl` and uses the DUCK strategy.

```bash
# Verify PulseAudio is running
pactl info
# Should show "Server Name: PulseAudio" or "PipeWire (via pulse)"

# If it is not running (rare on JetPack):
pulseaudio --start

# Enable as a user service (auto-starts on login)
systemctl --user enable pulseaudio
```

### 2.4 Disable Unnecessary Services

The Jetson runs Ubuntu desktop by default. For a dedicated voice assistant, disable services that waste CPU and RAM.

```bash
# Disable GUI desktop (saves ~300MB RAM). Only do this if you are
# running the dashboard via Chromium in kiosk mode on autologin.
# NOTE: Keep the display server running if you need the AMOLED dashboard.
# This disables the full GNOME desktop, not the display server itself.
# sudo systemctl set-default multi-user.target  # uncomment if truly headless

# Disable snap (saves ~200MB RAM + CPU spikes from background updates)
sudo systemctl disable snapd.service snapd.socket snapd.seeded.service
sudo systemctl mask snapd.service

# Disable unattended upgrades (prevents random apt locks during operation)
sudo systemctl disable unattended-upgrades.service
sudo systemctl mask unattended-upgrades.service

# Disable the print service (not needed)
sudo systemctl disable cups.service cups-browsed.service 2>/dev/null

# Disable ModemManager (not needed unless using a cellular modem)
sudo systemctl disable ModemManager.service 2>/dev/null
```

### 2.5 Set Static IP (optional but recommended)

A static IP makes SSH, deploy scripts, and the companion app discovery reliable.

```bash
# Using nmcli (NetworkManager, default on JetPack):
CONN_NAME="Wired connection 1"  # check with: nmcli con show
sudo nmcli con mod "$CONN_NAME" \
  ipv4.method manual \
  ipv4.addresses 192.168.1.100/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "1.1.1.1,8.8.8.8"
sudo nmcli con up "$CONN_NAME"

# For WiFi (replace with your network name):
WIFI_CONN="YourWiFiSSID"
sudo nmcli con mod "$WIFI_CONN" \
  ipv4.method manual \
  ipv4.addresses 192.168.1.100/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "1.1.1.1,8.8.8.8"
sudo nmcli con up "$WIFI_CONN"
```

---

## Phase 3: Software Installation

### 3.1 System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

# Audio
sudo apt install -y portaudio19-dev libasound2-dev pulseaudio-utils

# Media
sudo apt install -y ffmpeg mpv

# TTS engine (espeak-ng is used by Piper as a phonemizer backend)
sudo apt install -y espeak-ng

# Build tools (needed for some pip packages with C extensions)
sudo apt install -y build-essential python3-dev python3-venv python3-pip

# Git (for pulling the project)
sudo apt install -y git

# Chromium (for the dashboard kiosk display)
sudo apt install -y chromium-browser

# Bluetooth tools (for BT speaker pairing)
sudo apt install -y bluez pulseaudio-module-bluetooth

# Misc utilities
sudo apt install -y curl wget jq htop
```

### 3.2 Python Virtual Environment

```bash
# Create the project directory
mkdir -p ~/jarvis
cd ~/jarvis

# Create venv with system-site-packages
# (needed for system-installed CUDA-aware packages like onnxruntime)
python3 -m venv .venv --system-site-packages

# Activate
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

**Why `--system-site-packages`:** JetPack pre-installs CUDA-aware versions of numpy, onnxruntime, and PyTorch that are compiled specifically for the Jetson's Ampere GPU. If you create a fully isolated venv, pip will install generic CPU-only wheels from PyPI that do not use CUDA. The `--system-site-packages` flag lets the venv see these pre-installed packages while still isolating your project's other dependencies.

### 3.3 Install Ollama (LLM Backend)

Ollama provides pre-built ARM64 Linux binaries that include CUDA support for the Jetson.

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Ollama installs as a systemd service automatically.
# Verify:
sudo systemctl status ollama

# Pull the LLM model (this downloads ~2GB):
ollama pull llama3.2:3b

# Quick test:
ollama run llama3.2:3b "Say hello in one sentence"
```

**What happens on the Jetson:** Ollama detects the Ampere GPU via CUDA and loads the model's weight matrices into GPU VRAM. The 3B model with Q4_K_M quantization (4-bit weights, ~2GB on disk) expands to about 2.5GB in VRAM when loaded. During inference, the GPU runs matrix multiplications (the attention and feedforward layers) at much higher throughput than CPU-only. On the Orin Nano Super at MAXN mode, expect ~25-35 tokens/second for the 3B model -- enough for real-time chat responses.

### 3.4 Python Dependencies

```bash
source ~/jarvis/.venv/bin/activate

# Core dependencies
pip install pyyaml requests websockets aiohttp

# Brain (LLM client)
pip install ollama

# Ears (STT) -- CTranslate2-optimized Whisper with CUDA
pip install faster-whisper

# Voice (TTS)
pip install kokoro  # Kokoro TTS (82M params, ONNX)
pip install piper-tts  # Piper TTS (CPU fallback)
pip install edge-tts  # Edge TTS (cloud, optional)

# Music
pip install ytmusicapi  # YouTube Music search (no API key)

# Lights
pip install tinytuya  # Tuya smart devices (local network control)

# Knowledge
pip install duckduckgo-search  # Web search (no API key)

# Wake word
pip install openwakeword  # Pre-trained wake word models

# Microphone
pip install sounddevice  # Cross-platform audio I/O
pip install webrtcvad  # Voice activity detection

# Memory
# sqlite3 is in Python stdlib -- no pip install needed

# Weather
pip install httpx  # Async HTTP client for Open-Meteo

# Companion app API
pip install fastapi uvicorn[standard]

# mDNS discovery
pip install zeroconf

# Timer/Reminder
pip install python-dateutil

# ONNX Runtime with CUDA (for Kokoro TTS on GPU)
# The JetPack system package may already provide this.
# Check first:
python3 -c "import onnxruntime; print(onnxruntime.get_available_providers())"
# If CUDAExecutionProvider is NOT listed:
pip install onnxruntime-gpu
```

**Note on XTTS (voice cloning):** XTTS requires ~1.5-2GB of VRAM. On the 8GB Jetson with Ollama already using 2.5GB, loading XTTS simultaneously is tight. The recommended setup uses Kokoro (ONNX, runs efficiently on CPU with ARM NEON) as the primary TTS. XTTS can be enabled as a personality-specific provider but may require unloading the Whisper model first.

### 3.5 Verify CUDA Stack

```bash
# Check CUDA version
nvcc --version
# Should show CUDA 12.x

# Check GPU visibility
python3 -c "
import subprocess
result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
print(result.stdout if result.returncode == 0 else 'nvidia-smi not found (normal on Jetson -- use tegrastats)')
"

# Note: Jetson does not have nvidia-smi. Use tegrastats instead:
sudo tegrastats --interval 1000
# Press Ctrl+C after seeing output. Look for "GR3D" (GPU utilization).

# Check faster-whisper CUDA
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('tiny', device='cuda', compute_type='float16')
print('faster-whisper CUDA: OK')
"
```

---

## Phase 4: JARVIS Configuration

### 4.1 Deploy the Code

The easiest method during development is `rsync` from your Mac (see `deploy.sh` in this directory). For the first time:

```bash
# On the Jetson:
mkdir -p ~/jarvis/assistant

# On your Mac:
rsync -avz --exclude '.venv' --exclude 'node_modules' --exclude '.git' \
  --exclude '__pycache__' --exclude '*.pyc' --exclude 'data/' \
  jarvis/assistant/ jarvis@<jetson-ip>:~/jarvis/assistant/
```

### 4.2 Create config.yaml

```bash
# On the Jetson:
cd ~/jarvis/assistant
cp config.example.yaml config.yaml
```

Then edit `config.yaml` with Jetson-specific values. A ready-to-use template is provided at `config.jetson.yaml` in the assistant directory -- copy it instead of `config.example.yaml` for fewer edits:

```bash
cp config.jetson.yaml config.yaml
# Then edit only: light device IDs/keys/IPs, WiFi, and personal preferences
```

Key Jetson-specific settings (see `config.jetson.yaml` for the full file with inline comments):

| Setting | Mac Value | Jetson Value | Why |
|---------|-----------|-------------|-----|
| `hardware.platform` | `"auto"` | `"auto"` or `"jetson"` | Auto-detect works. Force `"jetson"` to skip detection. |
| `ears.device` | `"auto"` (picks MPS) | `"auto"` (picks CUDA) | Auto-detect works on both. |
| `ears.model_size` | `"medium"` | `"small"` | Saves ~500MB VRAM. `small` is still good for Hindi/English. |
| `ears.beam_size` | (default 5) | `1` | Greedy decoding. Faster, negligible quality loss for short commands. |
| `brain.model` | `"llama3.2:3b"` | `"llama3.2:3b"` | Same model. Ollama handles quantization identically. |
| `voice.fallback_provider` | `"kokoro"` | `"kokoro"` | Same. Kokoro ONNX runs on CPU (ARM NEON optimized). |
| `audio.focus.strategy` | `"auto"` (picks pause) | `"auto"` (picks duck) | Auto-detect: PulseAudio present = duck mode. |
| `knowledge.max_results` | `3` | `3` | Keep low. Each result = ~100-150 tokens in LLM context. |
| `ui.enabled` | `true` | `true` | Dashboard runs on the AMOLED display. |
| `api.enabled` | `true` | `true` | Companion app API. |

### 4.3 Secrets

The following values are secrets and must NOT be committed to git. Edit them directly in `config.yaml` on the Jetson:

- `lights.devices[].device_id` -- Tuya device ID
- `lights.devices[].local_key` -- Tuya local encryption key
- `lights.devices[].ip` -- Bulb's local IP address
- `api.token` -- Bearer token for companion app (if auth_enabled)

---

## Phase 5: Auto-Start on Boot

### 5.1 Install systemd Services

The service files are in `jarvis/05-the-body/systemd/`. Copy them to the Jetson:

```bash
# On the Jetson:
sudo cp ~/jarvis/05-the-body/systemd/jarvis-assistant.service /etc/systemd/system/
sudo cp ~/jarvis/05-the-body/systemd/jarvis-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable jarvis-assistant.service
sudo systemctl enable jarvis-dashboard.service

# Start now
sudo systemctl start jarvis-assistant.service
# Wait 10 seconds for the WebSocket server to be ready
sleep 10
sudo systemctl start jarvis-dashboard.service
```

**Ollama:** The `ollama install.sh` script already creates a systemd service (`ollama.service`). The `jarvis-assistant.service` has `After=ollama.service` so it waits for Ollama to be ready.

### 5.2 View Logs

```bash
# Live logs from the assistant
journalctl -u jarvis-assistant -f

# Last 100 lines
journalctl -u jarvis-assistant -n 100

# Ollama logs
journalctl -u ollama -f

# Dashboard logs
journalctl -u jarvis-dashboard -f
```

### 5.3 Restart / Stop

```bash
sudo systemctl restart jarvis-assistant
sudo systemctl stop jarvis-assistant

# Full restart (all services)
sudo systemctl restart ollama jarvis-assistant jarvis-dashboard
```

---

## Phase 6: Display Setup (5.5" AMOLED)

### 6.1 HDMI Configuration

The 5.5" AMOLED displays typically run at 1080x1920 (portrait) or 1920x1080 (landscape). For the JARVIS face UI, landscape (1920x1080) or a custom resolution works best.

```bash
# Check connected displays
xrandr

# If the display is detected but at wrong resolution:
xrandr --output HDMI-0 --mode 1920x1080 --rate 60

# If the native resolution is not listed, add a custom mode:
# Example for 1080x1920 portrait mode:
xrandr --newmode "1080x1920" 159.93 1080 1144 1256 1432 1920 1921 1924 1960 -hsync +vsync
xrandr --addmode HDMI-0 "1080x1920"
xrandr --output HDMI-0 --mode "1080x1920"
```

To persist across reboots, add to `/etc/X11/xorg.conf.d/10-display.conf`:
```
Section "Monitor"
    Identifier "HDMI-0"
    Option "PreferredMode" "1920x1080"
EndSection
```

### 6.2 Disable Screen Blanking

The dashboard should always be visible. Disable all screen savers and power management:

```bash
# Disable DPMS (Display Power Management Signaling)
xset s off
xset -dpms
xset s noblank

# Persist across reboots -- add to ~/.xprofile (runs on X login)
cat >> ~/.xprofile << 'EOF'
xset s off
xset -dpms
xset s noblank
EOF

# Also disable the GNOME screen lock (if desktop is still running):
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.session idle-delay 0
```

### 6.3 Chromium Kiosk Mode

The `jarvis-dashboard.service` systemd unit starts Chromium in kiosk mode automatically. If you want to test manually:

```bash
chromium-browser --kiosk --no-first-run --disable-restore-session-state \
  --disable-session-crashed-bubble --noerrdialogs \
  --disable-infobars --check-for-update-interval=31536000 \
  --app=http://localhost:8765
```

This opens the FaceUI dashboard full-screen with no browser chrome. The `--app` flag tells Chromium to treat it like an application window.

### 6.4 Touch Input (if touchscreen)

If your 5.5" display has a touch digitizer (many AMOLED panels do):

```bash
# List input devices
xinput list

# Identify the touch device (usually "USB Touchscreen" or similar)
# Map it to the correct display if multi-monitor:
xinput map-to-output "USB Touchscreen" HDMI-0
```

---

## Phase 7: Audio Setup

### 7.1 ReSpeaker Mic Array Configuration

The ReSpeaker Mic Array v3.0 shows up as a standard USB audio device. No special drivers are needed on Linux -- the XMOS XVF-3000 DSP handles beamforming internally.

```bash
# List capture devices
arecord -l
# Look for: "card X: XMOS" or "card X: ReSpeaker"
# Note the card number (e.g., card 2)

# Test recording (3 seconds)
arecord -D hw:2,0 -f S16_LE -r 16000 -c 1 -d 3 test_mic.wav
# Replace "hw:2,0" with your card number

# Play it back
aplay test_mic.wav
```

### 7.2 Speaker Output

**3.5mm analog (simplest):**
```bash
# List playback devices
aplay -l
# The Jetson's onboard audio shows as "tegra" or "HDA NVidia"

# Test playback
speaker-test -D default -t wav -c 2 -l 1
```

**USB speaker:**
```bash
aplay -l
# Find the USB audio device card number
# Set as default PulseAudio sink:
pactl set-default-sink alsa_output.usb-<device-name>.analog-stereo
```

### 7.3 Set Default Mic and Speaker in PulseAudio

```bash
# List all sources (microphones)
pactl list sources short

# Set ReSpeaker as default input
pactl set-default-source alsa_input.usb-XMOS_ReSpeaker_4_Mic_Array-00.multichannel-input
# (the exact name depends on your device -- use tab completion)

# List all sinks (speakers)
pactl list sinks short

# Set your speaker as default output
pactl set-default-sink alsa_output.platform-3530000.hda.hdmi-stereo
# (or the USB/3.5mm sink name)

# Persist: PulseAudio remembers default devices across reboots
# on JetPack 6.x (module-default-device-restore is loaded by default)
```

### 7.4 Full Audio Round-Trip Test

```bash
# Record 3 seconds from the ReSpeaker, play back through the speaker
arecord -D default -f S16_LE -r 16000 -c 1 -d 3 /tmp/test.wav && aplay /tmp/test.wav
```

If you hear your own voice played back clearly, the audio pipeline is working.

---

## Phase 8: Performance Tuning

### 8.1 Ollama Memory Settings

```bash
# Edit the Ollama systemd override to add environment variables:
sudo systemctl edit ollama

# Add this content:
[Service]
Environment="OLLAMA_GPU_OVERHEAD=0"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"

# Save and restart
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**What these do:**

| Variable | Value | Explanation |
|----------|-------|-------------|
| `OLLAMA_GPU_OVERHEAD` | `0` | By default Ollama reserves ~300MB of GPU VRAM as buffer. On 8GB shared memory, every MB counts. Setting to 0 tells Ollama to use all available VRAM for the model. |
| `OLLAMA_NUM_PARALLEL` | `1` | Number of concurrent inference requests. JARVIS is single-user, so 1 is optimal. Each parallel slot allocates its own KV cache in VRAM (~200MB for 3B at 2048 context). |
| `OLLAMA_KEEP_ALIVE` | `-1` | Keep the model loaded in VRAM forever (until `ollama stop`). Default is 5 minutes of idle before unloading. Unloading and reloading takes 2-3 seconds -- unacceptable latency for a voice assistant. |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Only keep one model in memory. Prevents accidentally loading two models and OOM-ing. |

### 8.2 TTS Strategy: Kokoro on CPU, GPU for Ollama + Whisper

The 8GB shared memory budget is tight. The recommended allocation:

| Component | Device | VRAM/RAM | Notes |
|-----------|--------|----------|-------|
| Ollama (llama3.2:3b Q4) | GPU | ~2.5 GB | KV cache grows with context length |
| faster-whisper (small) | GPU | ~0.5 GB | Loaded on-demand during transcription |
| Kokoro TTS (82M ONNX) | CPU | ~0.3 GB RAM | ARM NEON SIMD is fast enough |
| Everything else | CPU | ~1.5 GB RAM | Python, mpv, Chromium, OS |
| **Total** | | **~4.8 GB** | Leaves ~3.2 GB headroom |

Kokoro runs on CPU because:
1. Its ONNX model is only 82M parameters -- ARM NEON vectorized inference is fast enough for real-time.
2. Moving it to GPU would add ~0.5 GB VRAM pressure, competing with Ollama's KV cache.
3. CPU and GPU can run in parallel -- while Kokoro synthesizes the next sentence on CPU, Ollama can process the next intent on GPU.

### 8.3 Temperature Monitoring

The Jetson Orin Nano has multiple thermal zones. Under sustained load (LLM inference + Whisper transcription), the GPU can hit 70-80 degrees C. The included heatsink + fan handle this, but monitor it during soak tests.

```bash
# Real-time thermal/memory/GPU monitoring
sudo tegrastats --interval 2000

# Output example:
# RAM 3456/7620MB (lfb 102x4MB) SWAP 0/8192MB CPU [45%@1510,30%@1510,...] GR3D [80%@1020] tj@52C soc2@48C
#
# Key fields:
#   RAM: used/total CPU RAM
#   GR3D: GPU utilization % @ clock speed in MHz
#   tj: junction temperature (the hottest point on the SoC die)
#   soc2: SoC package temperature

# Thermal zones (for scripting):
cat /sys/devices/virtual/thermal/thermal_zone*/temp
# Values are in millidegrees C (e.g., 52000 = 52 C)
```

**Thermal limits:** The Orin Nano throttles at 97 degrees C and shuts down at 105 degrees C. With the stock fan at MAXN mode, typical sustained load sits at 55-65 degrees C. If you see temperatures consistently above 75 degrees C, check that the fan is spinning and the heatsink has good contact.

### 8.4 Fan Control

The JetPack default fan profile ramps up with temperature. For a voice assistant in a quiet room, you may want to tune it:

```bash
# Check current fan mode
cat /sys/devices/pwm-fan/hwmon/hwmon*/cur_pwm
# 0 = off, 255 = full speed

# Set manual fan speed (0-255):
echo 128 | sudo tee /sys/devices/pwm-fan/hwmon/hwmon*/target_pwm

# Or set to automatic (temperature-based):
echo 0 | sudo tee /sys/devices/pwm-fan/hwmon/hwmon*/manual
```

For the birthday demo, set the fan to a moderate constant speed to avoid distracting spin-up noise during quiet moments:
```bash
echo 1 | sudo tee /sys/devices/pwm-fan/hwmon/hwmon*/manual
echo 100 | sudo tee /sys/devices/pwm-fan/hwmon/hwmon*/target_pwm
```

---

## Memory Budget

Detailed breakdown of what fits in 8GB shared LPDDR5:

```
+-------------------------------+----------+--------+
| Component                     | Location | Memory |
+-------------------------------+----------+--------+
| Linux kernel + drivers        | CPU RAM  | 0.4 GB |
| Desktop services (minimal)    | CPU RAM  | 0.3 GB |
| Ollama server process         | CPU RAM  | 0.2 GB |
| Ollama model (llama3.2:3b Q4) | GPU VRAM | 2.5 GB |
| faster-whisper (small, fp16)  | GPU VRAM | 0.5 GB |
| Kokoro TTS (ONNX, CPU)        | CPU RAM  | 0.3 GB |
| OpenWakeWord model            | CPU RAM  | 0.05GB |
| Python + assistant process    | CPU RAM  | 0.4 GB |
| Chromium (dashboard kiosk)    | CPU RAM  | 0.3 GB |
| mpv (music playback)          | CPU RAM  | 0.1 GB |
| PulseAudio                    | CPU RAM  | 0.05GB |
+-------------------------------+----------+--------+
| TOTAL                         |          | 5.1 GB |
| Available (8GB - total)       |          | 2.9 GB |
| zram (compressed in-RAM swap) |          | 4.0 GB |
| NVMe swap (emergency)         |          | 8.0 GB |
+-------------------------------+----------+--------+
```

**The comfortable zone:** With 2.9GB of free RAM + 4GB zram + 8GB NVMe swap, the system has ample breathing room. The risk scenarios are:
- Running XTTS (voice cloning) alongside Ollama and Whisper -- this could push over 7GB.
- Opening multiple Chromium tabs or a memory-heavy web page.
- Ollama loading a second model accidentally (prevented by `OLLAMA_MAX_LOADED_MODELS=1`).

---

## Troubleshooting

### Ollama fails to start or is very slow
```bash
# Check if CUDA is working
ollama run llama3.2:3b "test" 2>&1 | head -5
# Look for "using CUDA" or "no GPU detected"

# If CPU-only: check CUDA driver
ls /usr/local/cuda/
ldconfig -p | grep cuda
# If missing, reinstall JetPack
```

### "No audio capture devices found"
```bash
# Check if ReSpeaker is detected
lsusb | grep -i xmos
arecord -l
# If not listed: try a different USB port, reboot, or check dmesg for errors
dmesg | tail -30
```

### Dashboard not showing on the AMOLED
```bash
# Check if the assistant's WebSocket server is running
curl -s http://localhost:8765 && echo "WebSocket server OK" || echo "NOT running"

# Check Chromium
systemctl status jarvis-dashboard
journalctl -u jarvis-dashboard -n 20

# Try manually:
DISPLAY=:0 chromium-browser --app=http://localhost:8765
```

### OOM kills (assistant gets killed)
```bash
# Check if OOM killer struck
dmesg | grep -i "oom\|killed process"

# Check current memory state
free -h
sudo tegrastats --interval 1000

# If consistently close to 8GB:
# 1. Switch ears.model_size to "tiny" (saves ~300MB)
# 2. Reduce knowledge.max_results to 2
# 3. Disable Chromium dashboard (saves ~300MB)
```

### Music does not play (mpv errors)
```bash
# Check mpv is installed
which mpv
mpv --version

# Test mpv directly
mpv --no-video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Check PulseAudio sink
pactl list sinks short
# If no sinks: restart PulseAudio
pulseaudio -k && pulseaudio --start
```

### Thermal throttling (slow inference)
```bash
# Check temperature
cat /sys/devices/virtual/thermal/thermal_zone0/temp
# If above 85000 (85C):

# 1. Check fan is spinning
cat /sys/devices/pwm-fan/hwmon/hwmon*/cur_pwm
# If 0: fan is off. Enable it:
echo 0 | sudo tee /sys/devices/pwm-fan/hwmon/hwmon*/manual

# 2. Ensure heatsink is properly mounted (thermal paste/pad contact)
# 3. Improve ventilation in the enclosure
```

### jetson_clocks does not persist
`jetson_clocks` does not survive reboots. It is handled by the `jarvis-assistant.service` via `ExecStartPre`, or you can add it to a crontab:
```bash
sudo crontab -e
# Add:
@reboot /usr/bin/jetson_clocks
```

---

## Quick Reference Commands

```bash
# Start everything
sudo systemctl start ollama jarvis-assistant jarvis-dashboard

# Stop everything
sudo systemctl stop jarvis-dashboard jarvis-assistant

# View live assistant logs
journalctl -u jarvis-assistant -f

# Run health check
bash ~/jarvis/05-the-body/health_check.sh

# Run performance monitor
python3 ~/jarvis/05-the-body/monitor.py

# Deploy from Mac
./jarvis/05-the-body/deploy.sh jarvis@192.168.1.100

# SSH into Jetson
ssh jarvis@192.168.1.100

# Manual run (for debugging)
cd ~/jarvis/assistant
source ~/jarvis/.venv/bin/activate
python main.py --wake
```
