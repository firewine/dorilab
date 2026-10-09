from __future__ import annotations

import hashlib

from dorilab.db import connection, one
from dorilab.worker import claim_job, recover_orphaned_jobs, run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def add_reference(client, headers, *, display_id="REF-DEMO"):
    data = b"synthetic public reference bytes\n"
    response = client.post(
        f"/api/v1/projects/{PROJECT}/artifacts",
        headers=headers,
        data={"rights_status": "PUBLIC", "edition": "DEMO-1", "adopted": "true", "applicability_status": "APPLICABLE"},
        files={"file": ("reference.txt", data, "text/plain")},
    )
    assert response.status_code == 201, response.text
    artifact = response.json()
    assert artifact["sha256"] == hashlib.sha256(data).hexdigest()
    downloaded = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == data
    evidence = client.post(
        f"/api/v1/projects/{PROJECT}/evidence",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "artifact_id": artifact["id"], "display_id": display_id, "kind": "REFERENCE",
            "basis": "SYNTHETIC", "scope": {}, "locator": "section demo",
            "quote": "synthetic public reference", "provenance": {"fixture": True},
        },
    )
    assert evidence.status_code == 201, evidence.text
    return evidence.json()


def create_review(client, headers, evidence_ids, key="idem-key-0001"):
    return client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": key},
        json={"claim_id": CLAIM, "evidence_ids": evidence_ids, "mode": "SIMULATED"},
    )


def test_bytes_hash_review_validation_and_human_decision_are_separate(client):
    headers = sign_in(client)
    evidence = add_reference(client, headers)
    created = create_review(client, headers, [evidence["id"]])
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    repeated = create_review(client, headers, [evidence["id"]])
    assert repeated.status_code == 202
    assert repeated.json()["job_id"] == job_id
    assert repeated.json()["idempotent_replay"] is True

    assert run_one() is True
    result = client.get(f"/api/v1/jobs/{job_id}")
    assert result.status_code == 200
    body = result.json()
    assert body["job"]["status"] == "AWAITING_REVIEW"
    assert body["model_run"]["validation_status"] == "VALID"
    assert body["model_run"]["parsed_output"]["actions"][0]["action"] == "NO_ACTION_REQUIRED"
    assert body["model_run"]["receipt"]["execution_mode"] == "SIMULATED"
    assert body["model_run"]["receipt"]["basis"] == "SYNTHETIC"

    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={
            "disposition": "REVISION_REQUESTED", "expected_job_version": body["job"]["version"],
            "edited_draft": {"reviewer_text": "수정된 사람 초안"}, "note": "공식 승인 아님",
        },
    )
    assert decision.status_code == 201, decision.text
    after = client.get(f"/api/v1/jobs/{job_id}").json()
    assert after["job"]["status"] == "COMPLETED"
    assert len(after["decisions"]) == 1
    assert after["decisions"][0]["edited_draft"] != after["model_run"]["parsed_output"]


def test_idempotency_conflict_cross_project_reference_and_csrf(client):
    headers = sign_in(client)
    first = create_review(client, headers, [], key="idem-key-conflict")
    assert first.status_code == 202
    conflict = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "idem-key-conflict"},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "REPLAY"},
    )
    assert conflict.status_code == 409

    no_csrf = client.post(
        f"/api/v1/projects/{PROJECT}/claims",
        json={"display_id": "X", "question": "This mutation has no CSRF header", "scope": {}},
    )
    assert no_csrf.status_code == 403

    second = client.post(
        "/api/v1/projects", headers=headers,
        json={"display_id": "PRIVATE-X", "name": "Other project", "framework": "ECSS"},
    )
    assert second.status_code == 201
    other_project = second.json()["id"]
    sign_in(client, "reviewer@demo")
    denied = client.get(f"/api/v1/projects/{other_project}")
    assert denied.status_code == 404


def test_claim_change_marks_result_stale_and_blocks_acceptance(client):
    headers = sign_in(client)
    created = create_review(client, headers, [], key="idem-key-stale")
    job_id = created.json()["job_id"]
    changed = client.put(
        f"/api/v1/claims/{CLAIM}", headers=headers,
        json={
            "question": "변경된 형상에서 근거가 충분한가?",
            "scope": {"unit": "DORI-01", "configuration": "TVAC-04", "run": "RUN-DEMO-02"},
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200
    assert run_one() is True
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["job"]["freshness"] == "STALE"

    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions", headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_job_version": body["job"]["version"]},
    )
    assert decision.status_code == 409


