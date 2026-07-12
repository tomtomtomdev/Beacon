#!/usr/bin/env bash
# run.sh — one-step launcher for Beacon (ingest + API + frontend).
#
#   ./run.sh              full run: install deps if missing, ingest, then serve API + frontend
#   ./run.sh --no-ingest  skip the ingest step (serve the existing beacon.db as-is)
#   ./run.sh --setup      force a dependency (re)install before running
#
# API listens on :8000 (the port the Vite dev-server proxy expects); the frontend
# runs in the foreground. Ctrl-C stops both.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
API_PORT=8000   # hardcoded: frontend/vite.config proxies /jobs + /healthz to localhost:8000

INGEST=1
SETUP=0
for arg in "$@"; do
  case "$arg" in
    --no-ingest) INGEST=0 ;;
    --setup)     SETUP=1 ;;
    -h|--help)   sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

log() { printf '\n\033[36m▶ %s\033[0m\n' "$*"; }

# --- dependencies -----------------------------------------------------------
if [[ $SETUP -eq 1 || ! -d "$BACKEND/.venv" ]]; then
  log "Installing backend deps (uv sync)"
  (cd "$BACKEND" && uv sync)
fi
if [[ $SETUP -eq 1 || ! -d "$FRONTEND/node_modules" ]]; then
  log "Installing frontend deps (npm install)"
  (cd "$FRONTEND" && npm install)
fi

# --- ingest (resilient: a failed poll must never abort the launch) ----------
if [[ $INGEST -eq 1 ]]; then
  log "Ingesting jobs into beacon.db"
  (cd "$BACKEND" && uv run python -m beacon.ingest) || echo "⚠ ingest reported errors — continuing to serve"
fi

# --- serve ------------------------------------------------------------------
API_PID=""
cleanup() { [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

log "Starting API → http://localhost:$API_PORT  (healthz, /jobs, /companies/health, /countries, …)"
(cd "$BACKEND" && exec uv run uvicorn beacon.api.app:create_app --factory --port "$API_PORT") &
API_PID=$!

# brief, non-fatal readiness wait so the first UI request isn't a proxy miss
for _ in $(seq 1 30); do
  curl -sf "http://localhost:$API_PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.5
done

log "Starting frontend (Vite dev server) — Ctrl-C to stop everything"
cd "$FRONTEND" && npm run dev
