#!/usr/bin/env bash
# MTA + MCFP preparation on A2: unpack MTA, extract features for both, build labelled tables.
# Start (detached):
#   cd ~/tls-sok && nohup setsid bash scripts/launch_mta_mcfp.sh > /data/tls-sok/out/mta_mcfp.log 2>&1 < /dev/null &
# Restart after any interruption with the same command: finished archives and pcaps are skipped.
set -uo pipefail
cd "$(dirname "$0")/.."
L=/data/tls-sok/out/lists
WORKERS=${WORKERS:-6}
mkdir -p "$L"
exec 9> /data/tls-sok/out/.mta_mcfp.lock
flock -n 9 || { echo "$(date +%F' '%T) another launcher is running; exiting"; exit 1; }
echo "$(date +%F' '%T) LAUNCH pid $$"

.venv/bin/python scripts/unpack_a2.py mta || { echo "unpack failed"; exit 1; }

find /data/tls-sok/raw/mcfp -name '*.pcap' | sort > "$L/mcfp.txt"
find /data/tls-sok/unpacked/mta -name '*.pcap' -o -name '*.pcapng' | sort > "$L/mta.txt"
wc -l "$L/mcfp.txt" "$L/mta.txt"

for ds in mta mcfp; do
  echo "$(date +%F' '%T) START extract $ds"
  .venv/bin/python scripts/run_extract.py "$ds" "$L/$ds.txt" --workers "$WORKERS"
  echo "$(date +%F' '%T) END extract $ds: $(tail -n 1 /data/tls-sok/out/$ds/progress.log)"
done
for ds in mta mcfp; do
  echo "$(date +%F' '%T) START table $ds"
  .venv/bin/python scripts/build_tables.py "$ds" --workers 12 > "/data/tls-sok/tables_$ds.log" 2>&1
  echo "$(date +%F' '%T) END table $ds (exit $?)"
done
echo "$(date +%F' '%T) ALL_FINISHED"
