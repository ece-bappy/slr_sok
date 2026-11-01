#!/usr/bin/env bash
# Rebuild training tables on A2. Detached:
#   cd ~/tls-sok && nohup setsid bash scripts/launch_tables.sh mta mcfp raid > /data/tls-sok/out/tables.log 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.tables.lock
flock -n 9 || { echo "$(date +%F' '%T) another table build is running; exiting"; exit 1; }
for ds in "$@"; do
  echo "$(date +%F' '%T) START table $ds"
  .venv/bin/python scripts/build_tables.py "$ds" --workers 12 > "/data/tls-sok/tables_$ds.log" 2>&1
  echo "$(date +%F' '%T) END table $ds (exit $?)"
done
echo "$(date +%F' '%T) TABLES_FINISHED"
