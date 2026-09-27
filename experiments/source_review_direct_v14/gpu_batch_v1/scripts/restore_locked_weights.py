"""Restore explicit fixed-revision model files only, verifying every size and historical SHA256."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime,hashlib,json,os,shutil,traceback,urllib.request
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parents[2]
HIST=WORK/'results/source_review_v13_qwen27/cpu_source_audit/MODEL_CACHE_RESTORE.json'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
 return h.hexdigest()
def put(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def main():
 old=json.loads(HIST.read_text());model='Qwen/Qwen3.8-27B';revision='1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
 assert old['model']==model and old['revision']==revision
 small={'config.json','generation_config.json','model.safetensors.index.json','tokenizer_config.json','tokenizer.json','vocab.json','merges.txt','chat_template.jinja','preprocessor_config.json','video_preprocessor_config.json'}
 names=small|{f'model-{i:05d}-of-00018.safetensors' for i in range(1,19)}
 entries={Path(x['path']).name:x for x in old['files'] if Path(x['path']).name in names}
 assert set(entries)==names
 dest=Path('/root/hf-cache/hub/models--Qwen--Qwen3.8-27B/snapshots')/revision;dest.mkdir(parents=True,exist_ok=True)
 required=sum(x['bytes'] for x in entries.values() if not (dest/Path(x['path']).name).exists());free=shutil.disk_usage(dest).free
 put(ROOT/'audit/RESTORE_PREFLIGHT.json',{'model':model,'revision':revision,'required_download_bytes':required,'free_bytes':free,'reserve_bytes':8*1024**3,'snapshot_path':str(dest),'files':{k:{'bytes':v['bytes'],'sha256':v['sha256']} for k,v in entries.items()}})
 if free<required+8*1024**3:raise RuntimeError('insufficient disk; do not delete prior data')
 def fetch(name):
  expected=entries[name];path=dest/name
  if path.exists():
   if path.stat().st_size!=expected['bytes'] or sha(path)!=expected['sha256']:raise ValueError('existing file mismatch: '+name)
   return {'file':name,'bytes':expected['bytes'],'sha256':expected['sha256'],'source':'existing verified file'}
  url=f'https://huggingface.co/{model}/resolve/{revision}/{name}'
  part=dest/(name+'.part');h=hashlib.sha256();size=0
  with urllib.request.urlopen(url,timeout=90) as response,part.open('xb') as output:
   while True:
    chunk=response.read(8*1024**2)
    if not chunk:break
    size+=len(chunk)
    if size>expected['bytes']:raise ValueError('oversized file: '+name)
    output.write(chunk);h.update(chunk)
   output.flush();os.fsync(output.fileno())
  if size!=expected['bytes'] or h.hexdigest()!=expected['sha256']:raise ValueError('download hash/size mismatch: '+name)
  part.rename(path)
  record={'file':name,'bytes':size,'sha256':h.hexdigest(),'source':url}
  put(ROOT/'audit'/('verified_'+name+'.json'),record)
  print('VERIFIED',name,size,flush=True);return record
 results=[]
 try:
  with ThreadPoolExecutor(max_workers=4) as pool:
   pending={pool.submit(fetch,n):n for n in sorted(entries)}
   for future in as_completed(pending):results.append(future.result())
 except Exception:
  put(ROOT/'audit/RESTORE_FAILURE.json',{'status':'FAILED','verified':results,'error':traceback.format_exc(),'partial_files_preserved':True,'automatic_retry':False});raise
 put(ROOT/'MODEL_CACHE_RESTORE.json',{'status':'RESTORED_SAME_IMMUTABLE_REVISION','model':model,'revision':revision,'snapshot_path':str(dest),'files':sorted(results,key=lambda x:x['file']),'file_count':len(results),'verified_bytes':sum(x['bytes'] for x in results),'historical_hashes_all_match':True,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 print('RESTORE_COMPLETE',str(dest),flush=True)
if __name__=='__main__':main()
