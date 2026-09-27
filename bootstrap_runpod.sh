#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# ============================================================
# DoriLab RunPod Bootstrap
#
# Persistent:
#   /workspace/dorilab
#     - project
#     - runtime locks
#     - RC3 LoRA adapter
#     - experiment results
#
# Ephemeral:
#   /root
#     - Python venv
#     - npm/Codex binary
#     - Qwen3.8-27B base model
#     - HF/pip/npm caches
#
# Qwen base is intentionally NOT persisted to /workspace.
# ============================================================


# ------------------------------------------------------------
# Fixed paths
# ------------------------------------------------------------

ROOT="/workspace/dorilab"

VENV="/root/venvs/dorilab-tournament"
PYTHON="$VENV/bin/python"

CODEX_PREFIX="/root/npm-global"

STATUS="$ROOT/.bootstrap.status"
LOGROOT="$ROOT/logs"
LOCK_FILE="$ROOT/.bootstrap.lock"

TRANSFORMERS_LOCK="$ROOT/runtime/transformers_qwen27.lock.txt"


# ------------------------------------------------------------
# Fixed Qwen deployment
# ------------------------------------------------------------

MODEL_ID="Qwen/Qwen3.8-27B"
MODEL_REVISION="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"

MODEL_ROOT="/root/models"
MODEL_RUNTIME="$MODEL_ROOT/qwen38-27b"

MODEL_READY_MARKER="$MODEL_RUNTIME/.dorilab_model_ready"


# ------------------------------------------------------------
# Fixed RC3 adapter
# ------------------------------------------------------------

ADAPTER_DIR="$ROOT/models/qwen38-27b/current/adapter"

EXPECTED_ADAPTER_SHA="d90dee59f00f7c987c1b61ae334f928464bfb412ddb26110d692b92b9a46a689"


# ------------------------------------------------------------
# Optional inference service
#
# Later create:
#   /workspace/dorilab/inference/start_inference.sh
#
# It should start the inference server and return.
# Expected internal endpoint:
#   http://127.0.0.1:8080/health
# ------------------------------------------------------------

INFERENCE_START_SCRIPT="$ROOT/inference/start_inference.sh"
INFERENCE_HEALTH_URL="${DORILAB_INFERENCE_HEALTH_URL:-http://127.0.0.1:8080/health}"

# 0:
#   inference server not yet installed -> finish at MODEL_READY
#
# 1:
#   inference server is mandatory -> missing service is an error
DORILAB_REQUIRE_INFERENCE="${DORILAB_REQUIRE_INFERENCE:-0}"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

now() {
    date -Iseconds
}

log() {
    echo "[$(now)] $*"
}

set_status() {
    local phase="$1"
    shift || true

    if [ "$#" -gt 0 ]; then
        echo "$phase $(now) $*" > "$STATUS"
    else
        echo "$phase $(now)" > "$STATUS"
    fi

    log "STATUS=$phase $*"
}


# ------------------------------------------------------------
# Persistent + local directories
# ------------------------------------------------------------

mkdir -p \
    "$ROOT" \
    "$LOGROOT" \
    "$ROOT/runtime" \
    "$ROOT/codex-home" \
    /root/codex-home \
    /root/venvs \
    /root/npm-global \
    /root/npm-cache \
    /root/pip-cache \
    /root/hf-cache \
    /root/tmp \
    "$MODEL_ROOT"


# ------------------------------------------------------------
# Prevent duplicate bootstrap
# ------------------------------------------------------------

exec 9>"$LOCK_FILE"

if command -v flock >/dev/null 2>&1; then

    if ! flock -n 9; then
        log "Another bootstrap process is already running."
        exit 0
    fi

else
    log "WARNING: flock is not installed; duplicate-run protection unavailable."
fi


# ------------------------------------------------------------
# Error handling
# ------------------------------------------------------------

fail_handler() {
    local rc=$?
    local line="${BASH_LINENO[0]:-unknown}"

    echo "FAILED $(now) rc=$rc line=$line" > "$STATUS"

    log "BOOTSTRAP FAILED rc=$rc line=$line"

    exit "$rc"
}

trap fail_handler ERR


set_status "RUNNING"


# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------

CODEX_PERSIST="$ROOT/codex-home"
CODEX_RUNTIME="/root/codex-home"

export CODEX_HOME="$CODEX_RUNTIME"

