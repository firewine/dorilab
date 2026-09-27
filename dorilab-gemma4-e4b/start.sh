#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
unset PYTHONPATH BNB_CUDA_VERSION VIRTUAL_ENV CONDA_PREFIX
export PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false
export HF_HUB_DISABLE_TELEMETRY=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
bash "$ROOT/setup_env.sh"
exec "$ROOT/.venv/bin/python" "$ROOT/run_gemma.py" all "$@"
