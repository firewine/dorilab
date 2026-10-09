"""The shipped document page reuses Artifact/Parser APIs, without learning activation."""
import hashlib

from dorilab.db import connection

from conftest import sign_in
from test_document_rag import PROJECT, parse_document, text_pdf, upload_document


def overview(client, project=PROJECT):
    response = client.get(f'/api/v1/projects/{project}/learning')
    assert response.status_code == 200, response.text
    return response.json()


def test_registration_lists_bytes_metadata_parser_receipt_and_locations(client):
    headers = sign_in(client)
    assert overview(client)['documents'] == []
    content = text_pdf()
    source = upload_document(client, headers, name='synthetic-paper.pdf', content=content,
                             content_type='application/pdf', purpose='TRAINING')
    assert overview(client)['documents'][0]['parser_status'] is None
    parsed = parse_document(client, headers, source['id'])
    record = overview(client)['documents'][0]
    assert record['id'] == source['id']
    assert record['sha256'] == hashlib.sha256(content).hexdigest()
    assert record['byte_size'] == len(content)
    assert record['edition'] == 'REV-A'
    assert record['usage_purpose'] == 'TRAINING'
    assert record['parser_status'] == 'COMPLETED'
    assert record['receipt_sha256'] == parsed['parser_run']['receipt_sha256']
    assert record['parser_version'] == 'dorilab-parser-v1'
    assert record['chunker_version'] == 'paragraph-1600-v1'
    detail = client.get(f"/api/v1/artifacts/{source['id']}/chunks").json()
    assert detail['chunks'][0]['locator'].startswith('PDF page 1')
    assert client.get(f"/api/v1/artifacts/{source['id']}/download").content == content
    assert overview(client)['preparation_enabled'] is False
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT (SELECT count(*) FROM review_jobs) AS jobs, (SELECT count(*) FROM model_runs) AS models')
        assert cur.fetchone() == {'jobs': 0, 'models': 0}


def test_failed_parse_keeps_original_and_failure_reason_after_retry(client):
    headers = sign_in(client)
    content = b'%PDF-1.7\nnot an actual PDF\n'
    source = upload_document(client, headers, name='broken.pdf', content=content,
                             content_type='application/pdf')
    for _ in range(2):
        response = client.post(f"/api/v1/artifacts/{source['id']}/parse", headers=headers)
        assert response.status_code == 422
        record = overview(client)['documents'][0]
        assert record['parser_status'] == 'FAILED'
        assert record['error_code'] == 'PDF_PARSE_FAILED'
        assert record['error_detail'] == 'PDF structure could not be read'
        assert record['finished_at']
        assert client.get(f"/api/v1/artifacts/{source['id']}/download").content == content
        assert client.get(f"/api/v1/artifacts/{source['id']}/chunks").json()['chunks'] == []
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) AS artifacts FROM artifact_versions')
        assert cur.fetchone()['artifacts'] == 1


def test_completed_reparse_reuses_chunks_and_does_not_duplicate_registration(client):
    headers = sign_in(client)
    source = upload_document(client, headers)
    first = parse_document(client, headers, source['id'])
    repeated = parse_document(client, headers, source['id'])
    assert first == repeated
    assert len(overview(client)['documents']) == 1
    assert len(client.get(f"/api/v1/artifacts/{source['id']}/chunks").json()['chunks']) == 2


def test_viewer_reads_own_documents_but_cannot_register_or_parse_foreign_project(client):
    headers = sign_in(client)
    source = upload_document(client, headers)
    foreign = client.post('/api/v1/projects', headers=headers, json={
        'display_id': 'DOC-ISOLATION', 'name': 'isolated document check',
        'framework': 'KASA', 'mode': 'DEMO', 'data_policy': 'LOCAL_ONLY'}).json()['id']
    other_source = upload_document(client, headers, project=foreign, name='foreign-source.md')
    viewer = sign_in(client, 'viewer@demo')
    assert overview(client)['role'] == 'viewer'
    assert [d['id'] for d in overview(client)['documents']] == [source['id']]
    assert client.get(f"/api/v1/artifacts/{source['id']}/download").status_code == 200
    assert client.post(f"/api/v1/artifacts/{source['id']}/parse", headers=viewer).status_code == 403
    assert client.post(f'/api/v1/projects/{PROJECT}/artifacts', headers=viewer,
                       files={'file': ('unauthorized.txt', b'no permission', 'text/plain')}).status_code == 403
    for path in (f'/api/v1/projects/{foreign}/learning',
                 f"/api/v1/artifacts/{other_source['id']}/download",
                 f"/api/v1/artifacts/{other_source['id']}/chunks"):
        assert client.get(path).status_code == 404
    assert client.post(f"/api/v1/artifacts/{other_source['id']}/parse", headers=viewer).status_code == 404
    assert overview(client)['preparation_enabled'] is False
