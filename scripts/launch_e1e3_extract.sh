#!/usr/bin/env bash
# E1-E3 feature extraction on A2: unpack, list pcaps, run the resumable driver per dataset.
# Start (detached, survives the user's PC going down):
#   cd ~/tls-sok && nohup setsid bash scripts/launch_e1e3_extract.sh > /data/tls-sok/out/e1e3.log 2>&1 < /dev/null &
# Restart after any interruption: run the same command. Finished archives and pcaps are skipped.
# Progress: tail /data/tls-sok/out/e1e3.log /data/tls-sok/out/*/progress.log
set -uo pipefail
cd "$(dirname "$0")/.."
R=/data/tls-sok/raw
U=/data/tls-sok/unpacked
L=/data/tls-sok/out/lists
WORKERS=${WORKERS:-6}
mkdir -p "$L"

bash scripts/unpack_a2.sh all || { echo "unpack failed"; exit 1; }

find "$U/raid_tranco" -name '*.pcap' | sort > "$L/raid_tranco.txt"
find "$U/raid_ms" -name '*.pcap' -o -name '*.pcapng' | sort > "$L/raid_ms.txt"
# HIKARI attack pcaps in place; raw/hikari/benign is an earlier test copy, so it is left out
find "$R/hikari" -name '*.pcap' -not -path "$R/hikari/benign/*" | sort > "$L/hikari_attack.txt"
find "$U/hikari_benign" -name '*.pcap' | sort > "$L/hikari_benign.txt"
wc -l "$L"/*.txt

for ds in raid_ms hikari_benign hikari_attack raid_tranco; do
  echo "$(date +%F' '%T) START $ds"
  .venv/bin/python scripts/run_extract.py "$ds" "$L/$ds.txt" --workers "$WORKERS"
  echo "$(date +%F' '%T) END $ds: $(tail -n 1 /data/tls-sok/out/$ds/progress.log)"
done
echo "$(date +%F' '%T) ALL_FINISHED"
