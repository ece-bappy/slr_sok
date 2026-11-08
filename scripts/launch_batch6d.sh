#!/usr/bin/env bash
# Batch 6 item 10 (padding vs the ECH tier, with/without padding-augmented training) and the item-8 rerun with
# the corrected padding rule (data-carrying packets only, capped at 1,514 B). Starts after batch6c (7b).
# Resumable; the log ends with "BATCH batch6d DONE|FAILED <steps>":
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch6d_$(date +%H%M).log bash scripts/launch_batch6d.sh
set -uo pipefail
cd "$(dirname "$0")"
exec 9> /data/tls-sok/out/.batch6d.lock
flock -n 9 || { echo "$(date +%F' '%T) batch6d already running; exiting"; exit 1; }
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
until grep -qh " BATCH batch6c " /data/tls-sok/out/batch6c_*.log 2>/dev/null; do sleep 120; done
echo "$(date +%F' '%T) batch6c finished"
step b6_padech $PY run_b6.py padech --jobs 16
step b6_evasion_v2 $PY run_b6.py evasion --jobs 16
if [ -n "$FAILED" ]; then echo "$(date +%F' '%T) BATCH batch6d FAILED ${FAILED#,}"
else echo "$(date +%F' '%T) BATCH batch6d DONE"; fi
