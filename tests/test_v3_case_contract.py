from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from dorilab import worker
from dorilab.db import connection

from conftest import sign_in


FIXTURE_PATH = Path("/app/fixtures/v3/sc03_contract.json")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_result(destination: Path, value: dict) -> None:
    """Atomically publish the human-readable contract result without weakening it on failure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _project_counts(project_id: str) -> dict[str, int]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                 (SELECT count(*) FROM context_snapshots WHERE project_id=%s) AS snapshots,
                 (SELECT count(*) FROM review_jobs WHERE project_id=%s) AS jobs,
                 (SELECT count(*) FROM model_runs WHERE project_id=%s) AS model_runs,
                 (SELECT count(*) FROM human_reviews WHERE project_id=%s) AS human_decisions,
                 (SELECT count(*) FROM verification_closures WHERE project_id=%s) AS closures""",
            (project_id,) * 5,
        )
        return dict(cur.fetchone())


def _claim_projection(client, project_id: str, claim_id: str) -> dict:
    response = client.get(f"/api/v1/projects/{project_id}/closure")
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["claims"] if str(item["claim"]["id"]) == claim_id)


def _create_claim(client, headers: dict, project_id: str, fixture: dict, purpose: str) -> dict:
    label = "PERFORMANCE" if purpose == "PRODUCT_PERFORMANCE" else "INPUT"
    question = (
        "SC-03 합성 As-run 입력이 RV-ACC-001 제품 성능 요구를 충족하는가?"
        if purpose == "PRODUCT_PERFORMANCE"
        else "SC-03 합성 원입력이 후속 검토를 위한 입력 근거로 등록되었는가?"
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/claims",
        headers=headers,
        json={
            "display_id": f"SC03-{label}",
            "question": question,
            "review_target": "BM1",
            "scope": fixture["current_mvp_adapter"]["scope"],
            "review_purpose": purpose,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _request_review(client, headers: dict, project_id: str, claim_id: str, evidence_id: str, suffix: str):
    return client.post(
        f"/api/v1/projects/{project_id}/reviews",
        headers={**headers, "Idempotency-Key": f"v3-sc03-{suffix}-{uuid4().hex}"},
        json={
            "claim_id": claim_id,
            "evidence_ids": [evidence_id],
            "mode": "SIMULATED",
        },
    )


def _request_closure(client, headers: dict, claim_id: str):
    return client.post(
        f"/api/v1/claims/{claim_id}/closures",
        headers=headers,
        json={
            "result": "SATISFIED",
            "closure_basis": "COMPLIANCE",
            "note": "SC-03 목적 경계 회귀에서 종결이 생성되지 않아야 한다.",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )


def test_sc03_original_input_is_preserved_while_current_mvp_refuses_performance_judgement(
    client, tmp_path, monkeypatch
):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    adapter = fixture["current_mvp_adapter"]
    original_input_text = _canonical_json(fixture["original_input"])
    original_input_bytes = original_input_text.encode("utf-8")
    configured_result_path = os.getenv("DORILAB_V3_RESULT_FILE")
    result_path = Path(configured_result_path) if configured_result_path else tmp_path / "sc03_contract_result.json"
    remote_call_count = 0

    def reject_remote_model_call(job: dict):
        nonlocal remote_call_count
        remote_call_count += 1
        raise AssertionError(f"SC-03 boundary regression attempted a remote model call for {job['id']}")

    monkeypatch.setattr(worker, "live_output", reject_remote_model_call)
    actual: dict = {
        "current_mvp_boundary_regression": {"status": "RUNNING"},
        "v3_contract_assessment": {
            "met": False,
            "scenario_result": "NOT_EVALUATED",
            "missing_finding_ids": ["F-01", "F-02", "F-03"],
            "finding_domain": "NOT_IMPLEMENTED",
            "blocker_domain": "NOT_IMPLEMENTED",
            "retest_domain": "NOT_IMPLEMENTED",
            "product_performance": "NOT_EVALUATED",
            "assessment_basis": (
                "Repository inspection found no current backend execution for the V3 deterministic "
                "F-01/F-02/F-03, blocker, or partial-retest domains. These are declared support gaps, "
                "not dynamic Finding results produced by this test."
            ),
        },
        "transport_observation": {"remote_call_count": 0},
    }
    result = {
        "schema_id": "dorilab.v3.case-contract-result.v1",
        "case_id": fixture["case_id"],
        "data_class": fixture["data_class"],
        "source": fixture["provenance"],
        "input": fixture["original_input"],
        "expected": {
            "original_v3": fixture["original_expected"],
            "current_mvp_boundary": adapter,
        },
        "actual": actual,
    }

    try:
        assert fixture["case_id"] == "SC-03"
        assert fixture["data_class"] == "SYNTHETIC"
        assert adapter["mode"] == "SIMULATED"
        assert adapter["model_call_expected"] is False
        assert adapter["original_case_coverage_expected"] == "NOT_IMPLEMENTED"

        headers = sign_in(client)
        project_response = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "display_id": f"V3_SC03_{uuid4().hex[:10]}",
                "name": "V3 SC-03 synthetic boundary regression",
                "framework": "ECSS",
                "framework_edition": None,
                "data_policy": "EXTERNAL_SYNTHETIC_ALLOWED",
                "mode": "DEMO",
            },
        )
        assert project_response.status_code == 201, project_response.text
        project_id = str(project_response.json()["id"])

        artifact_response = client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            headers=headers,
            data={
                "rights_status": "PUBLIC",
                "edition": "V3-SC03-1.0.0",
                "adopted": "true",
                "applicability_status": "APPLICABLE",
                "usage_purpose": "OPERATIONAL_EVIDENCE",
            },
            files={"file": ("sc03-original-input.json", original_input_bytes, "application/json")},
        )
        assert artifact_response.status_code == 201, artifact_response.text
        artifact = artifact_response.json()
        assert artifact["sha256"] == hashlib.sha256(original_input_bytes).hexdigest()
        downloaded = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content == original_input_bytes

        evidence_response = client.post(
            f"/api/v1/projects/{project_id}/evidence",
            headers=headers,
            json={
                "artifact_id": artifact["id"],
                "display_id": "SC03-AS-RUN-OBSERVATION",
                "kind": "OBSERVATION",
                "basis": "SYNTHETIC",
                "scope": adapter["scope"],
                "locator": "freshState.inputs",
                "quote": original_input_text,
                "provenance": {"case_id": fixture["case_id"], "data_class": fixture["data_class"]},
            },
        )
        assert evidence_response.status_code == 201, evidence_response.text
        evidence = evidence_response.json()
        actual["registered_input"] = {
            "artifact_id": str(artifact["id"]),
            "artifact_sha256": artifact["sha256"],
            "artifact_byte_size": artifact["byte_size"],
            "evidence_id": str(evidence["id"]),
            "evidence_kind": evidence["kind"],
        }

        performance_claim = _create_claim(
            client, headers, project_id, fixture, "PRODUCT_PERFORMANCE"
        )
        performance_review = _request_review(
            client,
            headers,
            project_id,
            str(performance_claim["id"]),
            str(evidence["id"]),
            "performance",
        )
        assert performance_review.status_code == 409, performance_review.text
        performance_detail = performance_review.json()["detail"]
        assert "PERFORMANCE_ASSESSMENT_UNSUPPORTED" in performance_detail
        assert "PRODUCT_PERFORMANCE" in performance_detail

        performance_closure_attempt = _request_closure(
            client, headers, str(performance_claim["id"])
        )
        assert performance_closure_attempt.status_code == 409, performance_closure_attempt.text
        assert "PERFORMANCE_ASSESSMENT_UNSUPPORTED" in performance_closure_attempt.json()["detail"]

        performance_projection = _claim_projection(
            client, project_id, str(performance_claim["id"])
        )
        performance_scope = performance_projection["assessment_scope"]
        counts_after_performance = _project_counts(project_id)
        actual["product_performance_guard"] = {
            "review_status_code": performance_review.status_code,
            "error": performance_detail,
            "assessment_scope": performance_scope,
            "ready_for_satisfied": performance_projection["ready_for_satisfied"],
            "current_closure": performance_projection["current_closure"],
            "side_effect_counts": counts_after_performance,
        }
        assert performance_scope["review_purpose"] == "PRODUCT_PERFORMANCE"
        assert performance_scope["supported"] is False
        assert performance_scope["status"] == adapter["performance_review_expected"]
        assert performance_scope["product_performance_status"] == "NOT_EVALUATED"
        assert performance_projection["ready_for_satisfied"] is False
        assert performance_projection["current_closure"] is None
        assert counts_after_performance == {
            "snapshots": 0,
            "jobs": 0,
            "model_runs": 0,
            "human_decisions": 0,
            "closures": 0,
        }

        input_claim = _create_claim(client, headers, project_id, fixture, "INPUT_READINESS")
        input_review = _request_review(
            client,
            headers,
            project_id,
            str(input_claim["id"]),
            str(evidence["id"]),
            "input-readiness",
        )
        assert input_review.status_code == 202, input_review.text
        assert input_review.json()["excluded_evidence"] == []
        assert worker.run_one() is True

        job_id = str(input_review.json()["job_id"])
        job_response = client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200, job_response.text
        job = job_response.json()
        raw_artifact_id = str(job["model_run"]["raw_artifact_id"])
        raw_response = client.get(f"/api/v1/artifacts/{raw_artifact_id}/download")
        assert raw_response.status_code == 200, raw_response.text
        raw_text = raw_response.content.decode("utf-8")
        raw_sha256 = hashlib.sha256(raw_response.content).hexdigest()
        assert raw_sha256 == job["model_run"]["raw_sha256"]
        assert json.loads(raw_text) == job["model_run"]["parsed_output"]
        scope = job["assessment_scope"]
        action = job["model_run"]["parsed_output"]["actions"][0]
        user_packet = json.loads(job["snapshot"]["messages"][1]["content"])
        assert user_packet["evidence"][0]["quote"] == original_input_text
        assert user_packet["evidence"][0]["scope"] == adapter["scope"]
        packet_text = _canonical_json(user_packet)
        assert "original_expected" not in packet_text
        assert "human_decision" not in packet_text
        assert all(finding["id"] not in packet_text for finding in fixture["original_expected"]["findings"])

        assert job["job"]["mode"] == "SIMULATED"
        assert job["job"]["status"] == "AWAITING_REVIEW"
        assert job["model_run"]["validation_status"] == "VALID"
        assert action["action"] == adapter["input_readiness_expected_action"]
        assert job["model_run"]["receipt"]["basis"] == "SYNTHETIC"
        assert job["model_run"]["receipt"]["execution_mode"] == "SIMULATED"
        assert scope["review_purpose"] == "INPUT_READINESS"
        assert scope["supported"] is True
        assert scope["status"] == "SUPPORTED"
        assert scope["product_performance_status"] == adapter["product_performance_status"]
        assert "제품 성능 요구 충족은 판단하지 않습니다" in scope["result_scope"]

        input_closure_attempt = _request_closure(client, headers, str(input_claim["id"]))
        assert input_closure_attempt.status_code == 409, input_closure_attempt.text
        input_projection = _claim_projection(client, project_id, str(input_claim["id"]))
        checks = {item["code"]: item["satisfied"] for item in input_projection["checks"]}
        final_counts = _project_counts(project_id)
        actual["input_readiness_guard"] = {
            "review_status_code": input_review.status_code,
            "job_id": job_id,
            "job_status": job["job"]["status"],
            "validation_status": job["model_run"]["validation_status"],
            "action": action["action"],
            "action_origin": adapter["input_readiness_action_origin"],
            "simulated_raw_output": {
                "artifact_id": raw_artifact_id,
                "text": raw_text,
                "sha256": raw_sha256,
                "receipt": job["model_run"]["receipt"],
            },
            "assessment_scope": scope,
            "closure_checks": checks,
            "ready_for_satisfied": input_projection["ready_for_satisfied"],
            "current_closure": input_projection["current_closure"],
            "side_effect_counts": final_counts,
            "model_accuracy_assessed": False,
        }
        assert checks["CURRENT_EVIDENCE"] is True
        assert checks["VALID_RESULT"] is True
        assert checks["RULE_JUDGEMENT"] is True
        assert checks["HUMAN_REVIEW_ACCEPTED"] is False
        assert input_projection["ready_for_satisfied"] is False
        assert input_projection["current_closure"] is None
        assert final_counts == {
            "snapshots": 1,
            "jobs": 1,
            "model_runs": 1,
            "human_decisions": 0,
            "closures": 0,
        }
        assert remote_call_count == 0

        actual["transport_observation"]["remote_call_count"] = remote_call_count
        actual["current_mvp_boundary_regression"]["status"] = "PASSED"
    except Exception as exc:
        actual["current_mvp_boundary_regression"]["status"] = "FAILED"
        actual["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        actual["transport_observation"]["remote_call_count"] = remote_call_count
        _write_result(result_path, result)
