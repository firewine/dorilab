from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICTS = {'SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT', 'UNREVIEWABLE'}
DECISIONS = {'ACCEPT_DRAFT', 'REVISE', 'REJECT', 'DEFER'}

def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def load_jsonl(path: Path) -> list[dict]:
    out=[]
    with path.open(encoding='utf-8-sig') as f:
        for n, line in enumerate(f, 1):
            if not line.strip(): continue
            x=json.loads(line)
            if not isinstance(x,dict): raise ValueError(f'{path}:{n}: JSON object required')
            out.append(x)
    return out

def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        for x in rows: f.write(json.dumps(x,ensure_ascii=False)+'\n')

def validate_case(c: dict) -> list[str]:
    errors=[]
    for k in ('case_id','pair_id','domain','role','question','proposal','provenance'):
        if not isinstance(c.get(k),str) or not c[k].strip(): errors.append(f'missing:{k}')
    if not isinstance(c.get('evidence'),list) or not c['evidence']: errors.append('missing:evidence')
    ev=c.get('evidence',[])
    ids=[e.get('id') for e in ev]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)): errors.append('invalid:evidence_ids')
    draft=c.get('reference_draft',{})
    if not isinstance(draft,dict) or not isinstance(draft.get('expected'),dict): errors.append('missing:reference_draft')
    else:
        if not set(draft['expected'].get('evidence_refs',[])) <= set(ids): errors.append('unavailable:reference_evidence')
    return errors

def readability_gaps(c: dict) -> list[str]:
    d=c.get('reference_draft',{})
    return [k for k in ('verdict','issue_ko','rationale_ko','next_step_ko') if not d.get(k)]

def public_case(c: dict) -> dict:
    # Reference labels/rationale/expected answers are never sent by this endpoint.
    return {k:v for k,v in c.items() if k not in {'reference_draft','legacy_record'}}

def model_input(c: dict) -> dict:
    # Input builder intentionally excludes human labels, reference explanations,
    # model outputs, pair IDs and A/B variant markers.
    return {k:c[k] for k in ('role','domain','question','proposal','scope','evidence') if k in c}

