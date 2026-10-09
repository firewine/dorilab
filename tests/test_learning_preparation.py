from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest

from conftest import sign_in
from test_document_rag import PROJECT, parse_document, retrieve, upload_document
from dorilab.contracts import digest
from dorilab.db import connection
from dorilab.storage import resolved_path


@pytest.fixture(autouse=True)
def enable_preparation_draft_for_tests(monkeypatch):
    # The draft is not enabled in the user's app; exercise it only in the isolated test DB.
    monkeypatch.setattr('dorilab.learning.PREPARATION_ENABLED', True)


def source(client, headers, **kwargs):
    artifact = upload_document(client, headers, **kwargs)
    parsed = parse_document(client, headers, artifact['id'])
    return artifact, parsed['chunks'][0]


def example(client, headers, chunk, *, key='prepare-example-01', **kwargs):
    payload = {'title':'Thermal input example','family_key':'thermal-input-v1','split':'TRAIN',
               'origin':'SYNTHETIC_HUMAN_AUTHORED','source_chunk_id':chunk['id'],
               'prompt':'Which thermal correlation inputs are required?',
               'completion':'Component dissipation and heat-source location; performance remains unassessed.', **kwargs}
    return client.post(f'/api/v1/projects/{PROJECT}/learning/examples',
                       headers={**headers,'Idempotency-Key':key},json=payload)


def approve(client, example_id):
    headers = sign_in(client,'reviewer@demo')
    result = client.post(f'/api/v1/learning/examples/{example_id}/decisions', headers=headers,
                         json={'expected_version':1,'decision':'APPROVED',
                               'note':'Source checked. Local synthetic preparation only.', 'data_use_confirmed':True})
    assert result.status_code == 200, result.text
    return headers, result.json()


def freeze(client, headers, ids, *, key='dataset-freeze-01', **kwargs):
    return client.post(f'/api/v1/projects/{PROJECT}/learning/datasets',
                       headers={**headers,'Idempotency-Key':key},
                       json={'name':'bm1-input','split':'TRAIN','example_ids':ids, **kwargs})


def test_baseline_is_dated_source_backed_and_never_current_gpu_readiness(client):
    assert client.get(f'/api/v1/projects/{PROJECT}/development').status_code == 401
    sign_in(client)
    result = client.get(f'/api/v1/projects/{PROJECT}/development').json()
    assert result['overall_status'] == 'PARTIAL'
    assert [m['id'] for m in result['milestones']] == ['M1','M2','M3','M4','M5','M6']
    assert result['model_baseline_scope'] == 'PINNED_PROFILE_NOT_CURRENT_READINESS'
    for entry in result['evidence']:
        response = client.get(entry['download_url'])
        assert response.status_code == 200
        assert entry['source_verified']
        assert hashlib.sha256(response.content).hexdigest() == entry['sha256']
    assert client.get(f'/api/v1/projects/{PROJECT}/development/evidence/unknown').status_code == 404
    overview = client.get(f'/api/v1/projects/{PROJECT}/learning').json()
    assert overview['documents'] == overview['examples'] == overview['datasets'] == []
    assert overview['training']['state'] == 'BLOCKED'
    assert overview['training']['job_id'] is None
    assert overview['training']['remote_checked'] is False
    assert overview['training']['remote_execution_enabled'] is False


def test_example_idempotency_partition_and_authority_are_server_enforced(client):
    headers = sign_in(client)
    artifact, chunk = source(client,headers)
    first = example(client,headers,chunk)
    assert first.status_code == 201, first.text
    row = first.json()
    assert row['status'] == 'DRAFT' and row['freshness'] == 'CURRENT'
    assert row['source_snapshot']['sha256'] == artifact['sha256']
    assert example(client,headers,chunk).json()['id'] == row['id']
    assert example(client,headers,chunk,title='Changed title').status_code == 409
    assert example(client,headers,chunk,key='different-key-001',split='EVALUATION').json()['detail'] == 'TRAIN_EVALUATION_OVERLAP'
    assert example(client,headers,chunk,key='different-key-002',family_key='invented-family').json()['detail'] == 'SOURCE_FAMILY_CONFLICT'
    denied = client.post(f"/api/v1/learning/examples/{row['id']}/decisions", headers=headers,
                         json={'expected_version':1,'decision':'APPROVED','note':'not authorized','data_use_confirmed':True})
    assert denied.status_code == 403
    assert freeze(client,headers,[row['id']]).status_code == 409
    viewer = sign_in(client,'viewer@demo')
    assert example(client,viewer,chunk,key='viewer-key-0001').status_code == 403
    assert client.post(f'/api/v1/projects/{PROJECT}/learning/examples',json={}).status_code == 403


