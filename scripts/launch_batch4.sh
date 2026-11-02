#!/usr/bin/env bash
# Batch 4 (cross-family check of the fingerprint result; Zeek-free E7 option); resumable: steps with a
# .done marker in /data/tls-sok/logs are skipped, so after an interruption just launch it again:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch4_$(date +%H%M).log bash scripts/launch_batch4.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch4.lock
flock -n 9 || { echo "$(date +%F' '%T) batch4 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
B=/data/tls-sok/benchmark
mkdir -p $L
PY=".venv/bin/python"
step() {  # step NAME command...
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  [ $rc -eq 0 ] && touch "$L/$name.done"
}

# E7 Zeek-free option first, while the box is otherwise idle. The full pipeline is re-timed in the same
# warm-cache conditions (tags *_w) so the two pipelines are directly comparable.
step e7_prep_lite $PY scripts/run_e7.py prep --set g1g2g3
for m in xgb lgbm; do
  step e7_inf_${m}_server_lite $PY scripts/run_e7.py infer --model $m --threads 16 --tag server --set g1g2g3
  step e7_inf_${m}_edge1_lite taskset -c 0 $PY scripts/run_e7.py infer --model $m --threads 1 --tag edge1 --set g1g2g3
done
for t in server edge2 edge1; do
  case $t in server) TS=""; N=0;; edge2) TS="taskset -c 0,1"; N=2;; edge1) TS="taskset -c 0"; N=1;; esac
  step e7_ext_${t}_w $TS $PY scripts/run_e7.py extract --threads $N --tag ${t}_w
  step e7_ext_${t}_nozeek $TS $PY scripts/run_e7.py extract --threads $N --tag ${t} --no-zeek
done

# Cross-family check: all vs loo_g5 (= no fingerprints) vs g1g2g3 (Zeek-free) for every tabular model
for m in xgb lgbm rf lr; do
  step cf_mta_$m $PY scripts/run_benchmark.py mta --model $m --sets all,loo_g5,g1g2g3 --exps E3 --name cf_mta_$m --jobs 32
  step cf_e4_$m $PY scripts/run_e4.py --pairs 'mcfp>mta' --model $m --jobs 32 --out $B/cf_e4_$m \
    --sets all,loo_g5,g1g2g3,all_notime,loo_g5_notime,g1g2g3_notime
done
for m in lgbm rf lr; do
  step cf_e9_$m $PY scripts/run_e9.py --model $m --sets no_fp,fp_ja3,fp_ja4,fp_both --out $B/cf_e9_$m --jobs 32
done
echo "$(date +%F' '%T) BATCH4_FINISHED"
