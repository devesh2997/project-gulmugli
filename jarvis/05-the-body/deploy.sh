#!/usr/bin/env bash
# ===================================================================
# JARVIS Deploy Script -- Mac to Jetson
# ===================================================================
# One-command deployment: syncs the project, installs services,
# restarts everything, and runs the health check.
#
# Usage:
#   ./deploy.sh jarvis@192.168.1.100
#   ./deploy.sh jarvis@192.168.1.100 --sync-only    # just rsync, no restart
#   ./deploy.sh jarvis@192.168.1.100 --restart-only  # just restart services
#   ./deploy.sh jarvis@192.168.1.100 --health        # just run health check
#
# Prerequisites:
#   - SSH key-based auth configured (ssh-copy-id jarvis@<ip>)
#   - Jetson has completed Phase 1-3 of JETSON_SETUP.md
#
# What it does:
#   1. rsync the project to the Jetson (excluding .venv, .git, etc.)
#   2. Copy systemd service files
#   3. Restart Ollama + assistant + dashboard services
#   4. Run the health check
# ===================================================================

set -euo pipefail

# Colors
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

log()  { echo -e "${CYAN}[deploy]${NC} $1"; }
ok()   { echo -e "${GREEN}[deploy]${NC} $1"; }
err()  { echo -e "${RED}[deploy]${NC} $1" >&2; }
warn() { echo -e "${YELLOW}[deploy]${NC} $1"; }

# ── Parse arguments ──────────────────────────────────────────────

