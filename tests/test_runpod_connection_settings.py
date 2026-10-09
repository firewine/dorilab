from __future__ import annotations

import hashlib

import dorilab.api as api_module
from dorilab.config import CONNECTION_CONFIG_PATH, KNOWN_HOSTS_PATH

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
HOST = "205.196.144.18"
PORT = 11771
HOST_KEY_LINE = f"[{HOST}]:{PORT} ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeDoriLabTestKey"


def clear_connection_files():
    CONNECTION_CONFIG_PATH.unlink(missing_ok=True)
    KNOWN_HOSTS_PATH.unlink(missing_ok=True)


def test_runpod_connection_is_saved_for_a_project_member(client):
    clear_connection_files()
    engineer_headers = sign_in(client)
    saved = client.put(
        f"/api/v1/projects/{PROJECT}/runpod-connection",
        headers=engineer_headers,
        json={"host": HOST, "port": PORT},
    )
    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert saved.json()["host_key_state"] == "HOST_KEY_CONFIRMATION_REQUIRED"
    assert CONNECTION_CONFIG_PATH.read_text() == f"RUNPOD_HOST={HOST}\nRUNPOD_SSH_PORT={PORT}\n"

    rejected = client.put(
        f"/api/v1/projects/{PROJECT}/runpod-connection",
        headers=engineer_headers,
        json={"host": "example.test -oProxyCommand=bad", "port": PORT},
    )
    assert rejected.status_code == 422


def test_fingerprint_review_and_one_time_host_key_confirmation(client, monkeypatch):
    clear_connection_files()
    headers = sign_in(client, "approver@demo")
    saved = client.put(
        f"/api/v1/projects/{PROJECT}/runpod-connection",
        headers=headers,
        json={"host": HOST, "port": PORT},
    )
    assert saved.status_code == 200
    payload = (HOST_KEY_LINE + "\n").encode()
    scan_sha256 = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        api_module,
        "_scan_runpod_host_key",
        lambda host, port: {
            "lines": [HOST_KEY_LINE],
            "fingerprints": [f"256 SHA256:fixture [{host}]:{port} (ED25519)"],
            "scan_sha256": scan_sha256,
        },
    )

    scan = client.post(
        f"/api/v1/projects/{PROJECT}/runpod-connection/scan-host-key",
        headers=headers,
    )
    assert scan.status_code == 200
    assert scan.json()["host_key_state"] == "HOST_KEY_CONFIRMATION_REQUIRED"
    assert scan.json()["scan_sha256"] == scan_sha256

    confirmed = client.post(
        f"/api/v1/projects/{PROJECT}/runpod-connection/confirm-host-key",
        headers=headers,
        json={"scan_sha256": scan_sha256},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["host_key_state"] == "HOST_KEY_VERIFIED"
    assert HOST_KEY_LINE in KNOWN_HOSTS_PATH.read_text()


def test_changed_host_key_is_not_replaced(client, monkeypatch):
    clear_connection_files()
    headers = sign_in(client, "approver@demo")
    client.put(
        f"/api/v1/projects/{PROJECT}/runpod-connection",
        headers=headers,
        json={"host": HOST, "port": PORT},
    )
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    original = f"[{HOST}]:{PORT} ssh-ed25519 AAAAC3NzaOldStoredKey\n"
    KNOWN_HOSTS_PATH.write_text(original)
    payload = (HOST_KEY_LINE + "\n").encode()
    scan_sha256 = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        api_module,
        "_scan_runpod_host_key",
        lambda host, port: {
            "lines": [HOST_KEY_LINE],
            "fingerprints": ["256 SHA256:new-key (ED25519)"],
            "scan_sha256": scan_sha256,
        },
    )

    scan = client.post(
        f"/api/v1/projects/{PROJECT}/runpod-connection/scan-host-key",
        headers=headers,
    )
    assert scan.json()["host_key_state"] == "HOST_KEY_CHANGED"
    refused = client.post(
        f"/api/v1/projects/{PROJECT}/runpod-connection/confirm-host-key",
        headers=headers,
        json={"scan_sha256": scan_sha256},
    )
    assert refused.status_code == 409
    assert KNOWN_HOSTS_PATH.read_text() == original
