import json

from conftest import sign_in
from dorilab.db import connection


PROJECT = "00000000-0000-4000-8000-000000000001"


def test_legacy_system_gate_copy_changes_display_without_rewriting_saved_records(client, request):
    sign_in(client)
    before = client.get(f"/api/v1/projects/{PROJECT}/gates").json()["gates"]
    mission = next(gate for gate in before if gate["gate_key"] == "mission")
    srr = next(gate for gate in before if gate["gate_key"] == "srr")
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM review_gates WHERE id=ANY(%s::uuid[])", ([mission["id"], srr["id"]],))
        original_rows = cur.fetchall()
        def restore_gate_copy():
            with connection() as conn, conn.cursor() as cur:
                for gate in original_rows:
                    cur.execute("""UPDATE review_gates SET description=%s,entry_criteria=%s::jsonb,
                                   success_criteria=%s::jsonb WHERE id=%s""",
                                (gate["description"], json.dumps(gate["entry_criteria"]),
                                 json.dumps(gate["success_criteria"]), gate["id"]))
        request.addfinalizer(restore_gate_copy)
        cur.execute("UPDATE review_gates SET description=%s WHERE id=%s",
                    ("요구사항 기준선과 시스템 구조", srr["id"]))
        cur.execute("""UPDATE review_gates SET entry_criteria=jsonb_set(entry_criteria,'{0,label}',to_jsonb(%s::text)),
                       success_criteria=jsonb_set(success_criteria,'{0,label}',to_jsonb(%s::text)) WHERE id=%s""",
                    ("프로젝트 기준선 등록", "사용자가 작성한 기준선 검토 문구", mission["id"]))
        cur.execute("SELECT * FROM review_gates WHERE project_id=%s ORDER BY id", (PROJECT,))
        saved_before = cur.fetchall()
    listed = client.get(f"/api/v1/projects/{PROJECT}/gates").json()["gates"]
    displayed_mission = next(gate for gate in listed if gate["id"] == mission["id"])
    displayed_srr = client.get(f"/api/v1/gates/{srr['id']}").json()
    assert displayed_srr["description"] == "요구사항 기준점과 시스템 구조"
    assert displayed_mission["evaluated_entry_criteria"][0]["label"] == "프로젝트 기준점 등록"
    assert displayed_mission["evaluated_success_criteria"][0]["label"] == "사용자가 작성한 기준선 검토 문구"
    for key in ("state", "ready_count", "criteria_count", "ready_for_decision", "authority", "version"):
        assert displayed_mission[key] == mission[key]
        assert displayed_srr[key] == srr[key]
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM review_gates WHERE project_id=%s ORDER BY id", (PROJECT,))
        assert cur.fetchall() == saved_before


def test_gate_criteria_authority_and_transition_boundary(client):
    engineer_headers = sign_in(client)
    response = client.get(f"/api/v1/projects/{PROJECT}/gates")
    assert response.status_code == 200
    body = response.json()
    assert [gate["gate_key"] for gate in body["gates"]] == [
        "mission", "srr", "pdr", "cdr", "sir", "trr", "trb", "accept", "orr"
    ]
    mission = body["gates"][0]
    accept = next(gate for gate in body["gates"] if gate["gate_key"] == "accept")
    assert mission["state"] == "READY"
    assert mission["ready_count"] == mission["criteria_count"] == 2
    assert accept["state"] == "UNRESOLVED"

    denied = client.post(
        f"/api/v1/gates/{mission['id']}/decisions",
        headers=engineer_headers,
        json={
            "disposition": "APPROVED",
            "note": "임무 개념 검토 범위 확인",
            "expected_gate_version": mission["version"],
            "expected_project_version": body["project"]["version"],
        },
    )
    assert denied.status_code == 403

    reviewer_headers = sign_in(client, "reviewer@demo")
    approved = client.post(
        f"/api/v1/gates/{mission['id']}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "APPROVED",
            "note": "등록된 기준선과 요구사항 범위에서 검토함",
            "expected_gate_version": mission["version"],
            "expected_project_version": body["project"]["version"],
        },
    )
    assert approved.status_code == 201
    assert approved.json()["disposition"] == "APPROVED"
    assert client.get(f"/api/v1/gates/{mission['id']}").json()["state"] == "REVIEW_COMPLETE"

    accept_by_reviewer = client.post(
        f"/api/v1/gates/{accept['id']}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "APPROVED",
            "note": "권한 경계 확인",
            "expected_gate_version": accept["version"],
            "expected_project_version": body["project"]["version"],
        },
    )
    assert accept_by_reviewer.status_code == 403

    approver_headers = sign_in(client, "approver@demo")
    unresolved = client.post(
        f"/api/v1/gates/{accept['id']}/decisions",
        headers=approver_headers,
        json={
            "disposition": "APPROVED",
            "note": "미충족 조건에서는 승인할 수 없음",
            "expected_gate_version": accept["version"],
            "expected_project_version": body["project"]["version"],
        },
    )
    assert unresolved.status_code == 409

    hold = client.post(
        f"/api/v1/projects/{PROJECT}/transitions",
        headers=approver_headers,
        json={
            "disposition": "HOLD",
            "note": "제품 인수와 운용 준비 근거 보완",
            "expected_project_version": body["project"]["version"],
        },
    )
    assert hold.status_code == 201
    assert hold.json()["transition"]["disposition"] == "HOLD"
    assert hold.json()["project"]["current_phase"] == 4
    assert hold.json()["project"]["version"] == 1

    go = client.post(
        f"/api/v1/projects/{PROJECT}/transitions",
        headers=approver_headers,
        json={
            "disposition": "GO",
            "note": "필수 Gate 없이 진입할 수 없음",
            "expected_project_version": 1,
        },
    )
    assert go.status_code == 409