def test_sealed_dataset_preserves_bytes_provenance_versions_and_does_not_create_model_or_business_decisions(client):
    headers = sign_in(client)
    _, chunk = source(client,headers)
    draft = example(client,headers,chunk).json()
    headers, accepted = approve(client,draft['id'])
    assert accepted['approval_scope'] == 'LOCAL_DATASET_PREPARATION_ONLY'
    assert accepted['version'] == 2
    first = freeze(client,headers,[draft['id']])
    assert first.status_code == 201, first.text
    dataset = first.json()
    assert dataset['manifest_sha256'] == digest(dataset['manifest'])
    assert dataset['manifest']['local_only'] is True
    assert dataset['manifest']['recipe_mapping_verified'] is False
    origin = dataset['manifest']['examples'][0]
    assert origin['created_by'] == 'engineer@demo' and origin['reviewed_by'] == 'reviewer@demo'
    assert origin['reviewed_at'] and origin['source_snapshot']['locator'] == chunk['locator']
    download = client.get(dataset['download_url'])
    assert hashlib.sha256(download.content).hexdigest() == dataset['manifest']['jsonl_sha256']
    assert json.loads(download.content)['completion'] == draft['completion']
    assert freeze(client,headers,[draft['id']]).json()['id'] == dataset['id']
    assert freeze(client,headers,[draft['id']],name='different-name').status_code == 409
    second = freeze(client,headers,[draft['id']],key='dataset-freeze-02').json()
    assert second['version'] == 2 and second['id'] != dataset['id']
    assert client.get(dataset['download_url']).content == download.content
    assert client.get(dataset['manifest_url']).json()['manifest'] == dataset['manifest']
    repeat = client.post(f"/api/v1/learning/examples/{draft['id']}/decisions", headers=headers,
                          json={'expected_version':1,'decision':'APPROVED','note':'again','data_use_confirmed':True})
    assert repeat.status_code == 409
    assert freeze(client,headers,[draft['id']],key='wrong-split-key1',split='EVALUATION').status_code == 409
    assert freeze(client,headers,[draft['id'],draft['id']],key='duplicate-key01').status_code == 422
    assert client.post(f"/api/v1/artifacts/{dataset['artifact_id']}/parse",headers=headers).status_code == 422
    with connection() as conn, conn.cursor() as cur:
        for table in ('model_runs','review_jobs','human_reviews','gate_decisions','verification_closures'):
            cur.execute(f'SELECT count(*) AS total FROM {table}')
            assert cur.fetchone()['total'] == 0
        cur.execute('SELECT object_key,usage_purpose FROM artifact_versions WHERE id=%s',(dataset['artifact_id'],))
        stored = cur.fetchone()
    assert stored['usage_purpose'] == 'TRAINING'
    assert resolved_path(stored['object_key']).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('change', ['edition','bytes','chunk','parser'])
def test_source_change_keeps_old_approval_and_release_but_marks_them_stale(client, change):
    headers = sign_in(client)
    artifact, chunk = source(client,headers)
    draft = example(client,headers,chunk).json()
    headers, _ = approve(client,draft['id'])
    dataset = freeze(client,headers,[draft['id']]).json()
    saved = client.get(dataset['download_url']).content
    with connection() as conn, conn.cursor() as cur:
        if change == 'edition':
            cur.execute("UPDATE artifact_versions SET edition='REV-B' WHERE id=%s",(artifact['id'],))
        elif change == 'chunk':
            cur.execute("UPDATE document_chunks SET chunk_text='Modified source' WHERE id=%s",(chunk['id'],))
        elif change == 'parser':
            cur.execute("UPDATE document_parser_runs SET status='FAILED' WHERE artifact_id=%s",(artifact['id'],))
        else:
            cur.execute('SELECT object_key FROM artifact_versions WHERE id=%s',(artifact['id'],))
            resolved_path(cur.fetchone()['object_key']).write_bytes(b'changed source bytes')
    overview = client.get(f'/api/v1/projects/{PROJECT}/learning').json()
    assert overview['examples'][0]['status'] == 'APPROVED'
    assert overview['examples'][0]['freshness'] == 'STALE'
    assert overview['datasets'][0]['freshness'] == 'STALE'
    assert overview['datasets'][0]['manifest_sha256'] == dataset['manifest_sha256']
    assert freeze(client,headers,[draft['id']],key='stale-freeze-key1').status_code == 409
    assert client.get(dataset['download_url']).content == saved
    assert 'TRAIN_DATASET_NOT_READY' in overview['training']['blockers']


