from __future__ import annotations

import time

import pytest

from dorilab import api as api_module, local_connection, worker
from conftest import sign_in
from test_runpod_connection_settings import PROJECT, HOST, PORT, HOST_KEY_LINE, clear_connection_files
from dorilab.config import KNOWN_HOSTS_PATH


@pytest.fixture
def controller(tmp_path, monkeypatch, client):
    clear_connection_files()
    monkeypatch.setenv("DORILAB_LOCAL_CONNECTION_CONTROL", "1")
    monkeypatch.setattr(local_connection, "CONTROL_PATH", tmp_path)
    headers = sign_in(client)
    client.put(f"/api/v1/projects/{PROJECT}/runpod-connection", headers=headers,
               json={"host": HOST, "port": PORT})
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_HOSTS_PATH.write_text(HOST_KEY_LINE + "\n")
    (tmp_path / "heartbeat.env").write_text(f"UPDATED_AT={int(time.time())}\n")
    return tmp_path, headers


def test_demo_save_is_distinct_from_explicit_live_apply_and_deduplicates(client, controller, monkeypatch):
    folder, headers = controller
    path = f"/api/v1/projects/{PROJECT}/runpod-connection"
    before = client.get(path).json()
    assert before["runtime"]["mode"] == "DEMO"
    assert before["runtime"]["remote"]["state"] == "LOCAL_ONLY"
    assert before["controller"]["available"] is True
    assert not (folder / "request.env").exists()
    # The API only writes a validated request; it does not shell out or run a model.
    monkeypatch.setattr(api_module.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("SSH in API")))
    monkeypatch.setattr(api_module, "_host_key_state", lambda *a: "HOST_KEY_VERIFIED")
    first = client.post(path + "/apply", headers=headers, json={"host": HOST, "port": PORT})
    assert first.status_code == 202
    same = client.post(path + "/apply", headers=headers, json={"host": HOST, "port": PORT})
    assert same.status_code == 202
    assert same.json()["request_id"] == first.json()["request_id"]
    assert (folder / "request.env").stat().st_mode & 0o777 == 0o600
    assert worker.claim_job() is None
    edit = client.put(path, headers=headers, json={"host": "other.test", "port": PORT})
    assert edit.status_code == 409
    assert edit.json()["detail"] == "CONNECTION_APPLY_IN_PROGRESS"


def test_apply_requires_member_csrf_fresh_settings_trust_and_local_controller(client, controller):
    folder, headers = controller
    path = f"/api/v1/projects/{PROJECT}/runpod-connection/apply"
    body = {"host": HOST, "port": PORT}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, headers=headers, json={"host": "other.test", "port": PORT}).status_code == 409
    outsider = sign_in(client, "viewer@demo")
    assert client.post(path, headers=outsider, json=body).status_code == 403
    headers = sign_in(client)
    KNOWN_HOSTS_PATH.unlink()
    assert client.post(path, headers=headers, json=body).json()["detail"] == "HOST_KEY_CONFIRMATION_REQUIRED"
    KNOWN_HOSTS_PATH.write_text(HOST_KEY_LINE + "\n")
    (folder / "heartbeat.env").write_text("UPDATED_AT=1\n")
    rejected = client.post(path, headers=headers, json=body)
    assert rejected.status_code == 409
    assert rejected.json()["detail"].startswith("LOCAL_CONNECTOR_NOT_RUNNING")
    assert not (folder / "request.env").exists()


def test_running_or_queued_reviews_block_transport_replacement(client, controller):
    folder, headers = controller
    created = client.post(f"/api/v1/projects/{PROJECT}/reviews", headers={**headers, "Idempotency-Key": "connection-busy-fixture"},
                          json={"claim_id": "00000000-0000-4000-8000-000000000101", "evidence_ids": [], "mode": "SIMULATED"})
    assert created.status_code == 202
    result = client.post(f"/api/v1/projects/{PROJECT}/runpod-connection/apply", headers=headers,
                         json={"host": HOST, "port": PORT})
    assert result.status_code == 409
    assert result.json()["detail"].startswith("CONNECTION_CHANGE_BUSY")
    assert not (folder / "request.env").exists()


def test_apply_result_is_visible_on_reopen_and_does_not_claim_model_ready(client, controller):
    folder, headers = controller
    id_ = local_connection.request_apply(HOST, PORT)
    (folder / "status.env").write_text(f"REQUEST_ID={id_}\nPHASE=APPLIED\nCODE=SERVICE_NOT_DEPLOYED\n"
                                      f"ACTIVE_HOST={HOST}\nACTIVE_PORT={PORT}\nUPDATED_AT=1\n")
    result = client.get(f"/api/v1/projects/{PROJECT}/runpod-connection").json()
    assert result["controller"]["phase"] == "APPLIED"
    assert result["controller"]["pending"] is False
    assert result["controller"]["code"] == "SERVICE_NOT_DEPLOYED"
    assert result["host_key_state"] == "HOST_KEY_VERIFIED"
    assert result["runtime"]["remote"]["state"] == "LOCAL_ONLY"


def test_same_applied_live_configuration_does_not_restart_worker(client, controller, monkeypatch):
    folder, headers = controller
    monkeypatch.setattr(api_module, "APP_MODE", "LIVE")
    id_ = local_connection.request_apply(HOST, PORT)
    (folder / "status.env").write_text(f"REQUEST_ID={id_}\nPHASE=APPLIED\nCODE=APPLIED\n"
                                      f"ACTIVE_HOST={HOST}\nACTIVE_PORT={PORT}\nSSH_STATE=CONNECTED\n")
    worker.set_remote_state("MODEL_RELEASE_MISMATCH", receipt={"ready": True, "boot_id": "restored-boot"})
    before = (folder / "request.env").read_bytes()
    result = client.post(f"/api/v1/projects/{PROJECT}/runpod-connection/apply", headers=headers,
                         json={"host": HOST, "port": PORT})
    assert result.status_code == 202
    assert result.json()["unchanged"] is True
    assert (folder / "request.env").read_bytes() == before


@pytest.mark.parametrize("remote_state", ["INFERENCE_AUTH_FAILED", "SERVICE_NOT_DEPLOYED", "EXPIRED_READY"])
def test_same_address_allows_explicit_recovery_when_authentication_or_probe_is_lost(client, controller, monkeypatch, remote_state):
    from dorilab.db import connection

    folder, headers = controller
    monkeypatch.setattr(api_module, "APP_MODE", "LIVE")
    previous_id = local_connection.request_apply(HOST, PORT)
    (folder / "status.env").write_text(f"REQUEST_ID={previous_id}\nPHASE=APPLIED\nCODE=APPLIED\n"
                                      f"ACTIVE_HOST={HOST}\nACTIVE_PORT={PORT}\nSSH_STATE=CONNECTED\n")
    worker.set_remote_state("READY" if remote_state == "EXPIRED_READY" else remote_state,
                            receipt={"ready": True, "boot_id": "previous-boot"})
    if remote_state == "EXPIRED_READY":
        with connection() as conn:
            conn.execute("UPDATE system_state SET updated_at=now()-interval '1 minute' WHERE key='remote_status'")
    result = client.post(f"/api/v1/projects/{PROJECT}/runpod-connection/apply", headers=headers,
                         json={"host": HOST, "port": PORT})
    assert result.status_code == 202
    assert result.json()["status"] == "REQUESTED"
    assert result.json()["request_id"] != previous_id
    assert local_connection.pending() is True
