"""Authenticated HTTPS ingress to the existing API, with explicit identity mapping.

No business rules are implemented here. The local API remains private and owns
membership, versions, validation, approvals, raw bytes, and audit history.
"""
from __future__ import annotations
import hmac
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from .auth import COOKIE_NAME, issue_session

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
MAX_BODY = 24 * 1024 * 1024  # preserve the original 20 MiB file limit plus multipart metadata


def upstream_origin():
    value = os.getenv('DORILAB_API_UPSTREAM', 'http://api:8000').rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'api','127.0.0.1'}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or parsed.port not in {8000,8001}):
        raise RuntimeError('invalid private API upstream')
    return value


def wake_worker():
    path = os.getenv('DORILAB_WORKER_WAKE_FILE')
    if path:
        marker = Path(path)
        marker.parent.mkdir(parents=True,exist_ok=True)
        marker.touch(mode=0o600,exist_ok=True)


def config():
    token = Path(os.environ['DORILAB_SITES_TOKEN_FILE']).read_text().strip()
    mapping = json.loads(Path(os.environ['DORILAB_SITES_IDENTITIES_FILE']).read_text())
    return token, mapping


def fail(detail, code):
    return JSONResponse({'detail': detail}, status_code=code, headers={'Cache-Control': 'no-store'})


@app.get('/healthz')
def health():
    return {'status': 'gateway_alive'}


@app.api_route('/api/v1/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE'])
async def relay(path: str, request: Request):
    token, mapping = config()
    if not token or not hmac.compare_digest(request.headers.get('authorization', '').encode(), ('Bearer ' + token).encode()):
        return fail('AUTHENTICATION_REQUIRED', 401)
    identity = request.headers.get('x-dorilab-site-user', '')
    allowed = mapping.get('identities', {}).get(identity, [])
    actor = request.headers.get('x-dorilab-legacy-actor', '')
    if not allowed or actor not in allowed:
        return fail('LEGACY_ACCESS_NOT_GRANTED', 403)
    if '..' in path or '\\' in path or '%' in path:
        return fail('NOT_FOUND', 404)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            return fail('REQUEST_TOO_LARGE', 413)
    if path == 'session':
        if request.method == 'POST':
            try:
                value = json.loads(body)
                selected = value['user_id']
                if set(value) != {'user_id'} or selected not in allowed:
                    return fail('LEGACY_ROLE_NOT_GRANTED', 403)
            except (ValueError, KeyError, TypeError):
                return fail('INVALID_REQUEST', 422)
        elif request.method == 'GET':
            selected = actor
        else:
            return fail('METHOD_NOT_ALLOWED', 405)
        return JSONResponse({'user': {'id': selected}, 'auth_mode': 'SITES_MAPPED_IDENTITY',
                             'allowed_actors': allowed, 'backend_location': mapping.get('backend_location', 'SERVER')},
                            headers={'Cache-Control': 'no-store'})
    headers = {'Cookie': f'{COOKIE_NAME}={issue_session(actor)}', 'X-DoriLab-CSRF': '1'}
    for name in ['content-type', 'idempotency-key', 'range', 'accept']:
        if name in request.headers:
            headers[name] = request.headers[name]
    # Never forward the visitor's cookies, authorization, or other identity headers.
    target = upstream_origin() + '/api/v1/' + path
    if request.url.query:
        target += '?' + request.url.query
    client = httpx.AsyncClient(timeout=60, follow_redirects=False)
    try:
        upstream = await client.send(client.build_request(request.method, target, headers=headers, content=bytes(body)), stream=True)
    except httpx.HTTPError:
        await client.aclose()
        return fail('LEGACY_BACKEND_UNREACHABLE', 503)
    if 300 <= upstream.status_code < 400:
        await upstream.aclose()
        await client.aclose()
        return fail('LEGACY_REDIRECT_BLOCKED', 502)
    if request.method in {'POST','PUT','DELETE'} and upstream.status_code < 400:
        # Signal only after the API has committed and admitted the operation.
        # This is not a new generation or an automatic retry.
        try:
            wake_worker()
        except OSError:
            # Preserve the already committed response. Do not encourage a new
            # submission when only the observation/wake file failed.
            print('CLOUD_WORKER_WAKE_FAILED',flush=True)

    async def stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()
    response_headers = {'Cache-Control': 'no-store'}
    for name in ['content-type', 'content-disposition', 'content-length', 'content-range', 'accept-ranges']:
        if name in upstream.headers:
            response_headers[name] = upstream.headers[name]
    return StreamingResponse(stream(), status_code=upstream.status_code, headers=response_headers)
