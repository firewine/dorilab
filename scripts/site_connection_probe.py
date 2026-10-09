"""Read-only authenticated ingress check; never creates jobs or rotates tokens."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--record',required=True)
    args=parser.parse_args()
    target=urlsplit(args.base_url)
    if target.scheme!='https' or target.username or target.password or target.path not in ('','/') or target.query or target.fragment:
        raise RuntimeError('HTTPS origin required')
    token=Path('/run/secrets/token').read_text().strip()
    identities=json.loads(Path('/run/secrets/identities').read_text())['identities']
    owner=next(iter(identities))
    headers={'Authorization':'Bearer '+token,'X-DoriLab-Site-User':owner,'X-DoriLab-Legacy-Actor':'engineer@demo'}
    with httpx.Client(base_url=args.base_url,timeout=30,follow_redirects=False) as client:
        health=client.get('/healthz')
        assert health.status_code==200
        assert client.get('/api/v1/projects').status_code==401
        assert client.get('/api/v1/projects',headers={**headers,'X-DoriLab-Site-User':'unmapped'}).status_code==403
        response=client.get('/api/v1/projects',headers=headers)
        assert response.status_code==200
        projects=response.json()
        project='00000000-0000-4000-8000-000000000001'
        assert any(p['id']==project for p in projects)
        jobs=client.get('/api/v1/projects/'+project+'/jobs',headers=headers)
        assert jobs.status_code==200
        jobs=jobs.json()
        # The list endpoint exposes validation_status, not model_run_id.
        sample=next((j for j in jobs if j.get('validation_status')),None)
        checked=None
        if sample:
            detail=client.get('/api/v1/jobs/'+sample['id'],headers=headers)
            assert detail.status_code==200
            run=detail.json()['model_run']
            assert run is not None
            raw=client.get('/api/v1/artifacts/'+run['raw_artifact_id']+'/download',headers=headers)
            assert raw.status_code==200
            assert hashlib.sha256(raw.content).hexdigest()==run['raw_sha256']
            checked={'sha256':run['raw_sha256'],'bytes':len(raw.content)}
    value=dict(passed=True,read_only=True,live_model_calls=0,authenticated_projects=len(projects),
               historical_project_jobs=len(jobs),raw_sample=checked,anonymous=401,unmapped_user=403)
    record=Path(args.record)
    record.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value))


if __name__=='__main__':
    try: main()
    except Exception as error:
        print('CONNECTION_CHECK_FAILED: '+type(error).__name__)
        raise SystemExit(1)
