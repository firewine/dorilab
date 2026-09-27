import torch

from transformers import (
    AutoProcessor,
    AutoModelForMultimodalLM,
)

from runtime.dorilab_prompts_v01 import SYSTEM


MODEL_ID = "Qwen/Qwen3.5-2B"


print("=" * 70)
print("DoriLab Qwen3.5-2B BASE TEST")
print("=" * 70)

print("Loading processor...")

processor = AutoProcessor.from_pretrained(
    MODEL_ID
)


print("Loading model...")

model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="auto",
)

model.eval()


print()
print("GPU:", torch.cuda.get_device_name(0))

print(
    "Allocated after load:",
    round(
        torch.cuda.memory_allocated() / 1024**3,
        2,
    ),
    "GB",
)


messages = [
    {
        "role": "system",
        "content": SYSTEM["ANALYSIS"],
    },
    {
        "role": "user",
        "content": """
<ROLE>ANALYSIS</ROLE>

STATE:
{
  "task": "CHECK_AXIS_DURATION",
  "requirement_s": 60,
  "actual_by_axis": {
    "X": 60,
    "Y": 60,
    "Z": 58
  },
  "tool_result": null
}
""".strip(),
    },
]


print()
print("Building prompt...")

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
)

inputs = inputs.to(model.device)


print("Generating...")

with torch.no_grad():

    outputs = model.generate(
        **inputs,
        max_new_tokens=180,
        do_sample=False,
    )


generated = outputs[0][
    inputs["input_ids"].shape[-1]:
]


answer = processor.decode(
    generated,
    skip_special_tokens=True,
)


print()
print("=" * 70)
print("MODEL OUTPUT")
print("=" * 70)

print(answer)


print()
print("=" * 70)
print("GPU MEMORY")
print("=" * 70)

print(
    "Allocated:",
    round(
        torch.cuda.memory_allocated() / 1024**3,
        2,
    ),
    "GB",
)

print(
    "Reserved:",
    round(
        torch.cuda.memory_reserved() / 1024**3,
        2,
    ),
    "GB",
)
