#!/bin/sh
set -eu

stage=$1
release_dir=$2
target=/workspace/dorilab/services/inference

case "$stage" in /workspace/dorilab/services/.inference-stage-*) ;; *) echo "invalid stage" >&2; exit 64;; esac
case "$release_dir" in /workspace/dorilab/*) ;; *) echo "invalid release locator" >&2; exit 64;; esac
[ -d "$stage" ] || { echo "stage missing" >&2; exit 1; }
[ -d "$release_dir" ] || { echo "approved release locator missing: $release_dir" >&2; exit 2; }
[ -f "$release_dir/service.env" ] || { echo "approved service.env locator is required" >&2; exit 2; }

profile=
for candidate in "$release_dir/model_profile.json" "$release_dir/MODEL_PROFILE_RC3_DEPLOYED.json"; do
  if [ -f "$candidate" ]; then profile=$candidate; break; fi
done
[ -n "$profile" ] || { echo "resolved deployed model profile is required" >&2; exit 2; }

if grep -Eq '"(template_sha256|renderer_sha256|output_schema_sha256)"[[:space:]]*:[[:space:]]*null' "$profile"; then
  echo "release profile contains unresolved contract hashes" >&2
  exit 2
fi

runtime_python=$(sed -n 's/^DORILAB_RUNTIME_PYTHON=//p' "$release_dir/service.env" | sed -n '1p')
loader_module=$(sed -n 's/^DORILAB_LOADER_MODULE=//p' "$release_dir/service.env" | sed -n '1p')
loader_path=$(sed -n 's/^DORILAB_LOADER_PYTHONPATH=//p' "$release_dir/service.env" | sed -n '1p')
case "$runtime_python" in /*) ;; *) echo "invalid runtime python locator" >&2; exit 2;; esac
case "$loader_path" in /*) ;; *) echo "invalid loader pythonpath locator" >&2; exit 2;; esac
case "$loader_module" in *[!A-Za-z0-9_.]*|'') echo "invalid loader module" >&2; exit 2;; esac
[ -x "$runtime_python" ] || { echo "runtime python is not executable" >&2; exit 2; }
[ -d "$loader_path" ] || { echo "loader pythonpath is not a directory" >&2; exit 2; }

if [ -d "$target" ]; then
  if [ -f "$target/server.py" ] && [ -f "$target/run.sh" ] && \
     cmp -s "$target/server.py" "$stage/server.py" && cmp -s "$target/run.sh" "$stage/run.sh"; then
    rm -rf -- "$stage"
    if [ -s "$target/run/server.pid" ] && kill -0 "$(sed -n '1p' "$target/run/server.pid")" 2>/dev/null; then
      echo "identical wrapper already installed and running; service was not restarted"
      exit 0
    fi
    installed_runtime=$(sed -n 's/^DORILAB_RUNTIME_PYTHON=//p' "$target/release/service.env" | sed -n '1p')
    installed_module=$(sed -n 's/^DORILAB_LOADER_MODULE=//p' "$target/release/service.env" | sed -n '1p')
    installed_path=$(sed -n 's/^DORILAB_LOADER_PYTHONPATH=//p' "$target/release/service.env" | sed -n '1p')
    DORILAB_RUNTIME_PYTHON="$installed_runtime" \
    DORILAB_LOADER_MODULE="$installed_module" \
    DORILAB_LOADER_PYTHONPATH="$installed_path" \
    PYTHONPATH="$installed_path" \
      "$target/run.sh"
    echo "identical wrapper was present but stopped; service recovery was started"
    exit 0
  fi
  echo "existing inference service differs; preserving it and refusing overwrite" >&2
  exit 3
fi

mkdir -p "$stage/release" "$stage/secrets" "$stage/run" "$stage/logs"
cp -- "$profile" "$stage/release/model_profile.json"
cp -- "$release_dir/service.env" "$stage/release/service.env"
mv -- "$stage/rc3.json" "$stage/release/design_profile.json"
mv -- "$stage/inference_token" "$stage/secrets/service_token"
chmod 600 "$stage/secrets/service_token" "$stage/release/service.env"
chmod 755 "$stage/run.sh" "$stage/server.py"
mv -- "$stage" "$target"

DORILAB_RUNTIME_PYTHON="$runtime_python" \
DORILAB_LOADER_MODULE="$loader_module" \
DORILAB_LOADER_PYTHONPATH="$loader_path" \
PYTHONPATH="$loader_path" \
  "$target/run.sh"

echo "installed and started wrapper at $target; readiness must still be checked"
