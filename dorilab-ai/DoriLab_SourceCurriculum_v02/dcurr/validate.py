import json,collections,sys
from .common import ROOT,cases,sources,validate_answer,semantic_state_hash,sha256

def main():
    ss=sources();cs=cases();seen=set();pairs=collections.defaultdict(list)
    for c in cs:
        if c['case_id'] in seen:raise ValueError('duplicate case id')
        seen.add(c['case_id']);pairs[c['pair_id']].append(c)
        if c['source_id'] not in ss:raise ValueError('unknown source')
        if c['planned_split']!='TRAIN_CANDIDATE':raise ValueError('unexpected shipped split')
        if ss[c['source_id']]['proposed_use'].startswith('EVAL'):raise ValueError('reserved source in training candidates')
        if c['basis']!='SYNTHETIC_COUNTERFACTUAL':raise ValueError('unexpected evidence basis')
        validate_answer(c['expected'],c)
    for pid,pp in pairs.items():
        if len(pp)!=2 or {x['variant'] for x in pp}!={'A','B'}:raise ValueError(pid+' incomplete pair')
        if len({x['source_id'] for x in pp})!=1:raise ValueError(pid+' source mismatch')
        if len({semantic_state_hash(x) for x in pp})!=2:raise ValueError(pid+' duplicate state')
        if len({x['expected']['action'] for x in pp})<2:raise ValueError(pid+' does not change action')
    a=ROOT/'data/legacy32_unmodified.jsonl';b=ROOT/'legacy/PhysicsSeed32_v01/data/physics_cases_seed32_v01.jsonl'
    if sha256(a)!=sha256(b):raise ValueError('legacy records changed')
    # Domain taxonomy is sidecar to preserve legacy record bytes.
    tax=json.loads((ROOT/'data/case_taxonomy_v02.json').read_text())
    if {x['case_id'] for x in tax}!=seen:raise ValueError('taxonomy mismatch')
    out={'status':'PASS','sources':len(ss),'domains':dict(collections.Counter(x['primary_domain'] for x in ss.values())),'candidate_cases':len(cs),'pairs':len(pairs),'legacy_unchanged':True,'human_approved_cases_in_shipped_package':0,'source_pdf_files_included':0}
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
