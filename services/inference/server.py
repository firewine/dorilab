#!/usr/bin/env python3
"""Small authenticated loopback API around an already verified RC3 loader.

This layer deliberately has no torch/transformers dependency. The approved RunPod
runtime supplies a loader module named by DORILAB_LOADER_MODULE. That module must
export load(profile), count_tokens(model, messages), and generate(model, messages,
max_new_tokens). No generic loader fallback is provided.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BOOT_ID = str(uuid.uuid4())
SERVICE_ROOT = Path(os.environ.get("DORILAB_INFERENCE_ROOT", "/workspace/dorilab/services/inference"))
EXPECTED_PROFILE = {
    "profile_id": "dorilab-source-review-v15-rc3",
    "base_model": "Qwen/Qwen3.8-27B",
    "base_revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
    "transformers_commit": "002e1edf5b5198488297f401dd853056b6521d02",
    "adapter_model_sha256": "d90dee59f00f7c987c1b61ae334f928464bfb412ddb26110d692b92b9a46a689",
    "adapter_config_sha256": "d037e965c05ec56ed6069581635ada7f704a6c6331b56831075f127f52f61628",
}
STATE = {"ready": False, "state": "WARMING_UP", "detail": "loader has not completed", "receipt": {}, "model": None}
GENERATIONS: dict[str, dict] = {}
LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="generation")
ACTIVE = False
LOADER = None


def read_token() -> str:
    path = os.environ.get("DORILAB_INFERENCE_TOKEN_FILE", "/workspace/dorilab/services/inference/secrets/service_token")
    return Path(path).read_text(encoding="utf-8").strip()


TOKEN = read_token()


def send_json(handler: BaseHTTPRequestHandler, code: int, body: dict, headers: dict | None = None):
    data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(data)


def authenticated(handler: BaseHTTPRequestHandler) -> bool:
    supplied = handler.headers.get("Authorization", "")
    expected = f"Bearer {TOKEN}"
    if not hmac.compare_digest(supplied, expected):
        send_json(handler, 401, {"error": "unauthorized"})
        return False
    return True


def load_model():
    global LOADER
    try:
        profile_path = Path(os.environ.get("DORILAB_MODEL_PROFILE_FILE", "/workspace/dorilab/services/inference/release/model_profile.json"))
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        for key, expected in EXPECTED_PROFILE.items():
            if profile.get(key) != expected:
                raise RuntimeError(f"approved profile mismatch: {key}")
        unresolved = [key for key in ("contract_id", "template_sha256", "renderer_sha256", "output_schema_sha256") if not profile.get(key)]
        if unresolved:
            raise RuntimeError("unresolved release fields: " + ",".join(unresolved))
        module_name = os.environ.get("DORILAB_LOADER_MODULE")
        if not module_name:
            raise RuntimeError("DORILAB_LOADER_MODULE is not configured")
        LOADER = importlib.import_module(module_name)
        for name in ("load", "count_tokens", "generate", "receipt"):
            if not callable(getattr(LOADER, name, None)):
                raise RuntimeError(f"loader is missing callable {name}")
        model = LOADER.load(profile)
        receipt = LOADER.receipt(model, profile)
        for field in (*EXPECTED_PROFILE, "template_sha256", "renderer_sha256", "output_schema_sha256", "contract_id"):
            if receipt.get(field) != profile.get(field):
                raise RuntimeError(f"release receipt mismatch: {field}")
        expected_runtime = {
            "model_eval": True,
            "gradient_enabled": False,
            "dtype": "bfloat16",
            "attention": "sdpa",
            "do_sample": False,
            "enable_thinking": False,
        }
        for field, expected in expected_runtime.items():
            if receipt.get(field) != expected:
                raise RuntimeError(f"runtime receipt mismatch: {field}")
        smoke = LOADER.generate(model, [{"role": "user", "content": "DoriLab token smoke"}], 1)
        if not isinstance(smoke, dict) or "raw_output" not in smoke:
            raise RuntimeError("token smoke did not return the loader result contract")
        STATE.update(ready=True, state="READY", detail=None, receipt={**receipt, "boot_id": BOOT_ID}, model=model)
        (SERVICE_ROOT / "run" / "version_receipt.json").write_text(
            json.dumps(STATE["receipt"], ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        STATE.update(ready=False, state="MODEL_RELEASE_MISMATCH", detail=str(exc), model=None)


def run_generation(request_id: str, payload: dict):
    global ACTIVE
    started = time.monotonic()
    try:
        result = LOADER.generate(STATE["model"], payload["messages"], payload["max_new_tokens"])
        required = ("raw_output", "raw_output_with_special_tokens", "token_usage", "finish_reason")
        if not isinstance(result, dict) or any(field not in result for field in required):
            raise RuntimeError("loader generation result is missing receipt fields")
        GENERATIONS[request_id].update(
            status="COMPLETED",
            raw_output=result["raw_output"],
            raw_output_with_special_tokens=result.get("raw_output_with_special_tokens"),
            output_token_ids=result.get("output_token_ids"),
            token_usage=result.get("token_usage", {}),
            finish_reason=result.get("finish_reason"),
            generation_seconds=round(time.monotonic() - started, 6),
            receipt=STATE["receipt"],
        )
    except Exception as exc:
        GENERATIONS[request_id].update(status="FAILED", error=type(exc).__name__)
    finally:
        with LOCK:
            ACTIVE = False


class Handler(BaseHTTPRequestHandler):
    server_version = "DoriLabInference/0.1"

    def log_message(self, fmt, *args):
        print(json.dumps({"event": "http", "path": self.path, "status": str(args[1]) if len(args) > 1 else None}))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            send_json(self, 200, {"status": "alive", "boot_id": BOOT_ID})
            return
        if not authenticated(self):
            return
        if path == "/readyz":
            code = 200 if STATE["ready"] else 503
            send_json(self, code, {"state": STATE["state"], "detail": STATE["detail"], "boot_id": BOOT_ID})
            return
        if path == "/version":
            if not STATE["ready"]:
                send_json(self, 503, {"state": STATE["state"], "detail": STATE["detail"], "boot_id": BOOT_ID})
            else:
                send_json(self, 200, STATE["receipt"])
            return
        prefix = "/v1/generations/"
        if path.startswith(prefix):
            request_id = path[len(prefix):]
            result = GENERATIONS.get(request_id)
            send_json(self, 200 if result else 404, result or {"error": "not_found", "boot_id": BOOT_ID})
            return
        send_json(self, 404, {"error": "not_found"})

    def do_POST(self):
        global ACTIVE
        path = urlparse(self.path).path
        if not authenticated(self):
            return
        if path != "/v1/generations":
            send_json(self, 404, {"error": "not_found"})
            return
        if not STATE["ready"]:
            send_json(self, 503, {"state": STATE["state"], "detail": STATE["detail"]})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 * 1024:
                raise ValueError("invalid body size")
            payload = json.loads(self.rfile.read(length))
            required = {"request_id", "attempt_id", "model_profile", "contract_id", "snapshot_sha256", "messages", "max_new_tokens"}
            if set(payload) != required:
                raise ValueError("request fields do not match contract")
            if payload["model_profile"] != STATE["receipt"]["profile_id"]:
                raise ValueError("model profile mismatch")
            if payload["contract_id"] != STATE["receipt"]["contract_id"]:
                raise ValueError("contract mismatch")
            if not isinstance(payload["messages"], list) or not payload["messages"]:
                raise ValueError("messages required")
            max_new = int(payload["max_new_tokens"])
            if max_new < 1 or max_new > 384:
                raise ValueError("max_new_tokens exceeds release limit")
            prompt_tokens = int(LOADER.count_tokens(STATE["model"], payload["messages"]))
            if prompt_tokens + max_new > 4096:
                send_json(self, 422, {"error": "TOKEN_BUDGET_EXCEEDED", "prompt_tokens": prompt_tokens})
                return
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            send_json(self, 422, {"error": "INVALID_REQUEST", "detail": str(exc)})
            return
        request_id = payload["request_id"]
        with LOCK:
            existing = GENERATIONS.get(request_id)
            request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if existing:
                if existing["request_hash"] != request_hash:
                    send_json(self, 409, {"error": "REQUEST_ID_CONFLICT"})
                else:
                    send_json(self, 202, {"request_id": request_id, "boot_id": BOOT_ID, "status": existing["status"]})
                return
            if ACTIVE:
                send_json(self, 429, {"error": "SERVICE_BUSY"}, {"Retry-After": "2"})
                return
            ACTIVE = True
            GENERATIONS[request_id] = {
                "request_id": request_id,
                "attempt_id": payload["attempt_id"],
                "boot_id": BOOT_ID,
                "status": "RUNNING",
                "request_hash": request_hash,
            }
            EXECUTOR.submit(run_generation, request_id, payload)
        send_json(self, 202, {"request_id": request_id, "boot_id": BOOT_ID, "status": "RUNNING"})


def main():
    (SERVICE_ROOT / "run").mkdir(parents=True, exist_ok=True)
    (SERVICE_ROOT / "run" / "boot_id").write_text(BOOT_ID + "\n", encoding="utf-8")
    threading.Thread(target=load_model, daemon=True, name="model-loader").start()
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("DORILAB_INFERENCE_PORT", "8080"))), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
