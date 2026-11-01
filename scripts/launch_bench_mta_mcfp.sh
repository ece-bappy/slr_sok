#!/usr/bin/env bash
# Rebuild the MCFP table (year fix), then E1-E3 on MTA and MCFP. Detached:
#   cd ~/tls-sok && nohup setsid bash scripts/launch_bench_mta_mcfp.sh > /data/tls-sok/out/bench_mta_mcfp.log 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.bench_mta_mcfp.lock
flock -n 9 || { echo "$(date +%F' '%T) another launcher is running; exiting"; exit 1; }
echo "$(date +%F' '%T) LAUNCH pid $$"
.venv/bin/python scripts/build_tables.py mcfp --workers 12 > /data/tls-sok/tables_mcfp.log 2>&1 \
  || { echo "table mcfp failed"; exit 1; }
for ds in mta mcfp; do
  echo "$(date +%F' '%T) START bench $ds"
  .venv/bin/python scripts/run_benchmark.py "$ds" > "/data/tls-sok/bench_$ds.log" 2>&1
  echo "$(date +%F' '%T) END bench $ds (exit $?)"
done
echo "$(date +%F' '%T) ALL_FINISHED"
