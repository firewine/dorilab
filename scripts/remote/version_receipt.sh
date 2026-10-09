#!/bin/sh
set -eu

token_path=/root/.config/dorilab/inference.token
[ -r "$token_path" ] || { echo "remote inference token unavailable" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 unavailable" >&2; exit 2; }

python3 - "$token_path" <<'PY'
import pathlib
import sys
import urllib.request

token = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
request = urllib.request.Request(
    "http://127.0.0.1:8080/version",
    headers={"Authorization": "Bearer " + token},
)
with urllib.request.urlopen(request, timeout=5) as response:
    sys.stdout.buffer.write(response.read())
PY
