#!/usr/bin/env bash
set -euo pipefail

project_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$project_root"

env_file="$project_root/.env"
derived_file="$project_root/.env.derived"
secrets_dir="$project_root/.secrets"
connection_file="$project_root/var/connection/runpod.env"
last_mode_file="$secrets_dir/last_mode"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*"; }

env_value() {
  local key=$1 file=${2:-$env_file}
  [[ -f "$file" ]] || return 0
  awk -v key="$key" 'index($0,key "=")==1 {print substr($0,length(key)+2); exit}' "$file"
}

live_value() {
  local key=$1 value
  value=$(env_value "$key" "$connection_file")
  if [[ -n "$value" ]]; then printf '%s\n' "$value"; else env_value "$key" "$env_file"; fi
}

valid_host() {
  local value=$1
  [[ "$value" =~ ^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])$ ]] && [[ "$value" != -* ]]
}

valid_port() {
  local value=$1
  [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 ))
}

absolute_path() {
  local value=$1 directory base
  if [[ "$value" == "~/"* ]]; then value="$HOME/${value#~/}"; fi
  directory=$(dirname -- "$value")
  base=$(basename -- "$value")
  [[ -d "$directory" ]] || return 1
  printf '%s/%s\n' "$(CDPATH= cd -- "$directory" && pwd -P)" "$base"
}

generate_secret() {
  local path=$1 bytes=$2
  if [[ -e "$path" ]]; then
    [[ -f "$path" && ! -L "$path" ]] || die "refusing non-regular secret path: $path"
    chmod 600 "$path"
    return
  fi
  command -v openssl >/dev/null 2>&1 || die "openssl is required to create local random secrets"
  umask 077
  openssl rand -hex "$bytes" >"$path"
  chmod 600 "$path"
}

prepare_local() {
  [[ -f "$env_file" ]] || cp .env.example "$env_file"
  mkdir -p "$secrets_dir" var/artifacts var/run-records var/exports var/connection
  chmod 700 "$secrets_dir" var/artifacts var/run-records var/exports var/connection
  generate_secret "$secrets_dir/db_password" 32
  generate_secret "$secrets_dir/app_session_key" 48
  generate_secret "$secrets_dir/inference_token" 32
  if [[ ! -e "$secrets_dir/known_hosts" ]]; then
    umask 077
    : >"$secrets_dir/known_hosts"
  fi
  [[ -f "$secrets_dir/known_hosts" && ! -L "$secrets_dir/known_hosts" ]] || die "invalid known_hosts path"
  chmod 600 "$secrets_dir/known_hosts"

  local key_input key_path known_path current_user current_key current_port current_remote_port current_profile current_agent
  current_user=$(env_value DORILAB_SSH_USER "$derived_file")
  current_key=$(env_value DORILAB_SSH_KEY_PATH "$derived_file")
  current_port=$(env_value DORILAB_APP_PORT "$derived_file")
  current_remote_port=$(env_value DORILAB_REMOTE_INFERENCE_PORT "$derived_file")
  current_profile=$(env_value DORILAB_MODEL_PROFILE "$derived_file")
  current_agent=$(env_value DORILAB_SSH_USE_AGENT "$derived_file")
  key_input=${DORILAB_SSH_KEY_PATH:-${current_key:-$HOME/.ssh/id_ed25519}}
  key_path=$(absolute_path "$key_input") || key_path="$key_input"
  known_path=$(absolute_path "$secrets_dir/known_hosts")
  umask 077
  {
    printf 'DORILAB_SSH_USER=%s\n' "${DORILAB_SSH_USER:-${current_user:-root}}"
    printf 'DORILAB_SSH_KEY_PATH=%s\n' "$key_path"
    printf 'DORILAB_KNOWN_HOSTS_PATH=%s\n' "$known_path"
    printf 'DORILAB_APP_PORT=%s\n' "${DORILAB_APP_PORT:-${current_port:-8000}}"
    printf 'DORILAB_REMOTE_INFERENCE_PORT=%s\n' "${DORILAB_REMOTE_INFERENCE_PORT:-${current_remote_port:-8080}}"
    printf 'DORILAB_MODEL_PROFILE=%s\n' "${DORILAB_MODEL_PROFILE:-${current_profile:-dorilab-source-review-v15-rc3}}"
    printf 'DORILAB_SSH_USE_AGENT=%s\n' "${DORILAB_SSH_USE_AGENT:-${current_agent:-0}}"
  } >"$derived_file"
  chmod 600 "$derived_file"
}

