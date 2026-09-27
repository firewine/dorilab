"""Restore only missing locked API dependencies; refuse changing installed packages."""
import importlib.metadata as m
import json
from pathlib import Path
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent
out=HERE/'artifacts'/('restore-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
out.mkdir(parents=True,exist_ok=True)
def snapshot(name):
 r=subprocess.run([sys.executable,'-m','pip','list','--format=json'],capture_output=True,text=True,check=True)
 (out/name).write_text(r.stdout)
 return {x['name'].lower().replace('_','-'):x['version'] for x in json.loads(r.stdout)}
before=snapshot('before.json');missing=[]
for line in (HERE/'requirements-api.lock').read_text().splitlines():
 name,version=line.split('==')
 try: actual=m.version(name)
 except m.PackageNotFoundError: missing.append(line);continue
 if actual!=version: raise SystemExit(f'installed API dependency differs from lock: {name}; refusing upgrade')
if missing:
 with (out/'install.log').open('w') as log:
  subprocess.run([sys.executable,'-m','pip','install','--no-deps',*missing],stdout=log,stderr=subprocess.STDOUT,check=True)
after=snapshot('after.json')
assert all(after[k]==v for k,v in before.items()), 'existing runtime packages changed'
(out/'diff.json').write_text(json.dumps({k:v for k,v in after.items() if k not in before},indent=2))
r=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
(out/'pip-check.txt').write_text(r.stdout+r.stderr)
if r.returncode: raise SystemExit('pip check failed; see restore artifact')
print('API lock verified; existing packages unchanged; pip check passed')
