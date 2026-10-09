#!/usr/bin/env bash
# Mac-side controller: only an explicit, authenticated UI apply request is handled.
# The app gets neither the private key nor the Docker socket. No remote writes.
set -euo pipefail

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
source "$project_root/scripts/dev.sh"
control_dir="$project_root/var/connection/control"
request_file="$control_dir/request.env"
status_file="$control_dir/status.env"
umask 077

write_status() {
  local id=$1 phase=$2 code=$3 active_host=${4:-} active_port=${5:-} ssh_state=${6:-NOT_CONNECTED} temporary
  temporary=$(mktemp "$control_dir/.status.XXXXXX")
  {
    printf 'REQUEST_ID=%s\nPHASE=%s\nCODE=%s\n' "$id" "$phase" "$code"
    printf 'ACTIVE_HOST=%s\nACTIVE_PORT=%s\nUPDATED_AT=%s\n' "$active_host" "$active_port" "$(date -u +%s)"
    printf 'SSH_STATE=%s\n' "$ssh_state"
  } >"$temporary"
  mv -f -- "$temporary" "$status_file"
}

heartbeat() {
  local temporary
  temporary=$(mktemp "$control_dir/.heartbeat.XXXXXX")
  printf 'UPDATED_AT=%s\n' "$(date -u +%s)" >"$temporary"
  mv -f -- "$temporary" "$control_dir/heartbeat.env"
}

apply_request() {
  local id host port requested now lookup error_file code credential_code=APPLIED
  id=$(env_value REQUEST_ID "$request_file")
  if [[ "$id" == "$(env_value REQUEST_ID "$status_file")" ]] && \
     [[ $(env_value PHASE "$status_file") =~ ^(APPLIED|FAILED)$ ]]; then
    return 0
  fi
  host=$(env_value RUNPOD_HOST "$request_file")
  port=$(env_value RUNPOD_SSH_PORT "$request_file")
  requested=$(env_value REQUESTED_AT "$request_file")
  [[ "$id" =~ ^[a-f0-9]{32}$ ]] || return 64
  if ! valid_host "$host" || ! valid_port "$port" || [[ ! "$requested" =~ ^[0-9]{1,12}$ ]]; then
    write_status "$id" FAILED INVALID_CONNECTION_REQUEST
    return 0
  fi
  now=$(date -u +%s)
  if (( now - requested > 300 || requested > now + 5 )); then
    write_status "$id" FAILED CONNECTION_REQUEST_EXPIRED
    return 0
  fi
  if [[ "$host" != "$(live_value RUNPOD_HOST)" || "$port" != "$(live_value RUNPOD_SSH_PORT)" ]]; then
    write_status "$id" FAILED CONNECTION_SETTINGS_CHANGED
    return 0
  fi
  write_status "$id" APPLYING CHECKING_SSH
  error_file=$(mktemp "$control_dir/.error.XXXXXX")
  if ! (load_live_values) >"$error_file" 2>&1; then
    write_status "$id" FAILED SSH_AUTH_FAILED
    rm -f -- "$error_file"
    return 0
  fi
  load_live_values
  lookup="[$host]:$port"
  if ! ssh-keygen -F "$lookup" -f "$KNOWN_HOSTS_VALUE" >/dev/null 2>&1; then
    write_status "$id" FAILED HOST_KEY_CONFIRMATION_REQUIRED
    rm -f -- "$error_file"
    return 0
  fi
  if ! docker_ready || ! docker_is_local_mac; then
    write_status "$id" FAILED LOCAL_DOCKER_UNAVAILABLE
    rm -f -- "$error_file"
    return 0
  fi
  ssh_args
  if ! ssh "${SSH_ARGS[@]}" -- "$SSH_USER_VALUE@$host" true >"$error_file" 2>&1; then
    code=SSH_UNREACHABLE
    if grep -qi 'permission denied\|load key\|sign_and_send_pubkey' "$error_file"; then code=SSH_AUTH_FAILED; fi
    if grep -qi 'host key verification failed\|REMOTE HOST IDENTIFICATION HAS CHANGED' "$error_file"; then code=HOST_KEY_CONFIRMATION_REQUIRED; fi
    write_status "$id" FAILED "$code"
    rm -f -- "$error_file"
    return 0
  fi
  # API/worker admission is paused by this request. Check retained jobs again,
  # including requests accepted just before the UI applied the new connection.
  compose_args live
  local busy
  busy=$("${COMPOSE[@]}" exec -T db psql -U dorilab -d dorilab -At -c \
    "SELECT count(*) FROM review_jobs WHERE status IN ('QUEUED','DISPATCHING','RUNNING','OUTPUT_RECEIVED','VALIDATING')")
  if [[ "$busy" != 0 ]]; then
    write_status "$id" FAILED CONNECTION_CHANGE_BUSY
    rm -f -- "$error_file"
    return 0
  fi
  write_status "$id" APPLYING SSH_CONNECTED
  if ! (cmd_sync_runpod_token --during-up) >"$error_file" 2>&1; then
    # An absent API/token does not take down the local app or invent a credential.
    credential_code=SERVICE_NOT_DEPLOYED
  fi
  write_status "$id" APPLYING STARTING_TUNNEL
  "${COMPOSE[@]}" --profile live up -d --no-deps llm-tunnel
  local ssh_state=SSH_UNREACHABLE
  for _ in {1..20}; do
    if "${COMPOSE[@]}" exec -T llm-tunnel nc -z 127.0.0.1 18080 >/dev/null 2>&1; then
      ssh_state=CONNECTED
      break
    fi
    sleep 1
  done
  if [[ "$ssh_state" != CONNECTED ]]; then
    "${COMPOSE[@]}" --profile live logs --tail=20 llm-tunnel >"$error_file" 2>&1 || true
    if grep -qi 'permission denied\|unprotected private key\|load key' "$error_file"; then ssh_state=SSH_AUTH_FAILED; fi
    if grep -qi 'host key verification failed\|REMOTE HOST IDENTIFICATION HAS CHANGED' "$error_file"; then ssh_state=HOST_KEY_CONFIRMATION_REQUIRED; fi
    credential_code=$ssh_state
  fi
  write_status "$id" APPLYING ACTIVATING_LIVE
  "${COMPOSE[@]}" --profile live up -d --no-deps --force-recreate worker
  "${COMPOSE[@]}" --profile live up -d --no-deps api
  printf 'live\n' >"$last_mode_file"
  rm -f -- "$error_file"
  write_status "$id" APPLIED "$credential_code" "$host" "$port" "$ssh_state"
}

