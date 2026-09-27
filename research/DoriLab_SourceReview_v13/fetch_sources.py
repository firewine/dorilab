#!/usr/bin/env python3
"""Fetch official source bytes on the user's server. No approval is inferred from download success."""
import argparse,hashlib,json,urllib.request,urllib.error
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--ids',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();root=Path(__file__).resolve().parent
 src={s['source_id']:s for s in json.loads((root/'sources/source_manifest.json').read_text())}
 unknown=set(a.ids)-set(src)
 if unknown:raise SystemExit('Unknown or evaluator-only sources: '+', '.join(sorted(unknown)))
 a.out.mkdir(parents=True,exist_ok=True)
 report=[]
 for sid in a.ids:
  s=src[sid];url=s.get('download_url') or s['landing_url'];entry={'source_id':sid,'requested_url':url,'content_verified':False,'rights_approved':False}
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'DoriLab-SourceAudit/13 (research source verification)'})
   with urllib.request.urlopen(req,timeout=30) as res:
    typ=res.headers.get('Content-Type','');body=res.read(25*1024*1024+1);entry['final_url']=res.url;entry['content_type']=typ
   if len(body)>25*1024*1024:raise ValueError('source exceeds 25 MiB cap; review manually')
   if s.get('download_url'):
    if not body.startswith(b'%PDF-'):raise ValueError('expected PDF bytes, received another content type')
    suffix='.pdf'
   else:
    head=body[:20000].decode('utf-8',errors='ignore').lower()
    if ('challenge validation' in head or 'too many requests' in head or 'access denied' in head):raise ValueError('publisher access/challenge page; use a browser or licensed institutional path')
    suffix='.html'
   path=a.out/(sid+suffix)
   if path.exists():raise FileExistsError('preserving existing '+str(path))
   with path.open('xb') as f:f.write(body)
   entry.update(status='FETCHED_UNREVIEWED',verified_local_source_path=str(path.resolve()),raw_file_sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
  except (OSError,ValueError,urllib.error.URLError) as ex:entry.update(status='FAILED_PRESERVED',error=str(ex))
  report.append(entry)
  print(json.dumps(entry,ensure_ascii=False))
 print('No training, no label changes, no source-approval fields were set true.')
if __name__=='__main__':main()