docker_ready() {
  command -v docker >/dev/null 2>&1 || die "Docker CLI is not installed"
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is unavailable"
  docker info >/dev/null 2>&1
}

docker_is_local_mac() {
  local operating_system
  operating_system=$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || true)
  [[ "$operating_system" == *"Docker Desktop"* ]]
}

load_live_values() {
  RUNPOD_HOST_VALUE=$(live_value RUNPOD_HOST)
  RUNPOD_SSH_PORT_VALUE=$(live_value RUNPOD_SSH_PORT)
  valid_host "$RUNPOD_HOST_VALUE" || die "RunPod HostName is empty or invalid; save it in the app connection settings"
  valid_port "$RUNPOD_SSH_PORT_VALUE" || die "RunPod SSH port must be 1..65535; save it in the app connection settings"
  [[ -f "$derived_file" ]] || die "run ./scripts/dev.sh setup first"
  SSH_USER_VALUE=$(env_value DORILAB_SSH_USER "$derived_file")
  SSH_KEY_VALUE=$(env_value DORILAB_SSH_KEY_PATH "$derived_file")
  KNOWN_HOSTS_VALUE=$(env_value DORILAB_KNOWN_HOSTS_PATH "$derived_file")
  SSH_AGENT_MODE=$(env_value DORILAB_SSH_USE_AGENT "$derived_file")
  [[ "$SSH_USER_VALUE" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "invalid DORILAB_SSH_USER"
  if [[ "$SSH_AGENT_MODE" == 1 ]]; then
    ssh-add -L >/dev/null 2>&1 || die "agent mode is selected but no unlocked SSH identity is loaded"
  else
    [[ -f "$SSH_KEY_VALUE" ]] || die "SSH key not found: $SSH_KEY_VALUE"
  fi
  [[ -f "$KNOWN_HOSTS_VALUE" ]] || die "known_hosts file not found; run setup"
}

ssh_args() {
  SSH_ARGS=(
    -p "$RUNPOD_SSH_PORT_VALUE"
    -o BatchMode=yes
    -o StrictHostKeyChecking=yes
    -o UserKnownHostsFile="$KNOWN_HOSTS_VALUE"
    -o ForwardAgent=no
    -o ConnectTimeout=10
    -o ServerAliveInterval=60
    -o ServerAliveCountMax=5
  )
  if [[ "$SSH_AGENT_MODE" == 1 ]]; then
    SSH_ARGS+=(-o IdentitiesOnly=no)
  else
    SSH_ARGS+=(-o IdentitiesOnly=yes -i "$SSH_KEY_VALUE")
  fi
}

host_key_setup() {
  load_live_values
  local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE" temp answer
  if ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1; then
    note "Host key: verified entry already exists for $lookup"
  else
    temp=$(mktemp "${TMPDIR:-/tmp}/dorilab-known-host.XXXXXX")
    if ! ssh-keyscan -T 10 -p "$RUNPOD_SSH_PORT_VALUE" "$RUNPOD_HOST_VALUE" >"$temp" 2>/dev/null; then
      rm -f -- "$temp"
      note "SSH_UNREACHABLE: could not scan $lookup; local setup is complete."
      return 0
    fi
    note "HOST_KEY_CONFIRMATION_REQUIRED for $lookup"
    ssh-keygen -lf "$temp"
    note "Compare this fingerprint with a separately authenticated RunPod console."
    if [[ ! -t 0 ]]; then
      rm -f -- "$temp"
      note "Run setup interactively to approve this host key. ssh-keyscan output was not trusted."
      return 0
    fi
    read -r -p "Fingerprint verified in RunPod console; trust this host key? [yes/no] " answer
    if [[ "$answer" != yes ]]; then
      rm -f -- "$temp"
      note "Host key not stored."
      return 0
    fi
    cat "$temp" >>"$KNOWN_HOSTS_VALUE"
    rm -f -- "$temp"
    chmod 600 "$KNOWN_HOSTS_VALUE"
    note "Stored the explicitly confirmed host key."
  fi

  ssh_args
  if ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" true; then
    note "SSH authentication: READY"
  else
    note "SSH_AUTH_FAILED: unlock the existing key in ssh-agent or verify the selected key/account."
  fi
}

compose_args() {
  COMPOSE=(docker compose --env-file "$env_file" --env-file "$derived_file" -f compose.yaml)
  if [[ -f "$connection_file" ]]; then COMPOSE=(docker compose --env-file "$env_file" --env-file "$derived_file" --env-file "$connection_file" -f compose.yaml); fi
  local mode=${1:-}
  if [[ "$mode" == demo ]]; then
    COMPOSE+=(-f compose.demo.yaml)
  else
    COMPOSE+=(-f compose.live.yaml)
  fi
  if [[ $(env_value DORILAB_SSH_USE_AGENT "$derived_file") == 1 ]]; then
    COMPOSE+=(-f compose.ssh-agent.yaml)
  else
    COMPOSE+=(-f compose.ssh-key.yaml)
  fi
}

start_local_controller() {
  [[ -f "$project_root/scripts/local-connection.sh" ]] || return 0
  mkdir -p "$project_root/var/connection/control"
  chmod 700 "$project_root/var/connection/control"
  local controller_pid=""
  [[ -f "$secrets_dir/local-connection.pid" ]] && controller_pid=$(<"$secrets_dir/local-connection.pid")
  if [[ "$controller_pid" =~ ^[0-9]+$ ]] && kill -0 "$controller_pid" 2>/dev/null && \
     [[ $(ps -p "$controller_pid" -o args=) == *"$project_root/scripts/local-connection.sh watch"* ]]; then
    return 0
  fi
  if [[ $(uname -s) == Darwin ]] && command -v launchctl >/dev/null 2>&1; then
    local label log
    label=$(local_controller_label)
    log="$project_root/var/run-records/local-connection-controller.log"
    # launchd owns the process lifetime; closing a terminal/Codex command must
    # not silently remove the UI's connection capability. No global install.
    launchctl remove "$label" >/dev/null 2>&1 || true
    local launch_args=(/usr/bin/env "PATH=$PATH")
    if [[ $(env_value DORILAB_SSH_USE_AGENT "$derived_file") == 1 ]]; then
      launch_args+=("SSH_AUTH_SOCK=${SSH_AUTH_SOCK:-}")
    fi
    launch_args+=(/bin/bash "$project_root/scripts/local-connection.sh" watch)
    launchctl submit -l "$label" -o "$log" -e "$log" -- "${launch_args[@]}"
  else
    nohup bash "$project_root/scripts/local-connection.sh" watch \
      </dev/null >>"$project_root/var/run-records/local-connection-controller.log" 2>&1 &
    controller_pid=$!
    umask 077
    printf '%s\n' "$controller_pid" >"$secrets_dir/local-connection.pid"
    chmod 600 "$secrets_dir/local-connection.pid"
  fi
  note "Local connection controller: started (settings can apply LIVE without another shell command)."
}

local_controller_label() {
  local digest
  digest=$(printf '%s' "$project_root" | openssl dgst -sha256 | awk '{print substr($NF,1,16)}')
  printf 'org.dorilab.local-connection.%s\n' "$digest"
}

stop_local_controller() {
  if [[ $(uname -s) == Darwin ]] && command -v launchctl >/dev/null 2>&1; then
    launchctl remove "$(local_controller_label)" >/dev/null 2>&1 || true
  fi
  local controller_pid=""
  [[ -f "$secrets_dir/local-connection.pid" ]] && controller_pid=$(<"$secrets_dir/local-connection.pid")
  if [[ "$controller_pid" =~ ^[0-9]+$ ]] && kill -0 "$controller_pid" 2>/dev/null && \
     [[ $(ps -p "$controller_pid" -o args=) == *"$project_root/scripts/local-connection.sh watch"* ]]; then
    kill "$controller_pid"
    for _ in {1..5}; do
      kill -0 "$controller_pid" 2>/dev/null || break
      sleep 1
    done
  fi
  rm -f -- "$secrets_dir/local-connection.pid" "$project_root/var/connection/control/heartbeat.env"
}

cmd_setup() {
  prepare_local
  note "Local directories and non-overwriting secrets are prepared."
  if docker_ready; then
    note "Docker: READY ($(docker context show), $(docker compose version --short))"
    if docker_is_local_mac; then
      note "Docker target: local Mac Docker Desktop confirmed"
    else
      note "Docker target: REVIEW_REQUIRED; current context does not identify Docker Desktop and was not changed"
    fi
  else
    note "Docker daemon is not reachable. Start Docker Desktop once, then rerun up/test. The current context was not changed."
  fi
  if [[ $(env_value DORILAB_SSH_USE_AGENT "$derived_file") == 1 ]]; then
    if ssh-add -L >/dev/null 2>&1; then note "SSH credential: unlocked local agent identity available"; else note "SSH credential: agent selected but no unlocked identity is loaded"; fi
  else
    local configured_key
    configured_key=$(env_value DORILAB_SSH_KEY_PATH "$derived_file")
    if [[ -f "$configured_key" ]]; then note "SSH credential: selected key file exists"; else note "SSH credential: selected key file is missing ($configured_key)"; fi
  fi
  local host port
  host=$(live_value RUNPOD_HOST); port=$(live_value RUNPOD_SSH_PORT)
  if [[ -z "$host" || -z "$port" ]]; then
    note "LIVE_PENDING: save HostName and SSH port in the app's RunPod connection settings. DEMO mode is already usable."
    return 0
  fi
  host_key_setup
}

port_conflict() {
  local mode=${1:-} port
  port=$(env_value DORILAB_APP_PORT "$derived_file"); port=${port:-8000}
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    compose_args "$mode"
    if ! "${COMPOSE[@]}" ps --status running api 2>/dev/null | grep -q api; then
      die "127.0.0.1:$port is already in use. No process was stopped; use DORILAB_APP_PORT as an advanced override before setup."
    fi
  fi
}

cmd_up() {
  local mode=live
  [[ ${1:-} == --demo ]] && mode=demo
  prepare_local
  docker_ready || die "Docker Desktop daemon is not reachable"
  docker_is_local_mac || die "current Docker context is not confirmed as local Docker Desktop; context was not changed"
  port_conflict "$mode"
  compose_args "$mode"
  if [[ "$mode" == demo ]]; then
    printf 'demo\n' >"$last_mode_file"
    "${COMPOSE[@]}" up --build -d db migrate api worker
  else
    load_live_values
    local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE"
    ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1 || die "HOST_KEY_CONFIRMATION_REQUIRED: run setup interactively"
    printf 'live\n' >"$last_mode_file"
    "${COMPOSE[@]}" --profile live up --build -d db migrate api llm-tunnel
    # A recreated Pod may have a new service token. Read the existing token over
    # verified SSH; this never creates/rotates a remote credential or blocks the app.
    if ! (cmd_sync_runpod_token --during-up); then
      note "Inference credential sync unavailable; the existing local credential was preserved. Local app startup continues."
    fi
    "${COMPOSE[@]}" --profile live up --build -d --force-recreate worker
  fi
  local app_port ready=0
  app_port=$(env_value DORILAB_APP_PORT "$derived_file"); app_port=${app_port:-8000}
  for _ in {1..30}; do
    if curl -fsS --max-time 2 "http://127.0.0.1:$app_port/healthz" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "$ready" == 1 ]] || note "API health did not become ready within 30 seconds; inspect ./scripts/dev.sh logs"
  start_local_controller
  cmd_status
  note "Browser: http://localhost:$app_port"
}

