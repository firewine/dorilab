"""Register newly annotated training candidates. Defaults to validation-only."""
import argparse,json,csv,datetime,shutil
from pathlib import Path
from .common import ROOT,cases,sources,load_jsonl,validate_answer,write_json,sha256,read_csv

def main():
    p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--commit',action='store_true');a=p.parse_args()
    new=load_jsonl(a.file);old=cases();ss=sources();oldids={c['case_id'] for c in old};oldpairs={c['pair_id'] for c in old};pairs={}
    if not new:raise SystemExit('No records')
    seen=set()
    required={'case_id','pair_id','variant','role','domain','source_id','source_fact_ids','source_program_groups','basis','packet','expected','rationale_ko','source_facts_verification'}
    for c in new:
        if not required<=set(c):raise ValueError('Missing fields '+str(required-set(c)))
        if c['case_id'] in oldids|seen or c['pair_id'] in oldpairs:raise ValueError('Case/pair ID already registered; use a new version')
        seen.add(c['case_id']);pairs.setdefault(c['pair_id'],[]).append(c)
        if c['source_id'] not in ss:raise ValueError('Source must first be registered')
        if ss[c['source_id']]['proposed_use'] not in ['TRAIN_RESERVED','TRAIN_CANDIDATE']:raise ValueError('This source is not assigned to training')
        if c['role'] not in ['EVIDENCE','CRITIC']:raise ValueError('Current Physics contract supports Evidence/Critic only')
        if c['source_facts_verification'] not in ['USER_CHECKED_BODY','PDF_TEXT_SECTION_CHECKED','PDF_TEXT_CHECKED_NOT_VISUALLY_VERIFIED']:raise ValueError('Verify the actual source section before registering')
        if not set(ss[c['source_id']]['program_groups'])<=set(c['source_program_groups']):raise ValueError('Missing program group from source registry')
        refs=c['packet']['reference_context']
        for r in refs:
            if r.get('source_id')!=c['source_id'] or not r.get('section') or not r.get('text'):raise ValueError('Reference must identify source, section and paraphrase')
        if not set(c['source_fact_ids'])<={r['reference_id'] for r in refs}:raise ValueError('Source fact link missing')
        validate_answer(c['expected'],c)
        c['human_review_status']='PENDING';c['planned_split']='TRAIN_CANDIDATE'
    for pid,pp in pairs.items():
        if len(pp)!=2 or {c['variant'] for c in pp}!={'A','B'}:raise ValueError(pid+' requires complete A/B')
        if len({c['expected']['action'] for c in pp})!=2:raise ValueError(pid+' needs an action-changing contrast')
    print('VALIDATION PASS:',len(new),'cases;',len(pairs),'pairs')
    if not a.commit:print('No files changed. Re-run with --commit after checking the draft.');return
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=ROOT/'reports'/('registration_backup_'+stamp);backup.mkdir(parents=True)
    dest=ROOT/'data/additional_candidates.jsonl';review=ROOT/'data/review_decisions.csv';tax=ROOT/'data/case_taxonomy_v02.json'
    for f in [dest,review,tax]:
        if f.exists():shutil.copy2(f,backup/f.name)
    with dest.open('a',encoding='utf-8') as f:
        for c in new:f.write(json.dumps(c,ensure_ascii=False)+'\n')
    r=read_csv(review)
    for c in new:r.append({'case_id':c['case_id'],'pair_id':c['pair_id'],'decision':'PENDING','reviewer':'','reviewed_at':'','notes':''})
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(r[0]));w.writeheader();w.writerows(r)
    t=json.loads(tax.read_text())
    for c in new:t.append({'case_id':c['case_id'],'primary_domain':ss[c['source_id']]['primary_domain'],'source_id':c['source_id'],'subdomains':ss[c['source_id']]['subdomains'],'curriculum_stage':'L2_SINGLE_DOMAIN','legacy_record_preserved':False})
    write_json(tax,t);print('Registered PENDING; backup:',backup)
if __name__=='__main__':main()
