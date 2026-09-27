#!/usr/bin/env bash
set -Eeuo pipefail
# Bootstrap owns FD9. Close it BEFORE any long-lived child can inherit it.
exec 9>&-
cd /workspace/dorilab/inference
exec /root/venvs/dorilab-tournament/bin/python start_service.py "$@"
