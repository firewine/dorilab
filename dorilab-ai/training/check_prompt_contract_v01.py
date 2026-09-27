import json
from runtime.dorilab_prompts_v01 import SYSTEM

DATA = "data/train150_v01.jsonl"

with open(DATA, "r", encoding="utf-8") as f:
    rows = [json.loads(x) for x in f if x.strip()]

errors = []

for i, row in enumerate(rows):
    messages = row["messages"]

    user = messages[1]["content"]

    role = (
        user.split("<ROLE>", 1)[1]
        .split("</ROLE>", 1)[0]
    )

    train_system = messages[0]["content"]
    runtime_system = SYSTEM[role]

    if train_system != runtime_system:
        errors.append((i, role))

print("Rows:", len(rows))
print("Prompt mismatches:", len(errors))

if errors:
    print("First mismatches:", errors[:10])
    raise SystemExit("PROMPT CONTRACT CHECK: FAIL")

print("PROMPT CONTRACT CHECK: PASS")
