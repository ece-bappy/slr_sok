#!/usr/bin/env bash
# RAID 2024 UCNet gaps: same unedited notebooks, same rebuilt UCNet inputs, same seeds and n_jobs; only the
# scikit-learn version changes, 1.9.1 (main venv) -> 1.3.2 (the paper's). User approval relayed by Main on 8 Nov
# 2026 ("Yes, run it"), including the PyPI download. Separate venv; the main venv is untouched; no root.
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/sk132_$(date +%H%M).log bash scripts/launch_sk132.sh
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9> /data/tls-sok/out/.sk132.lock
flock -n 9 || { echo "$(date +%F' '%T) sk132 already running; exiting"; exit 1; }
L=/data/tls-sok/logs
V=/data/tls-sok/venv-sk132
R=/data/tls-sok/benchmark/r24_repro_ucnet/sk132
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
fail() { echo "$(date +%F' '%T) BATCH sk132 FAILED $1"; exit 1; }
# wheels only (no source builds). Keep pandas/joblib/tqdm at the main venv's versions so that only scikit-learn
# (and the numpy/scipy it needs, numpy<2) changes; fall back to pandas 2.2.3 only if that cannot resolve.
venv() {
  [ -x "$V/bin/python" ] || python3 -m venv "$V" || return 1
  "$V/bin/pip" install -q --only-binary=:all: scikit-learn==1.3.2 numpy==1.26.4 scipy==1.11.4 pandas==3.1.0 \
      joblib==1.6.0 tqdm==4.70.1 \
    || "$V/bin/pip" install -q --only-binary=:all: scikit-learn==1.3.2 numpy==1.26.4 scipy==1.11.4 pandas==2.2.3 \
      joblib==1.6.0 tqdm==4.70.1 || return 1
  "$V/bin/pip" freeze > /data/tls-sok/logs/sk132_freeze.txt
  "$V/bin/python" -c "import sklearn, numpy, scipy, pandas; print(sklearn.__version__, numpy.__version__, scipy.__version__, pandas.__version__)"
}
step sk132_venv venv || fail sk132_venv
mkdir -p "$R"
step sk132_03 "$V/bin/python" scripts/r24_reproduce.py --only 03-C-CERT.ipynb --out "$R/03-C-CERT" || fail sk132_03
step sk132_04_grid "$V/bin/python" scripts/r24_reproduce.py --only 04-C-BEHAV.ipynb --grid --out "$R/04-C-BEHAV" \
  || fail sk132_04_grid
cp /data/tls-sok/logs/sk132_freeze.txt "$R/"
echo "$(date +%F' '%T) BATCH sk132 DONE"
