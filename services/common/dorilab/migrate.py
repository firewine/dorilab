from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from .blackboard import append_event, create_contribution, create_work_item
from .db import connection
from .gates import seed_project_gates
from .orchestration import backfill_legacy_runs


MIGRATIONS = Path("/app/migrations")
DEMO_PROJECT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_CLAIM = UUID("00000000-0000-4000-8000-000000000101")
DEMO_REQUIREMENTS = [
    (UUID("00000000-0000-4000-8000-000000000201"), "MIS-001", "MISSION", "ConOps-01",
     "정의된 열환경에서 관측 임무를 수행한다.", "운용 시나리오 확인", "시스템 담당", None, "임무 적합성", 3, 1, "UNSPECIFIED"),
    (UUID("00000000-0000-4000-8000-000000000202"), "THM-041", "EQUIPMENT", "SYS-THERM",
     "상관해석 입력에 부품별 소산전력과 열원 위치를 연결한다.", "자료 검토", "열설계 담당", DEMO_CLAIM, "CLM-TH-INPUT", 19, 2, "INPUT_READINESS"),
    (UUID("00000000-0000-4000-8000-000000000203"), "THM-042", "EQUIPMENT", "SYS-THERM",
     "같은 물리량의 온도 잔차를 상관 기준과 비교한다.", "분석과 시험", "해석 담당", None, "CLM-TH-CORR", 19, 3, "PRODUCT_PERFORMANCE"),
    (UUID("00000000-0000-4000-8000-000000000204"), "MEC-011", "EQUIPMENT", "SYS-STRUCT",
     "하중 방향과 모드 특성에 맞는 검증 근거를 확보한다.", "분석과 시험", "구조 담당", None, "CLM-MEC-011", 17, 4, "UNSPECIFIED"),
    (UUID("00000000-0000-4000-8000-000000000205"), "EEE-021", "EQUIPMENT", "SYS-EPS",
     "운용모드별 기능 관측과 시험조건을 연결한다.", "기능 시험", "전장 담당", None, "CLM-EEE-021", 17, 5, "UNSPECIFIED"),
]


def apply_migrations() -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        for path in sorted(MIGRATIONS.glob("*.sql")):
            cur.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (path.name,))
            if cur.fetchone():
                continue
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (path.name,))
        seed(cur)
        backfill_blackboard(cur)
        backfill_legacy_runs(cur)


