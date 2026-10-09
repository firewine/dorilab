"""Serving bridge to the sealed RC3 native tokenization/checkpoint code.
Loader and generation kwargs match experiment_rc3_resume_01/infer_once.py.
No evaluation runner main(), training entry, or gold files are executed/read.
"""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/workspace/dorilab')
HERE = ROOT / 'inference'
RC3 = ROOT / 'results/v15_release_progress/cpu_rc3'
RUN = ROOT / 'results/v15_release_progress/experiment_rc3_resume_01'
BASE = Path('/root/models/qwen38-27b')
ADAPTER = ROOT / 'models/qwen38-27b/current/adapter'
MODEL_ID = 'Qwen/Qwen3.8-27B'
REVISION = '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
COMMIT = '002e1edf5b5198488297f401dd853056b6521d02'
WEIGHTS_SHA = 'd90dee59f00f7c987c1b61ae334f928464bfb412ddb26110d692b92b9a46a689'
CONFIG_SHA = 'd037e965c05ec56ed6069581635ada7f704a6c6331b56831075f127f52f61628'
sys.dont_write_bytecode = True
sys.path.insert(0, str(RC3))
from tokenization import processor, inference
from train_once import verify_checkpoint
from common import digest, sha


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def contracts():
    data = json.loads((HERE / 'contracts/system_allowlist.json').read_text())
    assert data['source_sha256'] == '483c95abbd8324919774bd3a21cf747601d14f04aae6f0c9cfa227d5317b2485'
    result = {}
    for row in data['contracts']:
        assert hashlib.sha256(row['system'].encode()).hexdigest() == row['system_sha256'] == row['id']
        result[row['id']] = row
    # Bind exact systems to the original, input-only sealed evaluation artifact.
    assert sha(RUN / 'EVALUATION_INPUTS.jsonl') == data['source_sha256']
    original = {hashlib.sha256(json.loads(line)['messages'][0]['content'].encode()).hexdigest()
                for line in (RUN / 'EVALUATION_INPUTS.jsonl').read_text().splitlines()}
    assert set(result) == original
    # Service-only contracts are immutable overlays. The sealed evaluation allowlist above remains
    # byte-for-byte bound to its original input artifact and is never rewritten.
    overlay_path = HERE / 'contracts/service_contracts.json'
    if overlay_path.exists():
        overlay = json.loads(overlay_path.read_text())
        assert overlay['schema_version'] == 1
        routes = {row['route'] for row in result.values()}
        for row in overlay['contracts']:
            required = {'id', 'route', 'system_sha256', 'parent_id', 'change', 'system'}
            assert set(row) == required
            assert row['parent_id'] in result
            assert row['id'] not in result and row['route'] not in routes
            assert hashlib.sha256(row['system'].encode()).hexdigest() == row['system_sha256'] == row['id']
            result[row['id']] = row
            routes.add(row['route'])
    return result


