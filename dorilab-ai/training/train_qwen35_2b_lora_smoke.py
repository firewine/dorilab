import torch

from datasets import load_dataset

from transformers import (
    AutoProcessor,
    AutoModelForMultimodalLM,
)

from peft import LoraConfig

from trl import (
    SFTConfig,
    SFTTrainer,
)


MODEL_ID = "Qwen/Qwen3.5-2B"
DATA_FILE = "data/train150_v01.jsonl"

OUTPUT_DIR = (
    "adapters/"
    "dorilab-qwen35-2b-smoke-v01"
)


print("=" * 70)
print("DoriLab Qwen3.5-2B LoRA SMOKE")
print("=" * 70)


# ---------------------------------------------------------
# Processor / tokenizer
# ---------------------------------------------------------

print("Loading processor...")

processor = AutoProcessor.from_pretrained(
    MODEL_ID
)

tokenizer = processor.tokenizer

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


# ---------------------------------------------------------
# Dataset
# ---------------------------------------------------------

print("Loading dataset...")

dataset = load_dataset(
    "json",
    data_files=DATA_FILE,
    split="train",
)


def to_prompt_completion(example):

    messages = example["messages"]

    prompt_messages = messages[:-1]
    answer = messages[-1]["content"]

    prompt = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    return {
        "prompt": prompt,
        "completion": answer,
    }


dataset = dataset.map(
    to_prompt_completion,
    remove_columns=dataset.column_names,
)

print(
    "Training examples:",
    len(dataset),
)


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------

print("Loading Qwen3.5-2B base...")

model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
)

model.config.use_cache = False


# ---------------------------------------------------------
# LANGUAGE-ONLY LoRA
# ---------------------------------------------------------

TARGET_MODULES = [
    # Standard self attention
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",

    # Qwen3.5 linear attention
    "in_proj_qkv",
    "in_proj_z",
    "in_proj_b",
    "in_proj_a",
    "out_proj",

    # MLP
    "gate_proj",
    "up_proj",
    "down_proj",
]


peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,

    target_modules=TARGET_MODULES,

    bias="none",
    task_type="CAUSAL_LM",
)


args = SFTConfig(
    output_dir=OUTPUT_DIR,

    # Smoke only
    max_steps=5,

    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,

    learning_rate=5e-5,

    warmup_steps=1,

    weight_decay=0.01,

    bf16=True,

    gradient_checkpointing=True,

    max_length=1024,

    completion_only_loss=True,

    logging_steps=1,

    save_strategy="steps",
    save_steps=5,
    save_total_limit=1,

    report_to="none",

    seed=42,
)


trainer = SFTTrainer(
    model=model,
    args=args,
    train_dataset=dataset,
    processing_class=tokenizer,
    peft_config=peft_config,
)


print()
print("=" * 70)
print("TRAINABLE PARAMETERS")
print("=" * 70)

trainer.model.print_trainable_parameters()


# ---------------------------------------------------------
# Verify that vision received NO LoRA
# ---------------------------------------------------------

print()
print("=" * 70)
print("LoRA MODULE CHECK")
print("=" * 70)

vision_lora = []
language_lora = []

for name, module in trainer.model.named_modules():

    lname = name.lower()

    if "lora_" not in lname:
        continue

    if "visual" in lname:
        vision_lora.append(name)

    if "language_model" in lname:
        language_lora.append(name)


print(
    "Language LoRA modules:",
    len(language_lora),
)

print(
    "Vision LoRA modules:",
    len(vision_lora),
)


if vision_lora:
    print()
    print("ERROR: LoRA was attached to vision modules!")

    for x in vision_lora[:20]:
        print(x)

    raise RuntimeError(
        "Vision LoRA detected."
    )


print()
print("Vision isolation: PASS")


# ---------------------------------------------------------
# Training
# ---------------------------------------------------------

print()
print("=" * 70)
print("START 5-STEP SMOKE TRAINING")
print("=" * 70)

trainer.train()


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

print()
print("=" * 70)
print("SAVE SMOKE ADAPTER")
print("=" * 70)

trainer.save_model(
    OUTPUT_DIR
)

processor.save_pretrained(
    OUTPUT_DIR
)


print()
print("Saved:")
print(OUTPUT_DIR)
