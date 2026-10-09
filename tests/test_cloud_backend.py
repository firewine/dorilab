"""CPU-only transport/storage regressions, using the dedicated test database."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from psycopg.conninfo import conninfo_to_dict

from dorilab import cloud_storage, cloud_worker, config, storage
from dorilab.db import connection
from dorilab.sites_gateway import upstream_origin
from conftest import sign_in

PROJECT = '00000000-0000-4000-8000-000000000001'


@pytest.fixture
def durable(monkeypatch):
    monkeypatch.setenv('DORILAB_ARTIFACT_BACKEND','postgres')
    with connection() as conn,conn.cursor() as cur:
        cur.execute('DELETE FROM cloud_artifact_objects')
    yield
    with connection() as conn,conn.cursor() as cur:
        cur.execute('DELETE FROM cloud_artifact_objects')


def external_file(tmp_path):
    value = dict(host='approved.neon.tech',dbname='neondb',user='runtime',password="has ' spaces \\",
                 sslmode='verify-full',sslrootcert='/etc/ssl/certs/ca-certificates.crt',channel_binding='require')
    path = tmp_path/'db.json'
    path.write_text(json.dumps(value))
    return path,value


def test_external_db_verifies_certificate_and_quotes_password(monkeypatch,tmp_path):
    path,value = external_file(tmp_path)
    monkeypatch.setenv('DORILAB_DB_CONNECTION_FILE',str(path))
    actual = conninfo_to_dict(config.database_url())
    assert all(actual[key] == expected for key,expected in value.items())
    assert actual['connect_timeout'] == '15'


@pytest.mark.parametrize('field,value',[('sslmode','require'),('channel_binding','prefer'),
                                     ('host','bad.neon.tech otherhost'),('user','runtime\noptions=bad'),
                                     ('password',None),('unknown','value')])
def test_external_db_rejects_weakened_or_injected_contract(monkeypatch,tmp_path,field,value):
    path,original = external_file(tmp_path)
    original[field]=value
    path.write_text(json.dumps(original))
    monkeypatch.setenv('DORILAB_DB_CONNECTION_FILE',str(path))
    with pytest.raises(RuntimeError): config.database_url()


def test_local_db_password_quoting_preserved(monkeypatch):
    monkeypatch.delenv('DORILAB_DB_CONNECTION_FILE',raising=False)
    monkeypatch.setenv('DORILAB_DB_PASSWORD',"contains ' slash\\ and space")
    assert conninfo_to_dict(config.database_url())['password'] == "contains ' slash\\ and space"


def test_original_file_and_report_bytes_survive_empty_cache(durable):
    data=b'original \x00\xff bytes\r\n'
    key,size,sha=storage.write_bytes(PROJECT,uuid4(),data)
    local=storage.resolved_path(key)
    local.unlink()
    assert storage.resolved_path(key).read_bytes()==data
    assert size==len(data) and sha==hashlib.sha256(data).hexdigest()
    report_key,_,_=storage.write_export(PROJECT,uuid4(),b'# immutable report\n')
    storage.resolved_export_path(report_key).unlink()
    assert storage.resolved_export_path(report_key).read_bytes()==b'# immutable report\n'


def test_cache_recovery_does_not_accept_corrupt_durable_bytes(durable):
    key,_,_=storage.write_bytes(PROJECT,uuid4(),b'original')
    storage.resolved_path(key).write_bytes(b'bad cache')
    assert storage.resolved_path(key).read_bytes()==b'original'
    with connection() as conn,conn.cursor() as cur:
        cur.execute('UPDATE cloud_artifact_objects SET content=%s WHERE object_key=%s',(b'corrupt!',key))
    with pytest.raises(ValueError,match='integrity'): storage.resolved_path(key)


def test_storage_quota_and_immutable_keys(durable,monkeypatch):
    monkeypatch.setenv('DORILAB_CLOUD_ARTIFACT_LIMIT_BYTES','4')
    cloud_storage.persist('artifacts','same',b'1234')
    cloud_storage.persist('artifacts','same',b'1234')
    with pytest.raises(ValueError,match='immutable'): cloud_storage.persist('artifacts','same',b'4321')
    with pytest.raises(ValueError,match='quota'): cloud_storage.persist('exports','next',b'1')
    with pytest.raises(ValueError,match='object key'): storage.resolved_path('../../outside')


def test_download_still_checks_project_membership_before_storage(durable,client):
    headers=sign_in(client)
    response=client.post(f'/api/v1/projects/{PROJECT}/artifacts',headers=headers,
                         files={'file':('public.txt',b'public synthetic source','text/plain')},
                         data={'rights_status':'PUBLIC','edition':'DEMO-1','adopted':'true','applicability_status':'APPLICABLE'})
    assert response.status_code==201,response.text
    artifact=response.json()
    with connection() as conn,conn.cursor() as cur:
        cur.execute('DELETE FROM memberships WHERE project_id=%s AND user_id=%s',(PROJECT,'engineer@demo'))
    try:
        with patch('dorilab.storage.cloud_storage.materialize') as materialize:
            response=client.get(f"/api/v1/artifacts/{artifact['id']}/download")
            assert response.status_code==404,response.text
            materialize.assert_not_called()
    finally:
        with connection() as conn,conn.cursor() as cur:
            cur.execute("INSERT INTO memberships(project_id,user_id,role) VALUES (%s,%s,'engineer')",(PROJECT,'engineer@demo'))


def test_durable_mode_preserves_original_bm1_and_human_decision(durable,client):
    from test_bm1_flow import test_bytes_hash_review_validation_and_human_decision_are_separate
    test_bytes_hash_review_validation_and_human_decision_are_separate(client)
    with connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT a.object_key,a.sha256 FROM model_runs m JOIN artifact_versions a ON a.id=m.raw_artifact_id")
        raw=cur.fetchone()
    path=storage.resolved_path(raw['object_key'])
    path.unlink()
    assert hashlib.sha256(storage.resolved_path(raw['object_key']).read_bytes()).hexdigest()==raw['sha256']


def test_idle_worker_does_not_poll_database_or_model(tmp_path):
    with patch('dorilab.cloud_worker.worker.recover_orphaned_jobs') as recovery, \
         patch('dorilab.cloud_worker.worker.run_one',return_value=False) as run, \
         patch('dorilab.cloud_worker.queued_work_exists',return_value=False) as pending, \
         patch('dorilab.cloud_worker.time.monotonic',return_value=100):
        driver=cloud_worker.Driver(tmp_path/'wake')
        assert driver.step()
        assert not driver.step()
        assert not driver.step()
        assert recovery.call_count==run.call_count==pending.call_count==1
        driver.marker.touch()
        assert driver.step()
        assert run.call_count==2


def test_deferred_queued_work_revisited_without_marker_change(tmp_path):
    with patch('dorilab.cloud_worker.worker.recover_orphaned_jobs'), \
         patch('dorilab.cloud_worker.worker.run_one',return_value=False) as run, \
         patch('dorilab.cloud_worker.queued_work_exists',side_effect=[True,False]), \
         patch('dorilab.cloud_worker.time.monotonic',side_effect=[100,100,101,103,104]):
        driver=cloud_worker.Driver(tmp_path/'wake')
        assert driver.step()
        assert not driver.step()
        assert driver.step()
        assert not driver.step()
        assert run.call_count==2


@pytest.mark.parametrize('url',['https://outside.example','http://localhost:8000','http://127.0.0.1:22',
                               'http://user:password@127.0.0.1:8001','http://127.0.0.1:8001/path'])
def test_gateway_rejects_nonprivate_target(monkeypatch,url):
    monkeypatch.setenv('DORILAB_API_UPSTREAM',url)
    with pytest.raises(RuntimeError): upstream_origin()


def test_gateway_wakes_only_committed_writes_and_preserves_response(monkeypatch,tmp_path):
    from test_sites_gateway import setup,headers
    client=setup(monkeypatch,tmp_path)
    monkeypatch.setenv('DORILAB_API_UPSTREAM','http://127.0.0.1:8001')
    original=httpx.AsyncClient
    statuses=iter([202,409,200])
    async def serve(request):
        assert request.url.host=='127.0.0.1'
        return httpx.Response(next(statuses),stream=httpx.ByteStream(b'{}'))
    with patch('dorilab.sites_gateway.httpx.AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(serve),**kw)), \
         patch('dorilab.sites_gateway.wake_worker',side_effect=OSError('marker unwritable')) as wake:
        assert client.post('/api/v1/projects/p/reviews',headers=headers(),json={}).status_code==202
        assert client.post('/api/v1/projects/p/reviews',headers=headers(),json={}).status_code==409
        assert client.get('/api/v1/projects',headers=headers()).status_code==200
        assert wake.call_count==1
