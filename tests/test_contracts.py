import json

import httpx
import pytest

from dorilab.contracts import LIVE_CONTRACT, LIVE_CONTRACT_ROUTE, canonical, render_live, scope_decision
from dorilab.db import one
from dorilab.validation import validate_output
from dorilab.worker import PROFILE_PATH, _remote_token_usage, _verify_receipt, live_output, refresh_remote_state


def test_reference_and_observation_scope_are_distinct():
    claim = {"unit": "U1", "configuration": "C1", "run": "R1"}
    reference = {
        "kind": "REFERENCE", "rights_status": "PUBLIC", "edition": "1", "adopted": True,
        "applicability_status": "APPLICABLE", "scope": {}, "quote": "Synthetic source span.",
    }
    assert scope_decision(claim, reference) == (True, None)
    observation = {**reference, "kind": "OBSERVATION", "scope": {"unit": "U1", "configuration": "C1", "run": "OTHER"}}
    assert scope_decision(claim, observation) == (False, "OBSERVATION_RUN_MISMATCH")


def test_invalid_json_and_unprovided_reference_are_rejected_without_repair():
    parsed, errors = validate_output("not-json", set())
    assert parsed is None and errors[0].startswith("INVALID_JSON")
    raw = '{"actions":[{"action":"NO_ACTION_REQUIRED","reason_code":"EVIDENCE_SUFFICIENT","reason":"x","evidence_refs":["foreign"],"requested_items":[]}]}'
    parsed, errors = validate_output(raw, {"allowed"})
    assert parsed["actions"][0]["evidence_refs"] == ["foreign"]
    assert "actions[0]:UNPROVIDED_EVIDENCE_REF" in errors


def test_live_receipt_requires_exact_release_and_resolved_contract_hashes():
    receipt = {
        "ready": True,
        "model_receipt_id": "wrong-receipt",
        "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
        "limits": {"max_total_tokens": 4096, "max_new_tokens": 384},
    }
    errors = _verify_receipt(receipt)
    assert "model_receipt_id_MISMATCH" in errors
    assert "contract_id_MISMATCH" not in errors


@pytest.mark.parametrize("unexpected_receipt_id", [
    "b96e72897a27c3a6a0eee4db7c04d55efba10bbd373efe0a83f56221d8a2a847",
    "0" * 64,
])
def test_candidate_runtime_keeps_exact_gate_after_explicit_registration(unexpected_receipt_id, tmp_path, monkeypatch):
    profile = json.loads(PROFILE_PATH.read_text())
    # Exercise a candidate registration only in this isolated test process.
    # The actual approved profile is not changed by candidate verification.
    candidate_id = "7e8f301cdbe9511d4e6b108a3b8bc8ae7330b59a59b7d3dfcb69296c66bb4f0a"
    profile["model_receipt_id"] = candidate_id
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(profile))
    monkeypatch.setattr("dorilab.worker.PROFILE_PATH", candidate_path)
    receipt = {
        "ready": True, "model_receipt_id": profile["model_receipt_id"],
        "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
        "limits": {"max_total_tokens": 4096, "max_new_tokens": 384},
    }
    assert _verify_receipt(receipt) == []
    receipt["model_receipt_id"] = unexpected_receipt_id
    assert _verify_receipt(receipt) == ["model_receipt_id_MISMATCH"]


def test_remote_token_usage_preserves_output_reservation():
    usage = _remote_token_usage({
        "input_tokens": 963,
        "generated_tokens": 46,
        "reserved_output_tokens": 384,
        "max_new_tokens": 128,
    })
    assert usage == {
        "input_tokens": 963,
        "generated_tokens": 46,
        "reserved_new_tokens": 384,
    }


def test_mock_remote_api_failure_is_explicit_and_never_simulated(monkeypatch):
    class OfflineClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("synthetic offline endpoint")

    monkeypatch.setattr("dorilab.worker.httpx.Client", OfflineClient)
    with pytest.raises(RuntimeError, match="SERVICE_NOT_DEPLOYED"):
        packet = canonical({"claim_id": "SYNTHETIC"}).decode()
        live_output({"contract_id": LIVE_CONTRACT, "messages": [{"role": "user", "content": packet}]})
    state = one("SELECT value FROM system_state WHERE key='remote_status'")
    assert state["value"]["state"] == "SERVICE_NOT_DEPLOYED"


def test_periodic_remote_probe_checks_authenticated_ready_and_version(monkeypatch):
    approved_profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    receipt = {
        "service": "DoriLab RC3",
        "ready": True,
        "model_receipt_id": approved_profile["model_receipt_id"],
        "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
        "limits": {"max_total_tokens": 4096, "max_new_tokens": 384},
        "boot_id": "synthetic-boot-id",
    }

    class Response:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

        def raise_for_status(self):
            return None

    class ReadyClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, **kwargs):
            if url.endswith("/readyz"):
                assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
                return Response({"state": "READY"})
            assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
            return Response(receipt)

    monkeypatch.setattr("dorilab.worker.httpx.Client", ReadyClient)
    monkeypatch.setattr("dorilab.worker.inference_token", lambda: "test-token")
    result = refresh_remote_state()
    assert result["state"] == "READY"
    saved = one("SELECT value FROM system_state WHERE key='remote_status'")
    assert saved["value"]["state"] == "READY"
    assert saved["value"]["receipt"]["boot_id"] == "synthetic-boot-id"


