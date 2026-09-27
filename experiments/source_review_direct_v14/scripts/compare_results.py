"""Offline only: sealed direct_v14 outputs + unchanged v13 scorer; baseline official scores are read, not recomputed."""
from pathlib import Path
import argparse,collections,datetime,json,sys
from prepare_inputs import ROOT,BASE,PACK,sha,write_new
from contract import violations
sys.path.insert(0,str(PACK))
import packtool as p

def index(rows):
 result={r['case_id']:r for r in rows}
 if len(result)!=len(rows):raise ValueError('duplicate case IDs')
 return result
def metrics(score,raw,packet):
 try:answer=p.strict_json(raw['raw_output'])
 except (ValueError,TypeError):answer=None
 return {'json_valid':score['json_valid'],'schema_valid':score['schema_valid'],
 'parsed_action_correct':score['action_correct'],
 'schema_qualified_action_correct':score['schema_valid'] and score['action_correct'],
 'reference_exact':score.get('reference_exact'), 'strict_pass':score['strict_pass'],
 'contract_violations':violations(answer,packet), 'generation_seconds':raw['generation_seconds'],
 'prompt_tokens':raw['prompt_tokens'],'generated_tokens':raw['generated_tokens'],
 'hit_generation_limit':raw.get('hit_generation_limit',False),'scorer_error':score['error']}
def aggregate(items):
 keys=['json_valid','schema_valid','parsed_action_correct','schema_qualified_action_correct','strict_pass']
 out={'cases':len(items),**{key:sum(r[key] is True for r in items) for key in keys}}
 out['reference_exact']={label:sum(r['reference_exact'] is value for r in items) for label,value in [('true',True),('false',False),('not_evaluated',None)]}
 out['contract_violation_cases']=sum(bool(r['contract_violations']) for r in items)
 out['contract_violations']=dict(collections.Counter(v for r in items for v in r['contract_violations']))
 out['generation_seconds']=sum(r['generation_seconds'] for r in items)
 out['generation_limit_hits']=sum(r['hit_generation_limit'] for r in items)
 return out
def transitions(old,new):
 changes={}
 for key in ['json_valid','schema_valid','parsed_action_correct','schema_qualified_action_correct','strict_pass','reference_exact']:
  a,b=old[key],new[key]
  if a==b:state='unchanged'
  elif a is None or b is None:state='evaluation_availability_changed'
  else:state='improved' if b else 'regressed'
  changes[key]={'before':a,'after':b,'transition':state}
 changes['contract_violations']={'before':old['contract_violations'],'after':new['contract_violations']}
 changes['generation_seconds_delta']=new['generation_seconds']-old['generation_seconds']
 return changes

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);a=ap.parse_args()
 run=a.run.resolve()
 if not run.is_relative_to(ROOT/'runs'):raise ValueError('run must be in this experiment')
 lock=p.read_json(ROOT/'EXPERIMENT_LOCK.json');seal=p.read_json(run/'OUTPUT_SEAL.json');manifest=p.read_json(run/'RUN_MANIFEST.json')
 if manifest['experiment_version']!='direct_v14' or manifest['input_sha256']!=lock['input_sha256']:raise ValueError('run/input mismatch')
 if sha(ROOT/lock['input_file'])!=lock['input_sha256']:raise ValueError('input hash changed')
 if sha(run/'predictions.jsonl')!=seal['output_sha256']:raise ValueError('new output seal mismatch')
 if sha(PACK/'packtool.py')!=lock['scorer_sha256']:raise ValueError('scorer changed')
 # Verify pre-CPU-work gold/baseline bytes before any gold join. No old file is written.
 before=p.read_json(ROOT/'audit/PRESERVATION_BEFORE.json');work=ROOT.parents[1]
 for path in [PACK/'data/dev/gold_candidate.jsonl',BASE/'RAW_OFFICIAL_CASE_RESULTS.jsonl',BASE/'baseline_direct/predictions.jsonl']:
  if sha(path)!=before[str(path.relative_to(work))]:raise ValueError('preserved comparison source changed')
 inp=index(p.rows(ROOT/lock['input_file']));new=index(p.rows(run/'predictions.jsonl'))
 oldraw=index(p.rows(BASE/'baseline_direct/predictions.jsonl'));oldscore=index(p.rows(BASE/'RAW_OFFICIAL_CASE_RESULTS.jsonl'))
 if set(new)!=set(inp) or set(oldraw)!=set(inp) or set(oldscore)!=set(inp):raise ValueError('comparison membership mismatch')
 for cid,row in new.items():
  if row['path']!='direct_v14' or row['messages_sha256']!=inp[cid]['messages_sha256']:raise ValueError('new row provenance mismatch')
 # Candidate labels become visible only in this separate post-seal process.
 gold=index(p.rows(PACK/'data/dev/gold_candidate.jsonl'));reasons=p.read_json(PACK/'schemas/reason_definitions_v13.json')
 joined_at=datetime.datetime.now(datetime.timezone.utc).isoformat();details=[];comparisons=[]
 for cid in inp:
  packet=json.loads(inp[cid]['messages'][1]['content']);raw=new[cid]
  score=p.evaluate_output({'case_id':cid,'packet':packet},gold[cid],raw['raw_output'],reasons,normalize=False)
  if raw.get('hit_generation_limit'):
   score.update(strict_pass=False,error='GENERATION_LIMIT_REACHED',hit_generation_limit=True)
  prior=oldscore[cid]['scorer_result_unchanged']
  if prior['raw_output']!=oldraw[cid]['raw_output']:raise ValueError('baseline raw/official mismatch')
  previous=metrics(prior,oldraw[cid],packet);current=metrics(score,raw,packet)
  details.append(score);comparisons.append({'case_id':cid,'baseline':previous,'direct_v14':current,'changes':transitions(previous,current)})
 summary={'experiment_version':'direct_v14','candidate_status':'SOURCE_GROUNDED_AI_CANDIDATE',
 'human_review_performed':False,'training_eligible':False,'independent_generalization_evaluation':False,
 'scorer':'unchanged packtool.evaluate_output(normalize=False)','baseline_official_rescored':False,
 'raw_output_repaired':False,'gold_join_at_utc':joined_at,'gold_sha256':sha(PACK/'data/dev/gold_candidate.jsonl'),
 'scorer_sha256':sha(PACK/'packtool.py'),'output_sha256':seal['output_sha256'],
 'baseline':aggregate([r['baseline'] for r in comparisons]),'direct_v14':aggregate([r['direct_v14'] for r in comparisons]),
 'strict_improved_cases':[r['case_id'] for r in comparisons if r['changes']['strict_pass']['transition']=='improved'],
 'strict_regressed_cases':[r['case_id'] for r in comparisons if r['changes']['strict_pass']['transition']=='regressed'],
 'time_comparison_note':'Total and per-case generation wall time; prompt lengths may differ. Record hardware/runtime; no speedup claim if environments differ.',
 'baseline_timing':p.read_json(BASE/'baseline_direct/OUTPUT_SEAL.json'), 'direct_v14_timing':seal}
 target=run/'comparison';target.mkdir(exist_ok=False)
 write_new(target/'CASE_RESULTS.jsonl',details,True);write_new(target/'CASE_COMPARISON.jsonl',comparisons,True);write_new(target/'SUMMARY.json',summary)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
