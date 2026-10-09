from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5


GATE_KEYS = ("mission", "srr", "pdr", "cdr", "sir", "trr", "trb", "accept", "orr")
GATE_NAMES = {
    "KASA": {
        "mission": "임무 개념 검토", "srr": "SRR", "pdr": "PDR", "cdr": "CDR",
        "sir": "S-IRR", "trr": "TRR", "trb": "TRB", "accept": "제품 인수 검토", "orr": "운용 준비검토",
    },
    "ECSS": {
        "mission": "MDR", "srr": "SRR", "pdr": "PDR", "cdr": "CDR",
        "sir": "통합 준비검토", "trr": "TRR", "trb": "TRB", "accept": "AR", "orr": "ORR",
    },
    "NASA": {
        "mission": "MCR", "srr": "SRR", "pdr": "PDR", "cdr": "CDR",
        "sir": "SIR", "trr": "TRR", "trb": "시험 결과 검토", "accept": "SAR", "orr": "ORR",
    },
}
GATE_DESCRIPTIONS = {
    "mission": "임무 목적과 개념, 대안과 위험",
    "srr": "요구사항 기준점과 시스템 구조",
    "pdr": "예비 설계와 인터페이스, 검증 접근",
    "cdr": "상세 설계 기준점과 제작 준비",
    "sir": "통합 형상과 주요 조치사항",
    "trr": "시험 절차, 시설과 계측, 실행 범위",
    "trb": "시험목표와 결과, 부적합 처분",
    "accept": "납품 형상과 수준별 검증 기록",
    "orr": "운용 준비와 시스템 시나리오",
}

# Older projects retain seeded copy in their DB records. Only known system text
# gets the current display name; user text and stored history stay untouched.
LEGACY_GATE_DISPLAY_TEXT = {
    "요구사항 기준선과 시스템 구조": "요구사항 기준점과 시스템 구조",
    "상세 설계 기준선과 제작 준비": "상세 설계 기준점과 제작 준비",
    "프로젝트 기준선 등록": "프로젝트 기준점 등록",
    "현재 기준선의 설계 근거 등록": "현재 기준점의 설계 근거 등록",
    "통합 형상 기준선 등록": "통합 형상 기준점 등록",
    "현 기준선의 검증된 모델 결과": "현 기준점의 검증된 모델 결과",
}


def criterion(code: str, label: str, target: str | None = None) -> dict:
    value = {"code": code, "label": label}
    if target:
        value["target"] = target
    return value


GATE_CRITERIA = {
    "mission": (
        [criterion("BASELINE_PRESENT", "프로젝트 기준점 등록")],
        [criterion("REQUIREMENTS_PRESENT", "임무와 제품 요구사항 등록")],
    ),
    "srr": (
        [criterion("REQUIREMENTS_PRESENT", "요구사항 등록부 구성")],
        [criterion("CLAIM_LINK_PRESENT", "검토 Claim과 제품 요구 연결")],
    ),
    "pdr": (
        [criterion("REQUIREMENTS_PRESENT", "예비 설계 대상 요구사항 등록")],
        [criterion("ADOPTED_PROFILE_DOCUMENT", "채택 문서와 적용 조항 확인")],
    ),
    "cdr": (
        [criterion("ADOPTED_PROFILE_DOCUMENT", "상세 설계 적용 기준 채택")],
        [criterion("EVIDENCE_PRESENT", "현재 기준점의 설계 근거 등록")],
    ),
    "sir": (
        [criterion("BASELINE_PRESENT", "통합 형상 기준점 등록")],
        [criterion("EVIDENCE_PRESENT", "형상과 인터페이스 근거 등록")],
    ),
    "trr": (
        [criterion("EVIDENCE_PRESENT", "시험형상과 채널 대응 근거")],
        [criterion("NO_OPEN_EVIDENCE_REQUESTS", "미해결 자료 요청 없음")],
    ),
    "trb": (
        [criterion("ACCEPTED_REVIEW", "입력 완전성 검토 의견 수용")],
        [criterion("VALID_MODEL_RUN", "현 기준점의 검증된 모델 결과"), criterion("NO_OPEN_EVIDENCE_REQUESTS", "자료 요청 처리")],
    ),
    "accept": (
        [criterion("GATE_APPROVED", "시험 결과 검토 완료", "trb")],
        [criterion("ADOPTED_PROFILE_DOCUMENT", "납품 형상과 인계 문서 채택")],
    ),
    "orr": (
        [criterion("GATE_APPROVED", "제품 인수 검토 승인", "accept")],
        [criterion("OPS_CONFIRMATION", "운용 시나리오 확인 기록")],
    ),
}


def seed_project_gates(cur, project_id, framework: str, created_by: str) -> None:
    for sort_order, key in enumerate(GATE_KEYS, 1):
        entry, success = GATE_CRITERIA[key]
        gate_id = uuid5(NAMESPACE_URL, f"dorilab:{project_id}:{framework}:{key}")
        authority = "APPROVER" if key in {"accept", "orr"} else "REVIEWER_OR_APPROVER"
        cur.execute(
            """INSERT INTO review_gates(id,project_id,framework,gate_key,original_name,display_name,
                       product_level,description,entry_criteria,success_criteria,authority,source_chapter,
                       sort_order,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,'프로젝트 채택 제품 수준',%s,%s::jsonb,%s::jsonb,%s,4,%s,%s)
               ON CONFLICT (project_id,framework,gate_key) DO NOTHING""",
            (gate_id, project_id, framework, key, GATE_NAMES[framework][key], GATE_NAMES[framework][key],
             GATE_DESCRIPTIONS[key], json.dumps(entry, ensure_ascii=False), json.dumps(success, ensure_ascii=False),
             authority, sort_order, created_by),
        )


