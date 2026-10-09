#!/bin/sh
set -eu

stage=$1
expected_current_sha=$2
expected_contractfix1_sha=$3
target=/workspace/dorilab/inference
runtime=/root/venvs/dorilab-tournament/bin/python

case "$stage" in "$target"/.contractfix1-stage-*) ;; *) echo "invalid contractfix stage" >&2; exit 64;; esac
[ -d "$stage" ] || { echo "stage missing" >&2; exit 2; }
for file in model_runtime.py contract_conformance.py finalize_receipt.py contracts/service_contracts.json; do
  [ -f "$stage/$file" ] || { echo "stage file missing: $file" >&2; exit 2; }
done
[ -x "$runtime" ] || { echo "approved runtime unavailable" >&2; exit 2; }
[ -f "$target/server.py" ] && [ -f "$target/start_service.py" ] || {
  echo "installed inference service source is incomplete" >&2; exit 2;
}

current_sha=$(sha256sum "$target/model_runtime.py" | awk '{print $1}')
new_sha=$(sha256sum "$stage/model_runtime.py" | awk '{print $1}')
if [ "$current_sha" != "$expected_current_sha" ] && \
   [ "$current_sha" != "$expected_contractfix1_sha" ] && \
   [ "$current_sha" != "$new_sha" ]; then
  echo "installed model_runtime.py differs from both reviewed and staged versions" >&2
  exit 3
fi

"$runtime" - "$stage" <<'PY'
import ast, hashlib, json, pathlib, sys
stage = pathlib.Path(sys.argv[1])
for name in ('model_runtime.py', 'contract_conformance.py', 'finalize_receipt.py'):
    ast.parse((stage / name).read_text(encoding='utf-8'), filename=name)
doc = json.loads((stage / 'contracts/service_contracts.json').read_text(encoding='utf-8'))
assert doc['schema_version'] == 1 and len(doc['contracts']) == 1
row = doc['contracts'][0]
assert row['route'] == 'v15_rc1_cf1'
assert row['parent_id'] == '4fe243c2300a5084f54833e7b6fd8aa45f55592c9dfcf6aaa53cc07692e0282f'
assert hashlib.sha256(row['system'].encode()).hexdigest() == row['system_sha256'] == row['id']
print('staged_contract_id=' + row['id'])
PY

if [ "$current_sha" = "$new_sha" ] && \
   cmp -s "$target/contracts/service_contracts.json" "$stage/contracts/service_contracts.json" && \
   cmp -s "$target/contract_conformance.py" "$stage/contract_conformance.py" && \
   cmp -s "$target/finalize_receipt.py" "$stage/finalize_receipt.py"; then
  rm -rf -- "$stage"
  echo "identical contractfix1 files are already installed"
  exit 0
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="$target/backups/contractfix1-$stamp"
mkdir -p "$backup"
cp -- "$target/model_runtime.py" "$backup/model_runtime.py"
if [ -f "$target/contracts/service_contracts.json" ]; then
  cp -- "$target/contracts/service_contracts.json" "$backup/service_contracts.json"
  : >"$backup/had_service_contracts"
fi
if [ -f "$target/contract_conformance.py" ]; then
  cp -- "$target/contract_conformance.py" "$backup/contract_conformance.py"
  : >"$backup/had_contract_conformance"
fi
if [ -f "$target/finalize_receipt.py" ]; then
  cp -- "$target/finalize_receipt.py" "$backup/finalize_receipt.py"
  : >"$backup/had_finalize_receipt"
fi

cp -- "$stage/model_runtime.py" "$target/.model_runtime.py.contractfix1"
cp -- "$stage/contract_conformance.py" "$target/.contract_conformance.py.contractfix1"
cp -- "$stage/finalize_receipt.py" "$target/.finalize_receipt.py.contractfix1"
cp -- "$stage/contracts/service_contracts.json" "$target/contracts/.service_contracts.json.contractfix1"
chmod 644 "$target/.model_runtime.py.contractfix1" "$target/.contract_conformance.py.contractfix1" \
  "$target/.finalize_receipt.py.contractfix1" \
  "$target/contracts/.service_contracts.json.contractfix1"
