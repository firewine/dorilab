from __future__ import annotations
import argparse
import json
from tools.common import ROOT, read_jsonl


def main():
    parser = argparse.ArgumentParser(description="Print a source-grounded case pair for human review.")
    parser.add_argument("--pair", required=True, help="Example: TH01-P07 or VBX1-P03")
    args = parser.parse_args()
    cases = read_jsonl(ROOT / "data/physics_cases_seed32_v01.jsonl")
    matches = sorted((c for c in cases if c["pair_id"] == args.pair), key=lambda c: c["variant"])
    if not matches:
        raise SystemExit("Unknown pair. See docs/CASE_REVIEW.md.")
    for case in matches:
        print("=" * 88)
        print(case["case_id"], "|", case["role"], "| SYNTHETIC / HUMAN REVIEW PENDING")
        print(json.dumps(case["packet"], ensure_ascii=False, indent=2))
        print("\nPROPOSED LABEL:")
        print(json.dumps(case["expected"], ensure_ascii=False, indent=2))
        print("\n검토 근거:", case["rationale_ko"])

if __name__ == "__main__":
    main()
