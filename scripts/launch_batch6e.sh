#!/usr/bin/env bash
# Batch 6 items 11 (leave-one-dataset-out, pooled-source training + origin probe) and 12 (host-level alerting
# on MTA E3), Main 8 Nov. Resumable; the log ends with "BATCH batch6e DONE|FAILED <steps>":
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch6e_$(date +%H%M).log bash scripts/launch_batch6e.sh
set -uo pipefail
cd "$(dirname "$0")"
exec 9> /data/tls-sok/out/.batch6e.lock
flock -n 9 || { echo "$(date +%F' '%T) batch6e already running; exiting"; exit 1; }
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
step b6_hosts $PY run_b6.py hosts --jobs 16
step b6_lodo $PY run_b6.py lodo --jobs 16
if [ -n "$FAILED" ]; then echo "$(date +%F' '%T) BATCH batch6e FAILED ${FAILED#,}"
else echo "$(date +%F' '%T) BATCH batch6e DONE"; fi