mv -- "$target/.model_runtime.py.contractfix1" "$target/model_runtime.py"
mv -- "$target/.contract_conformance.py.contractfix1" "$target/contract_conformance.py"
mv -- "$target/.finalize_receipt.py.contractfix1" "$target/finalize_receipt.py"
mv -- "$target/contracts/.service_contracts.json.contractfix1" "$target/contracts/service_contracts.json"
rm -rf -- "$stage"

service_pid() {
  "$runtime" - "$target/run/service.json" 2>/dev/null <<'PY' || true
import json, pathlib, sys
try: print(json.loads(pathlib.Path(sys.argv[1]).read_text())['pid'])
except Exception: pass
PY
}

stop_exact_service() {
  pid=$(service_pid)
  [ -n "$pid" ] || { echo "service pid missing" >&2; return 1; }
  [ -r "/proc/$pid/cmdline" ] || { echo "service process missing" >&2; return 1; }
  command=$(tr '\000' ' ' <"/proc/$pid/cmdline")
  case "$command" in *"$target/server.py"*) ;; *) echo "pid does not match DoriLab inference server" >&2; return 1;; esac
  kill -TERM "$pid"
  count=0
  while kill -0 "$pid" 2>/dev/null; do
    count=$((count+1))
    [ "$count" -le 60 ] || { echo "service did not stop after SIGTERM; no stronger signal sent" >&2; return 1; }
    sleep 1
  done
}

ready() {
  "$runtime" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz',timeout=3).read()" \
    >/dev/null 2>&1
}

wait_ready() {
  count=0
  while ! ready; do
    count=$((count+1))
    if [ $((count % 6)) -eq 0 ]; then echo "waiting_for_model_ready_seconds=$((count*5))"; fi
    [ "$count" -le 180 ] || return 1
    sleep 5
  done
}

start_service() {
  count=0
  while true; do
    if "$runtime" "$target/start_service.py"; then return 0; fi
    count=$((count+1))
    [ "$count" -le 15 ] || return 1
    echo "waiting_for_listener_release_seconds=$count"
    sleep 1
  done
}

restore_files() {
  cp -- "$backup/model_runtime.py" "$target/model_runtime.py"
  if [ -f "$backup/had_service_contracts" ]; then
    cp -- "$backup/service_contracts.json" "$target/contracts/service_contracts.json"
  else
    rm -f -- "$target/contracts/service_contracts.json"
  fi
  if [ -f "$backup/had_contract_conformance" ]; then
    cp -- "$backup/contract_conformance.py" "$target/contract_conformance.py"
  else
    rm -f -- "$target/contract_conformance.py"
  fi
  if [ -f "$backup/had_finalize_receipt" ]; then
    cp -- "$backup/finalize_receipt.py" "$target/finalize_receipt.py"
  else
    rm -f -- "$target/finalize_receipt.py"
  fi
}

rollback() {
  echo "contractfix1 verification failed; restoring reviewed service files" >&2
  stop_exact_service || true
  restore_files
  start_service || { echo "reviewed service could not be restarted; operator inspection required" >&2; exit 5; }
  wait_ready || { echo "restored service did not become ready; operator inspection required" >&2; exit 5; }
  echo "reviewed prior service restored and ready" >&2
  exit 4
}

if ! stop_exact_service; then
  restore_files
  echo "service was not restarted; staged file changes were rolled back" >&2
  exit 4
fi

if ! start_service; then
  echo "new service could not start; restoring reviewed files" >&2
  restore_files
  start_service || { echo "reviewed service could not be restarted; operator inspection required" >&2; exit 5; }
  wait_ready || { echo "restored service did not become ready; operator inspection required" >&2; exit 5; }
  exit 4
fi
wait_ready || rollback

conformance_log="$target/artifacts/contractfix1-conformance-$stamp.log"
if "$runtime" "$target/contract_conformance.py" >"$conformance_log" 2>&1; then
  cat "$conformance_log"
else
  cat "$conformance_log" >&2
  rollback
fi

conformance_dir=$("$runtime" - "$conformance_log" <<'PY'
import json, pathlib, sys
lines = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()
value = json.loads(lines[-1])
print(value['directory'])
PY
)
if ! "$runtime" "$target/finalize_receipt.py" "$conformance_dir"; then
  rollback
fi

echo "contractfix1 deployed, model ready, and three synthetic cases passed"
