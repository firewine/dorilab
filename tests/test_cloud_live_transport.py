"""Cloud transport guards; all model replies are mocks, never LIVE evidence."""
import json
import hashlib
from unittest.mock import patch

import httpx
import pytest

from dorilab import cloud_transport, cloud_worker, worker
from dorilab.contracts import LIVE_CONTRACT, LIVE_CONTRACT_ROUTE, canonical
from dorilab.db import connection, one


ORIGIN = "https://approvedpod-19124.proxy.runpod.net"


@pytest.fixture
def live_settings(monkeypatch, tmp_path):
    token_file = tmp_path / "inference_token"
    token_file.write_text("synthetic-service-credential\n")
    monkeypatch.setenv("DORILAB_MODE", "LIVE")
    monkeypatch.setenv("DORILAB_INFERENCE_URL", ORIGIN)
    monkeypatch.setenv("DORILAB_INFERENCE_TOKEN_FILE", str(token_file))
    monkeypatch.delenv("DORILAB_INFERENCE_TOKEN", raising=False)
    return token_file


def test_demo_needs_no_endpoint_token_or_ssh(monkeypatch):
    monkeypatch.setenv("DORILAB_MODE", "DEMO")
    monkeypatch.delenv("DORILAB_INFERENCE_URL", raising=False)
    monkeypatch.delenv("DORILAB_INFERENCE_TOKEN_FILE", raising=False)
    assert cloud_transport.validate_cloud_mode() == "DEMO"


def test_live_configuration_does_not_contact_gpu(live_settings):
    with patch("httpx.Client") as client:
        assert cloud_transport.validate_cloud_mode() == "LIVE"
        client.assert_not_called()


@pytest.mark.parametrize("origin", [
    "", "http://approvedpod-19124.proxy.runpod.net", "http://llm-tunnel:18080",
    "https://approvedpod-8080.proxy.runpod.net", "https://outside.example",
    ORIGIN + "/path", ORIGIN + "/", ORIGIN + "?token=x", ORIGIN + "#fragment",
    "https://user:password@approvedpod-19124.proxy.runpod.net",
    ORIGIN + ".attacker.example", ORIGIN + "\n",
])
def test_cloud_live_rejects_nonapproved_origin(live_settings, monkeypatch, origin):
    monkeypatch.setenv("DORILAB_INFERENCE_URL", origin)
    with pytest.raises(RuntimeError, match="approved RunPod HTTPS origin"):
        cloud_transport.validate_cloud_mode()


@pytest.mark.parametrize("content", ["", "has embedded whitespace", "\xff"])
def test_cloud_live_rejects_invalid_token_file(live_settings, content):
    live_settings.write_bytes(content.encode("latin-1"))
    with pytest.raises(RuntimeError, match="token file"):
        cloud_transport.validate_cloud_mode()


def test_cloud_live_requires_file_and_refuses_env_token(live_settings, monkeypatch):
    monkeypatch.setenv("DORILAB_INFERENCE_TOKEN", "must-not-be-used")
    with pytest.raises(RuntimeError, match="configured file"):
        cloud_transport.validate_cloud_mode()
    monkeypatch.delenv("DORILAB_INFERENCE_TOKEN")
    live_settings.unlink()
    with pytest.raises(RuntimeError, match="unavailable"):
        cloud_transport.validate_cloud_mode()
    monkeypatch.delenv("DORILAB_INFERENCE_TOKEN_FILE")
    with pytest.raises(RuntimeError, match="requires an inference token file"):
        cloud_transport.validate_cloud_mode()


def test_cloud_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("DORILAB_MODE", "AUTOMATIC")
    with pytest.raises(RuntimeError, match="unsupported"):
        cloud_transport.validate_cloud_mode()


def test_demo_driver_never_probes_or_generates(monkeypatch):
    monkeypatch.setattr(worker, "APP_MODE", "DEMO")
    with patch.object(worker, "refresh_remote_state") as probe, \
         patch.object(worker, "set_remote_state") as state, \
         patch.object(worker, "live_output") as generate:
        cloud_worker.initialize_remote_state()
        probe.assert_not_called()
        generate.assert_not_called()
        assert state.call_args.args[0] == "LOCAL_ONLY"


