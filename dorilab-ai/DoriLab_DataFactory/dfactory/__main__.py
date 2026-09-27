from __future__ import annotations
import argparse
import hashlib
import json
from urllib.error import URLError
from pathlib import Path
from .core import Store,load_jsonl,legacy_candidates,write_jsonl,readability_gaps,model_input

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description='DoriLab review-first Data Factory prototype')
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('demo');s.add_argument('--work',type=Path,default=Path('work_demo'))
    s=sub.add_parser('import-current');s.add_argument('--root',type=Path,required=True);s.add_argument('--work',type=Path,default=Path('work_current'))
    s=sub.add_parser('audit');s.add_argument('--work',type=Path,required=True)
    s=sub.add_parser('serve');s.add_argument('--work',type=Path,required=True);s.add_argument('--port',type=int,default=8790)
    s=sub.add_parser('export-reviews');s.add_argument('--work',type=Path,required=True);s.add_argument('--out',type=Path,required=True)
    s=sub.add_parser('export-model-inputs');s.add_argument('--work',type=Path,required=True);s.add_argument('--out',type=Path,required=True)
    s=sub.add_parser('discover');s.add_argument('--query',required=True);s.add_argument('--domain',required=True);s.add_argument('--out',type=Path,required=True);s.add_argument('--rows',type=int,default=10);s.add_argument('--mailto')
    a=p.parse_args()
    if a.cmd=='discover':
        from .discovery import discover
        print('Metadata candidates:',discover(a.query,a.domain,a.out,a.rows,a.mailto));return
    store=Store(a.work)
    if a.cmd=='demo':
        f=ROOT/'examples/j7_review_demo.jsonl';cs=load_jsonl(f)
        n=store.add_many(cs,str(f),hashlib.sha256(f.read_bytes()).hexdigest());print('Demo cases added:',n)
    elif a.cmd=='import-current':
        cs,f=legacy_candidates(a.root)
        n=store.add_many(cs,str(f),hashlib.sha256(f.read_bytes()).hexdigest())
        print('Imported training candidates:',n);print('Original package unchanged. Model runs v08 are not imported.')
    elif a.cmd=='audit':
        rows=store.list_cases();report={'cases':len(rows),'reviewed_cases':sum(r['reviewed'] for r in rows),
          'readability_gaps':{r['case_id']:r['gaps'] for r in rows if r['gaps']},
          'note':'Missing narrative fields are authoring tasks, not student model errors.'}
        print(json.dumps(report,ensure_ascii=False,indent=2))
    elif a.cmd=='serve':
        from .server import serve
        serve(store,a.port)
    elif a.cmd=='export-reviews':
        rows=store.reviews();write_jsonl(a.out,rows)
        print('Review event records exported:',len(rows));print('Not SFT: source-rights and approved-label export remain in dcurr.prepare.')
    elif a.cmd=='export-model-inputs':
        rows=[{'case_id':r['case_id'],'input':model_input(store.get(r['case_id']))} for r in store.list_cases()]
        write_jsonl(a.out,rows);print('Answer-free input packets:',len(rows))

if __name__=='__main__':
    try:main()
    except URLError as e:raise SystemExit('네트워크 요청 실패: '+str(e)+'. WSL 인터넷/DNS를 확인한 뒤 다시 실행하세요. 기존 파일은 변경하지 않았습니다.')
    except (ValueError,FileNotFoundError,FileExistsError,KeyError) as e:raise SystemExit(str(e))
