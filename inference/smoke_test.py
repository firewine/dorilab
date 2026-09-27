"""Exactly one synthetic authenticated HTTP generation; never an accuracy evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

HERE=Path(__file__).resolve().parent
CID='0703fba59425b087a4061a1fc9a370f2e6d7a192a2b2ce4b1ad2b1377f89a00b'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--timeout',type=int,default=900);a=parser.parse_args()
    token=Path('/root/.config/dorilab/inference.token').read_text().strip()
    out=HERE/'artifacts'/('http-smoke-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    out.mkdir(exist_ok=False)
    def call(path,body=None,auth=True):
        headers={'Authorization':'Bearer '+token} if auth else {}
        raw=None
        if body is not None:
            raw=json.dumps(body,ensure_ascii=False).encode();headers['Content-Type']='application/json'
        req=urllib.request.Request('http://127.0.0.1:8080'+path,data=raw,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    deadline=time.monotonic()+a.timeout
    observations=[]
    while True:
        status,raw=call('/readyz',auth=False)
        if status==200:break
        if time.monotonic()>deadline:raise RuntimeError('readiness timeout; no generation sent')
        time.sleep(2)
    for path in ['/healthz','/readyz','/health']:
        status,raw=call(path,auth=False);assert status==200
        observations.append(dict(path=path,status=status,body=json.loads(raw)))
    for path in ['/version','/v1/generations/unknown']:
        status,_=call(path,auth=False);assert status==401
        observations.append(dict(path=path,authenticated=False,status=status))
    status,raw=call('/version');assert status==200;version=json.loads(raw)
    (out/'version.json').write_bytes(raw)
    request=dict(request_id='synthetic-smoke-'+uuid.uuid4().hex,contract_id=CID,
        user=json.dumps({'task':'CHECK_AXIS_DURATION','required_s':17,'actual_by_axis':{'synthetic_x':19,'synthetic_y':13}},separators=(',',':')),
        max_new_tokens=384)
    (out/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    start=time.monotonic();status,raw=call('/v1/generations',request)
    (out/'accepted.json').write_bytes(raw);assert status==202
    accepted=json.loads(raw);jid=accepted['id'];polls=[]
    while True:
        status,raw=call('/v1/generations/'+jid);assert status==200
        result=json.loads(raw);polls.append(dict(elapsed_seconds=time.monotonic()-start,status=result['status']))
        if result['status'] in ('completed','failed'):break
        if time.monotonic()>deadline:raise RuntimeError('job timeout; no resubmission')
        time.sleep(.5)
    (out/'polls.json').write_text(json.dumps(polls,indent=2))
    (out/'result.http.json').write_bytes(raw)
    assert result['status']=='completed', 'model generation failed; no retry'
    assert result['boot_id']==version['boot_id']
    (out/'raw_output.txt').write_text(result['raw_text'])
    (out/'decoded_output.txt').write_text(result['text'])
    assert hashlib.sha256(result['raw_text'].encode()).hexdigest()==result['output_sha256']
    receipt=HERE/'run'/version['boot_id']/'model_receipt.json'
    (out/'model_receipt.json').write_bytes(receipt.read_bytes())
    report=dict(purpose='HTTP technical smoke only; no engineering accuracy/generalization score',
        accepted_http_status=202,completed=True,job_id=jid,boot_id=version['boot_id'],
        http_elapsed_seconds=time.monotonic()-start,observations=observations,
        input_provenance='new synthetic input; no gold, rationale, reference answers',
        output_repaired=False,output_sha256=result['output_sha256'])
    (out/'SMOKE_RECEIPT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(directory=str(out),**report),ensure_ascii=False))
if __name__=='__main__':main()
