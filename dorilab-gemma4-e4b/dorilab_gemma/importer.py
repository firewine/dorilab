from __future__ import annotations
import copy, importlib, json, os, shutil, subprocess, sys
from pathlib import Path
from .common import *
from .scoring import score, aggregate

EXTENSIONS={'.json','.jsonl','.csv','.py','.md','.txt'}
SKIP={'__pycache__','results','reports','logs','.git','.venv','hf-cache','runs','adapters','sources'}

def copy_file(source,dest,inventory):
    source=Path(source).resolve();dest=Path(dest)
    require(source.is_file(),f'Missing source file: {source}')
    dest.parent.mkdir(parents=True,exist_ok=True)
    require(not dest.exists(),f'Will not overwrite: {dest}')
    before=sha(source);shutil.copyfile(source,dest)
    require(sha(dest)==before==sha(source),f'File changed during copy: {source}')
    inventory.append({'origin':str(source),'copy':str(dest),'sha256':before})

def mirror_tree(source,dest,inventory,extension_filter=True):
    source=Path(source)
    if not source.is_dir():return
    for directory,dirs,files in os.walk(source):
        dirs[:]=[x for x in dirs if x not in SKIP and not (Path(directory)/x).is_symlink()]
        for name in files:
            p=Path(directory)/name
            if p.is_symlink() or (extension_filter and p.suffix not in EXTENSIONS):continue
            require(p.stat().st_size<32*1024**2,f'Unexpected large metadata file: {p}')
            copy_file(p,Path(dest)/p.relative_to(source),inventory)

def old_modules(root):
    for name in list(sys.modules):
        if name=='dcurr' or name.startswith('dcurr.'):del sys.modules[name]
    sys.path.insert(0,str(root))
    c=importlib.import_module('dcurr.common');p=importlib.import_module('dcurr.prompts')
    require(Path(p.__file__).resolve()==root/'dcurr/prompts.py','Wrong copied prompts module')
    return c,p

