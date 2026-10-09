"""Transport checks only; existing business logic remains in the original API."""
import json
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from dorilab.sites_gateway import app


def setup(monkeypatch, tmp_path):
    token = tmp_path / 'token'
    token.write_text('test-server-secret')
    identities = tmp_path / 'identities.json'
    identities.write_text(json.dumps({'backend_location':'MAC','identities':{'owner':['engineer@demo','reviewer@demo','approver@demo']}}))
    monkeypatch.setenv('DORILAB_SITES_TOKEN_FILE', str(token))
    monkeypatch.setenv('DORILAB_SITES_IDENTITIES_FILE', str(identities))
    monkeypatch.setenv('DORILAB_SESSION_SECRET', 'test-session-secret')
    return TestClient(app)


def headers(owner='owner', actor='engineer@demo'):
    return {'Authorization':'Bearer test-server-secret','X-DoriLab-Site-User':owner,'X-DoriLab-Legacy-Actor':actor}


def test_gateway_anonymous_and_other_users_cannot_call_api(monkeypatch,tmp_path):
    client=setup(monkeypatch,tmp_path)
    with patch('httpx.AsyncClient') as upstream:
        assert client.get('/api/v1/projects').status_code == 401
        assert client.get('/api/v1/projects',headers=headers('other')).status_code == 403
        assert client.get('/api/v1/projects',headers=headers(actor='admin@arbitrary')).status_code == 403
        upstream.assert_not_called()


def test_session_only_uses_explicitly_mapped_roles(monkeypatch,tmp_path):
    client=setup(monkeypatch,tmp_path)
    response=client.post('/api/v1/session',json={'user_id':'reviewer@demo'},headers=headers())
    assert response.status_code == 200
    assert response.json()['user']['id'] == 'reviewer@demo'
    assert 'set-cookie' not in response.headers
    assert client.post('/api/v1/session',json={'user_id':'not-mapped'},headers=headers()).status_code == 403
    assert client.post('/api/v1/session',content='bad-json',headers=headers()).status_code == 422


def test_existing_bytes_identity_and_idempotency_are_preserved(monkeypatch,tmp_path):
    client=setup(monkeypatch,tmp_path)
    import httpx
    source=b'\x00\xff\x80original bytes\r\n'
    async def serve(request):
        assert request.url == 'http://api:8000/api/v1/projects/id/artifacts'
        assert await request.aread() == source
        assert request.headers['idempotency-key'] == 'original-key'
        assert 'Bearer' not in request.headers.get('authorization','')
        from dorilab.auth import parse_session
        assert parse_session(request.headers['cookie'].split('=',1)[1]) == 'engineer@demo'
        return httpx.Response(201,stream=httpx.ByteStream(source),headers={'set-cookie':'secret=not-forwarded','content-type':'application/octet-stream'})
    original_client=httpx.AsyncClient
    with patch('dorilab.sites_gateway.httpx.AsyncClient',side_effect=lambda **kw:original_client(transport=httpx.MockTransport(serve),**kw)):
        response=client.post('/api/v1/projects/id/artifacts',content=source,headers={**headers(),'Idempotency-Key':'original-key'})
    assert response.status_code == 201
    assert response.content == source
    assert 'set-cookie' not in response.headers


def test_api_unreachable_is_not_mock_success_or_retry(monkeypatch,tmp_path):
    client=setup(monkeypatch,tmp_path)
    import httpx
    original_client=httpx.AsyncClient
    calls=[]
    async def unavailable(request):
        calls.append(request)
        raise httpx.ConnectError('offline')
    with patch('dorilab.sites_gateway.httpx.AsyncClient',side_effect=lambda **kw:original_client(transport=httpx.MockTransport(unavailable),**kw)):
        response=client.post('/api/v1/projects/id/reviews',json={'test':'input'},headers=headers())
    assert response.status_code == 503
    assert response.json()['detail']=='LEGACY_BACKEND_UNREACHABLE'
    assert len(calls)==1