if [ $# -lt 1 ]; then
    echo "Usage: $0 <user@jetson-ip> [--sync-only|--restart-only|--health]"
    echo ""
    echo "Examples:"
    echo "  $0 jarvis@192.168.1.100           # full deploy"
    echo "  $0 jarvis@192.168.1.100 --sync-only"
    echo "  $0 jarvis@192.168.1.100 --restart-only"
    echo "  $0 jarvis@192.168.1.100 --health"
    exit 1
fi

TARGET="$1"
MODE="${2:-full}"

# ── Locate project root ─────────────────────────────────────────

# This script lives at jarvis/05-the-body/deploy.sh
# Project root is two directories up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
JARVIS_DIR="$PROJECT_ROOT/jarvis"

if [ ! -f "$JARVIS_DIR/assistant/main.py" ]; then
    err "Cannot find jarvis/assistant/main.py from project root: $PROJECT_ROOT"
    err "Are you running this from the right directory?"
    exit 1
fi

log "Project root: $PROJECT_ROOT"
log "Deploy target: $TARGET"

# ── Verify SSH connectivity ──────────────────────────────────────

log "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$TARGET" "echo ok" >/dev/null 2>&1; then
    err "Cannot connect to $TARGET via SSH."
    err "Make sure:"
    err "  1. The Jetson is powered on and connected to the network"
    err "  2. SSH is enabled (sudo systemctl enable ssh)"
    err "  3. SSH key is configured (ssh-copy-id $TARGET)"
    exit 1
fi
ok "SSH connection verified."

# ── Remote directory setup ───────────────────────────────────────

REMOTE_BASE="~/jarvis"

ssh "$TARGET" "mkdir -p $REMOTE_BASE/assistant $REMOTE_BASE/05-the-body/systemd"

# ── Sync ─────────────────────────────────────────────────────────

do_sync() {
    log "Syncing project files to Jetson..."

    # Sync the assistant code (the main codebase)
    rsync -avz --delete \
        --exclude '.venv' \
        --exclude 'node_modules' \
        --exclude '.git' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.DS_Store' \
        --exclude 'data/' \
        --exclude 'config.yaml' \
        "$JARVIS_DIR/assistant/" \
        "$TARGET:$REMOTE_BASE/assistant/"

    # Sync the 05-the-body directory (systemd files, health check, etc.)
    rsync -avz --delete \
        --exclude '.DS_Store' \
        "$JARVIS_DIR/05-the-body/" \
        "$TARGET:$REMOTE_BASE/05-the-body/"

    # Sync the dashboard UI
    if [ -d "$JARVIS_DIR/assistant/ui" ]; then
        rsync -avz --delete \
            --exclude '.DS_Store' \
            "$JARVIS_DIR/assistant/ui/" \
            "$TARGET:$REMOTE_BASE/assistant/ui/"
    fi

    # Sync the API server
    if [ -d "$JARVIS_DIR/assistant/api" ]; then
        rsync -avz --delete \
            --exclude '.DS_Store' \
            --exclude '__pycache__' \
            "$JARVIS_DIR/assistant/api/" \
            "$TARGET:$REMOTE_BASE/assistant/api/"
    fi

    ok "Sync complete."

    # Check if config.yaml exists on remote
    if ! ssh "$TARGET" "test -f $REMOTE_BASE/assistant/config.yaml"; then
        warn "config.yaml does not exist on Jetson!"
        warn "The assistant will not start without it."
        warn "On the Jetson, run:"
        warn "  cd ~/jarvis/assistant"
        warn "  cp config.jetson.yaml config.yaml"
        warn "  # Then edit config.yaml with your light device secrets"
    fi
}

# ── Install systemd services ─────────────────────────────────────

install_services() {
    log "Installing systemd service files..."

    ssh "$TARGET" "
        sudo cp $REMOTE_BASE/05-the-body/systemd/jarvis-assistant.service /etc/systemd/system/ 2>/dev/null || true
        sudo cp $REMOTE_BASE/05-the-body/systemd/jarvis-dashboard.service /etc/systemd/system/ 2>/dev/null || true

        # Ollama override (if not already overridden)
        if [ -f $REMOTE_BASE/05-the-body/systemd/jarvis-ollama.service ]; then
            sudo mkdir -p /etc/systemd/system/ollama.service.d/
            sudo cp $REMOTE_BASE/05-the-body/systemd/jarvis-ollama.service /etc/systemd/system/ollama.service.d/override.conf
        fi

        sudo systemctl daemon-reload
        sudo systemctl enable jarvis-assistant.service 2>/dev/null || true
        sudo systemctl enable jarvis-dashboard.service 2>/dev/null || true
    "

    ok "systemd services installed."
}

# ── Restart services ──────────────────────────────────────────────

do_restart() {
    log "Restarting services..."

    ssh "$TARGET" "
        echo 'Stopping assistant and dashboard...'
        sudo systemctl stop jarvis-dashboard 2>/dev/null || true
        sudo systemctl stop jarvis-assistant 2>/dev/null || true

        echo 'Restarting Ollama...'
        sudo systemctl restart ollama 2>/dev/null || true

        echo 'Waiting for Ollama to be ready...'
        for i in \$(seq 1 15); do
            if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
                echo 'Ollama ready.'
                break
            fi
            sleep 1
        done

        echo 'Starting assistant...'
        sudo systemctl start jarvis-assistant

        echo 'Waiting for assistant to bind ports...'
        sleep 8

        echo 'Starting dashboard...'
        sudo systemctl start jarvis-dashboard 2>/dev/null || true
    "

    ok "Services restarted."
}

# ── Health check ──────────────────────────────────────────────────

do_health() {
    log "Running health check..."
    echo ""

    ssh "$TARGET" "bash $REMOTE_BASE/05-the-body/health_check.sh"

    echo ""
    ok "Health check complete."
}

# ── Execute requested mode ────────────────────────────────────────

case "$MODE" in
    --sync-only)
        do_sync
        ;;
    --restart-only)
        do_restart
        ;;
    --health)
        do_health
        ;;
    full|*)
        do_sync
        install_services
        do_restart
        log "Waiting 5 seconds for services to stabilize..."
        sleep 5
        do_health
        echo ""
        ok "Deployment complete!"
        echo ""
        log "Useful commands:"
        log "  ssh $TARGET 'journalctl -u jarvis-assistant -f'   # live logs"
        log "  ssh $TARGET 'sudo systemctl restart jarvis-assistant'"
        log "  $0 $TARGET --health                                # quick check"
        ;;
esac
