#!/usr/bin/env python3
"""One isolated end-to-end Gemma E4B run; no writes to the source project."""
from __future__ import annotations
import argparse, os, subprocess, sys, time, traceback
from pathlib import Path
from dorilab_gemma.common import *
ROOT=Path(__file__).resolve().parent
STAGES=('import','preflight','baseline','train','finetuned','compare')

def code_hash():
    paths=[Path(__file__),*sorted((ROOT/'dorilab_gemma').glob('*.py'))]
    return digest({str(p.relative_to(ROOT)):sha(p) for p in paths})

def stage_outputs(stage):
    if stage=='import':return ['data/IMPORT_MANIFEST.json','data/train.jsonl','data/eval_ns10.jsonl','data/eval_before40.jsonl','data/eval_contract20.jsonl','data/action_schema.json','data/baseline_2b_scores.json']
    if stage=='preflight':return ['reports/preflight.json','reports/model_lock.json','data/encoded_train.jsonl','reports/mask_examples.json']
    if stage=='train':return ['reports/training_receipt.json']
    if stage in ('baseline','finetuned'):
        return [f'reports/{stage}/{s}.jsonl' for s in ('ns10','before40','contract20')]+[f'reports/{stage}/summary.json']
    return ['reports/comparison.json','reports/comparison_cases.jsonl','reports/RESULTS_KO.md']

def run_stage(stage,args):
    logdir=ROOT/'logs';logdir.mkdir(exist_ok=True)
    status=ROOT/'state';status.mkdir(exist_ok=True)
    done=status/f'{stage}.complete.json'
    if done.exists():
        rec=read_json(done);require(rec['code_sha256']==code_hash(),'Code changed since completed stage; use a new project folder')
        require(rec['settings']==SETTINGS,'Settings changed')
        for rel,h in rec['files'].items():require(sha(ROOT/rel)==h,'Completed output changed: '+rel)
        if stage=='import':require(read_json(ROOT/'data/IMPORT_MANIFEST.json')['selected_arm']==args.arm,'Imported arm differs')
        print('SKIP VERIFIED:',stage,flush=True);return
    log=logdir/f'{stage}.log'
    if log.exists():
        archived=logdir/(stage+'.previous_'+str(time.time_ns())+'.log')
        log.rename(archived)
        print('Preserved prior attempt log:',archived,flush=True)
    cmd=[sys.executable,str(ROOT/'run_gemma.py'),'_worker',stage,'--source',str(args.source),'--arm',args.arm]
    env=dict(os.environ);env.update(PYTHONHASHSEED='42',PYTHONDONTWRITEBYTECODE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
    env.pop('BNB_CUDA_VERSION',None)
    print('\n=== '+stage.upper()+' ===',flush=True)
    start=time.perf_counter()
    with log.open('x',encoding='utf-8') as f:
        p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        try:
            for line in p.stdout:print(line,end='',flush=True);f.write(line);f.flush()
            rc=p.wait()
        except KeyboardInterrupt:p.terminate();p.wait();raise
    require(rc==0,f'{stage} failed ({rc}); source project unchanged. Log: {log}')
    paths=stage_outputs(stage)
    if stage=='train':
        receipt=read_json(ROOT/'reports/training_receipt.json')
        paths += [receipt['adapter']+'/'+n for n in receipt['files']]
    require(all((ROOT/x).is_file() for x in paths),'Stage outputs incomplete: '+stage)
    write_json(done,{'stage':stage,'at_utc':now(),'code_sha256':code_hash(),'settings':SETTINGS,
                     'files':{x:sha(ROOT/x) for x in paths},'wall_seconds':time.perf_counter()-start})

def worker(stage,args):
    if stage=='import':
        from dorilab_gemma.importer import build
        build(args.source,ROOT,args.arm)
    else:
        from dorilab_gemma import workers
        if stage=='preflight':workers.preflight(ROOT)
        elif stage in ('baseline','finetuned'):workers.evaluate(ROOT,stage)
        elif stage=='train':workers.train(ROOT)
        elif stage=='compare':workers.compare(ROOT)
        else:raise ValueError(stage)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['all','doctor',*STAGES,'_worker'])
    ap.add_argument('worker_stage',nargs='?',choices=STAGES)
    ap.add_argument('--source',type=Path,default=Path.home()/'dorilab-ai/DoriLab_SourceCurriculum_v02')
    ap.add_argument('--arm',choices=['repeat','coverage'],default='repeat',help='Existing export, not merged. Default: stronger regression comparator repeat246.')
    args=ap.parse_args()
    require(sys.version_info[:2]==(3,12),'Use the separate Python 3.12 environment: bash start.sh')
    require(Path(sys.prefix).resolve()==(ROOT/'.venv').resolve(),'Do not use the old Qwen virtualenv; run bash start.sh')
    (ROOT/'reports').mkdir(exist_ok=True)
    if args.command=='_worker':worker(args.worker_stage,args);return
    if args.command=='doctor':
        from dorilab_gemma.modeling import check_gpu
        print(json.dumps({'environment':environment(),'cuda_test':check_gpu()},indent=2));return
    if args.command=='all':
        for stage in STAGES:run_stage(stage,args)
    else:run_stage(args.command,args)
    if args.command in ('all','compare'):
        print('\nRESULTS:',ROOT/'reports/RESULTS_KO.md')
        print('UPLOAD:',ROOT/'reports/comparison.json',ROOT/'reports/comparison_cases.jsonl')
if __name__=='__main__':
    try:main()
    except Exception as ex:
        traceback.print_exc()
        print('\nSTOP:',ex,file=sys.stderr)
        print('No automatic environment upgrade, input truncation, checkpoint merging, or model promotion.',file=sys.stderr)
        sys.exit(1)
