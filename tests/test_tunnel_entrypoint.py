from __future__ import annotations

import os
from pathlib import Path
import subprocess


ENTRYPOINT = Path("/app/services/llm-tunnel/entrypoint.sh")


def test_mock_ssh_receives_strict_forwarding_arguments_and_rejects_injection(tmp_path):
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    fake_ssh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "RUNPOD_HOST": "pod.example.test",
        "RUNPOD_SSH_PORT": "22001",
        "DORILAB_SSH_USER": "root",
        "DORILAB_REMOTE_INFERENCE_PORT": "8080",
        "DORILAB_SSH_USE_AGENT": "1",
    }
    forwarded = subprocess.run(["bash", str(ENTRYPOINT)], env=env, text=True, capture_output=True, check=True)
    args = forwarded.stdout.splitlines()
    assert "0.0.0.0:18080:127.0.0.1:8080" in args
    assert "StrictHostKeyChecking=yes" in args
    assert "ServerAliveInterval=60" in args
    assert "ServerAliveCountMax=5" in args
    assert "ForwardAgent=no" in args
    assert args[-1] == "root@pod.example.test"

    rejected = subprocess.run(
        ["bash", str(ENTRYPOINT)],
        env={**env, "RUNPOD_HOST": "pod.example.test -oProxyCommand=bad"},
        text=True,
        capture_output=True,
    )
    assert rejected.returncode == 64
    assert "invalid RUNPOD_HOST" in rejected.stderr
