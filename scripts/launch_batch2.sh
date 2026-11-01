#!/usr/bin/env bash
# Batch 2 on A2: MTA rerun (ipify fix), E4 rerun, E5b, E8, E6, model robustness. Detached:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch2.log bash scripts/launch_batch2.sh
# Each step writes its own log in /data/tls-sok/logs/; a failed step is reported and the batch continues.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch2.lock
flock -n 9 || { echo "$(date +%F' '%T) batch2 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
mkdir -p $L
PY=".venv/bin/python"
step() {  # step NAME command...
  local name=$1; shift
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  echo "$(date +%F' '%T) END $name (exit $?)"
}

step mta_e123 $PY scripts/run_benchmark.py mta
step e4 $PY scripts/run_e4.py

while ! grep -q "ALL_SHA1_FINISHED" /data/tls-sok/out/sha1.log; do sleep 30; done
step e5b_sslbl $PY scripts/e5b_audit.py sslbl
step e5b_origin $PY scripts/e5b_audit.py origin
step e5b_mta_sslbl $PY scripts/run_benchmark.py mta_sslbl --sets all,g1g2_notime
step e5b_mcfp_sslbl $PY scripts/run_benchmark.py mcfp_sslbl --sets all,g1g2_notime --exps E1,E2

TIERS=tier_tls12_full,tier_tls13,tier_tls13_ech
step e8_mta $PY scripts/run_benchmark.py mta --sets $TIERS --exps E2,E3 --name e8_mta
step e8_mcfp $PY scripts/run_benchmark.py mcfp --sets $TIERS --exps E2 --name e8_mcfp
step e8_raid $PY scripts/run_benchmark.py raid --sets $TIERS --exps E2 --name e8_raid

EARLY=early_3,early_5,early_10,early_20,early_3_notime,early_5_notime,early_10_notime,early_20_notime,all,all_notime
step e6_mta $PY scripts/run_benchmark.py mta --sets $EARLY --exps E2,E3 --name e6_mta
step e6_mcfp $PY scripts/run_benchmark.py mcfp --sets $EARLY --exps E2 --name e6_mcfp
step e5b_table $PY scripts/e5b_audit.py table

for m in lgbm lr rf; do
  step rob_mta_$m $PY scripts/run_benchmark.py mta --model $m --sets all,g1g2_notime --exps E2,E3 --jobs 32
  step rob_hikari_$m $PY scripts/run_benchmark.py hikari --model $m --sets g1g2_notime --exps E2,E3 --jobs 32
  step rob_mcfp_$m $PY scripts/run_benchmark.py mcfp --model $m --sets all,g1g2_notime --exps E2 --jobs 32
  step rob_e4_$m $PY scripts/run_e4.py --model $m --sets g1g2_notime --jobs 32
done
echo "$(date +%F' '%T) BATCH2_FINISHED"
