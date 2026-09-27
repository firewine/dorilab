"""Optional development-only baseline. GPU execution was not tested by the package author.

Runs source-evidence review candidates, NOT an independent or sealed evaluation.
Uses the same versioned prompt as the candidate SFT messages.
"""
from __future__ import annotations
import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tools.common import ROOT, action_errors, matches_gold, read_jsonl, sha256, write_json
from tools.validate_pack import validate
from runtime.physics_prompts_v01 import build_messages, POLICY_VERSION, SCHEMA_VERSION


def strict_object(text: str):
    try:
        obj = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen3.5-2B")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=384)
    args = parser.parse_args()
    if not 1 <= args.limit <= 32:
        raise SystemExit("--limit must be between 1 and 32")
    if not args.label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-." for c in args.label):
        raise SystemExit("Use letters, digits, _, - and . in --label")
    report = validate()
    if report["errors"]:
        raise SystemExit("Pack validation failed: " + "; ".join(report["errors"]))
    out = ROOT / "reports" / f"{args.label}.jsonl"
    summary_path = ROOT / "reports" / f"{args.label}.summary.json"
    if out.exists() or summary_path.exists():
        raise SystemExit("Result label already exists. Use a new --label to preserve earlier results.")
    adapter = args.adapter.resolve() if args.adapter else None
    if adapter is not None and not (adapter / "adapter_config.json").is_file():
        raise SystemExit(f"Adapter directory not found: {adapter}")
    # Import installed GPU packages only for this optional command.
    import torch
    import transformers
    from transformers import AutoProcessor
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this Python environment.")
    model_cls = getattr(transformers, "AutoModelForMultimodalLM", None)
    if model_cls is None:
        model_cls = getattr(transformers, "AutoModelForImageTextToText", None)
    if model_cls is None:
        raise SystemExit("Installed Transformers has no supported multimodal auto-model loader.")
    print("DEVELOPMENT DIAGNOSTIC: 32 synthetic source-grounded candidates; human labels pending.")
    print("Loading processor/model:", args.model, flush=True)
    processor = AutoProcessor.from_pretrained(args.model)
    model = model_cls.from_pretrained(args.model, dtype=torch.bfloat16, device_map={"": 0})
    if adapter is not None:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(adapter))
    model.eval()
    schema = json.loads((ROOT / "data/action_schema_v01.json").read_text(encoding="utf-8"))
    cases = read_jsonl(ROOT / "data/physics_cases_seed32_v01.jsonl")[:args.limit]
    rows = []
    started = datetime.now(timezone.utc).isoformat()
    with out.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cases, 1):
            messages = build_messages(c["role"], c["packet"])
            inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                  enable_thinking=False, return_dict=True, return_tensors="pt")
            n = int(inputs["input_ids"].shape[-1])
            if n > args.max_input_tokens:
                raise RuntimeError(f"{c['case_id']}: {n} tokens exceed limit; input was NOT silently truncated.")
            inputs = inputs.to(model.device)
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            begin = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(**inputs, do_sample=False, max_new_tokens=args.max_new_tokens)
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - begin
            tokens = output[0, n:]
            raw = processor.decode(tokens, skip_special_tokens=True)
            parsed = strict_object(raw)
            errors = action_errors(parsed, c["packet"], schema)
            row = {"case_id": c["case_id"], "pair_id": c["pair_id"], "role": c["role"],
                   "raw_output": raw, "output": parsed, "expected_candidate": c["expected"],
                   "strict_json_object": parsed is not None, "schema_errors": errors,
                   "action_match": isinstance(parsed, dict) and parsed.get("action") == c["expected"]["action"],
                   "full_match": not errors and matches_gold(c["expected"], parsed),
                   "input_tokens": n, "output_tokens": int(tokens.numel()),
                   "hit_generation_limit": int(tokens.numel()) >= args.max_new_tokens,
                   "generation_seconds": elapsed,
                   "peak_allocated_gib": torch.cuda.max_memory_allocated() / (1024**3),
                   "rendered_input_ids_sha256": __import__("hashlib").sha256(
                       json.dumps(inputs["input_ids"][0].tolist()).encode()).hexdigest()}
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i:02}/{len(cases):02}] {c['case_id']}: {'PASS' if row['full_match'] else 'FAIL'} | {elapsed:.2f}s", flush=True)
    pairs = defaultdict(list)
    for r in rows:
        pairs[r["pair_id"]].append(r)
    complete_pairs = [r for r in pairs.values() if len(r) == 2]
    no_action = [r for r in rows if r["expected_candidate"]["action"] == "NO_ACTION_REQUIRED"]
    summary = {
        "label": args.label, "started_at_utc": started, "model": args.model,
        "model_class": type(model).__name__, "adapter": str(adapter) if adapter else None,
        "adapter_sha256": sha256(adapter / "adapter_model.safetensors") if adapter and (adapter / "adapter_model.safetensors").is_file() else None,
        "evaluation_status": "DEVELOPMENT_CANDIDATE_LABELS_NOT_SEALED", "case_count": len(rows),
        "full_match_count": sum(r["full_match"] for r in rows),
        "action_match_count": sum(r["action_match"] for r in rows),
        "strict_json_count": sum(r["strict_json_object"] for r in rows),
        "schema_valid_count": sum(not r["schema_errors"] for r in rows),
        "complete_pairs": len(complete_pairs),
        "both_members_full_match": sum(all(r["full_match"] for r in p) for p in complete_pairs),
        "no_action_cases": len(no_action),
        "false_interventions": sum(isinstance(r["output"], dict) and r["output"].get("action") in {"CHALLENGE", "REQUEST_EVIDENCE"} for r in no_action),
        "generation_seconds_total": sum(r["generation_seconds"] for r in rows),
        "input_tokens_total": sum(r["input_tokens"] for r in rows),
        "output_tokens_total": sum(r["output_tokens"] for r in rows),
        "policy_version": POLICY_VERSION, "schema_version": SCHEMA_VERSION,
        "prompt_sha256": sha256(ROOT / "runtime/physics_prompts_v01.py"),
        "torch": torch.__version__, "transformers": transformers.__version__,
        "gpu": torch.cuda.get_device_name(0), "thinking": False,
        "note": "New source-review contract. Results are not directly comparable with previous Contract150/Eval40 scores.",
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Saved:", out)

if __name__ == "__main__":
    main()
