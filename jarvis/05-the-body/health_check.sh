#!/usr/bin/env bash
# ===================================================================
# JARVIS Health Check -- Jetson Orin Nano
# ===================================================================
# Quick diagnostic script to verify all JARVIS components are working.
# Run this after deployment or when something seems off.
#
# Usage:
#   bash health_check.sh
#   bash health_check.sh --verbose    # show extra debug info
#
# Exit code: 0 if all critical checks pass, 1 otherwise.
# ===================================================================

set -euo pipefail

VERBOSE=false
if [[ "${1:-}" == "--verbose" || "${1:-}" == "-v" ]]; then
    VERBOSE=true
fi

PASS=0
FAIL=0
WARN=0

# Colors (auto-disabled when piped)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
fi

pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    PASS=$((PASS + 1))
}

fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    FAIL=$((FAIL + 1))
}

warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    WARN=$((WARN + 1))
}

info() {
    if $VERBOSE; then
        echo -e "  ${CYAN}[INFO]${NC} $1"
    fi
}

section() {
    echo ""
    echo -e "${BOLD}=== $1 ===${NC}"
}

# ── Platform ─────────────────────────────────────────────────────

section "Platform"

if [ -f /etc/nv_tegra_release ]; then
    TEGRA_VERSION=$(head -1 /etc/nv_tegra_release 2>/dev/null || echo "unknown")
    pass "Jetson detected: $TEGRA_VERSION"
else
    SYSTEM=$(uname -s)
    if [ "$SYSTEM" = "Darwin" ]; then
        warn "Running on macOS (not Jetson) -- some checks will be skipped"
    else
        warn "Not a Jetson platform ($SYSTEM) -- some checks may not apply"
    fi
fi

# ── CUDA ─────────────────────────────────────────────────────────

section "CUDA"

if command -v nvcc &>/dev/null; then
    CUDA_VER=$(nvcc --version 2>/dev/null | grep "release" | awk '{print $6}' | tr -d ',')
    pass "CUDA compiler: $CUDA_VER"
else
    # On Jetson without nvcc in PATH, check the library
    if [ -d /usr/local/cuda ]; then
        warn "CUDA directory exists but nvcc not in PATH"
    elif [ "$(uname -s)" = "Darwin" ]; then
        info "CUDA not applicable on macOS (uses Metal/MPS)"
    else
        fail "CUDA not found -- LLM inference will be CPU-only (very slow)"
    fi
fi

# Check CUDA devices via Python
if command -v python3 &>/dev/null; then
    CUDA_CHECK=$(python3 -c "
try:
    import ctypes
    libcuda = ctypes.CDLL('libcuda.so')
    count = ctypes.c_int()
    libcuda.cuInit(0)
    libcuda.cuDeviceGetCount(ctypes.byref(count))
    print(f'ok:{count.value}')
except Exception as e:
    print(f'fail:{e}')
" 2>/dev/null || echo "fail:python error")
    if [[ "$CUDA_CHECK" == ok:* ]]; then
        GPU_COUNT="${CUDA_CHECK#ok:}"
        pass "CUDA devices: $GPU_COUNT"
    else
        info "CUDA device check skipped: ${CUDA_CHECK#fail:}"
    fi
fi

# ── Ollama ───────────────────────────────────────────────────────

section "Ollama"

if command -v ollama &>/dev/null; then
    pass "ollama binary found: $(which ollama)"
else
    fail "ollama not installed"
fi

# Check if Ollama service is running
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    pass "Ollama server is running on :11434"

    # Check if the model is loaded
    MODELS=$(curl -sf http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print(','.join(models) if models else 'none')
" 2>/dev/null || echo "error")

    if [ "$MODELS" != "none" ] && [ "$MODELS" != "error" ]; then
        pass "Models available: $MODELS"
    else
        fail "No models found -- run: ollama pull llama3.2:3b"
    fi
else
    fail "Ollama server not responding on :11434"
fi

# ── Python Environment ───────────────────────────────────────────

section "Python Environment"

VENV_PYTHON="$HOME/jarvis/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PY_VER=$("$VENV_PYTHON" --version 2>/dev/null)
    pass "venv Python: $PY_VER"
else
    # Try system python
    VENV_PYTHON="python3"
    warn "venv not found at ~/jarvis/.venv -- using system python3"
fi

# Check critical imports
IMPORT_CHECK=$("$VENV_PYTHON" -c "
results = []
for mod in ['yaml', 'requests', 'websockets', 'sounddevice', 'faster_whisper', 'tinytuya']:
    try:
        __import__(mod)
        results.append(f'{mod}:ok')
    except ImportError:
        results.append(f'{mod}:missing')
print('|'.join(results))
" 2>/dev/null || echo "error")

if [ "$IMPORT_CHECK" != "error" ]; then
    IFS='|' read -ra MODULES <<< "$IMPORT_CHECK"
    for entry in "${MODULES[@]}"; do
        MOD="${entry%%:*}"
        STATUS="${entry##*:}"
        if [ "$STATUS" = "ok" ]; then
            pass "Python module: $MOD"
        else
            fail "Python module missing: $MOD"
        fi
    done
else
    fail "Python import check failed"
fi

# ── Audio Devices ────────────────────────────────────────────────

section "Audio Devices"

# Microphone
if command -v arecord &>/dev/null; then
    MIC_COUNT=$(arecord -l 2>/dev/null | grep -c "^card" || echo "0")
    if [ "$MIC_COUNT" -gt 0 ]; then
        pass "Capture devices: $MIC_COUNT"
        if $VERBOSE; then
            arecord -l 2>/dev/null | grep "^card" | while read -r line; do
                info "  $line"
            done
        fi
    else
        fail "No capture devices (microphone) detected"
    fi
elif [ "$(uname -s)" = "Darwin" ]; then
    info "arecord not available on macOS -- skipping mic check"
else
    warn "arecord not found -- install: sudo apt install alsa-utils"
fi

# Speaker
if command -v aplay &>/dev/null; then
    SPK_COUNT=$(aplay -l 2>/dev/null | grep -c "^card" || echo "0")
    if [ "$SPK_COUNT" -gt 0 ]; then
        pass "Playback devices: $SPK_COUNT"
    else
        fail "No playback devices (speaker) detected"
    fi
elif [ "$(uname -s)" = "Darwin" ]; then
    info "aplay not available on macOS -- skipping speaker check"
else
    warn "aplay not found -- install: sudo apt install alsa-utils"
fi

# PulseAudio
if command -v pactl &>/dev/null; then
    if pactl info &>/dev/null 2>&1; then
        PA_VER=$(pactl info 2>/dev/null | grep "Server String" | head -1 || echo "running")
        pass "PulseAudio: running"
    else
        warn "pactl found but PulseAudio not responding"
    fi
else
    info "pactl not found -- audio ducking will use pause strategy"
fi

# ── External Commands ────────────────────────────────────────────

section "External Commands"

for cmd in mpv ffmpeg espeak-ng curl jq; do
    if command -v "$cmd" &>/dev/null; then
        pass "$cmd: $(which "$cmd")"
    else
        case "$cmd" in
            mpv) fail "$cmd not found -- music playback will not work" ;;
            ffmpeg) fail "$cmd not found -- audio processing will not work" ;;
            *) warn "$cmd not found" ;;
        esac
    fi
