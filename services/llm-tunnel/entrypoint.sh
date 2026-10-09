#!/usr/bin/env bash
set -euo pipefail

host=${RUNPOD_HOST:-}
port=${RUNPOD_SSH_PORT:-}
user=${DORILAB_SSH_USER:-root}
remote_port=${DORILAB_REMOTE_INFERENCE_PORT:-8080}

if [[ ! "$host" =~ ^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])$ ]] || [[ "$host" == -* ]]; then
  echo "invalid RUNPOD_HOST" >&2
  exit 64
fi
if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
  echo "invalid RUNPOD_SSH_PORT" >&2
  exit 64
fi
if [[ ! "$remote_port" =~ ^[0-9]+$ ]] || (( remote_port < 1 || remote_port > 65535 )); then
  echo "invalid remote inference port" >&2
  exit 64
fi
if [[ ! "$user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "invalid SSH user" >&2
  exit 64
fi

args=(
  -N -T
  -L "0.0.0.0:18080:127.0.0.1:${remote_port}"
  -p "$port"
  -o BatchMode=yes
  -o ExitOnForwardFailure=yes
  -o ServerAliveInterval=60
  -o ServerAliveCountMax=5
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile=/run/ssh/known_hosts
  -o ForwardAgent=no
)

if [[ ${DORILAB_SSH_USE_AGENT:-0} == 1 ]]; then
  args+=(-o IdentitiesOnly=no)
else
  args+=(-o IdentitiesOnly=yes -i /run/ssh/id_ed25519)
fi

exec ssh "${args[@]}" -- "${user}@${host}"