class ModelRuntime:
    def __init__(self, boot_id, directory):
        self.boot_id, self.directory = boot_id, Path(directory)
        self.allowlist = contracts()
        self.receipt = None

    def load(self):
        import torch
        from transformers import Qwen3_5ForConditionalGeneration
        from peft import PeftModel
        assert sys.executable == '/root/venvs/dorilab-tournament/bin/python'
        direct = json.loads(metadata.distribution('transformers').read_text('direct_url.json'))
        assert direct['vcs_info']['commit_id'] == COMMIT
        assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        for path, expected in json.loads((HERE / 'artifacts/source_preservation.json').read_text()).items():
            assert sha(path) == expected, 'sealed source changed'
        resolved = ADAPTER.resolve(strict=True)
        assert sha(resolved / 'adapter_model.safetensors') == WEIGHTS_SHA
        assert sha(resolved / 'adapter_config.json') == CONFIG_SHA
        print('Verifying all 18 base shards against existing per-shard receipts', flush=True)
        shards = verify_checkpoint(BASE)
        expected = json.loads((RUN / 'CHECKPOINT_HASHES.json').read_text())
        assert expected['model'] == MODEL_ID and expected['revision'] == REVISION
        assert shards == expected['shards']
        assert set(p.name for p in BASE.glob('model-*.safetensors')) == set(shards)
        self.proc, env = processor()
        print('Loading Qwen3_5ForConditionalGeneration BF16/SDPA and RC3 PEFT', flush=True)
        self.model = Qwen3_5ForConditionalGeneration.from_pretrained(
            BASE, local_files_only=True, trust_remote_code=False,
            dtype=torch.bfloat16, attn_implementation='sdpa', device_map={'': 0})
        base_class = type(self.model).__name__
        self.model = PeftModel.from_pretrained(self.model, resolved, is_trainable=False)
        self.model.eval()
        self.model.requires_grad_(False)
        assert not any(p.requires_grad for p in self.model.parameters())
        assert all(p.device.type == 'cuda' for p in self.model.parameters())
        assert self.model.active_adapters == ['default']
        self.generation = dict(do_sample=False, use_cache=True,
            pad_token_id=self.proc.tokenizer.pad_token_id,
            eos_token_id=self.proc.tokenizer.convert_tokens_to_ids('<|im_end|>'))
        assert self.generation['eos_token_id'] == 248046
        assert self.generation['pad_token_id'] == 248044
        release_receipt = dict(model=MODEL_ID, revision=REVISION,
            base_class=base_class, peft_class=type(self.model).__name__, adapter_realpath=str(resolved),
            adapter_weights_sha256=WEIGHTS_SHA, adapter_config_sha256=CONFIG_SHA,
            checkpoint_receipt_sha256=sha(RUN / 'CHECKPOINT_HASHES.json'),
            base_shards_sha256=shards, base_verification='full SHA256 and size against prior receipts',
            runtime=env, generation=self.generation, max_total_tokens=4096, max_new_tokens=384,
            enable_thinking=False, dtype='bfloat16', attention='sdpa', model_eval=True,
            trainable_parameters=0, active_adapters=self.model.active_adapters,
            lora_parameter_count=sum(p.numel() for n, p in self.model.named_parameters() if 'lora_' in n),
            native_generation_config=self.model.generation_config.to_dict())
        # The model release identity must survive a process restart. boot_id is recorded separately
        # in every run/result receipt and must not alter the immutable release digest.
        self.receipt_id = digest(release_receipt)
        self.receipt = dict(boot_id=self.boot_id, **release_receipt)
        atomic_json(self.directory / 'model_receipt.json', self.receipt)
        torch.cuda.reset_peak_memory_stats()
        warm = self.prepare('0703fba59425b087a4061a1fc9a370f2e6d7a192a2b2ce4b1ad2b1377f89a00b',
            '{"task":"CHECK_AXIS_DURATION","required_s":17,"actual_by_axis":{"synthetic_axis":19}}', 8)
        output = self.generate(warm, 8)
        atomic_json(self.directory / 'warmup.json', dict(purpose='technical warmup only', **output))
        atomic_json(self.directory / 'ready.json', dict(boot_id=self.boot_id, pid=os.getpid(),
            model_receipt_id=self.receipt_id, memory=self.memory(), ready=True))
        print('READY: adapter verified, GPU resident, technical warmup complete', flush=True)

    def prepare(self, contract_id, user, max_new_tokens):
        if any(marker in user for marker in ('<|im_start|>', '<|im_end|>', '<|endoftext|>')):
            raise ValueError('reserved native chat delimiter')
        def strict_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError('duplicate JSON key')
                result[key] = value
            return result
        def invalid_constant(value): raise ValueError('non-finite JSON number')
        value = json.loads(user.split('STATE:', 1)[-1], object_pairs_hook=strict_object,
                           parse_constant=invalid_constant)
        if not isinstance(value, dict): raise ValueError('native user input must contain a JSON object')
        forbidden = {'gold', 'expected', 'rationale', 'rationale_ko', 'reference_answer',
                     'sufficient_sets', 'acceptable_reason_codes', 'reference_requirement',
                     'training_eligible', 'supporting_fact_ids', 'supporting_observation_ids'}
        def clean(value):
            if isinstance(value, dict):
                return not (set(value) & forbidden) and all(clean(v) for v in value.values())
            if isinstance(value, list): return all(clean(v) for v in value)
            if isinstance(value, float):
                import math
                return math.isfinite(value)
            return True
        if not clean(value): raise ValueError('answer metadata or non-finite value is forbidden')
        messages = [{'role': 'system', 'content': self.allowlist[contract_id]['system']},
                    {'role': 'user', 'content': user}]
        rendered, ids = inference(self.proc, messages)
        if len(ids) + max_new_tokens > 4096:
            raise ValueError('input tokens plus reserved output exceed 4096; no truncation')
        return dict(messages=messages, ids=ids, input_sha256=digest(messages),
                    prompt_token_ids_sha256=digest(ids), rendered_sha256=digest(rendered))

    def generate(self, prepared, max_new_tokens):
        import torch
        started = time.monotonic()
        ids = prepared['ids']
        # Request-local tensors and cache: no past_key_values or conversation state accepted/stored.
        with torch.inference_mode():
            tensor = torch.tensor([ids], dtype=torch.long, device='cuda')
            result = self.model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                max_new_tokens=max_new_tokens, **self.generation)
            outids = result[0, len(ids):].tolist()
        raw = self.proc.tokenizer.decode(outids, skip_special_tokens=False)
        text = self.proc.tokenizer.decode(outids, skip_special_tokens=True)
        ended = bool(outids and outids[-1] == self.generation['eos_token_id'])
        del tensor, result
        return dict(raw_text=raw, text=text, generated_token_ids=outids,
            input_tokens=len(ids), generated_tokens=len(outids), reserved_output_tokens=max_new_tokens,
            finish_reason='eos' if ended else 'length' if len(outids) == max_new_tokens else 'other',
            ended_with_native_terminator=ended, elapsed_seconds=time.monotonic()-started,
            input_sha256=prepared['input_sha256'], prompt_token_ids_sha256=prepared['prompt_token_ids_sha256'],
            rendered_sha256=prepared['rendered_sha256'], output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            model_receipt_id=self.receipt_id, boot_id=self.boot_id, output_repaired=False)

    def memory(self):
        import torch
        free, total = torch.cuda.mem_get_info()
        return dict(allocated=torch.cuda.memory_allocated(), reserved=torch.cuda.memory_reserved(),
                    peak_allocated=torch.cuda.max_memory_allocated(), device_free=free, device_total=total)
