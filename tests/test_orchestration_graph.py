from __future__ import annotations

from dorilab.db import connection
from dorilab.orchestration import backfill_legacy_runs
from dorilab.worker import claim_job, recover_orphaned_jobs, run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"
GRAPH_NODES = [
    "SELECT_TASK",
    "SCOPE_GATE",
    "RETRIEVE_CONTEXT",
    "BUILD_CONTEXT",
    "SOURCE_REVIEW",
    "VALIDATE",
    "UPDATE_BLACKBOARD",
    "ROUTE",
    "WAIT_HUMAN",
    "RESUME",
    "COMPLETE",
]


def create_review(client, headers, key: str):
    return client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": key},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "SIMULATED"},
    )


def test_fixed_graph_checkpoints_waits_and_resumes_without_duplicate_model_call(client):
    headers = sign_in(client)
    created = create_review(client, headers, "graph-happy-path")
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    assert created.json()["orchestration"]["current_node"] == "SOURCE_REVIEW"

    initial = client.get(f"/api/v1/jobs/{job_id}/orchestration")
    assert initial.status_code == 200, initial.text
    graph = initial.json()
    assert graph["graph"]["nodes"] == GRAPH_NODES
    assert graph["run"]["origin"] == "NATIVE"
    assert graph["run"]["status"] == "QUEUED"
    assert graph["run"]["current_node"] == "SOURCE_REVIEW"
    assert [node["status"] for node in graph["nodes"][:4]] == ["COMPLETED"] * 4
    assert graph["nodes"][4]["status"] == "READY"
    assert graph["integrity"]["checkpoint_count"] == 4
    assert len(graph["integrity"]["latest_sha256"]) == 64
    assert all(len(item["state_sha256"]) == 64 for item in graph["checkpoints"])

    replay = create_review(client, headers, "graph-happy-path")
    assert replay.status_code == 202
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["orchestration"]["id"] == graph["run"]["id"]
    assert client.get(f"/api/v1/jobs/{job_id}/orchestration").json()["integrity"]["checkpoint_count"] == 4

    assert run_one() is True
    waiting = client.get(f"/api/v1/jobs/{job_id}").json()
    trace = waiting["orchestration"]
    assert waiting["job"]["status"] == "AWAITING_REVIEW"
    assert trace["run"]["status"] == "WAITING_HUMAN"
    assert trace["run"]["current_node"] == "WAIT_HUMAN"
    assert trace["nodes"][8]["status"] == "WAITING"
    assert [node["status"] for node in trace["nodes"][:8]] == ["COMPLETED"] * 8
    source_attempts = [
        item for item in trace["nodes"] if item["key"] == "SOURCE_REVIEW" and item["attempt"]
    ]
    assert len(source_attempts) == 1

    sign_in(client, "reviewer@demo")
    decided = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={
            "disposition": "REVISION_REQUESTED",
            "expected_job_version": waiting["job"]["version"],
            "note": "고정 그래프 resume 검사",
        },
    )
    assert decided.status_code == 201, decided.text
    completed = client.get(f"/api/v1/jobs/{job_id}").json()["orchestration"]
    assert completed["run"]["status"] == "COMPLETED"
    assert completed["run"]["current_node"] == "COMPLETE"
    assert [node["status"] for node in completed["nodes"]] == ["COMPLETED"] * len(GRAPH_NODES)
    assert completed["nodes"][9]["attempt"]["output_summary"]["duplicate_model_call"] is False
    assert completed["nodes"][10]["attempt"]["output_summary"]["formal_verification_approval"] is False
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) AS count FROM orchestration_node_attempts a
               JOIN orchestration_runs r ON r.id=a.run_id
               WHERE r.job_id=%s AND a.node_key='SOURCE_REVIEW'""",
            (job_id,),
        )
        assert cur.fetchone()["count"] == 1
        cur.execute("SELECT count(*) AS count FROM model_runs WHERE job_id=%s", (job_id,))
        assert cur.fetchone()["count"] == 1


def test_worker_recovery_is_checkpointed_and_live_ambiguity_stays_unknown(client):
    headers = sign_in(client)
    demo_id = create_review(client, headers, "graph-recover-demo").json()["job_id"]
    demo_job = claim_job()
    assert str(demo_job["id"]) == demo_id
    live_id = create_review(client, headers, "graph-recover-live").json()["job_id"]
    live_job = claim_job()
    assert str(live_job["id"]) == live_id
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE review_jobs SET leased_at=now()-interval '5 minutes' WHERE id=%s", (demo_id,))
        cur.execute(
            """UPDATE review_jobs SET mode='LIVE_MODEL_RUN',status='RUNNING',leased_at=now()-interval '5 minutes'
               WHERE id=%s""",
            (live_id,),
        )
        cur.execute("UPDATE review_attempts SET status='RUNNING' WHERE job_id=%s", (live_id,))
    assert recover_orphaned_jobs(stale_seconds=1) == {"recovered_demo": 1, "unknown_live": 1}

    demo_trace = client.get(f"/api/v1/jobs/{demo_id}/orchestration").json()
    live_trace = client.get(f"/api/v1/jobs/{live_id}/orchestration").json()
    assert demo_trace["run"]["status"] == "QUEUED"
    assert demo_trace["nodes"][4]["status"] == "RECOVERED"
    assert live_trace["run"]["status"] == "UNKNOWN_OUTCOME"
    assert live_trace["nodes"][4]["status"] == "UNKNOWN_OUTCOME"
    assert live_trace["run"]["state"]["nodes"]["SOURCE_REVIEW"]["status"] == "UNKNOWN_OUTCOME"


def test_claim_revision_marks_graph_stale_and_project_boundary_remains_enforced(client):
    headers = sign_in(client)
    job_id = create_review(client, headers, "graph-stale").json()["job_id"]
    changed = client.put(
        f"/api/v1/claims/{CLAIM}",
        headers=headers,
        json={
            "question": "변경 후 검토 질문",
            "scope": {"unit": "DORI-01", "configuration": "TVAC-04", "run": "RUN-04"},
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200, changed.text
    trace = client.get(f"/api/v1/jobs/{job_id}/orchestration").json()
    assert trace["run"]["status"] == "STALE"
    assert trace["run"]["state"]["stale_reason"] == "CLAIM_REVISION_CHANGED"

    other = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"display_id": "GRAPH-X", "name": "Graph access boundary", "framework": "ECSS"},
    )
    assert other.status_code == 201
    sign_in(client, "viewer@demo")
    hidden = client.get(f"/api/v1/jobs/{job_id}/orchestration")
    assert hidden.status_code == 200
    sign_in(client, "reviewer@demo")
    # Reviewer belongs to the demo project, so this run remains visible; a non-member project remains hidden.
    assert client.get(f"/api/v1/projects/{other.json()['id']}").status_code == 404


def test_legacy_projected_waiting_job_can_resume_without_replaying_model(client):
    headers = sign_in(client)
    job_id = create_review(client, headers, "graph-legacy-resume").json()["job_id"]
    assert run_one() is True
    waiting = client.get(f"/api/v1/jobs/{job_id}").json()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM orchestration_runs WHERE job_id=%s", (job_id,))
        backfill_legacy_runs(cur)
    legacy = client.get(f"/api/v1/jobs/{job_id}/orchestration").json()
    assert legacy["run"]["origin"] == "LEGACY_PROJECTION"
    assert legacy["run"]["status"] == "WAITING_HUMAN"

    sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers={"X-DoriLab-CSRF": "1"},
        json={
            "disposition": "ACCEPTED",
            "expected_job_version": waiting["job"]["version"],
            "note": "migration 이전 대기 Job 재개",
        },
    )
    assert decision.status_code == 201, decision.text
    resumed = client.get(f"/api/v1/jobs/{job_id}/orchestration").json()
    assert resumed["run"]["status"] == "COMPLETED"
    assert resumed["run"]["current_node"] == "COMPLETE"
    assert resumed["nodes"][9]["status"] == "COMPLETED"
    assert resumed["nodes"][10]["status"] == "COMPLETED"
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS count FROM model_runs WHERE job_id=%s", (job_id,))
        assert cur.fetchone()["count"] == 1
