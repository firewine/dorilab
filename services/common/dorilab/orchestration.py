from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from .blackboard import append_event
from .contracts import digest


GRAPH_ID = "dorilab.bm1.fixed"
GRAPH_VERSION = 1
GRAPH_NODES = (
    ("SELECT_TASK", "작업 선택", "검토할 Claim과 실행 모드를 고정"),
    ("SCOPE_GATE", "범위 게이트", "권리·판본·적용성과 시험 범위를 검사"),
    ("RETRIEVE_CONTEXT", "근거 검색", "직접 근거와 RAG 검색 결과를 선택"),
    ("BUILD_CONTEXT", "Context 구성", "계약 입력과 receipt를 Snapshot으로 고정"),
    ("SOURCE_REVIEW", "Source Review", "지정된 모델 또는 DEMO executor 실행"),
    ("VALIDATE", "출력 검증", "JSON 계약과 제공 참조를 검사"),
    ("UPDATE_BLACKBOARD", "Blackboard 반영", "검증된 제안과 작업을 저장"),
    ("ROUTE", "다음 경로 결정", "고정 규칙으로 사람 검토 경계를 선택"),
    ("WAIT_HUMAN", "사람 검토 대기", "자동 승인을 금지하고 결정을 대기"),
    ("RESUME", "결정 후 재개", "같은 실행에서 사람 결정을 반영"),
    ("COMPLETE", "실행 완료", "업무 결정과 실행 증거를 분리해 종결"),
)
NODE_KEYS = tuple(node[0] for node in GRAPH_NODES)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _next_node(node_key: str) -> str:
    index = NODE_KEYS.index(node_key)
    return NODE_KEYS[min(index + 1, len(NODE_KEYS) - 1)]


def _run_for_job(cur, job_id, *, lock: bool = False) -> dict | None:
    suffix = " FOR UPDATE" if lock else ""
    cur.execute(f"SELECT * FROM orchestration_runs WHERE job_id=%s{suffix}", (job_id,))
    return cur.fetchone()


def _checkpoint(
    cur,
    *,
    run: dict,
    node_key: str,
    run_status: str,
    current_node: str,
    event_type: str,
    state_patch: dict | None,
    actor_type: str,
    actor_id: str,
    idempotency_key: str,
    basis: str = "APP_SHA256",
) -> dict:
    cur.execute(
        "SELECT * FROM orchestration_checkpoints WHERE run_id=%s AND idempotency_key=%s",
        (run["id"], idempotency_key),
    )
    existing = cur.fetchone()
    if existing:
        return existing

    state = dict(run.get("state") or {})
    if state_patch:
        nodes = dict(state.get("nodes") or {})
        node_patch = state_patch.pop("_node", None)
        if node_patch is not None:
            nodes[node_key] = node_patch
            state["nodes"] = nodes
        state.update(state_patch)
    sequence = run["checkpoint_seq"] + 1
    state["graph_id"] = GRAPH_ID
    state["graph_version"] = GRAPH_VERSION
    state["current_node"] = current_node
    state["run_status"] = run_status
    state["checkpoint_sequence"] = sequence
    snapshot_sha256 = digest(state)
    checkpoint_id = uuid4()
    cur.execute(
        """INSERT INTO orchestration_checkpoints(
               id,run_id,sequence,node_key,run_status,event_type,state_snapshot,state_sha256,
               basis,actor_type,actor_id,idempotency_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
           RETURNING *""",
        (
            checkpoint_id,
            run["id"],
            sequence,
            node_key,
            run_status,
            event_type,
            _json(state),
            snapshot_sha256,
            basis,
            actor_type,
            actor_id,
            idempotency_key,
        ),
    )
    checkpoint = cur.fetchone()
    cur.execute(
        """UPDATE orchestration_runs SET status=%s,current_node=%s,state=%s::jsonb,
                   checkpoint_seq=%s,checkpoint_sha256=%s,version=version+1,
                   started_at=COALESCE(started_at,now()),
                   completed_at=CASE WHEN %s='COMPLETED' THEN COALESCE(completed_at,now()) ELSE completed_at END,
                   updated_at=now()
             WHERE id=%s RETURNING *""",
        (run_status, current_node, _json(state), sequence, snapshot_sha256, run_status, run["id"]),
    )
    updated = cur.fetchone()
    run.clear()
    run.update(updated)
    append_event(
        cur,
        project_id=run["project_id"],
        event_type="ORCHESTRATION_CHECKPOINT",
        object_type="ORCHESTRATION_RUN",
        object_id=str(run["id"]),
        actor_type=actor_type,
        actor_id=actor_id,
        payload={
            "event_type": event_type,
            "node_key": node_key,
            "run_status": run_status,
            "current_node": current_node,
            "checkpoint_sequence": sequence,
            "checkpoint_sha256": snapshot_sha256,
            "basis": basis,
        },
        source_version=run["version"] - 1,
        result_version=run["version"],
        idempotency_key=f"orchestration:{run['id']}:{idempotency_key}",
    )
    return checkpoint


