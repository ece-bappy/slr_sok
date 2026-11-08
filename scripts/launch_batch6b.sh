#!/usr/bin/env bash
# Batch 6 follow-ups to item 3 (Main, 8 Nov): the 2026 per-post breakdown, rolling origin with the item-4
# encodings (3c), and rolling origin for LightGBM / RF (3b). Runs as a third lane next to launch_batch6.sh
# with fewer threads. Resumable; the log ends with "BATCH batch6b DONE" or "BATCH batch6b FAILED <steps>":
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch6b_$(date +%H%M).log bash scripts/launch_batch6b.sh
set -uo pipefail
cd "$(dirname "$0")"
exec 9> /data/tls-sok/out/.batch6b.lock
flock -n 9 || { echo "$(date +%F' '%T) batch6b already running; exiting"; exit 1; }
L=/data/tls-sok/logs
PY="../.venv/bin/python"
FAILED=""
step() {
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  if [ $rc -eq 0 ]; then touch "$L/$name.done"; else FAILED="$FAILED,$name"; fi
}
step b6_post2026 $PY run_b6.py post2026 --jobs 8
step b6_rolling_enc $PY run_b6.py rolling_enc --jobs 8
step b6_rolling_models $PY run_b6.py rolling_models --jobs 8
if [ -n "$FAILED" ]; then echo "$(date +%F' '%T) BATCH batch6b FAILED ${FAILED#,}"
else echo "$(date +%F' '%T) BATCH batch6b DONE"; fi
