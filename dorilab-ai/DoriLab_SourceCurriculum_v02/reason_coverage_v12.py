#!/usr/bin/env python3
"""Pilot: matched-repeat vs reason-coverage data, using existing DoriLab trainer.
Copy beside dcurr/, new_source_reason_v10.py, data/, runs/.
prepare --accept-ai-authored-training-candidates; train; evaluate; compare.
No pip installs, no edits to old code/data/review files, no automatic resume.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, random, runpy
import subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
VERSION='reason-coverage-v1.2.0'
OUTDIR='data/reason_coverage_v12'
PARENT='data/evidence_training_v05/position210.jsonl'
PARENT_SHA='52045fec4cbab795b7863f9e32e366aa3485c2f66f07ddc9a7142a52b5fd1c81'
AUDIT='data/reason_exposure_v11/audit.json'
E2RUN='runs/evidence_training_v05_position_e2/RUN_MANIFEST.json'
V10='data/new_source_reason_v10'
ARMS=('repeat','coverage')
MODEL='Qwen/Qwen3.5-2B'
REVISION='15852e8c16360a2fea060d615a32b45270f8a8fc'
ABSENT={'CONFIGURATION_SCOPE_UNRESOLVED','EXPOSURE_METADATA_UNRESOLVED','METHOD_INTERPRETATION_ERROR','MEASUREMENT_MAPPING_MISMATCH','MODAL_INPUTS_MISSING'}


def need(ok, text):
    if not ok: raise ValueError(text)
def now(): return datetime.now(timezone.utc).isoformat()
def strict(text):
    def unique(ps):
        d={}
        for k,v in ps:
            need(k not in d,'Duplicate JSON key: '+k);d[k]=v
        return d
    def bad(x): raise ValueError('Non-finite JSON: '+x)
    return json.loads(text,object_pairs_hook=unique,parse_constant=bad)
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def readj(p): return strict(Path(p).read_text(encoding='utf-8-sig'))
def readl(p):
    rs=[strict(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    need(all(isinstance(r,dict) for r in rs),'JSONL object rows required: '+str(p));return rs
def writej(p,x):
    with Path(p).open('x',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def writel(p,rs):
    with Path(p).open('x',encoding='utf-8') as f:
        for r in rs:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
def local(root,name):
    p=Path(name);need(not p.is_absolute() and '..' not in p.parts,'Relative project path required: '+str(name))
    dest=root/p;need(dest.resolve().is_relative_to(root.resolve()),'Path escapes project');return dest
def idx(rs,key='case_id'):
    d={}
    for r in rs:
        k=r.get(key);need(isinstance(k,str) and k not in d,'Missing/duplicate '+key);d[k]=r
    return d
def helper(root):
    path=root/'new_source_reason_v10.py';need(path.is_file(),'Keep existing new_source_reason_v10.py beside dcurr/.')
    spec=importlib.util.spec_from_file_location('_coverage_v12_v10',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    need(mod.VERSION=='new-source-reason-v1.0.0','Unexpected v10 helper version');return mod

def make_cases(spec=None):
    if spec is None:spec=SPEC
    rng=random.Random(12042);used=set()
    def fresh(prefix):
        while True:
            s=prefix+str(rng.randrange(100000,999999))
            if s not in used:used.add(s);return s
    rows=[]
    for i,t in enumerate(spec['topics']):
        scope={'unit':'RC12-U'+str(i+201),'configuration':'RC12-C'+str(i+301),'run':'RC12-R'+str(i+401)}
        f=copy.deepcopy(spec['references'][t['fact_key']]);f['reference_id']=fresh('SF-')
        obsid=fresh('OBS-');claim=fresh('CLM-');pid='RC12-'+t['topic_id']
        question=('Review scope: unit={unit}; configuration={configuration}; run={run}. '
           'Only records matching all three scope identifiers may substantiate this check; '
           'any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. '
           +t['question']).format(**scope)
        for variant in ('A','B'):
            negative=(variant=='A')==(i%2==0)
            body=t['negative'] if negative else t['positive']
            text=('Record scope: unit={unit}; configuration={configuration}; run={run}. '+body).format(**scope)
            packet={'review_question':question,'claim_id':claim,'reference_context':[copy.deepcopy(f)],
              'case_packet':{'evidence':[{'evidence_id':obsid,'text':text}],'proposal':t['proposal']},
              'allowed_request_ids':copy.deepcopy(t['request_ids'])}
            expected={'action':t['action'] if negative else 'NO_ACTION_REQUIRED','claim_id':claim,'evidence_refs':[f['reference_id'],obsid]}
            if negative:
                expected['reason']=t['reason']
                if t['action']=='REQUEST_EVIDENCE':expected['requested_evidence']=copy.deepcopy(t['request_ids'])
            domain={'TH-01':'THERMAL','VB-X1':'VIBRATION','EE-02':'EEE','EE-03':'EEE'}[f['source_id']]
            rows.append({'case_id':pid+'-'+variant,'pair_id':pid,'variant':variant,
                'role':'CRITIC' if t['action']=='CHALLENGE' else 'EVIDENCE',
                'source_id':f['source_id'],'domain':domain,'packet':packet,'expected':expected,
                'acceptable_answers':[copy.deepcopy(expected)],'authoring':{
                'origin':'NEW_AI_AUTHORED_SYNTHETIC_TRAINING_CANDIDATE','human_review_performed':False,
                'engineering_approved':False,'real_measurement_available':False,'review_ko':t['review_ko'],
                'source_basis':spec['sources'][f['source_id']],
                'labels_are':'SOURCE_PRINCIPLE_PLUS_DORILAB_REASON_TAXONOMY',
                'not_from_evaluation':'No NS10/MRO/CM-2/RTG4 case, observation or proposed answer is used to construct these records.'}})
    validate_cases(rows)
    return rows

def validate_cases(rows):
    need(len(rows)==36 and len(idx(rows))==36,'Need 36 new scenarios')
    need(Counter(r['expected']['action'] for r in rows)=={'CHALLENGE':8,'REQUEST_EVIDENCE':10,'NO_ACTION_REQUIRED':18},'Wrong action mix')
    counts=Counter(r['expected'].get('reason') for r in rows if 'reason' in r['expected'])
    need(len(counts)==9 and set(counts.values())=={2},'Need 9 reason codes with 2 non-identical target scenarios each')
    need(ABSENT<=set(counts),'Missing required coverage')
    pairs=defaultdict(list)
    for r in rows:
        pairs[r['pair_id']].append(r)
        p=r['packet'];a=r['expected']
        need(a['claim_id']==p['claim_id'],'Claim mismatch')
        need(set(a['evidence_refs'])=={p['reference_context'][0]['reference_id'],p['case_packet']['evidence'][0]['evidence_id']},'Bad references')
        need(set(a.get('requested_evidence',[]))<=set(p['allowed_request_ids']),'Request outside whitelist')
        need(r['source_id'] in {'TH-01','VB-X1','EE-02','EE-03'},'Evaluation source used as training source')
        need(not any(s in canon(p) for s in ('NS10-','MRO','RTG4','CM-2','AP06-')),'Forbidden evaluation identity in model input')
        need(r['authoring']['human_review_performed'] is False,'Authorship must remain AI')
    need(len(pairs)==18,'Need 18 paired topic instances')
    for pid,rr in pairs.items():
        a,b=rr;need(a['packet']['review_question']==b['packet']['review_question'],'Pair question changed')
        need(a['packet']['case_packet']['proposal']==b['packet']['case_packet']['proposal'],'Pair proposal changed')
        need(a['expected']['action']!=b['expected']['action'],'Pair must change action')
        need(a['packet']['case_packet']['evidence']!=b['packet']['case_packet']['evidence'],'Observations not contrasted')

def make_arms(parent,cases,prompts):
    need(len(parent)==210,'Need parent 210 rows');idx(parent,'id')
    pools=defaultdict(list)
    for row in parent:
        if row.get('v05_metadata',{}).get('kind')=='physics':
            pools[strict(row['messages'][-1]['content'])['action']].append(row)
    need(all(pools[a] for a in ('CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED')),'No suitable Physics replay samples')
    new=[];replay=[];uses=Counter()
    system_set={r['messages'][0]['content'] for r in parent}
    for c in cases:
        answer=c['expected'];action=answer['action']
        messages=prompts.build_messages(c['role'],c['packet'],answer)
        ms=prompts.build_messages(c['role'],c['packet'])
        need(messages[:-1]==ms and messages[-1]['role']=='assistant','Train/inference prompt mismatch')
        need(strict(messages[-1]['content'])==answer,'Prompt factory changed target')
        need(messages[0]['content'] in system_set,'New system prompt differs from parent; stop, do not train a changed contract')
        need(len(ms)==2 and [m['role'] for m in ms]==['system','user'],'Unexpected input shape')
        new.append({'id':c['case_id'],'messages':messages,'metadata':{
          'task_pack':'PHYSICS_REVIEW','source_ids':[c['source_id']],'domain':c['domain'],
          'pair_id':c['pair_id'],'parent_case_id':c['case_id'],'program_groups':['AI_RC12_'+c['source_id']],
          'reviewed':'AI_REVIEWED_EXPERIMENTAL_CANDIDATE_NOT_HUMAN_SIGNOFF',
          'human_review_performed':False,'experimental_training_use':True}})
        choices=pools[action];old=copy.deepcopy(choices[uses[action]%len(choices)]);uses[action]+=1
        origin_id=old['id'];old['id']='RC12-REPLAY-'+c['case_id']
        old['v12_replay']={'parent_row_id':origin_id,'matched_action':action,'purpose':'MATCHED_EXTRA_ROW_CONTROL'}
        replay.append(old)
    # The same parent examples occupy the same slots in both arms. Additional
    # rows have matched action frequencies, not matched target tokens/reasons.
    schedule=[('parent',i) for i in range(210)]+[('extra',i) for i in range(36)]
    random.Random(42).shuffle(schedule)
    arms={}
    for arm,extra in [('repeat',replay),('coverage',new)]:
        arms[arm]=[copy.deepcopy(parent[i] if kind=='parent' else extra[i]) for kind,i in schedule]
        need(len(arms[arm])==246 and len(idx(arms[arm],'id'))==246,'246 unique row IDs required')
    for a,b in zip(arms['repeat'],arms['coverage']):
        need(strict(a['messages'][-1]['content'])['action']==strict(b['messages'][-1]['content'])['action'],'Row action imbalance')
    return arms

def exposure(rows):
    cs=Counter();acts=Counter()
    for r in rows:
        a=strict(r['messages'][-1]['content']);acts[a['action']]+=1
        if a.get('reason'):cs[a['reason']]+=1
    return {'rows':len(rows),'action_rows':dict(acts),'supervised_reason_rows':dict(cs)}

def review_md(cases):
    lines=['# v12 — reason coverage training candidates','',
      'AI 작성·AI 논리검토. 실제 시험자료나 사람 승인 아님. NS10 평가자료는 학습에 포함하지 않음.',
      '단일 관측으로 범위를 정리한 신규 사례를 사용하며 기존 210행의 위치 증강 사례는 그대로 replay한다.',
      '새로운 36개 상태는 18개 관련 쌍이다. 기존 반복 60행도 고유 Physics 20개일 뿐이다.',
      'source fact는 기존 제공 패킷의 발췌를 재사용한다. VB-X1 식(2)와 C² 선정 문단만 공개 출판사 HTML에서 다시 확인했다. PDF 전체/원시 시험값을 새로 검증하지 않았다.',
      '대조군과 학습군은 행 수·action 노출·데이터 슬롯·epoch를 맞추지만 입력 길이·정답 토큰 수는 같지 않다. 단일 seed의 개발 실험이다.','']
    for c in sorted(cases,key=lambda x:x['case_id']):
        p=c['packet'];lines += ['## '+c['case_id'],c['authoring']['review_ko'],
          '**문헌 원리:** '+p['reference_context'][0]['text'],
          '**위치:** '+p['reference_context'][0].get('section',''),
          '**가상 질문:** '+p['review_question'],'**제안:** '+p['case_packet']['proposal'],
          '**가상 관측:** '+p['case_packet']['evidence'][0]['text'],
          '**AI 정답 후보:** `'+canon(c['expected'])+'`','']
    return '\n\n'.join(lines)

def prepare(root,outdir,accept):
    need(accept,'Use --accept-ai-authored-training-candidates for this experimental training release; it is not human engineering approval.')
    d=local(root,outdir);need(not d.exists(),'Output folder exists; preserve it and use a new --outdir')
    slug=d.name;need(slug.replace('_','').isalnum(),'Use a simple alphanumeric output-folder name')
    h=helper(root);vd,vm=h.plan(root,V10);common,prompts=h.modules(root)
    parent_path=local(root,PARENT);dm=readj(parent_path.with_suffix('.manifest.json'));rm=readj(local(root,E2RUN));audit=readj(local(root,AUDIT))
    need(sha(parent_path)==PARENT_SHA==dm['data_sha256']==rm['data_manifest']['data_sha256'],'Parent dataset hash mismatch')
    need(audit['input_sha256'].get(PARENT)==PARENT_SHA and audit['input_sha256'].get(E2RUN)==sha(local(root,E2RUN)),'v11 does not describe this e2 data/run')
    need(dm['prompt_file_sha256']==sha(root/'dcurr/prompts.py') and dm['legacy_prompt_sha256']==sha(root/'dcurr/prompts_legacy.py'),'Original prompts changed')
    need(rm.get('rank')==16 and rm.get('lr')==5e-5 and rm.get('epochs_requested')==2,'Unexpected parent training settings')
    need(vm['model']==MODEL and vm['revision']==REVISION,'Unexpected measured model/revision')
    need(all(audit['reason_codes'][code]['supervised_rows']==0 for code in ABSENT),'This pilot was designed for the reported missing-target set')
    parent=readl(parent_path);cases=make_cases()
    for c in cases:common.validate_answer(c['expected'],c)
    arms=make_arms(parent,cases,prompts)
    need(set(SPEC['sources'])<=set(dm['source_ids']),'New training sources not present in original reviewed corpus')
    # Evaluation is consulted only AFTER training rows exist. Check identities
    # and exact question/proposal/observation copies; never generate from gold.
    evaluation=readl(vd/'evaluation_cases24.jsonl')
    eval_env={digest({'role':c['role'],'packet':c['packet']}) for c in evaluation}
    eval_obs={x['text'] for c in evaluation for x in c['packet']['case_packet']['evidence']}
    for c in cases:
        need(digest({'role':c['role'],'packet':c['packet']}) not in eval_env,'Exact eval input overlap')
        need(all(x['text'] not in eval_obs for x in c['packet']['case_packet']['evidence']),'Evaluation observation copied')
    frozen={}
    paths=[PARENT,str(Path(PARENT).with_suffix('.manifest.json')),E2RUN,AUDIT,'new_source_reason_v10.py',
       'data/action_schema_v02.json',V10+'/manifest.json',V10+'/evaluation_cases24.jsonl',
       V10+'/inputs_baseline24.jsonl',V10+'/results/baseline.jsonl',V10+'/comparison.json']
    paths += [str(p.relative_to(root)) for p in sorted((root/'dcurr').glob('*.py'))]
    before='data/evidence_probe_v04/cases_before.jsonl'
    # Actual path comes from the measured v05 plan, not a filename guess.
    oldplan=readj(root/'data/evidence_training_v05/manifest.json')
    before=oldplan['eval_files']['before'];need(local(root,before).is_file(),'Missing earlier position-regression cases')
    paths += [before,'data/evidence_training_v05/manifest.json']
    for p in ('data/review_decisions.csv','data/source_review.csv'):
        need(local(root,p).is_file(),'Missing source/review provenance');paths.append(p)
    for p in paths:frozen[p]=sha(local(root,p))
    contract_runner=root.parent/'eval/run_eval40_qwen35.py';need(contract_runner.is_file(),'Existing Contract runner missing')
    d.mkdir(parents=True);(d/'logs').mkdir();(d/'results').mkdir()
    writel(d/'new_cases36_AI_candidate.jsonl',cases)
    (d/'AI_REVIEW_KO.md').write_text(review_md(cases),encoding='utf-8')
    writej(d/'source_registry.json',SPEC['sources'])
    release={'author_type':'AI','human_review_performed':False,'engineering_approved':False,
       'experimental_training_use_authorized_by_cli':True,
       'not_formal_source_or_training_signoff':True,'created_at_utc':now(),
       'meaning':'Explicit experiment use of AI-authored synthetic candidates, without changing existing human review files.'}
    writej(d/'experimental_release.json',release)
    configs={}
    for arm,rs in arms.items():
        p=d/(arm+'246.jsonl');writel(p,rs)
        sidecar={'build':VERSION,'data_sha256':sha(p),'records':246,'contract_records':150,
            'physics_records':96,'unique_physics_synthetic_states':20 if arm=='repeat' else 56,
            'related_physics_pairs':10 if arm=='repeat' else 28,
            'source_ids':dm['source_ids'],'program_groups':sorted(set(dm.get('program_groups',[])) | {g for row in rs for g in row.get('metadata',{}).get('program_groups',[])}),
            'parent_source_program_groups':dm.get('program_groups',[]),
            'prompt_file_sha256':dm['prompt_file_sha256'],'legacy_prompt_sha256':dm['legacy_prompt_sha256'],
            'system_prompt_hashes':sorted({hashlib.sha256(x['messages'][0]['content'].encode()).hexdigest() for x in rs}),
            'parent_training_data':PARENT,'parent_training_data_sha256':PARENT_SHA,
            'parent_data_manifest_sha256':sha(parent_path.with_suffix('.manifest.json')),
            'experimental_release_file':str((d/'experimental_release.json').relative_to(root)),
            'experimental_release_sha256':sha(d/'experimental_release.json'),
            'original_review_csv_sha256':frozen['data/review_decisions.csv'],
            'original_source_review_sha256':frozen['data/source_review.csv'],
            'new_rows_authorship':'AI synthetic candidates' if arm=='coverage' else 'Replay of existing rows',
            'separation_note':'NS10 input/labels not used as training rows. NS10 is now an error-informed development/regression set, not an untouched holdout.'}
        writej(p.with_suffix('.manifest.json'),sidecar)
        configs[arm]={'data':str(p.relative_to(root)),'adapter':'runs/'+slug+'_'+arm+'_e2','exposure':exposure(rs)}
    for code in ABSENT:need(configs['coverage']['exposure']['supervised_reason_rows'].get(code)==2,'New missing-code coverage not as planned')
    generated={p.name:sha(p) for p in d.iterdir() if p.is_file()}
    m={'version':VERSION,'script_sha256':sha(Path(__file__)),'spec_sha256':digest(SPEC),'created_at_utc':now(),
      'model':MODEL,'revision':REVISION,'lr':5e-5,'rank':16,'epochs':2,'seed':42,'max_length':2048,'max_new_tokens':384,
      'frozen_files':frozen,'generated_files':generated,'arms':configs,'v10_dir':V10,'v10_cases':str((vd/'evaluation_cases24.jsonl').relative_to(root)),
      'v10_inputs':str((vd/'inputs_baseline24.jsonl').relative_to(root)),'before_cases':before,
      'contract_runner_sha256':sha(contract_runner),'data_changed':False,'training_executed':False,
      'interpretation':'Matched extra row/action control; new semantic examples and reason labels are a joint intervention. Token counts differ. One seed; no capacity-limit or causal proof.'}
    writej(d/'manifest.json',m)
    print('REASON COVERAGE PREPARE: PASS\n2 arms x 246 rows. New candidate states=36 (18 pairs). No model load.\nNext: train -> evaluate -> compare')

def plan(root,outdir):
    d=local(root,outdir);m=readj(d/'manifest.json')
    need(m['version']==VERSION and m['script_sha256']==sha(Path(__file__)) and m['spec_sha256']==digest(SPEC),'Script/spec changed since prepare')
    for p,x in m['frozen_files'].items():need(sha(local(root,p))==x,'Frozen input changed: '+p)
    for p,x in m['generated_files'].items():need(sha(d/p)==x,'Prepared file changed: '+p)
    need(sha(root.parent/'eval/run_eval40_qwen35.py')==m['contract_runner_sha256'],'Contract runner changed')
    return d,m

def logged(root,args,path,cwd=None):
    need(not path.exists(),'Log exists: '+str(path));print('\nRUN:', ' '.join(map(str,args)),flush=True)
    env=dict(os.environ);env['PYTHONHASHSEED']='42'
    with path.open('x',encoding='utf-8') as f:
        process=subprocess.Popen(args,cwd=cwd or root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        for line in process.stdout:print(line,end='',flush=True);f.write(line);f.flush()
        rc=process.wait()
    need(rc==0,f'Command failed ({rc}); preserved log: {path}')
    return path.read_text(encoding='utf-8')

def preflight_pass(text,rows):
    dec=json.JSONDecoder();found=[]
    for linepos in [i for i,c in enumerate(text) if c=='{']:
        try:x,_=dec.raw_decode(text[linepos:])
        except json.JSONDecodeError:continue
        if isinstance(x,dict) and x.get('status')=='PASS' and x.get('records')==rows:found.append(x)
    need(found and found[-1].get('silent_truncation') is False,'Preflight did not report required rows and no truncation')
    return found[-1]

def trained(root,d,m,arm):
    x=readj(d/(arm+'.train_complete.json'));out=local(root,m['arms'][arm]['adapter'])
    for p,v in x['files'].items():need(sha(out/p)==v,'Completed model artifact changed: '+arm+'/'+p)
    need(x['manifest_sha256']==sha(d/'manifest.json'),'Training receipt belongs to another plan');return x

def train(root,outdir):
    d,m=plan(root,outdir);pf=d/'preflight.json'
    if not pf.exists():
        stats={}
        for arm in ARMS:
            text=logged(root,[sys.executable,'-m','dcurr.preflight','--data',m['arms'][arm]['data'],'--max-length',str(m['max_length']),'--model',MODEL,'--revision',REVISION],d/'logs'/('preflight_'+arm+'.log'))
            stats[arm]=preflight_pass(text,246)
        writej(pf,{'manifest_sha256':sha(d/'manifest.json'),'arms':stats,'note':'Input and supervised token counts need not match; both are recorded.'})
    else:need(readj(pf)['manifest_sha256']==sha(d/'manifest.json'),'Preflight identity mismatch')
    for arm in ARMS:
        done=d/(arm+'.train_complete.json')
        if done.exists():trained(root,d,m,arm);print('SKIP VERIFIED COMPLETED',arm);continue
        out=local(root,m['arms'][arm]['adapter']);need(not out.exists(),'Existing run preserved; choose a new experiment folder AND new run paths, no implicit resume.')
        logged(root,[sys.executable,'-m','dcurr.train','--data',m['arms'][arm]['data'],'--out',str(out),'--model',MODEL,'--revision',REVISION,'--epochs','2','--lr','5e-5','--rank','16','--max-length','2048'],d/'logs'/('train_'+arm+'.log'))
        names=['adapter_model.safetensors','adapter_config.json','RUN_MANIFEST.json','TRAIN_RESULT.json']
        need(all((out/p).is_file() for p in names),'Trainer output incomplete: '+arm)
        rm=readj(out/'RUN_MANIFEST.json');need(rm['data_manifest']['data_sha256']==sha(local(root,m['arms'][arm]['data'])),'Trainer used wrong data')
        need(rm.get('rank')==16 and rm.get('lr')==5e-5 and rm.get('epochs_requested')==2,'Trainer settings mismatch')
        need(readj(out/'adapter_config.json').get('r')==16,'Adapter rank mismatch')
        writej(done,{'arm':arm,'at_utc':now(),'manifest_sha256':sha(d/'manifest.json'),'files':{p:sha(out/p) for p in names}})
    print('BOTH TRAINING RUNS COMPLETE. Next: evaluate')

def eval_worker(root,outdir,arm):
    d,m=plan(root,outdir);receipt=trained(root,d,m,arm);h=helper(root);common,prompts=h.modules(root)
    os.chdir(root)
    from transformers import set_seed
    set_seed(42)
    inputs=readl(local(root,m['v10_inputs']));tracepath=d/'results'/(arm+'_ns10.prompt_trace.jsonl')
    need(not tracepath.exists(),'Existing incomplete trace preserved')
    original,trace=h.install_hook(prompts,'baseline',inputs,tracepath)
    result=d/'results'/(arm+'_ns10.jsonl')
    sys.argv=['dcurr.evaluate','--cases',m['v10_cases'],'--adapter',m['arms'][arm]['adapter'],'--out',str(result),'--model',MODEL,'--revision',REVISION,'--max-new-tokens','384','--purpose','CANDIDATE_DIAGNOSTIC']
    try:runpy.run_module('dcurr.evaluate',run_name='__main__')
    finally:prompts.build_messages=original
    need(len(trace)==24,'Not 24 verified input calls')
    need(set(idx(readl(result)))==set(idx(readl(local(root,m['v10_cases'])))),'Incomplete NS10 output')

def eval_job(root,d,m,arm,suite):
    result=d/'results'/(arm+'_'+suite+'.jsonl');done=d/'results'/(arm+'_'+suite+'.complete.json')
    receipt=trained(root,d,m,arm)
    if done.exists():
        record=readj(done)
        need(record['model_sha256']==receipt['files']['adapter_model.safetensors'],'Evaluation model differs')
        need(record['manifest_sha256']==sha(d/'manifest.json'),'Evaluation plan differs')
        for p,x in record['files'].items():need(sha(d/'results'/p)==x,'Evaluation artifact changed')
        return
    need(not result.exists(),'Incomplete output exists; preserve it: '+str(result))
    if suite=='ns10':
        args=[sys.executable,str(Path(__file__).resolve()),'_eval-worker','--root',str(root),'--outdir',str(d.relative_to(root)),'--arm',arm]
        logged(root,args,d/'logs'/(arm+'_'+suite+'.log'));cases=readl(local(root,m['v10_cases']))
    elif suite=='before':
        args=[sys.executable,'-m','dcurr.evaluate','--cases',m['before_cases'],'--adapter',m['arms'][arm]['adapter'],'--out',str(result),'--model',MODEL,'--revision',REVISION,'--max-new-tokens','384','--purpose','CANDIDATE_DIAGNOSTIC']
        logged(root,args,d/'logs'/(arm+'_'+suite+'.log'));cases=readl(local(root,m['before_cases']))
    else:raise ValueError('Unknown evaluation suite')
    need(set(idx(readl(result)))==set(idx(cases)),'Incomplete evaluation set')
    sm=readj(result.with_suffix('.summary.json'))
    expectedcase=m['v10_cases'] if suite=='ns10' else m['before_cases']
    for key,val in {'records':len(cases),'model':MODEL,'adapter_sha256':receipt['files']['adapter_model.safetensors'],'case_file_sha256':sha(local(root,expectedcase))}.items():need(sm.get(key)==val,'Evaluator identity differs: '+key)
    paths=[result,result.with_suffix('.summary.json')]
    if suite=='ns10':paths += [d/'results'/(arm+'_ns10.prompt_trace.jsonl')]
    writej(done,{'manifest_sha256':sha(d/'manifest.json'),'model_sha256':receipt['files']['adapter_model.safetensors'],'files':{p.name:sha(p) for p in paths}})

def evaluate(root,outdir):
    d,m=plan(root,outdir)
    for arm in ARMS:
        for suite in ('ns10','before'):eval_job(root,d,m,arm,suite)
        label=d.name+'_'+arm+'_contract';p=root.parent/'eval/results'/(label+'_dev.jsonl')
        dest=d/'results'/(arm+'_contract.jsonl');done=d/'results'/(arm+'_contract.complete.json')
        if done.exists():
            rec=readj(done)
            need(sha(dest)==rec['result_sha256'] and rec['manifest_sha256']==sha(d/'manifest.json') and rec['adapter_sha256']==trained(root,d,m,arm)['files']['adapter_model.safetensors'],'Contract snapshot/model changed')
            continue
        need(not p.exists() and not dest.exists(),'Existing Contract result preserved: '+str(p))
        args=[sys.executable,'-m','eval.run_eval40_qwen35','--split','dev','--adapter',str(local(root,m['arms'][arm]['adapter'])),'--label',label]
        logged(root,args,d/'logs'/(arm+'_contract.log'),cwd=root.parent)
        rr=readl(p);need(len(rr)==20,'Incomplete Contract dev');idx(rr,'id')
        dest.write_bytes(p.read_bytes())
        writej(done,{'result_sha256':sha(dest),'origin_path':str(p),'adapter_sha256':trained(root,d,m,arm)['files']['adapter_model.safetensors'],'manifest_sha256':sha(d/'manifest.json')})
    print('ALL EVALUATIONS COMPLETE. Next: compare')

def regression_score(h, common, case, row):
    """Honor the already-declared alternate gold sets; do not rewrite them."""
    primary=h.score(common,case,row)
    variants=case.get('acceptable_answers') or [case['expected']]
    scored=[]
    for answer in variants:
        branch=copy.deepcopy(case);branch['expected']=answer
        scored.append(h.score(common,branch,row))
    primary['reference_exact']=any(r['reference_exact'] for r in scored)
    primary['strict_contract_pass']=any(r['strict_contract_pass'] for r in scored)
    return primary


def compare(root,outdir):
    d,m=plan(root,outdir);h=helper(root);common,_=h.modules(root)
    need(not (d/'comparison.json').exists(),'Comparison already exists; preserve it')
    v10rows=idx(readl(local(root,m['v10_cases'])));baseline_raw=idx(readl(local(root,V10+'/results/baseline.jsonl')))
    baseline={cid:h.score(common,c,baseline_raw[cid]) for cid,c in v10rows.items()}
    result={'version':VERSION,'at_utc':now(),'original_e2_ns10':h.summarise(list(baseline.values())),'arms':{},'interpretation':m['interpretation'],
      'evaluation_status':'NS10 is error-informed development/regression, not a new untouched holdout. Old 40 is same-source regression.',
      'authorship':'AI-authored new synthetic targets; no human engineering signoff.'}
    caseout=[];byarm={}
    for arm in ARMS:
        for suite in ('ns10','before'):
            # Only verifies completed artifacts; never runs inference in compare.
            need((d/'results'/(arm+'_'+suite+'.complete.json')).exists(),'Run evaluate first')
            eval_job(root,d,m,arm,suite)
        rr=idx(readl(d/'results'/(arm+'_ns10.jsonl')))
        scores={cid:h.score(common,c,rr[cid]) for cid,c in v10rows.items()};byarm[arm]=scores
        view={'ns10':h.summarise(list(scores.values())),'by_source':{},'exposure':m['arms'][arm]['exposure']}
        for source in sorted({r['source_id'] for r in v10rows.values()}):view['by_source'][source]=h.summarise([scores[cid] for cid,c in v10rows.items() if c['source_id']==source])
        bs=idx(readl(d/'results'/(arm+'_before.jsonl')));bc=idx(readl(local(root,m['before_cases'])))
        view['before40']=h.summarise([regression_score(h,common,c,bs[cid]) for cid,c in bc.items()])
        cp=d/'results'/(arm+'_contract.jsonl');cr=readj(d/'results'/(arm+'_contract.complete.json'))
        need(sha(cp)==cr['result_sha256'] and cr['manifest_sha256']==sha(d/'manifest.json'),'Contract receipt mismatch')
        need(cr['adapter_sha256']==trained(root,d,m,arm)['files']['adapter_model.safetensors'],'Contract used another adapter')
        cs=readl(cp);view['contract20']={'cases':len(cs),'pass':sum(x.get('pass') is True for x in cs),'action_correct':sum(x.get('action_ok') is True for x in cs)}
        result['arms'][arm]=view
    for cid,c in v10rows.items():
        a=byarm['repeat'][cid];b=byarm['coverage'][cid]
        caseout.append({'case_id':cid,'pair_id':c['pair_id'],'source_id':c['source_id'],'original_e2':baseline[cid],'repeat':a,'coverage':b,'gain_over_repeat':not a['strict_contract_pass'] and b['strict_contract_pass'],'loss_vs_repeat':a['strict_contract_pass'] and not b['strict_contract_pass']})
    result['paired_gain_over_repeat']=sum(x['gain_over_repeat'] for x in caseout);result['paired_loss_vs_repeat']=sum(x['loss_vs_repeat'] for x in caseout)
    result['counts_note']='36 new states belong to 18 pairs. Both arms=246 rows, 150 Contract + 96 Physics presentations; not 246 independent physical tests.'
    writej(d/'comparison.json',result);writel(d/'comparison_cases.jsonl',caseout)
    lines=['# v12 reason coverage comparison','',result['interpretation'],'', '|Metric|Original e2|Repeat control|Coverage|','|---|---:|---:|---:|']
    for key in ('action_correct','reference_exact','strict_contract_pass','wrongly_accepts_refuted_proposal','unnecessary_intervention'):
        lines.append('|'+key+'|'+str(result['original_e2_ns10'][key])+'|'+str(result['arms']['repeat']['ns10'][key])+'|'+str(result['arms']['coverage']['ns10'][key])+'|')
    lines+=['','Reason 동시 정답은 comparison.json의 reason_joint_correct에서 분모와 함께 확인.',
       '범위 게이트/프롬프트는 동일. 추가 설명 없음. 분류기준을 결과를 보고 바꾸거나 오답을 후처리하지 않음.',
       '대조군도 좋아지면 추가 학습 노출의 효과가 포함된다. 보강군만 좋더라도 한 seed·관련 시나리오이므로 독립 일반화나 2B 용량 결론이 아니다.',
       '', '## Contract / before40 regression',json.dumps({a:{k:result['arms'][a][k] for k in ('contract20','before40')} for a in ARMS},ensure_ascii=False,indent=2)]
    (d/'RESULTS_KO.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));print('Saved:',d/'comparison.json',d/'comparison_cases.jsonl')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','train','evaluate','compare','_eval-worker']);p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--outdir',default=OUTDIR);p.add_argument('--arm',choices=ARMS);p.add_argument('--accept-ai-authored-training-candidates',action='store_true');a=p.parse_args();root=a.root.resolve()
    try:
        if a.command=='prepare':prepare(root,a.outdir,a.accept_ai_authored_training_candidates)
        elif a.command=='train':train(root,a.outdir)
        elif a.command=='evaluate':evaluate(root,a.outdir)
        elif a.command=='compare':compare(root,a.outdir)
        else:need(a.arm is not None,'--arm required');eval_worker(root,a.outdir,a.arm)
    except (ValueError,KeyError,FileNotFoundError,ImportError,TypeError) as e:
        print('STOP:',e,file=sys.stderr);print('Existing artifacts preserved; do not overwrite them to hide a mismatch.',file=sys.stderr);raise SystemExit(1)

# SPEC is embedded so only this script needs to be copied. It contains original
# source principles and NEW synthetic training scenarios, not NS10 evaluation rows.
SPEC = {'references': {'mapping': {'source_id': 'TH-01', 'printed_pages': ['59'], 'pdf_pages_1based': [68], 'section': 'Canister Correlations', 'text': 'Calculated television-camera temperatures represented average case temperatures, whereas internal thermocouples measured heater temperatures for which corresponding models were absent.'}, 'power': {'source_id': 'TH-01', 'printed_pages': ['29', '62'], 'pdf_pages_1based': [38, 71], 'section': 'On-Site Thermal Support; Conclusions', 'text': 'Individual component power estimates were weakened by shared power buses and long measurement leads. The report emphasizes knowing both dissipation rates and heat-source locations for correlation.'}, 'modal': {'source_id': 'VB-X1', 'printed_pages': ['362'], 'pdf_pages_1based': [4], 'section': 'Section 4.1.1 Mathematical model', 'text': 'The stated CSMA load description includes total mass, fixed-interface natural frequencies, modal effective and residual masses, damping, and translational apparent-mass information.'}, 'exposure': {'source_id': 'EE-03', 'printed_pages': [], 'pdf_pages_1based': [7], 'section': '8 Data Requirements', 'text': 'The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.'}, 'observation': {'source_id': 'EE-02', 'printed_pages': [], 'pdf_pages_1based': [14], 'section': '1.6 Pass/Fail criteria', 'text': 'The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.'}, 'force': {'source_id': 'VB-X1', 'section': 'Introduction following Eq. (1)', 'printed_pages': ['360'], 'pdf_pages_1based': [2], 'text': 'The coefficient C^2 in the semi-empirical force-limit relation depends on configuration and needs an adequate justification for its selection.'}, 'method': {'source_id': 'VB-X1', 'section': 'Section 2, Equation (2)', 'printed_pages': ['360'], 'pdf_pages_1based': [2], 'text': 'Equation (2) defines C^2 as the maximum interface-force PSD divided by the total load mass squared and the maximum interface-acceleration PSD. These two maxima need not occur at the same frequency.'}}, 'topics': [{'topic_id': 'C1', 'fact_key': 'exposure', 'reason': 'CONFIGURATION_SCOPE_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['AS_TESTED_OPERATING_CONFIGURATION'], 'question': 'Are the bias and operating-mode settings traceable to the identified irradiation run? Review operating-configuration records only; exposure and event coverage are already available.', 'proposal': 'Complete the as-tested operating-configuration record check for this run.', 'negative': 'The exposure file and event time series are complete and linked to this run. The electrical setup form has empty bias and operating-mode entries. The specimen label and run identifier are present; neither missing setting can be recovered from another record.', 'positive': 'The exposure file and event time series are complete and linked to this run. The electrical setup form records the applied bias and operating mode, and its header matches the specimen and run identifiers.', 'review_ko': '노출·관측 자료는 유지하고 시험 당시 전기적 구성 기록만 바꾼다. 없는 항목은 노출량이나 파형이 아닌 bias/운용모드이므로 구성 추적성 분류를 사용한다. 범위키 존재와 실제 설정 기록의 완전성은 다르다.'}, {'topic_id': 'C2', 'fact_key': 'exposure', 'reason': 'CONFIGURATION_SCOPE_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['RUN_TO_SETUP_REVISION_LINK'], 'question': 'Can the electrical setup revision actually used in this run be identified? The check is traceability of the run to the setup, not a radiation-effects verdict.', 'proposal': 'Resolve the run-to-electrical-setup linkage before interpreting the result.', 'negative': 'Two signed electrical setup sheets list different bias and mode settings. The run log identifies the specimen and contains complete exposure and event records, but contains no sheet identifier or revision link. Both setup sheets remain plausible; the supplied package contains no other linkage.', 'positive': 'Two signed electrical setup sheets list different bias and mode settings. The run log identifies the specimen, contains complete exposure and event records, and explicitly names which setup-sheet revision was used during the interval.', 'review_ko': '기록이 둘 다 존재해도 실제 사용한 설정을 대응할 수 없으면 구성 연결 자료를 요청한다. 양쪽 설정이 모두 잘못됐다는 판단이나 관측 범위 부족으로 바꾸지 않는다.'}, {'topic_id': 'X1', 'fact_key': 'exposure', 'reason': 'EXPOSURE_METADATA_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['RUN_INTEGRATED_FLUENCE'], 'question': 'Is the run-integrated particle fluence available? The electrical operating configuration and event-monitoring coverage are established; do not assess event susceptibility.', 'proposal': 'Complete the exposure-data availability check for this irradiation interval.', 'negative': 'The run package identifies the ion and geometry and includes electrical settings and continuous event monitoring. The integrated particle fluence is not recorded, and no calibrated beam history permitting its reconstruction is available.', 'positive': 'The run package identifies the ion and geometry and includes electrical settings and continuous event monitoring. A beam-log entry supplies the integrated particle fluence and is linked to the same run interval.', 'review_ko': '이벤트 수·설정 기록과 입자 노출량은 별개다. 이 쌍은 fluence의 가용성만 바꾸며, 자료가 없다는 이유로 모니터링 자체가 없었다고 판단하지 않는다.'}, {'topic_id': 'X2', 'fact_key': 'exposure', 'reason': 'EXPOSURE_METADATA_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['ION_AND_INCIDENCE_GEOMETRY'], 'question': 'Are the ion identity and incidence geometry recorded for this run? Limit the check to the exposure record.', 'proposal': 'Complete the exposure-record checklist before combining this result with other runs.', 'negative': 'Electrical settings, integrated fluence and event logs are linked to the run. The ion-species field and incidence-angle field are blank. No beamline geometry sheet or facility entry resolves those fields.', 'positive': 'Electrical settings, integrated fluence and event logs are linked to the run. The exposure sheet names the ion species and incidence geometry, and the facility entry links those fields to this interval.', 'review_ko': '전기적 조건은 충분한 상태로 유지한다. 이온·입사 형상은 노출 메타데이터이며, 여기서는 LET 변환이나 이벤트 단면적을 계산하지 않는다.'}, {'topic_id': 'I1', 'fact_key': 'method', 'reason': 'METHOD_INTERPRETATION_ERROR', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the described scalar reduction implement Equation (2) in the cited method? All required spectra and mass data are supplied. Check the calculation rule, not the numerical result.', 'proposal': 'Use this reduction as an implementation of the cited equation for C^2.', 'negative': 'The force PSD and acceleration PSD attain their separate global maxima at different frequencies. The implementation takes the maximum force PSD but uses the acceleration PSD at that force-peak frequency in the denominator, even though it is smaller than the maximum acceleration PSD. The measured mass is squared in the denominator.', 'positive': 'The force PSD and acceleration PSD attain their separate global maxima at different frequencies. The implementation uses the separate maximum of each spectrum and divides the force maximum by the measured mass squared times the acceleration maximum.', 'review_ko': '입력이 없거나 모드를 식별하지 못한 문제가 아니다. 두 스펙트럼의 독립 최댓값을 사용하는 식과 다른 연산을 수행했으므로 방법 적용 오류다. 특정 평가 문제의 RMS·힘제어 사례를 가져오지 않았다.'}, {'topic_id': 'I2', 'fact_key': 'method', 'reason': 'METHOD_INTERPRETATION_ERROR', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the stated mass dependence match Equation (2) of the cited reduction? Input quantities and their units are known.', 'proposal': 'Accept the described reduction as algebraically consistent with the cited equation for C^2.', 'negative': 'The implementation uses the separate maxima of the force and acceleration PSDs. Its denominator contains the measured total mass to the first power multiplied by the acceleration maximum. It labels that result C^2; no other mass factor or unit conversion is applied.', 'positive': 'The implementation uses the separate maxima of the force and acceleration PSDs. Its denominator contains the measured total mass squared multiplied by the acceleration maximum. Consistent units are used throughout.', 'review_ko': '질량값·스펙트럼은 있고 질량의 지수만 다르다. 데이터 해석이나 선정근거 부족이 아니라 명시된 식을 구현한 방법의 일치 여부를 판단한다.'}, {'topic_id': 'Q1', 'fact_key': 'mapping', 'reason': 'MEASUREMENT_MAPPING_MISMATCH', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the reported temperature represent the same spatial quantity as the model output used in this comparison?', 'proposal': 'Compare the reported temperature directly with the modeled casing-average temperature.', 'negative': 'The reported channel is a single internal actuator-heater junction measurement. The model output averages the outer casing surface. No transfer model maps the heater junction to the casing average; boundary inputs and timing are otherwise documented.', 'positive': 'The reported channel is a weighted aggregate of outer-casing surface measurements. The model output uses the same locations and weights for its casing average. Boundary inputs and timing are documented.', 'review_ko': '경계 입력은 명시적으로 주어져 있으며 직접적인 차이는 측정 대상과 공간 집계다. 단위가 같은 온도값도 대응관계가 다르면 직접 비교를 반박한다.'}, {'topic_id': 'Q2', 'fact_key': 'mapping', 'reason': 'MEASUREMENT_MAPPING_MISMATCH', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Is the measurement-to-model mapping consistent for the stated surface-temperature statistic? Check mapping only.', 'proposal': 'Use the reported surface statistic as the directly corresponding measurement for the model statistic.', 'negative': 'The model statistic is an area-weighted average over six casing regions. The reported statistic is the temperature of only the hottest sampled region. Both are time-aligned and calibrated, but there is no mapping from that maximum-region statistic to the surface average.', 'positive': 'The model statistic is an area-weighted average over six casing regions. The reported statistic applies the same six region weights to the corresponding calibrated, time-aligned surface measurements.', 'review_ko': '최댓값과 평균의 공간 집계 대상이 다른 상황이다. RMS 연산 오류 사례와 다르게 여기서는 각 통계량 자체가 잘못 계산됐다고 하지 않고 대응관계만 검토한다.'}, {'topic_id': 'L1', 'fact_key': 'modal', 'reason': 'MODAL_INPUTS_MISSING', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['RESIDUAL_MASS_TERMS'], 'question': 'Is the listed load-model input package complete for residual-mass terms in the cited CSMA formulation? Damping and other listed inputs are available.', 'proposal': 'Complete this load-input availability check before running the coupled model.', 'negative': 'Total mass, fixed-interface frequencies, modal effective masses, damping and translational apparent-mass data are supplied. The residual-mass terms are absent. The package states that the retained-mode data do not permit these missing terms to be recovered.', 'positive': 'Total mass, fixed-interface frequencies, modal effective masses, damping and translational apparent-mass data are supplied. Direction-specific residual-mass terms are also tabulated and mapped to the load configuration.', 'review_ko': '모달 입력 항목 중 잔여질량만 누락시킨다. 추정값을 임의로 채우지 않고 그 항목을 요청하며, 제공됐을 때는 입력 존재 검사만 종료한다.'}, {'topic_id': 'L2', 'fact_key': 'modal', 'reason': 'MODAL_INPUTS_MISSING', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['MODAL_DAMPING_ASSIGNMENT'], 'question': 'Are the required modal damping inputs available for the cited load model? Check availability, not the correctness of the damping magnitudes.', 'proposal': 'Complete the modal-input checklist for this calculation package.', 'negative': 'The package contains total mass, fixed-interface frequencies, effective and residual masses, and apparent-mass information. The damping-assignment table is absent and no damping assumptions are recorded elsewhere.', 'positive': 'The package contains total mass, fixed-interface frequencies, effective and residual masses, and apparent-mass information. It also assigns a measured or justified assumed damping ratio to each modeled mode.', 'review_ko': '감쇠 가정 자체가 없는 것과 감쇠값의 정확도를 검증하지 못한 것은 다르다. 여기서는 전자에만 자료 요청을 붙인다.'}, {'topic_id': 'F1', 'fact_key': 'force', 'reason': 'FORCE_LIMIT_BASIS_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['CURRENT_INTERFACE_C2_JUSTIFICATION'], 'question': 'Is the choice of C^2 justified for the current load/support configuration? Input spectra, mass, modal data and as-tested identity are already available.', 'proposal': 'Complete the coefficient-selection-basis check before accepting the proposed force-limit envelope.', 'negative': 'The selected coefficient is copied from a differently mounted load. The current mounting and load identities are known and documented, but the package includes no derivation or equivalence justification linking that choice to the current interface dynamics.', 'positive': 'The selected coefficient is accompanied by a documented derivation tied to the current load and support dynamics. The record explicitly identifies the current mounting and load, with stated assumptions and a sensitivity check.', 'review_ko': '형상이 무엇인지 몰라서가 아니라, 알려진 현재 형상에 C²를 적용할 선정근거가 없다. 다른 장비 값을 복사했다는 이유만으로 무조건 잘못된 수치라고 확정하지 않고 질문 범위의 근거를 요청한다.'}, {'topic_id': 'F2', 'fact_key': 'force', 'reason': 'FORCE_LIMIT_BASIS_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['C2_SELECTION_DECISION_RECORD'], 'question': 'Is the engineering basis for selecting C^2 traceable in this record package? Other calculation inputs are complete.', 'proposal': 'Complete the rationale check for the chosen semi-empirical coefficient.', 'negative': 'A coefficient value and the current test-article identifiers are filled in. The rationale field contains only the words standard choice. There is no referenced experience dataset, analysis or written justification for this configuration.', 'positive': 'A coefficient value and the current test-article identifiers are filled in. The rationale links to an experience dataset or analysis with an explicit applicability argument for this configuration and records the selection decision.', 'review_ko': 'C² 숫자 존재와 선정 근거 존재를 구분한다. 단순 표준값 문구는 현재 형상에의 적용 근거가 아니며, 존재하는 근거의 정량 적정성을 이 문제에서 새로 승인하지 않는다.'}, {'topic_id': 'P1', 'fact_key': 'power', 'reason': 'POWER_DISSIPATION_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['MODE_SPECIFIC_COMPONENT_DISSIPATIONS'], 'question': 'Are the component heat-source powers available for the stated operating mode? Heat-source locations and configuration identity are already mapped.', 'proposal': 'Complete the component heat-input availability check for this operating mode.', 'negative': 'All heat-source locations and component identifiers are mapped. Only the assembly input-current record is supplied. There are no component-level dissipated powers or a power-allocation model for this mode in the package.', 'positive': 'All heat-source locations and component identifiers are mapped. The package also tabulates the component-level dissipated powers for this mode, including the stated loss allocation and a reconciliation to the assembly record.', 'review_ko': '센서 coverage나 노출 메타데이터가 아닌 열원 크기의 입력 누락이다. 전체 입력을 임의 비율로 분할하는 가정은 넣지 않는다.'}, {'topic_id': 'P2', 'fact_key': 'power', 'reason': 'POWER_DISSIPATION_UNRESOLVED', 'action': 'REQUEST_EVIDENCE', 'request_ids': ['HEAT_SOURCE_TO_MODEL_LOCATION_MAP'], 'question': 'Can each recorded dissipation be assigned to its physical heat-source location in the thermal model? Review the heat-input mapping record only.', 'proposal': 'Complete the thermal heat-source input checklist before correlation.', 'negative': 'Component dissipated powers and operating modes are tabulated and linked to this configuration. The identifiers on the power sheet cannot be linked to the physical components or thermal nodes. No allocation or location map is supplied.', 'positive': 'Component dissipated powers and operating modes are tabulated and linked to this configuration. An allocation table links every sheet identifier to its physical component and corresponding thermal-model node.', 'review_ko': '측정 온도와 계산 온도의 대응 문제가 아니라 발열 입력의 공간 배치 누락이다. 위치표가 있으면 준비상태만 확인하며 열모델 상관 결과를 승인하지 않는다.'}, {'topic_id': 'O1', 'fact_key': 'observation', 'reason': 'MONITORING_COVERAGE_INSUFFICIENT', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does this package actually document observation of the channel throughout the applied disturbance? Check observation coverage, not a numerical acceptance threshold.', 'proposal': 'Describe this package as containing channel monitoring throughout the disturbance interval.', 'negative': 'The clock and stimulus log are aligned. Channel readings were taken immediately before and after the disturbance, but the acquisition system was disabled for the entire disturbance interval. No measurement of that interval exists.', 'positive': 'The clock and stimulus log are aligned. Channel acquisition spans the complete disturbance interval as well as the before-and-after reference intervals. The acquisition log shows no gap in coverage.', 'review_ko': '관측했지만 해석을 잘못한 경우가 아니라, 문제의 구간을 관측하지 않았다. 전체 구간 관측을 주장하는 proposal에 대한 검토이므로 자료 요청 action으로 기계적으로 바꾸지 않는다.'}, {'topic_id': 'O2', 'fact_key': 'observation', 'reason': 'MONITORING_COVERAGE_INSUFFICIENT', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the acquisition record substantiate continuous coverage of the channel during the specified stimulus sequence?', 'proposal': 'Use this package as evidence of complete channel observation during the specified stimulus sequence.', 'negative': 'The intended channels are identified and the available samples are valid. A recorder-status log identifies an acquisition gap covering one complete pulse group. No backup channel data cover that missing interval.', 'positive': 'The intended channels are identified and the samples are valid. The recorder-status log and timestamps cover every pulse group without gaps; the continuous stream is linked to the stimulus sequence.', 'review_ko': '다른 시간의 데이터가 정상이더라도 비관측 구간의 상태는 확인되지 않는다. 시험의 합격·불합격이 아니라 전체 구간 관측을 입증하는지에 한정한다.'}, {'topic_id': 'D1', 'fact_key': 'observation', 'reason': 'EVIDENCE_INTERPRETATION_ERROR', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the report sentence agree with the time-aligned measurements? The acquisition coverage is complete.', 'proposal': 'Describe the monitored channel as having remained at its pre-stimulus baseline throughout the stimulus.', 'negative': 'The continuous and time-aligned channel record shows a repeatable offset during each stimulus interval. It returns to baseline after the intervals. No acquisition gap or measurement-mapping ambiguity is reported.', 'positive': 'The continuous and time-aligned channel record stays at its pre-stimulus baseline during each stimulus interval and afterward. No acquisition gap or measurement-mapping ambiguity is reported.', 'review_ko': '관측 누락이 아니라 실제 시간기록과 보고 문장의 모순이다. 종료 후 정상 복귀는 자극 중 변화가 없었다는 결론의 근거가 아니다. 정량 EMC 합격기준을 새로 지정하지 않는다.'}, {'topic_id': 'D2', 'fact_key': 'observation', 'reason': 'EVIDENCE_INTERPRETATION_ERROR', 'action': 'CHALLENGE', 'request_ids': [], 'question': 'Does the proposed description match the archived continuous channel stream for this interval?', 'proposal': 'State that the archive contains no repeatable channel disturbance time-aligned with the applied excitation.', 'negative': 'The archive includes complete synchronized excitation and channel traces. Repeated excitation onsets coincide with repeated channel steps, and the observations are explicitly retained in the run report.', 'positive': 'The archive includes complete synchronized excitation and channel traces. It contains no repeatable channel step or excursion aligned with excitation in this interval.', 'review_ko': '측정은 이루어졌고 기록 내용이 제안을 지지·반박하는지만 바꾼다. 방법 구현 오류나 관측 범위 누락과 대비된다.'}], 'sources': {'TH-01': {'title': 'NASA-TN-D-6646 (existing TH-01)', 'url': 'https://ntrs.nasa.gov/api/citations/19720011230/downloads/19720011230.pdf', 'basis': 'Previously supplied and AI-reviewed packet excerpts; no new PDF inspection in v12.'}, 'VB-X1': {'title': 'Wijker et al. Force limited random vibration testing (2015)', 'url': 'https://link.springer.com/article/10.1007/s12567-015-0086-0', 'basis': 'Supplied modal-input excerpt; Eq. (2), configuration rationale and load-input prose rechecked in the publisher HTML on 2026-09-20. No chart/table data used.'}, 'EE-02': {'title': 'Existing AMSU EMI/EMC report', 'url': 'https://ntrs.nasa.gov/api/citations/20000021554/downloads/20000021554.pdf', 'basis': 'Previously supplied and AI-reviewed interval-comparison excerpt. No new PDF inspection in v12.'}, 'EE-03': {'title': 'Existing OPA855 SEE report', 'url': 'https://ntrs.nasa.gov/api/citations/20230009783/downloads/OPA855_OpAmp_LBNL_20221111_SEE-TestReport_v3.pdf', 'basis': 'Previously supplied and AI-reviewed data-requirements excerpt. No new PDF inspection in v12.'}}, 'author_type': 'AI', 'human_review_performed': False, 'real_measurements': False}

if __name__ == "__main__": main()
