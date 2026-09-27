from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from tools.common import ROOT, action_errors, changed_paths, read_jsonl, sha256, write_json
from runtime.physics_prompts_v01 import build_messages


def validate() -> dict:
    manifest = json.loads((ROOT / "data/dataset_manifest_v01.json").read_text(encoding="utf-8"))
    source_pack = json.loads((ROOT / "sources/source_manifest_v01.json").read_text(encoding="utf-8"))
    sources = {s["source_id"]: s for s in source_pack["sources"]}
    cases = read_jsonl(ROOT / "data/physics_cases_seed32_v01.jsonl")
    facts = read_jsonl(ROOT / "data/source_facts_v01.jsonl")
    sft = read_jsonl(ROOT / "data/physics_sft_seed32_candidate_v01.jsonl")
    pairs = json.loads((ROOT / "data/pair_manifest_v01.json").read_text(encoding="utf-8"))["pairs"]
    schema = json.loads((ROOT / "data/action_schema_v01.json").read_text(encoding="utf-8"))
    errors = []
    for rel, digest in manifest["artifacts"].items():
        p = ROOT / rel
        if not p.is_file() or sha256(p) != digest:
            errors.append(f"file hash mismatch: {rel}")
    if sha256(ROOT / manifest["canonical_prompt_file"]) != manifest["canonical_prompt_sha256"]:
        errors.append("canonical prompt hash mismatch")
    if len(cases) != 32 or len(pairs) != 16 or len(facts) != 16 or len(sft) != 32:
        errors.append("unexpected record counts")
    by_case = {c["case_id"]: c for c in cases}
    by_fact = {f["fact_id"]: f for f in facts}
    by_sft = {s["id"]: s for s in sft}
    if len(by_case) != len(cases) or len(by_fact) != len(facts) or len(by_sft) != len(sft):
        errors.append("duplicate IDs")
    for fact in facts:
        source = sources.get(fact["source_id"])
        if not source:
            errors.append(f"unknown fact source: {fact['fact_id']}")
            continue
        for page in fact["pdf_pages_1based"]:
            if not isinstance(page, int) or not 1 <= page <= source["pdf_pages"]:
                errors.append(f"page out of range: {fact['fact_id']}")
        if fact["verification"] != "PDF_TEXT_CHECKED":
            errors.append(f"fact text review not recorded: {fact['fact_id']}")
    for case in cases:
        cid, packet = case["case_id"], case["packet"]
        if case["source_id"] not in {"TH-01", "VB-X1"}:
            errors.append(f"unexpected seed source: {cid}")
        if case["human_review_status"] != "PENDING" or case["basis"] != "SYNTHETIC_COUNTERFACTUAL":
            errors.append(f"unexpected authoring status: {cid}")
        if case["raw_measurement_available"]:
            errors.append(f"unexpected raw measurement claim: {cid}")
        errors.extend(f"{cid}: {e}" for e in action_errors(case["expected"], packet, schema))
        for ref in packet["reference_context"]:
            fact = by_fact.get(ref["reference_id"])
            if not fact or ref["text"] != fact["paraphrase_en"] or ref["source_id"] != fact["source_id"]:
                errors.append(f"reference text/source mismatch: {cid}")
        if cid not in by_sft or by_sft[cid]["messages"] != build_messages(case["role"], packet, case["expected"]):
            errors.append(f"SFT/canonical prompt mismatch: {cid}")
        # Authoring metadata is never placed in the user input.
        forbidden = {"expected", "rationale_ko", "variant", "pair_id", "case_id", "label"}
        if forbidden & set(packet):
            errors.append(f"label metadata in input: {cid}")
    for pair in pairs:
        a, b = [by_case[x] for x in pair["case_ids"]]
        actual_diff = changed_paths(a["packet"], b["packet"])
        if actual_diff != pair["changed_paths"] or len(actual_diff) != 1:
            errors.append(f"pair is not one-leaf counterfactual: {pair['pair_id']}: {actual_diff}")
        if a["expected"]["action"] == b["expected"]["action"]:
            errors.append(f"pair does not change action: {pair['pair_id']}")
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "checks": "hashes, IDs, source pages, schema, refs, canonical prompts, one-leaf pairs",
        "sources_registered": len(sources), "seed_sources": 2,
        "facts": len(facts), "cases": len(cases), "pairs": len(pairs),
        "actions": dict(Counter(c["expected"]["action"] for c in cases)),
        "roles": dict(Counter(c["role"] for c in cases)),
        "human_review": "PENDING", "raw_originals_included": False,
        "gpu_training_or_inference_performed": False,
        "content_accuracy_independently_verified": False,
        "errors": errors,
    }
    return result


def main() -> None:
    result = validate()
    write_json(ROOT / "reports/validation_report.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