cmd_status() {
  prepare_local
  if ! docker_ready; then
    note "Compose/DB/API: Docker daemon unavailable"
    return 0
  fi
  local mode=demo app_port logs
  [[ -f "$last_mode_file" ]] && mode=$(<"$last_mode_file")
  compose_args "$mode"
  note "Compose:"
  "${COMPOSE[@]}" ps 2>/dev/null || true
  app_port=$(env_value DORILAB_APP_PORT "$derived_file"); app_port=${app_port:-8000}
  if curl -fsS --max-time 3 "http://127.0.0.1:$app_port/healthz" >/dev/null 2>&1; then note "API: READY"; else note "API: LOCAL_ONLY/UNAVAILABLE"; fi
  if "${COMPOSE[@]}" exec -T db pg_isready -U dorilab -d dorilab >/dev/null 2>&1; then note "DB: READY"; else note "DB: UNAVAILABLE"; fi
  if [[ "$mode" == demo ]]; then
    note "SSH tunnel: LOCAL_ONLY"
    note "Remote API/model: LOCAL_ONLY (explicit DEMO mode)"
  else
    if "${COMPOSE[@]}" exec -T llm-tunnel nc -z 127.0.0.1 18080 >/dev/null 2>&1; then
      note "SSH tunnel: CONNECTED (forward listener only; model readiness is checked separately)"
    else
      logs=$("${COMPOSE[@]}" --profile live logs --tail=20 llm-tunnel 2>/dev/null || true)
      if grep -qi 'permission denied' <<<"$logs"; then note "SSH tunnel: SSH_AUTH_FAILED"
      elif grep -qi 'host key verification failed' <<<"$logs"; then note "SSH tunnel: HOST_KEY_CONFIRMATION_REQUIRED"
      else note "SSH tunnel: SSH_UNREACHABLE"; fi
    fi
    "${COMPOSE[@]}" exec -T worker python -m dorilab.remote_status 2>/dev/null || note '{"state":"SERVICE_NOT_DEPLOYED"}'
  fi
}

