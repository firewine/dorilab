"""Run the checked runner once; retain success/failure/partial output and logs, without retry."""
import argparse,datetime,json,os,subprocess,sys
from pathlib import Path
from preflight_core import EXPERIMENT,sha

def put(path,obj):
 with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--cpu-preflight',type=Path,required=True)
 ap.add_argument('--output',type=Path,required=True);ap.add_argument('--gpu-python',type=Path,required=True)
 a=ap.parse_args();dest=a.output.resolve();control=dest.with_name(dest.name+'_control')
 if not dest.is_relative_to(EXPERIMENT/'runs'):raise ValueError('output must be under experiment/runs')
 if dest.exists() or control.exists():raise FileExistsError('never overwrite a prior attempt')
 control.mkdir(parents=True,exist_ok=False)
 argv=[str(a.gpu_python),str(Path(__file__).with_name('run_direct_v14_checked.py')),'--snapshot',str(a.snapshot),'--output',str(dest),'--cpu-preflight',str(a.cpu_preflight),'--generate']
 put(control/'LAUNCH.json',{'command':argv,'current_pod_id':os.environ.get('RUNPOD_POD_ID'),'automatic_retry':False,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 with (control/'run.log').open('x') as log:rc=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
 # Do not read gold or repair partial JSON. A truncated line is preserved and reported.
 rows=[];partial=False;output=dest/'predictions.jsonl'
 if output.exists():
  for line in output.read_text().splitlines():
   try:rows.append(json.loads(line))
   except json.JSONDecodeError:partial=True
 lock=json.loads((EXPERIMENT/'EXPERIMENT_LOCK.json').read_text())
 expected=[json.loads(x)['case_id'] for x in (EXPERIMENT/lock['input_file']).read_text().splitlines()]
 ids=[r.get('case_id') for r in rows];complete=rc==0 and not partial and len(ids)==8 and len(set(ids))==8 and set(ids)==set(expected)
 seal=dest/'OUTPUT_SEAL.json'
 complete=complete and seal.is_file() and json.loads(seal.read_text())['output_sha256']==sha(output)
 status={'status':'COMPLETE' if complete else 'FAILED','process_exit_code':rc,'complete_case_ids':ids,'last_complete_case_id':ids[-1] if ids else None,
 'pending_case_ids':[x for x in expected if x not in ids],'partial_json_line':partial,'automatic_retry':False,
 'output_sha256':sha(output) if output.exists() else None,'resume_policy':'No automatic resume or overwrite. Preserve this attempt; review failure before any new execution.',
 'gold_joined':False,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 put(control/'COMPLETION.json',status)
 # Seal data and launch log before any independent CPU comparison.
 files=[p for root in [control,dest] if root.exists() for p in root.rglob('*') if p.is_file()]
 put(control/'SHA256.json',{str(p.relative_to(control.parent)):sha(p) for p in sorted(files)})
 print(json.dumps(status,indent=2),flush=True)
 return 0 if complete else (rc or 1)
if __name__=='__main__':sys.exit(main())
