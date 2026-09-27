import copy, hashlib, importlib.util, io, json, os, shutil, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
SCRIPT=PACKAGE/'new_source_reason_v10.py'
sp=importlib.util.spec_from_file_location('ns10',SCRIPT); n=importlib.util.module_from_spec(sp);sp.loader.exec_module(n)
GATE=PACKAGE/'tests/fixtures/scope_gate_v07.py'
COMMON='''import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def validate_answer(a,c):
 if not isinstance(a,dict):raise ValueError('object required')
 action=a.get('action')
 if action not in ('NO_ACTION_REQUIRED','REQUEST_EVIDENCE','CHALLENGE'):raise ValueError('action')
 if a.get('claim_id')!=c['packet']['claim_id']:raise ValueError('claim_id')
 ids={x['reference_id'] for x in c['packet']['reference_context']}|{x['evidence_id'] for x in c['packet']['case_packet']['evidence']}
 refs=a.get('evidence_refs')
 if not isinstance(refs,list) or not refs or not all(isinstance(x,str) for x in refs) or not set(refs)<=ids:raise ValueError('refs')
 if action!='NO_ACTION_REQUIRED' and not isinstance(a.get('reason'),str):raise ValueError('reason')
 if action=='REQUEST_EVIDENCE' and not a.get('requested_evidence'):raise ValueError('requests')
 if not set(a.get('requested_evidence',[]))<=set(c['packet']['allowed_request_ids']):raise ValueError('unknown request')
def answer_matches(e,a):
 if not isinstance(a,dict):return False
 for k,v in e.items():
  if k=='evidence_refs':
   if not set(v)<=set(a.get(k,[])):return False
  elif isinstance(v,list):
   if set(v)!=set(a.get(k,[])):return False
  elif a.get(k)!=v:return False
 return True
'''
PROMPTS='''import json
def build_messages(role,packet,answer=None):
 ms=[{'role':'system','content':'MOCK TEST POLICY: '+role},{'role':'user','content':json.dumps(packet,ensure_ascii=False)}]
 if answer is not None:ms.append({'role':'assistant','content':json.dumps(answer,ensure_ascii=False)})
 return ms
'''
EVAL='''# CPU MOCK EVALUATOR: no real model or quality result.
import argparse,json,hashlib
from pathlib import Path
from .prompts import build_messages
from .common import validate_answer,answer_matches
p=argparse.ArgumentParser()
for k in ('cases','adapter','out','model','revision','max-new-tokens','purpose'):p.add_argument('--'+k)
a=p.parse_args();cs=[json.loads(x) for x in Path(a.cases).read_text().splitlines() if x.strip()]
rs=[]
for c in cs:
 ms=build_messages(c['role'],c['packet'])
 pkt=json.loads(ms[1]['content'])
 o={'action':'NO_ACTION_REQUIRED','claim_id':pkt['claim_id'],'evidence_refs':[pkt['reference_context'][0]['reference_id'],pkt['case_packet']['evidence'][0]['evidence_id']]}
 validate_answer(o,c)
 rs.append({'case_id':c['case_id'],'parsed':o,'raw_output':json.dumps(o),'strict_json_valid':True,'schema_and_refs_valid':True,'action_ok':o['action']==c['expected']['action'],'contract_pass':answer_matches(c['expected'],o),'prompt_tokens':len(ms[0]['content'])+len(ms[1]['content']),'generated_tokens':20,'generation_seconds':0,'hit_generation_limit':False})
with Path(a.out).open('x') as f:
 for r in rs:f.write(json.dumps(r)+'\\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary={'records':len(rs),'model':a.model,'adapter_sha256':sha(Path(a.adapter)/'adapter_model.safetensors'),'case_file_sha256':sha(a.cases),'prompt_sha256':sha('dcurr/prompts.py'),'purpose':a.purpose,'strict_json_valid':len(rs),'schema_and_refs_valid':len(rs),'action_correct':sum(r['action_ok'] for r in rs),'contract_pass':sum(r['contract_pass'] for r in rs)}
Path(a.out).with_suffix('.summary.json').write_text(json.dumps(summary))
'''
# Use literal newline in the emitted mock module.
EVAL=EVAL.replace("+'\\\\n'","+'\\n'")
PREFLIGHT='''import argparse,json
p=argparse.ArgumentParser()
for k in ('data','max-length','model','revision'):p.add_argument('--'+k)
a=p.parse_args();rows=[json.loads(x) for x in open(a.data) if x.strip()]
assert len(rows)==24 and all(r['messages'][-1]['role']=='assistant' for r in rows)
print('CPU MOCK preflight passed; no tokenizer/GPU was used')
'''
class DataTests(unittest.TestCase):
 def test01_shape(self):n.validate_payload()
 def test02_domains(self):self.assertEqual(n.Counter(x['domain'] for x in n.PAYLOAD['cases']),{'THERMAL':8,'VIBRATION':8,'EEE':8})
 def test03_sources_unique(self):self.assertEqual(len({s['program_group'] for s in n.PAYLOAD['registry']}),3)
 def test04_gold_not_gate_input(self):self.assertEqual(set(n.envelope(n.PAYLOAD['cases'][0])),{'role','packet'})
 def test05_real_gate_selects_only_current(self):
  g=n.load_gate(GATE.parent)
  for c in n.PAYLOAD['cases']:
   env,e=g.gate_input(n.envelope(c));self.assertEqual(len(env['packet']['case_packet']['evidence']),1);self.assertEqual(len(e['excluded_from_model_context']),1)
   self.assertIn(env['packet']['case_packet']['evidence'][0]['evidence_id'],c['expected']['evidence_refs'])
 def test06_guide_frozen(self):self.assertEqual(n.PAYLOAD['guide'],(PACKAGE/'reference/reason_guide_v09_unchanged.txt').read_text())
 def test07_all_synthetic(self):self.assertTrue(all(not x['authoring']['real_measurement_available'] and not x['authoring']['human_review_performed'] for x in n.PAYLOAD['cases']))
 def test08_no_invented_pdf_hashes(self):self.assertTrue(all(s['pdf_bytes_sha256'] is None for s in n.PAYLOAD['registry']))
 def test09_cm2_fundamental_not_old_definition(self):
  f=next(f for f in n.PAYLOAD['facts'] if f['fact_id']=='PRINCIPLE-M1');self.assertIn('fundamental',f['text']);self.assertNotIn('effective mass',f['text'])
 def test10_cm2_execution_limited(self):self.assertIn('was not used in shaker control',next(f for f in n.PAYLOAD['facts'] if f['fact_id']=='PRINCIPLE-M3')['text'])
 def test11_mro_possible_not_proven(self):self.assertIn('possible',next(f for f in n.PAYLOAD['facts'] if f['fact_id']=='PRINCIPLE-T4')['text'])
 def test12_baseline_unchanged(self):
  ms=[{'role':'system','content':'a'},{'role':'user','content':'b'}];self.assertEqual(n.guided(ms,''),ms)
 def test13_append_system_only(self):
  ms=[{'role':'system','content':'a'},{'role':'user','content':'b'}];g=n.guided(ms,'x');self.assertEqual(g[1],ms[1]);self.assertEqual(ms[0]['content'],'a');self.assertEqual(g[0]['content'],'a\n\nx')
 def test14_reject_assistant(self):
  with self.assertRaises(ValueError):n.guided([{'role':'assistant','content':'gold'}],'x')
 def test15_duplicate_json(self):
  with self.assertRaises(ValueError):n.strict('{"a":1,"a":2}')
 def test16_nonfinite_json(self):
  with self.assertRaises(ValueError):n.strict('{"a":NaN}')
 def test17_traversal(self):
  with self.assertRaises(ValueError):n.local(Path('/tmp'),'../x')
 def test18_pairs_have_both_directions(self):
  aa=[r for r in n.PAYLOAD['cases'] if r['case_id'].endswith('-A')];self.assertGreater(sum(r['expected']['action']=='NO_ACTION_REQUIRED' for r in aa),0);self.assertLess(sum(r['expected']['action']=='NO_ACTION_REQUIRED' for r in aa),12)

