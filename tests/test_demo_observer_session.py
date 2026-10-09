from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from dorilab.db import connection

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"


def session_path(project_id: str, source_id: str) -> str:
    return f"/api/v1/projects/{project_id}/demo-observer/sessions/{source_id}"


def demo_state(
    *,
    source_id: str,
    project_id: str = PROJECT,
    sequence: int = 1,
    run_key: str | None = None,
    job_id: str | None = None,
    step_index: int = 1,
    step_title: str = "프로젝트와 기준선",
    execution_status: str = "PLAYING",
) -> dict:
    return {
        "schema": "dorilab.demo.observer.v1",
        "type": "DEMO_STATE",
        "source_instance_id": source_id,
        "sequence": sequence,
        "project_id": project_id,
        "run_key": run_key or str(uuid4()),
        "job_id": job_id,
        "mode": "REPLAY",
        "active": True,
        "playing": True,
        "step_index": step_index,
        "step_count": 9,
        "step_title": step_title,
        "execution_status": execution_status,
        "error": None,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def business_counts() -> dict[str, int]:
    tables = (
        "review_jobs",
        "review_attempts",
        "model_runs",
        "validations",
        "agent_contributions",
        "work_items",
        "board_events",
        "orchestration_runs",
        "orchestration_checkpoints",
        "audit_events",
    )
    with connection() as conn, conn.cursor() as cur:
        counts = {}
        for table in tables:
            cur.execute(f"SELECT count(*) AS count FROM {table}")
            counts[table] = cur.fetchone()["count"]
        return counts


def test_demo_observer_session_requires_login_membership_and_csrf_for_publish(client):
    source_id = str(uuid4())
    path = session_path(PROJECT, source_id)
    body = demo_state(source_id=source_id)

    assert client.get(path).status_code == 401
    assert client.put(path, headers={"X-DoriLab-CSRF": "1"}, json=body).status_code == 401

    headers = sign_in(client)
    assert client.put(path, json=body).status_code == 403

    published = client.put(path, headers=headers, json=body)
    assert published.status_code == 200, published.text
    assert published.json() == {"status": "accepted", "sequence": 1}

    observed = client.get(path)
    assert observed.status_code == 200, observed.text
    assert observed.headers["cache-control"] == "no-store"
    state = observed.json()
    assert state["schema"] == "dorilab.demo.observer.v1"
    assert state["type"] == "DEMO_STATE"
    assert state["source_instance_id"] == source_id
    assert state["project_id"] == PROJECT
    assert state["sequence"] == 1


def test_demo_observer_session_validates_protocol_uuid_and_positive_sequence(client):
    headers = sign_in(client)
    source_id = str(uuid4())
    path = session_path(PROJECT, source_id)
    valid = demo_state(source_id=source_id)

    assert client.put(path, headers=headers, json={**valid, "schema": "unknown.v1"}).status_code == 422
    assert client.put(path, headers=headers, json={**valid, "type": "OBSERVER_HELLO"}).status_code == 422
    assert client.put(path, headers=headers, json={**valid, "source_instance_id": "not-a-uuid"}).status_code == 422
    assert client.put(path, headers=headers, json={**valid, "sequence": 0}).status_code == 422


def test_demo_observer_session_is_monotonic_and_keeps_latest_state(client):
    headers = sign_in(client)
    source_id = str(uuid4())
    path = session_path(PROJECT, source_id)
    run_key = str(uuid4())
    job_id = str(uuid4())

    first = demo_state(
        source_id=source_id,
        sequence=10,
        run_key=run_key,
        job_id=job_id,
        step_index=5,
        step_title="BM1 입력과 Context",
    )
    accepted = client.put(path, headers=headers, json=first)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"status": "accepted", "sequence": 10}

    duplicate = client.put(path, headers=headers, json=first)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json() == {"status": "duplicate", "sequence": 10}

    older = demo_state(
        source_id=source_id,
        sequence=9,
        run_key=run_key,
        job_id=None,
        step_index=1,
        step_title="역순 메시지",
    )
    ignored = client.put(path, headers=headers, json=older)
    assert ignored.status_code == 200, ignored.text
    assert ignored.json() == {"status": "ignored", "sequence": 10}

    newest = demo_state(
        source_id=source_id,
        sequence=11,
        run_key=run_key,
        job_id=job_id,
        step_index=6,
        step_title="Qwen 입출력과 판단",
    )
    advanced = client.put(path, headers=headers, json=newest)
    assert advanced.status_code == 200, advanced.text
    assert advanced.json() == {"status": "accepted", "sequence": 11}

    current = client.get(path)
    assert current.status_code == 200, current.text
    state = current.json()
    assert state["sequence"] == 11
    assert state["run_key"] == run_key
    assert state["job_id"] == job_id
    assert state["step_index"] == 6
    assert state["step_title"] == "Qwen 입출력과 판단"


