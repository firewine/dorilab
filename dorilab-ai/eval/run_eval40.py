import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import hashlib
import json
import re
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


MODEL_ID = "Qwen/Qwen3-1.7B"

INPUTS = Path("eval/eval40_inputs_v1.jsonl")
GOLD = Path("eval/eval40_gold_v1.jsonl")
MANIFEST = Path("eval/eval40_manifest_v1.json")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_lock():
    m = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    assert sha256(INPUTS) == m["inputs_sha256"], (
        "INPUT evaluation file changed!"
    )

    assert sha256(GOLD) == m["gold_sha256"], (
        "GOLD evaluation file changed!"
    )

    print("Evaluation-set lock: PASS")
    print("Version:", m["version"])


from runtime.dorilab_prompts_v01 import SYSTEM



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


print()
print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)


print("Loading base model...")

base_model = AutoModelForCausalLM.from_pretrained(
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


results = []

for idx, case in enumerate(inputs, start=1):

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

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    model_inputs = tokenizer(
        prompt,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():

        output = model.generate(
            **model_inputs,
            max_new_tokens=180,
            do_sample=False,
        )

    generated = output[0][
        model_inputs.input_ids.shape[1]:
    ]

    raw = tokenizer.decode(
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

    # DEV는 상세 출력 허용.
    # Holdout/Adversarial은 개별 결과를 화면에 숨김.
    if args.split == "dev":

        print(
            f"[{idx:02d}/{len(inputs):02d}] "
            f"{case['id']}: "
            f"{'PASS' if exact else 'FAIL'}"
        )


out = Path(
    f"eval/results/{args.label}_{args.split}.jsonl"
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


total = len(results)

passed = sum(
    x["pass"]
    for x in results
)

json_ok = sum(
    x["json_valid"]
    for x in results
)

action_ok = sum(
    x["action_ok"]
    for x in results
)


print()
print("=" * 64)
print(
    f"{args.label} / {args.split.upper()}"
)
print("=" * 64)

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

    n_pass = sum(
        x["pass"]
        for x in subset
    )

    print(
        f"{role:10s}: "
        f"{n_pass}/{len(subset)} "
        f"({n_pass/len(subset):.1%})"
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

    n_pass = sum(
        x["pass"]
        for x in subset
    )

    print(
        f"{action:22s}: "
        f"{n_pass}/{len(subset)} "
        f"({n_pass/len(subset):.1%})"
    )


print()
print("Saved:")
print(out)
