"""Exercise the deployed CPU service over HTTP with approved synthetic data.

All bearer values are read privately from files. No test fixture truncation,
model requests, migration, or business history replacement is performed here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx
from db_transfer import save


def main():
    args=argparse.ArgumentParser()
    args.add_argument('action',choices=['create','verify'])
    args.add_argument('--base-url',default='http://backend:8000')
    value=args.parse_args()
    mapping=json.loads(Path('/run/secrets/sites_identities.json').read_text())
    identity=next(iter(mapping['identities']))
    token=Path('/run/secrets/sites_gateway_token').read_text().strip()
    headers={'Authorization':'Bearer '+token,'X-DoriLab-Site-User':identity,
             'X-DoriLab-Legacy-Actor':'engineer@demo'}
    receipt=Path('/records/cloud-flow.json')
    with httpx.Client(base_url=value.base_url,headers=headers,timeout=60) as client:
        def call(method,path,expected=200,**kwargs):
            response=client.request(method,'/api/v1/'+path,**kwargs)
            if response.status_code != expected:
                raise RuntimeError('unexpected HTTP status '+str(response.status_code)+' at '+path)
            return response
        assert httpx.get(value.base_url+'/api/v1/projects').status_code==401
        assert client.get('/api/v1/projects',headers={'X-DoriLab-Site-User':'unmapped'}).status_code==403
        projects=call('GET','projects').json()
        assert len(projects)>=1  # API returns only projects of the mapped actor
        baseline=call('GET','projects/00000000-0000-4000-8000-000000000001').json()
        assert baseline['display_id']=='DORI-01'
        if value.action=='create':
            if receipt.exists(): raise RuntimeError('existing test receipt preserved; use verify')
            project=call('POST','projects',201,json={'display_id':'CLOUD-'+uuid4().hex[:10],
                         'name':'외부 CPU 서버 연결 합성 시험','framework':'KASA','data_policy':'EXTERNAL_SYNTHETIC_ALLOWED','mode':'DEMO'}).json()
            project_id=project['id']
            claim=call('POST',f'projects/{project_id}/claims',201,json={'display_id':'CLOUD-BM1',
                      'question':'합성 입력 검토에 필요한 근거가 준비되었는가?', 'scope':{},'review_purpose':'INPUT_READINESS'}).json()
            data=b'Public synthetic reference for CPU cloud storage verification.\n'
            artifact=call('POST',f'projects/{project_id}/artifacts',201,
                          data={'rights_status':'PUBLIC','edition':'DEMO-1','adopted':'true','applicability_status':'APPLICABLE'},
                          files={'file':('cloud-smoke.txt',data,'text/plain')}).json()
            key=uuid4().hex
            packet={'claim_id':claim['id'],'evidence_ids':[],'mode':'SIMULATED'}
            job=call('POST',f'projects/{project_id}/reviews',202,headers={'Idempotency-Key':key},json=packet).json()
            repeat=call('POST',f'projects/{project_id}/reviews',202,headers={'Idempotency-Key':key},json=packet).json()
            assert repeat['job_id']==job['job_id'] and repeat['idempotent_replay']
            call('POST',f'projects/{project_id}/reviews',409,headers={'Idempotency-Key':key},json={**packet,'mode':'REPLAY'})
            for _ in range(60):
                result=call('GET','jobs/'+job['job_id']).json()
                if result['job']['status']=='AWAITING_REVIEW': break
                if result['job']['status']=='FAILED': raise RuntimeError('synthetic worker failed')
                time.sleep(1)
            else: raise RuntimeError('synthetic worker did not complete')
            assert result['model_run']['receipt']['execution_mode']=='SIMULATED'
            assert result['model_run']['validation_status']=='VALID'
            decision=call('POST',f"reviews/{job['job_id']}/decisions",201,json={'disposition':'REVISION_REQUESTED',
                          'expected_job_version':result['job']['version'],'edited_draft':{'reviewer_text':'합성 연결 시험의 사람 수정본'},
                          'note':'서버 연결 검증이며 공식 공학 승인 아님'}).json()
            save(receipt,dict(project_id=project_id,job_id=job['job_id'],artifact_id=artifact['id'],
                              artifact_sha256=hashlib.sha256(data).hexdigest(),raw_artifact_id=result['model_run']['raw_artifact_id'],
                              raw_sha256=result['model_run']['raw_sha256'],decision_id=decision['id'],
                              mode='SIMULATED',live_model_calls=0,passed=True))
        recorded=json.loads(receipt.read_text())
        result=call('GET','jobs/'+recorded['job_id']).json()
        assert result['job']['status']=='COMPLETED'
        assert any(d['id']==recorded['decision_id'] for d in result['decisions'])
        assert result['model_run']['raw_sha256']==recorded['raw_sha256']
        for field,hash_field in [('artifact_id','artifact_sha256'),('raw_artifact_id','raw_sha256')]:
            original=call('GET',f"artifacts/{recorded[field]}/download").content
            assert hashlib.sha256(original).hexdigest()==recorded[hash_field]
        # Runtime DB account must not create schema objects or truncate data.
        from dorilab.db import connection
        with connection() as conn,conn.cursor() as cur:
            cur.execute("SELECT has_schema_privilege(current_user,'public','CREATE') AS ddl,has_table_privilege(current_user,'review_jobs','TRUNCATE') AS destructive")
            permissions=cur.fetchone()
            assert not permissions['ddl'] and not permissions['destructive']
        save(Path('/records')/('cloud-'+value.action+'-result.json'),dict(passed=True,mode='SIMULATED',live_calls=0,
                            authentication_enforced=True,runtime_ddl_allowed=False,artifact_hashes_match=True,
                            human_decision_preserved=True,project_id=recorded['project_id']))
        print('CLOUD_'+value.action.upper()+'_PASSED: original API + worker + Neon + durable bytes')


if __name__=='__main__':
    try: main()
    except Exception as error:
        import traceback
        line=traceback.extract_tb(error.__traceback__)[-1].lineno
        print('CLOUD_PROBE_FAILED: '+type(error).__name__+' at line '+str(line))
        if isinstance(error,RuntimeError): print(str(error))
        raise SystemExit(1)
