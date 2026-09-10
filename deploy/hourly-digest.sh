#!/usr/bin/env bash
# hourly-digest.sh — one scheduled fire of the Beacon pipeline (deploy/com.beacon.digest.plist).
#
#   poll the sources → dedup → send the Telegram digest → exit
#
# This is the whole notification path: `python -m beacon.ingest` ends in send_digest(), the
# same tail run.sh dispatches at launch and on close. No API, no Vite — the UI contributes
# nothing to a digest, so a fire binds no ports and leaves nothing behind to kill.
#
# Two guards, because a full poll takes ~30-45 min against a 60 min gap between fires:
#   lock      a fire that finds the previous one still polling logs and skips (exit 0)
#   watchdog  a run is capped at BEACON_HOURLY_TIMEOUT (default 50 min); on a kill the
#             digest still goes out via `python -m beacon.notify`, which reports whatever
#             the truncated poll had already committed
#
# Env: BEACON_UV (uv path), BEACON_HOURLY_TIMEOUT (seconds), BEACON_HOURLY_LOCK (lock dir).
# Paths are absolute because launchd runs this with no login shell and no PATH worth trusting.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${BEACON_UV:-/opt/homebrew/bin/uv}"
LOCK="${BEACON_HOURLY_LOCK:-/tmp/beacon.hourly.lock}"
TIMEOUT="${BEACON_HOURLY_TIMEOUT:-3000}"   # 50 min, leaving 10 min of slack before the next fire
GRACE=10                                   # seconds between TERM and KILL
POLL_INTERVAL=5                            # watchdog tick

log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }

# `uv run` wraps the python process, so a TERM has to reach both: the wrapper forwards
# signals, but the descendant sweep makes that independent of uv's behaviour.
stop_child() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null || return 0
  pkill -TERM -P "$pid" 2>/dev/null || true
  kill -TERM "$pid" 2>/dev/null || true
  local _
  for _ in $(seq 1 "$GRACE"); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 1
  done
  pkill -KILL -P "$pid" 2>/dev/null || true
  kill -KILL "$pid" 2>/dev/null || true
}

# --- single instance --------------------------------------------------------
# mkdir is the atomic test-and-set; the PID inside tells a live holder from a stale lock
# left by a crash (or a reboot mid-poll).
if ! mkdir "$LOCK" 2>/dev/null; then
  holder="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [[ -n "$holder" ]] && kill -0 "$holder" 2>/dev/null; then
    log "hourly_skipped reason=locked pid=$holder"
    exit 0
  fi
  log "hourly_lock_stale pid=${holder:-unknown}"
  rm -rf "$LOCK"
  mkdir "$LOCK" 2>/dev/null || { log "hourly_skipped reason=lock_race"; exit 0; }
fi
echo $$ >"$LOCK/pid"

CHILD=""
cleanup() {
  if [[ -n "$CHILD" ]]; then
    stop_child "$CHILD"
  fi
  rm -rf "$LOCK" || true
}
trap cleanup EXIT INT TERM

# --- the poll ---------------------------------------------------------------
started=$SECONDS
log "hourly_start timeout=${TIMEOUT}s root=$ROOT"

"$UV" run --project "$ROOT/backend" python -m beacon.ingest &
CHILD=$!

killed=0
elapsed=0
while kill -0 "$CHILD" 2>/dev/null; do
  if (( elapsed >= TIMEOUT )); then
    killed=1
    log "hourly_timeout secs=$elapsed pid=$CHILD"
    stop_child "$CHILD"
    break
  fi
  sleep "$POLL_INTERVAL"
  elapsed=$(( elapsed + POLL_INTERVAL ))
done

status=0
wait "$CHILD" || status=$?
CHILD=""

# --- digest, even when the poll was cut short -------------------------------
# Upserts are committed per source, so the truncated run still has matches worth reporting.
# Costs a few reads and — only when something matched — one Telegram POST.
if (( killed == 1 )); then
  log "hourly_digest_fallback reason=timeout"
  "$UV" run --project "$ROOT/backend" python -m beacon.notify || log "hourly_digest_fallback_failed"
fi

log "hourly_done exit=$status secs=$(( SECONDS - started )) killed=$killed"
exit "$status"
