#!/usr/bin/env bash
# Batch 6 (robustness items 1-8 for the headline results; run_b6.py). Two CPU lanes run side by side, each in
# priority order; resumable via .done markers in /data/tls-sok/logs. Relaunch after an interruption with:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch6_$(date +%H%M).log bash scripts/launch_batch6.sh
set -uo pipefail
cd "$(dirname "$0")"
exec 9> /data/tls-sok/out/.batch6.lock
flock -n 9 || { echo "$(date +%F' '%T) batch6 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
PY="../.venv/bin/python"
step() {
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  if [ $rc -eq 0 ]; then touch "$L/$name.done"; else echo "$name" >> "$FAILED"; fi
}
FAILED=/data/tls-sok/out/.batch6.failed   # lanes are subshells, so failures are collected in a file
rm -f "$FAILED"
lane_a() {
  step b6_seeds $PY run_b6.py seeds --jobs 16          # item 2 (saves predictions for item 1)
  step b6_baserate $PY run_b6.py baserate --jobs 16    # item 1
  step b6_training $PY run_b6.py training --jobs 16    # item 6
}
lane_b() {
  step b6_rolling $PY run_b6.py rolling --jobs 16      # item 3
  step b6_encoding $PY run_b6.py encoding --jobs 16    # item 4
  step b6_ech $PY run_b6.py ech --jobs 16              # item 5
  step b6_family $PY run_b6.py family --jobs 16        # item 7
  step b6_evasion $PY run_b6.py evasion --jobs 16      # item 8
}
lane_a &
lane_b &
wait
if [ -s "$FAILED" ]; then echo "$(date +%F' '%T) BATCH batch6 FAILED $(paste -sd, "$FAILED")"
else echo "$(date +%F' '%T) BATCH batch6 DONE"; fi
