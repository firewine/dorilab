#!/bin/sh
set -eu

echo "DORILAB_REMOTE_INSPECTION_V1"
printf 'hostname='; hostname
printf 'kernel='; uname -srmo 2>/dev/null || uname -a

echo "gpu:"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,uuid,memory.total,memory.used --format=csv,noheader
else
  echo "NVIDIA_SMI_NOT_FOUND"
fi

echo "gpu_processes:"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null || true
fi

echo "inference_process:"
inference_pid=
if command -v ss >/dev/null 2>&1; then
  inference_pid=$(ss -ltnp 2>/dev/null | awk '$4 ~ /127\.0\.0\.1:8080$/ { if (match($0,/pid=[0-9]+/)) print substr($0,RSTART+4,RLENGTH-4) }' | sed -n '1p')
fi
if [ -n "$inference_pid" ] && [ -d "/proc/$inference_pid" ]; then
  printf 'pid=%s\n' "$inference_pid"
  printf 'cwd='; readlink -f "/proc/$inference_pid/cwd" 2>/dev/null || true
  printf 'exe='; readlink -f "/proc/$inference_pid/exe" 2>/dev/null || true
  printf 'command='; tr '\000' ' ' <"/proc/$inference_pid/cmdline" 2>/dev/null || true; echo
fi

echo "inference_listener:"
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | awk '$4 ~ /127\.0\.0\.1:8080$/ {print}' || true
else
  echo "SS_NOT_FOUND"
fi

service_state=/workspace/dorilab/inference/run/service.json
echo "inference_launcher_state:"
if [ -f "$service_state" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$service_state" <<'PY' 2>/dev/null || echo "SERVICE_STATE_INVALID"
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8"))
print("recorded_pid=" + str(value.get("pid", "")))
print("recorded_log=" + str(value.get("log", "")))
print("recorded_started_at=" + str(value.get("started_at", "")))
PY
else
  echo "SERVICE_STATE_NOT_FOUND"
fi

echo "inference_log_tail:"
service_log=
if [ -f "$service_state" ] && command -v python3 >/dev/null 2>&1; then
  service_log=$(python3 - "$service_state" <<'PY' 2>/dev/null || true
import json, pathlib, sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
candidate = pathlib.Path(str(value.get("log", "")))
root = pathlib.Path("/workspace/dorilab/inference/run")
try:
    resolved = candidate.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
except (OSError, ValueError):
    raise SystemExit(0)
if resolved.is_file() and resolved.name.startswith("server-") and resolved.suffix == ".log":
    print(resolved)
PY
  )
fi
if [ -n "$service_log" ]; then
  tail -n 80 "$service_log" 2>/dev/null || true
else
  echo "SERVICE_LOG_NOT_FOUND"
fi

echo "approved_area_candidates:"
if [ -d /workspace/dorilab ]; then
  find /workspace/dorilab -maxdepth 6 -type f \
    \( -name ADAPTER_SAVED.json -o -name ADAPTER_RELOADED.json -o -name CHECKPOINT_HASHES -o \
       -name DEPLOYMENT_MANIFEST.json -o -name MODEL_PROFILE_RC3_DEPLOYED.json -o \
       -name model_profile.json -o -name service.env \) \
    -print 2>/dev/null | sort | sed -n '1,100p'
else
  echo "DORILAB_APPROVED_AREA_NOT_FOUND"
fi

echo "runtime_candidates:"
for candidate in /root/venvs/*/bin/python /workspace/dorilab/runtime/bin/python; do
  [ -x "$candidate" ] || continue
  "$candidate" -c 'import sys; print(sys.executable, sys.version.split()[0])' 2>/dev/null || true
done

service_root=/workspace/dorilab/services/inference
token_path=
if [ -f /root/.config/dorilab/inference.token ]; then
  token_path=/root/.config/dorilab/inference.token
elif [ -f "$service_root/secrets/service_token" ]; then
  token_path="$service_root/secrets/service_token"
fi

if [ -n "$token_path" ]; then
  printf 'service_token_location='; printf '%s\n' "$token_path"
  if command -v stat >/dev/null 2>&1; then
    printf 'service_token_mode='; stat -c '%a' "$token_path" 2>/dev/null || true
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    printf 'service_token_sha256='; sha256sum "$token_path" | awk '{print $1}'
  fi
  echo "installed_service_receipt:"
  if command -v python3 >/dev/null 2>&1; then
    if receipt=$(python3 - "$token_path" 2>/dev/null <<'PY'
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
    ); then
      echo "DORILAB_INSTALLED_SERVICE=READY"
      printf '%s\n' "$receipt"
    else
      echo "DORILAB_INSTALLED_SERVICE=NOT_READY"
    fi
  fi
fi

echo "service_files:"
if [ -d /workspace/dorilab ]; then
  find /workspace/dorilab -maxdepth 7 -type f \
    \( -name API_CONTRACT.md -o -name 'client.py' -o -name 'fetch_token.sh' -o \
       -name 'system_allowlist.json' -o -name 'model_receipt.json' -o \
       -name 'service_manifest.json' -o -name 'deployment_manifest.json' \) \
    -print 2>/dev/null | sort | sed -n '1,100p'
else
  echo "DORILAB_APPROVED_AREA_NOT_FOUND"
fi

echo "mac_client_files:"
if [ -d /workspace/dorilab/inference/mac ]; then
  find /workspace/dorilab/inference/mac -maxdepth 3 -type f -printf '%p %s bytes\n' 2>/dev/null | sort | sed -n '1,100p'
else
  echo "MAC_CLIENT_DIRECTORY_NOT_FOUND"
fi
