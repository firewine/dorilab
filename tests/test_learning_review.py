"""Public local human review contract; no draft dataset enablement or remote calls."""
import pytest

from conftest import sign_in
from test_document_rag import PROJECT, parse_document, upload_document
from dorilab.contracts import digest
from dorilab.db import connection
from dorilab.storage import resolved_path


def draft(client, headers, *, project=PROJECT, **source_options):
    artifact = upload_document(client, headers, project=project, purpose='TRAINING', **source_options)
    chunk = parse_document(client, headers, artifact['id'])['chunks'][0]
    body = {'title':'TEST synthetic human review', 'family_key':'test-review-paper',
        'split':'TRAIN', 'origin':'SYNTHETIC_HUMAN_AUTHORED','source_chunk_id':chunk['id'],
        'prompt':'  Which inputs are needed?\n',
        'completion':'  Power and location. Product performance remains unassessed.\n'}
    response = client.post(f'/api/v1/projects/{project}/learning/examples',
        headers={**headers,'Idempotency-Key':'review-draft-key01'},json=body)
    assert response.status_code == 201, response.text
    return artifact, chunk, response.json()


def decision(client, headers, row, *, action='APPROVED', **overrides):
    body = {'expected_version':1,'decision':action,
        'note':'  TEST source and response checked. Local synthetic scope only.\n',
        'data_use_confirmed':action == 'APPROVED',**overrides}
    return client.post(f"/api/v1/learning/examples/{row['id']}/decisions",headers=headers,json=body), body


def stored(row):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM learning_examples WHERE id=%s',(row['id'],))
        return cur.fetchone()


@pytest.mark.parametrize('reviewer', ['reviewer@demo','approver@demo'])
@pytest.mark.parametrize('action', ['APPROVED','REJECTED'])
def test_review_preserves_original_content_and_one_immutable_human_decision(client, reviewer, action):
    engineer = sign_in(client)
    artifact, chunk, old = draft(client, engineer)
    headers = sign_in(client, reviewer)
    response, body = decision(client, headers, old, action=action)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row['status'] == action and row['version'] == 2
    assert row['reviewed_by'] == reviewer and row['reviewed_at']
    assert row['review_note'] == body['note']
    assert row['data_use_confirmed'] == (action == 'APPROVED')
    assert row['approval_scope'] == 'LOCAL_DATASET_PREPARATION_ONLY'
    assert row['semantic_correctness'] == ('HUMAN_REVIEW_ONLY' if action == 'APPROVED' else 'NOT_VERIFIED')
    for key in ('id','source_snapshot','prompt','completion','content_sha256','input_sha256','created_by','created_at'):
        assert row[key] == old[key]
    assert row['source_snapshot']['sha256'] == artifact['sha256']
    assert decision(client, headers, old, action=action)[0].status_code == 409
    assert decision(client, headers, old, action='REJECTED' if action == 'APPROVED' else 'APPROVED',expected_version=2)[0].status_code == 409
    current = client.get(f'/api/v1/projects/{PROJECT}/learning').json()
    assert current['examples'][0] == row and current['datasets'] == []
    assert current['example_review_enabled'] and not current['preparation_enabled']
    assert not current['training']['remote_execution_enabled']
    with connection() as conn, conn.cursor() as cur:
        for table in ('review_jobs','model_runs','human_reviews','gate_decisions','verification_closures','learning_datasets'):
            cur.execute(f'SELECT count(*) AS total FROM {table}')
            assert cur.fetchone()['total'] == 0
        cur.execute("SELECT actor,before_version,payload_hash FROM audit_events WHERE action='REVIEW_LEARNING_EXAMPLE'")
        assert cur.fetchall() == [{'actor':reviewer,'before_version':1,'payload_hash':digest(body)}]


@pytest.mark.parametrize('user', ['engineer@demo','viewer@demo'])
def test_non_reviewers_cannot_approve_or_reject(client, user):
    _, _, row = draft(client, sign_in(client))
    headers = sign_in(client, user)
    assert decision(client, headers, row)[0].status_code == 403
    assert decision(client, headers, row, action='REJECTED')[0].status_code == 403
    actual = stored(row)
    assert actual['status'] == 'DRAFT' and actual['version'] == 1 and actual['reviewed_by'] is None


