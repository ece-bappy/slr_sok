#!/usr/bin/env bash
# UCNet part of the RAID 2024 reproduction (user approval 4 Nov 2026: download the anonymised UCNet table
# linked from the RAID 2024 README, osf.io/x6yjg, and run the notebooks' UCNet cells). Waits for the
# download, verifies OSF's MD5 and SHA-256, rebuilds data/ucnet/, then reruns the notebooks (recorded
# parameters, then with grid searches). Resumable:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/ucnet_$(date +%H%M).log bash scripts/launch_ucnet.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.ucnet.lock
flock -n 9 || { echo "$(date +%F' '%T) ucnet already running; exiting"; exit 1; }
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
while ! grep -q QUEUE_FINISHED /data/tls-sok/dl/ucnet.log; do sleep 60; done
verify() { cd /data/tls-sok/raw && md5sum -c /data/tls-sok/dl/ucnet.md5 && sha256sum -c /data/tls-sok/dl/ucnet.sha256; }
step ucnet_verify verify || { echo "checksum mismatch: stopping"; exit 1; }
step ucnet_prep $PY scripts/r24_ucnet_prep.py --jobs 24 || exit 1
step r24_repro_ucnet $PY scripts/r24_reproduce.py
step r24_repro_grid_ucnet $PY scripts/r24_reproduce.py --grid
echo "$(date +%F' '%T) UCNET_FINISHED"
