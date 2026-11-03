#!/usr/bin/env bash
# Batch 5: record extraction for the RAID 2024 baselines, BiLSTM, unsupervised baselines, Optuna tuning
# for LightGBM / RF / LR / CNN / BiLSTM. Two lanes run side by side (CPU lane, GPU lane). Resumable:
# steps with a .done marker in /data/tls-sok/logs are skipped, so after an interruption launch it again:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/batch5_$(date +%H%M).log bash scripts/launch_batch5.sh
# The steps that execute the RAID 2024 authors' code are in launch_batch5_r24.sh (run separately).
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.batch5.lock
flock -n 9 || { echo "$(date +%F' '%T) batch5 already running; exiting"; exit 1; }
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

cpu_lane() {
  step r24_records $PY scripts/r24_records.py raid_ms raid_tranco mta mcfp --jobs 24
  step tune_lgbm $PY scripts/tune.py --model lgbm --jobs 24
  step tune_rf $PY scripts/tune.py --model rf --jobs 24
  step tune_lr $PY scripts/tune.py --model lr --jobs 24
}
gpu_lane() {  # CNN/BiLSTM tuning: 6 no-timing settings x 600 s search each = 1 h per model, plus refits
  step bilstm_within $TPY scripts/run_deep.py within --arch bilstm --name deep_bilstm
  step bilstm_e4 $TPY scripts/run_deep.py e4 --arch bilstm --name e4_deep_bilstm
  step unsup $TPY scripts/run_unsup.py --jobs 8
  step tune_cnn $TPY scripts/tune.py --model cnn --timeout 600
  step tune_bilstm $TPY scripts/tune.py --model bilstm --timeout 600
}
cpu_lane &
gpu_lane &
wait
echo "$(date +%F' '%T) BATCH5_FINISHED"