watch() {
  mkdir -p "$control_dir"
  local lock_dir="$secrets_dir/local-connection.lock" child="" id last_id phase
  if ! mkdir "$lock_dir" 2>/dev/null; then
    local owner=""
    [[ -f "$lock_dir/pid" ]] && owner=$(<"$lock_dir/pid")
    if [[ "$owner" =~ ^[0-9]+$ ]] && kill -0 "$owner" 2>/dev/null; then return 0; fi
    rm -f -- "$lock_dir/pid"
    rmdir "$lock_dir" 2>/dev/null || return 1
    mkdir "$lock_dir" || return 1
  fi
  printf '%s\n' "$$" >"$lock_dir/pid"
  printf '%s\n' "$$" >"$secrets_dir/local-connection.pid"
  trap 'rm -f -- "$control_dir/heartbeat.env" "$lock_dir/pid"; rmdir "$lock_dir" 2>/dev/null || true' EXIT
  trap 'exit 0' TERM INT
  # A previous controller may have died between Docker operations. Observe the
  # result; never replay that operation implicitly after a Mac/process restart.
  id=$(env_value REQUEST_ID "$request_file")
  if [[ "$id" =~ ^[a-f0-9]{32}$ ]] && [[ $(env_value PHASE "$status_file") == APPLYING ]]; then
    write_status "$id" FAILED UNKNOWN_LOCAL_APPLY_OUTCOME
  fi
  while true; do
    heartbeat
    id=$(env_value REQUEST_ID "$request_file")
    last_id=$(env_value REQUEST_ID "$status_file")
    phase=$(env_value PHASE "$status_file")
    if [[ "$id" =~ ^[a-f0-9]{32}$ ]] && \
       { [[ "$id" != "$last_id" ]] || [[ "$phase" != APPLIED && "$phase" != FAILED ]]; }; then
      # Keep the heartbeat alive while Docker/SSH is working. Exactly one apply.
      bash "$project_root/scripts/local-connection.sh" apply >"$control_dir/apply.log" 2>&1 &
      child=$!
      while kill -0 "$child" 2>/dev/null; do heartbeat; sleep 1; done
      if ! wait "$child"; then write_status "$id" FAILED LOCAL_APPLY_FAILED; fi
      child=""
    fi
    sleep 1
  done
}

case ${1:-} in
  watch) watch ;;
  apply) mkdir -p "$control_dir"; apply_request ;;
  *) exit 64 ;;
esac
