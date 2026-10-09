from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path("/app")


@pytest.mark.parametrize("remote_token,mode", [
    ("b" * 64, "live"),
    ("a" * 64, "live"),
    (None, "live"),
    ("b" * 64, "demo"),
])
def test_up_syncs_existing_remote_credential_only_over_verified_ssh_and_preserves_app_startup(tmp_path, remote_token, mode):
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    dev = scripts / "dev.sh"
    dev.write_bytes((ROOT / "scripts/dev.sh").read_bytes())
    secret_dir = project / ".secrets"
    secret_dir.mkdir()
    for name in ("db_password", "app_session_key", "inference_token"):
        (secret_dir / name).write_text("a" * 64 + "\n")
    (secret_dir / "known_hosts").write_text("synthetic verified host\n")
    token_file = secret_dir / "inference_token"
    original_inode = token_file.stat().st_ino
    identity = project / "identity"
    identity.write_text("synthetic SSH identity; not a private key")
    (project / ".env").write_text("RUNPOD_HOST=pod.example.test\nRUNPOD_SSH_PORT=22001\n")
    (project / ".env.derived").write_text(f"DORILAB_SSH_KEY_PATH={identity}\nDORILAB_APP_PORT=18000\n")
    remote_file = tmp_path / "remote.token"
    if remote_token:
        remote_file.write_text(remote_token + "\n")
    trace = tmp_path / "calls"
    tools = tmp_path / "tools"
    tools.mkdir()
    stub = '''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["DORILAB_TEST_CALLS"], "a") as output:
    output.write(json.dumps([name, *args]) + "\\n")
if name == "docker":
    if args[:2] == ["info", "--format"]:
        print("Docker Desktop")
    elif "ps" in args:
        print("dorilab-llm-tunnel-1 running")
    elif "dorilab.remote_status" in args:
        print('{"state":"READY"}')
elif name == "ssh":
    assert "StrictHostKeyChecking=yes" in args
    assert "ForwardAgent=no" in args
    assert "root@pod.example.test" in args
    assert args[-1] == "test -f /root/.config/dorilab/inference.token && test -r /root/.config/dorilab/inference.token && cat /root/.config/dorilab/inference.token"
    remote = pathlib.Path(os.environ["DORILAB_TEST_REMOTE_TOKEN"])
    if not remote.exists():
        sys.exit(1)
    sys.stdout.write(remote.read_text())
'''
    for name in ("docker", "ssh", "ssh-keygen", "curl", "lsof"):
        path = tools / name
        path.write_text(stub if name != "lsof" else "#!/bin/sh\nexit 1\n")
        path.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if not key.startswith("DORILAB_")}
    env.update({
        "PATH": f"{tools}:{os.environ['PATH']}",
        "DORILAB_TEST_CALLS": str(trace),
        "DORILAB_TEST_REMOTE_TOKEN": str(remote_file),
    })
    result = subprocess.run(["bash", str(dev), "up", *(["--demo"] if mode == "demo" else [])],
                            env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    calls = trace.read_text()
    expected_token = remote_token if remote_token and mode == "live" else "a" * 64
    assert token_file.read_text().strip() == expected_token
    assert (token_file.stat().st_mode & 0o777) == 0o600
    assert "a" * 64 not in result.stdout + result.stderr + calls
    assert "b" * 64 not in result.stdout + result.stderr + calls
    assert '"up"' in calls and '"api"' in calls and '"worker"' in calls
    if mode == "live":
        assert '"ssh"' in calls
        assert '"--force-recreate", "worker"' in calls
        assert remote_file.read_text().strip() == remote_token if remote_token else not remote_file.exists()
    else:
        assert '"ssh"' not in calls
    if expected_token == "a" * 64:
        assert token_file.stat().st_ino == original_inode
    if remote_token is None:
        assert "Local app startup continues" in result.stdout
