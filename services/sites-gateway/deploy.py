"""Dedicated gateway deployment, run over already approved strict SSH.

The Mac injects source into SOURCE_B64 before transfer. No model/package/token
changes. Existing different files or listeners stop the operation.
"""
import base64
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import time
import urllib.request

SOURCE_B64 = ""
os.umask(0o077)
source = base64.b64decode(SOURCE_B64, validate=True)
if not source:
    raise SystemExit("SOURCE_REQUIRED")
target = pathlib.Path("/workspace/dorilab/services/sites-gateway")
state = pathlib.Path("/root/.local/state/dorilab-sites-gateway")
token_file = pathlib.Path("/root/.config/dorilab/inference.token")
token = token_file.read_text().strip()
if not token or any(char.isspace() for char in token):
    raise SystemExit("EXISTING_TOKEN_REQUIRED")
def version(port):
    request = urllib.request.Request("http://127.0.0.1:%d/version" % port,
        headers={"Authorization": "Bearer " + token})
    return json.loads(urllib.request.urlopen(request, timeout=8).read())
upstream = version(8080)
if upstream.get("ready") is not True:
    raise SystemExit("UPSTREAM_NOT_READY")
if upstream.get("model_receipt_id") != "b96e72897a27c3a6a0eee4db7c04d55efba10bbd373efe0a83f56221d8a2a847":
    raise SystemExit("MODEL_RELEASE_MISMATCH")
digest = hashlib.sha256(source).hexdigest()
target.mkdir(parents=True, exist_ok=True)
state.mkdir(parents=True, exist_ok=True)
service = target / "server.py"
if service.exists() and hashlib.sha256(service.read_bytes()).hexdigest() != digest:
    raise SystemExit("EXISTING_GATEWAY_SOURCE_DIFFERS")
if not service.exists():
    with service.open("xb") as stream:
        stream.write(source)
pid_file = state / "service.pid"
pid = None
if pid_file.exists():
    candidate = int(pid_file.read_text())
    try:
        os.kill(candidate, 0)
        command = pathlib.Path("/proc/%d/cmdline" % candidate).read_bytes().split(b"\x00")
        if str(service).encode() not in command:
            raise SystemExit("PID_OWNERSHIP_MISMATCH")
        pid = candidate
    except ProcessLookupError:
        pass
if pid is None:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 19124)) == 0:
            raise SystemExit("PORT_ALREADY_IN_USE")
    with (state / "service.log").open("ab") as log:
        process = subprocess.Popen(["/usr/bin/python3", str(service)], stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True, cwd=state)
        pid = process.pid
    pid_file.write_text(str(pid))
ready = None
for _ in range(20):
    try:
        ready = version(19124)
        break
    except OSError:
        time.sleep(0.25)
if ready is None or ready.get("boot_id") != upstream.get("boot_id"):
    raise SystemExit("GATEWAY_READINESS_FAILED")
receipt = {"gateway_pid": pid, "source_sha256": digest, "upstream_boot_id": ready.get("boot_id"),
    "model_receipt_id": ready.get("model_receipt_id"),
    "host_boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "listener": "0.0.0.0:19124", "upstream": "127.0.0.1:8080"}
(state / "receipt.json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
