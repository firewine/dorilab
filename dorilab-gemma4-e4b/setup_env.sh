#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo 'This recipe targets Windows WSL2 Linux x86_64 + NVIDIA GPU.' >&2; exit 1
fi
# Every interpreter/cache below is inside the new project, except HF model cache.
export UV_CACHE_DIR="$ROOT/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$ROOT/.python"
export PIP_DISABLE_PIP_VERSION_CHECK=1
unset PYTHONPATH BNB_CUDA_VERSION VIRTUAL_ENV CONDA_PREFIX
if [[ -f "$ROOT/.environment_ready" ]]; then
  "$ROOT/.venv/bin/python" -m pip check
  echo 'Existing isolated environment kept; no automatic upgrade.'
  exit 0
fi
if [[ ! -x "$ROOT/.bootstrap/bin/python" ]]; then
  python3 -m venv "$ROOT/.bootstrap"
fi
"$ROOT/.bootstrap/bin/python" -m pip install 'uv>=0.8,<1'
"$ROOT/.bootstrap/bin/uv" python install 3.12
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$ROOT/.bootstrap/bin/uv" venv --python 3.12 --seed "$ROOT/.venv"
fi
P="$ROOT/.venv/bin/python"
"$P" - <<'PY'
import sys
from pathlib import Path
assert sys.version_info[:2] == (3,12),sys.version
assert Path(sys.prefix).resolve() == Path('.venv').resolve()
PY
"$P" -m pip install 'torch==2.10.0' 'torchvision==0.25.0' --index-url https://download.pytorch.org/whl/cu128
"$P" -m pip install -r requirements.txt -c constraints-torch.txt
"$P" -m pip check
mkdir -p reports
"$P" -m pip freeze > reports/requirements_resolved.txt
"$P" - <<'PY'
import torch,transformers,peft,bitsandbytes
from transformers import Gemma4ForConditionalGeneration, AutoProcessor
assert torch.version.cuda.startswith('12.8'),torch.version.cuda
print('Library imports PASS; real NF4/Gemma tests run during preflight/train.')
PY
printf 'Created only this project .venv; GPU training untested until run.\n' > .environment_ready
