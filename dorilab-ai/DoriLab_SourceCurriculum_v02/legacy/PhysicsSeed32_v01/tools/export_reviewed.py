from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tools.common import ROOT, read_jsonl, sha256, write_json


def select_approved(cases: list[dict], decisions: list[dict]) -> list[str]:
    by_id = {c["case_id"]: c for c in cases}
    rows = {}
    for row in decisions:
        cid = row.get("case_id", "").strip()
        if cid not in by_id or cid in rows:
            raise ValueError(f"Unknown or duplicate review case: {cid}")
        rows[cid] = row
    if set(rows) != set(by_id):
        raise ValueError("Review sheet must contain every case exactly once.")
    approved = set()
    for cid, row in rows.items():
        decision = row.get("decision", "").strip().upper()
        if decision not in {"PENDING", "APPROVED", "REVISE", "REJECTED"}:
            raise ValueError(f"{cid}: unknown decision {decision!r}")
        if decision == "APPROVED":
            if not row.get("reviewer", "").strip() or not row.get("reviewed_at", "").strip():
                raise ValueError(f"{cid}: APPROVED requires reviewer and reviewed_at")
            try:
                datetime.fromisoformat(row["reviewed_at"].strip())
            except ValueError as exc:
                raise ValueError(f"{cid}: reviewed_at must use ISO date/time, e.g. 2026-09-13") from exc
            approved.add(cid)
    pairs = defaultdict(set)
    for c in cases:
        pairs[c["pair_id"]].add(c["case_id"])
    incomplete = [p for p, members in pairs.items() if members & approved and not members <= approved]
    if incomplete:
        raise ValueError("Approve both members of a pair before export: " + ", ".join(incomplete))
    if not approved:
        raise ValueError("No approved pairs yet. Review docs/CASE_REVIEW.html and update data/review_decisions.csv.")
    return sorted(approved)


def main():
    p = argparse.ArgumentParser(description="Export explicitly human-reviewed pairs. Never auto-approves labels.")
    p.add_argument("--output", default="data/physics_sft_reviewed_v01.jsonl")
    args = p.parse_args()
    out = ROOT / args.output
    if out.exists():
        raise SystemExit(f"Output exists: {out}. Use a new versioned filename.")
    cases = read_jsonl(ROOT / "data/physics_cases_seed32_v01.jsonl")
    review_path = ROOT / "data/review_decisions.csv"
    with review_path.open(encoding="utf-8-sig", newline="") as f:
        decisions = list(csv.DictReader(f))
    try:
        approved = set(select_approved(cases, decisions))
    except ValueError as exc:
        raise SystemExit(str(exc))
    records = read_jsonl(ROOT / "data/physics_sft_seed32_candidate_v01.jsonl")
    selected = [r for r in records if r["id"] in approved]
    by_decision = {r["case_id"]: r for r in decisions}
    # Human approval is recorded here as a review event, leaving authored originals unchanged.
    exported = [{"id": r["id"], "messages": r["messages"],
                 "review_status": "HUMAN_APPROVED", "reviewer": by_decision[r["id"]]["reviewer"],
                 "reviewed_at": by_decision[r["id"]]["reviewed_at"]} for r in selected]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in exported), encoding="utf-8")
    write_json(out.with_suffix(".manifest.json"), {
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "records": len(exported),
        "cases": [r["id"] for r in exported], "sha256": sha256(out),
        "decision_csv_sha256": sha256(review_path),
        "candidate_sha256": sha256(ROOT / "data/physics_sft_seed32_candidate_v01.jsonl"),
        "prompt_sha256": sha256(ROOT / "runtime/physics_prompts_v01.py"),
        "basis": "User-recorded source/label review; not test approval or certification",
    })
    print(f"Exported {len(exported)} reviewed examples: {out}")

if __name__ == "__main__":
    main()
