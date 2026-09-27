"""Input-only DEV8 diagnostic runner. No candidate gold or evaluator package reads."""
from pathlib import Path
import json,hashlib,time,datetime,subprocess,importlib.metadata as md,os
import torch
from transformers import AutoProcessor,AutoModelForMultimodalLM,set_seed
root=Path(__file__).resolve().parents[1];dest=root/'baseline_direct'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,ensure_ascii=False)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
lock=json.load(open(root/'EXPERIMENT_LOCK.json'));cache=json.load(open(root/'cpu_source_audit/MODEL_CACHE_RESTORE.json'));snap=Path(cache['snapshot_path'])
assert md.version('transformers')==lock['transformers'];commit=json.loads(md.distribution('transformers').read_text('direct_url.json'))['vcs_info']['commit_id'];assert commit==lock['transformers_git_commit']
assert cache['revision']==lock['revision'] and snap.name==lock['revision']
input_path=root/lock['input_file'];assert sha(input_path)==lock['input_sha256']
proc=AutoProcessor.from_pretrained(snap,local_files_only=True,trust_remote_code=False);tok=proc.tokenizer
prepared=[]
for r in map(json.loads,input_path.read_text().splitlines()):
 text=proc.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
 ids=tok(text,add_special_tokens=False,truncation=False)['input_ids'];assert len(ids)+lock['max_new_tokens']<=lock['max_total_tokens'],'NO_TRUNCATION_OVER_LIMIT'
 prepared.append((r,text,ids))
set_seed(lock['seed']);start=time.perf_counter();at=now()
manifest={'status':'STARTED','start_utc':at,'experiment_lock_sha256':sha(root/'EXPERIMENT_LOCK.json'),'runner_sha256':sha(Path(__file__)),'input_sha256':sha(input_path),'model':lock['model'],'revision':lock['revision'],'transformers':md.version('transformers'),'transformers_git_commit':commit,'torch':torch.__version__,'cuda':torch.version.cuda,'peft':md.version('peft'),'attention_implementation':'sdpa','precision':'bfloat16','quantization':None,'native_template_sha256':sha(snap/'chat_template.jinja'),'enable_thinking':False,'seed':42,'max_total_tokens':2048,'max_new_tokens':384,'rows':len(prepared),'candidate_gold_read':False,'training_executed':False,'historical_baseline_rerun':False,'gpu':torch.cuda.get_device_name(0),'gpu_total_GiB':torch.cuda.get_device_properties(0).total_memory/1024**3}
put(dest/'RUN_MANIFEST.json',manifest)
print('Loading fixed local snapshot',str(snap),flush=True)
t0=time.perf_counter();model=AutoModelForMultimodalLM.from_pretrained(snap,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,device_map={'':0},low_cpu_mem_usage=True,attn_implementation='sdpa');model.eval()
for p in model.parameters():p.requires_grad_(False)
assert not any(p.requires_grad for p in model.parameters())
torch.cuda.synchronize();load_seconds=time.perf_counter()-t0
stops=set()
for v in [tok.eos_token_id,getattr(model.generation_config,'eos_token_id',None),getattr(model.config,'eos_token_id',None),getattr(getattr(model.config,'text_config',None),'eos_token_id',None)]:
 if isinstance(v,int):stops.add(v)
 elif isinstance(v,(list,tuple)):stops.update(v)
if '<|im_end|>' in tok.get_vocab():stops.add(tok.convert_tokens_to_ids('<|im_end|>'))
stops=sorted(stops);assert stops
pad=tok.pad_token_id if tok.pad_token_id is not None else stops[0]
put(dest/'LOAD_REPORT.json',{'load_seconds':load_seconds,'model_class':type(model).__name__,'all_base_parameters_frozen':True,'trainable_parameters':0,'stop_token_ids':stops,'pad_token_id':pad,'allocated_GiB':torch.cuda.memory_allocated()/1024**3,'reserved_GiB':torch.cuda.memory_reserved()/1024**3})
output=dest/'predictions.jsonl';durations=[]
with output.open('x') as f:
 for i,(r,text,ids) in enumerate(prepared,1):
  x=torch.tensor([ids],dtype=torch.long,device='cuda');mask=torch.ones_like(x)
  torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();t0=time.perf_counter()
  with torch.inference_mode():y=model.generate(input_ids=x,attention_mask=mask,max_new_tokens=lock['max_new_tokens'],do_sample=False,eos_token_id=stops,pad_token_id=pad,use_cache=True)
  torch.cuda.synchronize();duration=time.perf_counter()-t0;new=y[0,len(ids):].tolist();end=next((j for j,t in enumerate(new) if t in stops),None);hit=end is None and len(new)>=lock['max_new_tokens'];body=new[:end] if end is not None else new
  row={'case_id':r['case_id'],'model':lock['model'],'revision':lock['revision'],'path':'direct_v13','adapter':None,'messages_sha256':r['messages_sha256'],'rendered_prompt_sha256':hashlib.sha256(text.encode()).hexdigest(),'prompt_tokens':len(ids),'generated_tokens':len(new),'output_token_ids':new,'raw_output':tok.decode(body,skip_special_tokens=False),'raw_with_terminal':tok.decode(new,skip_special_tokens=False),'hit_generation_limit':hit,'generation_seconds':duration,'peak_allocated_GiB':torch.cuda.max_memory_allocated()/1024**3,'peak_reserved_GiB':torch.cuda.max_memory_reserved()/1024**3,'nvidia_smi_memory':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader'],text=True).strip(),'engineering_approved':False}
  f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno());durations.append(duration)
  print(f'{i}/{len(prepared)} {r["case_id"]} prompt={len(ids)} output={len(new)} hit_limit={hit} seconds={duration:.2f}',flush=True)
put(dest/'OUTPUT_SEAL.json',{'status':'OUTPUT_HASH_FIXED_BEFORE_OFFLINE_GOLD_JOIN','output_sha256':sha(output),'rows':len(prepared),'sealed_at_utc':now(),'load_seconds':load_seconds,'generation_seconds':sum(durations),'total_seconds':time.perf_counter()-start,'base_parameters_frozen':True,'human_review_performed':False,'training_eligible':False})
print('OUTPUT SEALED',sha(output),flush=True)
