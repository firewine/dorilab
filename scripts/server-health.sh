#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
umask 077
mkdir -p "$ROOT/var/run-records/server-health"
chmod 700 "$ROOT/var/run-records/server-health"
docker run --rm --user "$(id -u):$(id -g)" --entrypoint python \
  -v "$ROOT/scripts/server-health.py:/tools/server-health.py:ro" \
  -v "$ROOT/.secrets/sites_gateway_token:/run/secrets/sites_gateway_token:ro" \
  -v "$ROOT/.secrets/cloud-sites-identities.json:/run/secrets/sites_identities.json:ro" \
  -v "$ROOT/var/run-records/server-health:/records" \
  dorilab-cloud:stage1 /tools/server-health.py