cmd_logs() {
  local mode=demo
  [[ -f "$last_mode_file" ]] && mode=$(<"$last_mode_file")
  compose_args "$mode"
  "${COMPOSE[@]}" --profile live logs --tail=200 api worker llm-tunnel
}

cmd_test() {
  prepare_local
  docker_ready || die "Docker Desktop daemon is not reachable"
  docker_is_local_mac || die "current Docker context is not confirmed as local Docker Desktop; context was not changed"
  set +e
  docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
  local code=$?
  docker compose -f compose.test.yaml down --remove-orphans
  set -e
  return "$code"
}

cmd_down() {
  prepare_local
  local mode=demo
  [[ -f "$last_mode_file" ]] && mode=$(<"$last_mode_file")
  compose_args "$mode"
  local pending_id result_id result_phase
  pending_id=$(env_value REQUEST_ID "$project_root/var/connection/control/request.env")
  result_id=$(env_value REQUEST_ID "$project_root/var/connection/control/status.env")
  result_phase=$(env_value PHASE "$project_root/var/connection/control/status.env")
  if [[ -n "$pending_id" ]] && { [[ "$pending_id" != "$result_id" ]] || \
     [[ "$result_phase" != APPLIED && "$result_phase" != FAILED ]]; }; then
    die "connection apply is in progress; wait for its result before down"
  fi
  stop_local_controller
  "${COMPOSE[@]}" --profile live down --remove-orphans
  note "Stopped only this Compose project and its SSH tunnel. Named DB volume, artifacts, run records, exports, and secrets were preserved."
  note "The remote inference process and RunPod were not stopped; this command does not stop RunPod billing."
}

