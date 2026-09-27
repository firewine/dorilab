"""One process, one resident model, one admitted generation, no waiting queue."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import json
import logging
import os
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from model_runtime import HERE, ModelRuntime, atomic_json, digest

CONFIG = json.loads((HERE / 'service_config.json').read_text())

class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z0-9_.-]+$')
    contract_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    user: str = Field(min_length=2, max_length=60000)
    max_new_tokens: int = Field(default=384, ge=1, le=384)

class BodyLimit:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Bound bytes even for chunked requests, before JSON parsing.
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            size += len(message.get('body', b''))
            if size > CONFIG['max_body_bytes']:
                return await JSONResponse({'detail':'request body too large'}, status_code=413)(scope, receive, send)
            chunks.append(message)
            if not message.get('more_body', False): break
        async def replay():
            if chunks: return chunks.pop(0)
            return await receive()
        await self.app(scope, replay, send)

def create_app(runtime_factory=ModelRuntime, token=None, run_root=None):
    boot_id = str(uuid.uuid4())
    directory = Path(run_root or HERE / 'run') / boot_id
    directory.mkdir(parents=True, exist_ok=True)
    service_token = token if token is not None else Path(CONFIG['token_file']).read_text().strip()
    if len(service_token) < 32: raise RuntimeError('invalid service token file')
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='rc3-gpu')
    jobs, keys = {}, {}
    state = dict(ready=False, busy=False, phase='loading', boot_id=boot_id)
    runtime = runtime_factory(boot_id, directory)
    async def initialize():
        try:
            await asyncio.get_running_loop().run_in_executor(executor, runtime.load)
            state.update(ready=True, phase='ready')
        except Exception:
            state.update(ready=False, phase='failed')
            logging.exception('model startup failed')
    @asynccontextmanager
    async def lifespan(app):
        init = asyncio.create_task(initialize())
        yield
        state.update(ready=False, phase='stopping')
        await init
        executor.shutdown(wait=True)
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)
    app.state.runtime, app.state.service = runtime, state
    app.state.jobs = jobs
    async def authenticated(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate':'Bearer'})
        if not hmac.compare_digest(authorization[7:].encode(), service_token.encode()):
            raise HTTPException(403, 'invalid service token')
    @app.get('/healthz')
    async def live():
        return {'status':'alive'}
    @app.get('/health')
    @app.get('/readyz')
    async def ready():
        return JSONResponse({'status':'ready' if state['ready'] else 'not_ready'},
                            status_code=200 if state['ready'] else 503)
    @app.get('/version', dependencies=[Depends(authenticated)])
    async def version():
        return dict(service='DoriLab RC3', boot_id=boot_id, pid=os.getpid(),
            ready=state['ready'], phase=state['phase'], busy=state['busy'],
            model_receipt_id=getattr(runtime, 'receipt_id', None),
            contracts=[{k:r[k] for k in ('id','route','system_sha256')} for r in runtime.allowlist.values()],
            limits={k:CONFIG[k] for k in ('max_total_tokens','max_new_tokens','max_retained_jobs','result_ttl_seconds')})
    def expire():
        for jid, job in list(jobs.items()):
            if job['status'] in ('completed','failed') and time.time()-job['created_at'] > CONFIG['result_ttl_seconds']:
                keys.pop(job['request_id'], None); jobs.pop(jid)
        # Retained disk artifacts are immutable evidence; bounded admission limits each boot.
    async def execute(jid, prepared, limit):
        job = jobs[jid]
        try:
            output = await asyncio.get_running_loop().run_in_executor(executor, runtime.generate, prepared, limit)
            result = dict(id=jid, request_id=job['request_id'], status='completed', **output)
            atomic_json(directory / (jid+'.json'), result)
            job.update(status='completed', result=result)
        except Exception:
            logging.exception('generation failed id=%s', jid)
            job.update(status='failed', error='generation_failed')
            atomic_json(directory / (jid+'.json'), {k:v for k,v in job.items() if k!='fingerprint'})
            # CUDA errors can poison context. Fail readiness; no automatic model reload.
            state.update(ready=False, phase='failed')
        finally:
            state['busy'] = False
    @app.post('/v1/generations', dependencies=[Depends(authenticated)], status_code=202)
    async def submit(body: GenerationRequest):
        if not state['ready']: raise HTTPException(503, 'model not ready')
        if body.contract_id not in runtime.allowlist: raise HTTPException(422, 'unknown contract_id')
        fingerprint = digest(body.model_dump())
        expire()
        old = keys.get(body.request_id)
        if old:
            if jobs[old]['fingerprint'] != fingerprint: raise HTTPException(409, 'request_id already used with different input')
            return JSONResponse({'id':old,'status':jobs[old]['status'],'boot_id':boot_id,'duplicate':True},
                                status_code=202, headers={'Location':'/v1/generations/'+old})
        if state['busy']: raise HTTPException(429, 'generation busy; no queue', headers={'Retry-After':'1'})
        if len(jobs) >= CONFIG['max_retained_jobs'] or state.get('accepted',0) >= CONFIG['max_retained_jobs']:
            raise HTTPException(429, 'boot job capacity reached; operator restart required')
        state['busy'] = True
        try:
            prepared = await asyncio.get_running_loop().run_in_executor(executor, runtime.prepare,
                                body.contract_id, body.user, body.max_new_tokens)
        except (ValueError, KeyError, AssertionError, RuntimeError) as error:
            state['busy'] = False
            raise HTTPException(422, 'invalid native input or input/output token budget exceeded') from error
        except BaseException:
            state['busy'] = False
            raise
        jid = str(uuid.uuid4())
        job = dict(id=jid, request_id=body.request_id, status='running', created_at=time.time(),
                   fingerprint=fingerprint, boot_id=boot_id)
        try:
            atomic_json(directory / (jid+'.input.json'), dict(request=body.model_dump(),
                input_sha256=prepared['input_sha256'], prompt_token_ids=prepared['ids'], boot_id=boot_id))
        except Exception:
            state['busy'] = False
            raise
        jobs[jid], keys[body.request_id] = job, jid
        state['accepted'] = state.get('accepted',0)+1
        task = asyncio.create_task(execute(jid, prepared, body.max_new_tokens))
        # Retain tasks until done even if client disconnects.
        app.state.tasks.add(task); task.add_done_callback(app.state.tasks.discard)
        return JSONResponse({'id':jid,'status':'running','boot_id':boot_id,'duplicate':False},
                            status_code=202, headers={'Location':'/v1/generations/'+jid})
    @app.get('/v1/generations/{jid}', dependencies=[Depends(authenticated)])
    async def result(jid: str):
        expire()
        if jid not in jobs: raise HTTPException(404, 'unknown or expired job in this boot')
        job = jobs[jid]
        return job.get('result') or {k:v for k,v in job.items() if k!='fingerprint'}
    app.state.tasks = set()
    atomic_json(directory / 'boot.json', dict(boot_id=boot_id, pid=os.getpid(), listen='127.0.0.1:8080'))
    return app

if __name__ == '__main__':
    import uvicorn
    os.umask(0o077)
    uvicorn.run(create_app(), host='127.0.0.1', port=8080, workers=1,
                access_log=False, timeout_keep_alive=5, limit_concurrency=32)
