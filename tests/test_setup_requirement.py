from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from dorilab.db import connection

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
FIXTURE_ROOT = Path("/app/fixtures/demo")


def create_project(client, headers, label: str = "SETUP") -> dict:
    suffix = uuid4().hex[:10].upper()
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "display_id": f"{label}-{suffix}",
            "name": "자동 시연 설정 프로젝트",
            "framework": "KASA",
            "data_policy": "EXTERNAL_SYNTHETIC_ALLOWED",
            "mode": "DEMO",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_claim(client, headers, project_id: str, label: str = "SETUP-CLM") -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/claims",
        headers=headers,
        json={
            "display_id": label,
            "question": "현재 합성 BM1 자료가 입력 검토를 시작하기에 충분한가?",
            "review_target": "BM1",
            "scope": {
                "unit": "DORI-SETUP-01",
                "configuration": "TVAC-SYNTHETIC-A",
                "run": "RUN-SYNTHETIC-01",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def requirement_body(claim_id: str | None = None) -> dict:
    return {
        "display_id": "SETUP-REQ-001",
        "level": "EQUIPMENT",
        "parent_ref": "SYS-THERM-SYNTHETIC",
        "statement": "합성 열모델 입력자료의 형상과 run 식별자를 검토 근거에 연결한다.",
        "verification_method": "자료 검토",
        "owner": "열설계 담당",
        "claim_id": claim_id,
        "claim_label": "SETUP-CLM",
        "source_chapter": 19,
        "sort_order": 10,
    }


def test_requirement_create_is_server_backed_audited_and_does_not_approve(client):
    headers = sign_in(client)
    project = create_project(client, headers)
    claim = create_claim(client, headers, project["id"])

    created = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        headers=headers,
        json=requirement_body(claim["id"]),
    )
    assert created.status_code == 201, created.text
    requirement = created.json()
    assert requirement["project_id"] == project["id"]
    assert requirement["claim_id"] == claim["id"]
    assert requirement["display_claim"] == "SETUP-CLM"
    assert requirement["linked_claim_version"] == 1
    assert requirement["ui_status"] == "PURPOSE_UNSPECIFIED"
    assert requirement["review_purpose"] == "UNSPECIFIED"
    assert requirement["version"] == 1

    listed = client.get(f"/api/v1/projects/{project['id']}/requirements")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [requirement["id"]]
    detail = client.get(f"/api/v1/requirements/{requirement['id']}")
    assert detail.status_code == 200
    assert detail.json() == requirement

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT adoption_status,data_policy,mode FROM projects WHERE id=%s",
            (project["id"],),
        )
        saved_project = cur.fetchone()
        cur.execute(
            "SELECT count(*) AS count FROM audit_events WHERE project_id=%s AND action='CREATE' AND object_type='requirement' AND object_id=%s",
            (project["id"], requirement["id"]),
        )
        requirement_audit_count = cur.fetchone()["count"]
        cur.execute("SELECT count(*) AS count FROM gate_decisions WHERE project_id=%s", (project["id"],))
        gate_decision_count = cur.fetchone()["count"]
    assert saved_project == {
        "adoption_status": "UNCONFIRMED",
        "data_policy": "EXTERNAL_SYNTHETIC_ALLOWED",
        "mode": "DEMO",
    }
    assert requirement_audit_count == 1
    assert gate_decision_count == 0