def _exists(cur, query: str, params: tuple) -> bool:
    cur.execute(query, params)
    return bool(cur.fetchone()["ok"])


def evaluate_criterion(cur, project: dict, framework: str, item: dict) -> dict:
    code = item["code"]
    project_id = project["id"]
    satisfied = False
    basis = "등록 기록 없음"
    if code == "BASELINE_PRESENT":
        satisfied = project["baseline_display_id"] not in {"", "UNASSIGNED"}
        basis = project["baseline_display_id"] if satisfied else "기준점 미등록"
    elif code == "REQUIREMENTS_PRESENT":
        satisfied = _exists(cur, "SELECT EXISTS(SELECT 1 FROM requirements WHERE project_id=%s) AS ok", (project_id,))
        basis = "요구사항 등록부" if satisfied else "요구사항 미등록"
    elif code == "CLAIM_LINK_PRESENT":
        satisfied = _exists(cur, "SELECT EXISTS(SELECT 1 FROM requirements WHERE project_id=%s AND claim_id IS NOT NULL) AS ok", (project_id,))
        basis = "요구사항-Claim 연결" if satisfied else "Claim 연결 없음"
    elif code == "ADOPTED_PROFILE_DOCUMENT":
        satisfied = _exists(
            cur,
            "SELECT EXISTS(SELECT 1 FROM project_documents WHERE project_id=%s AND profile=%s AND status='ADOPTED') AS ok",
            (project_id, framework),
        )
        basis = "채택 문서" if satisfied else "채택 승인 문서 없음"
    elif code == "EVIDENCE_PRESENT":
        satisfied = _exists(cur, "SELECT EXISTS(SELECT 1 FROM evidence WHERE project_id=%s) AS ok", (project_id,))
        basis = "프로젝트 Evidence" if satisfied else "Evidence 미등록"
    elif code == "ACCEPTED_REVIEW":
        satisfied = _exists(
            cur,
            """SELECT EXISTS(SELECT 1 FROM human_reviews hr JOIN review_jobs j ON j.id=hr.job_id
                   WHERE hr.project_id=%s AND hr.disposition='ACCEPTED' AND j.freshness='CURRENT') AS ok""",
            (project_id,),
        )
        basis = "현행 검토 초안 수용" if satisfied else "수용된 현행 검토 없음"
    elif code == "VALID_MODEL_RUN":
        satisfied = _exists(
            cur,
            """SELECT EXISTS(SELECT 1 FROM model_runs mr JOIN validations v ON v.model_run_id=mr.id
                   JOIN review_jobs j ON j.id=mr.job_id WHERE mr.project_id=%s AND v.status='VALID' AND j.freshness='CURRENT') AS ok""",
            (project_id,),
        )
        basis = "검증된 현행 ModelRun" if satisfied else "검증된 현행 ModelRun 없음"
    elif code == "NO_OPEN_EVIDENCE_REQUESTS":
        satisfied = not _exists(
            cur,
            "SELECT EXISTS(SELECT 1 FROM evidence_requests WHERE project_id=%s AND status IN ('OPEN','RECEIVED')) AS ok",
            (project_id,),
        )
        basis = "미해결 요청 없음" if satisfied else "OPEN/RECEIVED 자료 요청 존재"
    elif code == "GATE_APPROVED":
        target = item.get("target")
        satisfied = _exists(
            cur,
            """SELECT EXISTS(SELECT 1 FROM gate_decisions gd JOIN review_gates rg ON rg.id=gd.gate_id
                   WHERE gd.project_id=%s AND rg.framework=%s AND rg.gate_key=%s AND gd.disposition='APPROVED'
                     AND gd.source_project_version=%s) AS ok""",
            (project_id, framework, target, project["version"]),
        )
        basis = f"{target} 승인 기록" if satisfied else f"{target} 승인 기록 없음"
    elif code == "OPS_CONFIRMATION":
        basis = "운용 확인 기록 기능 미구현"
    return {**item, "label": LEGACY_GATE_DISPLAY_TEXT.get(item["label"], item["label"]),
            "satisfied": satisfied, "basis": basis}


def project_gate_projection(cur, project: dict, gate: dict) -> dict:
    entry = [evaluate_criterion(cur, project, gate["framework"], item) for item in gate["entry_criteria"]]
    success = [evaluate_criterion(cur, project, gate["framework"], item) for item in gate["success_criteria"]]
    cur.execute(
        """SELECT * FROM gate_decisions WHERE gate_id=%s AND source_project_version=%s
           ORDER BY created_at DESC LIMIT 1""",
        (gate["id"], project["version"]),
    )
    decision = cur.fetchone()
    ready = all(item["satisfied"] for item in entry + success)
    if decision and decision["disposition"] == "APPROVED":
        state = "REVIEW_COMPLETE"
    elif decision and decision["disposition"] == "REJECTED":
        state = "REJECTED"
    elif ready:
        state = "READY"
    else:
        state = "UNRESOLVED"
    return {
        **gate,
        "description": LEGACY_GATE_DISPLAY_TEXT.get(gate["description"], gate["description"]),
        "evaluated_entry_criteria": entry,
        "evaluated_success_criteria": success,
        "ready_count": sum(item["satisfied"] for item in entry + success),
        "criteria_count": len(entry) + len(success),
        "ready_for_decision": ready,
        "state": state,
        "latest_decision": decision,
    }