done

# ── Network Services ─────────────────────────────────────────────

section "Network Services"

# WebSocket server (FaceUI dashboard)
if curl -sf --max-time 3 http://localhost:8765 >/dev/null 2>&1; then
    pass "Dashboard WebSocket server on :8765"
else
    # Try just connecting to the port
    if (echo >/dev/tcp/localhost/8765) 2>/dev/null; then
        pass "Dashboard WebSocket port 8765 is open"
    else
        warn "Dashboard WebSocket server not responding on :8765 (assistant may not be running)"
    fi
fi

# API server (companion app)
if curl -sf --max-time 3 http://localhost:8766/health >/dev/null 2>&1; then
    pass "Companion API server on :8766"
elif curl -sf --max-time 3 http://localhost:8766/ >/dev/null 2>&1; then
    pass "Companion API server on :8766 (no /health endpoint)"
else
    if (echo >/dev/tcp/localhost/8766) 2>/dev/null; then
        pass "Companion API port 8766 is open"
    else
        warn "Companion API server not responding on :8766"
    fi
fi

# ── System Resources ─────────────────────────────────────────────

section "System Resources"

# RAM
MEM_INFO=$(free -m 2>/dev/null | awk '/^Mem:/ {printf "%d/%dMB (%.0f%% used)", $3, $2, $3/$2*100}')
if [ -n "$MEM_INFO" ]; then
    MEM_PCT=$(free -m 2>/dev/null | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    if [ "$MEM_PCT" -gt 90 ]; then
        fail "RAM: $MEM_INFO -- CRITICAL (>90%)"
    elif [ "$MEM_PCT" -gt 75 ]; then
        warn "RAM: $MEM_INFO -- elevated (>75%)"
    else
        pass "RAM: $MEM_INFO"
    fi
fi

# Swap
SWAP_INFO=$(free -m 2>/dev/null | awk '/^Swap:/ {if ($2 > 0) printf "%d/%dMB", $3, $2; else print "none"}')
if [ "$SWAP_INFO" = "none" ]; then
    warn "No swap configured -- risk of OOM kills"
else
    pass "Swap: $SWAP_INFO"
fi

# Temperature (Jetson only)
if [ -f /sys/devices/virtual/thermal/thermal_zone0/temp ]; then
    TEMP_MC=$(cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null || echo "0")
    TEMP_C=$((TEMP_MC / 1000))
    if [ "$TEMP_C" -gt 85 ]; then
        fail "Temperature: ${TEMP_C}C -- CRITICAL (throttling likely)"
    elif [ "$TEMP_C" -gt 70 ]; then
        warn "Temperature: ${TEMP_C}C -- warm (check fan)"
    else
        pass "Temperature: ${TEMP_C}C"
    fi
fi

# Disk space
DISK_PCT=$(df -h / 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
DISK_INFO=$(df -h / 2>/dev/null | awk 'NR==2 {printf "%s/%s (%s used)", $3, $2, $5}')
if [ -n "$DISK_PCT" ]; then
    if [ "$DISK_PCT" -gt 90 ]; then
        fail "Disk: $DISK_INFO -- CRITICAL"
    elif [ "$DISK_PCT" -gt 75 ]; then
        warn "Disk: $DISK_INFO"
    else
        pass "Disk: $DISK_INFO"
    fi
fi

# ── systemd Services ─────────────────────────────────────────────

section "systemd Services"

for svc in ollama jarvis-assistant jarvis-dashboard; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        pass "$svc: active"
    elif systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        warn "$svc: enabled but not running"
    else
        info "$svc: not configured"
    fi
done

# ── Summary ──────────────────────────────────────────────────────

section "Summary"

TOTAL=$((PASS + FAIL + WARN))
echo ""
echo -e "  ${GREEN}Passed:${NC}   $PASS"
echo -e "  ${RED}Failed:${NC}   $FAIL"
echo -e "  ${YELLOW}Warnings:${NC} $WARN"
echo -e "  Total:    $TOTAL checks"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}All critical checks passed.${NC}"
    exit 0
else
    echo -e "  ${RED}${BOLD}$FAIL critical check(s) failed. See above for details.${NC}"
    exit 1
fi
