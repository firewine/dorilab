"""Diagnostic evaluation of reference-grounded review candidates.
Default corpus is public and intended for development, not an independent holdout.
"""
import argparse,json,time,collections
from pathlib import Path
from .common import ROOT,load_jsonl,strict_parse,validate_answer,answer_matches,write_json,sha256
from .prompts import build_messages,POLICY_VERSION,SCHEMA_VERSION
from .model_io import DEFAULT_MODEL,load_processor,load_model,prompt_tokens,stop_id,environment

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,default=ROOT/'data/physics_candidates40_v02.jsonl');p.add_argument('--adapter',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--model',default=DEFAULT_MODEL);p.add_argument('--revision');p.add_argument('--max-new-tokens',type=int,default=384);p.add_argument('--limit',type=int);p.add_argument('--purpose',default='CANDIDATE_DIAGNOSTIC',choices=['CANDIDATE_DIAGNOSTIC','REVIEWED_DEV','FROZEN_EXTERNAL_EVAL']);a=p.parse_args()
    if a.out.exists() or a.out.with_suffix('.summary.json').exists():raise SystemExit('Output already exists; choose a fresh result filename')
    cs=load_jsonl(a.cases)
    if a.limit:cs=cs[:a.limit]
    if not cs:raise SystemExit('No cases')
    if a.purpose!='CANDIDATE_DIAGNOSTIC' and any(c.get('human_review_status')!='APPROVED' for c in cs):raise SystemExit('This purpose requires reviewer-approved case copies')
    if a.purpose=='FROZEN_EXTERNAL_EVAL' and any(c.get('planned_split')!='FROZEN_EVAL' for c in cs):raise SystemExit('External evaluator must supply a frozen evaluation set')
    print('Purpose:',a.purpose,'/ Records:',len(cs))
    import torch
    from peft import PeftModel
    # Same base processor for all candidates; record it. For new trained candidates,
    # verify the saved renderer version before evaluation.
    processor=load_processor(a.model,a.revision)
    model=load_model(a.model,a.revision,inference=True)
    if a.adapter:
        if not (a.adapter/'adapter_config.json').exists():raise FileNotFoundError('adapter_config.json')
        rm=a.adapter/'RUN_MANIFEST.json'
        if rm.exists():
            run=json.loads(rm.read_text())
            if run['prompt_file_sha256']!=sha256(ROOT/'dcurr/prompts.py') or run['legacy_prompt_file_sha256']!=sha256(ROOT/'dcurr/prompts_legacy.py'):raise SystemExit('Prompt changed since training')
        model=PeftModel.from_pretrained(model,str(a.adapter))
    model.eval()
    a.out.parent.mkdir(parents=True,exist_ok=True);rows=[]
    with a.out.open('x',encoding='utf-8') as f:
        for i,c in enumerate(cs,1):
            # expected/rationale never enter build_messages.
            messages=build_messages(c['role'],c['packet']);text,ids=prompt_tokens(processor,messages)
            inp=torch.tensor([ids],device=model.get_input_embeddings().weight.device)
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();t=time.perf_counter()
            with torch.inference_mode():
                out=model.generate(input_ids=inp,attention_mask=torch.ones_like(inp),max_new_tokens=a.max_new_tokens,do_sample=False,eos_token_id=stop_id(processor),pad_token_id=processor.tokenizer.pad_token_id or stop_id(processor))
            torch.cuda.synchronize();secs=time.perf_counter()-t
            tokens=out[0,len(ids):];raw=processor.tokenizer.decode(tokens,skip_special_tokens=True);parsed=strict_parse(raw)
            schema_ok=False;error=None
            if parsed is not None:
                try:validate_answer(parsed,c);schema_ok=True
                except Exception as e:error=str(e)
            action_ok=isinstance(parsed,dict) and parsed.get('action')==c['expected']['action']
            semantic=any(answer_matches(x,parsed) for x in c.get('acceptable_answers',[c['expected']]))
            row={'case_id':c['case_id'],'pair_id':c['pair_id'],'domain':c['domain'],'source_id':c['source_id'],'role':c['role'],'gold_action':c['expected']['action'],'expected':c['expected'],'raw_output':raw,'parsed':parsed,'strict_json_valid':parsed is not None,'schema_and_refs_valid':schema_ok,'action_ok':action_ok,'contract_pass':schema_ok and semantic,'validation_error':error,'prompt_tokens':len(ids),'generated_tokens':len(tokens),'generation_seconds':secs,'peak_allocated_GiB':torch.cuda.max_memory_allocated()/2**30,'hit_generation_limit':len(tokens)>=a.max_new_tokens}
            rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
            print(f'{i}/{len(cs)} {c["case_id"]}: {"PASS" if row["contract_pass"] else "FAIL"}')
    bypair=collections.defaultdict(list)
    for r in rows:bypair[r['pair_id']].append(r)
    complete=[v for v in bypair.values() if len(v)==2]
    summary={'purpose':a.purpose,'records':len(rows),'case_file_sha256':sha256(a.cases),'model':a.model,'adapter':str(a.adapter) if a.adapter else None,'adapter_sha256':sha256(a.adapter/'adapter_model.safetensors') if a.adapter and (a.adapter/'adapter_model.safetensors').exists() else None,'environment':environment(),'prompt_version':POLICY_VERSION,'schema_version':SCHEMA_VERSION,'prompt_sha256':sha256(ROOT/'dcurr/prompts.py'),'strict_json_valid':sum(r['strict_json_valid'] for r in rows),'schema_and_refs_valid':sum(r['schema_and_refs_valid'] for r in rows),'action_correct':sum(r['action_ok'] for r in rows),'contract_pass':sum(r['contract_pass'] for r in rows),'complete_pairs':len(complete),'both_variants_pass':sum(all(r['contract_pass'] for r in pp) for pp in complete),'generation_seconds_total':sum(r['generation_seconds'] for r in rows),'timing_note':'Includes first-case warmup; excludes model load, parsing, retrieval and human review. Not end-to-end cost.','by_gold_action':{k:{'n':sum(r['gold_action']==k for r in rows),'pass':sum(r['gold_action']==k and r['contract_pass'] for r in rows)} for k in sorted({r['gold_action'] for r in rows})}}
    write_json(a.out.with_suffix('.summary.json'),summary,exclusive=True);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