def seed(cur) -> None:
    users = [
        ("engineer@demo", "Demo Engineer"),
        ("reviewer@demo", "Demo Reviewer"),
        ("approver@demo", "Demo Authority"),
        ("viewer@demo", "Demo Viewer"),
    ]
    cur.executemany(
        "INSERT INTO users(id, display_name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
        users,
    )
    cur.execute(
        """INSERT INTO projects(id, display_id, name, framework, framework_edition,
               adoption_status, data_policy, mode)
           VALUES (%s,'DORI-01','DORI-01 관측위성','KASA',NULL,'UNCONFIRMED',
                   'EXTERNAL_SYNTHETIC_ALLOWED','DEMO')
           ON CONFLICT (id) DO NOTHING""",
        (DEMO_PROJECT,),
    )
    cur.execute(
        """UPDATE projects SET display_id='DORI-01',name='DORI-01 관측위성'
           WHERE id=%s AND display_id='DORI-DEMO'""",
        (DEMO_PROJECT,),
    )
    cur.execute(
        """UPDATE projects SET baseline_display_id='BL-003',product_configuration='Rev.C',test_run='TVAC-03'
           WHERE id=%s AND baseline_display_id='BL-001' AND product_configuration='UNASSIGNED' AND test_run='UNASSIGNED'""",
        (DEMO_PROJECT,),
    )
    cur.execute("UPDATE projects SET current_phase=4 WHERE id=%s AND current_phase=0", (DEMO_PROJECT,))
    cur.executemany(
        """INSERT INTO memberships(project_id,user_id,role) VALUES (%s,%s,%s)
           ON CONFLICT (project_id,user_id) DO NOTHING""",
        [
            (DEMO_PROJECT, "engineer@demo", "engineer"),
            (DEMO_PROJECT, "reviewer@demo", "reviewer"),
            (DEMO_PROJECT, "approver@demo", "approver"),
            (DEMO_PROJECT, "viewer@demo", "viewer"),
        ],
    )
    cur.execute(
        """INSERT INTO claims(id,project_id,display_id,question,review_target,scope,created_by,review_purpose)
           VALUES (%s,%s,'THM-041','TVAC-03 열모델 상관 검토에 필요한 근거가 충분한가?',
                   'BM1',%s::jsonb,'engineer@demo','INPUT_READINESS') ON CONFLICT (id) DO NOTHING""",
        (
            DEMO_CLAIM,
            DEMO_PROJECT,
            json.dumps({"unit": "DORI-01", "configuration": "TVAC-03", "run": "RUN-DEMO-01"}),
        ),
    )
    cur.execute(
        """INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,created_at,review_purpose)
           SELECT id,project_id,version,question,scope,status,created_by,created_at,review_purpose FROM claims WHERE id=%s
           ON CONFLICT (claim_id,version) DO NOTHING""",
        (DEMO_CLAIM,),
    )
    cur.executemany(
        """INSERT INTO requirements(id,project_id,display_id,level,parent_ref,statement,
                   verification_method,owner,claim_id,claim_label,source_chapter,sort_order,review_purpose,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'engineer@demo')
           ON CONFLICT (id) DO NOTHING""",
        [(item[0], DEMO_PROJECT, *item[1:]) for item in DEMO_REQUIREMENTS],
    )
    seed_project_gates(cur, DEMO_PROJECT, "KASA", "engineer@demo")
    payload = json.dumps({"seed": "demo", "project": str(DEMO_PROJECT)}, sort_keys=True)
    cur.execute(
        """INSERT INTO audit_events(project_id,actor,action,object_type,object_id,payload_hash)
           SELECT %s,'system','SEED','project',%s,%s
           WHERE NOT EXISTS (SELECT 1 FROM audit_events WHERE action='SEED' AND object_id=%s)""",
        (DEMO_PROJECT, str(DEMO_PROJECT), hashlib.sha256(payload.encode()).hexdigest(), str(DEMO_PROJECT)),
    )


