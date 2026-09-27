"""Fetch only the eight explicitly allowed files from one immutable model revision."""
import hashlib,json,urllib.request,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 lock=json.loads((ROOT/'ASSET_ALLOWLIST.json').read_text());dest=ROOT/'assets'/lock['revision']
 dest.mkdir(exist_ok=False)
 fetched=[]
 try:
  for name,expected in lock['files'].items():
   if '/' in name or name.endswith(('.safetensors','.bin','.pt','.pth')):raise ValueError('disallowed file')
   url='https://huggingface.co/'+lock['model']+'/resolve/'+lock['revision']+'/'+name
   part=dest/(name+'.part')
   with urllib.request.urlopen(url,timeout=60) as response,part.open('xb') as output:
    data=response.read(expected['bytes']+1);output.write(data)
   actual=hashlib.sha256(data).hexdigest()
   if len(data)!=expected['bytes'] or actual!=expected['sha256']:raise ValueError('asset hash/size mismatch: '+name)
   part.rename(dest/name)
   fetched.append({'file':name,'url':url,'sha256':actual,'bytes':len(data)})
   print('VERIFIED',name,len(data),flush=True)
 except Exception:
  (ROOT/'audit/ASSET_FETCH_FAILURE.json').write_text(json.dumps({'status':'FAILED','fetched':fetched,'error':traceback.format_exc(),'no_fallback_used':True},indent=2)+'\n')
  raise
 (ROOT/'audit/ASSET_FETCH.json').write_text(json.dumps({'status':'PASS','model':lock['model'],'revision':lock['revision'],'files':fetched,'weights_downloaded':False,'fallback_used':False},indent=2)+'\n')
if __name__=='__main__':main()
