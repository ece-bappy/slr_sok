#!/usr/bin/env bash
# Leaf-cert SHA-1 pass for the SSLBL audit. Detached:
#   cd ~/tls-sok && nohup setsid bash scripts/launch_sha1.sh > /data/tls-sok/out/sha1.log 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.sha1.lock
flock -n 9 || { echo "$(date +%F' '%T) another SHA-1 pass is running; exiting"; exit 1; }
for ds in mta mcfp; do
  echo "$(date +%F' '%T) START $ds"
  .venv/bin/python scripts/zeek_sha1.py "$ds" --workers 12
done
echo "$(date +%F' '%T) ALL_SHA1_FINISHED"