def test_periodic_remote_probe_keeps_worker_alive_on_connection_reset(monkeypatch):
    class ResetClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, *_args, **_kwargs):
            raise httpx.ReadError("synthetic tunnel reset")

    monkeypatch.setattr("dorilab.worker.httpx.Client", ResetClient)
    result = refresh_remote_state()
    assert result["state"] == "SERVICE_NOT_DEPLOYED"
    saved = one("SELECT value FROM system_state WHERE key='remote_status'")
    assert saved["value"]["state"] == "SERVICE_NOT_DEPLOYED"


@pytest.mark.parametrize("auth_status", [401, 403])
def test_remote_service_auth_failure_is_distinct_from_model_mismatch_and_blocks_generation(monkeypatch, auth_status):
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/readyz":
            return httpx.Response(200, json={"state": "READY"})
        assert request.url.path == "/version"
        return httpx.Response(auth_status, json={"detail": "credential rejected"})

    client_type = httpx.Client
    monkeypatch.setattr("dorilab.worker.httpx.Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setattr("dorilab.worker.inference_token", lambda: "synthetic-local-credential")
    result = refresh_remote_state()
    assert result == {"state": "INFERENCE_AUTH_FAILED", "http_status": auth_status}
    saved = one("SELECT value FROM system_state WHERE key='remote_status'")["value"]
    assert saved["state"] == "INFERENCE_AUTH_FAILED"
    assert saved["detail"] == f"HTTP {auth_status}"
    assert "synthetic-local-credential" not in json.dumps(saved)

    with pytest.raises(RuntimeError, match="^INFERENCE_AUTH_FAILED$"):
        live_output({"contract_id": LIVE_CONTRACT, "messages": [{"role": "user", "content": canonical({"claim_id": "SYNTHETIC"}).decode()}]})
    assert calls == [("GET", "/readyz"), ("GET", "/version"), ("GET", "/version")]


def test_generation_auth_rejection_is_not_misreported_as_model_mismatch(monkeypatch):
    profile = json.loads(PROFILE_PATH.read_text())
    receipt = {
        "ready": True,
        "model_receipt_id": profile["model_receipt_id"],
        "contracts": [{"id": LIVE_CONTRACT, "route": LIVE_CONTRACT_ROUTE, "system_sha256": LIVE_CONTRACT}],
        "limits": {"max_total_tokens": 4096, "max_new_tokens": 384},
    }
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/version":
            return httpx.Response(200, json=receipt)
        assert request.method == "POST" and request.url.path == "/v1/generations"
        return httpx.Response(403, json={"detail": "credential changed"})

    client_type = httpx.Client
    monkeypatch.setattr("dorilab.worker.httpx.Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setattr("dorilab.worker.inference_token", lambda: "synthetic-local-credential")
    with pytest.raises(RuntimeError, match="^INFERENCE_AUTH_FAILED$"):
        live_output({"id": "synthetic-job", "contract_id": LIVE_CONTRACT, "messages": [{"role": "user", "content": canonical({"claim_id": "SYNTHETIC"}).decode()}]})
    assert calls == [("GET", "/version"), ("POST", "/v1/generations")]
    assert one("SELECT value FROM system_state WHERE key='remote_status'")["value"]["state"] == "INFERENCE_AUTH_FAILED"


def test_live_renderer_uses_one_native_user_packet_without_gold_or_system_message():
    claim = {
        "display_id": "THM-041",
        "question": "현재 범위의 자료가 충분한가?",
        "review_purpose": "INPUT_READINESS",
        "scope": {"unit": "U1", "configuration": "C1", "run": "R1"},
    }
    evidence = [{
        "id": "00000000-0000-4000-8000-000000000099",
        "display_id": "OBS-1",
        "kind": "OBSERVATION",
        "basis": "SYNTHETIC",
        "scope": claim["scope"],
        "quote": "Synthetic observation.",
        "locator": None,
    }]
    messages = render_live(claim, evidence)
    assert [message["role"] for message in messages] == ["user"]
    packet = json.loads(messages[0]["content"])
    assert packet["claim_id"] == "THM-041"
    assert packet["review_target"]["kind"] == "INPUT_READINESS"
    assert packet["observations"][0]["evidence_id"] == evidence[0]["id"]
    forbidden = {"gold", "expected", "rationale", "reference_answer", "system", "messages"}
    assert forbidden.isdisjoint(packet)
