#!/usr/bin/env bash
# run.sh — one-step launcher for Beacon (API + frontend, with a background refresh).
#
#   ./run.sh                serve the cached beacon.db immediately, refresh from the source
#                           APIs in the background; fresh jobs are cached for the next run
#   ./run.sh --no-ingest    skip the refresh entirely (cached jobs only)
#   ./run.sh --wait-ingest  old behaviour: finish the refresh before serving anything
#   ./run.sh --setup        force a dependency (re)install before running
#
# beacon.db IS the cache: the UI is served from it while `python -m beacon.ingest` polls
# the sources into the same file (SQLite is in WAL mode, so reads never block on the poll).
# Refresh output goes to .ingest.log, with a one-line verdict when it finishes.
# First run only (no beacon.db yet) the refresh is blocking — there is nothing to serve.
#
# Telegram digests are sent at three points in a run:
#   launch    what is already pending — source health + any un-notified matches
#   refresh   the poll's own digest, when it finishes (inside `python -m beacon.ingest`)
#   close     whatever this session turned up, even if Ctrl-C cut the poll short; sent
#             --matches-only, so a session that found nothing new sends nothing
# No Telegram creds set (Settings UI or BEACON_TELEGRAM_*) → the same digests print to
# .digest.log instead. The launch/close sends cost one API call each, never a poll.
#
# API listens on :8000 (the port the Vite dev-server proxy expects); the frontend
# runs in the foreground. Ctrl-C stops everything.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
API_PORT=8000   # hardcoded: frontend/vite.config proxies the API routes (/jobs, /countries, /companies, /resumes, /searches, /settings, /healthz) to localhost:8000

DB="${BEACON_DB_PATH:-$ROOT/beacon.db}"   # the cache itself; matches Settings.from_env()
INGEST_LOG="$ROOT/.ingest.log"
DIGEST_LOG="$ROOT/.digest.log"   # launch/close digest output (and where the digest itself lands with no Telegram creds)

INGEST=1
WAIT_INGEST=0
SETUP=0
for arg in "$@"; do
  case "$arg" in
    --no-ingest)   INGEST=0 ;;
    --wait-ingest) WAIT_INGEST=1 ;;
    --setup)       SETUP=1 ;;
    # The header block is the help text; read it to the first non-comment line so it cannot
    # rot against a hardcoded line range.
    -h|--help)     awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# Nothing cached yet — a background refresh would serve an empty UI, so block on this one.
if [[ $INGEST -eq 1 && ! -f "$DB" ]]; then
  WAIT_INGEST=1
fi

log() { printf '\n\033[36m▶ %s\033[0m\n' "$*"; }

# --- node/npm on PATH -------------------------------------------------------
# This script runs under a non-interactive shell, where nvm's shell function is
# never loaded — so `npm` can be missing even though node is installed. Resolve
# it ourselves: whatever is already on PATH wins, then nvm's `default` alias,
# then the highest installed nvm version.
if ! command -v npm >/dev/null 2>&1; then
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  npm_bin=""
  default_alias=""
  [[ -f "$NVM_DIR/alias/default" ]] && default_alias="$(cat "$NVM_DIR/alias/default")"
  while IFS= read -r dir; do
    [[ -x "$dir/bin/npm" ]] || continue
    if [[ -n "$default_alias" && "$(basename "$dir")" == "v$default_alias"* ]]; then
      npm_bin="$dir/bin"; break
    fi
    [[ -z "$npm_bin" ]] && npm_bin="$dir/bin"   # highest version, as fallback
  done < <(find "$NVM_DIR/versions/node" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort -Vr)
  if [[ -z "$npm_bin" ]]; then
    echo "npm not found: install Node (e.g. \`nvm install --lts\`) or put npm on PATH" >&2
    exit 127
  fi
  PATH="$npm_bin:$PATH"
  export PATH
fi

