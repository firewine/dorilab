#!/usr/bin/env python3
"""
DoriLab 9B~27B baseline tournament.

Purpose
- Reuse the frozen 84-case development/regression inputs already imported by
  the Gemma project.
- Run each candidate with its native tokenizer/chat template and BF16 weights.
- Pass only system+user messages to the model. Offline expected answers are
  used only after generation by the existing DoriLab scorer.
- Save raw outputs, per-case scores, load/memory/timing records and one summary.
- No training, label changes, score repair, deployment or engineering approval.

Default candidates
  Qwen/Qwen3.5-9B
  google/gemma-4-12B-it
  mistralai/Mistral-Small-3.2-24B-Instruct-2506
  google/gemma-4-26B-A4B-it
  Qwen/Qwen3.8-27B
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

VERSION = "dorilab-model-tournament-v1.0.0"
SUITES = {"ns10": 24, "before40": 40, "contract20": 20}
MAX_TOTAL = 2048
MAX_NEW = 384

REGISTRY = {
    "qwen35_9b": {
        "model": "Qwen/Qwen3.5-9B",
        "family": "hf_native",
        "thinking": False,
    },
    "gemma4_12b": {
        "model": "google/gemma-4-12B-it",
        "family": "hf_native",
        "thinking": False,
    },
    "mistral32_24b": {
        "model": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "family": "mistral_common",
        "thinking": None,
    },
    "gemma4_26b_a4b": {
        "model": "google/gemma-4-26B-A4B-it",
        "family": "hf_native",
        "thinking": False,
    },
    "qwen38_27b": {
        "model": "Qwen/Qwen3.8-27B",
        "family": "hf_native",
        "thinking": False,
    },
}

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def now():
    return datetime.now(timezone.utc).isoformat()

def strict_json_text(s: str):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, f"duplicate JSON key: {k}")
            out[k] = v
        return out
    def bad(x):
        raise ValueError("non-finite JSON: " + x)
    return json.loads(s, object_pairs_hook=pairs, parse_constant=bad)

def read_json(path: Path):
    return strict_json_text(path.read_text(encoding="utf-8-sig"))

def read_jsonl(path: Path):
    rows = [strict_json_text(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    require(rows and all(isinstance(x, dict) for x in rows), f"expected JSONL objects: {path}")
    return rows

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"preserving existing file: {path}")
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

def append_jsonl(path: Path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()

def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def digest(obj):
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()

def safe_slug(repo_id: str):
    return repo_id.replace("/", "--")

def import_scorer(project: Path):
    package_dir = project / "dorilab_gemma"
    scoring_path = package_dir / "scoring.py"
    require(package_dir.is_dir(), f"missing package: {package_dir}")
    require(scoring_path.is_file(), f"missing scorer: {scoring_path}")

    # Import it as its real package so relative imports such as
    # `from .common import ...` continue to work.
    project_str = str(project)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)

    mod = importlib.import_module("dorilab_gemma.scoring")
    require(hasattr(mod, "score") and hasattr(mod, "aggregate"), "scorer API missing")
    return mod

def validate_eval(project: Path):
    schema_path = project / "data/action_schema.json"
    comparison_path = project / "reports/comparison.json"
    require(schema_path.is_file(), f"missing {schema_path}")
    require(comparison_path.is_file(), f"missing {comparison_path}")
    schema = read_json(schema_path)
    historical = read_json(comparison_path)
    inputs = {}
    frozen = {
        "data/action_schema.json": sha(schema_path),
        "reports/comparison.json": sha(comparison_path),
        "dorilab_gemma/scoring.py": sha(project / "dorilab_gemma/scoring.py"),
    }
    for suite, count in SUITES.items():
        p = project / f"data/eval_{suite}.jsonl"
        require(p.is_file(), f"missing {p}")
        rows = read_jsonl(p)
        require(len(rows) == count, f"{suite}: expected {count}, got {len(rows)}")
        require(len({r["case_id"] for r in rows}) == count, f"{suite}: duplicate case_id")
        for r in rows:
            msgs = r.get("messages")
            require(isinstance(msgs, list) and [m.get("role") for m in msgs] == ["system", "user"],
                    f"{suite}/{r.get('case_id')}: model input must be system+user only")
            require(isinstance(r.get("case", {}).get("expected"), dict),
                    f"{suite}/{r.get('case_id')}: offline expected missing")
        inputs[suite] = rows
        frozen[f"data/eval_{suite}.jsonl"] = sha(p)
    return schema, historical, inputs, frozen

def environment():
    import torch, transformers, accelerate, peft, datasets, huggingface_hub
    return {
        "python": sys.version,
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "transformers": transformers.__version__,
        "accelerate": accelerate.__version__,
        "peft": peft.__version__,
        "datasets": datasets.__version__,
        "huggingface_hub": huggingface_hub.__version__,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
        "vram_GiB": torch.cuda.get_device_properties(0).total_memory / 1024**3 if torch.cuda.is_available() else None,
        "hf_home": os.environ.get("HF_HOME"),
    }

def resolve_revision(model_id: str):
    from transformers import AutoConfig
    from huggingface_hub import HfApi

    # transformers 5.x no longer reliably exposes the resolved Hub commit
    # through config._commit_hash. Resolve the immutable SHA from the Hub API
    # first, then load the config pinned to that exact revision.
    info = HfApi().model_info(model_id, revision="main")
    rev = getattr(info, "sha", None)
    require(isinstance(rev, str) and re.fullmatch(r"[0-9a-f]{40}", rev or ""),
            f"{model_id}: immutable revision could not be resolved from Hugging Face Hub")
    cfg = AutoConfig.from_pretrained(
        model_id,
        revision=rev,
        trust_remote_code=False,
    )
    return cfg, rev

@dataclass
class NativePrompt:
    processor: object

    def encode(self, messages):
        p = self.processor
        kwargs = dict(tokenize=False, add_generation_prompt=True)
        # Current Qwen/Gemma templates accept this. If a future tokenizer
        # removes it, retry without changing message contents.
        try:
            text = p.apply_chat_template(messages, enable_thinking=False, **kwargs)
        except TypeError:
            text = p.apply_chat_template(messages, **kwargs)
        tok = p.tokenizer
        ids = tok(text, add_special_tokens=False, truncation=False)["input_ids"]
        require(ids and isinstance(ids[0], int), "invalid native tokenization")
        return ids, digest(text)

    @property
    def decoder(self):
        return self.processor.tokenizer

@dataclass
class MistralPrompt:
    tokenizer: object

    def encode(self, messages):
        from mistral_common.protocol.instruct.request import ChatCompletionRequest
        # Keep DoriLab's exact system/user contents. This is a task benchmark,
        # so the repository's general-assistant SYSTEM_PROMPT is not injected.
        tokenized = self.tokenizer.encode_chat_completion(ChatCompletionRequest(messages=messages))
        ids = list(tokenized.tokens)
        require(ids and isinstance(ids[0], int), "invalid Mistral tokenization")
        return ids, digest(ids)

    @property
    def decoder(self):
        return self.tokenizer

def build_prompt_adapter(entry, revision):
    if entry["family"] == "mistral_common":
        from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
        tok = MistralTokenizer.from_hf_hub(entry["model"], revision=revision)
        return MistralPrompt(tok)
    from transformers import AutoProcessor
    p = AutoProcessor.from_pretrained(entry["model"], revision=revision, trust_remote_code=False)
    require(getattr(p, "tokenizer", None) is not None, f"{entry['model']}: processor tokenizer missing")
    return NativePrompt(p)

def load_model(entry, revision):
    import torch
    if entry["family"] == "mistral_common":
        from transformers import Mistral3ForConditionalGeneration
        cls = Mistral3ForConditionalGeneration
    else:
        from transformers import AutoModelForMultimodalLM
        cls = AutoModelForMultimodalLM
    t0 = time.perf_counter()
    model = cls.from_pretrained(
        entry["model"],
        revision=revision,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        device_map={"": 0},
        low_cpu_mem_usage=True,
        attn_implementation="sdpa",
    )
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    torch.cuda.synchronize()
    return model, {
        "load_seconds": time.perf_counter() - t0,
        "model_class": type(model).__name__,
        "allocated_GiB": torch.cuda.memory_allocated() / 1024**3,
        "reserved_GiB": torch.cuda.memory_reserved() / 1024**3,
    }

def eos_ids(model, decoder):
    values = set()
    candidates = [
        getattr(decoder, "eos_token_id", None),
        getattr(model.generation_config, "eos_token_id", None),
        getattr(model.config, "eos_token_id", None),
        getattr(getattr(model.config, "text_config", None), "eos_token_id", None),
    ]
    for v in candidates:
        if isinstance(v, int):
            values.add(v)
        elif isinstance(v, (list, tuple, set)):
            values.update(x for x in v if isinstance(x, int))
    # Native turn tokens used by the currently selected Qwen/Gemma families.
    if hasattr(decoder, "get_vocab") and hasattr(decoder, "convert_tokens_to_ids"):
        vocab = decoder.get_vocab()
        for s in ("<|im_end|>", "<turn|>", "<end_of_turn>"):
            if s in vocab:
                values.add(decoder.convert_tokens_to_ids(s))
    return sorted(x for x in values if isinstance(x, int) and x >= 0)

def decoder_pad_id(decoder, stops):
    v = getattr(decoder, "pad_token_id", None)
    if isinstance(v, int):
        return v
    return stops[0] if stops else None

def decode_ids(decoder, ids):
    try:
        return decoder.decode(ids, skip_special_tokens=False)
    except TypeError:
        return decoder.decode(ids)

def clean_cache_for(model_id: str):
    hf_home = Path(os.environ.get("HF_HOME", ""))
    require(str(hf_home).startswith("/root/hf-cache"),
            "cache cleanup is allowed only when HF_HOME is under /root/hf-cache")
    repo = hf_home / "hub" / ("models--" + model_id.replace("/", "--"))
    if repo.exists():
        # Hub 1.32 stores weights in a cache-wide shared blob store. Removing
        # only the repo directory leaves those weights behind and fills disk.
        from huggingface_hub import scan_cache_dir
        cache = scan_cache_dir(hf_home / "hub")
        revisions = [rev.commit_hash for info in cache.repos
                     if info.repo_path.resolve() == repo.resolve()
                     for rev in info.revisions]
        require(revisions, f"no revisions found for cache cleanup: {repo}")
        cache.delete_revisions(*revisions).execute()
    # Xet's reconstructed chunk cache is expendable for this sequential run.
    xet = hf_home / "xet"
    if xet.exists():
        shutil.rmtree(xet)

def run_one(slug, entry, project, outroot, scorer, schema, inputs, cleanup):
    import torch
    from transformers import set_seed
    dest = outroot / slug
    require(not dest.exists(), f"{slug}: output already exists and is preserved: {dest}")
    dest.mkdir(parents=True)
    (dest / "results").mkdir()
    set_seed(42)

    cfg, revision = resolve_revision(entry["model"])
    prompt = build_prompt_adapter(entry, revision)

    prepared = {}
    max_prompt = 0
    for suite, rows in inputs.items():
        prepared[suite] = []
        for item in rows:
            ids, prompt_hash = prompt.encode(item["messages"])
            require(len(ids) + MAX_NEW <= MAX_TOTAL,
                    f"{slug}/{suite}/{item['case_id']}: {len(ids)} + {MAX_NEW} > {MAX_TOTAL}; no truncation")
            max_prompt = max(max_prompt, len(ids))
            prepared[suite].append((item, ids, prompt_hash))

    write_json(dest / "MODEL_LOCK.json", {
        "slug": slug,
        "model": entry["model"],
        "revision": revision,
        "family": entry["family"],
        "config_model_type": getattr(cfg, "model_type", None),
        "max_prompt_tokens": max_prompt,
        "max_new_tokens": MAX_NEW,
        "dtype": "bfloat16",
        "quantization": None,
        "decoding": "greedy_do_sample_false",
        "training_executed": False,
        "at_utc": now(),
    })

    print(f"\n=== LOAD {slug}: {entry['model']} ===", flush=True)
    torch.cuda.empty_cache()
    model, load_report = load_model(entry, revision)
    stops = eos_ids(model, prompt.decoder)
    pad = decoder_pad_id(prompt.decoder, stops)
    require(stops, f"{slug}: no EOS/turn stop IDs resolved")
    load_report.update({
        "stops": stops,
        "pad_token_id": pad,
        "gpu": torch.cuda.get_device_name(0),
        "vram_GiB": torch.cuda.get_device_properties(0).total_memory / 1024**3,
    })
    write_json(dest / "LOAD_REPORT.json", load_report)

    summary = {}
    for suite, expected_count in SUITES.items():
        rows_out = []
        result_path = dest / "results" / f"{suite}.jsonl"
        for i, (item, ids, prompt_hash) in enumerate(prepared[suite], 1):
            x = torch.tensor([ids], dtype=torch.long, device="cuda")
            mask = torch.ones_like(x)
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            t0 = time.perf_counter()
            with torch.inference_mode():
                generated = model.generate(
                    input_ids=x,
                    attention_mask=mask,
                    max_new_tokens=MAX_NEW,
                    do_sample=False,
                    eos_token_id=stops,
                    pad_token_id=pad,
                    use_cache=True,
                )
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0
            new = generated[0, len(ids):].tolist()
            end = next((j for j, token in enumerate(new) if token in stops), None)
            hit = end is None and len(new) >= MAX_NEW
            content = new[:end] if end is not None else new
            raw = decode_ids(prompt.decoder, content)
            score = scorer.score(item, raw, schema, hit)
            row = {
                "case_id": item["case_id"],
                "pair_id": item["case"].get("pair_id"),
                "suite": suite,
                "model": entry["model"],
                "revision": revision,
                "adapter": None,
                "messages_sha256": digest(item["messages"]),
                "rendered_prompt_sha256": prompt_hash,
                "prompt_tokens": len(ids),
                "generated_tokens": len(new),
                "generation_seconds": elapsed,
                "peak_allocated_GiB": torch.cuda.max_memory_allocated() / 1024**3,
                "raw_output": raw,
                "raw_with_terminal": decode_ids(prompt.decoder, new),
                "hit_generation_limit": hit,
                "score": score,
                "engineering_approved": False,
                "human_review_required": True,
            }
            append_jsonl(result_path, row)
            rows_out.append(row)
            print(f"{slug} {suite} {i:02d}/{expected_count} {item['case_id']} "
                  + ("PASS" if score["strict_contract_pass"] else "FAIL"), flush=True)
            del x, mask, generated
        summary[suite] = scorer.aggregate(rows_out)

    write_json(dest / "summary.json", {
        "version": VERSION,
        "slug": slug,
        "model": entry["model"],
        "revision": revision,
        "training_executed": False,
        "inference_executed": True,
        "dtype": "bfloat16",
        "quantization": None,
        "decoding": "greedy_do_sample_false",
        "max_new_tokens": MAX_NEW,
        "suites": summary,
        "load_report": load_report,
        "environment": environment(),
        "evaluation_status": "Existing inspected development/regression suites; not independent holdout",
    })

    print(f"=== UNLOAD {slug} ===", flush=True)
    del model, prompt
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()

    if cleanup:
        clean_cache_for(entry["model"])
        print(f"cache removed: {entry['model']}", flush=True)
    return summary

def archive_final_reports(outroot: Path):
    """Preserve previous aggregate reports before publishing a new summary."""
    paths = [outroot / name for name in ("tournament_summary.json", "RESULTS_KO.md")]
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    archive = outroot / "report_history" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    archive.mkdir(parents=True, exist_ok=False)
    for path in existing:
        shutil.move(str(path), str(archive / path.name))

def make_final(outroot: Path, historical, selected):
    models = dict(historical.get("models", {}))
    for slug in selected:
        p = outroot / slug / "summary.json"
        require(p.is_file(), f"missing summary: {p}")
        models[slug] = read_json(p)["suites"]

    result = {
        "version": VERSION,
        "at_utc": now(),
        "models": models,
        "new_models": selected,
        "training_executed": False,
        "inference_executed": True,
        "evaluation_status": "Development/regression comparison only",
        "selection_policy": [
            "wrongly_accepts_refuted_proposal",
            "action_correct",
            "reference_exact",
            "strict_contract_pass",
            "generation_seconds",
        ],
        "limits": [
            "The 84 cases have been inspected during development and are not an untouched holdout.",
            "Model-native chat templates/tokenizers differ.",
            "All new tournament candidates use BF16 and greedy decoding.",
            "No model is automatically promoted from this result.",
            "No engineering approval is created by the evaluator.",
        ],
    }
    write_json(outroot / "tournament_summary.json", result)

    lines = [
        "# DoriLab 9B~27B baseline tournament",
        "",
        "동일한 84개 개발·회귀 입력으로 학습 전 모델을 비교했다. 새 후보는 BF16, greedy decoding, adapter 없음 조건이다.",
        "",
        "| 모델 | NS10 action | NS10 strict | Before40 action | Before40 strict | 잘못된 제안 수용 | Contract20 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    order = list(models.keys())
    for key in order:
        m = models[key]
        wrong = m.get("before40", {}).get("wrongly_accepts_refuted_proposal", 0)
        lines.append(
            f"| {key} | "
            f"{m['ns10']['action_correct']}/{m['ns10']['cases']} | "
            f"{m['ns10']['strict_contract_pass']}/{m['ns10']['cases']} | "
            f"{m['before40']['action_correct']}/{m['before40']['cases']} | "
            f"{m['before40']['strict_contract_pass']}/{m['before40']['cases']} | "
            f"{wrong} | "
            f"{m['contract20']['strict_contract_pass']}/{m['contract20']['cases']} |"
        )
    lines += [
        "",
        "선택 시 strict 점수 하나만 보지 않고 잘못된 정상 판정, action, 근거 선택, reason 오류를 사례별로 확인한다.",
        "상위 후보만 별도 LoRA 실험으로 넘기며 이 결과 자체는 배포 승인이나 공학 승인으로 사용하지 않는다.",
    ]
    (outroot / "RESULTS_KO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def doctor(project: Path, outroot: Path):
    import torch
    from huggingface_hub import HfApi
    require(torch.cuda.is_available(), "CUDA unavailable")
    require(torch.cuda.is_bf16_supported(), "BF16 unavailable")
    require(str(torch.version.cuda).startswith("12.8"),
            f"expected the current RunPod cu128 runtime, got {torch.version.cuda}")
    api = HfApi()
    who = None
    try:
        who = api.whoami()
    except Exception as ex:
        raise RuntimeError("Hugging Face login required: run `hf auth login`") from ex

    checks = {}
    for slug, entry in REGISTRY.items():
        try:
            cfg, rev = resolve_revision(entry["model"])
            checks[slug] = {
                "model": entry["model"],
                "revision": rev,
                "model_type": getattr(cfg, "model_type", None),
                "access": "PASS",
            }
            print(f"PASS {slug}: {entry['model']} @ {rev[:10]}", flush=True)
        except Exception as ex:
            checks[slug] = {"model": entry["model"], "access": "FAIL", "error": str(ex)}
            print(f"FAIL {slug}: {ex}", flush=True)
    outroot.mkdir(parents=True, exist_ok=True)
    path = outroot / "DOCTOR.json"
    if path.exists():
        path.unlink()
    write_json(path, {
        "version": VERSION,
        "at_utc": now(),
        "environment": environment(),
        "hf_user": who.get("name") if isinstance(who, dict) else str(who),
        "models": checks,
    })
    require(all(x["access"] == "PASS" for x in checks.values()),
            f"One or more model access/config checks failed. See {path}")
    print("DOCTOR PASS:", path)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["doctor", "run", "summarize"])
    ap.add_argument("--project", type=Path,
                    default=Path("/workspace/dorilab/dorilab-gemma4-e4b"))
    ap.add_argument("--out", type=Path,
                    default=Path("/workspace/dorilab/tournament/baseline_v1"))
    ap.add_argument("--models", nargs="*", choices=list(REGISTRY), default=list(REGISTRY))
    ap.add_argument("--keep-cache", action="store_true",
                    help="Keep base model cache. Default removes each base model cache after its successful evaluation.")
    args = ap.parse_args()
    project = args.project.resolve()
    outroot = args.out.resolve()

    if args.command == "doctor":
        doctor(project, outroot)
        return 0

    schema, historical, inputs, frozen = validate_eval(project)
    scorer = import_scorer(project)
    outroot.mkdir(parents=True, exist_ok=True)
    manifest_path = outroot / "RUN_MANIFEST.json"
    if not manifest_path.exists():
        write_json(manifest_path, {
            "version": VERSION,
            "created_at_utc": now(),
            "project": str(project),
            "models": args.models,
            "max_total_tokens": MAX_TOTAL,
            "max_new_tokens": MAX_NEW,
            "dtype": "bfloat16",
            "quantization": None,
            "decoding": "greedy_do_sample_false",
            "frozen_inputs_sha256": frozen,
            "environment": environment(),
        })
    else:
        old = read_json(manifest_path)
        require(old["frozen_inputs_sha256"] == frozen, "frozen evaluation inputs changed")
        require(old["max_new_tokens"] == MAX_NEW, "generation contract changed")

    if args.command == "run":
        summaries = {}
        for slug in args.models:
            summary_path = outroot / slug / "summary.json"
            if summary_path.exists():
                print("SKIP VERIFIED OUTPUT EXISTS:", slug, flush=True)
                summaries[slug] = read_json(summary_path)["suites"]
                continue
            summaries[slug] = run_one(
                slug, REGISTRY[slug], project, outroot, scorer, schema, inputs,
                cleanup=not args.keep_cache,
            )
        archive_final_reports(outroot)
        make_final(outroot, historical, args.models)
        print("\nCOMPLETE:", outroot / "RESULTS_KO.md")
        return 0

    # summarize: preserve all previous aggregate reports.
    archive_final_reports(outroot)
    make_final(outroot, historical, args.models)
    print("SUMMARY:", outroot / "RESULTS_KO.md")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as ex:
        traceback.print_exc()
        print("\nSTOP:", ex, file=sys.stderr)
        raise SystemExit(1)
