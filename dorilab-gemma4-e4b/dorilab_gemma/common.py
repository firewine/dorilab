from __future__ import annotations
import hashlib, json, os, platform, re
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'dorilab-gemma4-e4b-1.0.0'
MODEL_ID = 'google/gemma-4-E4B-it'
SETTINGS = dict(model=MODEL_ID, rank=16, alpha=32, dropout=0.05,
                learning_rate=5e-5, epochs=2, seed=42, batch_size=1,
                gradient_accumulation_steps=4, max_length=2048,
                max_new_tokens=384, quantization='bnb-nf4-double',
                compute_dtype='bfloat16', enable_thinking=False,
                loss='response_only_selected_logits', attention='sdpa')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def strict_json(text):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'Duplicate JSON key: ' + str(k))
            out[k] = v
        return out
    def bad(x):
        raise ValueError('Non-finite JSON: ' + x)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)

def read_json(path):
    return strict_json(Path(path).read_text(encoding='utf-8-sig'))

def read_jsonl(path):
    rows=[]
    for i, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip(): continue
        try: row = strict_json(line)
        except Exception as ex: raise ValueError(f'{path}:{i}: {ex}') from ex
        require(isinstance(row, dict), f'{path}:{i}: object required')
        rows.append(row)
    require(rows, f'Empty JSONL: {path}')
    return rows

def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def now(): return datetime.now(timezone.utc).isoformat()

def write_json(path, value):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')

def write_jsonl(path, rows):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')

def inside(root, name):
    root=Path(root).resolve(); p=(root/Path(name)).resolve()
    require(p.is_relative_to(root), f'Path escapes root: {name}')
    return p

def index(rows, key='case_id'):
    out={}
    for row in rows:
        value=row.get(key)
        require(isinstance(value,str) and value and value not in out, f'Missing/duplicate {key}: {value}')
        out[value]=row
    return out

def messages_ok(messages, training=False):
    require(isinstance(messages,list), 'messages must be a list')
    roles = ['system','user','assistant'] if training else ['system','user']
    require([m.get('role') for m in messages]==roles, f'This pilot requires {roles}')
    for m in messages:
        require(isinstance(m.get('content'),str) and m['content'].strip(), 'Nonempty text content required')
        for token in ('<|im_start|>','<|im_end|>','<|think|>','<|turn>','<turn|>'):
            require(token not in m['content'], f'Preformatted/chat control token in data: {token}')
    if training:
        require(isinstance(strict_json(messages[-1]['content']),dict), 'Assistant answer must be one JSON object')

def environment():
    from importlib.metadata import version, PackageNotFoundError
    versions={}
    for name in ('torch','transformers','peft','bitsandbytes','accelerate','jsonschema','huggingface-hub'):
        try: versions[name]=version(name)
        except PackageNotFoundError: versions[name]=None
    return {'python':platform.python_version(),'platform':platform.platform(),'packages':versions}