# --- dependencies -----------------------------------------------------------
if [[ $SETUP -eq 1 || ! -d "$BACKEND/.venv" ]]; then
  log "Installing backend deps (uv sync)"
  (cd "$BACKEND" && uv sync)
fi
if [[ $SETUP -eq 1 || ! -d "$FRONTEND/node_modules" ]]; then
  log "Installing frontend deps (npm install)"
  (cd "$FRONTEND" && npm install)
fi

# --- blocking refresh (first run, or --wait-ingest) ------------------------
# Resilient either way: a failed poll must never abort the launch.
if [[ $INGEST -eq 1 && $WAIT_INGEST -eq 1 ]]; then
  log "Refreshing jobs into beacon.db (blocking — nothing cached to serve yet)"
  (cd "$BACKEND" && uv run python -m beacon.ingest) || echo "⚠ refresh reported errors — continuing to serve"
  INGEST=0
fi

# --- launch digest ----------------------------------------------------------
# What is already pending, on the phone now: source health plus any matches the last poll
# left un-notified. Runs before the API so the report does not wait on the ~30-45 min poll.
log "Sending the launch digest (→ Telegram, or ${DIGEST_LOG#"$ROOT/"} with no creds)"
(cd "$BACKEND" && uv run python -m beacon.notify) 2>&1 | tee "$DIGEST_LOG" | grep -E 'searches=|Error|error' || true

# --- serve ------------------------------------------------------------------
API_PID=""
INGEST_PID=""
CLEANED=0
cleanup() {
  # Ctrl-C fires INT and then EXIT; without this guard the closing digest would send twice.
  if [[ $CLEANED -eq 1 ]]; then return 0; fi
  CLEANED=1
  [[ -n "$INGEST_PID" ]] && kill "$INGEST_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  # Closing digest: whatever this session turned up, including a poll Ctrl-C cut short before
  # it could send its own. --matches-only drops the source-health section, so a session that
  # found nothing new sends nothing rather than repeating the launch digest. Never fatal —
  # a failed send must not hold up shutdown.
  printf '\n\033[36m▶ Closing digest (new matches only)\033[0m\n'
  (cd "$BACKEND" && uv run python -m beacon.notify --matches-only) >>"$DIGEST_LOG" 2>&1 || true
  grep -E 'searches=' "$DIGEST_LOG" | tail -1 || true
}
trap cleanup EXIT INT TERM

log "Starting API → http://localhost:$API_PORT  (healthz, /jobs, /companies/health, /countries, …)"
(cd "$BACKEND" && exec uv run uvicorn beacon.api.app:create_app --factory --port "$API_PORT") &
API_PID=$!

# brief, non-fatal readiness wait so the first UI request isn't a proxy miss
for _ in $(seq 1 30); do
  curl -sf "http://localhost:$API_PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.5
done

# --- background refresh -----------------------------------------------------
# The cached rows are already being served; poll the sources into the same beacon.db and
# announce the verdict when it lands. Output is redirected so it cannot interleave with
# the Vite dev-server log.
if [[ $INGEST -eq 1 ]]; then
  log "Serving cached jobs — refreshing from source APIs in the background (→ ${INGEST_LOG#"$ROOT/"})"
  (
    status=0
    (cd "$BACKEND" && uv run python -m beacon.ingest) >"$INGEST_LOG" 2>&1 || status=$?
    if [[ $status -eq 0 ]]; then
      printf '\n\033[32m✔ refresh done — fresh jobs cached in beacon.db; reload the page to see them\033[0m\n'
    else
      printf '\n\033[33m⚠ refresh failed (exit %d) — still serving cached jobs; see %s\033[0m\n' \
        "$status" "${INGEST_LOG#"$ROOT/"}"
    fi
  ) &
  INGEST_PID=$!
fi

log "Starting frontend (Vite dev server) — Ctrl-C to stop everything"
cd "$FRONTEND" && npm run dev
