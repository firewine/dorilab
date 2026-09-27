#!/usr/bin/env bash
# Persistent RunPod start wrapper. Configure the Pod Start Command to:
# /bin/bash /workspace/dorilab/runpod_start.sh
# Recreates the pre-start hook on every fresh container, then preserves
# the image's SSH/Jupyter/nginx initialization in /start.sh.
set -Eeuo pipefail
ROOT=/workspace/dorilab
HOOK=/pre_start.sh
TARGET="$ROOT/runpod_post_start.sh"

for file in "$TARGET" "$ROOT/bootstrap_runpod.sh" "$ROOT/inference/start_inference.sh" /start.sh; do
    if [[ ! -f "$file" ]]; then
        echo "DoriLab startup error: required script missing: $file" >&2
        exit 1
    fi
done

# Do not replace an unrelated image/user hook without review.
if [[ -e "$HOOK" || -L "$HOOK" ]]; then
    if [[ ! -L "$HOOK" || "$(readlink "$HOOK")" != "$TARGET" ]]; then
        echo "DoriLab startup error: unrelated /pre_start.sh exists; left unchanged" >&2
        exit 1
    fi
fi

if [[ "${1:-}" == "--check" ]]; then
    echo 'DoriLab start wrapper checks passed; no process started or files changed'
    exit 0
fi
if [[ "$#" != 0 ]]; then
    echo 'Usage: runpod_start.sh [--check]' >&2
    exit 2
fi

ln -sfn -- "$TARGET" "$HOOK"
chmod +x "$TARGET" "$ROOT/bootstrap_runpod.sh" "$ROOT/inference/start_inference.sh"
exec /start.sh