def test_requirement_create_rejects_duplicate_and_cross_project_claim(client):
    headers = sign_in(client)
    first_project = create_project(client, headers, "REQ-A")
    second_project = create_project(client, headers, "REQ-B")
    other_claim = create_claim(client, headers, second_project["id"], "OTHER-CLM")

    cross_project = client.post(
        f"/api/v1/projects/{first_project['id']}/requirements",
        headers=headers,
        json=requirement_body(other_claim["id"]),
    )
    assert cross_project.status_code == 422
    assert cross_project.json()["detail"] == "linked claim must belong to the project"

    body = requirement_body()
    first = client.post(
        f"/api/v1/projects/{first_project['id']}/requirements",
        headers=headers,
        json=body,
    )
    assert first.status_code == 201, first.text
    duplicate = client.post(
        f"/api/v1/projects/{first_project['id']}/requirements",
        headers=headers,
        json=body,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "requirement display_id already exists"


def test_requirement_create_enforces_auth_csrf_role_and_field_constraints(client):
    body = requirement_body()
    unauthenticated = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers={"X-DoriLab-CSRF": "1"},
        json=body,
    )
    assert unauthenticated.status_code == 401
    assert client.post(f"/api/v1/projects/{PROJECT}/requirements", json=body).status_code == 403

    sign_in(client)
    assert client.post(f"/api/v1/projects/{PROJECT}/requirements", json=body).status_code == 403

    viewer_headers = sign_in(client, "viewer@demo")
    denied = client.post(f"/api/v1/projects/{PROJECT}/requirements", headers=viewer_headers, json=body)
    assert denied.status_code == 403

    engineer_headers = sign_in(client)
    invalid_level = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=engineer_headers,
        json={**body, "level": "PROGRAM"},
    )
    assert invalid_level.status_code == 422
    invalid_chapter = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=engineer_headers,
        json={**body, "source_chapter": 21},
    )
    assert invalid_chapter.status_code == 422
    extra_field = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=engineer_headers,
        json={**body, "approved": True},
    )
    assert extra_field.status_code == 422


def test_setup_fixture_is_authenticated_no_store_and_observational(client):
    path = "/api/v1/demo/setup-fixture"
    assert client.get(path).status_code == 401
    sign_in(client)

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS projects FROM projects")
        projects_before = cur.fetchone()["projects"]
        cur.execute("SELECT count(*) AS requirements FROM requirements")
        requirements_before = cur.fetchone()["requirements"]
        cur.execute("SELECT count(*) AS jobs FROM review_jobs")
        jobs_before = cur.fetchone()["jobs"]
        cur.execute("SELECT count(*) AS audit_events FROM audit_events")
        audit_before = cur.fetchone()["audit_events"]

    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    fixture = json.loads((FIXTURE_ROOT / "setup_walkthrough.json").read_text(encoding="utf-8"))
    assert set(fixture["requirement"]["body"]) == {
        "display_id",
        "level",
        "parent_ref",
        "statement",
        "verification_method",
        "owner",
        "claim_id",
        "claim_label",
        "source_chapter",
        "sort_order",
        "review_purpose",
    }
    assert response.json() == {
        "fixture": fixture,
        "document_text": (FIXTURE_ROOT / "setup_walkthrough.md").read_text(encoding="utf-8"),
    }

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS projects FROM projects")
        assert cur.fetchone()["projects"] == projects_before
        cur.execute("SELECT count(*) AS requirements FROM requirements")
        assert cur.fetchone()["requirements"] == requirements_before
        cur.execute("SELECT count(*) AS jobs FROM review_jobs")
        assert cur.fetchone()["jobs"] == jobs_before
        cur.execute("SELECT count(*) AS audit_events FROM audit_events")
        assert cur.fetchone()["audit_events"] == audit_before


def test_authorized_artifact_chunk_projection_includes_saved_text(client):
    headers = sign_in(client)
    document_bytes = (FIXTURE_ROOT / "setup_walkthrough.md").read_bytes()
    uploaded = client.post(
        f"/api/v1/projects/{PROJECT}/artifacts",
        headers=headers,
        files={"file": ("setup_walkthrough.md", document_bytes, "text/markdown")},
        data={
            "rights_status": "PUBLIC",
            "edition": "DEMO-SETUP-1",
            "adopted": "true",
            "applicability_status": "APPLICABLE",
            "usage_purpose": "OPERATIONAL_EVIDENCE",
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    artifact_id = uploaded.json()["id"]
    parsed = client.post(f"/api/v1/artifacts/{artifact_id}/parse", headers=headers)
    assert parsed.status_code == 201, parsed.text

    projected = client.get(f"/api/v1/artifacts/{artifact_id}/chunks")
    assert projected.status_code == 200, projected.text
    chunks = projected.json()["chunks"]
    assert chunks
    assert "component dissipation power map" in "\n".join(chunk["chunk_text"] for chunk in chunks)
    for chunk in chunks:
        assert hashlib.sha256(chunk["chunk_text"].encode("utf-8")).hexdigest() == chunk["text_sha256"]
