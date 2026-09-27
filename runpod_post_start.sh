#!/usr/bin/env bash

LOG=/workspace/dorilab/runpod_bootstrap.log

(
    echo "=================================================="
    echo "[POST_START] $(date -Iseconds)"

    /workspace/dorilab/bootstrap_runpod.sh

    echo "[POST_START] bootstrap finished"
) >> "$LOG" 2>&1 &

exit 0