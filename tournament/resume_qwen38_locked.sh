#!/usr/bin/env bash
set -uo pipefail
source /workspace/dorilab/env.sh
source /root/venvs/dorilab-tournament/bin/activate
python /workspace/dorilab/tournament/resume_qwen38_locked.py 2>&1 | tee /workspace/dorilab/tournament/qwen38_retry_download_20260923.log
result=${PIPESTATUS[0]}
printf 'RETRY_EXIT_CODE=%s\n' "$result" | tee -a /workspace/dorilab/tournament/qwen38_retry_download_20260923.log
exit "$result"
