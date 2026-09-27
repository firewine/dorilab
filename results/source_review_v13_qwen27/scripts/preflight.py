from pathlib import Path
import json,hashlib,importlib.metadata as md,datetime,collections
from transformers import AutoProcessor
root=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2)
cache=json.load(open(root/'cpu_source_audit/MODEL_CACHE_RESTORE.json'));p=Path(cache['snapshot_path'])
version=md.version('transformers');direct=json.loads(md.distribution('transformers').read_text('direct_url.json'));commit=direct['vcs_info']['commit_id']
assert version=='5.18.0.dev0' and commit=='002e1edf5b5198488297f401dd853056b6521d02'
proc=AutoProcessor.from_pretrained(p,local_files_only=True,trust_remote_code=False);tok=proc.tokenizer
rows=[json.loads(x) for x in (root/'inputs/dev24_public_v13.jsonl').read_text().splitlines()]
selected=[];excluded=[];counts=[]
for row in rows:
 packet=json.loads(row['messages'][1]['content']);sids={x['fact_id'].rsplit('-',1)[0] for x in packet['source_refs']}
 assert len(sids)==1
 sid=next(iter(sids))
 # Membership is determined only by public source refs and source availability, not gold.
 text=proc.apply_chat_template(row['messages'],enable_thinking=False,tokenize=False,add_generation_prompt=True)
 ids=tok(text,add_special_tokens=False,truncation=False)['input_ids']
 counts.append({'case_id':row['case_id'],'source_id':sid,'prompt_tokens':len(ids),'requested_max_new_tokens':384,'total_reserved_tokens':len(ids)+384,'fits_2048':len(ids)+384<=2048,'rendered_prompt_sha256':hashlib.sha256(text.encode()).hexdigest()})
 (selected if sid=='SR13-HYPSO' else excluded).append(row)
assert len(selected)==8
out=root/'inputs/dev8_hypso_public_v13_source_available_v1.jsonl'
with out.open('x') as f:
 for r in selected:f.write(json.dumps(r,ensure_ascii=False)+'\n')
write(root/'DEV_SUBSET_MANIFEST.json',{'version':'v13-dev-source-available-v1','parent_public_inputs_sha256':sha(root/'inputs/dev24_public_v13.jsonl'),'subset_inputs_sha256':sha(out),'included_source_ids':['SR13-HYPSO'],'excluded_sources':{'SR13-CANYVAL':'SOURCE_UNAVAILABLE','SR13-PROBAV':'SOURCE_UNAVAILABLE'},'included_case_ids':[r['case_id'] for r in selected],'excluded_case_ids':[r['case_id'] for r in excluded],'selection_policy':'Public source refs + verified source availability only; all cases of each source kept together','case_count':8,'family_count':2,'source_count':1,'generalization_claim_allowed':False,'human_review_performed':False,'training_eligible':False})
write(root/'TOKEN_PREFLIGHT.json',{'native_template':True,'enable_thinking':False,'truncation':False,'actual_model_revision':cache['revision'],'template_sha256':sha(p/'chat_template.jinja'),'transformers':version,'transformers_git_commit':commit,'cases':counts,'selected_max_prompt_tokens':max(x['prompt_tokens'] for x in counts if x['source_id']=='SR13-HYPSO'),'selected_fit_2048':all(x['fits_2048'] for x in counts if x['source_id']=='SR13-HYPSO'),'training_response_mask':'NOT_RUN_NO_LABEL_RELEASE','ledger_budget':'NOT_RUN_NO_ROUTE_SELECTION'})
print(json.dumps({'selected_cases':len(selected),'max_prompt_tokens':max(x['prompt_tokens'] for x in counts if x['source_id']=='SR13-HYPSO'),'selected_over_limit':[x for x in counts if x['source_id']=='SR13-HYPSO' and not x['fits_2048']]},indent=2))