def test_live_request_never_falls_back_in_explicit_demo_mode(client):
    headers = sign_in(client)
    response = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "live-no-fallback"},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "LIVE_MODEL_RUN"},
    )
    assert response.status_code == 409
    assert "disabled in explicit DEMO mode" in response.json()["detail"]


def test_evidence_request_received_and_acceptance_are_separate(client):
    headers = sign_in(client)
    created = create_review(client, headers, [], key="evidence-request-flow")
    job_id = created.json()["job_id"]
    assert run_one() is True
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["model_run"]["parsed_output"]["actions"][0]["action"] == "REQUEST_EVIDENCE"
    request = job["evidence_requests"][0]
    assert request["status"] == "OPEN"

    evidence = add_reference(client, headers, display_id="REQUEST-SUBMISSION")
    submitted = client.post(
        f"/api/v1/evidence-requests/{request['id']}/submission",
        headers=headers,
        json={"evidence_id": evidence["id"], "expected_version": request["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "RECEIVED"

    forbidden = client.post(
        f"/api/v1/evidence-requests/{request['id']}/decision",
        headers=headers,
        json={"disposition": "ACCEPTED", "expected_version": submitted.json()["version"]},
    )
    assert forbidden.status_code == 403

    sign_in(client, "reviewer@demo")
    accepted = client.post(
        f"/api/v1/evidence-requests/{request['id']}/decision",
        headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_version": submitted.json()["version"], "note": "범위 확인"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["decided_by"] == "reviewer@demo"


def test_completed_review_report_is_hashed_idempotent_and_downloadable(client):
    headers = sign_in(client)
    evidence = add_reference(client, headers, display_id="REPORT-REF")
    created = create_review(client, headers, [evidence["id"]], key="report-flow")
    job_id = created.json()["job_id"]
    assert run_one() is True
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_job_version": job["job"]["version"], "note": "내부 초안 수락"},
    )
    assert decision.status_code == 201
    first = client.post(f"/api/v1/jobs/{job_id}/reports", headers={"X-DoriLab-CSRF": "1"})
    assert first.status_code == 201, first.text
    report = first.json()
    downloaded = client.get(f"/api/v1/reports/{report['id']}/download")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == report["sha256"]
    text = downloaded.content.decode("utf-8")
    assert "공식 시험 승인" in text
    assert "REPORT-REF" in text
    assert "내부 초안 수락" in text
    repeated = client.post(f"/api/v1/jobs/{job_id}/reports", headers={"X-DoriLab-CSRF": "1"})
    assert repeated.status_code == 201
    assert repeated.json()["id"] == report["id"]
    jobs = client.get(f"/api/v1/projects/{PROJECT}/jobs").json()
    listed = next(item for item in jobs if str(item["id"]) == job_id)
    assert listed["report_count"] == 1
    assert listed["latest_disposition"] == "ACCEPTED"


def test_worker_recovery_requeues_demo_but_never_replays_ambiguous_live(client):
    headers = sign_in(client)
    first = create_review(client, headers, [], key="recover-demo").json()["job_id"]
    demo_claim = claim_job()
    assert str(demo_claim["id"]) == first
    second = create_review(client, headers, [], key="recover-live").json()["job_id"]
    live_claim = claim_job()
    assert str(live_claim["id"]) == second
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE review_jobs SET leased_at=now()-interval '5 minutes' WHERE id=%s", (first,))
        cur.execute(
            """UPDATE review_jobs SET mode='LIVE_MODEL_RUN',status='RUNNING',leased_at=now()-interval '5 minutes'
               WHERE id=%s""",
            (second,),
        )
        cur.execute("UPDATE review_attempts SET status='RUNNING' WHERE job_id=%s", (second,))
    recovered = recover_orphaned_jobs(stale_seconds=1)
    assert recovered == {"recovered_demo": 1, "unknown_live": 1}
    assert one("SELECT status,error_code FROM review_jobs WHERE id=%s", (first,)) == {
        "status": "QUEUED", "error_code": "WORKER_RECOVERED"
    }
    assert one("SELECT status,error_code FROM review_jobs WHERE id=%s", (second,)) == {
        "status": "UNKNOWN_OUTCOME", "error_code": "UNKNOWN_OUTCOME"
    }
