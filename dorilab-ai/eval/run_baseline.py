import json
import re
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


MODEL_ID = "Qwen/Qwen3-1.7B"
CASE_FILE = Path("eval/cases_baseline.jsonl")
OUTPUT_FILE = Path("eval/results/base_1p7b_results.jsonl")


SYSTEM_PROMPTS = {
    "ANALYSIS": """
You are the DoriLab Analysis Specialist.
Inspect engineering verification state and select the next valid action.

Allowed actions:
CALL_TOOL
PROPOSE_FINDING
REQUEST_EVIDENCE
NO_ACTION_REQUIRED
ESCALATE

Return one JSON object only.
Do not use markdown.
""".strip(),

    "EVIDENCE": """
You are the DoriLab Evidence Specialist.
Inspect requirement, procedure, revision, configuration and evidence information.

Allowed actions:
PROPOSE_FINDING
REQUEST_EVIDENCE
NO_ACTION_REQUIRED
ESCALATE

Return one JSON object only.
Do not use markdown.
""".strip(),

    "CRITIC": """
You are the DoriLab Critic.
Check whether the proposed finding is supported by the supplied evidence and scope.

Allowed actions:
CHALLENGE
REQUEST_EVIDENCE
NO_ACTION_REQUIRED
ESCALATE

Return one JSON object only.
Do not use markdown.
""".strip(),
}


def parse_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

    return None


def score(expected, actual):
    result = {
        "json_valid": actual is not None,
        "action": False,
        "tool": None,
        "arguments": None,
        "overall": False,
    }

    if actual is None:
        return result

    result["action"] = actual.get("action") == expected.get("action")

    if "tool" in expected:
        result["tool"] = actual.get("tool") == expected.get("tool")

    expected_args = expected.get("arguments")

    if expected_args is not None:
        actual_args = actual.get("arguments", {})

        # Some base models may flatten arguments.
        if not actual_args:
            actual_args = {
                k: actual.get(k)
                for k in expected_args.keys()
            }

        result["arguments"] = all(
            actual_args.get(k) == v
            for k, v in expected_args.items()
        )

    checks = [result["json_valid"], result["action"]]

    if result["tool"] is not None:
        checks.append(result["tool"])

    if result["arguments"] is not None:
        checks.append(result["arguments"])

    # Score other expected top-level semantic fields.
    ignored = {"action", "tool", "arguments"}

    for key, value in expected.items():
        if key in ignored:
            continue

        checks.append(actual.get(key) == value)

    result["overall"] = all(checks)

    return result


print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

print("Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)

cases = []

with CASE_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            cases.append(json.loads(line))

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

results = []

for i, case in enumerate(cases, start=1):

    role = case["role"]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS[role],
        },
        {
            "role": "user",
            "content": (
                f"<ROLE>{role}</ROLE>\n"
                f"CASE_ID: {case['id']}\n"
                f"STATE:\n"
                f"{json.dumps(case['input'], ensure_ascii=False, indent=2)}"
            ),
        },
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(
        text,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=180,
            do_sample=False,
        )

    generated = outputs[0][inputs.input_ids.shape[1]:]

    raw_output = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    )

    parsed = parse_json(raw_output)

    scores = score(
        case["expected"],
        parsed,
    )

    row = {
        "id": case["id"],
        "role": role,
        "expected": case["expected"],
        "output": parsed,
        "raw_output": raw_output,
        "score": scores,
    }

    results.append(row)

    mark = "PASS" if scores["overall"] else "FAIL"

    print(
        f"[{i:02d}/{len(cases):02d}] "
        f"{case['id']}: {mark}"
    )

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    for row in results:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            ) + "\n"
        )

total = len(results)
passed = sum(
    1 for r in results
    if r["score"]["overall"]
)

json_ok = sum(
    1 for r in results
    if r["score"]["json_valid"]
)

action_ok = sum(
    1 for r in results
    if r["score"]["action"]
)

print()
print("=" * 60)
print("BASELINE SUMMARY")
print("=" * 60)
print(f"Total cases       : {total}")
print(f"Overall PASS      : {passed}/{total} ({passed/total:.1%})")
print(f"Valid JSON        : {json_ok}/{total} ({json_ok/total:.1%})")
print(f"Correct action    : {action_ok}/{total} ({action_ok/total:.1%})")
print()
print("Saved:")
print(OUTPUT_FILE)
