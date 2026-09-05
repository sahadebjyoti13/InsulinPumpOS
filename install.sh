#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  InsulinPump OS — Installer
#  Run this script once to install and start the system.
#  Usage:  bash install.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[InsulinPump OS]${NC} $1"; }
warn()    { echo -e "${YELLOW}[Warning]${NC} $1"; }
error()   { echo -e "${RED}[Error]${NC} $1"; exit 1; }

echo ""
echo "  ██████╗ ██╗   ██╗███╗   ███╗██████╗"
echo "  ██╔══██╗██║   ██║████╗ ████║██╔══██╗"
echo "  ██████╔╝██║   ██║██╔████╔██║██████╔╝"
echo "  ██╔═══╝ ██║   ██║██║╚██╔╝██║██╔═══╝"
echo "  ██║     ╚██████╔╝██║ ╚═╝ ██║██║"
echo "  ╚═╝      ╚═════╝ ╚═╝     ╚═╝╚═╝  InsulinPump OS"
echo ""

# ── Check Docker ─────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    error "Docker is not installed.\nPlease install Docker Desktop from https://www.docker.com and re-run this script."
fi

if ! docker info &>/dev/null; then
    error "Docker is installed but not running.\nPlease start Docker Desktop and re-run this script."
fi

if ! docker compose version &>/dev/null 2>&1; then
    error "Docker Compose plugin not found.\nPlease update Docker Desktop to the latest version."
fi

info "Docker found ✅"

# ── Pull images ───────────────────────────────────────────────────────────────
info "Pulling service images (this may take a few minutes on first run)…"
docker compose pull --quiet 2>/dev/null || true

# ── Start stack ───────────────────────────────────────────────────────────────
info "Starting all services…"
docker compose up -d --build

# ── Wait for webapp ───────────────────────────────────────────────────────────
info "Waiting for the web app to become ready…"
MAX_WAIT=90
ELAPSED=0
until curl -sf http://localhost:8501/_stcore/health &>/dev/null || [ "$ELAPSED" -ge "$MAX_WAIT" ]; do
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo -n "."
done
echo ""

if curl -sf http://localhost:8501/_stcore/health &>/dev/null; then
    info "System is ready! 🚀"
    echo ""
    echo "  ┌────────────────────────────────────────┐"
    echo "  │  Open your browser:                    │"
    echo "  │  👉  http://localhost:8501             │"
    echo "  └────────────────────────────────────────┘"
    echo ""
else
    warn "The app is taking longer than expected to start."
    warn "Check status with:  docker compose logs webapp"
    warn "Then open:          http://localhost:8501"
fi

# ── Helpful tips ──────────────────────────────────────────────────────────────
echo ""
info "Useful commands:"
echo "  Stop system:    docker compose down"
echo "  View logs:      docker compose logs -f"
echo "  Restart app:    docker compose restart webapp"
echo ""
