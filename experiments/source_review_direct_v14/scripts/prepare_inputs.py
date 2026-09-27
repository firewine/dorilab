"""CPU preparation: replace only the system message in the hash-verified saved DEV8 input."""
from pathlib import Path
import copy,hashlib,json,sys
from contract import assert_public
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parents[1]
BASE=WORK/'results/source_review_v13_qwen27'
PACK=WORK/'research/DoriLab_SourceReview_v13'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write_new(path,obj,jsonl=False):
 with path.open('x') as f:
  if jsonl:
   for row in obj:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  else:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def build(saved,prompt,old_prompt):
 result=[]
 for original in saved:
  if set(original)!={'case_id','messages','messages_sha256'}:raise ValueError('unexpected envelope')
  if digest(original['messages'])!=original['messages_sha256']:raise ValueError('message hash mismatch')
  messages=original['messages']
  if [m['role'] for m in messages]!=['system','user']:raise ValueError('unexpected roles')
  if messages[0]['content']!=old_prompt:raise ValueError('historical system differs')
  packet=json.loads(messages[1]['content']);assert_public(packet)
  if set(packet)!={'claim_id','review_question','review_target','scope','source_refs','observations','request_catalog','scope_of_result'}:raise ValueError('unexpected packet fields')
  row=copy.deepcopy(original);row['messages'][0]['content']=prompt
  row['messages_sha256']=digest(row['messages']);result.append(row)
 if len(result)!=8 or len({r['case_id'] for r in result})!=8:raise ValueError('DEV8 membership')
 return result
def main():
 lock=json.loads((BASE/'EXPERIMENT_LOCK.json').read_text());src=BASE/lock['input_file']
 if sha(src)!=lock['input_sha256']:raise ValueError('historical input hash mismatch')
 saved=[json.loads(x) for x in src.read_text().splitlines()]
 rows=build(saved,(ROOT/'prompts/direct_v14.txt').read_text(),(PACK/'prompts/direct_v13.txt').read_text())
 out=ROOT/'inputs/dev8_direct_v14.jsonl';write_new(out,rows,True)
 lock.update(status='CPU_PREPARED_NOT_INFERRED',experiment_version='direct_v14',input_file='inputs/dev8_direct_v14.jsonl',input_sha256=sha(out),baseline_input_sha256=sha(src),prompt_sha256=sha(ROOT/'prompts/direct_v14.txt'),scorer_sha256=sha(PACK/'packtool.py'),baseline_root=str(BASE),native_template_sha256=json.loads((BASE/'RUN_MANIFEST.json').read_text())['runtime']['native_template_sha256'])
 write_new(ROOT/'EXPERIMENT_LOCK.json',lock)
 print(json.dumps({'rows':len(rows),'input_sha256':sha(out),'gold_read':False,'user_messages_unchanged':True}))
if __name__=='__main__':main()
