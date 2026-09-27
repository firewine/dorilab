import torch

from transformers import (
    AutoModelForMultimodalLM,
)


MODEL_ID = "Qwen/Qwen3.5-2B"


print("Loading Qwen3.5-2B...")

model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
)


print()
print("=" * 100)
print("MODEL CLASS")
print("=" * 100)

print(type(model))


print()
print("=" * 100)
print("TOP LEVEL CHILDREN")
print("=" * 100)

for name, child in model.named_children():

    print(
        f"{name:30s}",
        type(child),
    )


print()
print("=" * 100)
print("LINEAR MODULES")
print("=" * 100)


count = 0


for name, module in model.named_modules():

    if isinstance(
        module,
        torch.nn.Linear,
    ):

        print(name)

        count += 1


print()
print(
    "Total Linear modules:",
    count,
)


print()
print("=" * 100)
print("LIKELY VISION MODULES")
print("=" * 100)


for name, module in model.named_modules():

    lname = name.lower()

    if (
        "vision" in lname
        or "visual" in lname
    ):

        if isinstance(
            module,
            torch.nn.Linear,
        ):

            print(name)