def build(source: Path, root: Path, arm='repeat'):
    source=source.resolve();root=root.resolve();d=root/'data'
    require((source/'dcurr/prompts.py').is_file(),'--source must point to DoriLab_SourceCurriculum_v02')
    require(not root.is_relative_to(source) and not source.is_relative_to(root),'New project must be separate from the old project')
    require(not (d/'IMPORT_MANIFEST.json').exists(),'Import already complete')
    require(not (root/'snapshot').exists(),'Partial snapshot preserved. Use a fresh extracted folder for a new import.')
    v12=read_json(source/'data/reason_coverage_v12/manifest.json')
    data_file=inside(source,v12['arms'][arm]['data'])
    meta=read_json(data_file.with_suffix('.manifest.json'));train=read_jsonl(data_file)
    require(len(train)==meta['records']==246,'Expected the existing 246-row export')
    require(meta['data_sha256']==sha(data_file),'Training dataset hash mismatch')
    for key,filename in [('prompt_file_sha256','prompts.py'),('legacy_prompt_sha256','prompts_legacy.py')]:
        require(meta[key]==sha(source/'dcurr'/filename),'Source prompt changed since training export: '+filename)
    for row in train:messages_ok(row['messages'],True)
    index(train,'id')
    inv=[];mirror=root/'snapshot/legacy_parent';old=mirror/source.name
    # Small source/data snapshot only: no model, environment, or PDF copying.
    mirror_tree(source/'dcurr',old/'dcurr',inv)
    mirror_tree(source/'data',old/'data',inv)
    mirror_tree(source.parent/'runtime',mirror/'runtime',inv)
    mirror_tree(source.parent/'eval',mirror/'eval',inv)
    mirror_tree(source.parent/'data',mirror/'data',inv)
    require((mirror/'eval/run_eval40_qwen35.py').is_file(),'Legacy Contract runner missing')
    copy_file(data_file,d/'train.jsonl',inv)
    copy_file(data_file.with_suffix('.manifest.json'),d/'source_train.manifest.json',inv)
    schema_file=source/'data/action_schema_v02.json';copy_file(schema_file,d/'action_schema.json',inv)
    common,prompts=old_modules(old)
    schema=read_json(d/'action_schema.json')
    ns_cases=read_jsonl(inside(old,v12['v10_cases']))
    before_cases=read_jsonl(inside(old,v12['before_cases']))
    trace=read_jsonl(inside(old,v12['v10_inputs']))
    declared=index(trace)
    require(len(ns_cases)==24 and len(before_cases)==40,'Unexpected eval suite counts')
    evals={}
    for suite,cases in [('ns10',ns_cases),('before40',before_cases)]:
        rows=[]
        for case in cases:
            ms=prompts.build_messages(case['role'],case['packet'])
            messages_ok(ms,False)
            if suite=='ns10':
                require(ms==declared[case['case_id']]['messages'],'NS10 messages differ from recorded baseline')
            common.validate_answer(case['expected'],case)
            rows.append({'case_id':case['case_id'],'suite':suite,'messages':ms,'case':case,
                         'messages_sha256':digest(ms)})
        index(rows);evals[suite]=rows
        write_jsonl(d/f'eval_{suite}.jsonl',rows)
    contract_path=d/'eval_contract20.jsonl'
    cmd=[sys.executable,'-m','dorilab_gemma.capture_contract','--mirror',str(mirror),'--out',str(contract_path)]
    result=subprocess.run(cmd,cwd=root,text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports/legacy_contract_export.log').write_text(result.stdout,encoding='utf-8')
    require(result.returncode==0,'Contract message export failed (no GPU was used). See reports/legacy_contract_export.log. Source was NOT edited.')
    evals['contract20']=read_jsonl(contract_path)
    # Replay historical raw outputs through NEW scoring, with a parity gate.
    baseline={};base_rows={}
    for suite,oldname in [('ns10',f'{arm}_ns10.jsonl'),('before40',f'{arm}_before.jsonl'),('contract20',f'{arm}_contract.jsonl')]:
        path=source/'data/reason_coverage_v12/results'/oldname
        copy_file(path,root/'snapshot/baseline'/oldname,inv)
        past=read_jsonl(path)
        oldidx={r.get('case_id',r.get('id')):r for r in past}
        require(set(oldidx)=={r['case_id'] for r in evals[suite]},'Historical IDs differ: '+suite)
        scored=[]
        for item in evals[suite]:
            oldrow=oldidx[item['case_id']]
            raw=oldrow.get('raw_output')
            require(isinstance(raw,str),'Historical raw_output missing')
            s=score(item,raw,schema,oldrow.get('hit_generation_limit',False))
            oldpass=oldrow.get('pass') if suite=='contract20' else oldrow.get('contract_pass')
            # Strict reference scoring may intentionally reject a legacy subset pass;
            # allow only that documented strictness difference in Physics suites.
            if suite=='contract20':require(s['strict_contract_pass']==oldpass,'Contract scoring parity failed: '+item['case_id'])
            scored.append({'case_id':item['case_id'],'pair_id':item['case'].get('pair_id'),'score':s})
        base_rows[suite]=scored;baseline[suite]=aggregate(scored)
    # Source suite memberships remain development/regression, never a new holdout.
    frozen={str(p.relative_to(root)):sha(p) for p in d.glob('*') if p.is_file()}
    report=source/'data/reason_coverage_v12/comparison.json'
    if report.exists():copy_file(report,root/'snapshot/v12_comparison.json',inv)
    result={'version':VERSION,'at_utc':now(),'source_project':str(source),'selected_arm':arm,
            'training_rows':len(train),'training_source_manifest':meta,'settings':SETTINGS,
            'frozen_data':frozen,'source_inventory':inv,'baseline_2b_rescored':baseline,
            'dataset_status':'Previously error-informed development/regression; not independent holdout',
            'source_updated':False,'old_adapter_imported':False,
            'scoring_note':'Physics uses frozen JSON Schema + required-field matching + exact unique reference set. Contract uses answer-field matching; parity checked on old 20 outputs.',
            'authorship':'Existing labels/review metadata preserved; no new approval or synthetic training targets created.'}
    write_json(d/'IMPORT_MANIFEST.json',result)
    write_json(d/'baseline_2b_scores.json',base_rows)
    print('IMPORT PASS: 246 training rows; NS10 24 + before40 40 + Contract20 20. No weights imported.')
    return result
