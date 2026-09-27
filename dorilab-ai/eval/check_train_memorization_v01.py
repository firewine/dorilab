import json
import re

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


MODEL_ID = "Qwen/Qwen3-1.7B"
ADAPTER = "adapters/dorilab-common-1p7b-v01"
DATA = "data/train150_v01.jsonl"


def parse_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        a = text.find("{")
        b = text.rfind("}")

        if a >= 0 and b > a:
            try:
                return json.loads(text[a:b+1])
            except Exception:
                return None

    return None


def subset(expected, actual):
    if not isinstance(actual, dict):
        return False

    for k, v in expected.items():
        if k not in actual:
            return False

        if isinstance(v, dict):
            if not subset(v, actual[k]):
                return False
        elif actual[k] != v:
            return False

    return True


with open(DATA, "r", encoding="utf-8") as f:
    rows = [json.loads(x) for x in f if x.strip()]


# 역할별/데이터 구간별로 흩어서 15개 선택
indices = [
    0, 5, 10, 20, 29,       # Analysis
    30, 40, 55, 70, 89,     # Evidence
    90, 100, 115, 130, 149, # Critic
]


print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

print("Loading base...")
base = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)

print("Loading adapter...")
model = PeftModel.from_pretrained(
    base,
    ADAPTER,
)

model.eval()

passed = 0

for n, idx in enumerate(indices, 1):

    row = rows[idx]

    messages = row["messages"]

    prompt_messages = messages[:-1]

    expected = json.loads(
        messages[-1]["content"]
    )

    text = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(
        text,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=180,
            do_sample=False,
        )

    generated = output[0][
        inputs.input_ids.shape[1]:
    ]

    raw = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    )

    actual = parse_json(raw)

    ok = subset(expected, actual)

    if ok:
        passed += 1

    role = (
        messages[1]["content"]
        .split("<ROLE>")[1]
        .split("</ROLE>")[0]
    )

    print()
    print("=" * 80)
    print(
        f"[{n:02d}/15] "
        f"index={idx} role={role} "
        f"{'PASS' if ok else 'FAIL'}"
    )
    print("EXPECTED:")
    print(json.dumps(expected, ensure_ascii=False, indent=2))
    print("OUTPUT:")
    print(json.dumps(actual, ensure_ascii=False, indent=2))
    print("RAW:")
    print(raw)


print()
print("=" * 80)
print("TRAIN MEMORIZATION CHECK")
print("=" * 80)
print(
    f"PASS: {passed}/15 "
    f"({passed/15:.1%})"
)
