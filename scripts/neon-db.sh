#!/usr/bin/env bash
# Stage 1 only: backup, isolated restore, compare. Never switches the app DB.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DC=(docker compose -f "$ROOT/compose.yaml")
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
EXPECTED_NEON_HOST='ep-empty-hall-b59hexb4.c-7.us-east-2.aws.neon.tech'
COMMAND="${1:-help}"
RECORDS="${2:-}"
HELPER_CONTAINER=''
LOCAL_CONTAINER=''
cleanup() {
  if [[ -n "$HELPER_CONTAINER" ]]; then docker rm -f "$HELPER_CONTAINER" >/dev/null 2>&1 || true; fi
  if [[ -n "$LOCAL_CONTAINER" ]]; then docker rm -f "$LOCAL_CONTAINER" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

case "$COMMAND" in
  backup|check-local|restore-test|verify-test) ;;
  *) echo 'Usage: ./scripts/neon-db.sh backup | check-local RECORDS | restore-test RECORDS | verify-test RECORDS'; exit 0 ;;
esac
docker info >/dev/null
API_ID="$("${DC[@]}" ps -q api)"
[[ -n "$API_ID" ]] || { echo 'Original API container must exist; nothing changed.'; exit 1; }
CPU_IMAGE="$(docker inspect --format '{{.Image}}' "$API_ID")"
DB_ID="$("${DC[@]}" ps -q db)"
[[ -n "$DB_ID" ]] || exit 1
DB_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$DB_ID")"
APP_NETWORK="$(docker inspect --format '{{range $name,$value := .NetworkSettings.Networks}}{{$name}}{{end}}' "$DB_ID")"

if [[ "$COMMAND" == backup ]]; then
  RECORDS="$(mktemp -d "$ROOT/var/run-records/neon-db-stage1-20261004.XXXXXX")"
else
  [[ -d "$RECORDS" ]] || { echo 'Backup record directory required.'; exit 1; }
  RECORDS="$(cd "$RECORDS" && pwd)"
  case "$RECORDS" in "$ROOT"/var/run-records/neon-db-stage1-*) ;; *) echo 'Unexpected backup directory'; exit 1 ;; esac
  [[ -f "$RECORDS/source-manifest.json" && -f "$RECORDS/database.dump" ]] || exit 1
  (cd "$RECORDS" && shasum -a 256 -c backups.sha256) >/dev/null
fi

python_tool() {
  local secret_mount
  if [[ "${3:-}" == local_test ]]; then
    secret_mount="$ROOT/.secrets/local-test.password:/secrets/local-test.password:ro"
  else
    secret_mount="$ROOT/.secrets/neon-test/neon-test.pgservice.conf:/secrets/neon-test.pgservice.conf:ro"
  fi
  docker run --rm --user "$HOST_UID:$HOST_GID" --network "$APP_NETWORK" \
    -e PGSERVICEFILE=/secrets/neon-test.pgservice.conf \
    -e TRANSFER_NEON_HOST="$EXPECTED_NEON_HOST" \
    -e TRANSFER_LOCAL_HOST="${LOCAL_CONTAINER:-unused}" \
    -v "$ROOT/scripts/db_transfer.py:/transfer.py:ro" \
    -v "$secret_mount" -v "$RECORDS:/records" \
    "$CPU_IMAGE" python /transfer.py "$@"
}

if [[ "$COMMAND" == backup ]]; then
  HELPER_CONTAINER="dorilab-snapshot-${RECORDS##*.}"
  docker run --rm --name "$HELPER_CONTAINER" --user "$HOST_UID:$HOST_GID" --network "$APP_NETWORK" \
    -e DORILAB_DB_HOST=db -e DORILAB_DB_PASSWORD_FILE=/secrets/db_password \
    -v "$ROOT/scripts/db_transfer.py:/transfer.py:ro" -v "$ROOT/.secrets/db_password:/secrets/db_password:ro" \
    -v "$RECORDS:/records" "$CPU_IMAGE" python /transfer.py snapshot >"$RECORDS/snapshot.log" 2>&1 &
  SNAPSHOT_PID=$!
  for ((i=0;i<120;i++)); do
    [[ -f "$RECORDS/snapshot.id" ]] && break
    kill -0 "$SNAPSHOT_PID" 2>/dev/null || { echo 'Snapshot failed; see protected record'; exit 1; }
    sleep 0.25
  done
  [[ -f "$RECORDS/snapshot.id" ]] || { echo 'Snapshot did not become ready'; exit 1; }
  read -r SNAPSHOT_ID < "$RECORDS/snapshot.id"
  [[ "$SNAPSHOT_ID" =~ ^[0-9A-F]+-[0-9A-F]+-[0-9]+$ ]] || exit 1
  "${DC[@]}" exec -T db pg_dump -U dorilab -d dorilab --format=custom --no-owner --no-acl \
    --snapshot="$SNAPSHOT_ID" > "$RECORDS/database.dump"
  touch "$RECORDS/snapshot.done"
  wait "$SNAPSHOT_PID"
  HELPER_CONTAINER=''
  tar -czf "$RECORDS/artifacts-exports.tar.gz" -C "$ROOT/var" artifacts exports
  (cd "$RECORDS" && shasum -a 256 database.dump artifacts-exports.tar.gz source-manifest.json > backups.sha256)
  echo "BACKUP_COMPLETE: $RECORDS"
  exit 0
