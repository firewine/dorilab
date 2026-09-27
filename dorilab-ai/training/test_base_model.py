import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "Qwen/Qwen3-1.7B"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

print("Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)

messages = [
    {
        "role": "system",
        "content": """
You are the DoriLab Analysis Specialist.

Your job is to inspect engineering verification evidence
and select the next valid action.

Return JSON only.

Allowed actions:
- CALL_TOOL
- PROPOSE_FINDING
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE
""".strip(),
    },
    {
        "role": "user",
        "content": """
<ROLE>ANALYSIS</ROLE>

Requirement:
Duration = 60 seconds per axis

Actual:
X = 60
Y = 60
Z = 58

Available tool:
compare_duration(required_s, actual_s, axis)
""".strip(),
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

print("Generating...")

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=160,
        do_sample=False,
    )

new_tokens = outputs[0][inputs.input_ids.shape[1]:]

answer = tokenizer.decode(
    new_tokens,
    skip_special_tokens=True,
)

print()
print("===== MODEL OUTPUT =====")
print(answer)

print()
print("===== GPU MEMORY =====")
print(
    "Allocated:",
    round(torch.cuda.memory_allocated() / 1024**3, 2),
    "GB",
)
print(
    "Reserved :",
    round(torch.cuda.memory_reserved() / 1024**3, 2),
    "GB",
)
