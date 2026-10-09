from __future__ import annotations

from dorilab.worker import run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def test_configuration_change_is_authorized_versioned_and_preserves_old_results(client):
    engineer_headers = sign_in(client)
    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**engineer_headers, "Idempotency-Key": "change-impact-review-0001"},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "SIMULATED"},
    )
    assert review.status_code == 202
    assert run_one() is True
    job_id = review.json()["job_id"]
    before_job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert before_job["job"]["freshness"] == "CURRENT"
    assert before_job["model_run"]["raw_sha256"]

    created = client.post(
        f"/api/v1/projects/{PROJECT}/changes",
        headers=engineer_headers,
        json={
            "to_baseline": "BL-004",
            "to_configuration": "Rev.D",
            "to_test_run": "TVAC-04",
            "reason": "계측 구성 변경을 다음 시험 기준선에 반영",
            "expected_project_version": 1,
        },
    )
    assert created.status_code == 201, created.text
    change = created.json()
    assert change["status"] == "DRAFT"
    assert change["from_baseline"] == "BL-003"
    assert change["impact_assessment"]["affected_claims"] == 1
    assert change["impact_assessment"]["current_review_jobs"] == 1

    listed = client.get(f"/api/v1/projects/{PROJECT}/changes").json()
    assert listed["project"]["version"] == 1
    assert listed["changes"][0]["id"] == change["id"]
    assert listed["impact"]["current_review_jobs"] == 1

    denied = client.post(
        f"/api/v1/changes/{change['id']}/decision",
        headers=engineer_headers,
        json={
            "disposition": "APPLIED",
            "note": "엔지니어에게 CCB 적용 권한은 없음",
            "expected_change_version": 1,
            "expected_project_version": 1,
        },
    )
    assert denied.status_code == 403

    approver_headers = sign_in(client, "approver@demo")
    applied = client.post(
        f"/api/v1/changes/{change['id']}/decision",
        headers=approver_headers,
        json={
            "disposition": "APPLIED",
            "note": "CCB 영향 확인 후 새 기준선 적용",
            "expected_change_version": 1,
            "expected_project_version": 1,
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["change"]["status"] == "APPLIED"
    assert body["project"]["baseline_display_id"] == "BL-004"
    assert body["project"]["product_configuration"] == "Rev.D"
    assert body["project"]["test_run"] == "TVAC-04"
    assert body["project"]["version"] == 2
    assert body["invalidated_review_jobs"] == 1

    after_job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert after_job["job"]["freshness"] == "STALE"
    assert after_job["job"]["version"] == before_job["job"]["version"] + 1
    assert after_job["model_run"]["raw_sha256"] == before_job["model_run"]["raw_sha256"]
    assert after_job["model_run"]["raw_artifact_id"] == before_job["model_run"]["raw_artifact_id"]

    stale_command = client.post(
        f"/api/v1/projects/{PROJECT}/changes",
        headers=approver_headers,
        json={
            "to_baseline": "BL-005",
            "to_configuration": "Rev.E",
            "to_test_run": "TVAC-05",
            "reason": "이전 화면에서 보낸 명령",
            "expected_project_version": 1,
        },
    )
    assert stale_command.status_code == 409
    assert stale_command.json()["detail"] == "project version conflict"

    duplicate_decision = client.post(
        f"/api/v1/changes/{change['id']}/decision",
        headers=approver_headers,
        json={
            "disposition": "APPLIED",
            "note": "이미 적용된 변경을 다시 적용하지 않음",
            "expected_change_version": 2,
            "expected_project_version": 2,
        },
    )
    assert duplicate_decision.status_code == 409

    rejected_draft = client.post(
        f"/api/v1/projects/{PROJECT}/changes",
        headers=approver_headers,
        json={
            "to_baseline": "BL-005",
            "to_configuration": "Rev.E",
            "to_test_run": "TVAC-05",
            "reason": "비교 검토용 변경 후보",
            "expected_project_version": 2,
        },
    )
    assert rejected_draft.status_code == 201
    rejected = client.post(
        f"/api/v1/changes/{rejected_draft.json()['id']}/decision",
        headers=approver_headers,
        json={
            "disposition": "REJECTED",
            "note": "현재 시험 범위에는 적용하지 않음",
            "expected_change_version": 1,
            "expected_project_version": 2,
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["change"]["status"] == "REJECTED"
    assert rejected.json()["project"]["version"] == 2

    audit = client.get(f"/api/v1/projects/{PROJECT}/audit").json()
    actions = {item["action"] for item in audit}
    assert {"CREATE_CONFIGURATION_CHANGE", "APPLY_CONFIGURATION_CHANGE", "REJECT_CONFIGURATION_CHANGE"} <= actions
