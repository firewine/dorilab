#!/usr/bin/env python3
"""DoriLab v02 identifier-invariance probe. Standard library only.

Place beside dcurr/ and data/ in DoriLab_SourceCurriculum_v02.
This does NOT train, approve, fix model outputs, or change source facts/actions.
It invokes no external service. Run your existing dcurr.evaluate separately.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "id-probe-v0.3.0"
DEFAULT_CASES = "data/physics_candidates40_v02.jsonl"
DEFAULT_DIR = "data/id_probe_v03"
EXPECTED_CASE_HASH = "f0a5641a1b4ee64964b2e39b2aafbf779da2fb1cb6cdc1528d62cd115eed83e8"
MODELS = {
    "lr5e5": {
        "adapter": "runs/qwen35_2b_physics20_v02_e1",
        "weight_sha256": "8d61d0d09e0c18ac607439a362192a6ec1f0cc87d5887a3e4f1c5d19deffc5de",
        "baseline": "reports/physics20_e1_all40.jsonl",
        "probe": "reports/physics20_lr5e5_idprobe_v03.jsonl",
    },
    "lr2e5": {
        "adapter": "runs/qwen35_2b_physics20_v02_lr2e5_e1",
        "weight_sha256": "016f12e332a29c95cad3d7a28742246722c14176baeaf773a17be226c93e0dc0",
        "baseline": "reports/physics20_lr2e5_e1_all40.jsonl",
        "probe": "reports/physics20_lr2e5_idprobe_v03.jsonl",
    },
}
CODE_FILES = (
    "dcurr/evaluate.py", "dcurr/common.py", "dcurr/prompts.py",
    "dcurr/prompts_legacy.py", "dcurr/model_io.py", "data/action_schema_v02.json",
)


def strict_loads(text: str) -> Any:
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError(f"Duplicate JSON key: {k}")
            d[k] = v
        return d

    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = strict_loads(line)
        except ValueError as e:
            raise ValueError(f"{path}:{i}: {e}") from e
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{i}: object required")
        rows.append(row)
    return rows


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def save_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def dump_jsonl(rows: list[dict]) -> str:
    # Preserve dict/key order and list order: ID spelling is the ONLY intervention.
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def by_id(rows: list[dict]) -> dict[str, dict]:
    d = {}
    for r in rows:
        cid = r.get("case_id")
        if not isinstance(cid, str) or not cid or cid in d:
            raise ValueError("Missing/duplicate case_id in cases or results")
        d[cid] = r
    return d


def swap_values(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [swap_values(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: swap_values(v, mapping) for k, v in value.items()}
    return value


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in collect_strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in collect_strings(v)]
    return []


def answer_variants(case: dict) -> list[dict]:
    v = case.get("acceptable_answers", [case["expected"]])
    if not isinstance(v, list) or not v or any(not isinstance(a, dict) for a in v):
        raise ValueError("acceptable_answers must be a nonempty list of objects")
    return v


def evidence_definitions(case: dict) -> dict[str, str]:
    packet = case["packet"]
    definitions = {}
    for field, key, prefix in (
        (packet["reference_context"], "reference_id", "SF-"),
        (packet["case_packet"]["evidence"], "evidence_id", "OBS-"),
    ):
        if not isinstance(field, list):
            raise ValueError("Expected lists of reference/evidence objects")
        for entry in field:
            value = entry.get(key) if isinstance(entry, dict) else None
            if not isinstance(value, str) or not value or value in definitions:
                raise ValueError(f"Missing/duplicate local reference ID: {case['case_id']}")
            if not value.startswith(prefix):
                raise ValueError(f"Unexpected ID format {value!r}; inspect before extending this probe")
            definitions[value] = prefix
    if not definitions:
        raise ValueError("No reference/evidence definitions")
    return definitions


def make_probe(cases: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    by_id(cases)
    if not cases:
        raise ValueError("Empty case file")
    all_original_ids = set()
    grouped = defaultdict(list)
    for c in cases:
        all_original_ids.update(evidence_definitions(c))
        pid = c.get("pair_id")
        if not isinstance(pid, str) or not pid:
            raise ValueError("pair_id is required")
        grouped[pid].append(c)
    # One bijection per pair; A/B get identical handles when they share evidence.
    rng = random.Random(seed)
    used = set(all_original_ids)
    pair_maps = {}
    for pid in sorted(grouped):
        defs = {}
        for c in grouped[pid]:
            defs.update(evidence_definitions(c))
        mapping = {}
        for old in sorted(defs):
            while True:
                new = defs[old] + str(rng.randrange(1000, 10000))
                if new not in used:
                    used.add(new)
                    break
            mapping[old] = new
        pair_maps[pid] = mapping

    outputs, mappings = [], []
    for original in cases:
        mapping = pair_maps[original["pair_id"]]
        # Embedded reference spellings in prose require a reviewed text rewrite.
        # Stop instead of silently changing a physical statement.
        for text in collect_strings(original["packet"]):
            for old in mapping:
                if old != text and old in text:
                    raise ValueError(f"{original['case_id']}: embedded ID in prose: {old}. Manual review required.")
        for a in [original["expected"]] + answer_variants(original):
            refs = a.get("evidence_refs")
            if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
                raise ValueError("Expected answer must contain a nonempty string evidence_refs list")
            if not set(refs) <= set(evidence_definitions(original)):
                raise ValueError("Expected answer cites an undefined local reference")

        modified = copy.deepcopy(original)
        modified["packet"] = swap_values(original["packet"], mapping)
        modified["expected"] = swap_values(original["expected"], mapping)
        if "acceptable_answers" in original:
            modified["acceptable_answers"] = swap_values(original["acceptable_answers"], mapping)
        # Do NOT alter source IDs, source_fact_ids, annotations, claim_id, proposal,
        # facts, numeric values, reason codes, roles, order, or the original files.
        inverse = {new: old for old, new in mapping.items()}
        if swap_values(modified["packet"], inverse) != original["packet"]:
            raise ValueError("Packet reverse-mapping check failed")
        if swap_values(modified["expected"], inverse) != original["expected"]:
            raise ValueError("Gold reverse-mapping check failed")
        if modified["packet"] == original["packet"]:
            raise ValueError("Probe did not change any visible identifier")
        outputs.append(modified)
        mappings.append({"case_id": original["case_id"], "pair_id": original["pair_id"],
                         "id_mapping": mapping})
    return outputs, mappings


def require_result_ids(rows: list[dict], cases: list[dict]) -> dict[str, dict]:
    result = by_id(rows)
    expected = set(by_id(cases))
    if set(result) != expected:
        raise ValueError(f"Incomplete/mismatched evaluation: missing={sorted(expected-set(result))}, extra={sorted(set(result)-expected)}")
    return result


def runtime_common(root: Path):
    if not (root / "dcurr/common.py").is_file():
        raise ValueError("Run from ~/dorilab-ai/DoriLab_SourceCurriculum_v02 (the directory containing dcurr/).")
    sys.path.insert(0, str(root))
    m = importlib.import_module("dcurr.common")
    if Path(m.__file__).resolve() != (root / "dcurr/common.py").resolve():
        raise ValueError("Imported dcurr.common from the wrong project")
    for name in ("validate_answer", "answer_matches"):
        if not callable(getattr(m, name, None)):
            raise ValueError(f"dcurr.common.{name} missing; do not guess a new API")
    return m


def result_output(row: dict):
    # This user's actual evaluator stores "parsed". Do not flatten nested dict refs.
    if "parsed" not in row:
        raise ValueError("Result row lacks 'parsed'; evaluator format differs. Keep logs and inspect its code.")
    return row["parsed"]


def score(common, case: dict, row: dict) -> dict:
    obj = result_output(row)
    valid = False
    try:
        common.validate_answer(obj, case)
        valid = True
    except Exception:
        # An invalid model answer is a failure, never a repaired answer.
        pass
    matched = valid and any(common.answer_matches(a, obj) for a in answer_variants(case))
    if "contract_pass" not in row or not isinstance(row["contract_pass"], bool):
        raise ValueError("Result must include the evaluator's boolean contract_pass")
    return {
        "action_correct": isinstance(obj, dict) and any(obj.get("action") == a.get("action") for a in answer_variants(case)),
        "schema_and_refs_valid": valid,
        "contract_pass": bool(matched),
        "stored_score_agrees": row["contract_pass"] == bool(matched),
    }


def collect_id_strings(obj: Any) -> list[str]:
    if not isinstance(obj, dict):
        return []
    # Diagnostics can see old ID spellings inside malformed ref objects too.
    # This function does not make such an output valid.
    return collect_strings(obj.get("evidence_refs", []))


def summarise_cases(rows: list[dict], field: str) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[r["pair_id"]].append(r)
    complete = [g for g in groups.values() if len(g) == 2]
    return {
        "cases": len(rows),
        "action_correct": sum(r[field]["action_correct"] for r in rows),
        "schema_and_refs_valid": sum(r[field]["schema_and_refs_valid"] for r in rows),
        "contract_pass": sum(r[field]["contract_pass"] for r in rows),
        "pairs": len(complete),
        "pair_action_both_correct": sum(all(r[field]["action_correct"] for r in g) for g in complete),
        "pair_contract_both_pass": sum(all(r[field]["contract_pass"] for r in g) for g in complete),
    }


def verify_frozen(root: Path, manifest: dict) -> None:
    for rel, expected in manifest["frozen_files"].items():
        p = root / rel
        if not p.is_file() or digest(p) != expected:
            raise ValueError(f"Frozen file changed/missing: {rel}. Keep this experiment; make a new version before comparing.")


def build(root: Path, outdir: Path, seed: int) -> None:
    root = root.resolve()
    target = root / outdir
    if target.exists():
        raise ValueError(f"{target} already exists. Inspect or use a new version; nothing was overwritten.")
    source = root / DEFAULT_CASES
    if digest(source) != EXPECTED_CASE_HASH:
        raise ValueError("Physics40 hash differs from the reported baseline. Preserve the new data and inspect before proceeding.")
    cases = read_jsonl(source)
    if len(cases) != 40 or set(Counter(c["pair_id"] for c in cases).values()) != {2}:
        raise ValueError("Expected 40 cases forming 20 complete pairs")
    transformed, maps = make_probe(cases, seed)
    common = runtime_common(root)
    for c in cases + transformed:
        common.validate_answer(c["expected"], c)
        for answer in answer_variants(c):
            common.validate_answer(answer, c)

    frozen = {}
    for rel in [DEFAULT_CASES, *CODE_FILES]:
        frozen[rel] = digest(root / rel)
    model_specs = copy.deepcopy(MODELS)
    for label, spec in model_specs.items():
        adapter = root / spec["adapter"]
        weight = adapter / "adapter_model.safetensors"
        observed = digest(weight)
        if observed != spec["weight_sha256"]:
            raise ValueError(f"{label}: adapter hash differs from the supplied run")
        for filename in ("adapter_model.safetensors", "adapter_config.json"):
            p = adapter / filename
            frozen[str(p.relative_to(root))] = digest(p)
        baseline = require_result_ids(read_jsonl(root / spec["baseline"]), cases)
        for c in cases:
            if not score(common, c, baseline[c["case_id"]])["stored_score_agrees"]:
                raise ValueError(f"{label}: current scorer disagrees with saved baseline {c['case_id']}. Inspect evaluator changes first.")
        frozen[spec["baseline"]] = digest(root / spec["baseline"])
        if (root / spec["probe"]).exists():
            raise ValueError(f"Probe output already exists: {spec['probe']}; choose another experiment version.")

    control_text = source.read_text(encoding="utf-8")
    probe_text = dump_jsonl(transformed)
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "version": VERSION, "created_at_utc": now, "seed": seed,
        "purpose": "CANDIDATE_DIAGNOSTIC_IDENTIFIER_INVARIANCE_NOT_HOLDOUT",
        "cases": len(cases), "original_pairs": 20,
        "transformation": "SF/OBS handle spelling only; same proposal, observations, source facts, action, reason, order, claim ID",
        "not_tested": ["new-program generalization", "relevant-vs-irrelevant evidence selection", "legacy Contract20 robustness"],
        "unverified_here": ["User's dcurr GPU runtime has not been executed in the package-creation environment"],
        "prompt_and_schema_changed": False, "model_or_review_files_modified": False,
        "model_specs": model_specs, "frozen_files": frozen, "mappings": maps,
        "control_file": str(outdir / "control40.jsonl"),
        "probe_file": str(outdir / "idrename40.jsonl"),
        "control_sha256": hashlib.sha256(control_text.encode("utf-8")).hexdigest(),
        "probe_sha256": hashlib.sha256(probe_text.encode("utf-8")).hexdigest(),
        "script_sha256": digest(Path(__file__)),
        "label_policy": "Original candidate labels retained; evidence ID strings bijectively renamed. No new source fact authored.",
    }
    # All checks have passed before creating output files.
    target.mkdir(parents=True, exist_ok=False)
    (target / "control40.jsonl").write_text(control_text, encoding="utf-8")
    (target / "idrename40.jsonl").write_text(probe_text, encoding="utf-8")
    save_json(target / "manifest.json", manifest)
    print("ID PROBE BUILD: PASS")
    print("Control: 40 original cases / 20 pairs")
    print("Probe:   40 ID-renamed views of the SAME cases / 20 pairs")
    print("Not 80 independent examples; do not use these derived probes for training.")
    print("NO original source, review, model, or evaluator files changed.")
    first = maps[0]
    print("Example:", first["case_id"], json.dumps(first["id_mapping"], ensure_ascii=False))
    print("Probe file:", manifest["probe_file"])
    print("Manifest:", target / "manifest.json")


def compare(root: Path, outdir: Path) -> None:
    root = root.resolve()
    target = root / outdir
    manifest = strict_loads((target / "manifest.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION:
        raise ValueError("Probe version mismatch")
    if manifest["script_sha256"] != digest(Path(__file__)):
        raise ValueError("Probe helper changed after build")
    verify_frozen(root, manifest)
    control_path, probe_path = root / manifest["control_file"], root / manifest["probe_file"]
    if digest(control_path) != manifest["control_sha256"] or digest(probe_path) != manifest["probe_sha256"]:
        raise ValueError("Probe/control file changed")
    cases, probes = read_jsonl(control_path), by_id(read_jsonl(probe_path))
    maps = {m["case_id"]: m["id_mapping"] for m in manifest["mappings"]}
    common = runtime_common(root)
    report = {
        "version": VERSION, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "Paired identifier-invariance diagnostic; not new-source generalization or a overfitting verdict.",
        "models": {},
    }
    details = []
    for label, spec in manifest["model_specs"].items():
        old = require_result_ids(read_jsonl(root / spec["baseline"]), cases)
        new_path = root / spec["probe"]
        new = require_result_ids(read_jsonl(new_path), cases)
        paired = []
        for c in cases:
            cid = c["case_id"]
            a, b = score(common, c, old[cid]), score(common, probes[cid], new[cid])
            if not a["stored_score_agrees"] or not b["stored_score_agrees"]:
                raise ValueError(f"{label}/{cid}: stored and current evaluator disagree; not a model comparison")
            ao, bo = result_output(old[cid]), result_output(new[cid])
            action_changed = (ao.get("action") if isinstance(ao, dict) else None) != (bo.get("action") if isinstance(bo, dict) else None)
            stale = sorted(set(collect_id_strings(bo)) & set(maps[cid]))
            r = {"model": label, "case_id": cid, "pair_id": c["pair_id"],
                 "baseline": a, "probe": b, "action_changed": action_changed,
                 "stale_original_reference_strings": stale,
                 "baseline_pass_lost": a["contract_pass"] and not b["contract_pass"],
                 "probe_pass_gained": not a["contract_pass"] and b["contract_pass"]}
            paired.append(r)
        sb, sp = summarise_cases(paired, "baseline"), summarise_cases(paired, "probe")
        summary = {
            "baseline": sb, "id_renamed": sp,
            "action_changed_count": sum(r["action_changed"] for r in paired),
            "original_contract_passes_lost": sum(r["baseline_pass_lost"] for r in paired),
            "original_contract_pass_denominator": sb["contract_pass"],
            "new_contract_passes_gained": sum(r["probe_pass_gained"] for r in paired),
            "rows_emitting_old_reference_ids": sum(bool(r["stale_original_reference_strings"]) for r in paired),
            "result_sha256": digest(new_path),
        }
        report["models"][label] = summary
        details.extend(paired)
    summary_file, detail_file = target / "comparison.json", target / "comparison_cases.jsonl"
    if summary_file.exists() or detail_file.exists():
        raise ValueError("Comparison files already exist; nothing overwritten")
    save_json(summary_file, report)
    detail_file.write_text(dump_jsonl(details), encoding="utf-8")
    print("IDENTIFIER INVARIANCE — SAME CASES, DIFFERENT LOCAL REFERENCE IDs")
    print("model      contract original -> renamed | action original -> renamed | lost | old-ID rows")
    for label, r in report["models"].items():
        a, b = r["baseline"], r["id_renamed"]
        print(f"{label:10s} {a['contract_pass']:2d}/40 -> {b['contract_pass']:2d}/40            "
              f"{a['action_correct']:2d}/40 -> {b['action_correct']:2d}/40          "
              f"{r['original_contract_passes_lost']:2d}     {r['rows_emitting_old_reference_ids']:2d}")
    print("\n", json.dumps(report, ensure_ascii=False, indent=2))
    print("Saved:", summary_file)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("build")
    a.add_argument("--root", type=Path, default=Path.cwd())
    a.add_argument("--outdir", type=Path, default=Path(DEFAULT_DIR))
    a.add_argument("--seed", type=int, default=20260919)
    a = sub.add_parser("compare")
    a.add_argument("--root", type=Path, default=Path.cwd())
    a.add_argument("--outdir", type=Path, default=Path(DEFAULT_DIR))
    args = p.parse_args()
    if args.outdir.is_absolute() or ".." in args.outdir.parts:
        raise ValueError("--outdir must be a relative subdirectory inside the project")
    if args.command == "build":
        build(args.root, args.outdir, args.seed)
    else:
        compare(args.root, args.outdir)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise SystemExit(f"STOP: {exc}\nNo training or automatic approval was performed.")
