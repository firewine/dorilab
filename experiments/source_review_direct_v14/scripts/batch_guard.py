"""CPU-only batch invariants, also used by the future GPU runner."""
import hashlib,json
from pathlib import Path
from prepare_inputs import digest

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def check_budget(counts,max_new_tokens=384,max_total_tokens=2048):
 if any(n+max_new_tokens>max_total_tokens for n in counts):
  raise ValueError('NO_TRUNCATION_OVER_LIMIT: stop before model load; do not silently change prompt/budget')
def check_lock(lock):
 expected={'experiment_version':'direct_v14','model':'Qwen/Qwen3.8-27B',
  'revision':'1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0','transformers':'5.18.0.dev0',
  'transformers_git_commit':'002e1edf5b5198488297f401dd853056b6521d02',
  'precision':'bfloat16','quantization':None,'enable_thinking':False,
  'decoder':'greedy do_sample=False','seed':42,'max_total_tokens':2048,'max_new_tokens':384}
 for key,value in expected.items():
  if lock.get(key)!=value:raise ValueError('locked condition mismatch: '+key)
def verify_rows(rows):
 if len(rows)!=8 or len({r['case_id'] for r in rows})!=8:raise ValueError('invalid DEV8 membership')
 for row in rows:
  if row['messages_sha256']!=digest(row['messages']):raise ValueError('message hash mismatch')
