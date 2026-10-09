"""Authoring remains distinct from human review; dataset exports are not enabled."""
import pytest

from dorilab.contracts import digest
from dorilab.db import connection
from dorilab.storage import resolved_path

from conftest import sign_in
from test_document_rag import PROJECT, parse_document, upload_document


def payload_for(client, headers):
    artifact = upload_document(client, headers, purpose='TRAINING')
    chunk = parse_document(client, headers, artifact['id'])['chunks'][0]
    return artifact, chunk, {'title':'TEST synthetic authoring', 'family_key':'synthetic-paper',
        'split':'TRAIN','origin':'SYNTHETIC_HUMAN_AUTHORED','source_chunk_id':chunk['id'],
        'prompt':'  What inputs are required?\n',
        'completion':'  Component power map and heat-source locations.\nPerformance remains unassessed.\n'}


def save(client, headers, payload, key='authoring-only-01'):
    return client.post(f'/api/v1/projects/{PROJECT}/learning/examples',
        headers={**headers,'Idempotency-Key':key},json=payload)


def test_draft_is_exact_source_linked_idempotent_and_has_no_business_side_effects(client):
    headers = sign_in(client)
    artifact, chunk, body = payload_for(client, headers)
    first = save(client, headers, body)
    assert first.status_code == 201, first.text
    row = first.json()
    assert row['status'] == 'DRAFT' and row['semantic_correctness'] == 'NOT_VERIFIED'
    assert row['authoring_scope'] == 'LOCAL_DRAFT_ONLY' and row['freshness'] == 'CURRENT'
    assert row['created_by'] == 'engineer@demo' and row['created_at']
    assert row['reviewed_by'] is row['reviewed_at'] is None
    assert row['data_use_confirmed'] is False
    assert row['prompt'] == body['prompt'] and row['completion'] == body['completion']
    assert row['content_sha256'] == digest({'prompt':body['prompt'],'completion':body['completion']})
    assert row['source_snapshot']['sha256'] == artifact['sha256']
    assert row['source_snapshot']['edition'] == artifact['edition']
    assert row['source_snapshot']['locator'] == chunk['locator']
    assert row['source_snapshot']['text_sha256'] == chunk['text_sha256']
    assert save(client, headers, body).json()['id'] == row['id']
    assert save(client, headers, {**body,'completion':'Different response'}).status_code == 409
    overview = client.get(f'/api/v1/projects/{PROJECT}/learning').json()
    assert overview['examples'][0] == row
    assert overview['datasets'] == [] and overview['preparation_enabled'] is False
    assert overview['example_review_enabled'] is True
    assert overview['training']['remote_execution_enabled'] is False
    with connection() as conn, conn.cursor() as cur:
        for table in ('review_jobs','model_runs','human_reviews','verification_closures','gate_decisions','learning_datasets'):
            cur.execute(f'SELECT count(*) AS total FROM {table}')
            assert cur.fetchone()['total'] == 0
        cur.execute("SELECT action FROM audit_events WHERE object_type='learning_example'")
        assert [r['action'] for r in cur.fetchall()] == ['PREPARE_LEARNING_EXAMPLE']


@pytest.mark.parametrize('change', ['edition','bytes','chunk','parser'])
def test_changed_source_keeps_old_draft_stale_and_checks_current_source(client, change):
    headers = sign_in(client)
    artifact, chunk, body = payload_for(client, headers)
    first = save(client, headers, body).json()
    with connection() as conn, conn.cursor() as cur:
        if change == 'edition':
            cur.execute("UPDATE artifact_versions SET edition='REV-B' WHERE id=%s", (artifact['id'],))
        elif change == 'bytes':
            resolved_path(artifact['object_key']).write_bytes(b'changed bytes')
        elif change == 'chunk':
            cur.execute("UPDATE document_chunks SET chunk_text='changed text' WHERE id=%s", (chunk['id'],))
        else:
            cur.execute("UPDATE document_parser_runs SET status='FAILED' WHERE artifact_id=%s", (artifact['id'],))
    row = client.get(f'/api/v1/projects/{PROJECT}/learning').json()['examples'][0]
    assert row['id'] == first['id'] and row['freshness'] == 'STALE'
    assert row['status'] == 'DRAFT' and row['source_snapshot'] == first['source_snapshot']
    assert row['prompt'] == body['prompt'] and row['completion'] == body['completion']
    attempted = save(client, headers, body, key='authoring-changed-source')
    # Current metadata can form a new draft; corruption/failed parsing cannot.
    # Neither path revises the old snapshot or approves its content.
    if change == 'edition':
        assert attempted.status_code == 201
        assert attempted.json()['source_snapshot']['edition'] == 'REV-B'
        assert attempted.json()['status'] == 'DRAFT'
    else:
        assert attempted.status_code == 409
        assert attempted.json()['detail'].startswith('SOURCE_NOT_CURRENT:')


def test_default_release_denies_viewer_and_foreign_chunk_without_membership_changes(client):
    headers = sign_in(client)
    artifact, chunk, body = payload_for(client, headers)
    other = client.post('/api/v1/projects',headers=headers,json={
        'display_id':'AUTHORING-FOREIGN','name':'isolated authoring test','framework':'KASA',
        'mode':'DEMO','data_policy':'LOCAL_ONLY'}).json()['id']
    foreign = upload_document(client, headers, project=other)
    foreign_chunk = parse_document(client, headers, foreign['id'])['chunks'][0]
    assert save(client, headers, {**body,'source_chunk_id':foreign_chunk['id']}).status_code == 404
    assert save(client, headers, body).status_code == 201
    viewer = sign_in(client, 'viewer@demo')
    assert len(client.get(f'/api/v1/projects/{PROJECT}/learning').json()['examples']) == 1
    assert save(client, viewer, body, key='viewer-authoring-01').status_code == 403
    assert client.get(f'/api/v1/projects/{other}/learning').status_code == 404


def test_authoring_cannot_cross_source_usage_or_promote_draft(client):
    headers = sign_in(client)
    artifact, chunk, body = payload_for(client, headers)
    assert save(client, headers, {**body,'split':'EVALUATION'}).json()['detail'] == 'SOURCE_USAGE_SPLIT_CONFLICT'
    draft = save(client, headers, body).json()
    response = client.post(f"/api/v1/learning/examples/{draft['id']}/decisions",headers=headers,
        json={'expected_version':1,'decision':'APPROVED','note':'next step','data_use_confirmed':True})
    assert response.status_code == 403
    assert save(client, headers, {**body,'status':'APPROVED'},key='invented-approval').status_code == 422
    assert client.get(f'/api/v1/learning/datasets/{draft["id"]}/manifest').status_code == 501


@pytest.mark.parametrize('field', ['title','prompt','completion'])
def test_blank_authoring_content_is_rejected_without_saving(client, field):
    headers = sign_in(client)
    _, _, body = payload_for(client, headers)
    assert save(client, headers, {**body,field:' \n '}).status_code == 422
    assert client.get(f'/api/v1/projects/{PROJECT}/learning').json()['examples'] == []
