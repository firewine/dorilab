#!/usr/bin/env bash
set -euo pipefail

root=/workspace/dorilab/services/inference
mkdir -p "$root/run" "$root/logs"
pid_file="$root/run/server.pid"

if [[ -s "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null; then
  echo "inference service already running"
  exit 0
fi

python_bin=${DORILAB_RUNTIME_PYTHON:?set DORILAB_RUNTIME_PYTHON to the verified runtime python}
nohup "$python_bin" "$root/server.py" >>"$root/logs/server.log" 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" >"$pid_file"
chmod 0600 "$pid_file"
echo "started inference pid=$pid; readiness still requires authenticated /readyz"
