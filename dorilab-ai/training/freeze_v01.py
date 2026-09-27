import hashlib
import json
from pathlib import Path

FILES = {
    "adapter_model":
        Path("adapters/dorilab-common-1p7b-v01/adapter_model.safetensors"),
    "adapter_config":
        Path("adapters/dorilab-common-1p7b-v01/adapter_config.json"),
    "prompt":
        Path("runtime/dorilab_prompts_v01.py"),
    "train_data":
        Path("data/train150_v01.jsonl"),
    "train_manifest":
        Path("data/train150_v01_manifest.json"),
    "eval_manifest":
        Path("eval/eval40_manifest_v1.json"),
}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

manifest = {
    "release": "dorilab-common-1p7b-v0.1",
    "base_model": "Qwen/Qwen3-1.7B",
    "status": "FROZEN_FOR_HOLDOUT_EVALUATION",
    "files": {},
    "dev_result": {
        "exact_pass": "17/20",
        "exact_accuracy": 0.85,
        "action_accuracy": 0.90,
        "json_valid": 1.00,
        "analysis": "5/6",
        "evidence": "7/7",
        "critic": "5/7",
    },
}

for name, path in FILES.items():
    if not path.exists():
        raise FileNotFoundError(path)

    manifest["files"][name] = {
        "path": str(path),
        "sha256": sha256(path),
    }

out = Path("adapters/dorilab-common-1p7b-v01/FROZEN_MANIFEST.json")

out.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(out)
print(json.dumps(manifest, indent=2, ensure_ascii=False))
