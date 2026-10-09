from __future__ import annotations

import json
from uuid import UUID, uuid4

from .contracts import digest


CONTRIBUTION_TYPES = {"FACT_PROPOSAL", "FINDING", "HYPOTHESIS", "CHALLENGE"}
WORK_TYPES = {"TASK", "TOOL_REQUEST", "EVIDENCE_REQUEST"}
WORK_ROLES = {"EVIDENCE", "ANALYSIS", "CRITIC", "ROUTER", "HUMAN", "TOOL"}


def append_event(
    cur,
    *,
    project_id,
    event_type: str,
    object_type: str,
    object_id: str,
    actor_type: str,
    actor_id: str,
    payload: dict,
    idempotency_key: str,
    source_version: int | None = None,
    result_version: int | None = None,
) -> None:
    cur.execute(
        """INSERT INTO board_events(project_id,event_type,object_type,object_id,actor_type,actor_id,
                   payload,source_version,result_version,idempotency_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
           ON CONFLICT (project_id,idempotency_key) DO NOTHING""",
        (
            project_id,
            event_type,
            object_type,
            object_id,
            actor_type,
            actor_id,
            json.dumps(payload, ensure_ascii=False),
            source_version,
            result_version,
            idempotency_key,
        ),
    )


def link_dependency(
    cur,
    *,
    project_id,
    upstream_type: str,
    upstream_id,
    upstream_version: int,
    downstream_type: str,
    downstream_id,
    downstream_version: int,
    relationship: str,
    actor_type: str,
    actor_id: str,
    source_job_id=None,
) -> None:
    cur.execute(
        """INSERT INTO object_dependencies(project_id,upstream_object_type,upstream_object_id,
                   upstream_version,downstream_object_type,downstream_object_id,downstream_version,
                   relationship,source_job_id,created_by_type,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        (
            project_id,
            upstream_type,
            str(upstream_id),
            upstream_version,
            downstream_type,
            str(downstream_id),
            downstream_version,
            relationship,
            source_job_id,
            actor_type,
            actor_id,
        ),
    )


def create_contribution(
    cur,
    *,
    project_id,
    claim_id,
    contribution_type: str,
    target_object_type: str,
    target_object_id,
    content: dict,
    evidence_refs: list[str],
    actor_type: str,
    actor_id: str,
    read_project_version: int,
    read_claim_version: int | None,
    idempotency_key: str,
    source_snapshot_id=None,
    source_job_id=None,
    action_index: int | None = None,
) -> tuple[dict, bool]:
    value_hash = digest(
        {
            "claim_id": str(claim_id) if claim_id else None,
            "contribution_type": contribution_type,
            "target_object_type": target_object_type,
            "target_object_id": str(target_object_id),
            "content": content,
            "evidence_refs": sorted(evidence_refs),
            "read_project_version": read_project_version,
            "read_claim_version": read_claim_version,
        }
    )
    cur.execute(
        "SELECT * FROM agent_contributions WHERE project_id=%s AND idempotency_key=%s",
        (project_id, idempotency_key),
    )
    existing = cur.fetchone()
    if existing:
        if existing["content_hash"] != value_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return existing, True

    contribution_id = uuid4()
    cur.execute(
        """INSERT INTO agent_contributions(id,project_id,claim_id,contribution_type,
                   target_object_type,target_object_id,content,evidence_refs,actor_type,actor_id,
                   source_snapshot_id,source_job_id,action_index,read_project_version,
                   read_claim_version,content_hash,idempotency_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING *""",
        (
            contribution_id,
            project_id,
            claim_id,
            contribution_type,
            target_object_type,
            str(target_object_id),
            json.dumps(content, ensure_ascii=False),
            json.dumps(evidence_refs),
            actor_type,
            actor_id,
            source_snapshot_id,
            source_job_id,
            action_index,
            read_project_version,
            read_claim_version,
            value_hash,
            idempotency_key,
        ),
    )
    row = cur.fetchone()
    append_event(
        cur,
        project_id=project_id,
        event_type="CONTRIBUTION_PROPOSED",
        object_type="CONTRIBUTION",
        object_id=str(contribution_id),
        actor_type=actor_type,
        actor_id=actor_id,
        payload={
            "contribution_type": contribution_type,
            "target_object_type": target_object_type,
            "target_object_id": str(target_object_id),
            "evidence_refs": evidence_refs,
            "content_hash": value_hash,
        },
        source_version=None,
        result_version=1,
        idempotency_key=f"{idempotency_key}:event:proposed",
    )
    for evidence_id in evidence_refs:
        cur.execute(
            "SELECT version FROM evidence WHERE id=%s AND project_id=%s",
            (evidence_id, project_id),
        )
        source = cur.fetchone()
        upstream_type = "EVIDENCE"
        if not source:
            cur.execute(
                "SELECT version FROM document_chunks WHERE id=%s AND project_id=%s",
                (evidence_id, project_id),
            )
            source = cur.fetchone()
            upstream_type = "DOCUMENT_CHUNK"
        if source:
            link_dependency(
                cur,
                project_id=project_id,
                upstream_type=upstream_type,
                upstream_id=evidence_id,
                upstream_version=source["version"],
                downstream_type="CONTRIBUTION",
                downstream_id=contribution_id,
                downstream_version=1,
                relationship="DERIVED_FROM",
                actor_type=actor_type,
                actor_id=actor_id,
                source_job_id=source_job_id,
            )
    if claim_id and read_claim_version:
        link_dependency(
            cur,
            project_id=project_id,
            upstream_type="CLAIM",
            upstream_id=claim_id,
            upstream_version=read_claim_version,
            downstream_type="CONTRIBUTION",
            downstream_id=contribution_id,
            downstream_version=1,
            relationship="CONSTRAINS",
            actor_type=actor_type,
            actor_id=actor_id,
            source_job_id=source_job_id,
        )
    return row, False


def create_work_item(
    cur,
    *,
    project_id,
    claim_id,
    work_type: str,
    title: str,
    purpose: str,
    input_refs: list[dict],
    assigned_role: str,
    budget: dict,
    status: str,
    idempotency_key: str,
    actor_type: str,
    actor_id: str,
    source_project_version: int,
    source_claim_version: int | None,
    source_contribution_id=None,
    source_job_id=None,
    evidence_request_id=None,
) -> tuple[dict, bool]:
    cur.execute(
        "SELECT * FROM work_items WHERE project_id=%s AND idempotency_key=%s",
        (project_id, idempotency_key),
    )
    existing = cur.fetchone()
    if existing:
        expected = digest(
            {
                "claim_id": str(claim_id) if claim_id else None,
                "work_type": work_type,
                "title": title,
                "purpose": purpose,
                "input_refs": input_refs,
                "assigned_role": assigned_role,
                "budget": budget,
                "source_project_version": source_project_version,
                "source_claim_version": source_claim_version,
            }
        )
        actual = digest(
            {
                "claim_id": str(existing["claim_id"]) if existing["claim_id"] else None,
                "work_type": existing["work_type"],
                "title": existing["title"],
                "purpose": existing["purpose"],
                "input_refs": existing["input_refs"],
                "assigned_role": existing["assigned_role"],
                "budget": existing["budget"],
                "source_project_version": existing["source_project_version"],
                "source_claim_version": existing["source_claim_version"],
            }
        )
        if actual != expected:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return existing, True

    work_item_id = uuid4()
    cur.execute(
        """INSERT INTO work_items(id,project_id,claim_id,work_type,title,purpose,input_refs,
                   assigned_role,budget,status,idempotency_key,source_contribution_id,source_job_id,
                   evidence_request_id,source_project_version,source_claim_version,actor_type,actor_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING *""",
        (
            work_item_id,
            project_id,
            claim_id,
            work_type,
            title,
            purpose,
            json.dumps(input_refs, ensure_ascii=False),
            assigned_role,
            json.dumps(budget),
            status,
            idempotency_key,
            source_contribution_id,
            source_job_id,
            evidence_request_id,
            source_project_version,
            source_claim_version,
            actor_type,
            actor_id,
        ),
    )
    row = cur.fetchone()
    append_event(
        cur,
        project_id=project_id,
        event_type="WORK_ITEM_CREATED",
        object_type="WORK_ITEM",
        object_id=str(work_item_id),
        actor_type=actor_type,
        actor_id=actor_id,
        payload={
            "work_type": work_type,
            "title": title,
            "assigned_role": assigned_role,
            "status": status,
        },
        result_version=1,
        idempotency_key=f"{idempotency_key}:event:created",
    )
    if source_contribution_id:
        link_dependency(
            cur,
            project_id=project_id,
            upstream_type="CONTRIBUTION",
            upstream_id=source_contribution_id,
            upstream_version=1,
            downstream_type="WORK_ITEM",
            downstream_id=work_item_id,
            downstream_version=1,
            relationship="REQUESTS",
            actor_type=actor_type,
            actor_id=actor_id,
            source_job_id=source_job_id,
        )
    return row, False


def board_projection(cur, project_id: UUID) -> dict:
    cur.execute(
        """SELECT id,display_id,name,framework,framework_edition,adoption_status,
                  baseline_display_id,product_configuration,test_run,current_phase,version
           FROM projects WHERE id=%s""",
        (project_id,),
    )
    project = cur.fetchone()
    cur.execute(
        """SELECT ac.*,c.display_id AS claim_display_id
           FROM agent_contributions ac LEFT JOIN claims c ON c.id=ac.claim_id
           WHERE ac.project_id=%s ORDER BY ac.created_at DESC LIMIT 200""",
        (project_id,),
    )
    contributions = cur.fetchall()
    cur.execute(
        """SELECT wi.*,c.display_id AS claim_display_id,er.status AS evidence_request_status
           FROM work_items wi LEFT JOIN claims c ON c.id=wi.claim_id
           LEFT JOIN evidence_requests er ON er.id=wi.evidence_request_id
           WHERE wi.project_id=%s ORDER BY wi.created_at DESC LIMIT 200""",
        (project_id,),
    )
    work_items = cur.fetchall()
    cur.execute(
        """SELECT * FROM object_dependencies WHERE project_id=%s AND active
           ORDER BY created_at DESC LIMIT 500""",
        (project_id,),
    )
    dependencies = cur.fetchall()
    cur.execute(
        """SELECT * FROM board_events WHERE project_id=%s ORDER BY created_at DESC LIMIT 200""",
        (project_id,),
    )
    events = cur.fetchall()
    cur.execute(
        """SELECT r.id,r.job_id,r.graph_id,r.graph_version,r.origin,r.status,r.current_node,
                  r.checkpoint_seq,r.checkpoint_sha256,r.version,r.created_at,r.updated_at,
                  j.claim_id,c.display_id AS claim_display_id,j.mode,j.freshness
           FROM orchestration_runs r JOIN review_jobs j ON j.id=r.job_id
           JOIN claims c ON c.id=j.claim_id
           WHERE r.project_id=%s ORDER BY r.updated_at DESC LIMIT 100""",
        (project_id,),
    )
    orchestration_runs = cur.fetchall()
    contribution_status = {}
    for row in contributions:
        contribution_status[row["status"]] = contribution_status.get(row["status"], 0) + 1
    work_status = {}
    for row in work_items:
        work_status[row["status"]] = work_status.get(row["status"], 0) + 1
    orchestration_status = {}
    for row in orchestration_runs:
        orchestration_status[row["status"]] = orchestration_status.get(row["status"], 0) + 1
    return {
        "schema_id": "dorilab.blackboard.v1",
        "project": project,
        "summary": {
            "contributions": len(contributions),
            "contribution_status": contribution_status,
            "work_items": len(work_items),
            "work_status": work_status,
            "dependencies": len(dependencies),
            "events": len(events),
            "orchestration_runs": len(orchestration_runs),
            "orchestration_status": orchestration_status,
        },
        "contributions": contributions,
        "work_items": work_items,
        "dependencies": dependencies,
        "events": events,
        "orchestration_runs": orchestration_runs,
    }
