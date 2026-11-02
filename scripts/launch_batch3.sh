#!/usr/bin/env bash
# Batch 3 (E5a ablation, E9 fingerprint drift, E7 cost, Optuna tuning); resumable: steps with a .done
# marker in /data/tls-sok/logs are skipped, so after an interruption just launch it again with a new log:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch3_$(date +%H%M).log bash scripts/launch_batch3.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch3.lock
flock -n 9 || { echo "$(date +%F' '%T) batch3 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
mkdir -p $L
PY=".venv/bin/python"
TPY=/data/tls-sok/venv-torch/bin/python
step() {  # step NAME command...
  local name=$1; shift
  if [ -e "$L/$name.done" ]; then echo "$(date +%F' '%T) SKIP $name (done)"; return; fi
  echo "$(date +%F' '%T) START $name"
  "$@" > "$L/$name.log" 2>&1
  local rc=$?
  echo "$(date +%F' '%T) END $name (exit $rc)"
  [ $rc -eq 0 ] && touch "$L/$name.done"
}

# E7 first, while the box is otherwise idle, so timings are not disturbed by other jobs
step e7_prep $PY scripts/run_e7.py prep
step e7_prep_cnn $TPY scripts/run_e7.py prep_cnn
for m in xgb lgbm rf lr; do
  step e7_inf_${m}_server $PY scripts/run_e7.py infer --model $m --threads 16 --tag server
  step e7_inf_${m}_edge2 taskset -c 0,1 $PY scripts/run_e7.py infer --model $m --threads 2 --tag edge2
  step e7_inf_${m}_edge1 taskset -c 0 $PY scripts/run_e7.py infer --model $m --threads 1 --tag edge1
done
step e7_inf_xgb_gpu $PY scripts/run_e7.py infer --model xgb --threads 16 --device cuda --tag gpu
step e7_inf_cnn_gpu $TPY scripts/run_e7.py infer --model cnn --threads 16 --device cuda --tag gpu
step e7_inf_cnn_server $TPY scripts/run_e7.py infer --model cnn --threads 16 --tag server
step e7_inf_cnn_edge2 taskset -c 0,1 $TPY scripts/run_e7.py infer --model cnn --threads 2 --tag edge2
step e7_inf_cnn_edge1 taskset -c 0 $TPY scripts/run_e7.py infer --model cnn --threads 1 --tag edge1
step e7_ext_server $PY scripts/run_e7.py extract --threads 0 --tag server
step e7_ext_edge2 taskset -c 0,1 $PY scripts/run_e7.py extract --threads 2 --tag edge2
step e7_ext_edge1 taskset -c 0 $PY scripts/run_e7.py extract --threads 1 --tag edge1

ABL=only_g1,only_g2,only_g3,only_g4,only_g5,loo_g1,loo_g2,loo_g3,loo_g4,loo_g5
ABLN=only_g1_notime,only_g2_notime,only_g3_notime,only_g4_notime,only_g5_notime,loo_g1_notime,loo_g2_notime,loo_g3_notime,loo_g4_notime,loo_g5_notime
step e5a_mta $PY scripts/run_benchmark.py mta --sets $ABL --exps E2,E3 --name e5a_mta --jobs 32
step e5a_mcfp $PY scripts/run_benchmark.py mcfp --sets $ABL --exps E2 --name e5a_mcfp --jobs 32
step e5a_e4 $PY scripts/run_e4.py --pairs 'mcfp>mta' --sets $ABLN --out /data/tls-sok/benchmark/e5a_e4 --jobs 32
step e9 $PY scripts/run_e9.py --jobs 32
step tune $PY scripts/tune.py --jobs 32
echo "$(date +%F' '%T) BATCH3_FINISHED"
