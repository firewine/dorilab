"""Export reviewed complete pairs, optionally adding existing contract replay."""
import argparse,json,collections,hashlib
from pathlib import Path
from .common import ROOT,cases,sources,read_csv,load_jsonl,sha256,validate_answer,write_json
from .prompts import build_messages,POLICY_VERSION,SCHEMA_VERSION

def select_approved(cs,review,source_review,ss):
    rr={x['case_id']:x for x in review};sr={x['source_id']:x for x in source_review}
    pp=collections.defaultdict(list)
    for c in cs:pp[c['pair_id']].append(c)
    selected=[]
    for pid,grp in pp.items():
        approved=[c for c in grp if rr.get(c['case_id'],{}).get('decision')=='APPROVED']
        if not approved:continue
        if len(grp)!=2 or len(approved)!=2:raise ValueError(f'{pid}: approve both A/B only after reviewing both')
        for c in grp:
            r=rr[c['case_id']];s=sr.get(c['source_id'],{})
            if not r.get('reviewer') or not r.get('reviewed_at'):raise ValueError('case review metadata missing')
            if s.get('permission_review')!='REVIEWED_OK' or not s.get('reviewer') or not s.get('reviewed_at'):raise ValueError(c['source_id']+': source permission review pending')
            if ss[c['source_id']]['proposed_use'] not in ['TRAIN_CANDIDATE','TRAIN_RESERVED']:raise ValueError('non-training source selected')
            validate_answer(c['expected'],c)
        selected.extend(grp)
    return selected

def main():
    p=argparse.ArgumentParser();p.add_argument('--contract',type=Path);p.add_argument('--out',type=Path,default=ROOT/'build/train_v02.jsonl');a=p.parse_args()
    if a.out.exists() or a.out.with_suffix('.manifest.json').exists():raise SystemExit('Choose a new --out; existing build preserved')
    cs=select_approved(cases(),read_csv(ROOT/'data/review_decisions.csv'),read_csv(ROOT/'data/source_review.csv'),sources())
    if not cs:raise SystemExit('No fully reviewed pairs. Review source permission and A/B cases first.')
    rows=[]
    for c in cs:
        rows.append({'id':c['case_id'],'messages':build_messages(c['role'],c['packet'],c['expected']),'metadata':{'task_pack':'PHYSICS_REVIEW','domain':{'VIBRATION':'MECHANICS'}.get(c['domain'],c['domain']),'source_ids':[c['source_id']],'program_groups':c['source_program_groups'],'pair_id':c['pair_id'],'prompt_version':POLICY_VERSION,'schema_version':SCHEMA_VERSION,'reviewed':True}})
    ncontract=0
    if a.contract:
        for i,c in enumerate(load_jsonl(a.contract)):
            m=c.get('messages',[])
            if len(m)!=3 or [x['role'] for x in m]!=['system','user','assistant']:raise ValueError('contract must be single-turn system/user/assistant')
            json.loads(m[-1]['content'])
            rows.append({'id':'REPLAY-'+str(i),'messages':m,'metadata':{'task_pack':'CONTRACT_REPLAY','domain':'COMMON','program_groups':['CONTRACT_SYNTHETIC_V01'],'reviewed':'USER_SUPPLIED_PREVIOUS_DATA'}});ncontract+=1
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    sys_hashes=sorted({hashlib.sha256(x['messages'][0]['content'].encode()).hexdigest() for x in rows})
    info={'build':'curriculum-v0.2','data_sha256':sha256(a.out),'records':len(rows),'physics_records':len(cs),'pairs':len(cs)//2,'contract_records':ncontract,'source_ids':sorted({c['source_id'] for c in cs}),'program_groups':sorted({g for c in cs for g in c['source_program_groups']}),'prompt_file_sha256':sha256(ROOT/'dcurr/prompts.py'),'legacy_prompt_sha256':sha256(ROOT/'dcurr/prompts_legacy.py'),'system_prompt_hashes':sys_hashes,'review_csv_sha256':sha256(ROOT/'data/review_decisions.csv'),'source_review_sha256':sha256(ROOT/'data/source_review.csv'),'contract_file_sha256':sha256(a.contract) if a.contract else None,'separation_note':'No independent evaluation set is included in this training export.'}
    write_json(a.out.with_suffix('.manifest.json'),info,exclusive=True);print(json.dumps(info,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
