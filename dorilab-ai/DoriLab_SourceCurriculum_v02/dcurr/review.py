"""Human review record writer; no auto-approval or bulk approval."""
import argparse,csv,json,datetime,os
from .common import ROOT,cases,read_csv,sources

def update(path,key,value,changes):
    rows=read_csv(path);found=False
    for row in rows:
        if row[key]==value:row.update(changes);found=True
    if not found:raise SystemExit('ID not found: '+value)
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    os.replace(tmp,path)

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--show-pair');g.add_argument('--case');g.add_argument('--source')
    p.add_argument('--decision',choices=['APPROVED','REVISE','REJECTED','REVIEWED_OK','BLOCKED'])
    p.add_argument('--reviewer');p.add_argument('--notes',default='')
    a=p.parse_args()
    if a.show_pair:
        pp=[c for c in cases() if c['pair_id']==a.show_pair]
        if not pp:raise SystemExit('Pair not found')
        print(json.dumps(sorted(pp,key=lambda x:x['variant']),ensure_ascii=False,indent=2));return
    if not a.reviewer or not a.decision:raise SystemExit('--reviewer and --decision are required')
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if a.source:
        if a.decision not in ['REVIEWED_OK','BLOCKED']:raise SystemExit('Source uses REVIEWED_OK/BLOCKED')
        if a.source not in sources():raise SystemExit('Unknown source')
        update(ROOT/'data/source_review.csv','source_id',a.source,dict(permission_review=a.decision,reviewer=a.reviewer,reviewed_at=stamp,notes=a.notes))
    else:
        if a.decision not in ['APPROVED','REVISE','REJECTED']:raise SystemExit('Case uses APPROVED/REVISE/REJECTED')
        update(ROOT/'data/review_decisions.csv','case_id',a.case,dict(decision=a.decision,reviewer=a.reviewer,reviewed_at=stamp,notes=a.notes))
    print('Review record saved. No source/case content was changed.')
if __name__=='__main__':main()