def _open_attempt(
    cur,
    *,
    run: dict,
    node_key: str,
    status: str,
    input_summary: dict,
    worker_id: str | None,
) -> dict:
    cur.execute(
        """SELECT * FROM orchestration_node_attempts
           WHERE run_id=%s AND node_key=%s AND finished_at IS NULL FOR UPDATE""",
        (run["id"], node_key),
    )
    existing = cur.fetchone()
    if existing:
        return existing
    cur.execute(
        "SELECT COALESCE(max(attempt_no),0)+1 AS attempt_no FROM orchestration_node_attempts WHERE run_id=%s AND node_key=%s",
        (run["id"], node_key),
    )
    attempt_no = cur.fetchone()["attempt_no"]
    cur.execute(
        """INSERT INTO orchestration_node_attempts(
               id,run_id,node_key,attempt_no,status,input_sha256,input_summary,worker_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
        (
            uuid4(),
            run["id"],
            node_key,
            attempt_no,
            status,
            digest(input_summary),
            _json(input_summary),
            worker_id,
        ),
    )
    return cur.fetchone()


def _finish_attempt(
    cur,
    *,
    attempt_id,
    status: str,
    output_summary: dict,
    error_code: str | None = None,
) -> dict:
    cur.execute(
        """UPDATE orchestration_node_attempts
           SET status=%s,output_sha256=%s,output_summary=%s::jsonb,error_code=%s,finished_at=now()
           WHERE id=%s RETURNING *""",
        (status, digest(output_summary), _json(output_summary), error_code, attempt_id),
    )
    return cur.fetchone()


def _complete_instant_node(
    cur,
    *,
    run: dict,
    node_key: str,
    input_summary: dict,
    output_summary: dict,
    actor_type: str,
    actor_id: str,
    next_node: str | None = None,
    next_status: str = "RUNNING",
    idempotency_key: str | None = None,
) -> dict:
    key = idempotency_key or f"{node_key.lower()}:completed"
    cur.execute(
        """SELECT * FROM orchestration_checkpoints
           WHERE run_id=%s AND idempotency_key=%s""",
        (run["id"], key),
    )
    if cur.fetchone():
        return run
    attempt = _open_attempt(
        cur,
        run=run,
        node_key=node_key,
        status="RUNNING",
        input_summary=input_summary,
        worker_id=actor_id,
    )
    _finish_attempt(cur, attempt_id=attempt["id"], status="COMPLETED", output_summary=output_summary)
    _checkpoint(
        cur,
        run=run,
        node_key=node_key,
        run_status=next_status,
        current_node=next_node or _next_node(node_key),
        event_type="NODE_COMPLETED",
        state_patch={"_node": {"status": "COMPLETED", "output": output_summary}},
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=key,
    )
    return run


def create_native_run(
    cur,
    *,
    project: dict,
    claim: dict,
    job_id,
    snapshot_id,
    snapshot_sha256: str,
    mode: str,
    actor_id: str,
    included_evidence_ids: list[str],
    excluded_evidence: list[dict],
    retrieval_run_id,
    retrieved_chunk_ids: list[str],
    retrieval_receipt_sha256: str | None,
) -> dict:
    existing = _run_for_job(cur, job_id)
    if existing:
        return existing
    run = {
        "id": uuid4(),
        "project_id": project["id"],
        "job_id": job_id,
        "graph_id": GRAPH_ID,
        "graph_version": GRAPH_VERSION,
        "origin": "NATIVE",
        "status": "RUNNING",
        "current_node": "SELECT_TASK",
        "state": {
            "job_id": str(job_id),
            "snapshot_id": str(snapshot_id),
            "mode": mode,
            "claim_id": str(claim["id"]),
            "claim_version": claim["version"],
            "project_version": project["version"],
            "nodes": {},
        },
        "checkpoint_seq": 0,
        "version": 1,
    }
    cur.execute(
        """INSERT INTO orchestration_runs(
               id,project_id,job_id,graph_id,graph_version,origin,status,current_node,state,started_at)
           VALUES (%s,%s,%s,%s,%s,'NATIVE','RUNNING','SELECT_TASK',%s::jsonb,now()) RETURNING *""",
        (run["id"], project["id"], job_id, GRAPH_ID, GRAPH_VERSION, _json(run["state"])),
    )
    run = cur.fetchone()
    _complete_instant_node(
        cur,
        run=run,
        node_key="SELECT_TASK",
        input_summary={"project_id": str(project["id"]), "claim_id": str(claim["id"])},
        output_summary={"job_id": str(job_id), "mode": mode, "review_target": claim["review_target"]},
        actor_type="HUMAN",
        actor_id=actor_id,
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="SCOPE_GATE",
        input_summary={"claim_version": claim["version"], "project_version": project["version"]},
        output_summary={
            "included_count": len(included_evidence_ids),
            "excluded_count": len(excluded_evidence),
            "scope_gate": "PASSED",
        },
        actor_type="SYSTEM",
        actor_id="api",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="RETRIEVE_CONTEXT",
        input_summary={"retrieval_run_id": str(retrieval_run_id) if retrieval_run_id else None},
        output_summary={
            "direct_evidence_count": len(included_evidence_ids) - len(retrieved_chunk_ids),
            "retrieved_chunk_count": len(retrieved_chunk_ids),
            "retrieval_receipt_sha256": retrieval_receipt_sha256,
        },
        actor_type="TOOL",
        actor_id="document-rag-v1",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="BUILD_CONTEXT",
        input_summary={"included_evidence_ids": included_evidence_ids},
        output_summary={"snapshot_id": str(snapshot_id), "snapshot_sha256": snapshot_sha256},
        actor_type="SYSTEM",
        actor_id="context-builder",
        next_status="QUEUED",
    )
    return run


def begin_source_review(cur, *, job_id, worker_id: str) -> dict | None:
    run = _run_for_job(cur, job_id, lock=True)
    if not run:
        return None
    attempt = _open_attempt(
        cur,
        run=run,
        node_key="SOURCE_REVIEW",
        status="RUNNING",
        input_summary={"job_id": str(job_id), "mode": run["state"].get("mode")},
        worker_id=worker_id,
    )
    _checkpoint(
        cur,
        run=run,
        node_key="SOURCE_REVIEW",
        run_status="RUNNING",
        current_node="SOURCE_REVIEW",
        event_type="NODE_STARTED",
        state_patch={"_node": {"status": "RUNNING", "attempt_no": attempt["attempt_no"]}},
        actor_type="SYSTEM",
        actor_id=worker_id,
        idempotency_key=f"source-review:attempt:{attempt['attempt_no']}:started",
    )
    return attempt


def complete_worker_path(
    cur,
    *,
    job: dict,
    model_run_id,
    raw_sha256: str,
    receipt: dict,
    validation_id,
    validation_status: str,
    validation_errors: list,
    contribution_count: int,
    work_item_count: int,
) -> None:
    run = _run_for_job(cur, job["id"], lock=True)
    attempt_id = job.get("orchestration_attempt_id")
    if not run or not attempt_id:
        return
    source_output = {
        "model_run_id": str(model_run_id),
        "raw_sha256": raw_sha256,
        "request_id": receipt.get("request_id"),
        "boot_id": receipt.get("boot_id"),
        "model_receipt_id": receipt.get("model_receipt_id"),
    }
    _finish_attempt(cur, attempt_id=attempt_id, status="COMPLETED", output_summary=source_output)
    _checkpoint(
        cur,
        run=run,
        node_key="SOURCE_REVIEW",
        run_status="RUNNING",
        current_node="VALIDATE",
        event_type="NODE_COMPLETED",
        state_patch={"_node": {"status": "COMPLETED", "output": source_output}},
        actor_type="MODEL" if job["mode"] == "LIVE_MODEL_RUN" else "TOOL",
        actor_id=job["model_profile"],
        idempotency_key=f"source-review:attempt:{attempt_id}:completed",
    )
    validation_output = {
        "validation_id": str(validation_id),
        "status": validation_status,
        "error_count": len(validation_errors),
        "errors": validation_errors,
    }
    if validation_status != "VALID":
        attempt = _open_attempt(
            cur,
            run=run,
            node_key="VALIDATE",
            status="RUNNING",
            input_summary={"model_run_id": str(model_run_id), "raw_sha256": raw_sha256},
            worker_id="validator",
        )
        _finish_attempt(
            cur,
            attempt_id=attempt["id"],
            status="FAILED",
            output_summary=validation_output,
            error_code="OUTPUT_VALIDATION_FAILED",
        )
        _checkpoint(
            cur,
            run=run,
            node_key="VALIDATE",
            run_status="FAILED",
            current_node="VALIDATE",
            event_type="NODE_FAILED",
            state_patch={"_node": {"status": "FAILED", "output": validation_output}},
            actor_type="SYSTEM",
            actor_id="validator",
            idempotency_key="validate:failed",
        )
        return
    _complete_instant_node(
        cur,
        run=run,
        node_key="VALIDATE",
        input_summary={"model_run_id": str(model_run_id), "raw_sha256": raw_sha256},
        output_summary=validation_output,
        actor_type="SYSTEM",
        actor_id="validator",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="UPDATE_BLACKBOARD",
        input_summary={"validation_id": str(validation_id)},
        output_summary={"contribution_count": contribution_count, "work_item_count": work_item_count},
        actor_type="SYSTEM",
        actor_id="blackboard-projector",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="ROUTE",
        input_summary={"validation_status": validation_status},
        output_summary={"next_node": "WAIT_HUMAN", "rule": "VALID_PROPOSAL_REQUIRES_HUMAN_REVIEW"},
        actor_type="SYSTEM",
        actor_id="fixed-router-v1",
        next_status="RUNNING",
    )
    waiting = _open_attempt(
        cur,
        run=run,
        node_key="WAIT_HUMAN",
        status="WAITING",
        input_summary={"job_id": str(job["id"]), "required_role": "reviewer_or_approver"},
        worker_id=None,
    )
    _checkpoint(
        cur,
        run=run,
        node_key="WAIT_HUMAN",
        run_status="WAITING_HUMAN",
        current_node="WAIT_HUMAN",
        event_type="NODE_WAITING",
        state_patch={"_node": {"status": "WAITING", "attempt_no": waiting["attempt_no"]}},
        actor_type="SYSTEM",
        actor_id="fixed-router-v1",
        idempotency_key="wait-human:started",
    )


def resume_after_human(cur, *, job_id, review: dict, actor_id: str) -> None:
    run = _run_for_job(cur, job_id, lock=True)
    if not run:
        return
    cur.execute(
        """SELECT * FROM orchestration_node_attempts
           WHERE run_id=%s AND node_key='WAIT_HUMAN' AND finished_at IS NULL FOR UPDATE""",
        (run["id"],),
    )
    waiting = cur.fetchone()
    decision = {
        "human_review_id": str(review["id"]),
        "disposition": review["disposition"],
        "actor": actor_id,
    }
    if waiting:
        _finish_attempt(cur, attempt_id=waiting["id"], status="COMPLETED", output_summary=decision)
    _checkpoint(
        cur,
        run=run,
        node_key="WAIT_HUMAN",
        run_status="RUNNING",
        current_node="RESUME",
        event_type="HUMAN_DECISION_RECEIVED",
        state_patch={"_node": {"status": "COMPLETED", "output": decision}, "human_decision": decision},
        actor_type="HUMAN",
        actor_id=actor_id,
        idempotency_key=f"wait-human:decision:{review['id']}",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="RESUME",
        input_summary=decision,
        output_summary={"job_status": "COMPLETED", "duplicate_model_call": False},
        actor_type="SYSTEM",
        actor_id="orchestrator",
    )
    _complete_instant_node(
        cur,
        run=run,
        node_key="COMPLETE",
        input_summary={"human_review_id": str(review["id"])},
        output_summary={"execution_complete": True, "formal_verification_approval": False},
        actor_type="SYSTEM",
        actor_id="orchestrator",
        next_node="COMPLETE",
        next_status="COMPLETED",
    )


def fail_source_review(cur, *, job: dict, status: str, error_code: str, detail: str) -> None:
    run = _run_for_job(cur, job["id"], lock=True)
    if not run:
        return
    attempt_id = job.get("orchestration_attempt_id")
    if attempt_id:
        attempt_status = "UNKNOWN_OUTCOME" if status == "UNKNOWN_OUTCOME" else "FAILED"
        _finish_attempt(
            cur,
            attempt_id=attempt_id,
            status=attempt_status,
            output_summary={"error_code": error_code},
            error_code=error_code,
        )
    run_status = "QUEUED" if status == "QUEUED" else status
    _checkpoint(
        cur,
        run=run,
        node_key="SOURCE_REVIEW",
        run_status=run_status,
        current_node="SOURCE_REVIEW",
        event_type="NODE_RETRY_SCHEDULED" if status == "QUEUED" else "NODE_FAILED",
        state_patch={"_node": {"status": run_status, "error_code": error_code}, "last_error": error_code},
        actor_type="SYSTEM",
        actor_id=job.get("leased_by") or "worker",
        idempotency_key=f"source-review:{job.get('attempt_id')}:{run_status.lower()}:{error_code}",
    )


def recover_source_review(cur, *, job_id, live: bool) -> None:
    run = _run_for_job(cur, job_id, lock=True)
    if not run:
        return
    cur.execute(
        """SELECT * FROM orchestration_node_attempts
           WHERE run_id=%s AND node_key='SOURCE_REVIEW' AND finished_at IS NULL FOR UPDATE""",
        (run["id"],),
    )
    attempt = cur.fetchone()
    result_status = "UNKNOWN_OUTCOME" if live else "RECOVERED"
    if attempt:
        _finish_attempt(
            cur,
            attempt_id=attempt["id"],
            status=result_status,
            output_summary={"lease_expired": True, "safe_to_requeue": not live},
            error_code="UNKNOWN_OUTCOME" if live else "WORKER_RECOVERED",
        )
    _checkpoint(
        cur,
        run=run,
        node_key="SOURCE_REVIEW",
        run_status="UNKNOWN_OUTCOME" if live else "QUEUED",
        current_node="SOURCE_REVIEW",
        event_type="LEASE_EXPIRED",
        state_patch={"_node": {"status": result_status}},
        actor_type="SYSTEM",
        actor_id="worker-recovery",
        idempotency_key=f"source-review:recovery:{attempt['id'] if attempt else job_id}:{result_status}",
    )


def mark_stale(cur, *, job_id, actor_id: str, reason: str) -> None:
    run = _run_for_job(cur, job_id, lock=True)
    if not run or run["status"] == "STALE":
        return
    _checkpoint(
        cur,
        run=run,
        node_key=run["current_node"],
        run_status="STALE",
        current_node=run["current_node"],
        event_type="INPUT_BECAME_STALE",
        state_patch={"stale_reason": reason},
        actor_type="SYSTEM",
        actor_id=actor_id,
        idempotency_key=f"stale:{reason}:{run['version']}",
    )


def backfill_legacy_runs(cur) -> None:
    cur.execute(
        """SELECT j.*,cs.claim_version,cs.project_version,cs.snapshot_sha256,
                  mr.id AS model_run_id,v.status AS validation_status,
                  (SELECT hr.id FROM human_reviews hr WHERE hr.job_id=j.id ORDER BY hr.created_at DESC LIMIT 1) AS review_id
           FROM review_jobs j JOIN context_snapshots cs ON cs.id=j.snapshot_id
           LEFT JOIN model_runs mr ON mr.job_id=j.id
           LEFT JOIN validations v ON v.model_run_id=mr.id
           WHERE NOT EXISTS (SELECT 1 FROM orchestration_runs r WHERE r.job_id=j.id)
           ORDER BY j.created_at"""
    )
    for job in cur.fetchall():
        if job["freshness"] == "STALE":
            current_node, status = "SOURCE_REVIEW", "STALE"
        elif job["status"] == "COMPLETED":
            current_node, status = "COMPLETE", "COMPLETED"
        elif job["status"] == "AWAITING_REVIEW":
            current_node, status = "WAIT_HUMAN", "WAITING_HUMAN"
        elif job["status"] in {"OUTPUT_REJECTED", "FAILED"}:
            current_node, status = "VALIDATE", "FAILED"
        elif job["status"] == "UNKNOWN_OUTCOME":
            current_node, status = "SOURCE_REVIEW", "UNKNOWN_OUTCOME"
        elif job["status"] == "QUEUED":
            current_node, status = "SOURCE_REVIEW", "QUEUED"
        else:
            current_node, status = "SOURCE_REVIEW", "RUNNING"
        run_id = uuid4()
        state = {
            "graph_id": GRAPH_ID,
            "graph_version": GRAPH_VERSION,
            "job_id": str(job["id"]),
            "snapshot_id": str(job["snapshot_id"]),
            "claim_version": job["claim_version"],
            "project_version": job["project_version"],
            "mode": job["mode"],
            "legacy_projection": True,
            "projection_basis": {
                "job_status": job["status"],
                "freshness": job["freshness"],
                "model_run_id": str(job["model_run_id"]) if job["model_run_id"] else None,
                "validation_status": job["validation_status"],
                "human_review_id": str(job["review_id"]) if job["review_id"] else None,
            },
            "current_node": current_node,
            "run_status": status,
            "checkpoint_sequence": 1,
        }
        state_sha256 = digest(state)
        cur.execute(
            """INSERT INTO orchestration_runs(
                   id,project_id,job_id,graph_id,graph_version,origin,status,current_node,state,
                   checkpoint_seq,checkpoint_sha256,started_at,completed_at)
               VALUES (%s,%s,%s,%s,%s,'LEGACY_PROJECTION',%s,%s,%s::jsonb,1,%s,%s,
                       CASE WHEN %s='COMPLETED' THEN %s ELSE NULL END)""",
            (
                run_id,
                job["project_id"],
                job["id"],
                GRAPH_ID,
                GRAPH_VERSION,
                status,
                current_node,
                _json(state),
                state_sha256,
                job["created_at"],
                status,
                job["updated_at"],
            ),
        )
        cur.execute(
            """INSERT INTO orchestration_checkpoints(
                   id,run_id,sequence,node_key,run_status,event_type,state_snapshot,state_sha256,
                   basis,actor_type,actor_id,idempotency_key,created_at)
               VALUES (%s,%s,1,%s,%s,'LEGACY_STATE_PROJECTED',%s::jsonb,%s,
                       'LEGACY_PROJECTION','SYSTEM','migration','legacy-projection',%s)""",
            (uuid4(), run_id, current_node, status, _json(state), state_sha256, job["updated_at"]),
        )


def orchestration_projection(cur, job_id) -> dict | None:
    run = _run_for_job(cur, job_id)
    if not run:
        return None
    cur.execute(
        """SELECT DISTINCT ON (node_key) * FROM orchestration_node_attempts
           WHERE run_id=%s ORDER BY node_key,attempt_no DESC""",
        (run["id"],),
    )
    attempts = {row["node_key"]: row for row in cur.fetchall()}
    current_index = NODE_KEYS.index(run["current_node"])
    nodes = []
    for index, (key, label, description) in enumerate(GRAPH_NODES):
        attempt = attempts.get(key)
        if attempt:
            node_status = attempt["status"]
        elif run["origin"] == "LEGACY_PROJECTION" and index < current_index:
            node_status = "PROJECTED_COMPLETED"
        elif key == run["current_node"]:
            node_status = {
                "QUEUED": "READY",
                "WAITING_HUMAN": "WAITING",
                "COMPLETED": "COMPLETED",
            }.get(run["status"], run["status"])
        else:
            node_status = "PENDING"
        nodes.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "status": node_status,
                "attempt": attempt,
            }
        )
    cur.execute(
        "SELECT * FROM orchestration_checkpoints WHERE run_id=%s ORDER BY sequence",
        (run["id"],),
    )
    checkpoints = cur.fetchall()
    return {
        "schema_id": "dorilab.orchestration-trace.v1",
        "graph": {"id": GRAPH_ID, "version": GRAPH_VERSION, "nodes": list(NODE_KEYS)},
        "run": run,
        "nodes": nodes,
        "checkpoints": checkpoints,
        "integrity": {
            "checkpoint_count": len(checkpoints),
            "latest_sha256": run["checkpoint_sha256"],
            "hash_basis": "APP_SHA256" if run["origin"] == "NATIVE" else "LEGACY_PROJECTION",
        },
    }
