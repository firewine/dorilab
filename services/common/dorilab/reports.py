from __future__ import annotations

import json
from typing import Any

from .contracts import assessment_scope


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def render_review_markdown(
    *,
    project: dict,
    claim: dict,
    job: dict,
    snapshot: dict,
    model_run: dict,
    decisions: list[dict],
    evidence: list[dict],
    retrieved_chunks: list[dict],
    evidence_requests: list[dict],
    orchestration: dict | None = None,
) -> bytes:
    scope = assessment_scope(snapshot.get("review_purpose"))
    lines = [
        f"# DoriLab BM1 검토 보고서 — {claim['display_id']}",
        "",
        "> 이 문서는 검토 초안과 사람 결정을 보존하는 내부 기록입니다. 공식 시험 승인, waiver, 위험 수용 또는 검증 종결이 아닙니다.",
        "",
        "## 범위와 현행성",
        "",
        f"- 프로젝트: {project['display_id']} / {project['name']}",
        f"- Claim: {claim['display_id']} / {claim['question']}",
        f"- 원본 revision: Claim v{snapshot.get('claim_version', '미보존')} / project v{snapshot.get('project_version', '미보존')}",
        f"- 검토 목적: {scope['label']} / {scope['review_purpose']}",
        f"- 판단 범위: {scope['result_scope']}",
        f"- NO_ACTION_REQUIRED 계약: {scope['no_action_required_meaning']}",
        f"- 제품 성능 요구: {scope['product_performance_status']}",
        f"- 별도 종결의 범위: {scope['closure_label']} (이 보고서 자체는 종결 승인 아님)",
        f"- Job: {job['id']}",
        f"- 상태: {job['status']}",
        f"- 현행성: {job['freshness']}",
        f"- 실행 모드: {job['mode']}",
        f"- Snapshot SHA256: {snapshot['snapshot_sha256']}",
        f"- Contract: {snapshot['contract_id']}",
        f"- Model profile: {snapshot['model_profile']}",
        "",
        "## 포함 근거",
        "",
    ]
    if evidence:
        for item in evidence:
            receipt = snapshot.get("source_verifications", {}).get(str(item["id"]), {})
            lines.append(
                f"- {item['display_id']} ({item['kind']}, {item['basis']}) — artifact SHA256 `{receipt.get('artifact_sha256', item['artifact_sha256'])}`; locator `{receipt.get('submitted_locator') or item.get('locator') or 'NONE'}`"
            )
            lines.append(f"  - Snapshot의 원문 위치 검증: {receipt.get('status', 'UNRESOLVED')} / "
                         f"{receipt.get('freshness', '미보존')} / {receipt.get('reason_code', 'LEGACY_NOT_VERIFIED')}; "
                         f"chunk `{receipt.get('document_chunk_id', '미보존')}`; "
                         f"parser receipt `{receipt.get('parser_receipt_sha256', '미보존')}`")
    else:
        lines.append("- 없음")
    lines.extend(["", "> 원문 텍스트 일치는 내용의 존재 확인입니다. 조항의 의미적 지지·적용성·제품 적합성 승인을 보증하지 않습니다. "
                  "PDF의 물리 페이지와 추출 텍스트 줄/chunk만 대조하며, 인쇄 페이지·OCR·표·그림은 검증하지 않습니다. "
                  "이전 등록 자료와 미지원 형식은 자동 검증되지 않았습니다."])
    lines.extend(["", "## 오케스트레이션 실행", ""])
    if orchestration:
        run = orchestration["run"]
        lines.extend(
            [
                f"- Graph: {run['graph_id']} v{run['graph_version']}",
                f"- Run: {run['id']} / {run['status']} / {run['current_node']}",
                f"- Origin: {run['origin']}",
                f"- Checkpoints: {orchestration['integrity']['checkpoint_count']}",
                f"- Latest checkpoint SHA256: `{orchestration['integrity']['latest_sha256']}`",
                "",
            ]
        )
        for node in orchestration["nodes"]:
            lines.append(f"- {node['key']}: {node['status']}")
        lines.extend(
            [
                "",
                "> COMPLETE는 이 내부 검토 실행의 완료다. 공식 시험 승인이나 VerificationClosure를 뜻하지 않는다.",
            ]
        )
    else:
        lines.append("- 실행 추적 없음")
    lines.extend(["", "## 문서 RAG 검색", ""])
    if snapshot.get("retrieval_receipt"):
        lines.extend(
            [
                f"- Retrieval run: {snapshot.get('retrieval_run_id')}",
                f"- Receipt SHA256: `{snapshot['retrieval_receipt'].get('receipt_sha256', 'stored-in-snapshot')}`",
                f"- Parser: {snapshot['retrieval_receipt'].get('parser_version')}",
                f"- Index: {snapshot['retrieval_receipt'].get('index_version')}",
                f"- Query SHA256: `{snapshot['retrieval_receipt'].get('query_sha256')}`",
                f"- Source text truncated: {snapshot.get('context_budget', {}).get('source_text_truncated')}",
            ]
        )
        for item in retrieved_chunks:
            lines.append(
                f"- chunk `{item['id']}` — artifact SHA256 `{item['artifact_sha256']}`; "
                f"chunk SHA256 `{item['text_sha256']}`; locator `{item['locator']}`"
            )
    else:
        lines.append("- 검색 없음")
    lines.extend(
        [
            "",
            "## 모델 원출력 보존 정보",
            "",
            f"- Raw artifact ID: {model_run['raw_artifact_id']}",
            f"- Raw SHA256: `{model_run['raw_sha256']}`",
            f"- Validation: {model_run['validation_status']}",
            f"- Finish reason: {model_run.get('finish_reason') or 'NONE'}",
            "",
            "### 검증된 구조",
            "",
            "```json",
            _json(model_run.get("parsed_output")),
            "```",
            "",
            "### 실행 receipt",
            "",
            "```json",
            _json(model_run.get("receipt")),
            "```",
            "",
            "## 자료 요청",
            "",
        ]
    )
    if evidence_requests:
        for request in evidence_requests:
            lines.append(
                f"- [{request['status']}] {request['requested_item']} — 제출 근거 `{request.get('submitted_evidence_id') or 'NONE'}`"
            )
    else:
        lines.append("- 없음")
    lines.extend(["", "## 사람 결정", ""])
    if decisions:
        for decision in decisions:
            lines.extend(
                [
                    f"### {decision['disposition']}",
                    "",
                    f"- Actor: {decision['actor']}",
                    f"- 시각: {decision['created_at']}",
                    f"- 기준 Job version: {decision['source_job_version']}",
                    f"- 메모: {decision.get('note') or '없음'}",
                    "",
                    "```json",
                    _json(decision.get("edited_draft")),
                    "```",
                    "",
                ]
            )
    else:
        lines.append("- 결정 없음")
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")
