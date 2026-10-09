from __future__ import annotations

from dorilab.db import connection, one
from dorilab.migrate import backfill_blackboard
from dorilab.worker import run_one

from conftest import sign_in
from test_bm1_flow import add_reference, create_review


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def test_model_action_becomes_proposal_and_evidence_work_item(client):
    headers = sign_in(client)
    job_id = create_review(client, headers, [], key="blackboard-request").json()["job_id"]
    assert run_one() is True

    board = client.get(f"/api/v1/projects/{PROJECT}/blackboard")
    assert board.status_code == 200, board.text
    projection = board.json()
    assert projection["schema_id"] == "dorilab.blackboard.v1"
    assert projection["summary"]["contributions"] == 1
    assert projection["summary"]["work_items"] == 1
    contribution = projection["contributions"][0]
    work_item = projection["work_items"][0]
    assert contribution["status"] == "PROPOSED"
    assert contribution["content"]["action"] == "REQUEST_EVIDENCE"
    assert contribution["actor_type"] == "MODEL"
    assert work_item["work_type"] == "EVIDENCE_REQUEST"
    assert work_item["status"] == "WAITING_INPUT"
    assert work_item["source_contribution_id"] == contribution["id"]
    assert projection["summary"]["dependencies"] >= 2

    request = client.get(f"/api/v1/jobs/{job_id}").json()["evidence_requests"][0]
    assert work_item["evidence_request_id"] == request["id"]
    evidence = add_reference(client, headers, display_id="BLACKBOARD-SUBMISSION")
    submitted = client.post(
        f"/api/v1/evidence-requests/{request['id']}/submission",
        headers=headers,
        json={"evidence_id": evidence["id"], "expected_version": request["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    waiting = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()["work_items"][0]
    assert waiting["status"] == "WAITING_REVIEW"
    assert waiting["input_refs"][-1] == {"object_type": "EVIDENCE", "object_id": evidence["id"]}

    sign_in(client, "reviewer@demo")
    accepted = client.post(
        f"/api/v1/evidence-requests/{request['id']}/decision",
        headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_version": submitted.json()["version"], "note": "범위 확인"},
    )
    assert accepted.status_code == 200, accepted.text
    completed = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    assert completed["work_items"][0]["status"] == "COMPLETED"
    assert one("SELECT freshness FROM review_jobs WHERE id=%s", (job_id,))["freshness"] == "STALE"
    assert any(event["event_type"] == "WORK_ITEM_COMPLETED" for event in completed["events"])


def test_human_contribution_is_idempotent_versioned_and_project_scoped(client):
    headers = sign_in(client)
    body = {
        "claim_id": CLAIM,
        "contribution_type": "HYPOTHESIS",
        "content": {"statement": "합성 fixture의 경계조건을 먼저 확인한다."},
        "evidence_ids": [],
        "expected_project_version": 1,
        "expected_claim_version": 1,
    }
    first = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/contributions",
        headers={**headers, "Idempotency-Key": "human-hypothesis-001"},
        json=body,
    )
    assert first.status_code == 201, first.text
    assert first.json()["idempotent_replay"] is False
    repeated = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/contributions",
        headers={**headers, "Idempotency-Key": "human-hypothesis-001"},
        json=body,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["idempotent_replay"] is True
    assert repeated.json()["contribution"]["id"] == first.json()["contribution"]["id"]

    changed = {**body, "content": {"statement": "같은 키의 다른 내용"}}
    conflict = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/contributions",
        headers={**headers, "Idempotency-Key": "human-hypothesis-001"},
        json=changed,
    )
    assert conflict.status_code == 409

    sign_in(client, "viewer@demo")
    forbidden = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/contributions",
        headers={"X-DoriLab-CSRF": "1", "Idempotency-Key": "viewer-cannot-propose"},
        json=body,
    )
    assert forbidden.status_code == 403
    assert client.get(f"/api/v1/projects/{PROJECT}/blackboard").status_code == 200


