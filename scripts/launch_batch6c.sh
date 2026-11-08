#!/usr/bin/env bash
# Batch 6 follow-ups 9 (TLS 1.3 diagnostic) and 7b (leave-one-family-out for LightGBM / RF), Main 8 Nov.
# Starts when batch 6 lane B frees (b6_evasion ends). Resumable; the log ends with "BATCH batch6c DONE|FAILED":
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch6c_$(date +%H%M).log bash scripts/launch_batch6c.sh
set -uo pipefail
cd "$(dirname "$0")"
exec 9> /data/tls-sok/out/.batch6c.lock
flock -n 9 || { echo "$(date +%F' '%T) batch6c already running; exiting"; exit 1; }
L=/data/tls-sok/logs
PY="../.venv/bin/python"
FAILED=""
step() {
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  if [ $rc -eq 0 ]; then touch "$L/$name.done"; else FAILED="$FAILED,$name"; fi
}
until grep -qh -e "END b6_evasion" -e " BATCH batch6 " /data/tls-sok/out/batch6_*.log 2>/dev/null; do sleep 120; done
echo "$(date +%F' '%T) lane B free"
step b6_tls13 $PY run_b6.py tls13 --jobs 16
step b6_family_models $PY run_b6.py family_models --jobs 16
if [ -n "$FAILED" ]; then echo "$(date +%F' '%T) BATCH batch6c FAILED ${FAILED#,}"
else echo "$(date +%F' '%T) BATCH batch6c DONE"; fi
