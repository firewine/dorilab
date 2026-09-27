import json
import re
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


MODEL_ID = "Qwen/Qwen3-1.7B"
ADAPTER_DIR = "adapters/dorilab-common-smoke-v01"
CASE_FILE = Path("eval/cases_contract_v1.jsonl")
OUTPUT_FILE = Path("eval/results/lora_smoke_1p7b_contract_v1.jsonl")


COMMON = """
You operate under the DoriLab engineering execution contract.

General rules:
- Do not invent engineering criteria.
- Missing evidence is not the same as failure.
- Evidence must match configuration and revision, or applicability must be established.
- Findings must not exceed the scope supported by evidence.
- Return exactly one JSON object.
- Do not use markdown.
""".strip()


SYSTEM_PROMPTS = {

    "ANALYSIS": f"""
You are the DoriLab Analysis Specialist.

{COMMON}

Available deterministic tool:

compare_axis_durations
Arguments:
- required_s: number
- actual_by_axis: object mapping axis names to measured durations

When task is CHECK_AXIS_DURATION, do not perform the engineering
acceptance comparison yourself. Request the deterministic tool.

Allowed output:

{{
  "action": "CALL_TOOL",
  "tool": "compare_axis_durations",
  "arguments": {{
    "required_s": <copy from state>,
    "actual_by_axis": <copy from state>
  }}
}}
""".strip(),

    "EVIDENCE": f"""
You are the DoriLab Evidence Specialist.

{COMMON}

Allowed actions:
- PROPOSE_FINDING
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

Finding types:
- PROCEDURE_REQUIREMENT_CONFLICT

REQUEST_EVIDENCE reason codes:
- CONFIGURATION_MISMATCH
- REVISION_MISMATCH
- AS_RUN_MISSING

Rules:
- A procedure value conflicting with a requirement is a
  PROCEDURE_REQUIREMENT_CONFLICT.
- A different configuration without applicability evidence requires
  CONFIGURATION_MISMATCH evidence review.
- A different requirement revision without supersession/applicability
  review requires REVISION_MISMATCH review.
- Missing as-run evidence requires AS_RUN_MISSING.
""".strip(),

    "CRITIC": f"""
You are the DoriLab Critic.

{COMMON}

Allowed actions:
- CHALLENGE
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

CHALLENGE reason codes:
- SCOPE_ERROR
- EVIDENCE_CONTRADICTION
- CONFIGURATION_MISMATCH

If the claimed scope exceeds the tool/evidence-supported scope:
{{
  "action": "CHALLENGE",
  "reason": "SCOPE_ERROR",
  "valid_scope": [...]
}}

If the conclusion contradicts deterministic evidence:
{{
  "action": "CHALLENGE",
  "reason": "EVIDENCE_CONTRADICTION",
  "valid_scope": [...]
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


def compare_expected(expected, actual):
    if actual is None:
        return False

    for key, expected_value in expected.items():
        if key not in actual:
            return False

        if actual[key] != expected_value:
            return False

    return True


print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

print("Loading model...")
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(
    base_model,
    ADAPTER_DIR,
)

model.eval()

cases = []

with CASE_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            cases.append(json.loads(line))

results = []

for i, case in enumerate(cases, 1):

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
                "STATE:\n"
                + json.dumps(
                    case["input"],
                    ensure_ascii=False,
                    indent=2,
                )
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

    raw = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    )

    parsed = parse_json(raw)

    passed = compare_expected(
        case["expected"],
        parsed,
    )

    results.append({
        "id": case["id"],
        "role": role,
        "expected": case["expected"],
        "output": parsed,
        "raw_output": raw,
        "pass": passed,
    })

    print(
        f"[{i:02d}/{len(cases):02d}] "
        f"{case['id']}: "
        f"{'PASS' if passed else 'FAIL'}"
    )

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    for row in results:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )

passed = sum(r["pass"] for r in results)
total = len(results)

print()
print("=" * 60)
print("LORA-SMOKE CONTRACT-V1 SUMMARY")
print("=" * 60)
print(f"Overall PASS : {passed}/{total} ({passed/total:.1%})")

for role in ["ANALYSIS", "EVIDENCE", "CRITIC"]:
    subset = [r for r in results if r["role"] == role]

    role_pass = sum(r["pass"] for r in subset)

    print(
        f"{role:10s} : "
        f"{role_pass}/{len(subset)} "
        f"({role_pass/len(subset):.1%})"
    )

print()
print("Saved:", OUTPUT_FILE)
