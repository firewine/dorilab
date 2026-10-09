#!/usr/bin/env bash
# Small CPU backend stage; does not change the original app or Sites destination.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export DORILAB_CLOUD_TEST_UID="$(id -u)"
export DORILAB_CLOUD_TEST_GID="$(id -g)"
DC=(docker compose -f "$ROOT/compose.cloud-test.yaml")
RECORDS="$ROOT/var/run-records/cloud-backend-20261004"
case "${1:-help}" in
  build)
    docker build -f services/cloud/Dockerfile -t dorilab-cloud:stage1 . ;;
  prepare-test)
    BACKUP="$ROOT/var/run-records/neon-db-stage1-20261004.KUPyNv"
    if [[ -f "$BACKUP/cloud-preparation.json" ]]; then
      echo 'Existing test preparation retained. Use verify-test; no credentials or data changed.'
      exit 0
    fi
    (cd "$BACKUP" && shasum -a 256 -c backups.sha256) >/dev/null
    docker run --rm --user "$DORILAB_CLOUD_TEST_UID:$DORILAB_CLOUD_TEST_GID" \
      -e PGSERVICEFILE=/secrets/neon-test.pgservice.conf \
      -v "$ROOT/.secrets/neon-test/neon-test.pgservice.conf:/secrets/neon-test.pgservice.conf:ro" \
      -v "$ROOT/.secrets:/credentials" \
      -v "$ROOT/.secrets/sites_identities.json:/source-secrets/sites_identities.json:ro" \
      -v "$ROOT/scripts:/tools:ro" -v "$BACKUP:/records" dorilab-cloud:stage1 python /tools/cloud_prepare.py ;;
  up-test)
    [[ -f .secrets/cloud-runtime-db.json && -f .secrets/cloud-sites-identities.json ]] || { echo 'Prepare the verified Neon test branch first.'; exit 1; }
    "${DC[@]}" up -d --wait --wait-timeout 90 ;;
  create-test|verify-test)
    ACTION="${1%-test}"
    mkdir -p "$RECORDS"
    "${DC[@]}" run --rm --no-deps -e PYTHONPATH=/app:/tools --entrypoint python \
      -v "$ROOT/scripts:/tools:ro" -v "$RECORDS:/records" backend /tools/cloud_probe.py "$ACTION" ;;
  down-test)
    "${DC[@]}" down --remove-orphans
    echo 'Only CPU test containers removed. Neon, original Mac app, files and RunPod preserved.' ;;
  status-test) "${DC[@]}" ps ;;
  *) echo 'Usage: ./scripts/cloud-backend.sh build | prepare-test | up-test | create-test | verify-test | down-test | status-test' ;;
esac
