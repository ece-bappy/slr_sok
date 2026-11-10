#!/usr/bin/env bash
# CIRA-CIC-DoHBrw-2020 feature extraction on A2 (flows, G1-G5, record sequences via tlssok.extract).
# Pcaps are untrusted data: parsed only, never executed. Labels are built later from the dataset's own split
# (capture folder / tool name in the file name), never from certificates, SSLBL or JA3/JA4.
# Start (detached):
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/dohbrw_extract_$(date +%H%M%S).log bash scripts/launch_dohbrw.sh
# Rerun the same command to resume: finished pcaps are skipped. Log ends "BATCH dohbrw_extract DONE|FAILED".
set -uo pipefail
cd "$(dirname "$0")/.."
X=/data/tls-sok/raw/dohbrw/x
L=/data/tls-sok/out/lists
mkdir -p "$L"
exec 9> /data/tls-sok/out/.dohbrw_extract.lock
flock -n 9 || { echo "$(date +%F' '%T) another launcher is running; exiting"; exit 1; }
echo "$(date +%F' '%T) LAUNCH pid $$"

find "$X" -path '*BenignDoH_NonDoH-*' -name '*.pcap' | sort > "$L/dohbrw_benign.txt"
find "$X" -path '*MaliciousDoH-*' -name '*.pcap' | sort > "$L/dohbrw_malicious.txt"
wc -l "$L/dohbrw_benign.txt" "$L/dohbrw_malicious.txt"

status=DONE
# benign: 7 captures of 1-3 GB each, so few workers (memory); malicious: 1,800 small captures
for spec in dohbrw_benign:${WORKERS_BIG:-3} dohbrw_malicious:${WORKERS:-12}; do
  ds=${spec%%:*} w=${spec##*:}
  echo "$(date +%F' '%T) START $ds ($w workers)"
  .venv/bin/python scripts/run_extract.py "$ds" "$L/$ds.txt" --workers "$w" || status=FAILED
  last=$(tail -n 1 /data/tls-sok/out/$ds/progress.log)
  echo "$(date +%F' '%T) END $ds: $last"
  echo "$last" | grep -q "failed 0;" || status=FAILED
done
echo "$(date +%F' '%T) BATCH dohbrw_extract $status"
