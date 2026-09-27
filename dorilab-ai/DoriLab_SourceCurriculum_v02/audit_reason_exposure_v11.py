#!/usr/bin/env python3
"""Read-only audit of reason-label exposure in the actual e2 training export.
No model imports, training, inference, network, or automatic relabeling.
Run beside dcurr/: python audit_reason_exposure_v11.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "reason-exposure-audit-v1.1.0"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(text):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, "Duplicate JSON key: " + str(key))
            obj[key] = value
        return obj

    def bad_constant(value):
        raise ValueError("Non-finite JSON value: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)


def load_json(path):
    return strict_json(path.read_text(encoding="utf-8-sig"))


def load_rows(path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = strict_json(line)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
        require(isinstance(row, dict), f"{path}:{number}: expected an object")
        rows.append(row)
    require(rows, f"Empty JSONL: {path}")
    return rows


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def project_path(root, relative):
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts,
            "Use a project-relative path: " + str(relative))
    full = (root / path).resolve()
    require(full.is_relative_to(root), "Path escapes the project: " + str(relative))
    return full


def training_targets(rows):
    targets = []
    ids = set()
    for index, row in enumerate(rows):
        rid = row.get("id")
        require(isinstance(rid, str) and rid not in ids,
                f"Missing/duplicate training row id at row {index + 1}")
        ids.add(rid)
        messages = row.get("messages")
        require(isinstance(messages, list) and len(messages) >= 2,
                f"{rid}: messages required")
        require(all(isinstance(m, dict) and isinstance(m.get("content"), str)
                    for m in messages), f"{rid}: text-only messages required")
        assistant = [m for m in messages if m.get("role") == "assistant"]
        require(len(assistant) == 1 and messages[-1].get("role") == "assistant",
                f"{rid}: this audit requires exactly one final supervised assistant")
        answer = strict_json(messages[-1]["content"])
        require(isinstance(answer, dict) and isinstance(answer.get("action"), str),
                f"{rid}: supervised answer must be an action object")
        reason = answer.get("reason")
        require("reason" not in answer or isinstance(reason, str),
                f"{rid}: reason must be a string when present")
        meta = row.get("v05_metadata", {})
        require(isinstance(meta, dict), f"{rid}: bad v05_metadata")
        kind = meta.get("kind")
        if kind not in ("physics", "contract"):
            pack = row.get("metadata", {}).get("task_pack")
            kind = {"PHYSICS_REVIEW": "physics", "CONTRACT_REPLAY": "contract"}.get(pack)
        require(kind in ("physics", "contract"), f"{rid}: unknown task kind")
        parent = meta.get("parent_case_id") if kind == "physics" else rid
        require(isinstance(parent, str) and parent, f"{rid}: missing Physics parent_case_id")
        targets.append({
            "row_id": rid, "kind": kind, "parent_case_id": parent,
            "action": answer["action"], "reason": reason,
            "system_text": "\n".join(m["content"] for m in messages
                                      if m.get("role") == "system"),
        })
    return targets


def analyze(rows, comparisons):
    targets = training_targets(rows)
    ids = set()
    gold_codes = set()
    for row in comparisons:
        cid = row.get("case_id")
        require(isinstance(cid, str) and cid not in ids, "Missing/duplicate evaluation case id")
        ids.add(cid)
        for arm in ("baseline", "guide"):
            require(isinstance(row.get(arm), dict), f"{cid}: missing {arm}")
            require(isinstance(row[arm].get("expected"), dict), f"{cid}: missing expected")
        require(row["baseline"]["expected"] == row["guide"]["expected"],
                f"{cid}: gold differs across arms")
        reason = row["baseline"]["expected"].get("reason")
        if reason is not None:
            require(isinstance(reason, str), f"{cid}: invalid gold reason")
            gold_codes.add(reason)
    all_codes = gold_codes | {t["reason"] for t in targets if t["reason"] is not None}
    exposures = {}
    for code in sorted(all_codes):
        matches = [t for t in targets if t["reason"] == code]
        boundary = re.compile(r"(?<![A-Z0-9_])" + re.escape(code) + r"(?![A-Z0-9_])")
        eval_rows = [r for r in comparisons if r["baseline"]["expected"].get("reason") == code]
        exposures[code] = {
            "supervised_rows": len(matches),
            "supervised_physics_rows": sum(t["kind"] == "physics" for t in matches),
            "supervised_contract_rows": sum(t["kind"] == "contract" for t in matches),
            "unique_physics_parent_cases": len({t["parent_case_id"] for t in matches if t["kind"] == "physics"}),
            "physics_parent_case_ids": sorted({t["parent_case_id"] for t in matches if t["kind"] == "physics"}),
            "rows_with_literal_code_in_system": sum(bool(boundary.search(t["system_text"])) for t in targets),
            "evaluation_cases_with_this_gold_reason": len(eval_rows),
            "baseline_joint_action_reason_correct": sum(
                isinstance(r["baseline"].get("parsed"), dict)
                and r["baseline"]["parsed"].get("action") == r["baseline"]["expected"].get("action")
                and r["baseline"]["parsed"].get("reason") == code for r in eval_rows),
            "guide_joint_action_reason_correct": sum(
                isinstance(r["guide"].get("parsed"), dict)
                and r["guide"]["parsed"].get("action") == r["guide"]["expected"].get("action")
                and r["guide"]["parsed"].get("reason") == code for r in eval_rows),
        }
    failures = []
    for row in comparisons:
        baseline = row["baseline"]
        if baseline.get("strict_contract_pass") is True:
            continue
        expected = baseline["expected"]
        code = expected.get("reason")
        predicted = baseline.get("parsed") or {}
        require(isinstance(predicted, dict), f"{row['case_id']}: non-object parsed baseline")
        count = exposures[code]["supervised_rows"] if code in exposures else None
        failures.append({
            "case_id": row["case_id"], "expected_action": expected.get("action"),
            "expected_reason": code, "predicted_action": predicted.get("action"),
            "predicted_reason": predicted.get("reason"),
            "supervised_rows_for_expected_reason": count,
            "diagnostic_label": (
                "NO_TARGET_EXAMPLE_FOR_CODE_IN_THIS_EXPORT" if count == 0 else
                "TARGET_EXAMPLES_PRESENT_SEMANTIC_BOUNDARY_STILL_NEEDS_CHECKING" if count is not None else
                "NOT_A_REASON_LABELED_CASE"),
        })
    kinds = Counter(t["kind"] for t in targets)
    return {
        "training_rows": len(targets), "physics_rows": kinds["physics"],
        "contract_rows": kinds["contract"],
        "unique_physics_parent_cases": len({t["parent_case_id"] for t in targets if t["kind"] == "physics"}),
        "supervised_action_rows": dict(Counter(t["action"] for t in targets)),
        "rows_with_supervised_reason": sum(t["reason"] is not None for t in targets),
        "evaluation_cases": len(comparisons), "reason_codes": exposures,
        "baseline_failures": failures,
        "evaluation_gold_codes_without_training_targets": sorted(code for code in gold_codes if exposures[code]["supervised_rows"] == 0),
        "limits": [
            "Counts are rows in one training export, not optimizer updates or independent experiments.",
            "System-string occurrence is NOT evidence that the code was defined or learned.",
            "No supervised target for a code here does NOT mean the base model has never seen the concept or code.",
            "This audit does not establish semantic label validity, causal error explanation, or model capacity limits.",
            "Evaluation labels and source metadata are read for diagnosis only; no training data or scores are changed.",
        ],
    }


def render_report(result):
    lines = ["# v11 — 학습 정답에서 reason 코드 노출 점검", "",
             "학습·추론·파일 수정 없음. 행 수는 1회 데이터 export 기준이며, epoch별 반복 횟수가 아니다.", "",
             f"Contract {result['contract_rows']}행 + Physics {result['physics_rows']}행; 고유 Physics {result['unique_physics_parent_cases']}개.", "",
             "|reason|전체 정답 행|Physics 행|고유 Physics 사례|system 문자열 포함 행|평가 reason 사례|기본 action+reason 정답|",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for code, item in result["reason_codes"].items():
        lines.append(f"|`{code}`|{item['supervised_rows']}|{item['supervised_physics_rows']}|{item['unique_physics_parent_cases']}|{item['rows_with_literal_code_in_system']}|{item['evaluation_cases_with_this_gold_reason']}|{item['baseline_joint_action_reason_correct']}|")
    lines += ["", "## 기존 baseline 실패와 실제 학습 신호", ""]
    for item in result["baseline_failures"]:
        lines.append(f"- {item['case_id']}: `{item['predicted_reason']}` → 기준 `{item['expected_reason']}`; 기준 코드의 학습 정답 {item['supervised_rows_for_expected_reason']}행.")
    lines += ["", "## 해석", "",
              "0행이면 이 export의 정답에서 직접 제시하지 않은 코드다. 베이스 모델의 지식 부재나 이해 불가능을 의미하지 않는다.",
              "행이 있어도 사례가 한 유형에 몰렸는지, 혼동하는 코드와 대비하는 예가 있었는지는 추가 내용 검토가 필요하다.",
              "system에서 코드 이름이 발견됐다는 사실만으로 정의가 제공됐다고 판정하지 않는다.",
              "이번 결과로 평가 정답을 수정하거나 평가 사례를 학습에 추가하지 않는다.", ""]
    return "\n".join(lines)


def run(root, data_name, run_name, eval_name, out_name):
    root = root.resolve()
    data = project_path(root, data_name)
    run_path = project_path(root, run_name)
    eval_path = project_path(root, eval_name)
    sidecar = data.with_suffix(".manifest.json")
    out = project_path(root, out_name)
    require(not out.exists(), "Result folder already exists; preserve it: " + str(out))
    for path in (data, run_path, sidecar, eval_path):
        require(path.is_file(), "Missing file: " + str(path))
    hashes = {str(p.relative_to(root)): file_sha(p) for p in (data, run_path, sidecar, eval_path)}
    data_hash = hashes[str(data.relative_to(root))]
    rm, dm = load_json(run_path), load_json(sidecar)
    require(dm.get("data_sha256") == data_hash, "Data file differs from its manifest")
    require(isinstance(rm.get("data_manifest"), dict)
            and rm["data_manifest"].get("data_sha256") == data_hash,
            "This is not the training data recorded by the selected run")
    rows, comparisons = load_rows(data), load_rows(eval_path)
    require(dm.get("records") == len(rows), "Manifest row count mismatch")
    result = analyze(rows, comparisons)
    result.update({"version": VERSION, "at_utc": datetime.now(timezone.utc).isoformat(),
                   "training_executed": False, "inference_executed": False,
                   "input_sha256": hashes,
                   "run_epochs_requested": rm.get("epochs_requested"),
                   "script_sha256": file_sha(Path(__file__).resolve())})
    for name, digest in hashes.items():
        require(file_sha(project_path(root, name)) == digest, "Input changed during audit: " + name)
    out.mkdir(parents=True, exist_ok=False)
    with (out / "audit.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    with (out / "RESULTS_KO.md").open("x", encoding="utf-8") as handle:
        handle.write(render_report(result))
    print("REASON EXPOSURE AUDIT: PASS")
    print(f"Training rows: {len(rows)}; unique Physics parents: {result['unique_physics_parent_cases']}")
    for item in result["baseline_failures"]:
        print(f"{item['case_id']}: {item['expected_reason']} -> {item['supervised_rows_for_expected_reason']} target rows")
    print("Saved:", out / "audit.json", out / "RESULTS_KO.md", sep="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--data", default="data/evidence_training_v05/position210.jsonl")
    parser.add_argument("--run-manifest", default="runs/evidence_training_v05_position_e2/RUN_MANIFEST.json")
    parser.add_argument("--evaluation", default="data/new_source_reason_v10/comparison_cases.jsonl")
    parser.add_argument("--outdir", default="data/reason_exposure_v11")
    args = parser.parse_args()
    try:
        run(args.root, args.data, args.run_manifest, args.evaluation, args.outdir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("STOP:", exc, file=sys.stderr)
        print("Original data, models and evaluation outputs were not modified.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
