#!/bin/sh
set -eu

token_path=/root/.config/dorilab/inference.token
[ -r "$token_path" ] || { echo "remote inference token unavailable" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 unavailable" >&2; exit 2; }

python3 - "$token_path" <<'PY'
import json
import pathlib
import re
import sys
import urllib.request

token = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
request = urllib.request.Request(
    "http://127.0.0.1:8080/version",
    headers={"Authorization": "Bearer " + token},
)
with urllib.request.urlopen(request, timeout=5) as response:
    receipt = json.load(response)
boot_id = receipt.get("boot_id", "")
if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", boot_id):
    raise SystemExit("invalid boot id")
print(boot_id)
PY
