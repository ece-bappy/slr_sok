#!/usr/bin/env bash
# Deep model (1D-CNN on G2 sequences) on the A2 GPU; resumable by step markers. Detached:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/deep_$(date +%H%M).log bash scripts/launch_deep.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.deep.lock
flock -n 9 || { echo "$(date +%F' '%T) deep run already active; exiting"; exit 1; }
L=/data/tls-sok/logs
mkdir -p $L
PY=/data/tls-sok/venv-torch/bin/python
for part in within e4; do
  if [ -e "$L/deep_$part.done" ]; then echo "SKIP deep_$part"; continue; fi
  echo "$(date +%F' '%T) START deep_$part"
  $PY scripts/run_deep.py $part > "$L/deep_$part.log" 2>&1
  rc=$?
  echo "$(date +%F' '%T) END deep_$part (exit $rc)"
  [ $rc -eq 0 ] && touch "$L/deep_$part.done"
done
echo "$(date +%F' '%T) DEEP_FINISHED"
