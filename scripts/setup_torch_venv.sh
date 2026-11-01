#!/usr/bin/env bash
# PyTorch venv on /data for the deep model (no root, nothing written outside /data/tls-sok). Detached:
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/torch_setup.log bash scripts/setup_torch_venv.sh
set -euo pipefail
export PIP_CACHE_DIR=/data/tls-sok/pipcache TMPDIR=/data/tls-sok/tmp
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"
V=/data/tls-sok/venv-torch
[ -x $V/bin/python ] || python3 -m venv $V
$V/bin/pip install -q --upgrade pip
$V/bin/pip install -q torch numpy pandas pyarrow scikit-learn
$V/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
du -sh $V
echo TORCH_SETUP_FINISHED
