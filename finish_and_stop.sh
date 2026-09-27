#!/usr/bin/env bash
set -u

RESULT_DIR="${1:-/workspace/dorilab/results/source_review_v13_qwen27}"
POD_ID="${RUNPOD_POD_ID:-}"

mkdir -p "$RESULT_DIR"

date -Iseconds > "$RESULT_DIR/stop_requested_at.txt"

if [ -z "$POD_ID" ]; then
    echo "AUTO_STOP_FAILED: RUNPOD_POD_ID empty" \
      | tee -a "$RESULT_DIR/COMPLETED.txt"
    exit 1
fi

if ! command -v runpodctl >/dev/null 2>&1; then
    echo "AUTO_STOP_FAILED: runpodctl missing" \
      | tee -a "$RESULT_DIR/COMPLETED.txt"
    exit 1
fi

echo "pod_id=$POD_ID" >> "$RESULT_DIR/COMPLETED.txt"

sync

echo "Stopping Pod: $POD_ID"

if runpodctl pod stop "$POD_ID"; then
    exit 0
fi

echo "New stop command failed; trying legacy self-stop" \
  >> "$RESULT_DIR/COMPLETED.txt"

sync

runpodctl stop pod "$POD_ID"
