import json,os,re,datetime,hashlib
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
out=Path(__file__).parent
entry=json.load(open('/workspace/dorilab/tournament/baseline_v1/DOCTOR.json'))['models']['qwen38_27b']
lock=json.load(open('/workspace/dorilab/tournament/baseline_v1/qwen38_27b/MODEL_LOCK.json'))
assert entry['model']==lock['model'] and entry['revision']==lock['revision']
assert re.fullmatch('[0-9a-f]{40}',entry['revision'])
info=HfApi().model_info(entry['model'],revision=entry['revision']);assert info.sha==entry['revision']
print('Restoring',entry,flush=True)
p=snapshot_download(repo_id=entry['model'],revision=entry['revision'],cache_dir='/root/hf-cache/hub',max_workers=4)
files=[]
for f in sorted(Path(p).rglob('*')):
 if f.is_file():
  h=hashlib.sha256()
  with f.open('rb') as stream:
   for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
  files.append({'path':str(f),'bytes':f.stat().st_size,'sha256':h.hexdigest()})
r={'model':entry['model'],'revision':entry['revision'],'snapshot_path':p,'files':files,'status':'RESTORED_SAME_IMMUTABLE_REVISION','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out/'MODEL_CACHE_RESTORE.json').write_text(json.dumps(r,indent=2));print('RESTORED',p,flush=True)
