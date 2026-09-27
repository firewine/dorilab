"""Shared CPU/GPU input preparation. No model class loading, inference or gold reads."""
from pathlib import Path
import hashlib,json,importlib.metadata as md,sys
STAGE=Path(__file__).resolve().parents[1]
EXPERIMENT=STAGE.parent
sys.path.insert(0,str(EXPERIMENT/'scripts'))
from batch_guard import check_lock,verify_rows

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def json_sha(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate_assets(snapshot):
 allow=json.loads((STAGE/'ASSET_ALLOWLIST.json').read_text())
 if snapshot.name!=allow['revision']:raise ValueError('revision directory mismatch')
 hashes={}
 for name,expected in allow['files'].items():
  file=snapshot/name
  if file.stat().st_size!=expected['bytes'] or sha(file)!=expected['sha256']:raise ValueError('asset mismatch: '+name)
  hashes[name]=sha(file)
 return hashes

def render_rows(proc,rows):
 # Exact original GPU runner render/tokenize calls, including all flags.
 tok=proc.tokenizer;prepared=[]
 for r in rows:
  text=proc.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
  ids=tok(text,add_special_tokens=False,truncation=False)['input_ids']
  prepared.append((r,text,ids))
 return prepared

def prepare(snapshot):
 lock=json.loads((EXPERIMENT/'EXPERIMENT_LOCK.json').read_text());check_lock(lock)
 if md.version('transformers')!=lock['transformers']:raise ValueError('Transformers version mismatch')
 direct=json.loads(md.distribution('transformers').read_text('direct_url.json'))
 commit=direct.get('vcs_info',{}).get('commit_id')
 if commit!=lock['transformers_git_commit']:raise ValueError('Transformers commit mismatch')
 hashes=validate_assets(snapshot)
 input_path=EXPERIMENT/lock['input_file']
 if sha(input_path)!=lock['input_sha256']:raise ValueError('input hash mismatch')
 if sha(EXPERIMENT/'prompts/direct_v14.txt')!=lock['prompt_sha256']:raise ValueError('prompt hash mismatch')
 rows=[json.loads(line) for line in input_path.read_text().splitlines()];verify_rows(rows)
 from transformers import AutoProcessor
 proc=AutoProcessor.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
 prepared=render_rows(proc,rows)
 records=[]
 for row,text,ids in prepared:
  records.append({'case_id':row['case_id'],'messages_sha256':row['messages_sha256'],
   'rendered_text':text,'rendered_prompt_sha256':hashlib.sha256(text.encode()).hexdigest(),
   'input_token_ids':ids,'input_token_ids_sha256':json_sha(ids),'prompt_tokens':len(ids),
   'response_budget':384,'total_reserved_tokens':len(ids)+384,'fits_2048':len(ids)<=1664,
   'tokenizer_and_template_file_sha256':hashes})
 info={'model':lock['model'],'revision':lock['revision'],'transformers':md.version('transformers'),
  'transformers_git_commit':commit,'input_sha256':sha(input_path),'prompt_sha256':lock['prompt_sha256'],
  'preflight_core_sha256':sha(Path(__file__)),'tokenizer_and_template_file_sha256':hashes,
  'processor_class':type(proc).__name__,'tokenizer_class':type(proc.tokenizer).__name__,
  'render_flags':{'tokenize':False,'add_generation_prompt':True,'enable_thinking':False},
  'tokenize_flags':{'add_special_tokens':False,'truncation':False}}
 return proc,prepared,records,info

def verify_cpu_reference(records,info,cpu_dir):
 manifest=json.loads((cpu_dir/'TOKEN_PREFLIGHT.json').read_text())
 expected_sha=(cpu_dir/'SHA256SUMS.txt').read_text().splitlines()
 for line in expected_sha:
  wanted,name=line.split('  ',1)
  path=cpu_dir/name
  if not path.resolve().is_relative_to(cpu_dir.resolve()) or sha(path)!=wanted:raise ValueError('CPU artifact checksum mismatch')
 if manifest['status']!='PASS' or manifest['cases']!=8:raise ValueError('CPU gate not passed')
 for key in ['model','revision','transformers_git_commit','input_sha256','prompt_sha256','preflight_core_sha256','tokenizer_and_template_file_sha256']:
  if info[key]!=manifest[key]:raise ValueError('CPU/GPU provenance mismatch: '+key)
 expected=[json.loads(x) for x in (cpu_dir/'actual_model_inputs.jsonl').read_text().splitlines()]
 if records!=expected:raise ValueError('CPU/GPU rendering or token ID mismatch; generation forbidden')
 return sha(cpu_dir/'TOKEN_PREFLIGHT.json')