def test_review_cannot_cross_project_membership(client):
    headers = sign_in(client)
    other = client.post('/api/v1/projects',headers=headers,json={
        'display_id':'REVIEW-FOREIGN','name':'TEST isolated review','framework':'KASA',
        'mode':'DEMO','data_policy':'LOCAL_ONLY'}).json()['id']
    _, _, row = draft(client, headers, project=other)
    reviewer = sign_in(client,'reviewer@demo')
    assert decision(client, reviewer, row)[0].status_code == 404
    assert stored(row)['reviewed_by'] is None


@pytest.mark.parametrize('change', ['edition','bytes','chunk','parser'])
def test_stale_source_blocks_approval_but_can_be_rejected_with_reason(client, change):
    artifact, chunk, row = draft(client, sign_in(client))
    with connection() as conn, conn.cursor() as cur:
        if change == 'edition':
            cur.execute("UPDATE artifact_versions SET edition='REV-B' WHERE id=%s",(artifact['id'],))
        elif change == 'bytes':
            resolved_path(artifact['object_key']).write_bytes(b'TEST changed source')
        elif change == 'chunk':
            cur.execute("UPDATE document_chunks SET chunk_text='TEST modified text' WHERE id=%s",(chunk['id'],))
        else:
            cur.execute("UPDATE document_parser_runs SET status='FAILED' WHERE artifact_id=%s",(artifact['id'],))
    headers = sign_in(client,'reviewer@demo')
    response, _ = decision(client, headers, row)
    assert response.status_code == 409 and response.json()['detail'].startswith('SOURCE_NOT_CURRENT:')
    assert stored(row)['reviewed_by'] is None
    rejected, _ = decision(client, headers, row, action='REJECTED',note='TEST stale source; prepare a new case.')
    assert rejected.status_code == 200
    assert rejected.json()['status'] == 'REJECTED' and rejected.json()['freshness'] == 'STALE'
    assert rejected.json()['source_snapshot'] == row['source_snapshot']


@pytest.mark.parametrize('rights,edition,confirmed', [
    ('UNCONFIRMED','DEMO-1',True),('RESTRICTED','DEMO-1',True),
    ('PUBLIC','',True),('PUBLIC',' \n ',True),('PUBLIC','DEMO-1',False)])
def test_use_rights_edition_and_actual_attestation_are_required(client, rights, edition, confirmed):
    _, _, row = draft(client, sign_in(client), rights=rights, edition=edition)
    headers = sign_in(client,'reviewer@demo')
    response, _ = decision(client, headers, row, data_use_confirmed=confirmed)
    assert response.status_code == 409
    assert response.json()['detail'] == 'DATA_USE_OR_EDITION_UNCONFIRMED'
    assert stored(row)['status'] == 'DRAFT'
    assert decision(client, headers, row, action='REJECTED',note='TEST unconfirmed use or edition.')[0].status_code == 200


def test_invalid_note_version_and_missing_csrf_leave_draft_unchanged(client):
    _, _, row = draft(client, sign_in(client))
    headers = sign_in(client,'reviewer@demo')
    assert decision(client, headers, row, note=' \n ')[0].status_code == 422
    assert decision(client, headers, row, expected_version=0)[0].status_code == 422
    assert decision(client, headers, row, expected_version=2)[0].status_code == 409
    assert decision(client, {}, row)[0].status_code == 403
    assert stored(row)['status'] == 'DRAFT' and stored(row)['reviewed_by'] is None


def test_approved_then_changed_source_preserves_historical_decision_without_reapproval(client):
    artifact, _, row = draft(client, sign_in(client))
    headers = sign_in(client,'reviewer@demo')
    accepted, _ = decision(client, headers, row)
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE artifact_versions SET edition='REV-B' WHERE id=%s",(artifact['id'],))
    current = client.get(f'/api/v1/projects/{PROJECT}/learning').json()['examples'][0]
    assert current['status'] == 'APPROVED' and current['freshness'] == 'STALE'
    for key in ('source_snapshot','review_note','reviewed_by','reviewed_at','version','prompt','completion'):
        assert current[key] == accepted.json()[key]
    assert decision(client, headers, row, expected_version=2)[0].status_code == 409


def test_approval_does_not_release_dataset_export_or_remote_training(client):
    _, _, row = draft(client, sign_in(client))
    headers = sign_in(client,'reviewer@demo')
    assert decision(client, headers, row)[0].status_code == 200
    result = client.post(f'/api/v1/projects/{PROJECT}/learning/datasets',
        headers={**headers,'Idempotency-Key':'review-not-freeze'},
        json={'name':'test-prepared','split':'TRAIN','example_ids':[row['id']]})
    assert result.status_code == 501
    assert client.get(f'/api/v1/learning/datasets/{row["id"]}/manifest').status_code == 501
