#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# JARVIS Brain — One-shot benchmark runner
# Run this on your Mac. It handles everything:
#   1. Checks/installs Ollama
#   2. Pulls candidate models
#   3. Runs the evaluation framework
#   4. Saves results
#
# Usage:
#   cd jarvis/01-the-brain
#   chmod +x run_benchmarks.sh
#   ./run_benchmarks.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  JARVIS Brain — Model Benchmark Runner"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ─── Step 1: Check Ollama ──────────────────────────────────────
if ! command -v ollama &> /dev/null; then
    echo "Ollama not found. Installing via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "ERROR: Homebrew not installed. Install from https://brew.sh first."
        exit 1
    fi
    brew install ollama
    echo "✓ Ollama installed"
else
    echo "✓ Ollama already installed: $(ollama --version)"
fi

# ─── Step 2: Start Ollama server if not running ───────────────
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama server..."
    ollama serve &
    OLLAMA_PID=$!
    sleep 3
    echo "✓ Ollama server started (PID: $OLLAMA_PID)"
else
    echo "✓ Ollama server already running"
    OLLAMA_PID=""
fi

# ─── Step 3: Pull models ──────────────────────────────────────
MODELS=("qwen2.5:3b" "llama3.2:3b" "phi4-mini")

echo ""
echo "Pulling ${#MODELS[@]} models for comparison..."
echo "(This may take a few minutes on first run)"
echo ""

for model in "${MODELS[@]}"; do
    echo "─── Pulling: $model ───"
    ollama pull "$model"
    echo "✓ $model ready"
    echo ""
done

# ─── Step 4: Install Python dependencies ──────────────────────
echo "Checking Python dependencies..."
pip3 install requests pyyaml --quiet 2>/dev/null || pip install requests pyyaml --quiet 2>/dev/null
echo "✓ Dependencies ready"

# ─── Step 5: Run benchmarks ───────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Running evaluation framework..."
echo "═══════════════════════════════════════════════════════════"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/experiments"

python3 eval_framework.py "${MODELS[@]}"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Done! Check notes/eval-results/ for detailed JSON."
echo "═══════════════════════════════════════════════════════════"

# Clean up if we started Ollama
if [ -n "$OLLAMA_PID" ]; then
    echo ""
    echo "Note: Ollama server is still running (PID: $OLLAMA_PID)."
    echo "To stop it: kill $OLLAMA_PID"
fi
