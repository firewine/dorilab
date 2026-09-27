#!/usr/bin/env bash
set -Eeuo pipefail
set +x
: "${DORILAB_SSH_HOST:?Set RunPod direct SSH host}"
: "${DORILAB_SSH_PORT:?Set RunPod direct SSH port}"
: "${DORILAB_SSH_KEY:?Set absolute SSH private key path}"
umask 077
dest="${DORILAB_TOKEN_FILE:-$HOME/.config/dorilab/inference.token}"
mkdir -p "$(dirname "$dest")"
chmod 700 "$(dirname "$dest")"
tmp=$(mktemp "${dest}.tmp.XXXXXX")
trap 'rm -f "$tmp"' EXIT
ssh -T -p "$DORILAB_SSH_PORT" -i "$DORILAB_SSH_KEY" \
  -o StrictHostKeyChecking=yes -o BatchMode=yes \
  "root@$DORILAB_SSH_HOST" \
  'test -f /root/.config/dorilab/inference.token && cat /root/.config/dorilab/inference.token' > "$tmp"
python3 - "$tmp" <<'PY'
import pathlib,sys
s=pathlib.Path(sys.argv[1]).read_text().strip()
if len(s)<32 or any(c.isspace() for c in s):raise SystemExit('invalid token transfer; existing token retained')
PY
chmod 600 "$tmp"
mv "$tmp" "$dest"
trap - EXIT
printf 'Service token securely saved; value not displayed.\n'
