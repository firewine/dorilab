#!/bin/bash
# Reuse the whole local Docker application; do not export its DB or private keys.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
COMPOSE=(docker compose -f compose.yaml -f compose.sites.yaml)
case ${1:-status} in
  setup)
    owner=${2:-}
    [[ "$owner" =~ ^[A-Za-z0-9_-]{10,200}$ ]] || { echo 'The verified Sites owner ID is required.' >&2; exit 2; }
    mkdir -p .secrets
    docker run --rm --network none --user "$(id -u):$(id -g)" -v "$ROOT/.secrets:/secrets" --entrypoint python dorilab-api -c '
import json, os, secrets, sys
from pathlib import Path
os.umask(0o077)
token=Path("/secrets/sites_gateway_token")
if not token.exists():
    with token.open("x") as f: f.write(secrets.token_urlsafe(48)+"\n")
mapping=Path("/secrets/sites_identities.json")
value={"backend_location":"MAC","identities":{sys.argv[1]:["engineer@demo","reviewer@demo","approver@demo"]}}
if not mapping.exists():
    with mapping.open("x") as f: json.dump(value,f)
elif json.loads(mapping.read_text())!=value:
    raise SystemExit("Existing identity mapping differs; it was preserved.")
for file in [token,mapping]: file.chmod(0o600)
' "$owner"
    echo 'Sites gateway token and verified owner mapping prepared; existing secrets preserved.'
    ;;
  up)
    [[ -f .secrets/sites_gateway_token && -f .secrets/sites_identities.json ]] || { echo 'Run setup first.' >&2; exit 2; }
    "${COMPOSE[@]}" config --quiet
    "${COMPOSE[@]}" up --no-deps --build -d sites-gateway
    "${COMPOSE[@]}" up --no-deps -d sites-tunnel
    echo 'Only the Sites gateway/tunnel were started. Existing API, worker, DB and volumes were preserved.'
    echo 'Mac and Docker must remain running. Quick Tunnel URLs change after recreation.'
    ;;
  status) "${COMPOSE[@]}" ps sites-gateway sites-tunnel ;;
  url) "${COMPOSE[@]}" logs --no-log-prefix sites-tunnel 2>/dev/null | sed -nE 's/.*(https:\/\/[a-z0-9-]+\.trycloudflare\.com).*/\1/p' | tail -1 ;;
  down)
    "${COMPOSE[@]}" stop sites-tunnel sites-gateway
    echo 'Stopped only Sites ingress. The local app, DB, attachments and secrets remain.'
    ;;
  *) echo 'Usage: ./scripts/sites-bridge.sh setup <verified-site-owner-id> | up | status | url | down' >&2; exit 2 ;;
esac
