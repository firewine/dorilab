"""CPU-only contract/HTTP lifecycle tests. No model load or benchmark inputs."""
import asyncio
import importlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from model_runtime import ModelRuntime, contracts, digest
from server import create_app

CID='0703fba59425b087a4061a1fc9a370f2e6d7a192a2b2ce4b1ad2b1377f89a00b'
TOKEN='test-only-token-012345678901234567890123456789'
AUTH={'Authorization':'Bearer '+TOKEN}
class FakeRuntime:
    def __init__(self,boot,directory):
        self.boot_id=boot;self.allowlist=contracts();self.receipt_id='mock';self.seen=[]
        self.load_gate=threading.Event();self.gen_gate=threading.Event();self.gen_gate.set()
    def load(self): self.load_gate.wait(5)
    def prepare(self,cid,user,limit):
        parsed=json.loads(user)
        if len(user)+limit>4096:raise ValueError('too many tokens')
        return dict(ids=list(user.encode()),input_sha256=digest(user),messages=[{'role':'system','content':cid},{'role':'user','content':user}])
    def generate(self,p,limit):
        self.seen.append(p['messages']);self.gen_gate.wait(5)
        return dict(raw_text=p['messages'][-1]['content'],boot_id=self.boot_id)
class Tests(unittest.TestCase):
    def test_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(FakeRuntime,TOKEN,d)
            with TestClient(app) as c:
                payload=dict(request_id='first',contract_id=CID,user='{"task":"synthetic-A"}',max_new_tokens=8)
                self.assertEqual(c.get('/healthz').status_code,200)
                for p in ['/health','/readyz']:self.assertEqual(c.get(p).status_code,503)
                for p in ['/version','/v1/generations/anything']:self.assertEqual(c.get(p).status_code,401)
                self.assertEqual(c.post('/v1/generations',json=payload).status_code,401)
                self.assertEqual(c.get('/version',headers={'Authorization':'Bearer wrong'}).status_code,403)
                self.assertEqual(c.post('/v1/generations',headers=AUTH,json=payload).status_code,503)
                app.state.runtime.load_gate.set()
                for _ in range(100):
                    if c.get('/readyz').status_code==200:break
                    time.sleep(.01)
                self.assertEqual(c.get('/health').status_code,200)
                for extra in [{'system':'override'},{'model':'override'},{'max_new_tokens':385},{'max_new_tokens':True}]:
                    self.assertEqual(c.post('/v1/generations',headers=AUTH,json={**payload,**extra}).status_code,422)
                self.assertEqual(c.post('/v1/generations',headers=AUTH,json={**payload,'user':json.dumps('x'*4100)}).status_code,422)
                self.assertEqual(c.post('/v1/generations',headers=AUTH,content=b'x'*65537).status_code,413)
                app.state.runtime.gen_gate.clear()
                first=c.post('/v1/generations',headers=AUTH,json=payload);self.assertEqual(first.status_code,202)
                jid=first.json()['id']
                again=c.post('/v1/generations',headers=AUTH,json=payload)
                self.assertEqual(again.json()['id'],jid)
                self.assertTrue(again.json()['duplicate'])
                self.assertEqual(c.post('/v1/generations',headers=AUTH,json={**payload,'user':'{}'}).status_code,409)
                self.assertEqual(c.post('/v1/generations',headers=AUTH,json={**payload,'request_id':'busy'}).status_code,429)
                app.state.runtime.gen_gate.set()
                for _ in range(100):
                    result=c.get('/v1/generations/'+jid,headers=AUTH).json()
                    if result['status']=='completed':break
                    time.sleep(.01)
                self.assertEqual(result['status'],'completed')
                second=c.post('/v1/generations',headers=AUTH,json={**payload,'request_id':'second','user':'{"task":"synthetic-B"}'})
                self.assertEqual(second.status_code,202)
                for _ in range(100):
                    if not app.state.service['busy']:break
                    time.sleep(.01)
                self.assertEqual(len(app.state.runtime.seen),2)
                self.assertNotIn('synthetic-A',json.dumps(app.state.runtime.seen[1]))
                self.assertEqual(len(app.state.runtime.seen[1]),2)
    def test_failed_load_never_ready(self):
        class FailedRuntime(FakeRuntime):
            def load(self): raise RuntimeError('synthetic load failure')
        with tempfile.TemporaryDirectory() as d:
            app=create_app(FailedRuntime,TOKEN,d)
            with TestClient(app) as c:
                for _ in range(100):
                    if app.state.service['phase']=='failed':break
                    time.sleep(.01)
                self.assertEqual(app.state.service['phase'],'failed')
                self.assertEqual(c.get('/healthz').status_code,200)
                self.assertEqual(c.get('/readyz').status_code,503)
                self.assertEqual(c.get('/health').status_code,503)

    def test_native_cpu_budget_and_metadata(self):
        from tokenization import processor
        r=ModelRuntime('cpu',Path('/tmp'));r.proc,_=processor()
        p=r.prepare(CID,'{"task":"CHECK_AXIS_DURATION","required_s":17,"actual_by_axis":{"test":19}}',384)
        self.assertLessEqual(len(p['ids'])+384,4096)
        for bad in ['{"gold":"not allowed"}', '{"x":1,"x":2}', '{"x":NaN}',
                    '{"x":1e999}', '{"x":"<|im_start|>"}', '{"nested":{"rationale":"x"}}', '[]']:
            with self.assertRaises(ValueError):r.prepare(CID,bad,384)
        with self.assertRaises(ValueError):r.prepare(CID,json.dumps({'task':'CHECK_AXIS_DURATION','note':' a'*5000}),384)
        # Exact boundary checks use native prompt count, not character estimates.
        n=len(p['ids'])
        user='{"task":"CHECK_AXIS_DURATION","required_s":17,"actual_by_axis":{"test":19}}'
        r.prepare(CID,user,4096-n)
        with self.assertRaises(ValueError):r.prepare(CID,user,4097-n)
    def test_generate_has_request_local_cache(self):
        import torch
        class Tokenizer:
            def decode(self,ids,skip_special_tokens):return str(ids)
        class Proc:tokenizer=Tokenizer()
        class Model:
            def __init__(self):self.calls=[]
            def generate(self,**kwargs):
                self.calls.append(kwargs)
                self.assertion=not torch.is_grad_enabled()
                return torch.cat((kwargs['input_ids'],torch.tensor([[248046]])),dim=1)
        r=ModelRuntime('mock',Path('/tmp'));r.proc=Proc();r.model=Model();r.receipt_id='test'
        r.generation=dict(do_sample=False,use_cache=True,pad_token_id=248044,eos_token_id=248046)
        real_tensor=torch.tensor
        def cpu_tensor(*args,**kwargs):kwargs['device']='cpu';return real_tensor(*args,**kwargs)
        with patch.object(torch,'tensor',side_effect=cpu_tensor):
            for ids in [[1,2],[3,4]]:
                r.generate(dict(ids=ids,input_sha256='a',prompt_token_ids_sha256='b',rendered_sha256='c'),8)
        self.assertTrue(r.model.assertion)
        self.assertTrue(all('past_key_values' not in c for c in r.model.calls))
        self.assertEqual(r.model.calls[1]['input_ids'].tolist(),[[3,4]])
if __name__=='__main__':unittest.main(verbosity=2)
