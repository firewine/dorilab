"""Download selected originals only; checks PDF magic, records hashes, preserves files."""
import argparse,datetime,urllib.request,time
from pathlib import Path
from .common import ROOT,sources,sha256,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--ids',nargs='+',required=True);p.add_argument('--allow-reserved',action='store_true');a=p.parse_args();ss=sources();report=[]
    target=ROOT/'sources/originals';target.mkdir(exist_ok=True)
    for sid in a.ids:
        if sid not in ss:raise SystemExit('Unknown ID '+sid)
        s=ss[sid]
        if s['proposed_use']=='EVAL_RESERVED' and not a.allow_reserved:raise SystemExit(sid+' is evaluation-reserved. Assign the evaluation author separately or pass --allow-reserved deliberately.')
        row={'source_id':sid,'status':'FAILED','landing_url':s['landing_url']}
        out=target/(sid+'.pdf')
        if out.exists():
            row.update(status='ALREADY_PRESENT',path=str(out.relative_to(ROOT)),sha256=sha256(out));report.append(row);continue
        errors=[]
        for url in s['download_urls']:
            tmp=out.with_suffix('.part')
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'DoriLabResearch/0.2 contact-local-user'})
                with urllib.request.urlopen(req,timeout=60) as r,tmp.open('wb') as f:
                    size=0
                    while True:
                        b=r.read(1<<20)
                        if not b:break
                        size+=len(b)
                        if size>250*1024*1024:raise ValueError('file exceeds 250 MiB limit')
                        f.write(b)
                with tmp.open('rb') as f:magic=f.read(1024)
                if b'%PDF-' not in magic:raise ValueError('Response is not a PDF, possibly a catalog/denial page')
                tmp.replace(out);row.update(status='DOWNLOADED',url=url,path=str(out.relative_to(ROOT)),sha256=sha256(out),bytes=out.stat().st_size);break
            except Exception as e:
                errors.append(str(e));tmp.unlink(missing_ok=True)
        if row['status']=='FAILED':row['errors']=errors
        report.append(row);print(sid,row['status'],s['landing_url']);time.sleep(.3)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=ROOT/'reports'/('downloads_'+stamp+'.json');write_json(out,report,exclusive=True);print('Report:',out)
if __name__=='__main__':main()
