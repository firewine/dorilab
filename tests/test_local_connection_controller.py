from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

import pytest


@pytest.mark.parametrize("failure,expected", [
    ("", "APPLIED"), ("missing-token", "SERVICE_NOT_DEPLOYED"),
    ("auth", "SSH_AUTH_FAILED"), ("host-key", "HOST_KEY_CONFIRMATION_REQUIRED"),
    ("busy", "CONNECTION_CHANGE_BUSY"), ("changed-settings", "CONNECTION_SETTINGS_CHANGED"),
])
def test_explicit_apply_uses_saved_target_without_redeploy_or_duplicate_generation(tmp_path, failure, expected):
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    for name in ("dev.sh", "local-connection.sh"):
        (project / "scripts" / name).write_bytes((Path("/app/scripts") / name).read_bytes())
    secrets = project / ".secrets"
    secrets.mkdir()
    original_token = "a" * 64 + "\n"
    for name in ("db_password", "app_session_key", "inference_token"):
        (secrets / name).write_text(original_token)
    (secrets / "known_hosts").write_text("synthetic verified host\n")
    identity = project / "synthetic-key"
    identity.write_text("fixture; not a private key")
    (project / ".env").write_text("DORILAB_MODE=DEMO\n")
    (project / ".env.derived").write_text(f"DORILAB_SSH_KEY_PATH={identity}\n"
                                          f"DORILAB_KNOWN_HOSTS_PATH={secrets / 'known_hosts'}\n"
                                          "DORILAB_SSH_USER=root\nDORILAB_APP_PORT=18000\nDORILAB_SSH_USE_AGENT=0\n")
    folder = project / "var/connection/control"
    folder.mkdir(parents=True)
    (folder.parent / "runpod.env").write_text("RUNPOD_HOST=pod.example.test\nRUNPOD_SSH_PORT=22001\n")
    request_id = "b" * 32
    host = "changed.example.test" if failure == "changed-settings" else "pod.example.test"
    (folder / "request.env").write_text(f"REQUEST_ID={request_id}\nRUNPOD_HOST={host}\n"
                                        f"RUNPOD_SSH_PORT=22001\nREQUESTED_AT={int(time.time())}\n")
    trace = tmp_path / "calls"
    tools = tmp_path / "tools"
    tools.mkdir()
    stub = '''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CONNECTION_TEST_TRACE"], "a") as output:
    output.write(json.dumps([name, *args]) + "\\n")
failure = os.environ["CONNECTION_TEST_FAILURE"]
if name == "docker":
    if args[:2] == ["info", "--format"]: print("Docker Desktop")
    if "psql" in args: print("1" if failure == "busy" else "0")
elif name == "ssh":
    assert "StrictHostKeyChecking=yes" in args
    assert "ForwardAgent=no" in args and "-A" not in args
    assert "22001" in args and "root@pod.example.test" in args
    if failure == "auth":
        print("Permission denied (publickey)", file=sys.stderr); sys.exit(1)
    if args[-1] != "true":
        if failure == "missing-token": sys.exit(1)
        print("c" * 64)
elif name == "ssh-keygen" and failure == "host-key": sys.exit(1)
'''
    for name in ("docker", "ssh", "ssh-keygen"):
        path = tools / name
        path.write_text(stub)
        path.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("DORILAB_")}
    env.update({"PATH": f"{tools}:{env['PATH']}", "CONNECTION_TEST_TRACE": str(trace), "CONNECTION_TEST_FAILURE": failure})
    command = ["bash", str(project / "scripts/local-connection.sh"), "apply"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    fields = dict(line.split("=", 1) for line in (folder / "status.env").read_text().splitlines())
    assert fields["CODE"] == expected
    calls = trace.read_text() if trace.exists() else ""
    assert "a" * 64 not in result.stdout + result.stderr + calls
    assert "c" * 64 not in result.stdout + result.stderr + calls
    if expected in {"APPLIED", "SERVICE_NOT_DEPLOYED"}:
        assert fields["PHASE"] == "APPLIED"
        assert (secrets / "last_mode").read_text().strip() == "live"
        operations = [json.loads(line) for line in calls.splitlines()]
        updates = [call for call in operations if call[0] == "docker" and "up" in call]
        assert len(updates) == 3
        assert all("--no-deps" in call and "compose.live.yaml" in call for call in updates)
        assert all(not any(value in call for value in ("build", "down", "migrate", "--build", "--volumes")) for call in updates)
        assert (secrets / "inference_token").read_text() == (original_token if failure else "c" * 64 + "\n")
    else:
        assert fields["PHASE"] == "FAILED"
        assert '"up"' not in calls
        assert (secrets / "inference_token").read_text() == original_token
    assert not any(value in result.stdout + result.stderr + calls for value in ("/v1/generations", "deploy-runpod", "StrictHostKeyChecking=no"))
    repeated = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    assert repeated.returncode == 0
    assert (trace.read_text() if trace.exists() else "") == calls


def test_mac_controller_is_owned_by_launchd_and_stop_removes_only_its_job(tmp_path):
    project = tmp_path / "project with spaces"
    (project / "scripts").mkdir(parents=True)
    for name in ("dev.sh", "local-connection.sh"):
        (project / "scripts" / name).write_bytes((Path("/app/scripts") / name).read_bytes())
    (project / ".secrets").mkdir()
    (project / "var/run-records").mkdir(parents=True)
    tools = tmp_path / "tools"
    tools.mkdir()
    trace = tmp_path / "calls"
    (tools / "uname").write_text("#!/bin/sh\nprintf 'Darwin\\n'\n")
    (tools / "launchctl").write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ["CONNECTION_TEST_TRACE"],"a") as out:
    out.write(json.dumps(sys.argv[1:])+"\\n")
''')
    for path in tools.iterdir():
        path.chmod(0o755)
    env = {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "CONNECTION_TEST_TRACE": str(trace)}
    result = subprocess.run(["bash", "-c", 'source "$1"; start_local_controller; stop_local_controller',
                             "bash", str(project / "scripts/dev.sh")], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    submit = next(row for row in calls if row[0] == "submit")
    label = submit[submit.index("-l")+1]
    assert label.startswith("org.dorilab.local-connection.")
    assert str(project / "scripts/local-connection.sh") in submit
    assert submit[-1] == "watch"
    assert calls[-1] == ["remove", label]
    assert not any(value in " ".join(submit) for value in ("bootstrap", "id_ed25519", "inference_token", "sudo"))
