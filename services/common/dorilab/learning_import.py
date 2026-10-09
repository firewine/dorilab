"""Strict parser for the reviewed DoriLab 100Q Markdown handoff.

Extraction preserves the file's labels and provenance declarations. It does
not verify the original papers, approve labels, or start model training.
"""
from __future__ import annotations

import re


_SECTION_START = "## 3. Q001~Q100 원래 입력·답안과 문항별 보완점"
_SECTION_END = "## 4. 원본 출처 등록부"
IMPORTER_VERSION = "dorilab.100q-handoff.v2"
_QUESTION = re.compile(r"(?m)^### Q(?P<id>\d{3}) · (?P<category>.+?) · (?P<split>TRAIN|EVALUATION)\s*$")


def _field(text: str, label: str) -> str:
    pattern = re.compile(r"(?ms)^\*\*" + re.escape(label) + r"\*\*[ \t]*\n(.*?)(?=^\*\*[^*\n]+\*\*|^---[ \t]*$|\Z)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _inline(text: str, label: str) -> str:
    match = re.search(r"(?m)^\*\*" + re.escape(label) + r":?\*\*[ \t]*(.*)", text)
    return match.group(1).split("**", 1)[0].strip().rstrip("·").strip() if match else ""


def _native_line(prompt: str, label: str) -> str:
    match = re.search(r"(?m)^" + re.escape(label) + r":[ \t]*(.*)$", prompt)
    return match.group(1).strip() if match else ""


def parse_100q_handoff(markdown: str) -> dict:
    """Extract 100 original examples from the handoff's dedicated Q001–Q100 section."""
    if not isinstance(markdown, str) or len(markdown.encode("utf-8")) > 20 * 1024 * 1024:
        raise ValueError("HANDOFF_FILE_TOO_LARGE_OR_INVALID")
    start = markdown.find(_SECTION_START)
    if start < 0:
        raise ValueError("UNSUPPORTED_HANDOFF_FORMAT")
    end = markdown.find(_SECTION_END, start + len(_SECTION_START))
    if end < 0:
        raise ValueError("HANDOFF_QUESTION_SECTION_INCOMPLETE")
    source = markdown[start:end]
    matches = list(_QUESTION.finditer(source))
    if len(matches) != 100:
        raise ValueError("HANDOFF_EXPECTED_100_QUESTIONS")

    rows = []
    seen = set()
    for index, match in enumerate(matches):
        qid = f"Q{match.group('id')}"
        if qid in seen:
            raise ValueError("HANDOFF_DUPLICATE_QUESTION_ID")
        seen.add(qid)
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        block = source[match.end():block_end]

        question = _field(block, "원래 질문")
        prompt_field = _field(block, "원래 모델 입력 전체")
        answer = _field(block, "원래 정답 초안")
        rejected = _field(block, "원래 오답")
        reason = _field(block, "원래 오답 이유")
        prompt_match = re.search(r"(?ms)^```text\s*\n(.*?)\n```", prompt_field)
        prompt = prompt_match.group(1).strip() if prompt_match else ""
        if not all((question, prompt, answer, rejected, reason)):
            raise ValueError(f"HANDOFF_REQUIRED_FIELD_MISSING:{qid}")
        if not re.search(r"\bDRAFT_UNREVIEWED\b", _inline(block, "라벨 상태")):
            raise ValueError(f"HANDOFF_UNEXPECTED_LABEL_STATUS:{qid}")

        source_label = _inline(block, "출처")
        source_match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]{0,79})\s*·\s*(.+)", source_label)
        family = _inline(block, "원자료 계열").strip("`")
        family_valid = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", family))
        origin = re.search(r"\*\*사례 성격:\*\*\s*`([^`]+)`", block)
        source_link = _inline(block, "원본 출처 연결")
        doi = re.search(r"DOI\s+`([^`]+)`", source_link)

        rows.append({
            "id": qid,
            "category": match.group("category").strip(),
            "split": match.group("split"),
            "question": question,
            "prompt": prompt,
            "completion_draft": answer,
            "rejected_draft": rejected,
            "rejected_reason_draft": reason,
            "rubric": _field(block, "원래 최소 채점항목"),
            "review_classification": _inline(block, "검토 분류"),
            "review_observations": _field(block, "검토에서 관찰한 점"),
            "revision_suggestion": _field(block, "수정 제안"),
            "expression_diagnostic": _inline(block, "표현 진단"),
            "origin": origin.group(1) if origin else None,
            "family_key": family if family_valid else None,
            "source": {
                "id": source_match.group(1) if source_match else None,
                "title": source_match.group(2) if source_match else source_label or None,
                "edition": _native_line(prompt, "판본") or None,
                "locator": _inline(block, "위치") or _native_line(prompt, "원문 위치") or None,
                "doi": doi.group(1) if doi else None,
                "url": _inline(block, "주소") or None,
                "access_status": _inline(block, "접근 상태").strip("`") or None,
                "confirmation_scope": _field(block, "원문 확인 범위") or None,
                "verification": "HANDOFF_DECLARATION_NOT_VERIFIED",
            },
            "classification_issues": [] if family_valid and source_match else ["SOURCE_CLASSIFICATION_METADATA_MISSING"],
            "review_status": "DRAFT_UNREVIEWED",
            "training_eligible": False,
        })

    if seen != {f"Q{i:03d}" for i in range(1, 101)}:
        raise ValueError("HANDOFF_QUESTION_IDS_INCOMPLETE")
    partitions = {}
    for row in rows:
        if row["family_key"]:
            partitions.setdefault(row["family_key"], set()).add(row["split"])
    for row in rows:
        if len(partitions.get(row["family_key"], set())) > 1:
            row["classification_issues"].append("SOURCE_FAMILY_SPLIT_CONFLICT")
    return {
        "format": "DORILAB_100Q_HANDOFF_V1",
        "importer_version": IMPORTER_VERSION,
        "example_count": len(rows),
        "train_count": sum(row["split"] == "TRAIN" for row in rows),
        "evaluation_count": sum(row["split"] == "EVALUATION" for row in rows),
        "rows": rows,
        "training_started": False,
        "approval_required": True,
    }
