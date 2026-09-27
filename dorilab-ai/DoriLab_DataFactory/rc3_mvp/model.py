import importlib.metadata as md,json,sys,time
from pathlib import Path

def file_sha(path):
 import hashlib
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def load_registry(path):
 path=Path(path);r=json.loads(path.read_text())
 if r['status']!='INTERNAL_MVP_CANDIDATE' or r['engineering_approval'] or r['official_deployment_approval']:raise ValueError('CANDIDATE_SCOPE_MISMATCH')
 for p,h in r['bindings'].items():
  if file_sha(p)!=h:raise ValueError('CANDIDATE_BINDING_MISMATCH: '+p)
 if file_sha(r['adapter_weights'])!=r['adapter_sha256']:raise ValueError('ADAPTER_HASH_MISMATCH')
 return r
class RC3Model:
 def __init__(self,registry):
  self.r=registry;self.model=None;self.disabled=None
  if sys.executable!=registry['runtime_python']:raise RuntimeError('USE_FIXED_RUNTIME_PYTHON: '+registry['runtime_python'])
  sys.dont_write_bytecode=True
  sys.path.insert(0,str(Path(registry['sealed_tokenization_module']).parent))
  from tokenization import processor,inference
  self.proc,env=processor();self.inference=inference
  expected=registry['runtime']
  for key in ['torch','transformers','peft','accelerate']:
   if md.version(key)!=expected[key]:raise RuntimeError('RUNTIME_VERSION_MISMATCH: '+key)
  direct=json.loads(md.distribution('transformers').read_text('direct_url.json'))
  if direct['vcs_info']['commit_id']!=expected['transformers_direct_url']['vcs_info']['commit_id']:raise RuntimeError('RUNTIME_COMMIT_MISMATCH')
  if env['asset_sha256']!=registry['processor_asset_sha256']:raise RuntimeError('PROCESSOR_ASSET_MISMATCH')
  self.environment=env
 def tokenize(self,messages):return self.inference(self.proc,messages)[1]
 def load(self):
  if self.disabled:raise RuntimeError('MODEL_DISABLED_AFTER_ERROR: '+self.disabled)
  if self.model is not None:return
  import torch
  from transformers import Qwen3_5ForConditionalGeneration,set_seed
  from peft import PeftModel
  if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise RuntimeError('GPU_BF16_UNAVAILABLE')
  snapshot=Path(self.r['snapshot'])
  for name,h in self.r['checkpoint_shards'].items():
   if file_sha(snapshot/name)!=h:raise RuntimeError('MODEL_SHARD_HASH_MISMATCH: '+name)
  for name in ['config.json']:
   p=Path(self.r['processor_assets_directory'])/name
   if file_sha(snapshot/name)!=file_sha(p):raise RuntimeError('MODEL_CONFIG_MISMATCH')
  if file_sha(self.r['adapter_weights'])!=self.r['adapter_sha256']:raise RuntimeError('ADAPTER_CHANGED')
  set_seed(42)
  base=Qwen3_5ForConditionalGeneration.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':0})
  self.model=PeftModel.from_pretrained(base,self.r['adapter_directory'],is_trainable=False)
  self.model.eval()
  if any(p.requires_grad for p in self.model.parameters()):raise RuntimeError('INFERENCE_MODEL_HAS_TRAINABLE_PARAMETERS')
 def generate(self,ids):
  start=time.monotonic()
  try:
   self.load()
   import torch
   tensor=torch.tensor([ids],dtype=torch.long,device='cuda');t=time.monotonic()
   with torch.inference_mode():out=self.model.generate(input_ids=tensor,attention_mask=torch.ones_like(tensor),**self.r['generation'])
   generated=out[0,len(ids):].tolist();text=self.proc.tokenizer.decode(generated,skip_special_tokens=True)
   return dict(raw_text=self.proc.tokenizer.decode(generated,skip_special_tokens=False),text=text,generated_token_ids=generated,
    generated_tokens=len(generated),ended_with_native_terminator=bool(generated and generated[-1]==self.r['generation']['eos_token_id']),
    generation_latency_seconds=time.monotonic()-t,total_model_latency_seconds=time.monotonic()-start)
  except Exception as e:
   self.disabled=type(e).__name__+': '+str(e)
   raise
