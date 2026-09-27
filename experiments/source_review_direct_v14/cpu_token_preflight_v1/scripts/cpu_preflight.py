"""New CPU preflight artifacts only; never historical v13 token IDs. No model load."""
import argparse,datetime,importlib.metadata as md,json,os,platform,sys,traceback
from pathlib import Path
# No GPU/MPS selection; no Hub fetch during processor load.
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from preflight_core import prepare,sha

def put(path,obj):
 with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def seal(dest):
 with (dest/'SHA256SUMS.txt').open('x') as f:
  for path in sorted(dest.iterdir()):
   if path.is_file() and path.name!='SHA256SUMS.txt':f.write(sha(path)+'  '+path.name+'\n')
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
 a=ap.parse_args();dest=a.output.resolve();dest.mkdir(parents=True,exist_ok=False)
 try:
  proc,prepared,records,info=prepare(a.snapshot.resolve())
  with (dest/'actual_model_inputs.jsonl').open('x') as f:
   for record in records:f.write(json.dumps(record,ensure_ascii=False)+'\n')
  over=[{'case_id':r['case_id'],'prompt_tokens':r['prompt_tokens'],'total_reserved_tokens':r['total_reserved_tokens']} for r in records if not r['fits_2048']]
  status='FAIL_TOKEN_BUDGET' if over else 'PASS'
  report={**info,'status':status,'cases':len(records),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
   'artifact_origin':'NEW_DIRECT_V14_CPU_PREFLIGHT_NOT_HISTORICAL_V13_INPUT_IDS',
   'execution_platform':platform.platform(),'python':platform.python_version(),
   'platform_authorization':'User approved current Linux CPU environment after macOS unavailability was disclosed',
   'max_input_tokens':1664,'max_new_tokens':384,'max_total_tokens':2048,
   'all_fit':not over,'over_limit_cases':over,'actual_inputs_sha256':sha(dest/'actual_model_inputs.jsonl'),
   'max_observed_prompt_tokens':max(r['prompt_tokens'] for r in records),
   'model_loaded':False,'inference_executed':False,'gpu_started':False,
   'runtime_packages':{k:md.version(k) for k in ['transformers','torch','torchvision','tokenizers','huggingface-hub','jinja2']},
   'case_lengths':[{k:r[k] for k in ['case_id','messages_sha256','rendered_prompt_sha256','input_token_ids_sha256','prompt_tokens','total_reserved_tokens','fits_2048']} for r in records]}
  put(dest/'TOKEN_PREFLIGHT.json',report)
  put(dest/'COMPLETION.json',{'cpu_measurement_completed':True,'gpu_gate_passed':not over,'status':status,'next_step':'STOP_NO_GPU' if over else 'GPU_RECHECK_REQUIRED'})
  seal(dest)
  print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
  return 2 if over else 0
 except Exception:
  put(dest/'FAILURE.json',{'status':'FAILED','error':traceback.format_exc(),'model_loaded':False,'inference_executed':False,'automatic_retry':False})
  seal(dest);raise
if __name__=='__main__':sys.exit(main())
