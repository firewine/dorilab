from __future__ import annotations
import json, hashlib, csv, re
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]

def load_jsonl(path: str | Path) -> list[dict]:
    path=Path(path); rows=[]
    with path.open(encoding='utf-8-sig') as f:
        for n,line in enumerate(f,1):
            if not line.strip():continue
            try:x=json.loads(line)
            except json.JSONDecodeError as e:raise ValueError(f'{path}:{n}: {e}') from e
            if not isinstance(x,dict):raise ValueError(f'{path}:{n}: object required')
            rows.append(x)
    return rows

def sha256(path: str | Path) -> str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def write_json(path: str | Path, obj, exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x' if exclusive else 'w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def sources():
    return {x['source_id']:x for x in json.loads((ROOT/'sources/source_manifest_v02.json').read_text())['sources']}

def cases():
    rows=load_jsonl(ROOT/'data/physics_candidates40_v02.jsonl')
    extra=ROOT/'data/additional_candidates.jsonl'
    if extra.exists():rows+=load_jsonl(extra)
    return rows

def packet_ids(case):
    p=case['packet'];return {x['reference_id'] for x in p['reference_context']}|{x['evidence_id'] for x in p['case_packet']['evidence']}

def strict_parse(raw):
    try:
        x=json.loads(raw.strip())
        return x if isinstance(x,dict) else None
    except (ValueError,TypeError):return None

def validate_answer(answer,case):
    import jsonschema
    schema=json.loads((ROOT/'data/action_schema_v02.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(answer)
    if answer['claim_id']!=case['packet']['claim_id']:raise ValueError('claim_id mismatch')
    if not set(answer['evidence_refs'])<=packet_ids(case):raise ValueError('unprovided evidence reference')
    if not set(answer.get('requested_evidence',[]))<=set(case['packet']['allowed_request_ids']):raise ValueError('unprovided request id')

def answer_matches(expected,actual):
    if not isinstance(actual,dict):return False

    def canon(x):
        return json.dumps(
            x,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",",":")
        )

    for k,v in expected.items():
        actual_v=actual.get(k)

        if k=="evidence_refs":
            if not isinstance(actual_v,list):return False
            actual_items=[canon(x) for x in actual_v]
            if not all(canon(x) in actual_items for x in v):return False

        elif isinstance(v,list):
            if not isinstance(actual_v,list):return False
            if sorted(canon(x) for x in v)!=sorted(canon(x) for x in actual_v):
                return False

        elif actual_v!=v:
            return False

    return True

def semantic_state_hash(case):
    # Exact packet only, metadata IDs/split/labels not used for equivalence.
    payload={'role':case['role'],'packet':case['packet']}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def mask_completion(prompt_ids,answer_ids,end_id,max_length):
    if not prompt_ids or not answer_ids:raise ValueError('empty prompt/answer tokens')
    completion=list(answer_ids)+[int(end_id)]
    ids=list(prompt_ids)+completion
    if len(ids)>max_length:
        raise ValueError(f'{len(ids)} tokens > max_length {max_length}; shorten context or raise the limit; no silent truncation')
    return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':[-100]*len(prompt_ids)+completion}

def collate_rows(rows,pad_id):
    import torch
    longest=max(len(x['input_ids']) for x in rows)
    data={k:[] for k in ['input_ids','attention_mask','labels']}
    for x in rows:
        n=longest-len(x['input_ids'])
        data['input_ids'].append(x['input_ids']+[pad_id]*n)
        data['attention_mask'].append(x['attention_mask']+[0]*n)
        data['labels'].append(x['labels']+[-100]*n)
    return {k:torch.tensor(v,dtype=torch.long) for k,v in data.items()}
