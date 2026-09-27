import json
from collections import Counter, defaultdict
from pathlib import Path

FILES = {
    "BASE": Path("eval/results/base_1p7b_eval40_v1_dev.jsonl"),
    "SMOKE": Path("eval/results/smoke_1p7b_eval40_v1_dev.jsonl"),
}

def load(path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

for name, path in FILES.items():

    rows = load(path)

    print()
    print("=" * 90)
    print(name)
    print("=" * 90)

    confusion = Counter()
    by_role = defaultdict(Counter)

    for r in rows:

        expected = r["expected"].get("action")
        output = r.get("output")

        if isinstance(output, dict):
            predicted = output.get("action", "<NO_ACTION_FIELD>")
        else:
            predicted = "<INVALID_JSON>"

        confusion[(expected, predicted)] += 1
        by_role[r["role"]][(expected, predicted)] += 1

        print(
            f"{r['id']:12s} "
            f"GOLD={expected:22s} "
            f"PRED={str(predicted):22s} "
            f"{'PASS' if r['pass'] else 'FAIL'}"
        )

    print()
    print("--- CONFUSION ---")

    for (gold, pred), n in confusion.most_common():
        print(f"{gold:22s} -> {pred:22s} : {n}")

    print()
    print("--- BY ROLE ---")

    for role, counts in by_role.items():
        print()
        print(role)

        for (gold, pred), n in counts.most_common():
            print(f"  {gold:22s} -> {pred:22s} : {n}")

print()
print("=" * 90)
print("SMOKE FAILED OUTPUTS")
print("=" * 90)

rows = load(FILES["SMOKE"])

for r in rows:
    if r["pass"]:
        continue

    print()
    print("-" * 90)
    print("CASE:", r["id"], "/", r["role"])
    print("EXPECTED:")
    print(json.dumps(r["expected"], ensure_ascii=False, indent=2))
    print("MODEL:")
    print(json.dumps(r["output"], ensure_ascii=False, indent=2))
