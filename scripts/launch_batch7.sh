#!/usr/bin/env bash
# Batch 7: Wang, Fok & Thing (C&S 2022) protocol on our data -- pooled random stratified 5-fold CV vs grouped
# 5-fold CV on the same pool (run_b7.py). No downloads; reads /data/tls-sok/tables only. Resumable:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch7_$(date +%H%M).log bash scripts/launch_batch7.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch7.lock
flock -n 9 || { echo "$(date +%F' '%T) batch7 already running; exiting"; exit 1; }
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
  return $rc
}
fail() { echo "$(date +%F' '%T) BATCH b7 FAILED $1"; exit 1; }
step b7_wang $PY scripts/run_b7.py --seeds 5 --jobs 24 || fail b7_wang
echo "$(date +%F' '%T) BATCH b7 DONE"
