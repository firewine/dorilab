import torch

from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer


MODEL_ID = "Qwen/Qwen3-1.7B"
DATA_FILE = "data/train_seed50.jsonl"
OUTPUT_DIR = "adapters/dorilab-common-smoke-v01"


print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


print("Loading dataset...")

dataset = load_dataset(
    "json",
    data_files=DATA_FILE,
    split="train",
)


def to_prompt_completion(example):

    messages = example["messages"]

    prompt_messages = messages[:-1]
    assistant_answer = messages[-1]["content"]

    prompt = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    completion = (
        assistant_answer
        + tokenizer.eos_token
    )

    return {
        "prompt": prompt,
        "completion": completion,
    }


dataset = dataset.map(
    to_prompt_completion,
    remove_columns=dataset.column_names,
)

print("Dataset rows:", len(dataset))

print()
print("Sample prompt:")
print(dataset[0]["prompt"][-800:])

print()
print("Sample completion:")
print(dataset[0]["completion"])


print()
print("Loading base model...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
)

model.config.use_cache = False


peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules="all-linear",
    bias="none",
    task_type="CAUSAL_LM",
)


args = SFTConfig(
    output_dir=OUTPUT_DIR,

    max_steps=10,

    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,

    learning_rate=1e-4,

    warmup_steps=1,
    weight_decay=0.01,

    bf16=True,

    gradient_checkpointing=True,

    max_length=1024,

    completion_only_loss=True,

    logging_steps=1,

    save_strategy="steps",
    save_steps=10,
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
print("===== TRAINABLE PARAMETERS =====")

trainer.model.print_trainable_parameters()


print()
print("===== START TRAINING =====")

trainer.train()


print()
print("===== SAVING ADAPTER =====")

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)


print()
print("Saved adapter to:")
print(OUTPUT_DIR)
