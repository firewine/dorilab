#!/usr/bin/env python3
"""CPU-only source-review pack validation, input rendering, offline scoring and gated SFT export.
No model/API calls, no training, no writes to existing DoriLab projects.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, math, re, sys
from collections import Counter
from pathlib import Path

VERSION='source-review-v13.0'
ACTIONS={'NO_ACTION_REQUIRED','REQUEST_EVIDENCE','CHALLENGE','CALL_TOOL','PROPOSE_FINDING'}

def require(condition, message):
    if not condition: raise ValueError(message)

def strict_json(text):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out, f'duplicate JSON key: {k}');out[k]=v
        return out
    def constant(x): raise ValueError(f'non-finite JSON: {x}')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)

def read_json(path):return strict_json(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):
    result=[strict_json(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    require(all(isinstance(x,dict) for x in result),f'non-object JSONL: {path}')
    return result

def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def file_sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(path, obj, jsonl=False):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:
        if jsonl:
            for row in obj:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        else:f.write(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def forbidden_fields(obj):
    bad={'expected','gold','rationale_ko','relation_to_target','acceptable_reason_codes','label_status'}
    if isinstance(obj,dict):return (set(obj)&bad) or any(forbidden_fields(v) for v in obj.values())
    if isinstance(obj,list):return any(forbidden_fields(v) for v in obj)
    return False

def verify_package_manifest(root):
    mf=read_json(root/'PACKAGE_MANIFEST.json')
    for name,wanted in mf['files'].items():
        p=(root/name).resolve()
        require(p.is_relative_to(root.resolve()),'manifest path escapes package')
        require(p.is_file() and file_sha(p)==wanted,f'package hash mismatch: {name}')
    return mf

def load_split(root,split):
    base=root/'data'/split.lower()
    inputs=rows(base/'inputs.jsonl');gold=rows(base/'gold_candidate.jsonl');meta=rows(base/'metadata.jsonl')
    for name,rr in [('inputs',inputs),('gold',gold),('metadata',meta)]:
        require(len({x['case_id'] for x in rr})==len(rr),f'duplicate case ID in {split}/{name}')
    require({x['case_id'] for x in inputs}=={x['case_id'] for x in gold}=={x['case_id'] for x in meta},f'ID mismatch: {split}')
    return inputs,{x['case_id']:x for x in gold},{x['case_id']:x for x in meta}

def check_answer(answer,packet,reasons):
    require(isinstance(answer,dict),'answer must be an object')
    require(set(answer)<= {'action','claim_id','evidence_refs','reason','requested_evidence','tool','arguments','finding_type'},'unexpected answer fields')
    require(answer.get('action') in ACTIONS,'unknown action')
    require(answer.get('claim_id')==packet['claim_id'],'claim_id mismatch')
    refs=answer.get('evidence_refs')
    require(isinstance(refs,list) and all(isinstance(x,str) for x in refs),'evidence_refs must be a string list')
    require(len(refs)==len(set(refs)),'duplicate evidence reference')
    allowed={x['reference_id'] for x in packet['source_refs']}|{x['evidence_id'] for x in packet['observations']}
    require(set(refs)<=allowed,'unprovided evidence reference')
    if 'reason' in answer:require(answer['reason'] in reasons,'unknown reason')
    if answer['action'] in {'CHALLENGE','REQUEST_EVIDENCE'}: require('reason' in answer,'missing reason')
    if 'requested_evidence' in answer:
        r=answer['requested_evidence'];require(isinstance(r,list) and all(isinstance(x,str) for x in r),'requested_evidence must be a string list')
        require(len(r)==len(set(r)),'duplicate request');require(set(r)<={x['request_id'] for x in packet['request_catalog']},'unprovided request')
    if answer['action']=='REQUEST_EVIDENCE':require(bool(answer.get('requested_evidence')),'missing requested_evidence')
    if answer['action']=='CALL_TOOL':require(isinstance(answer.get('tool'),str) and isinstance(answer.get('arguments'),dict),'missing tool/arguments')
    if answer['action']=='PROPOSE_FINDING':require(isinstance(answer.get('finding_type'),str),'missing finding_type')

def recompute_calculation(c):
    if c is None:return None
    i=c['inputs'];k=c['kind']
    if k=='mean_and_residual':
        m=i['measured_K'];p=i['prediction_K'];require(len(m)==len(p)>0,'bad array lengths')
        return {'mean_K':sum(m)/len(m),'max_abs_residual_K':max(abs(a-b) for a,b in zip(m,p)),'rmse_K':math.sqrt(sum((a-b)**2 for a,b in zip(m,p))/len(m))}
    if k=='relative_difference':
        require(i['baseline']!=0,'zero baseline');return {'percent':100*(i['candidate']-i['baseline'])/i['baseline']}
    if k=='radiative_path':
        q=i['k_W_K4']*(i['hot_K']**4-i['cold_K']**4);return {'q_W':q,'exceeds_threshold':q>i['threshold_W']}
    if k=='shortfall':return {'shortfall_mm':i['required_mm']-i['observed_mm'],'meets_requirement':i['observed_mm']>=i['required_mm']}
    raise ValueError(f'unknown calculation {k}')

def validate(root):
    reasons=read_json(root/'schemas/reason_definitions_v13.json')
    sources=read_json(root/'sources/source_manifest.json'); sm={s['source_id']:s for s in sources}
    facts=read_json(root/'sources/facts.json');fm={f['fact_id']:f for f in facts}
    require(len(sm)==len(sources),'duplicate source'); require(len(fm)==len(facts),'duplicate fact')
    program_splits={};source_splits={};total=0;counts={};seen=set();calculations=0
    for s in sources:
        require(s['raw_file_sha256'] is None,'source bytes were not shipped; do not invent hashes')
        require(not s['human_review_performed'],'unverified human review claim')
        for f in s['reviewed_sections']:
            require(f['section'] and f['text'],'source locator/text missing')
            require(f['used_table_or_figure_values'] is False,'unverified figure/table data must be excluded')
    for path in sorted((root/'data').iterdir()):
        if not path.is_dir():continue
        split=path.name.upper();ins,gold,meta=load_split(root,split);count=Counter();families={}
        for inp in ins:
            require(set(inp)=={'case_id','packet'},'public envelope contains extra metadata')
            p=inp['packet'];g=gold[inp['case_id']];m=meta[inp['case_id']]
            require(not forbidden_fields(inp),'gold-bearing field in public input')
            require(g['human_review_performed'] is False and not g['training_eligible'],'candidate falsely promoted')
            require(g['model_outputs_seen_during_label_authoring'] is False,'post-output gold contamination')
            s=sm[m['source_id']];require(s['split']==split,'source/split mismatch')
            require(m['program_group']==s['program_group'],'program mismatch')
            for key,registry in [(m['source_id'],source_splits),(m['program_group'],program_splits)]:
                require(key not in registry or registry[key]==split,'source/program split overlap');registry[key]=split
            for rf in p['source_refs']:require(rf['fact_id'] in fm and fm[rf['fact_id']]['source_id']==m['source_id'],'wrong source context')
            ids=[x['reference_id'] for x in p['source_refs']]+[x['evidence_id'] for x in p['observations']]
            require(len(ids)==len(set(ids)),'duplicate context ref')
            require(all(x['scope']==p['scope'] for x in p['observations']),'core includes out-of-scope metadata unexpectedly')
            check_answer(g['expected'],p,reasons)
            require(set(g['reference_requirement']['required'])==set(g['expected']['evidence_refs']),'gold refs disagree')
            require(g['review_note']['engineering_disposition']=='DRAFT_ONLY','approval boundary changed')
            ph=digest(p);require(ph not in seen,'exact duplicate packet');seen.add(ph)
            c=g['calculation']
            if c:
                actual=recompute_calculation(c)
                for k,wanted in c['expected'].items():
                    if isinstance(wanted,bool):require(actual[k] is wanted,'calculation boolean mismatch')
                    else:require(math.isclose(actual[k],wanted,rel_tol=1e-10,abs_tol=1e-10),f'calculation mismatch {inp["case_id"]}/{k}')
                calculations+=1
            count[g['expected']['action']]+=1;families.setdefault(m['family_id'],[]).append((inp,g,m))
        for fid,members in families.items():
            require(len(members)==4,'expected complete four-state family')
            vv={m['variant_index']:(i,g) for i,g,m in members};require(set(vv)=={0,1,2,3},'incomplete family variants')
            def ob_text(inp):return sorted((o['text'] for o in inp['packet']['observations']))
            require(ob_text(vv[0][0])==ob_text(vv[1][0]),'proposal-polarity pair changed evidence')
            require(vv[0][1]['expected']['action']=='CHALLENGE' and vv[1][1]['expected']['action']=='NO_ACTION_REQUIRED','bad proposal pair gold')
            require(vv[2][1]['expected']['action']=='REQUEST_EVIDENCE' and vv[3][1]['expected']['action']=='NO_ACTION_REQUIRED','bad readiness pair gold')
        counts[split]={'cases':len(ins),'families':len(families),'sources':len({m['source_id'] for m in meta.values()}),'actions':dict(count)};total+=len(ins)
    return {'status':'PASS','checks_scope':'Structural integrity and toy calculations only; source interpretation/human truth not established','cases':total,'splits':counts,'calculation_records_checked':calculations,'human_review_performed':False,'training_executed':False,'inference_executed':False}

def messages_for_input(inp,facts,system):
    # Deliberately takes no gold argument. Assembly uses all source refs assigned in public input.
    p=copy.deepcopy(inp['packet'])
    for rf in p['source_refs']:
        f=facts[rf['fact_id']]
        rf.update(text=f['text'],source_url=f['source_url'],section=f['section'],pdf_pages_1based=f['pdf_pages_1based'])
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(p,ensure_ascii=False,separators=(',',':'))}]

def render(root,split,out):
    # This path reads only public inputs, facts and the policy; never gold_candidate.jsonl.
    ins=rows(root/'data'/split.lower()/'inputs.jsonl')
    facts={f['fact_id']:f for f in read_json(root/'sources/facts.json')}
    system=(root/'prompts/direct_v13.txt').read_text()
    rr=[]
    for inp in ins:
        msgs=messages_for_input(inp,facts,system)
        rr.append({'case_id':inp['case_id'],'messages':msgs,'messages_sha256':digest(msgs)})
    write_new(out,rr,jsonl=True)
    return {'status':'RENDERED','rows':len(rr),'path':str(out),'tokens':'NOT_MEASURED: run the actual model native tokenizer preflight before inference'}

def exact_fence_unwrap(raw):
    # No extraction of a JSON substring, no completion, no key fixing or channel deletion.
    m=re.fullmatch(r'\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```\s*',raw)
    if not m:return raw,False
    return m.group(1),True

def evaluate_output(inp,gold,raw,reasons,normalize=False):
    text,unwrapped=exact_fence_unwrap(raw) if normalize else (raw,False)
    result={'case_id':inp['case_id'],'raw_output':raw,'normalization_applied':unwrapped,'json_valid':False,'schema_valid':False,'action_correct':False,'strict_pass':False,'false_normal':None,'reason_applicable':'reason' in gold['expected'],'reason_joint_correct':False,'error':None}
    try:
        answer=strict_json(text);require(isinstance(answer,dict),'not a JSON object');result['json_valid']=True
        result['parsed']=answer;result['action_correct']=answer.get('action')==gold['expected']['action']
        result['false_normal']=answer.get('action')=='NO_ACTION_REQUIRED' and gold['expected']['action'] in {'CHALLENGE','REQUEST_EVIDENCE'}
        check_answer(answer,inp['packet'],reasons);result['schema_valid']=True
        e=gold['expected'];refs=answer.get('evidence_refs',[])
        result['reference_exact']=set(refs)==set(e['evidence_refs'])
        reasonok=answer.get('reason') in gold['acceptable_reason_codes'] if 'reason' in e else 'reason' not in answer
        reqok=set(answer.get('requested_evidence',[]))==set(e.get('requested_evidence',[]))
        result['reason_correct']=reasonok if 'reason' in e else None;result['reason_joint_correct']=('reason' in e and reasonok and result['action_correct']);result['request_correct']=reqok
        # This release's core contains only three actions; tool validation is integration scope.
        exact_fields=set(answer)==set(e)
        result['strict_pass']=result['action_correct'] and result['reference_exact'] and reasonok and reqok and exact_fields
    except (ValueError,TypeError,KeyError) as ex:result['error']=str(ex)
    return result

def score(root,split,predfile,out,normalize=False):
    ins,gold,meta=load_split(root,split);im={x['case_id']:x for x in ins};pr=rows(predfile)
    require(len({x.get('case_id') for x in pr})==len(pr),'duplicate predictions')
    require({x.get('case_id') for x in pr}==set(im),'missing/unknown prediction cases')
    reasons=read_json(root/'schemas/reason_definitions_v13.json')
    results=[]
    for x in pr:
        require(isinstance(x.get('raw_output'),str),'prediction requires raw_output string')
        r=evaluate_output(im[x['case_id']],gold[x['case_id']],x['raw_output'],reasons,normalize)
        if x.get('hit_generation_limit') is True:
            r['strict_pass']=False;r['error']='GENERATION_LIMIT_REACHED';r['hit_generation_limit']=True
        r['source_id']=meta[x['case_id']]['source_id'];r['family_id']=meta[x['case_id']]['family_id'];results.append(r)
    counts={k:sum(r.get(k) is True for r in results) for k in ['json_valid','schema_valid','action_correct','reference_exact','reason_correct','reason_joint_correct','strict_pass','false_normal']}
    summary={'status':'SCORED_AGAINST_AI_CANDIDATE_GOLD','policy_version':VERSION,'cases':len(results),'counts':counts,
      'invalid_or_unparsed':sum(not r['json_valid'] for r in results),
      'reason_denominator':sum('reason' in g['expected'] for g in gold.values()),
      'valid_output_false_normal':sum(r['schema_valid'] and r['false_normal'] is True for r in results),
      'false_normal_denominator':sum(g['expected']['action'] in {'CHALLENGE','REQUEST_EVIDENCE'} for g in gold.values()),
      'gold_challenge_cases':sum(g['expected']['action']=='CHALLENGE' for g in gold.values()),
      'wrongly_accepts_refuted_proposal':sum(r.get('parsed',{}).get('action')=='NO_ACTION_REQUIRED' and gold[r['case_id']]['expected']['action']=='CHALLENGE' for r in results),
      'format_track':'EXACT_FENCE_ADAPTER_DIAGNOSTIC' if normalize else 'RAW_STRICT_V13',
      'interpretation':'Not the original v02 scorer; invalid outputs are failures and are not evidence of safe acceptance. No independence or engineering approval claim.',
      'results':results}
    write_new(out,summary);return {k:v for k,v in summary.items() if k!='results'}

def export_sft(root,review_dir,out):
    ins,gold,meta=load_split(root,'TRAIN')
    release=read_json(review_dir/'release.json')
    verify_package_manifest(root)
    require(release.get('approved_pack_manifest_sha256')==file_sha(root/'PACKAGE_MANIFEST.json'),'review release does not lock current package manifest')
    require(not out.exists() and not Path(str(out)+'.manifest.json').exists(),'output or output manifest already exists')
    for key in ['source_program_split_audit_pass','legacy_corpus_audit_pass','candidate_label_policy_accepted','approved_training_experiment']:
        require(release.get(key) is True,f'training export blocked: {key}')
    require(release.get('reviewer') and release.get('reviewed_at'),'release review identity/time missing')
    sr={x['source_id']:x for x in read_json(review_dir/'source_review.json')}
    cr={x['case_id']:x for x in read_json(review_dir/'train_case_review.json')}
    facts={f['fact_id']:f for f in read_json(root/'sources/facts.json')};system=(root/'prompts/direct_v13.txt').read_text()
    output=[]
    for inp in ins:
        cid=inp['case_id'];g=gold[cid];s=sr.get(meta[cid]['source_id'],{});r=cr.get(cid,{})
        for key in ['content_verified','rights_approved','split_novelty_verified']:require(s.get(key) is True,f'source approval missing {cid}/{key}')
        require(s.get('reviewer') and s.get('reviewed_at'),'source review identity missing')
        raw_path=Path(s.get('verified_local_source_path',''))
        require(raw_path.is_file(),'verified_local_source_path missing/unavailable')
        require(file_sha(raw_path)==s.get('raw_file_sha256'),'verified source bytes mismatch')
        require(r.get('decision')=='APPROVED_FOR_TRAINING' and r.get('reviewer') and r.get('reviewed_at'),f'unreviewed case {cid}')
        require(r.get('case_sha256')==digest(inp) and r.get('gold_sha256')==digest(g),f'case/gold changed after review {cid}')
        msgs=messages_for_input(inp,facts,system)+[{'role':'assistant','content':json.dumps(g['expected'],ensure_ascii=False,separators=(',',':'))}]
        output.append({'id':cid,'messages':msgs,'metadata':{'task_pack':'SOURCE_REVIEW_V13','source_id':meta[cid]['source_id'],'family_id':meta[cid]['family_id'],'review_status':'APPROVED_FOR_TRAINING'}})
    write_new(out,output,jsonl=True)
    manifest={'version':VERSION,'records':len(output),'data_sha256':file_sha(out),'review_release_sha256':file_sha(review_dir/'release.json'),
      'training_executed':False,'note':'New TRAIN rows only. Compose and audit any legacy replay in a separate versioned build. Not directly compatible with dcurr.train manifest without an adapter.'}
    write_new(Path(str(out)+'.manifest.json'),manifest);return manifest

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('validate')
    p=sub.add_parser('render');p.add_argument('--split',choices=['TRAIN','DEV','RESERVED_TEST'],required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--split',choices=['TRAIN','DEV','RESERVED_TEST'],required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--unwrap-single-fence',action='store_true')
    p=sub.add_parser('export-sft');p.add_argument('--reviews',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();root=a.root.resolve()
    if a.cmd=='validate':res=validate(root)
    elif a.cmd=='render':res=render(root,a.split,a.out)
    elif a.cmd=='score':res=score(root,a.split,a.predictions,a.out,a.unwrap_single_fence)
    else:res=export_sft(root,a.reviews,a.out)
    print(json.dumps(res,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,FileExistsError,KeyError) as e:
        print('STOP:',e,file=sys.stderr);sys.exit(1)
