"""Local dataset preparation. No SSH credentials, GPU calls, training, or model promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import actor, csrf
from .contracts import digest
from .db import connection
from .rag import CHUNKER_VERSION, PARSER_VERSION
from .storage import resolved_path, write_bytes

BASELINE_ROOT = Path('/app/packages/contracts/development')
PROFILE_PATH = Path('/app/packages/contracts/model_profiles/rc3.json')
# Local authoring and human review only. Dataset exports remain an unreleased draft.
EXAMPLES_ENABLED = True
EXAMPLE_REVIEW_ENABLED = True
PREPARATION_ENABLED = False


class ExampleCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=160)
    family_key: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
    split: Literal['TRAIN', 'EVALUATION']
    origin: Literal['HUMAN_AUTHORED', 'SYNTHETIC_HUMAN_AUTHORED']
    source_chunk_id: UUID
    prompt: str = Field(min_length=1, max_length=8192)
    completion: str = Field(min_length=1, max_length=8192)

    @field_validator('title', 'prompt', 'completion')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank values are not allowed')
        return value


class ExampleDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    decision: Literal['APPROVED', 'REJECTED']
    note: str = Field(min_length=1, max_length=2000)
    data_use_confirmed: bool = False

    @field_validator('note')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('review note must not be blank')
        return value


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
    split: Literal['TRAIN', 'EVALUATION']
    example_ids: list[UUID] = Field(min_length=1, max_length=100)


def _key(value):
    if not value or not 8 <= len(value) <= 160 or any(c.isspace() for c in value):
        raise HTTPException(422, 'Idempotency-Key must be 8..160 non-whitespace characters')
    return value


def _lock(cur, project_id):
    # Serialize family partition checks and dataset version allocation within a project.
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (f'learning:{project_id}',))


def _source(cur, chunk_id):
    cur.execute(
        """SELECT c.id,c.project_id,c.artifact_id,c.text_sha256,c.locator,c.chunk_text,
                  c.version AS chunk_version,a.sha256,a.edition,a.filename,a.object_key,
                  a.rights_status,a.usage_purpose,a.kind,r.status AS parser_status,
                  r.receipt_sha256,r.source_sha256,r.parser_version,r.chunker_version
           FROM document_chunks c JOIN artifact_versions a ON a.id=c.artifact_id
           JOIN document_parser_runs r ON r.id=c.parser_run_id WHERE c.id=%s""", (chunk_id,))
    return cur.fetchone()


def _source_snapshot(source):
    return {key: str(source[key]) if key in {'id', 'artifact_id'} else source[key] for key in (
        'id', 'artifact_id', 'sha256', 'edition', 'filename', 'rights_status', 'usage_purpose',
        'text_sha256', 'locator', 'chunk_version', 'receipt_sha256', 'parser_version', 'chunker_version')}


def _source_reasons(source, snapshot=None):
    if not source:
        return ['SOURCE_UNAVAILABLE']
    reasons = []
    if source['kind'] != 'SOURCE' or source['parser_status'] != 'COMPLETED':
        reasons.append('SOURCE_PARSE_NOT_COMPLETED')
    if source['parser_version'] != PARSER_VERSION or source['chunker_version'] != CHUNKER_VERSION:
        reasons.append('SOURCE_PARSER_VERSION_CHANGED')
    if source['source_sha256'] != source['sha256']:
        reasons.append('SOURCE_PARSE_STALE')
    if snapshot and _source_snapshot(source) != snapshot:
        reasons.append('SOURCE_METADATA_CHANGED')
    if hashlib.sha256(source['chunk_text'].encode()).hexdigest() != source['text_sha256']:
        reasons.append('SOURCE_TEXT_CHANGED')
    try:
        actual = hashlib.sha256(resolved_path(source['object_key']).read_bytes()).hexdigest()
        if actual != source['sha256']:
            reasons.append('SOURCE_BYTES_CHANGED')
    except (OSError, ValueError):
        reasons.append('SOURCE_BYTES_UNAVAILABLE')
    return reasons


def _example_projection(cur, example):
    reasons = _source_reasons(_source(cur, example['source_chunk_id']), example['source_snapshot'])
    return {**example, 'freshness': 'STALE' if reasons else 'CURRENT', 'source_issues': reasons,
            'approval_scope': 'LOCAL_DATASET_PREPARATION_ONLY', 'authoring_scope': 'LOCAL_DRAFT_ONLY',
            'semantic_correctness': 'HUMAN_REVIEW_ONLY' if example['status'] == 'APPROVED' else 'NOT_VERIFIED'}


def _dataset_projection(cur, dataset):
    reasons = []
    for item in dataset['manifest']['examples']:
        issues = _source_reasons(_source(cur, UUID(item['source_chunk_id'])), item['source_snapshot'])
        reasons.extend(issues)
    cur.execute('SELECT object_key,sha256 FROM artifact_versions WHERE id=%s', (dataset['artifact_id'],))
    export = cur.fetchone()
    try:
        if (not export or hashlib.sha256(resolved_path(export['object_key']).read_bytes()).hexdigest()
                != dataset['manifest']['jsonl_sha256'] or export['sha256'] != dataset['manifest']['jsonl_sha256']):
            reasons.append('DATASET_BYTES_CHANGED')
    except (OSError, ValueError):
        reasons.append('DATASET_BYTES_UNAVAILABLE')
    if digest(dataset['manifest']) != dataset['manifest_sha256']:
        reasons.append('DATASET_MANIFEST_CHANGED')
    return {**dataset, 'freshness': 'STALE' if reasons else 'CURRENT', 'source_issues': sorted(set(reasons)),
            'download_url': f"/api/v1/artifacts/{dataset['artifact_id']}/download",
            'manifest_url': f"/api/v1/learning/datasets/{dataset['id']}/manifest"}


def create_router(membership, audit):
    router = APIRouter(tags=['Local development and learning preparation'])

    def require_preparation():
        if not PREPARATION_ENABLED:
            raise HTTPException(501, 'LEARNING_PREPARATION_NOT_RELEASED: next development step')

    def require_examples():
        if not (EXAMPLES_ENABLED or PREPARATION_ENABLED):
            raise HTTPException(501, 'EXAMPLE_AUTHORING_NOT_RELEASED')

    def require_example_review():
        if not (EXAMPLE_REVIEW_ENABLED or PREPARATION_ENABLED):
            raise HTTPException(501, 'EXAMPLE_REVIEW_NOT_RELEASED')

    @router.get('/api/v1/projects/{project_id}/development')
    def development(project_id: UUID, user_id: str = Depends(actor)):
        with connection() as conn, conn.cursor() as cur:
            member = membership(cur, project_id, user_id)
        catalog = json.loads((BASELINE_ROOT / 'catalog.json').read_text())
        evidence = []
        for entry in catalog['evidence']:
            path = BASELINE_ROOT / 'evidence' / entry['filename']
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            evidence.append({**entry, 'source_verified': actual == entry['sha256'],
                             'download_url': f"/api/v1/projects/{project_id}/development/evidence/{entry['id']}"})
        profile = json.loads(PROFILE_PATH.read_text())
        # deployment_status in the historical profile is not current GPU readiness.
        return {**catalog, 'evidence': evidence, 'role': member['role'], 'project_id': project_id,
                'released_sections': ['goals','documents','learning'] if (EXAMPLES_ENABLED or PREPARATION_ENABLED) else ['goals','documents'],
                'model_baseline': {k: profile[k] for k in ('profile_id','base_model','base_revision','adapter_model_sha256')},
                'model_baseline_scope': 'PINNED_PROFILE_NOT_CURRENT_READINESS'}

    @router.get('/api/v1/projects/{project_id}/development/evidence/{evidence_id}')
    def development_evidence(project_id: UUID, evidence_id: str, user_id: str = Depends(actor)):
        with connection() as conn, conn.cursor() as cur:
            membership(cur, project_id, user_id)
        catalog = json.loads((BASELINE_ROOT / 'catalog.json').read_text())
        entry = next((e for e in catalog['evidence'] if e['id'] == evidence_id), None)
        if not entry:
            raise HTTPException(404, 'development evidence not found')
        path = BASELINE_ROOT / 'evidence' / entry['filename']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise HTTPException(409, 'DEVELOPMENT_EVIDENCE_HASH_MISMATCH')
        return FileResponse(path, media_type='text/markdown', filename=entry['filename'])

    @router.get('/api/v1/projects/{project_id}/learning')
    def learning_overview(project_id: UUID, user_id: str = Depends(actor)):
        with connection() as conn, conn.cursor() as cur:
            member = membership(cur, project_id, user_id)
            cur.execute(
                """SELECT a.id,a.filename,a.content_type,a.sha256,a.byte_size,a.edition,a.rights_status,
                          a.adopted,a.applicability_status,a.usage_purpose,a.created_at,
                          r.id AS parser_run_id,r.status AS parser_status,r.chunk_count,r.page_count,
                          r.error_code,r.error_detail,r.issues,r.receipt_sha256,
                          r.parser_name,r.parser_version,r.chunker_version,r.finished_at
                   FROM artifact_versions a LEFT JOIN LATERAL (
                     SELECT * FROM document_parser_runs WHERE artifact_id=a.id ORDER BY started_at DESC LIMIT 1
                   ) r ON true WHERE a.project_id=%s AND a.kind='SOURCE' ORDER BY a.created_at DESC""", (project_id,))
            documents = cur.fetchall()
            examples, datasets = [], []
            if EXAMPLES_ENABLED or PREPARATION_ENABLED:
                cur.execute('SELECT * FROM learning_examples WHERE project_id=%s ORDER BY created_at DESC', (project_id,))
                examples = [_example_projection(cur, e) for e in cur.fetchall()]
            if PREPARATION_ENABLED:
                cur.execute('SELECT * FROM learning_datasets WHERE project_id=%s ORDER BY created_at DESC', (project_id,))
                datasets = [_dataset_projection(cur, d) for d in cur.fetchall()]
        blockers = ['TRAINING_RECIPE_UNVERIFIED', 'REMOTE_TRAINING_RUNNER_NOT_IMPLEMENTED']
        for split in ('TRAIN', 'EVALUATION'):
            if not any(d['split'] == split and d['freshness'] == 'CURRENT' for d in datasets):
                blockers.append(f'{split}_DATASET_NOT_READY')
        return {'project_id': project_id, 'role': member['role'], 'preparation_enabled': PREPARATION_ENABLED,
                'example_authoring_enabled': EXAMPLES_ENABLED or PREPARATION_ENABLED,
                'example_review_enabled': EXAMPLE_REVIEW_ENABLED or PREPARATION_ENABLED,
                'documents': documents, 'examples': examples,
                'datasets': datasets, 'training': {'state': 'BLOCKED', 'blockers': blockers,
                'remote_checked': False, 'job_id': None, 'remote_execution_enabled': False,
                'scope': 'LOCAL_PREPARATION_ONLY', 'format': 'PROMPT_COMPLETION_JSONL_PREPARATION_V1',
                'recipe_mapping_verified': False}}

    @router.post('/api/v1/projects/{project_id}/learning/examples', status_code=201, dependencies=[Depends(csrf)])
    def create_example(project_id: UUID, body: ExampleCreate,
                       idempotency_key: str | None = Header(default=None), user_id: str = Depends(actor)):
        key = _key(idempotency_key)
        require_examples()
        payload = body.model_dump(mode='json')
        request_hash = digest(payload)
        with connection() as conn, conn.cursor() as cur:
            membership(cur, project_id, user_id, {'engineer','reviewer','approver'})
            _lock(cur, project_id)
            cur.execute('SELECT * FROM learning_examples WHERE project_id=%s AND idempotency_key=%s', (project_id,key))
            previous = cur.fetchone()
            if previous:
                if previous['request_sha256'] != request_hash:
                    raise HTTPException(409, 'IDEMPOTENCY_KEY_CONFLICT')
                return _example_projection(cur, previous)
            source = _source(cur, body.source_chunk_id)
            if not source or source['project_id'] != project_id:
                raise HTTPException(404, 'source chunk not found')
            issues = _source_reasons(source)
            if issues:
                raise HTTPException(409, 'SOURCE_NOT_CURRENT: ' + ','.join(issues))
            if ((body.split == 'TRAIN' and source['usage_purpose'] == 'EVALUATION_GOLD') or
                    (body.split == 'EVALUATION' and source['usage_purpose'] == 'TRAINING')):
                raise HTTPException(409, 'SOURCE_USAGE_SPLIT_CONFLICT')
            content_hash = digest({'prompt':body.prompt, 'completion':body.completion})
            input_hash = digest({'prompt':body.prompt})
            cur.execute(
                """SELECT family_key,split,source_snapshot FROM learning_examples
                   WHERE project_id=%s AND (family_key=%s OR source_snapshot->>'sha256'=%s
                        OR input_sha256=%s OR source_snapshot->>'artifact_id'=%s)""",
                (project_id,body.family_key,source['sha256'],input_hash,str(source['artifact_id'])))
            for old in cur.fetchall():
                if old['split'] != body.split:
                    raise HTTPException(409, 'TRAIN_EVALUATION_OVERLAP')
                if old['source_snapshot']['artifact_id'] == str(source['artifact_id']) and old['family_key'] != body.family_key:
                    raise HTTPException(409, 'SOURCE_FAMILY_CONFLICT')
            example_id = uuid4()
            cur.execute(
                """INSERT INTO learning_examples(id,project_id,title,family_key,split,origin,source_chunk_id,
                   source_snapshot,prompt,completion,content_sha256,input_sha256,created_by,idempotency_key,request_sha256)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (example_id,project_id,body.title,body.family_key,body.split,body.origin,body.source_chunk_id,
                 json.dumps(_source_snapshot(source)),body.prompt,body.completion,content_hash,input_hash,user_id,key,request_hash))
            example = cur.fetchone()
            audit(cur,project_id,user_id,'PREPARE_LEARNING_EXAMPLE','learning_example',str(example_id),payload)
            return _example_projection(cur, example)

    @router.post('/api/v1/learning/examples/{example_id}/decisions', dependencies=[Depends(csrf)])
    def decide_example(example_id: UUID, body: ExampleDecision, user_id: str = Depends(actor)):
        require_example_review()
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM learning_examples WHERE id=%s FOR UPDATE', (example_id,))
            example = cur.fetchone()
            if not example:
                raise HTTPException(404, 'learning example not found')
            membership(cur,example['project_id'],user_id,{'reviewer','approver'})
            if example['status'] != 'DRAFT' or example['version'] != body.expected_version:
                raise HTTPException(409, 'EXAMPLE_VERSION_OR_STATUS_CONFLICT')
            source = _source(cur, example['source_chunk_id'])
            if body.decision == 'APPROVED':
                issues = _source_reasons(source, example['source_snapshot'])
                if issues:
                    raise HTTPException(409, 'SOURCE_NOT_CURRENT: ' + ','.join(issues))
                if (not body.data_use_confirmed or source['rights_status'] not in {'PUBLIC','GRANTED'}
                        or not (source['edition'] or '').strip()):
                    raise HTTPException(409, 'DATA_USE_OR_EDITION_UNCONFIRMED')
            cur.execute(
                """UPDATE learning_examples SET status=%s,version=version+1,reviewed_by=%s,reviewed_at=now(),
                   review_note=%s,data_use_confirmed=%s WHERE id=%s RETURNING *""",
                (body.decision,user_id,body.note,body.data_use_confirmed,example_id))
            updated = cur.fetchone()
            audit(cur,example['project_id'],user_id,'REVIEW_LEARNING_EXAMPLE','learning_example',str(example_id),
                  body.model_dump(),example['version'])
            return _example_projection(cur, updated)

    @router.post('/api/v1/projects/{project_id}/learning/datasets', status_code=201, dependencies=[Depends(csrf)])
    def freeze_dataset(project_id: UUID, body: DatasetCreate,
                       idempotency_key: str | None = Header(default=None), user_id: str = Depends(actor)):
        key = _key(idempotency_key)
        require_preparation()
        if len(set(body.example_ids)) != len(body.example_ids):
            raise HTTPException(422, 'duplicate example IDs')
        request_hash = digest(body.model_dump(mode='json'))
        object_key = None
        try:
            with connection() as conn, conn.cursor() as cur:
                membership(cur,project_id,user_id,{'engineer','reviewer','approver'})
                _lock(cur,project_id)
                cur.execute('SELECT * FROM learning_datasets WHERE project_id=%s AND idempotency_key=%s', (project_id,key))
                previous = cur.fetchone()
                if previous:
                    if previous['request_sha256'] != request_hash:
                        raise HTTPException(409, 'IDEMPOTENCY_KEY_CONFLICT')
                    return _dataset_projection(cur, previous)
                entries, rows = [], []
                for example_id in sorted(body.example_ids, key=str):
                    cur.execute('SELECT * FROM learning_examples WHERE id=%s AND project_id=%s FOR SHARE', (example_id,project_id))
                    example = cur.fetchone()
                    if not example:
                        raise HTTPException(404, 'learning example not found')
                    if example['status'] != 'APPROVED' or example['split'] != body.split or not example['data_use_confirmed']:
                        raise HTTPException(409, 'DATASET_EXAMPLE_NOT_APPROVED_OR_SPLIT_MISMATCH')
                    current = _example_projection(cur, example)
                    if current['freshness'] != 'CURRENT':
                        raise HTTPException(409, 'DATASET_SOURCE_STALE')
                    entries.append({k: str(example[k]) if k in {'id','source_chunk_id'} else example[k] for k in
                                    ('id','source_chunk_id','source_snapshot','family_key','origin','content_sha256',
                                     'version','created_by','reviewed_by','review_note')})
                    entries[-1].update(created_at=example['created_at'].isoformat(), reviewed_at=example['reviewed_at'].isoformat())
                    rows.append({'prompt':example['prompt'], 'completion':example['completion']})
                cur.execute('SELECT coalesce(max(version),0)+1 AS next FROM learning_datasets WHERE project_id=%s AND name=%s',
                            (project_id,body.name))
                version = cur.fetchone()['next']
                dataset_id, artifact_id = uuid4(), uuid4()
                data = ''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in rows).encode()
                object_key,size,sha256 = write_bytes(project_id,artifact_id,data)
                resolved_path(object_key).chmod(0o600)
                manifest = {'schema':'dorilab.learning.dataset.v1','name':body.name,'version':version,'split':body.split,
                            'format':'PROMPT_COMPLETION_JSONL_PREPARATION_V1','example_count':len(rows),
                            'examples':entries,'jsonl_sha256':sha256,'local_only':True,'recipe_mapping_verified':False,
                            'approval_scope':'LOCAL_DATASET_PREPARATION_ONLY','created_by':user_id}
                purpose = 'TRAINING' if body.split == 'TRAIN' else 'EVALUATION_GOLD'
                cur.execute(
                    """INSERT INTO artifact_versions(id,project_id,kind,filename,content_type,byte_size,sha256,
                       object_key,usage_purpose,created_by) VALUES (%s,%s,'LEARNING_DATASET',%s,'application/json',%s,%s,%s,%s,%s)""",
                    (artifact_id,project_id,f'{body.name}-v{version}-{body.split.lower()}.jsonl',size,sha256,object_key,purpose,user_id))
                cur.execute(
                    """INSERT INTO learning_datasets(id,project_id,name,split,version,manifest,manifest_sha256,
                       artifact_id,created_by,idempotency_key,request_sha256) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                       RETURNING *""", (dataset_id,project_id,body.name,body.split,version,json.dumps(manifest),digest(manifest),
                                        artifact_id,user_id,key,request_hash))
                dataset = cur.fetchone()
                audit(cur,project_id,user_id,'FREEZE_LEARNING_DATASET','learning_dataset',str(dataset_id),manifest)
                result = _dataset_projection(cur, dataset)
            return result
        except Exception:
            if object_key:
                resolved_path(object_key).unlink(missing_ok=True)
            raise

    @router.get('/api/v1/learning/datasets/{dataset_id}/manifest')
    def dataset_manifest(dataset_id: UUID, user_id: str = Depends(actor)):
        require_preparation()
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM learning_datasets WHERE id=%s', (dataset_id,))
            dataset = cur.fetchone()
            if not dataset:
                raise HTTPException(404, 'dataset not found')
            membership(cur,dataset['project_id'],user_id)
            return _dataset_projection(cur,dataset)

    return router
