"""Persist question-set classification and individual human label reviews.

These records are not verified paper evidence or exportable training datasets.
There is deliberately no model call, remote runner, or bulk approval path.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import actor, csrf
from .contracts import digest
from .db import connection
from .learning_import import IMPORTER_VERSION, parse_100q_handoff
from .storage import resolved_path

APPROVAL_SCOPE = 'LOCAL_LABEL_REVIEW_ONLY'
_DECISION_NOT_LOADED = object()


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    artifact_id: UUID


class ImportDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    decision: Literal['APPROVED', 'REJECTED']
    note: str = Field(min_length=1, max_length=2000)
    review_confirmed: bool = False
    prompt: str | None = Field(default=None, min_length=1, max_length=32768)
    completion: str | None = Field(default=None, min_length=1, max_length=32768)

    @field_validator('note', 'prompt', 'completion')
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError('review fields must not be blank')
        return value


def _snapshot(artifact):
    return {key: str(artifact[key]) if key == 'id' else artifact[key] for key in (
        'id', 'kind', 'filename', 'content_type', 'byte_size', 'sha256',
        'usage_purpose', 'rights_status', 'edition')}


def _artifact(cur, project_id, artifact_id):
    cur.execute('SELECT * FROM artifact_versions WHERE id=%s AND project_id=%s FOR SHARE',
                (artifact_id, project_id))
    return cur.fetchone()


def read_handoff(cur, project_id, artifact_id):
    artifact = _artifact(cur, project_id, artifact_id)
    if not artifact:
        raise HTTPException(404, 'training source artifact not found')
    if (artifact['kind'] != 'SOURCE' or artifact['usage_purpose'] != 'TRAINING'
            or not artifact['filename'].lower().endswith('.md')
            or artifact['content_type'] not in {'text/markdown', 'text/plain'}):
        raise HTTPException(422, 'HANDOFF_REQUIRES_MARKDOWN_TRAINING_SOURCE')
    if artifact['byte_size'] > 20 * 1024 * 1024:
        raise HTTPException(413, 'HANDOFF_FILE_TOO_LARGE')
    try:
        raw = resolved_path(artifact['object_key']).read_bytes()
    except (OSError, ValueError):
        raise HTTPException(409, 'HANDOFF_SOURCE_UNAVAILABLE')
    if len(raw) != artifact['byte_size'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
        raise HTTPException(409, 'HANDOFF_SOURCE_HASH_MISMATCH')
    try:
        parsed = parse_100q_handoff(raw.decode('utf-8-sig'))
    except UnicodeDecodeError:
        raise HTTPException(422, 'HANDOFF_MARKDOWN_MUST_BE_UTF8')
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return artifact, parsed


def _source_issues(cur, batch):
    issues = []
    if batch['importer_version'] != IMPORTER_VERSION:
        issues.append('HANDOFF_IMPORTER_VERSION_CHANGED')
    artifact = _artifact(cur, batch['project_id'], batch['artifact_id'])
    if not artifact:
        return issues + ['HANDOFF_SOURCE_UNAVAILABLE']
    if _snapshot(artifact) != batch['source_snapshot']:
        issues.append('HANDOFF_SOURCE_METADATA_CHANGED')
    try:
        raw = resolved_path(artifact['object_key']).read_bytes()
        if (hashlib.sha256(raw).hexdigest() != batch['source_sha256']
                or len(raw) != batch['source_snapshot']['byte_size']):
            issues.append('HANDOFF_SOURCE_BYTES_CHANGED')
    except (OSError, ValueError):
        issues.append('HANDOFF_SOURCE_UNAVAILABLE')
    return issues


def is_import_source(cur, project_id, source_sha256):
    """A mixed set is not a verified original-paper chunk for manual authoring."""
    cur.execute('SELECT 1 FROM learning_imports WHERE project_id=%s AND source_sha256=%s LIMIT 1',
                (project_id, source_sha256))
    return cur.fetchone() is not None


def _items(cur, import_id):
    cur.execute('SELECT * FROM learning_import_items WHERE import_id=%s ORDER BY question_id', (import_id,))
    return cur.fetchall()


def _integrity_issues(item):
    original = item['original_payload']
    issues = []
    if digest(original) != item['original_sha256']:
        issues.append('HANDOFF_ITEM_HASH_MISMATCH')
    if (original.get('id') != item['question_id'] or original.get('category') != item['category']
            or original.get('split') != item['split'] or original.get('family_key') != item['family_key']):
        issues.append('HANDOFF_ITEM_CLASSIFICATION_CHANGED')
    return issues


def _summary(cur, batch, items=None, issues=None):
    items = _items(cur, batch['id']) if items is None else items
    issues = _source_issues(cur, batch) if issues is None else issues
    issues = sorted(set(issues + [issue for item in items for issue in _integrity_issues(item)]))
    counts = {status: sum(i['status'] == status for i in items) for status in ('DRAFT', 'APPROVED', 'REJECTED')}
    return {**batch, 'example_count': len(items), 'counts': counts,
            'train_count': sum(i['split'] == 'TRAIN' for i in items),
            'evaluation_count': sum(i['split'] == 'EVALUATION' for i in items),
            'categories': sorted({i['category'] for i in items}),
            'freshness': 'STALE' if issues else 'CURRENT', 'source_issues': issues,
            'approval_scope': APPROVAL_SCOPE, 'original_source_verified': False,
            'training_started': False, 'training_eligible': False}


def list_imports(cur, project_id):
    cur.execute('SELECT * FROM learning_imports WHERE project_id=%s ORDER BY created_at DESC,id', (project_id,))
    return [_summary(cur, b) for b in cur.fetchall()]


def _project_item(cur, item, issues, decision=_DECISION_NOT_LOADED):
    original = item['original_payload']
    issues = list(issues) + _integrity_issues(item)
    if decision is _DECISION_NOT_LOADED:
        cur.execute('SELECT * FROM learning_import_decisions WHERE item_id=%s', (item['id'],))
        decision = cur.fetchone()
    if ((item['status'] != 'DRAFT' and not decision) or
            (decision and (decision['decision'] != item['status'] or decision['to_version'] != item['version']))):
        issues.append('IMPORT_ITEM_REVIEW_HISTORY_MISMATCH')
    return {**original, **{k: item[k] for k in ('id', 'import_id', 'question_id', 'category', 'split',
                                              'family_key', 'status', 'version', 'original_sha256')},
            'original_payload': original, 'decision_history': [decision] if decision else [],
            'review_status': item['status'], 'original_review_status': original['review_status'],
            'reviewed_prompt': decision['reviewed_prompt'] if decision else None,
            'reviewed_completion': decision['reviewed_completion'] if decision else None,
            'freshness': 'STALE' if issues else 'CURRENT', 'source_issues': issues,
            'approval_scope': APPROVAL_SCOPE, 'original_source_verified': False,
            'training_eligible': False,
            'training_blockers': ['EVALUATION_EXCLUDED_FROM_TRAINING'] if item['split'] == 'EVALUATION' else
                ['ORIGINAL_PAPER_AND_DATA_USE_NOT_VERIFIED', 'IMPORT_DATASET_EXPORT_NOT_CONNECTED']}


def create_import_router(membership, audit):
    router = APIRouter(tags=['Question-set label review'])

    @router.post('/api/v1/projects/{project_id}/learning/imports', status_code=201, dependencies=[Depends(csrf)])
    def import_handoff(project_id: UUID, body: ImportRequest,
                       idempotency_key: str | None = Header(default=None), user_id: str = Depends(actor)):
        if not idempotency_key or not 8 <= len(idempotency_key) <= 160 or any(c.isspace() for c in idempotency_key):
            raise HTTPException(422, 'Idempotency-Key must be 8..160 non-whitespace characters')
        request_hash = digest(body.model_dump(mode='json'))
        with connection() as conn, conn.cursor() as cur:
            membership(cur, project_id, user_id, {'engineer', 'reviewer', 'approver'})
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (f'learning:{project_id}',))
            cur.execute('SELECT * FROM learning_import_requests WHERE project_id=%s AND idempotency_key=%s',
                        (project_id, idempotency_key))
            previous = cur.fetchone()
            if previous:
                if previous['request_sha256'] != request_hash:
                    raise HTTPException(409, 'IDEMPOTENCY_KEY_CONFLICT')
                cur.execute('SELECT * FROM learning_imports WHERE id=%s', (previous['import_id'],))
                return {**_summary(cur, cur.fetchone()), 'duplicate': True}
            artifact, parsed = read_handoff(cur, project_id, body.artifact_id)
            metadata_hash = digest({k: artifact[k] for k in ('rights_status', 'edition', 'usage_purpose')})
            cur.execute('''SELECT * FROM learning_imports WHERE project_id=%s AND source_sha256=%s
                           AND metadata_sha256=%s AND importer_version=%s''',
                        (project_id, artifact['sha256'], metadata_hash, IMPORTER_VERSION))
            batch = cur.fetchone()
            duplicate = batch is not None
            if batch is None:
                import_id = uuid4()
                cur.execute('''INSERT INTO learning_imports(id,project_id,artifact_id,source_snapshot,source_sha256,
                    metadata_sha256,importer_version,format,created_by,idempotency_key,request_sha256)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (import_id, project_id, artifact['id'], json.dumps(_snapshot(artifact)), artifact['sha256'],
                     metadata_hash, IMPORTER_VERSION, parsed['format'], user_id, idempotency_key, request_hash))
                batch = cur.fetchone()
                for row in parsed['rows']:
                    cur.execute('''INSERT INTO learning_import_items(id,import_id,project_id,question_id,category,
                        split,family_key,original_payload,original_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)''',
                        (uuid4(), import_id, project_id, row['id'], row['category'], row['split'], row['family_key'],
                         json.dumps(row, ensure_ascii=False), digest(row)))
                audit(cur, project_id, user_id, 'IMPORT_LEARNING_SET', 'learning_import', str(import_id),
                      {'source_sha256': artifact['sha256'], 'importer_version': IMPORTER_VERSION,
                       'count': parsed['example_count'], 'train': parsed['train_count'], 'evaluation': parsed['evaluation_count']})
            cur.execute('''INSERT INTO learning_import_requests(project_id,idempotency_key,request_sha256,import_id)
                           VALUES (%s,%s,%s,%s)''', (project_id, idempotency_key, request_hash, batch['id']))
            return {**_summary(cur, batch), 'duplicate': duplicate}

    @router.get('/api/v1/learning/imports/{import_id}')
    def get_import(import_id: UUID, user_id: str = Depends(actor)):
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM learning_imports WHERE id=%s', (import_id,))
            batch = cur.fetchone()
            if not batch:
                raise HTTPException(404, 'learning import not found')
            membership(cur, batch['project_id'], user_id)
            issues = _source_issues(cur, batch)
            items = _items(cur, import_id)
            cur.execute('''SELECT d.* FROM learning_import_decisions d JOIN learning_import_items i ON i.id=d.item_id
                           WHERE i.import_id=%s''', (import_id,))
            decisions = {d['item_id']: d for d in cur.fetchall()}
            return {**_summary(cur, batch, items, issues),
                    'items': [_project_item(cur, i, issues, decisions.get(i['id'])) for i in items]}

    @router.post('/api/v1/learning/import-items/{item_id}/decisions', dependencies=[Depends(csrf)])
    def decide_import_item(item_id: UUID, body: ImportDecision, user_id: str = Depends(actor)):
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM learning_import_items WHERE id=%s FOR UPDATE', (item_id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(404, 'learning import item not found')
            membership(cur, item['project_id'], user_id, {'reviewer', 'approver'})
            if item['status'] != 'DRAFT' or item['version'] != body.expected_version:
                raise HTTPException(409, 'IMPORT_ITEM_VERSION_OR_STATUS_CONFLICT')
            cur.execute('SELECT * FROM learning_imports WHERE id=%s', (item['import_id'],))
            batch = cur.fetchone()
            projected = _project_item(cur, item, _source_issues(cur, batch))
            prompt = completion = None
            if body.decision == 'APPROVED':
                if projected['source_issues']:
                    raise HTTPException(409, 'HANDOFF_SOURCE_NOT_CURRENT: ' + ','.join(projected['source_issues']))
                if not body.review_confirmed:
                    raise HTTPException(409, 'LABEL_REVIEW_CONFIRMATION_REQUIRED')
                prompt = body.prompt if body.prompt is not None else item['original_payload']['prompt']
                completion = body.completion if body.completion is not None else item['original_payload']['completion_draft']
            elif body.prompt is not None or body.completion is not None:
                raise HTTPException(422, 'REJECTED_ITEM_CANNOT_SAVE_APPROVED_TEXT')
            cur.execute('''INSERT INTO learning_import_decisions(id,item_id,project_id,decision,from_version,to_version,
                note,reviewed_prompt,reviewed_completion,review_confirmed,reviewed_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (uuid4(), item_id, item['project_id'], body.decision, item['version'], item['version'] + 1,
                 body.note, prompt, completion, body.review_confirmed, user_id))
            decision = cur.fetchone()
            cur.execute('UPDATE learning_import_items SET status=%s,version=version+1 WHERE id=%s RETURNING *',
                        (body.decision, item_id))
            updated = cur.fetchone()
            audit(cur, item['project_id'], user_id, 'REVIEW_IMPORTED_LEARNING_ITEM', 'learning_import_item', str(item_id),
                  {'decision_id': str(decision['id']), 'decision': body.decision, 'note': body.note,
                   'original_sha256': item['original_sha256'], 'reviewed_text_sha256': digest([prompt, completion]),
                   'approval_scope': APPROVAL_SCOPE}, item['version'])
            return _project_item(cur, updated, projected['source_issues'], decision)

    return router
