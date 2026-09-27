import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import torch

from transformers import (
    AutoProcessor,
    AutoModelForMultimodalLM,
)

from peft import PeftModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.dorilab_prompts_v01 import SYSTEM


MODEL_ID = "Qwen/Qwen3.5-2B"

INPUTS = Path("eval/eval40_inputs_v1.jsonl")
GOLD = Path("eval/eval40_gold_v1.jsonl")
MANIFEST = Path("eval/eval40_manifest_v1.json")


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)

            if not b:
                break

            h.update(b)

    return h.hexdigest()


def verify_lock():
    m = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    assert sha256(INPUTS) == m["inputs_sha256"]
    assert sha256(GOLD) == m["gold_sha256"]

    print("Evaluation-set lock: PASS")
    print("Version:", m["version"])


def parse_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    try:
        return json.loads(text)

    except Exception:
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            try:
                return json.loads(
                    text[start:end + 1]
                )
            except Exception:
                pass

    return None


def expected_subset(expected, actual):
    if not isinstance(actual, dict):
        return False

    for key, value in expected.items():

        if key not in actual:
            return False

        actual_value = actual[key]

        if isinstance(value, dict):

            if not expected_subset(
                value,
                actual_value,
            ):
                return False

        else:
            if actual_value != value:
                return False

    return True


parser = argparse.ArgumentParser()

parser.add_argument(
    "--split",
    required=True,
    choices=[
        "dev",
        "holdout",
        "adversarial",
    ],
)

parser.add_argument(
    "--adapter",
    default=None,
)

parser.add_argument(
    "--label",
    required=True,
)

args = parser.parse_args()


verify_lock()


# ---------------------------------------------------------
# Load evaluation input
# ---------------------------------------------------------

inputs = []

with INPUTS.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        row = json.loads(line)

        if row["split"] == args.split:
            inputs.append(row)


gold = {}

with GOLD.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        row = json.loads(line)

        gold[row["id"]] = row["expected"]


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------

print()
print("Loading processor...")

processor = AutoProcessor.from_pretrained(
    MODEL_ID
)


print("Loading Qwen3.5-2B...")

base_model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)


if args.adapter:

    print("Loading LoRA adapter:")
    print(args.adapter)

    model = PeftModel.from_pretrained(
        base_model,
        args.adapter,
    )

else:

    model = base_model


model.eval()


print()
print(
    "GPU:",
    torch.cuda.get_device_name(0),
)

print(
    "VRAM after load:",
    round(
        torch.cuda.memory_allocated()
        / 1024**3,
        2,
    ),
    "GB",
)


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

results = []


for idx, case in enumerate(
    inputs,
    start=1,
):

    role = case["role"]

    messages = [
        {
            "role": "system",
            "content": SYSTEM[role],
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


    model_inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )

    model_inputs = model_inputs.to(
        model.device
    )


    with torch.no_grad():

        output = model.generate(
            **model_inputs,
            max_new_tokens=180,
            do_sample=False,
        )


    generated = output[0][
        model_inputs["input_ids"].shape[-1]:
    ]


    raw = processor.decode(
        generated,
        skip_special_tokens=True,
    )


    parsed = parse_json(raw)

    expected = gold[case["id"]]

    json_valid = parsed is not None

    action_ok = (
        json_valid
        and parsed.get("action")
        == expected.get("action")
    )

    exact = expected_subset(
        expected,
        parsed,
    )


    results.append({
        "id": case["id"],
        "split": case["split"],
        "role": role,
        "expected": expected,
        "output": parsed,
        "raw_output": raw,
        "json_valid": json_valid,
        "action_ok": action_ok,
        "pass": exact,
    })


    if args.split == "dev":

        print(
            f"[{idx:02d}/{len(inputs):02d}] "
            f"{case['id']}: "
            f"{'PASS' if exact else 'FAIL'}"
        )


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

out = Path(
    f"eval/results/"
    f"{args.label}_{args.split}.jsonl"
)

out.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with out.open(
    "w",
    encoding="utf-8",
) as f:

    for row in results:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

total = len(results)

passed = sum(
    x["pass"]
    for x in results
)

action_ok = sum(
    x["action_ok"]
    for x in results
)

json_ok = sum(
    x["json_valid"]
    for x in results
)


print()
print("=" * 70)

print(
    f"{args.label} / "
    f"{args.split.upper()}"
)

print("=" * 70)


print(
    f"Exact PASS      : "
    f"{passed}/{total} "
    f"({passed/total:.1%})"
)

print(
    f"Action accuracy : "
    f"{action_ok}/{total} "
    f"({action_ok/total:.1%})"
)

print(
    f"Valid JSON      : "
    f"{json_ok}/{total} "
    f"({json_ok/total:.1%})"
)


print()
print("BY ROLE")


for role in [
    "ANALYSIS",
    "EVIDENCE",
    "CRITIC",
]:

    subset = [
        x for x in results
        if x["role"] == role
    ]

    if not subset:
        continue

    n = sum(
        x["pass"]
        for x in subset
    )

    print(
        f"{role:10s}: "
        f"{n}/{len(subset)} "
        f"({n/len(subset):.1%})"
    )


print()
print("BY GOLD ACTION")


actions = sorted(
    set(
        x["expected"]["action"]
        for x in results
    )
)


for action in actions:

    subset = [
        x for x in results
        if x["expected"]["action"]
        == action
    ]

    n = sum(
        x["pass"]
        for x in subset
    )

    print(
        f"{action:22s}: "
        f"{n}/{len(subset)} "
        f"({n/len(subset):.1%})"
    )


print()
print("Saved:")
print(out)
