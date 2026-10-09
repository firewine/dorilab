from __future__ import annotations

import hashlib

from dorilab.worker import run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def test_audit_projection_and_json_export_are_server_scoped_and_hashed(client):
    engineer_headers = sign_in(client)
    created = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**engineer_headers, "Idempotency-Key": "audit-page-review-0001"},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "SIMULATED"},
    )
    assert created.status_code == 202
    assert run_one() is True
    job_id = created.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    reviewer_headers = sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "ACCEPTED",
            "expected_job_version": job["job"]["version"],
            "note": "감사 화면용 내부 초안 수용",
        },
    )
    assert decision.status_code == 201
    report_response = client.post(f"/api/v1/jobs/{job_id}/reports", headers=reviewer_headers)
    assert report_response.status_code == 201
    report = report_response.json()

    view_response = client.get(f"/api/v1/projects/{PROJECT}/audit-view")
    assert view_response.status_code == 200
    view = view_response.json()
    assert view["summary"]["execution_snapshots"] == 1
    assert view["summary"]["model_runs"] == 1
    assert view["summary"]["human_records"] == 1
    assert view["summary"]["report_exports"] == 1
    assert view["summary"]["audit_events"] >= 4
    assert view["summary"]["orchestration_runs"] == 1
    assert view["summary"]["orchestration_checkpoints"] >= 13
    assert view["reports"][0]["id"] == report["id"]
    assert view["reports"][0]["sha256"] == report["sha256"]
    actions = {event["action"] for event in view["events"]}
    assert {"CREATE", "DECIDE", "EXPORT"} <= actions
    assert all("payload_hash" in event for event in view["events"])

    exported = client.get(f"/api/v1/projects/{PROJECT}/audit-export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert "attachment" in exported.headers["content-disposition"]
    assert hashlib.sha256(exported.content).hexdigest() == exported.headers["x-content-sha256"]
    bundle = exported.json()
    assert bundle["schema_id"] == "dorilab.audit-bundle.v1"
    assert bundle["authority"] == "READ_ONLY_PROJECT_PROJECTION"
    assert bundle["project"]["id"] == PROJECT
    assert bundle["jobs"][0]["snapshot_sha256"]
    assert bundle["jobs"][0]["raw_sha256"] == job["model_run"]["raw_sha256"]
    assert bundle["decision_records"]["human_reviews"][0]["note"] == "감사 화면용 내부 초안 수용"
    assert bundle["decision_records"]["orchestration_runs"][0]["status"] == "COMPLETED"
    assert len(bundle["decision_records"]["orchestration_checkpoints"]) >= 13
    assert bundle["report_exports"][0]["sha256"] == report["sha256"]
    assert b"db_password" not in exported.content
    assert b"inference_token" not in exported.content

    downloaded_report = client.get(f"/api/v1/reports/{report['id']}/download")
    assert downloaded_report.status_code == 200
    assert hashlib.sha256(downloaded_report.content).hexdigest() == report["sha256"]
    report_text = downloaded_report.content.decode("utf-8")
    assert "오케스트레이션 실행" in report_text
    assert "공식 시험 승인이나 VerificationClosure를 뜻하지 않는다." in report_text

    sign_in(client, "engineer@demo")
    private_project = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={"display_id": "AUDIT-PRIVATE", "name": "감사 격리 프로젝트", "framework": "KASA"},
    )
    assert private_project.status_code == 201
    private_id = private_project.json()["id"]
    sign_in(client, "reviewer@demo")
    assert client.get(f"/api/v1/projects/{private_id}/audit-view").status_code == 404
    assert client.get(f"/api/v1/projects/{private_id}/audit-export").status_code == 404


def test_audit_page_keeps_import_and_destructive_reset_explicitly_disabled():
    html = open("/app/apps/web/index.html", encoding="utf-8").read()
    script = open("/app/apps/web/app.js", encoding="utf-8").read()
    assert 'id="auditContent"' in html
    assert "작업 JSON 불러오기" in script
    assert "시연 초기화" in script
    assert "disabled" in script
    assert "READ_ONLY_PROJECT_PROJECTION" not in html


def test_audit_event_details_keep_open_state_across_async_renders():
    script = open("/app/apps/web/app.js", encoding="utf-8").read()
    assert "auditOpenEventIds: []" in script
    assert 'summary[data-audit-event-summary]' in script
    assert "event.preventDefault()" in script
    assert 'data-audit-event-id="${escapeHtml(eventId)}"' in script
    assert 'openEventIds.has(eventId) ? " open" : ""' in script
    assert 'showPage(step.page, {loadData: step.page !== "audit"})' in script