def backfill_blackboard(cur) -> None:
    """Project immutable legacy review records into Blackboard v1 without rerunning models."""
    cur.execute(
        """SELECT j.id AS job_id,j.project_id,j.claim_id,j.created_by,cs.id AS snapshot_id,
                  cs.project_version,cs.claim_version,cs.model_profile,cs.included_evidence_ids,
                  v.parsed_output,
                  (SELECT hr.disposition FROM human_reviews hr WHERE hr.job_id=j.id
                   ORDER BY hr.created_at DESC LIMIT 1) AS human_disposition,
                  (SELECT hr.actor FROM human_reviews hr WHERE hr.job_id=j.id
                   ORDER BY hr.created_at DESC LIMIT 1) AS human_actor,
                  (SELECT hr.note FROM human_reviews hr WHERE hr.job_id=j.id
                   ORDER BY hr.created_at DESC LIMIT 1) AS human_note
           FROM review_jobs j JOIN context_snapshots cs ON cs.id=j.snapshot_id
           JOIN model_runs mr ON mr.job_id=j.id JOIN validations v ON v.model_run_id=mr.id
           WHERE v.status='VALID'
             AND NOT EXISTS (SELECT 1 FROM agent_contributions ac WHERE ac.source_job_id=j.id)
           ORDER BY j.created_at"""
    )
    jobs = cur.fetchall()
    for job in jobs:
        parsed = job["parsed_output"] or {}
        actions = parsed.get("actions") or [parsed]
        for action_index, action in enumerate(actions):
            action_name = action.get("action")
            if not action_name:
                continue
            contribution_type = "CHALLENGE" if action_name in {"CHALLENGE", "CONTRADICT"} else "FINDING"
            contribution, _ = create_contribution(
                cur,
                project_id=job["project_id"],
                claim_id=job["claim_id"],
                contribution_type=contribution_type,
                target_object_type="CLAIM",
                target_object_id=job["claim_id"],
                content=action,
                evidence_refs=[str(value) for value in action.get("evidence_refs", [])],
                actor_type="MODEL",
                actor_id=job["model_profile"],
                read_project_version=job["project_version"],
                read_claim_version=job["claim_version"],
                idempotency_key=f"review-job:{job['job_id']}:action:{action_index}",
                source_snapshot_id=job["snapshot_id"],
                source_job_id=job["job_id"],
                action_index=action_index,
            )
            if job["human_disposition"]:
                status = {
                    "ACCEPTED": "ACCEPTED",
                    "REVISION_REQUESTED": "REVISION_REQUESTED",
                    "REJECTED": "REJECTED",
                }[job["human_disposition"]]
                cur.execute(
                    """UPDATE agent_contributions SET status=%s,reviewed_by=%s,review_note=%s,
                              decided_at=now(),version=version+1,updated_at=now()
                       WHERE id=%s RETURNING version""",
                    (status, job["human_actor"], job["human_note"], contribution["id"]),
                )
                result_version = cur.fetchone()["version"]
                append_event(
                    cur,
                    project_id=job["project_id"],
                    event_type="CONTRIBUTION_DECIDED",
                    object_type="CONTRIBUTION",
                    object_id=str(contribution["id"]),
                    actor_type="HUMAN",
                    actor_id=job["human_actor"],
                    payload={"source": "LEGACY_HUMAN_REVIEW", "disposition": status},
                    source_version=1,
                    result_version=result_version,
                    idempotency_key=f"review:{job['job_id']}:contribution:{contribution['id']}:backfill",
                )

    cur.execute(
        """SELECT er.*,cs.project_version,cs.claim_version,cs.model_profile,
                  ac.id AS contribution_id
           FROM evidence_requests er JOIN review_jobs j ON j.id=er.job_id
           JOIN context_snapshots cs ON cs.id=j.snapshot_id
           LEFT JOIN LATERAL (
             SELECT id FROM agent_contributions WHERE source_job_id=j.id ORDER BY action_index LIMIT 1
           ) ac ON true
           WHERE NOT EXISTS (SELECT 1 FROM work_items wi WHERE wi.evidence_request_id=er.id)
           ORDER BY er.created_at"""
    )
    requests = cur.fetchall()
    for request in requests:
        work_status = {
            "OPEN": "WAITING_INPUT",
            "RECEIVED": "WAITING_REVIEW",
            "ACCEPTED": "COMPLETED",
            "REJECTED": "REJECTED",
        }[request["status"]]
        input_refs = [
            {"object_type": "CLAIM", "object_id": str(request["claim_id"]), "version": request["claim_version"]}
        ]
        if request["submitted_evidence_id"]:
            input_refs.append({"object_type": "EVIDENCE", "object_id": str(request["submitted_evidence_id"])})
        create_work_item(
            cur,
            project_id=request["project_id"],
            claim_id=request["claim_id"],
            work_type="EVIDENCE_REQUEST",
            title=f"근거 요청 · {request['requested_item'][:240]}",
            purpose=request["requested_item"],
            input_refs=input_refs,
            assigned_role="EVIDENCE",
            budget={"model_calls": 0, "requires_human_submission": True},
            status=work_status,
            idempotency_key=f"legacy-evidence-request:{request['id']}",
            actor_type="MODEL" if request["source"] == "MODEL" else "HUMAN",
            actor_id=request["model_profile"] if request["source"] == "MODEL" else request["created_by"],
            source_project_version=request["project_version"],
            source_claim_version=request["claim_version"],
            source_contribution_id=request["contribution_id"],
            source_job_id=request["job_id"],
            evidence_request_id=request["id"],
        )


if __name__ == "__main__":
    apply_migrations()
    print("migrations applied")