fi

if [[ "$COMMAND" == check-local ]]; then
  LOCAL_CONTAINER="dorilab-restore-check-${RECORDS##*.}"
  [[ ! -f "$ROOT/.secrets/local-test.password" ]] || { echo 'Existing test password retained'; }
  if [[ ! -f "$ROOT/.secrets/local-test.password" ]]; then
    docker run --rm "$CPU_IMAGE" python -c 'import secrets; print(secrets.token_hex(32))' > "$ROOT/.secrets/local-test.password"
  fi
  docker run -d --name "$LOCAL_CONTAINER" --network "$APP_NETWORK" \
    --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_DB=restore_test -e POSTGRES_USER=restore_test \
    -e POSTGRES_PASSWORD_FILE=/run/secrets/password \
    -v "$ROOT/.secrets/local-test.password:/run/secrets/password:ro" "$DB_IMAGE" >/dev/null
  for ((i=0;i<60;i++)); do
    docker exec "$LOCAL_CONTAINER" pg_isready -U restore_test -d restore_test >/dev/null 2>&1 && break
    sleep 1
  done
  docker exec "$LOCAL_CONTAINER" pg_isready -U restore_test -d restore_test >/dev/null
  python_tool empty --database local_test
  docker exec -i "$LOCAL_CONTAINER" pg_restore -U restore_test -d restore_test --no-owner --no-privileges \
    --single-transaction --exit-on-error < "$RECORDS/database.dump" 2> "$RECORDS/local-restore.log"
  python_tool verify --database local_test
  python_tool files --database local_test
  exit 0
fi

[[ -f "$ROOT/.secrets/neon-test/neon-test.pgservice.conf" ]] || {
  mkdir -p "$ROOT/.secrets/neon-test"
  chmod 700 "$ROOT/.secrets/neon-test"
  docker run --rm --network none --user "$HOST_UID:$HOST_GID" -v "$ROOT/scripts/db_transfer.py:/transfer.py:ro" \
    -v "$ROOT/.secrets/neon-test.url:/secrets/neon-test.url:ro" \
    -v "$ROOT/.secrets/neon-test:/credentials" "$CPU_IMAGE" python /transfer.py prepare-neon --host "$EXPECTED_NEON_HOST"
}
if [[ "$COMMAND" == restore-test ]]; then
  [[ -f "$RECORDS/local_test-result.json" && -f "$RECORDS/file-backup-result.json" ]] || { echo 'Run check-local first'; exit 1; }
  docker run --rm --user "$HOST_UID:$HOST_GID" -v "$RECORDS:/records:ro" "$CPU_IMAGE" \
    python -c 'import json; assert all(json.load(open("/records/"+p))["passed"] for p in ("local_test-result.json","file-backup-result.json"))'
  python_tool empty --database neon_test
  # Credentials stay in a read-only service file, never process arguments or image.
  docker run --rm -i --user "$HOST_UID:$HOST_GID" --network "$APP_NETWORK" \
    -e PGSERVICE=neon_test -e PGSERVICEFILE=/run/secrets/neon-test.pgservice.conf \
    -v "$ROOT/.secrets/neon-test/neon-test.pgservice.conf:/run/secrets/neon-test.pgservice.conf:ro" \
    "$DB_IMAGE" pg_restore --dbname=service=neon_test --no-owner --no-privileges --single-transaction --exit-on-error \
    < "$RECORDS/database.dump" 2> "$RECORDS/neon-restore.log"
fi
python_tool verify --database neon_test
