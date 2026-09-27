import json
import re
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


MODEL_ID = "Qwen/Qwen3-1.7B"
CASE_FILE = Path("eval/cases_baseline.jsonl")
OUTPUT_FILE = Path("eval/results/base_1p7b_prompt_v1_results.jsonl")


COMMON_POLICY = """
DoriLab execution policy:

1. Use an available deterministic calculation tool when the required inputs exist.
2. Do not invent tolerance, acceptance margin, waiver, or engineering criteria.
3. Missing evidence means evidence is missing. It does not mean pass or fail.
4. Evidence from a different configuration or revision requires applicability review or matching evidence.
5. Findings must be limited to the scope actually supported by the evidence.
6. If a proposed finding claims more than the evidence supports, challenge it.
7. Return one JSON object only. Do not use markdown or explanatory text outside JSON.
""".strip()


SYSTEM_PROMPTS = {
    "ANALYSIS": f"""
You are the DoriLab Analysis Specialist.

Your role:
- inspect numerical engineering verification state
- choose the next valid action
- prefer deterministic tools for deterministic comparisons

{COMMON_POLICY}

Allowed actions:
- CALL_TOOL
- PROPOSE_FINDING
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

When calling a tool, use:
{{
  "action": "CALL_TOOL",
  "tool": "<tool_name>",
  "arguments": {{ ... }}
}}
""".strip(),

    "EVIDENCE": f"""
You are the DoriLab Evidence Specialist.

Your role:
- inspect requirement, procedure, revision, configuration and evidence
- distinguish missing evidence from noncompliance
- detect configuration or revision mismatches

{COMMON_POLICY}

Allowed actions:
- PROPOSE_FINDING
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

For a procedure/requirement mismatch use:
{{
  "action": "PROPOSE_FINDING",
  "finding_type": "PROCEDURE_REQUIREMENT_CONFLICT"
}}

For missing or mismatched evidence use:
{{
  "action": "REQUEST_EVIDENCE",
  "reason": "<reason>"
}}
""".strip(),

    "CRITIC": f"""
You are the DoriLab Critic.

Your role:
- inspect whether a proposed finding is supported by evidence
- verify scope, configuration and logical consistency

{COMMON_POLICY}

Allowed actions:
- CHALLENGE
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

If a finding claims failure outside the supported scope use:
{{
  "action": "CHALLENGE",
  "reason": "SCOPE_ERROR",
  "valid_scope": "<supported scope>"
}}
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

        if not actual_args:
            actual_args = {
                k: actual.get(k)
                for k in expected_args.keys()
            }

        result["arguments"] = all(
            actual_args.get(k) == v
            for k, v in expected_args.items()
        )

    checks = [
        result["json_valid"],
        result["action"]
    ]

    if result["tool"] is not None:
        checks.append(result["tool"])

    if result["arguments"] is not None:
        checks.append(result["arguments"])

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
            max_new_tokens=160,
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
passed = sum(r["score"]["overall"] for r in results)
json_ok = sum(r["score"]["json_valid"] for r in results)
action_ok = sum(r["score"]["action"] for r in results)

print()
print("=" * 60)
print("PROMPT-V1 BASELINE SUMMARY")
print("=" * 60)
print(f"Total cases       : {total}")
print(f"Overall PASS      : {passed}/{total} ({passed/total:.1%})")
print(f"Valid JSON        : {json_ok}/{total} ({json_ok/total:.1%})")
print(f"Correct action    : {action_ok}/{total} ({action_ok/total:.1%})")
print()
print("Saved:")
print(OUTPUT_FILE)
