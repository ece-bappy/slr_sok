#!/usr/bin/env bash
# Batch 5, RAID 2024 part: steps that execute the authors' released code (notebooks + tls_paper_funcs.py from
# github.com/CarlosANovo/extending12to13). Waits for launch_batch5.sh's r24_records step. Resumable:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch5r24_$(date +%H%M).log bash scripts/launch_batch5_r24.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch5r24.lock
flock -n 9 || { echo "$(date +%F' '%T) batch5_r24 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
PY=".venv/bin/python"
step() {
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  [ $rc -eq 0 ] && touch "$L/$name.done"
}
step r24_repro $PY scripts/r24_reproduce.py
while [ ! -e "$L/r24_records.done" ]; do sleep 60; done
step r24_protocol $PY scripts/r24_benchmark.py --jobs 16
step r24_repro_grid $PY scripts/r24_reproduce.py --grid
echo "$(date +%F' '%T) BATCH5_R24_FINISHED"