def test_demo_observer_session_does_not_write_business_blackboard_or_model_state(client):
    headers = sign_in(client)
    source_id = str(uuid4())
    path = session_path(PROJECT, source_id)
    before_counts = business_counts()
    before_board = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()

    body = demo_state(
        source_id=source_id,
        sequence=1,
        run_key=str(uuid4()),
        job_id=None,
        step_index=1,
    )
    published = client.put(path, headers=headers, json=body)
    assert published.status_code == 200, published.text
    assert client.get(path).status_code == 200

    after_counts = business_counts()
    after_board = client.get(f"/api/v1/projects/{PROJECT}/blackboard").json()
    assert after_counts == before_counts
    assert after_board == before_board


def test_demo_observer_session_is_project_scoped(client):
    engineer_headers = sign_in(client)
    created = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={
            "display_id": "OBSERVER-PRIVATE",
            "name": "관찰 세션 격리 프로젝트",
            "framework": "KASA",
        },
    )
    assert created.status_code == 201, created.text
    private_project = str(created.json()["id"])
    source_id = str(uuid4())
    path = session_path(private_project, source_id)
    body = demo_state(source_id=source_id, project_id=private_project)

    owner_publish = client.put(path, headers=engineer_headers, json=body)
    assert owner_publish.status_code == 200, owner_publish.text

    reviewer_headers = sign_in(client, "reviewer@demo")
    assert client.get(path).status_code == 404
    assert client.put(path, headers=reviewer_headers, json={**body, "sequence": 2}).status_code == 404

    sign_in(client, "engineer@demo")
    owner_read = client.get(path)
    assert owner_read.status_code == 200
    assert owner_read.json()["source_instance_id"] == source_id


def test_demo_observer_session_returns_not_found_for_unknown_source(client):
    sign_in(client)
    missing_source = str(uuid4())
    response = client.get(session_path(PROJECT, missing_source))
    assert response.status_code == 404
    assert "detail" in response.json()


def test_demo_observer_sessions_are_isolated_by_source_instance(client):
    headers = sign_in(client)
    source_a = str(uuid4())
    source_b = str(uuid4())
    state_a = demo_state(source_id=source_a, sequence=4, step_title="A 실행")
    state_b = demo_state(source_id=source_b, sequence=1, step_title="B 실행")

    assert client.put(session_path(PROJECT, source_a), headers=headers, json=state_a).status_code == 200
    assert client.put(session_path(PROJECT, source_b), headers=headers, json=state_b).status_code == 200

    observed_a = client.get(session_path(PROJECT, source_a)).json()
    observed_b = client.get(session_path(PROJECT, source_b)).json()
    assert observed_a["source_instance_id"] == source_a
    assert observed_a["sequence"] == 4
    assert observed_a["step_title"] == "A 실행"
    assert observed_b["source_instance_id"] == source_b
    assert observed_b["sequence"] == 1
    assert observed_b["step_title"] == "B 실행"
