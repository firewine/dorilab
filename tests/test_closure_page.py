from __future__ import annotations

import hashlib

from dorilab.db import connection
from dorilab.worker import run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def add_current_reference(client, headers):
    data = b"synthetic closure reference\n"
    artifact = client.post(
        f"/api/v1/projects/{PROJECT}/artifacts",
        headers=headers,
        data={"rights_status": "PUBLIC", "edition": "DEMO-1", "adopted": "true", "applicability_status": "APPLICABLE"},
        files={"file": ("closure.txt", data, "text/plain")},
    )
    assert artifact.status_code == 201
    assert artifact.json()["sha256"] == hashlib.sha256(data).hexdigest()
    evidence = client.post(
        f"/api/v1/projects/{PROJECT}/evidence",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "artifact_id": artifact.json()["id"],
            "display_id": "CLOSURE-REF",
            "kind": "REFERENCE",
            "basis": "SYNTHETIC",
            "scope": {},
            "locator": "section closure",
            "quote": "synthetic closure reference",
            "provenance": {"fixture": True},
        },
    )
    assert evidence.status_code == 201
    return evidence.json()


def test_verification_closure_is_versioned_and_requires_separate_authority(client):
    engineer_headers = sign_in(client)
    seeded_claim = client.get(f"/api/v1/claims/{CLAIM}")
    assert seeded_claim.status_code == 200, seeded_claim.text
    assert seeded_claim.json()["claim"]["review_purpose"] == "INPUT_READINESS"
    assert seeded_claim.json()["revisions"][0]["review_purpose"] == "INPUT_READINESS"
    requirements = client.get(f"/api/v1/projects/{PROJECT}/requirements")
    assert requirements.status_code == 200, requirements.text
    requirements_by_id = {item["display_id"]: item for item in requirements.json()}
    assert requirements_by_id["THM-041"]["claim_id"] == CLAIM
    assert requirements_by_id["THM-041"]["review_purpose"] == "INPUT_READINESS"
    assert requirements_by_id["THM-042"]["claim_id"] is None
    assert requirements_by_id["THM-042"]["review_purpose"] == "PRODUCT_PERFORMANCE"

    evidence = add_current_reference(client, engineer_headers)
    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**engineer_headers, "Idempotency-Key": "closure-review-0001"},
        json={"claim_id": CLAIM, "evidence_ids": [evidence["id"]], "mode": "SIMULATED"},
    )
    assert review.status_code == 202
    assert run_one() is True
    job_id = review.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assessment_scope = job["assessment_scope"]
    assert assessment_scope == job["snapshot"]["assessment_scope"]
    assert job["snapshot"]["review_purpose"] == "INPUT_READINESS"
    assert assessment_scope["review_purpose"] == "INPUT_READINESS"
    assert assessment_scope["label"]
    assert assessment_scope["result_scope"]
    assert "NO_ACTION_REQUIRED" in assessment_scope["no_action_required_meaning"]
    assert assessment_scope["product_performance_status"] == "NOT_EVALUATED"

    # An input-readiness model run must not advance the separate THM-042
    # product-performance requirement.
    requirements_after_run = client.get(f"/api/v1/projects/{PROJECT}/requirements").json()
    thm_042 = next(item for item in requirements_after_run if item["display_id"] == "THM-042")
    assert thm_042["review_purpose"] == "PRODUCT_PERFORMANCE"
    assert thm_042["ui_status"] == "PERFORMANCE_ASSESSMENT_UNSUPPORTED"

    denied_quality = client.post(
        f"/api/v1/claims/{CLAIM}/quality-assessments",
        headers=engineer_headers,
        json={
            "quality_status": "VALID",
            "note": "권한 경계 확인",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )
    assert denied_quality.status_code == 403

    reviewer_headers = sign_in(client, "reviewer@demo")
    accepted = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "ACCEPTED",
            "expected_job_version": job["job"]["version"],
            "note": "현재 Snapshot과 근거에 한정한 검토 수용",
        },
    )
    assert accepted.status_code == 201
    report_response = client.post(f"/api/v1/jobs/{job_id}/reports", headers=reviewer_headers)
    assert report_response.status_code == 201, report_response.text
    report = client.get(f"/api/v1/reports/{report_response.json()['id']}/download")
    assert report.status_code == 200, report.text
    assert assessment_scope["label"] in report.content.decode("utf-8")

    quality = client.post(
        f"/api/v1/claims/{CLAIM}/quality-assessments",
        headers=reviewer_headers,
        json={
            "quality_status": "VALID",
            "note": "등록된 합성 자료의 추적성과 현재 범위를 확인함",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )
    assert quality.status_code == 201, quality.text

    gates = client.get(f"/api/v1/projects/{PROJECT}/gates").json()
    trb = next(item for item in gates["gates"] if item["gate_key"] == "trb")
    assert trb["ready_for_decision"] is True
    approved = client.post(
        f"/api/v1/gates/{trb['id']}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "APPROVED",
            "note": "현재 기준선의 입력 완전성 검토 결과를 확인함",
            "expected_gate_version": trb["version"],
            "expected_project_version": 1,
        },
    )
    assert approved.status_code == 201

    projection = client.get(f"/api/v1/projects/{PROJECT}/closure").json()
    claim_view = projection["claims"][0]
    assert claim_view["assessment_scope"]["review_purpose"] == "INPUT_READINESS"
    assert claim_view["assessment_scope"]["label"] == assessment_scope["label"]
    assert claim_view["assessment_scope"]["product_performance_status"] == "NOT_EVALUATED"
    assert claim_view["ready_for_satisfied"] is True
    assert claim_view["current_closure"] is None
    assert all(item["satisfied"] for item in claim_view["checks"])

    # A legacy mixed-purpose link must not be hidden by one matching input
    # requirement.  The model result remains valid for input readiness, but
    # closure is blocked until every linked Requirement has the same explicit
    # purpose.
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE requirements SET claim_id=%s WHERE id='00000000-0000-4000-8000-000000000203'::uuid",
            (CLAIM,),
        )
    try:
        mixed_projection = client.get(f"/api/v1/projects/{PROJECT}/closure").json()["claims"][0]
        mixed_checks = {item["code"]: item for item in mixed_projection["checks"]}
        assert mixed_checks["REVIEW_PURPOSE"]["satisfied"] is True
        assert mixed_checks["REQUIREMENT_REVISION"]["satisfied"] is False
        assert mixed_checks["RULE_JUDGEMENT"]["satisfied"] is True
        assert mixed_projection["ready_for_satisfied"] is False
        mixed_requirements = client.get(f"/api/v1/projects/{PROJECT}/requirements").json()
        mixed_thm_042 = next(item for item in mixed_requirements if item["display_id"] == "THM-042")
        assert mixed_thm_042["claim_id"] == CLAIM
        assert mixed_thm_042["review_purpose"] == "PRODUCT_PERFORMANCE"
        assert mixed_thm_042["ui_status"] == "PERFORMANCE_ASSESSMENT_UNSUPPORTED"

        approver_headers = sign_in(client, "approver@demo")
        mixed_close = client.post(
            f"/api/v1/claims/{CLAIM}/closures",
            headers=approver_headers,
            json={
                "result": "SATISFIED",
                "closure_basis": "COMPLIANCE",
                "note": "혼합 목적 요구사항을 우회하지 않아야 함",
                "expected_claim_version": 1,
                "expected_project_version": 1,
            },
        )
        assert mixed_close.status_code == 409, mixed_close.text
        assert "REQUIREMENT_REVISION" in mixed_close.json()["detail"]
    finally:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE requirements SET claim_id=NULL WHERE id='00000000-0000-4000-8000-000000000203'::uuid"
            )

    restored = client.get(f"/api/v1/projects/{PROJECT}/closure").json()["claims"][0]
    assert restored["ready_for_satisfied"] is True
    assert all(item["satisfied"] for item in restored["checks"])

    reviewer_headers = sign_in(client, "reviewer@demo")
    reviewer_denied = client.post(
        f"/api/v1/claims/{CLAIM}/closures",
        headers=reviewer_headers,
        json={
            "result": "SATISFIED",
            "closure_basis": "COMPLIANCE",
            "note": "검토자에게는 공식 종결 권한이 없음",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )
    assert reviewer_denied.status_code == 403

    approver_headers = sign_in(client, "approver@demo")
    closed = client.post(
        f"/api/v1/claims/{CLAIM}/closures",
        headers=approver_headers,
        json={
            "result": "SATISFIED",
            "closure_basis": "COMPLIANCE",
            "note": "현재 요구사항 revision과 범위에 한정해 검증 종결",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )
    assert closed.status_code == 201, closed.text
    assert closed.json()["actor"] == "approver@demo"
    assert closed.json()["review_purpose"] == "INPUT_READINESS"
    assert closed.json()["source_snapshot_id"] == job["snapshot"]["id"]
    assert closed.json()["assessment_scope"] == assessment_scope
    after = client.get(f"/api/v1/projects/{PROJECT}/closure").json()
    assert after["claims"][0]["current_closure"]["result"] == "SATISFIED"
    assert after["claims"][0]["current_closure"]["closure_basis"] == "COMPLIANCE"
    assert after["claims"][0]["current_closure"]["review_purpose"] == "INPUT_READINESS"
    assert after["claims"][0]["current_closure"]["source_snapshot_id"] == job["snapshot"]["id"]
    assert after["claims"][0]["current_closure"]["assessment_scope"] == assessment_scope
    assert after["claims"][0]["assessment_scope"]["label"] == assessment_scope["label"]
    assert after["claims"][0]["claim"]["status"] == "SATISFIED"
    assert len(after["history"]) == 1

    duplicate = client.post(
        f"/api/v1/claims/{CLAIM}/closures",
        headers=approver_headers,
        json={
            "result": "SATISFIED",
            "closure_basis": "COMPLIANCE",
            "note": "중복 종결 차단",
            "expected_claim_version": 1,
            "expected_project_version": 1,
        },
    )
    assert duplicate.status_code == 409

    engineer_headers = sign_in(client)
    changed = client.put(
        f"/api/v1/claims/{CLAIM}",
        headers=engineer_headers,
        json={
            "question": "변경된 현재 형상에서 제품 성능 요구를 충족했는가?",
            "scope": {"unit": "DORI-01", "configuration": "TVAC-04", "run": "RUN-DEMO-02"},
            "review_purpose": "PRODUCT_PERFORMANCE",
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "OPEN"
    assert changed.json()["review_purpose"] == "PRODUCT_PERFORMANCE"
    reopened = client.get(f"/api/v1/projects/{PROJECT}/closure").json()
    assert reopened["claims"][0]["current_closure"] is None
    assert reopened["claims"][0]["latest_quality_assessment"] is None
    assert reopened["claims"][0]["assessment_scope"]["status"] == "PERFORMANCE_ASSESSMENT_UNSUPPORTED"
    assert reopened["claims"][0]["assessment_scope"]["product_performance_status"] == "NOT_EVALUATED"
    assert len(reopened["history"]) == 1
    assert reopened["history"][0]["review_purpose"] == "INPUT_READINESS"
    assert reopened["history"][0]["assessment_scope"] == assessment_scope
    assert reopened["history"][0]["scope"] == {
        "unit": "DORI-01",
        "configuration": "TVAC-03",
        "run": "RUN-DEMO-01",
    }
    stale_job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert stale_job["job"]["freshness"] == "STALE"
    assert stale_job["snapshot"]["review_purpose"] == "INPUT_READINESS"
    assert stale_job["assessment_scope"] == assessment_scope

    stale_report_response = client.post(f"/api/v1/jobs/{job_id}/reports", headers=engineer_headers)
    assert stale_report_response.status_code == 201, stale_report_response.text
    stale_report = client.get(f"/api/v1/reports/{stale_report_response.json()['id']}/download")
    assert stale_report.status_code == 200, stale_report.text
    stale_report_text = stale_report.content.decode("utf-8")
    assert "TVAC-03 열모델 상관 검토에 필요한 근거가 충분한가?" in stale_report_text
    assert "원본 revision: Claim v1 / project v1" in stale_report_text
    assert assessment_scope["label"] in stale_report_text
    assert "변경된 현재 형상에서 제품 성능 요구를 충족했는가?" not in stale_report_text