def test_stale_contribution_cannot_be_accepted(client):
    headers = sign_in(client)
    proposed = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/contributions",
        headers={**headers, "Idempotency-Key": "stale-contribution"},
        json={
            "claim_id": CLAIM,
            "contribution_type": "FINDING",
            "content": {"finding": "현재 revision에만 적용되는 합성 finding"},
            "evidence_ids": [],
            "expected_project_version": 1,
            "expected_claim_version": 1,
        },
    ).json()["contribution"]
    changed = client.put(
        f"/api/v1/claims/{CLAIM}",
        headers=headers,
        json={
            "question": "변경된 Claim에서 같은 finding을 사용할 수 있는가?",
            "scope": {"unit": "DORI-01", "configuration": "TVAC-04", "run": "RUN-DEMO-02"},
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200

    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/blackboard/contributions/{proposed['id']}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_version": proposed["version"], "note": "검토"},
    )
    assert decision.status_code == 409
    assert decision.json()["detail"] == "contribution is stale"


def test_review_decision_updates_model_contribution_separately(client):
    headers = sign_in(client)
    evidence = add_reference(client, headers, display_id="CONTRIBUTION-REF")
    job_id = create_review(client, headers, [evidence["id"]], key="contribution-decision").json()["job_id"]
    assert run_one() is True
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    board = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    contribution = next(item for item in board["contributions"] if item["source_job_id"] == job_id)
    assert contribution["status"] == "PROPOSED"

    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={"disposition": "ACCEPTED", "expected_job_version": job["job"]["version"], "note": "초안 범위 수용"},
    )
    assert decision.status_code == 201, decision.text
    decided = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    contribution = next(item for item in decided["contributions"] if item["source_job_id"] == job_id)
    assert contribution["status"] == "ACCEPTED"
    assert contribution["reviewed_by"] == "reviewer@demo"


def test_human_work_item_uses_guarded_transitions(client):
    headers = sign_in(client)
    created = client.post(
        f"/api/v1/projects/{PROJECT}/blackboard/work-items",
        headers={**headers, "Idempotency-Key": "manual-analysis-task"},
        json={
            "claim_id": CLAIM,
            "work_type": "TASK",
            "title": "합성 경계조건 확인",
            "purpose": "공개 fixture의 적용범위를 확인한다.",
            "input_refs": [{"object_type": "CLAIM", "object_id": CLAIM, "version": 1}],
            "assigned_role": "ANALYSIS",
            "budget": {"model_calls": 0},
            "expected_project_version": 1,
            "expected_claim_version": 1,
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()["work_item"]
    ready = client.post(
        f"/api/v1/blackboard/work-items/{item['id']}/transitions",
        headers=headers,
        json={"status": "READY", "expected_version": item["version"]},
    )
    assert ready.status_code == 200, ready.text
    forbidden = client.post(
        f"/api/v1/blackboard/work-items/{item['id']}/transitions",
        headers=headers,
        json={"status": "COMPLETED", "expected_version": ready.json()["version"]},
    )
    assert forbidden.status_code == 403
    sign_in(client, "reviewer@demo")
    invalid = client.post(
        f"/api/v1/blackboard/work-items/{item['id']}/transitions",
        headers={"X-DoriLab-CSRF": "1"},
        json={"status": "COMPLETED", "expected_version": ready.json()["version"]},
    )
    assert invalid.status_code == 409


def test_blackboard_backfill_projects_existing_review_without_rerunning_model(client):
    headers = sign_in(client)
    job_id = create_review(client, headers, [], key="legacy-backfill").json()["job_id"]
    assert run_one() is True
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM object_dependencies WHERE project_id=%s", (PROJECT,))
        cur.execute("DELETE FROM board_events WHERE project_id=%s", (PROJECT,))
        cur.execute("DELETE FROM work_items WHERE project_id=%s", (PROJECT,))
        cur.execute("DELETE FROM agent_contributions WHERE project_id=%s", (PROJECT,))
        backfill_blackboard(cur)

    board = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    assert len(board["contributions"]) == 1
    assert board["contributions"][0]["source_job_id"] == job_id
    assert len(board["work_items"]) == 1
    assert board["work_items"][0]["evidence_request_id"] is not None
    assert board["summary"]["dependencies"] >= 2