def test_document_family_reupload_and_input_overlap_are_not_independent_evaluation(client):
    headers = sign_in(client)
    _, chunk = source(client,headers)
    assert example(client,headers,chunk).status_code == 201
    _, revision = source(client,headers,name='revision.md',edition='REV-B',content=b'Revised thermal source.\n')
    assert example(client,headers,revision,key='family-eval-key1',split='EVALUATION',prompt='Another question').json()['detail'] == 'TRAIN_EVALUATION_OVERLAP'
    assert example(client,headers,revision,key='input-eval-key1',family_key='other-paper',split='EVALUATION',completion='Different expected response').json()['detail'] == 'TRAIN_EVALUATION_OVERLAP'
    _, same_bytes = source(client,headers,name='copied.md')
    assert example(client,headers,same_bytes,key='copy-eval-key1',family_key='other-family',split='EVALUATION',prompt='New question').json()['detail'] == 'TRAIN_EVALUATION_OVERLAP'
    independent = example(client,headers,revision,key='valid-eval-key1',family_key='independent-paper',split='EVALUATION',prompt='Independent held-out question')
    assert independent.status_code == 201
    headers, _ = approve(client,independent.json()['id'])
    release = freeze(client,headers,[independent.json()['id']],split='EVALUATION')
    assert release.status_code == 201
    assert release.json()['manifest']['split'] == 'EVALUATION'


@pytest.mark.parametrize('purpose,split', [('EVALUATION_GOLD','TRAIN'),('TRAINING','EVALUATION')])
def test_reserved_source_purpose_stays_out_of_training_or_evaluation_and_rag(client,purpose,split):
    headers = sign_in(client)
    _, chunk = source(client,headers,purpose=purpose)
    assert example(client,headers,chunk,split=split).json()['detail'] == 'SOURCE_USAGE_SPLIT_CONFLICT'
    retrieved = retrieve(client,headers,'component dissipation power map',key='prepared-source-rag1')
    assert retrieved['run']['candidate_count'] == 0


def test_review_requires_actual_current_source_edition_and_use_attestation(client):
    headers = sign_in(client)
    _, chunk = source(client,headers,rights='UNCONFIRMED',edition='')
    draft = example(client,headers,chunk).json()
    reviewer = sign_in(client,'reviewer@demo')
    decision = {'expected_version':1,'decision':'APPROVED','note':'unconfirmed','data_use_confirmed':True}
    response = client.post(f"/api/v1/learning/examples/{draft['id']}/decisions",headers=reviewer,json=decision)
    assert response.status_code == 409
    rejected = client.post(f"/api/v1/learning/examples/{draft['id']}/decisions",headers=reviewer,json={**decision,'decision':'REJECTED','data_use_confirmed':False})
    assert rejected.status_code == 200 and rejected.json()['review_note'] == 'unconfirmed'
    _, valid = source(client,reviewer,name='valid-source.md',content=b'Another valid source.\n')
    draft2 = example(client,reviewer,valid,key='confirmed-source1',family_key='new-paper',prompt='Another question').json()
    response2 = client.post(f"/api/v1/learning/examples/{draft2['id']}/decisions",headers=reviewer,json={**decision,'data_use_confirmed':False})
    assert response2.json()['detail'] == 'DATA_USE_OR_EDITION_UNCONFIRMED'


def test_preparation_and_download_are_project_isolated(client):
    headers = sign_in(client)
    other = client.post('/api/v1/projects',headers=headers,json={'display_id':'ISOLATED-LEARNING','name':'Local isolation','framework':'KASA','mode':'DEMO','data_policy':'LOCAL_ONLY'}).json()
    foreign, foreign_chunk = source(client,headers,project=other['id'])
    assert example(client,headers,foreign_chunk).status_code == 404
    _, own_chunk = source(client,headers)
    draft = example(client,headers,own_chunk).json()
    reviewer, _ = approve(client,draft['id'])
    dataset = freeze(client,reviewer,[draft['id']]).json()
    with connection() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM memberships WHERE project_id=%s AND user_id=%s',(PROJECT,'viewer@demo'))
    try:
        sign_in(client,'viewer@demo')
        for path in (f'/api/v1/projects/{PROJECT}/learning',f'/api/v1/projects/{PROJECT}/development',
                     dataset['download_url'],dataset['manifest_url']):
            assert client.get(path).status_code == 404
        assert client.get(f"/api/v1/artifacts/{foreign['id']}/chunks").status_code == 404
    finally:
        # Restore the shared fixture's viewer membership for unrelated regression tests.
        with connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO memberships(project_id,user_id,role) VALUES (%s,'viewer@demo','viewer') ON CONFLICT DO NOTHING",(PROJECT,))