def test_live_driver_offline_state_keeps_existing_business_reads_available(monkeypatch, client):
    from conftest import sign_in
    monkeypatch.setattr(worker, "APP_MODE", "LIVE")
    original = httpx.Client
    def offline(request):
        raise httpx.ConnectError("synthetic offline GPU", request=request)
    monkeypatch.setattr(worker.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(offline), **kw))
    with patch.object(worker, "live_output") as generate:
        cloud_worker.initialize_remote_state()
        generate.assert_not_called()
    assert one("SELECT value FROM system_state WHERE key='remote_status'")["value"]["state"] == "SERVICE_NOT_DEPLOYED"
    headers = sign_in(client)
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/v1/projects", headers=headers).status_code == 200


def test_https_ready_and_version_both_authenticated_without_redirects(monkeypatch):
    profile = json.loads(worker.PROFILE_PATH.read_text())
    receipt = {"ready": True, "boot_id": "synthetic-boot",
               "model_receipt_id": profile["model_receipt_id"],
               "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
               "limits": {"max_total_tokens": 4096, "max_new_tokens": 384}}
    calls = []
    def handle(request):
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer synthetic-service-credential"
        return httpx.Response(200, json=receipt if request.url.path == "/version" else {"state": "READY"})
    original = httpx.Client
    def make_client(**kw):
        assert kw["follow_redirects"] is False and kw["trust_env"] is False
        return original(transport=httpx.MockTransport(handle), **kw)
    monkeypatch.setattr(worker, "INFERENCE_URL", ORIGIN)
    monkeypatch.setattr(worker, "inference_token", lambda: "synthetic-service-credential")
    monkeypatch.setattr(worker.httpx, "Client", make_client)
    assert worker.refresh_remote_state()["state"] == "READY"
    assert calls == ["/readyz", "/version"]