cmd_deploy_runpod() {
  prepare_local
  load_live_values
  local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE"
  ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1 || die "HOST_KEY_CONFIRMATION_REQUIRED: run setup interactively"
  ssh_args
  note "Read-only RunPod inspection: $SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$RUNPOD_SSH_PORT_VALUE"
  local inspection remote_token_hash local_token_hash
  inspection=$(ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" sh -s <scripts/remote/inspect.sh)
  printf '%s\n' "$inspection" | sed '/^service_token_sha256=/d'
  remote_token_hash=$(awk -F= '$1=="service_token_sha256"{print $2; exit}' <<<"$inspection")
  if [[ -n "$remote_token_hash" ]]; then
    local_token_hash=$(openssl dgst -sha256 "$secrets_dir/inference_token" | awk '{print $NF}')
    if [[ "$remote_token_hash" != "$local_token_hash" ]]; then
      note "LIVE_PENDING: an existing inference service uses a different credential."
      note "Provide the approved existing service token locally; the script did not expose or rotate it."
      return 2
    fi
  fi
  if grep -q '^DORILAB_INSTALLED_SERVICE=READY$' <<<"$inspection"; then
    note "An authenticated inference service is already prepared; no install, restart, or model reload was performed."
    note "Run ./scripts/dev.sh up and verify the exact model receipt with ./scripts/dev.sh status."
    return 0
  fi

  local release_dir=${DORILAB_REMOTE_RELEASE_DIR:-}
  if [[ -z "$release_dir" ]]; then
    note "LIVE_PENDING: set DORILAB_REMOTE_RELEASE_DIR to the one approved RC3 release locator reported by inspection."
    note "No remote files or processes were changed. Training and model download were not started."
    return 2
  fi
  [[ "$release_dir" =~ ^/workspace/dorilab/[A-Za-z0-9._/-]+$ ]] || die "release locator must be an absolute path under /workspace/dorilab"

  note "Deployment plan:"
  note "  target: $SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$RUNPOD_SSH_PORT_VALUE"
  note "  release locator: $release_dir"
  note "  write a new wrapper only under /workspace/dorilab/services/inference"
  note "  install no packages; download no weights; stop no process; change no Pod setting"
  note "  place the local service token only if no inference wrapper is installed"
  [[ -t 0 ]] || die "deploy-runpod requires an interactive confirmation"
  local answer stamp stage
  read -r -p "Proceed with this exact plan? [deploy/no] " answer
  [[ "$answer" == deploy ]] || { note "Deployment cancelled; no changes made."; return 0; }

  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  stage="/workspace/dorilab/services/.inference-stage-$stamp"
  ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" mkdir -p -- "$stage"
  SCP_ARGS=(-q -P "$RUNPOD_SSH_PORT_VALUE" -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS_VALUE")
  if [[ "$SSH_AGENT_MODE" != 1 ]]; then SCP_ARGS+=(-o IdentitiesOnly=yes -i "$SSH_KEY_VALUE"); fi
  scp "${SCP_ARGS[@]}" services/inference/server.py services/inference/run.sh services/inference/README.md \
    packages/contracts/model_profiles/rc3.json "$secrets_dir/inference_token" "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$stage/"
  ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" sh -s -- "$stage" "$release_dir" <scripts/remote/install.sh
  note "Wrapper deployment finished. READY still requires authenticated /readyz and exact receipt checks."
}

cmd_sync_runpod_token() {
  prepare_local
  load_live_values
  local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE"
  ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1 || \
    die "HOST_KEY_CONFIRMATION_REQUIRED: confirm the fingerprint in the app connection settings"
  ssh_args

  local temp byte_count line_count
  umask 077
  temp=$(mktemp "$secrets_dir/.inference_token.XXXXXX")
  chmod 600 "$temp"
  if ! ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" \
      'test -f /root/.config/dorilab/inference.token && test -r /root/.config/dorilab/inference.token && cat /root/.config/dorilab/inference.token' \
      >"$temp"; then
    rm -f -- "$temp"
    die "remote inference token is unavailable; no local credential was changed"
  fi

  byte_count=$(wc -c <"$temp" | tr -d ' ')
  line_count=$(awk 'END { print NR }' "$temp")
  if (( byte_count < 32 || byte_count > 513 )) || [[ "$line_count" != 1 ]] || \
     ! LC_ALL=C grep -Eq '^[A-Za-z0-9._~-]+$' "$temp"; then
    rm -f -- "$temp"
    die "remote inference token did not pass the local format check; no local credential was changed"
  fi

  if cmp -s -- "$temp" "$secrets_dir/inference_token"; then
    rm -f -- "$temp"
    note "RunPod inference credential already matches; the existing local file was preserved."
  else
    mv -f -- "$temp" "$secrets_dir/inference_token"
    chmod 600 "$secrets_dir/inference_token"
    note "Existing RunPod inference credential synchronized to the local Compose secret without printing it."
  fi
  if [[ ${1:-} != --during-up ]]; then
    note "Run ./scripts/dev.sh up to recreate the LIVE worker with this credential."
  fi
}

cmd_fetch_runpod_bundle() {
  prepare_local
  load_live_values
  local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE"
  ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1 || \
    die "HOST_KEY_CONFIRMATION_REQUIRED: confirm the fingerprint in the app connection settings"
  ssh_args

  local root="$project_root/reference/runpod" target="$project_root/reference/runpod/inference" stage stamp current_boot
  local expected_receipt actual_receipt pending
  mkdir -p "$root"
  stage=$(mktemp -d "$root/.inference.XXXXXX")
  mkdir -p "$stage/contracts" "$stage/receipts"

  SCP_ARGS=(-q -r -P "$RUNPOD_SSH_PORT_VALUE" -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$KNOWN_HOSTS_VALUE" -o ForwardAgent=no)
  if [[ "$SSH_AGENT_MODE" == 1 ]]; then
    SCP_ARGS+=(-o IdentitiesOnly=no)
  else
    SCP_ARGS+=(-o IdentitiesOnly=yes -i "$SSH_KEY_VALUE")
  fi

  current_boot=$(ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" sh -s <scripts/remote/current_boot.sh)
  [[ "$current_boot" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
    rm -rf -- "$stage"
    die "authenticated remote /version returned an invalid boot id"
  }
  mkdir -p "$stage/receipts/by-boot/$current_boot"
  if ! ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" sh -s \
      <scripts/remote/version_receipt.sh >"$stage/receipts/version.json"; then
    rm -rf -- "$stage"
    die "failed to preserve the authenticated RunPod version receipt"
  fi

  if ! scp "${SCP_ARGS[@]}" \
      "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:/workspace/dorilab/inference/mac" "$stage/" || \
     ! scp "${SCP_ARGS[@]}" \
      "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:/workspace/dorilab/inference/API_CONTRACT.md" "$stage/" || \
     ! scp "${SCP_ARGS[@]}" \
      "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:/workspace/dorilab/inference/contracts/system_allowlist.json" "$stage/contracts/" || \
     ! scp "${SCP_ARGS[@]}" \
      "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:/workspace/dorilab/inference/run/$current_boot/model_receipt.json" "$stage/receipts/model_receipt.json"; then
    rm -rf -- "$stage"
    die "failed to copy the approved RunPod inference client/contract bundle"
  fi
  cp -- "$stage/receipts/model_receipt.json" "$stage/receipts/by-boot/$current_boot/model_receipt.json"
  cp -- "$stage/receipts/version.json" "$stage/receipts/by-boot/$current_boot/version.json"
  if ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" \
      test -f /workspace/dorilab/inference/contracts/service_contracts.json; then
    if ! scp "${SCP_ARGS[@]}" \
        "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:/workspace/dorilab/inference/contracts/service_contracts.json" \
        "$stage/contracts/service_contracts.json"; then
      rm -rf -- "$stage"
      die "failed to copy the installed service contract overlay"
    fi
  fi

  find "$stage" -type f -exec chmod 600 {} +
  find "$stage" -type d -exec chmod 700 {} +
  expected_receipt=$(awk -F'"' '$2=="model_receipt_id"{print $4; exit}' packages/contracts/model_profiles/rc3.json)
  actual_receipt=$(awk -F'"' '$2=="model_receipt_id"{print $4; exit}' "$stage/receipts/version.json")
  [[ "$expected_receipt" =~ ^[0-9a-f]{64}$ && "$actual_receipt" =~ ^[0-9a-f]{64}$ ]] || {
    rm -rf -- "$stage"
    die "model receipt IDs could not be validated while fetching the RunPod bundle"
  }
  if [[ "$actual_receipt" != "$expected_receipt" ]]; then
    pending="$root/inference.pending-$current_boot"
    if [[ -e "$pending" ]]; then
      stamp=$(date -u +%Y%m%dT%H%M%SZ)
      pending="$root/inference.pending-$current_boot-$stamp"
    fi
    mv -- "$stage" "$pending"
    note "MODEL_RELEASE_MISMATCH: preserved the unapproved current bundle at $pending."
    note "The approved reference/runpod/inference baseline was not replaced."
    return 2
  fi
  if [[ -e "$target" ]]; then
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    mv -- "$target" "$target.previous-$stamp"
  fi
  mv -- "$stage" "$target"
  note "Copied the approved RunPod Mac client, API contract, allowlist, and current boot receipt ($current_boot) to reference/runpod/inference."
  note "No remote file or process was changed. No service token was included in the bundle."
}

cmd_deploy_runpod_contractfix1() {
  prepare_local
  load_live_values
  local lookup="[$RUNPOD_HOST_VALUE]:$RUNPOD_SSH_PORT_VALUE"
  ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1 || \
    die "HOST_KEY_CONFIRMATION_REQUIRED: confirm the fingerprint in the app connection settings"
  ssh_args

  local package="$project_root/services/inference/runpod_rc3_contractfix1"
  local expected_sha="358b23d9445ee2950ad63d383ed68330c4d3cba18f41231a76be5b7f495961e5"
  local expected_contractfix1_sha="1eecf4df26f21b6b0d1eb99abebf8932cf319092b59c4f0005bc3b0191e80f1c"
  local contract_id="7240db117d7c66d5bb162ce72290fee4b87bfaefa97771246d392be07c0b0114"
  [[ -f "$package/model_runtime.py" && -f "$package/contract_conformance.py" && \
     -f "$package/finalize_receipt.py" && \
     -f "$package/contracts/service_contracts.json" ]] || die "contractfix1 package is incomplete"

  local remote_sha
  remote_sha=$(ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" \
    sha256sum /workspace/dorilab/inference/model_runtime.py | awk '{print $1}')
  if [[ "$remote_sha" != "$expected_sha" && "$remote_sha" != "$expected_contractfix1_sha" && \
        "$remote_sha" != "$(openssl dgst -sha256 "$package/model_runtime.py" | awk '{print $NF}')" ]]; then
    die "RunPod model_runtime.py differs from the reviewed source; no files were changed"
  fi

  note "Contract improvement deployment plan:"
  note "  target: $SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$RUNPOD_SSH_PORT_VALUE"
  note "  preserve parent contract: 4fe243…0282f (v15_rc1)"
  note "  add immutable contract: $contract_id (v15_rc1_cf1)"
  note "  change: require evidence_refs for every action, including [] when empty"
  note "  receipt: separate immutable model release digest from per-process boot_id"
  note "  verify: three new synthetic cases; no customer data or evaluation gold"
  note "  restart only the exact /workspace/dorilab/inference/server.py process"
  note "  change no weights, adapter, packages, Pod setting, port, token, or local Validator"
  note "  automatically restore the reviewed files if readiness or conformance fails"
  [[ -t 0 ]] || die "deploy-runpod-contractfix1 requires an interactive confirmation"
  local answer stamp stage
  read -r -p "Proceed with this exact approved plan? [deploy/no] " answer
  [[ "$answer" == deploy ]] || { note "Deployment cancelled; no changes made."; return 0; }

  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  stage="/workspace/dorilab/inference/.contractfix1-stage-$stamp"
  ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" mkdir -p -- "$stage/contracts"
  SCP_ARGS=(-q -P "$RUNPOD_SSH_PORT_VALUE" -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$KNOWN_HOSTS_VALUE" -o ForwardAgent=no)
  if [[ "$SSH_AGENT_MODE" == 1 ]]; then
    SCP_ARGS+=(-o IdentitiesOnly=no)
  else
    SCP_ARGS+=(-o IdentitiesOnly=yes -i "$SSH_KEY_VALUE")
  fi
  scp "${SCP_ARGS[@]}" "$package/model_runtime.py" "$package/contract_conformance.py" \
    "$package/finalize_receipt.py" \
    "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$stage/"
  scp "${SCP_ARGS[@]}" "$package/contracts/service_contracts.json" \
    "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE:$stage/contracts/"
  ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$RUNPOD_HOST_VALUE" \
    sh -s -- "$stage" "$expected_sha" "$expected_contractfix1_sha" <scripts/remote/deploy_contractfix1.sh
}

usage() {
  cat <<'EOF'
Usage: ./scripts/dev.sh <setup|sync-runpod-token|fetch-runpod-bundle|deploy-runpod|deploy-runpod-contractfix1|up|status|logs|test|down> [--demo]
EOF
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  command=${1:-}
  shift || true
  case "$command" in
  setup) cmd_setup "$@" ;;
  sync-runpod-token) cmd_sync_runpod_token "$@" ;;
  fetch-runpod-bundle) cmd_fetch_runpod_bundle "$@" ;;
  deploy-runpod) cmd_deploy_runpod "$@" ;;
  deploy-runpod-contractfix1) cmd_deploy_runpod_contractfix1 "$@" ;;
  up) cmd_up "$@" ;;
  status) cmd_status "$@" ;;
  logs) cmd_logs "$@" ;;
  test) cmd_test "$@" ;;
  down) cmd_down "$@" ;;
  *) usage; exit 64 ;;
  esac
fi