class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.sha=n.E2_SHA;self.oldpath=list(sys.path)
  for k in list(sys.modules):
   if k=='dcurr' or k.startswith('dcurr.'):del sys.modules[k]
  d=self.root/'dcurr';d.mkdir();(d/'__init__.py').write_text('');(d/'common.py').write_text(COMMON);(d/'prompts.py').write_text(PROMPTS);(d/'evaluate.py').write_text(EVAL);(d/'preflight.py').write_text(PREFLIGHT)
  (self.root/'transformers.py').write_text('def set_seed(x): pass\n')
  shutil.copy2(GATE,self.root/GATE.name)
  a=self.root/n.ADAPTER;a.mkdir(parents=True);(a/'adapter_model.safetensors').write_bytes(b'MOCK WEIGHTS');(a/'adapter_config.json').write_text('{}');n.E2_SHA=n.sha(a/'adapter_model.safetensors')
  dd=self.root/'data';dd.mkdir();(dd/'action_schema_v02.json').write_text('{}');(dd/'train_curriculum_physics20_v02_r1.jsonl').write_text(json.dumps({'metadata':{'source_ids':['TH-01'],'program_groups':['ATM_TSU']},'messages':[]})+'\n')
  (dd/'evidence_training_v05').mkdir();(dd/'evidence_training_v05/position210.jsonl').write_text(json.dumps({'metadata':{'source_ids':['VB-X1'],'program_groups':['JWST_MIRI_IFLV']},'messages':[]})+'\n')
 def tearDown(self):
  n.E2_SHA=self.sha;sys.path[:]=self.oldpath
  for k in list(sys.modules):
   if k=='dcurr' or k.startswith('dcurr.'):del sys.modules[k]
  self.tmp.cleanup()
 def prep(self):
  with redirect_stdout(io.StringIO()):n.prepare(self.root,n.DEFAULT_DIR,True)
  return self.root/n.DEFAULT_DIR
 def test19_optin(self):
  with self.assertRaises(ValueError):n.prepare(self.root,n.DEFAULT_DIR,False)
 def test20_prepare_exports(self):
  d=self.prep();self.assertEqual(len(n.readl(d/'evaluation_cases24.jsonl')),24);self.assertFalse(n.readj(d/'manifest.json')['human_review_performed'])
 def test21_no_project_modification(self):
  paths=list((self.root/'dcurr').glob('*.py'));before={str(p):n.sha(p) for p in paths};self.prep();self.assertEqual(before,{str(p):n.sha(p) for p in paths})
 def test22_no_overwrite(self):
  self.prep()
  with self.assertRaises(ValueError):n.prepare(self.root,n.DEFAULT_DIR,True)
 def test23_weight_mismatch(self):
  (self.root/n.ADAPTER/'adapter_model.safetensors').write_bytes(b'changed')
  with self.assertRaises(ValueError):self.prep()
 def test24_source_overlap(self):
  (self.root/'data/evidence_training_v05/position210.jsonl').write_text('{"messages":["RTG4"]}\n')
  with self.assertRaises(ValueError):self.prep()
 def test25_registry_is_not_training(self):
  (self.root/'sources').mkdir();(self.root/'sources/source_manifest_v02.json').write_text('{"reserved":"RTG4"}');d=self.prep();self.assertEqual(len(n.readj(d/'source_overlap_audit.json')['already_registered_sources']),1)
 def test26_guide_mutation_stops(self):
  d=self.prep();(d/'reason_guide_v09_unchanged.txt').write_text('changed')
  with self.assertRaises(ValueError):n.plan(self.root,n.DEFAULT_DIR)
 def test27_duplicate_output_key_rejected(self):
  d=self.prep();c=n.readl(d/'evaluation_cases24.jsonl')[0];common,_=n.modules(self.root);s=n.score(common,c,{'raw_output':'{"action":"CHALLENGE","action":"NO_ACTION_REQUIRED"}'});self.assertFalse(s['strict_contract_pass']);self.assertTrue(s['duplicate_or_invalid_json'])
 def test28_correct_answer_scores(self):
  d=self.prep();common,_=n.modules(self.root)
  for c in n.readl(d/'evaluation_cases24.jsonl'):
   s=n.score(common,c,{'raw_output':json.dumps(c['expected'])});self.assertTrue(s['strict_contract_pass'])
 def test29_bad_refs(self):
  d=self.prep();common,_=n.modules(self.root);c=n.readl(d/'evaluation_cases24.jsonl')[0];a=copy.deepcopy(c['expected']);a['evidence_refs']=['OLD-ID'];s=n.score(common,c,{'raw_output':json.dumps(a)});self.assertFalse(s['schema_and_refs_valid']);self.assertFalse(s['reference_exact'])
 def test30_hook_rejects_gold(self):
  d=self.prep();_,p=n.modules(self.root);c=n.readl(d/'evaluation_cases24.jsonl')[0];old,tr=n.install_hook(p,'baseline',n.readl(d/'inputs_baseline24.jsonl'),d/'trace.jsonl')
  try:
   with self.assertRaises(ValueError):p.build_messages(c['role'],c['packet'],c['expected'])
  finally:p.build_messages=old
 def test31_hook_guidance_trace(self):
  d=self.prep();_,p=n.modules(self.root);c=n.readl(d/'evaluation_cases24.jsonl')[0];old,tr=n.install_hook(p,'guide',n.readl(d/'inputs_guide24.jsonl'),d/'trace.jsonl')
  try:
   ms=p.build_messages(c['role'],c['packet']);self.assertTrue(ms[0]['content'].endswith(n.PAYLOAD['guide']));self.assertEqual(len(tr),1)
   with self.assertRaises(ValueError):p.build_messages(c['role'],c['packet'])
  finally:p.build_messages=old
 def test32_prompt_changed_detected(self):
  d=self.prep();(self.root/'dcurr/prompts.py').write_text('changed')
  with self.assertRaises(ValueError):n.plan(self.root,n.DEFAULT_DIR)
 def test33_full_mock_subprocess_flow(self):
  d=self.prep()
  with redirect_stdout(io.StringIO()):n.evaluate(self.root,n.DEFAULT_DIR);n.compare(self.root,n.DEFAULT_DIR)
  res=n.readj(d/'comparison.json');self.assertEqual(res['unique_scenarios'],24);self.assertEqual(res['arms']['baseline']['overall']['action_correct'],12);self.assertEqual(res['arms']['guide']['overall']['strict_contract_pass'],12)
  self.assertEqual(len(n.readl(d/'results/guide.prompt_trace.jsonl')),24)
 def test34_prompt_unknown_packet_blocked(self):
  d=self.prep();_,p=n.modules(self.root);c=n.readl(d/'evaluation_cases24.jsonl')[0];old,tr=n.install_hook(p,'baseline',n.readl(d/'inputs_baseline24.jsonl'),d/'trace.jsonl')
  try:
   pkt=copy.deepcopy(c['packet']);pkt['injected_gold']=c['expected']
   with self.assertRaises(ValueError):p.build_messages(c['role'],pkt)
  finally:p.build_messages=old
 def test35_truncated_generation_rejected(self):
  d=self.prep();common,_=n.modules(self.root);c=n.readl(d/'evaluation_cases24.jsonl')[0];s=n.score(common,c,{'raw_output':json.dumps(c['expected']),'hit_generation_limit':True});self.assertFalse(s['strict_contract_pass'])
if __name__=='__main__':unittest.main(verbosity=2)