def test_redirect_never_forwards_token_or_admits_generation(monkeypatch):
    calls = []
    def handle(request):
        calls.append((request.method, str(request.url)))
        return httpx.Response(302, headers={"Location": "https://outside.example/steal"})
    original = httpx.Client
    monkeypatch.setattr(worker, "INFERENCE_URL", ORIGIN)
    monkeypatch.setattr(worker, "inference_token", lambda: "synthetic-service-credential")
    monkeypatch.setattr(worker.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    assert worker.refresh_remote_state()["state"] == "SERVICE_NOT_DEPLOYED"
    with pytest.raises(httpx.HTTPStatusError):
        worker.live_output({"contract_id": LIVE_CONTRACT,
                            "messages": [{"role": "user", "content": canonical({"claim_id": "SYNTHETIC"}).decode()}]})
    assert calls == [("GET", ORIGIN + "/readyz"), ("GET", ORIGIN + "/version")]
    assert "synthetic-service-credential" not in json.dumps(one("SELECT value FROM system_state WHERE key='remote_status'")["value"])


@pytest.mark.parametrize("outcome", ["completed", "invalid_output", "boot_changed"])
def test_mock_https_job_raw_validation_board_and_human_history(client, monkeypatch, outcome):
    from conftest import sign_in
    from dorilab import api
    from test_bm1_flow import PROJECT, CLAIM, add_reference
    headers = sign_in(client)
    evidence = add_reference(client, headers)
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE projects SET data_policy='EXTERNAL_SYNTHETIC_ALLOWED' WHERE id=%s", (PROJECT,))
    monkeypatch.setattr(api, "APP_MODE", "LIVE")
    monkeypatch.setattr(worker, "APP_MODE", "LIVE")
    monkeypatch.setattr(worker, "INFERENCE_URL", ORIGIN)
    monkeypatch.setattr(worker, "inference_token", lambda: "synthetic-service-credential")
    payload = {"claim_id": CLAIM, "evidence_ids": [evidence["id"]], "mode": "LIVE_MODEL_RUN"}
    key = "mock-cloud-live-" + outcome
    created = client.post(f"/api/v1/projects/{PROJECT}/reviews", headers={**headers, "Idempotency-Key": key}, json=payload)
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    repeated = client.post(f"/api/v1/projects/{PROJECT}/reviews", headers={**headers, "Idempotency-Key": key}, json=payload)
    assert repeated.json()["job_id"] == job_id
    conflict = client.post(f"/api/v1/projects/{PROJECT}/reviews", headers={**headers, "Idempotency-Key": key}, json={**payload, "evidence_ids": []})
    assert conflict.status_code == 409

    profile = json.loads(worker.PROFILE_PATH.read_text())
    receipt = {"ready": True, "boot_id": "synthetic-boot", "model_receipt_id": profile["model_receipt_id"],
               "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
               "limits": {"max_total_tokens": 4096, "max_new_tokens": 384}}
    text = canonical({"action": "NO_ACTION_REQUIRED", "claim_id": "THM-041", "evidence_refs": [evidence["id"]]}).decode()
    if outcome == "invalid_output":
        text = "invalid synthetic model JSON"
    raw = text + "<|im_end|>"
    calls = []
    def handle(request):
        calls.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer synthetic-service-credential"
        if request.url.path == "/version":
            return httpx.Response(200, json=receipt)
        if request.method == "POST":
            submitted = json.loads(request.content)
            assert submitted["request_id"] == job_id and submitted["contract_id"] == LIVE_CONTRACT
            assert submitted["max_new_tokens"] == 384
            assert set(submitted) == {"request_id", "contract_id", "user", "max_new_tokens"}
            assert json.loads(submitted["user"])["claim_id"] == "THM-041"
            return httpx.Response(202, json={"id": job_id, "boot_id": "synthetic-boot", "status": "running"})
        return httpx.Response(200, json={"id": job_id, "status": "completed",
            "boot_id": "other-boot" if outcome == "boot_changed" else "synthetic-boot",
            "raw_text": raw, "text": text, "model_receipt_id": profile["model_receipt_id"],
            "input_tokens": 99, "generated_tokens": 20, "reserved_output_tokens": 384,
            "generated_token_ids": [248046], "finish_reason": "eos", "elapsed_seconds": 0.1,
            "output_sha256": hashlib.sha256(raw.encode()).hexdigest(), "execution_mode": "MOCK"})
    original = httpx.Client
    monkeypatch.setattr(worker.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    with patch.object(worker, "simulated_output", side_effect=AssertionError("LIVE cannot fall back")):
        assert worker.run_one()
        assert not worker.run_one()
    assert sum(method == "POST" for method, path in calls) == 1
    result = client.get(f"/api/v1/jobs/{job_id}").json()
    if outcome == "boot_changed":
        assert result["job"]["status"] == "UNKNOWN_OUTCOME"
        assert result["model_run"] is None and result["decisions"] == []
        return
    model = result["model_run"]
    assert model["receipt"]["execution_mode"] == "MOCK"
    assert model["token_usage"]["reserved_new_tokens"] == 384
    assert model["receipt"]["generated_token_ids"] == [248046]
    downloaded = client.get(f"/api/v1/artifacts/{model['raw_artifact_id']}/download")
    assert downloaded.content == raw.encode()
    assert model["raw_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert result["decisions"] == []
    board = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    if outcome == "invalid_output":
        assert result["job"]["status"] == "OUTPUT_REJECTED"
        assert model["validation_status"] == "REJECTED"
        assert model["parsed_output"] is None
        return
    assert result["job"]["status"] == "AWAITING_REVIEW" and model["validation_status"] == "VALID"
    assert any(item["actor_type"] == "MODEL" and item["content"]["action"] == "NO_ACTION_REQUIRED"
               for item in board["contributions"])
    sign_in(client, "reviewer@demo")
    decision = client.post(f"/api/v1/reviews/{job_id}/decisions", headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "REVISION_REQUESTED", "expected_job_version": result["job"]["version"],
              "edited_draft": {"reviewer_text": "MOCK transport review only"}, "note": "No product acceptance"})
    assert decision.status_code == 201, decision.text
    final = client.get(f"/api/v1/jobs/{job_id}").json()
    assert final["model_run"]["raw_sha256"] == model["raw_sha256"]
    assert len(final["decisions"]) == 1 and final["decisions"][0]["edited_draft"] != model["parsed_output"]