# Persistent Codex settings -> secure local runtime
mkdir -p "$CODEX_PERSIST" "$CODEX_RUNTIME"

chown root:root "$CODEX_RUNTIME"
chmod 700 "$CODEX_RUNTIME"

if [ -f "$CODEX_PERSIST/config.toml" ]; then
    cp "$CODEX_PERSIST/config.toml" \
       "$CODEX_RUNTIME/config.toml"
fi

if [ -f "$CODEX_PERSIST/auth.json" ]; then
    cp "$CODEX_PERSIST/auth.json" \
       "$CODEX_RUNTIME/auth.json"
fi

chmod 600 "$CODEX_RUNTIME/config.toml" 2>/dev/null || true
chmod 600 "$CODEX_RUNTIME/auth.json" 2>/dev/null || true

export PATH="$CODEX_PREFIX/bin:$PATH"

export npm_config_prefix="$CODEX_PREFIX"
export npm_config_cache="/root/npm-cache"

export HF_HOME="/root/hf-cache"
export HF_HUB_CACHE="/root/hf-cache/hub"

export PIP_CACHE_DIR="/root/pip-cache"
export TMPDIR="/root/tmp"

export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false

# Model runtime variables for later inference server
export DORILAB_BASE_MODEL_ID="$MODEL_ID"
export DORILAB_BASE_REVISION="$MODEL_REVISION"
export DORILAB_BASE_RUNTIME="$MODEL_RUNTIME"

export DORILAB_ADAPTER_DIR="$ADAPTER_DIR"
export DORILAB_ADAPTER_SHA256="$EXPECTED_ADAPTER_SHA"


log "=================================================="
log "DoriLab bootstrap started"
log "ROOT=$ROOT"


# ------------------------------------------------------------
# GPU inventory
# ------------------------------------------------------------

if ! command -v nvidia-smi >/dev/null 2>&1; then
    log "ERROR: nvidia-smi not found"
    exit 1
fi

log "GPU inventory:"

nvidia-smi \
    --query-gpu=name,memory.total,driver_version \
    --format=csv


# ------------------------------------------------------------
# Base system dependencies
# ------------------------------------------------------------

NEED_APT=0

command -v git >/dev/null 2>&1 || NEED_APT=1
command -v node >/dev/null 2>&1 || NEED_APT=1
command -v npm >/dev/null 2>&1 || NEED_APT=1
command -v bwrap >/dev/null 2>&1 || NEED_APT=1

