#!/usr/bin/env bash
# E4 cross-dataset run on A2. Detached:
#   cd ~/tls-sok && nohup setsid bash scripts/launch_e4.sh > /data/tls-sok/bench_e4.log 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.e4.lock
flock -n 9 || { echo "$(date +%F' '%T) another E4 run is active; exiting"; exit 1; }
echo "$(date +%F' '%T) LAUNCH pid $$"
.venv/bin/python scripts/run_e4.py
echo "$(date +%F' '%T) E4_EXIT $?"