class Store:
    def __init__(self, work: Path):
        self.work=work.resolve();self.work.mkdir(parents=True,exist_ok=True)
        self.path=self.work/'factory.sqlite3'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS cases(
              id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT UNIQUE NOT NULL, case_id TEXT NOT NULL,
              content_hash TEXT NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS imports(
              source_path TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
              imported_at TEXT NOT NULL);
            ''')
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        return db
    def add_many(self, cases: list[dict], source_path: str, source_sha256: str) -> int:
        for c in cases:
            errors=validate_case(c)
            if errors: raise ValueError(c.get('case_id','?')+': '+', '.join(errors))
        added=0
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for c in cases:
                h=digest(c);old=db.execute('SELECT content_hash FROM cases WHERE id=?',(c['case_id'],)).fetchone()
                if old:
                    if old['content_hash']!=h: raise ValueError('ID content changed; use a new revision: '+c['case_id'])
                    continue
                db.execute('INSERT INTO cases VALUES(?,?,?)',(c['case_id'],h,json.dumps(c,ensure_ascii=False)));added+=1
            db.execute('INSERT OR IGNORE INTO imports VALUES(?,?,?)',(source_path,source_sha256,stamp()))
        return added
    def get(self, case_id: str) -> dict:
        with self.connect() as db:
            row=db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
        if row is None: raise KeyError(case_id)
        c=json.loads(row['payload']);c['content_hash']=row['content_hash'];return c
    def list_cases(self) -> list[dict]:
        with self.connect() as db:
            rows=db.execute('SELECT * FROM cases ORDER BY id').fetchall()
            reviewed={r['case_id'] for r in db.execute("SELECT DISTINCT case_id FROM events WHERE kind='REVIEW'")}
        return [{'case_id':r['id'],'pair_id':c['pair_id'],'domain':c['domain'],'title':c.get('title',c['question']),
                 'reviewed':r['id'] in reviewed,'gaps':readability_gaps(c),'content_hash':r['content_hash']}
                for r in rows for c in [json.loads(r['payload'])]]
    def record(self, case_id: str, kind: str, body: dict) -> dict:
        c=self.get(case_id)
        if body.get('content_hash')!=c['content_hash']: raise ValueError('화면의 사례 버전이 다릅니다. 새로고침하세요.')
        rid=body.get('request_id','')
        if not isinstance(rid,str) or not rid.strip(): raise ValueError('request_id required')
        if kind=='REVIEW':
            if body.get('verdict') not in VERDICTS: raise ValueError('공학 판정을 선택하세요.')
            if body.get('decision') not in DECISIONS: raise ValueError('검토 처리방식을 선택하세요.')
            if not str(body.get('reviewer','')).strip(): raise ValueError('검토자 이름이 필요합니다.')
            if not str(body.get('notes','')).strip(): raise ValueError('판단 이유를 한 문장 이상 기록하세요.')
            if body.get('decision')=='ACCEPT_DRAFT':
                if not body.get('reference_seen'): raise ValueError('기준 초안을 먼저 확인하세요.')
                if not body.get('source_checked'): raise ValueError('원문 근거 확인 여부를 기록하세요. 미확인은 보류로 저장할 수 있습니다.')
                if c.get('demo_only'): raise ValueError('시연 사례는 학습 정답으로 승인하지 않습니다. 보류 또는 수정요청을 선택하세요.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT payload,kind,case_id FROM events WHERE request_id=?',(rid,)).fetchone()
            serialized=json.dumps(body,ensure_ascii=False,sort_keys=True)
            if old:
                if old['payload']!=serialized or old['kind']!=kind or old['case_id']!=case_id:
                    raise ValueError('request_id conflict')
                return {'saved':True,'duplicate':True}
            db.execute('INSERT INTO events(request_id,case_id,content_hash,kind,payload,created_at) VALUES(?,?,?,?,?,?)',
                       (rid,case_id,c['content_hash'],kind,serialized,stamp()))
        return {'saved':True,'duplicate':False}
    def reviews(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r)|{'payload':json.loads(r['payload'])} for r in db.execute("SELECT * FROM events WHERE kind='REVIEW' ORDER BY event_id")]

def legacy_candidates(root: Path) -> tuple[list[dict],Path]:
    root=root.resolve();path=root/'data/physics_candidates40_v02.jsonl'
    if not path.is_file(): raise FileNotFoundError('SourceCurriculum_v02 후보 파일을 찾지 못했습니다: '+str(path))
    rows=load_jsonl(path);extra=root/'data/additional_candidates.jsonl'
    if extra.exists(): rows+=load_jsonl(extra)
    normalized=[]
    for c in rows:
        # Import only disclosed training candidates. Never read separate eval files.
        if c.get('planned_split') not in ('TRAIN_CANDIDATE','TRAIN_RESERVED'): continue
        p=c['packet'];refs=p.get('reference_context',[]);obs=p['case_packet'].get('evidence',[])
        evidence=[{'id':r['reference_id'],'type':'등록된 문헌 요약','text':r['text'],
                   'source_id':r.get('source_id'),'pdf_pages':r.get('pdf_pages_1based',[]),
                   'section':r.get('section'),'printed_pages':r.get('printed_pages',[])} for r in refs]
        evidence += [{'id':e['evidence_id'],'type':'가상 사례의 관측 조건','text':e['text']} for e in obs]
        normalized.append({'case_id':c['case_id'],'pair_id':c['pair_id'],'variant':c.get('variant'),
          'title':c['case_id']+' · '+c['domain'],'domain':c['domain'],'role':c['role'],
          'question':p['review_question'],'proposal':p['case_packet']['proposal'],
          'scope':c.get('scope_of_no_action','해당 검토 질문에 한정'), 'evidence':evidence,
          'pair_changed_paths':c.get('pair_changed_paths',[]),
          'provenance':'기존 SourceCurriculum_v02의 사례·해설을 내용 변경 없이 가져옴. v08 모델 실행결과는 미연결.',
          'reference_draft':{'expected':c['expected'],'verdict':None,'issue_ko':None,
              'rationale_ko':c.get('rationale_ko'),'next_step_ko':None,'review_status':'PENDING',
              'origin':'기존 학습 후보의 기준 초안. 모델이 생성한 설명이 아님'},
          'model_result':None, 'demo_only':False,'legacy_record':c})
    return normalized,path