if [ "$NEED_APT" -eq 1 ]; then

    log "Installing required OS packages"

    apt-get update

    DEBIAN_FRONTEND=noninteractive \
        apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        nodejs \
        npm \
        bubblewrap

    rm -rf /var/lib/apt/lists/*
fi

log "node: $(node --version)"
log "npm : $(npm --version)"
log "git : $(git --version)"


# ============================================================
# Codex
# ============================================================

CODEX_BIN="$CODEX_PREFIX/bin/codex"
CODEX_LOCK="$ROOT/codex.package-version.txt"

if [ ! -x "$CODEX_BIN" ]; then

    if [ -s "$CODEX_LOCK" ]; then

        CODEX_VERSION="$(tr -d '[:space:]' < "$CODEX_LOCK")"

        log "Installing locked Codex version: $CODEX_VERSION"

        npm install -g "@openai/codex@$CODEX_VERSION"

    else

        log "No Codex version lock found."
        log "Installing Codex latest once and creating persistent lock."

        npm install -g @openai/codex@latest

        node -p \
            "require('$CODEX_PREFIX/lib/node_modules/@openai/codex/package.json').version" \
            > "$CODEX_LOCK"

    fi
fi

log "codex: $("$CODEX_BIN" --version)"


# ============================================================
# Python runtime creation
# ============================================================

create_python_runtime() {

    log "Creating DoriLab Python runtime"

    rm -rf "$VENV"

    python3 -m venv \
        --system-site-packages \
        "$VENV"

    "$PYTHON" -m pip install -U \
        pip \
        setuptools \
        wheel


    # --------------------------------------------------------
    # Check torch provided by RunPod image
    # --------------------------------------------------------

    if ! "$PYTHON" - <<'PY'
import torch

assert torch.__version__ == "2.8.0+cu128", torch.__version__
assert torch.version.cuda == "12.8", torch.version.cuda

print("System torch runtime acceptable:", torch.__version__)
PY
    then

        log "Exact torch runtime not available from system packages."
        log "Installing torch 2.8.0 CUDA 12.8 into venv."

        "$PYTHON" -m pip install \
            --index-url https://download.pytorch.org/whl/cu128 \
            "torch==2.8.0" \
            "torchvision==0.23.0"
    fi


    # --------------------------------------------------------
    # Fixed Python dependencies
    # --------------------------------------------------------

    log "Installing fixed DoriLab Python dependencies"

    "$PYTHON" -m pip install \
        accelerate==1.15.0 \
        peft==0.21.0 \
        datasets==5.0.1 \
        huggingface_hub==1.32.0 \
        mistral-common==1.12.0 \
        safetensors \
        sentencepiece \
        jsonschema \
        psutil \
        rich


    # --------------------------------------------------------
    # Exact Transformers Git commit
    # --------------------------------------------------------

    if [ ! -s "$TRANSFORMERS_LOCK" ]; then
        log "ERROR: Transformers lock missing:"
        log "$TRANSFORMERS_LOCK"
        return 1
    fi

    log "Installing Transformers from persistent lock:"
    cat "$TRANSFORMERS_LOCK"

    TMPDIR="/root/tmp" \
    PIP_CACHE_DIR="/root/pip-cache" \
        "$PYTHON" -m pip install \
        -r "$TRANSFORMERS_LOCK"
}


# ------------------------------------------------------------
# Create runtime if missing
# ------------------------------------------------------------

if [ ! -x "$PYTHON" ]; then
    create_python_runtime
fi


# ============================================================
# Python runtime validation
# ============================================================

validate_python_runtime() {

    "$PYTHON" -m pip check

    "$PYTHON" - <<'PY'
import json
from pathlib import Path
import importlib.metadata as md

import torch
import transformers
import accelerate
import peft
import datasets
import huggingface_hub


EXPECTED_TRANSFORMERS_SHA = \
    "002e1edf5b5198488297f401dd853056b6521d02"


print("python:", __import__("sys").executable)

print("torch:", torch.__version__)
print("cuda runtime:", torch.version.cuda)

print("transformers:", transformers.__version__)
print("transformers path:", transformers.__file__)

print("accelerate:", accelerate.__version__)
print("peft:", peft.__version__)
print("datasets:", datasets.__version__)
print("huggingface_hub:", huggingface_hub.__version__)


assert torch.__version__ == "2.8.0+cu128", \
    f"Unexpected torch: {torch.__version__}"

assert torch.version.cuda == "12.8", \
    f"Unexpected CUDA runtime: {torch.version.cuda}"

assert transformers.__version__ == "5.18.0.dev0", \
    f"Unexpected Transformers: {transformers.__version__}"

assert "/root/venvs/dorilab-tournament/" in transformers.__file__, \
    f"Transformers imported outside DoriLab venv: {transformers.__file__}"

assert accelerate.__version__ == "1.15.0"
assert peft.__version__ == "0.21.0"
assert datasets.__version__ == "5.0.1"
assert huggingface_hub.__version__ == "1.32.0"

assert torch.cuda.is_available(), \
    "CUDA is not available"


dist = md.distribution("transformers")

direct = Path(dist._path) / "direct_url.json"

assert direct.exists(), \
    "transformers direct_url.json missing"

data = json.loads(direct.read_text())

sha = data.get("vcs_info", {}).get("commit_id")

assert sha == EXPECTED_TRANSFORMERS_SHA, \
    f"Transformers SHA mismatch: {sha}"


print("transformers commit:", sha)
print("gpu:", torch.cuda.get_device_name(0))
print("capability:", torch.cuda.get_device_capability(0))
PY
}


# ------------------------------------------------------------
# Validate; rebuild once automatically if venv drifted
# ------------------------------------------------------------

if ! validate_python_runtime; then

    log "Existing Python runtime failed validation."
    log "Rebuilding ephemeral venv once."

    create_python_runtime

    validate_python_runtime
fi


set_status "RUNTIME_READY"


# ============================================================
# Write deployment environment
# ============================================================

DEPLOY_ENV="$ROOT/runtime/qwen27_rc3_deployment.env"

cat > "$DEPLOY_ENV" <<EOF_DEPLOY
export DORILAB_BASE_MODEL_ID="$MODEL_ID"
export DORILAB_BASE_REVISION="$MODEL_REVISION"
export DORILAB_BASE_RUNTIME="$MODEL_RUNTIME"

export DORILAB_ADAPTER_DIR="$ADAPTER_DIR"
export DORILAB_ADAPTER_SHA256="$EXPECTED_ADAPTER_SHA"

export HF_HOME="/root/hf-cache"
export HF_HUB_CACHE="/root/hf-cache/hub"

export TOKENIZERS_PARALLELISM=false
EOF_DEPLOY

chmod 644 "$DEPLOY_ENV"

log "Deployment environment written:"
log "$DEPLOY_ENV"


# ============================================================
# Qwen3.8-27B local model validation
# ============================================================

validate_qwen_model() {

    MODEL_RUNTIME="$MODEL_RUNTIME" \
        "$PYTHON" - <<'PY'

import json
import os
from pathlib import Path

from transformers import AutoConfig, AutoProcessor


root = Path(os.environ["MODEL_RUNTIME"])

required = [
    root / "config.json",
    root / "model.safetensors.index.json",
    root / "tokenizer_config.json",
]

for path in required:
    if not path.is_file():
        raise RuntimeError(f"Missing required model file: {path}")


index_path = root / "model.safetensors.index.json"

index = json.loads(index_path.read_text())

weight_map = index.get("weight_map", {})

if not weight_map:
    raise RuntimeError("Empty model weight_map")


shards = sorted(set(weight_map.values()))

missing = [
    str(root / shard)
    for shard in shards
    if not (root / shard).is_file()
]

if missing:
    raise RuntimeError(
        "Missing model shards:\n" +
        "\n".join(missing[:20])
    )


total_bytes = sum(
    (root / shard).stat().st_size
    for shard in shards
)

print("model shards:", len(shards))
print("model shard bytes:", total_bytes)


# Expected historical snapshot was ~55.6 GB.
# Do not require exact byte count here, because metadata files are separate,
# but reject clearly incomplete downloads.
if total_bytes < 50_000_000_000:
    raise RuntimeError(
        f"Model weight size appears incomplete: {total_bytes}"
    )


config = AutoConfig.from_pretrained(
    root,
    local_files_only=True,
    trust_remote_code=False,
)

print("config type:", type(config).__name__)


processor = AutoProcessor.from_pretrained(
    root,
    local_files_only=True,
    trust_remote_code=False,
)

print("processor type:", type(processor).__name__)

print("Qwen local snapshot validation: PASS")
PY
}


# ============================================================
# Qwen3.8-27B download to ephemeral disk
# ============================================================

MODEL_NEEDS_DOWNLOAD=0

if [ ! -f "$MODEL_READY_MARKER" ]; then
    MODEL_NEEDS_DOWNLOAD=1
else

    # Marker exists; still verify files.
    if ! validate_qwen_model; then
        log "Qwen ready marker exists but snapshot validation failed."
        rm -f "$MODEL_READY_MARKER"
        MODEL_NEEDS_DOWNLOAD=1
    fi
fi


if [ "$MODEL_NEEDS_DOWNLOAD" -eq 1 ]; then

    set_status "MODEL_DOWNLOADING"

    log "Qwen3.8-27B runtime snapshot missing or incomplete."
    log "Downloading exact revision to ephemeral disk."
    log "Model:    $MODEL_ID"
    log "Revision: $MODEL_REVISION"
    log "Path:     $MODEL_RUNTIME"


    mkdir -p "$MODEL_RUNTIME"


    # Report available disk.
    log "Available /root disk before model download:"

    df -h /root || true


    MODEL_ID="$MODEL_ID" \
    MODEL_REVISION="$MODEL_REVISION" \
    MODEL_RUNTIME="$MODEL_RUNTIME" \
        "$PYTHON" - <<'PY'

from huggingface_hub import snapshot_download
import os


repo_id = os.environ["MODEL_ID"]
revision = os.environ["MODEL_REVISION"]
local_dir = os.environ["MODEL_RUNTIME"]


print("Downloading:")
print(" repo_id =", repo_id)
print(" revision =", revision)
print(" local_dir =", local_dir)


path = snapshot_download(
    repo_id=repo_id,
    revision=revision,
    local_dir=local_dir,
)


print("Qwen base model download complete")
print("resolved path:", path)
PY


    # Full validation after download.
    validate_qwen_model


    {
        echo "model_id=$MODEL_ID"
        echo "revision=$MODEL_REVISION"
        echo "validated_at=$(now)"
    } > "$MODEL_READY_MARKER"


    log "Qwen model ready marker written:"
    log "$MODEL_READY_MARKER"

else

    log "Existing ephemeral Qwen snapshot is valid."
    log "Skipping model download."
fi


# ============================================================
# RC3 adapter validation
# ============================================================

set_status "ADAPTER_CHECK"


if [ ! -d "$ADAPTER_DIR" ]; then
    log "ERROR: RC3 adapter directory missing:"
    log "$ADAPTER_DIR"
    exit 1
fi


if [ ! -f "$ADAPTER_DIR/adapter_config.json" ]; then
    log "ERROR: adapter_config.json missing"
    exit 1
fi


if [ ! -f "$ADAPTER_DIR/adapter_model.safetensors" ]; then
    log "ERROR: adapter_model.safetensors missing"
    exit 1
fi


ACTUAL_ADAPTER_SHA="$(
    sha256sum \
        "$ADAPTER_DIR/adapter_model.safetensors" \
        | awk '{print $1}'
)"


log "RC3 adapter SHA256:"
log "expected=$EXPECTED_ADAPTER_SHA"
log "actual  =$ACTUAL_ADAPTER_SHA"


if [ "$ACTUAL_ADAPTER_SHA" != "$EXPECTED_ADAPTER_SHA" ]; then

    log "ERROR: RC3 adapter SHA mismatch"

    exit 1
fi


ADAPTER_DIR="$ADAPTER_DIR" \
    "$PYTHON" - <<'PY'

import json
import os
from pathlib import Path


root = Path(os.environ["ADAPTER_DIR"])

config_path = root / "adapter_config.json"

data = json.loads(config_path.read_text())

print("adapter config:")
print(" peft_type:", data.get("peft_type"))
print(" r:", data.get("r"))
print(" lora_alpha:", data.get("lora_alpha"))
print(" lora_dropout:", data.get("lora_dropout"))
print(" base_model_name_or_path:", data.get("base_model_name_or_path"))

print("RC3 adapter metadata read: PASS")
PY


log "RC3 adapter validation: PASS"


# ============================================================
# MODEL READY
# ============================================================

set_status "MODEL_READY"

log "=================================================="
log "DoriLab model runtime prepared"
log "Base model:"
log "  $MODEL_RUNTIME"
log "Adapter:"
log "  $ADAPTER_DIR"
log "=================================================="


# ============================================================
# Optional inference service
# ============================================================

if [ -f "$INFERENCE_START_SCRIPT" ]; then

    set_status "SERVICE_STARTING"

    log "Inference start script found:"
    log "$INFERENCE_START_SCRIPT"

    chmod +x "$INFERENCE_START_SCRIPT"

    # The start script is expected to launch the server in background
    # and then return.
    bash "$INFERENCE_START_SCRIPT"


    log "Waiting for inference health endpoint:"
    log "$INFERENCE_HEALTH_URL"


    HEALTH_OK=0

    for _ in $(seq 1 180); do

        if HEALTH_URL="$INFERENCE_HEALTH_URL" \
            "$PYTHON" - <<'PY' >/dev/null 2>&1
import os
import urllib.request

url = os.environ["HEALTH_URL"]

with urllib.request.urlopen(
    url,
    timeout=2,
) as response:
    if 200 <= response.status < 300:
        raise SystemExit(0)

raise SystemExit(1)
PY
        then
            HEALTH_OK=1
            break
        fi

        sleep 2
    done


    if [ "$HEALTH_OK" -ne 1 ]; then
        log "ERROR: inference service health check timed out"
        exit 1
    fi


    set_status "READY"

    log "Inference API is READY."
    log "Health: $INFERENCE_HEALTH_URL"

else

    if [ "$DORILAB_REQUIRE_INFERENCE" = "1" ]; then

        log "ERROR: inference server is required but start script is missing:"
        log "$INFERENCE_START_SCRIPT"

        exit 1
    fi


    # Current development stage:
    # runtime + base + RC3 are ready,
    # but inference API has not yet been implemented.
    set_status "MODEL_READY" "service_not_configured"

    log "Inference start script not installed yet."
    log "Runtime, Qwen base, and RC3 adapter are ready."
fi


log "BOOTSTRAP COMPLETE $(now)"
