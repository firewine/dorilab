import ast,hashlib,json,sys,tempfile,unittest
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'scripts'))
from preflight_core import render_rows,validate_assets,verify_cpu_reference
class PreflightTests(unittest.TestCase):
 def test_exact_original_render_and_tokenize_calls(self):
  old=ast.parse((STAGE.parent/'scripts/run_direct_v14.py').read_text())
  new=ast.parse((STAGE/'scripts/preflight_core.py').read_text())
  def calls(tree):
   return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Attribute) and n.func.attr=='apply_chat_template') or (isinstance(n.func,ast.Name) and n.func.id=='tok'))]
  self.assertEqual(calls(old),calls(new))
 def test_render_keeps_case_order_text_and_ids(self):
  class Proc:
   def apply_chat_template(self,messages,**kwargs):
    assert kwargs==dict(tokenize=False,add_generation_prompt=True,enable_thinking=False)
    return messages[0]['content']
   def tokenizer(self,text,**kwargs):
    assert kwargs==dict(add_special_tokens=False,truncation=False)
    return {'input_ids':[ord(x) for x in text]}
  rows=[{'case_id':'format-a','messages':[{'content':'AB'}]},{'case_id':'format-b','messages':[{'content':'C'}]}]
  out=render_rows(Proc(),rows)
  self.assertEqual([(r['case_id'],text,ids) for r,text,ids in out],[('format-a','AB',[65,66]),('format-b','C',[67])])
 def test_allowlist_exactly_eight_nonweight_files(self):
  lock=json.loads((STAGE/'ASSET_ALLOWLIST.json').read_text())
  self.assertEqual(set(lock['files']),{'config.json','tokenizer_config.json','tokenizer.json','vocab.json','merges.txt','chat_template.jinja','preprocessor_config.json','video_preprocessor_config.json'})
  self.assertFalse(lock['weights_allowed']);self.assertFalse(lock['fallback_revision_allowed'])
 def test_downloaded_files_all_match_historical_hashes(self):
  lock=json.loads((STAGE/'ASSET_ALLOWLIST.json').read_text());snapshot=STAGE/'assets'/lock['revision']
  hashes=validate_assets(snapshot)
  self.assertEqual(hashes,{k:v['sha256'] for k,v in lock['files'].items()})
  self.assertEqual({p.name for p in snapshot.iterdir()},set(lock['files']))
 def test_no_model_or_generation_in_preflight_source(self):
  for name in ['preflight_core.py','cpu_preflight.py']:
   source=(STAGE/'scripts'/name).read_text();ast.parse(source)
   self.assertNotIn('AutoModel',source);self.assertNotIn('.generate(',source);self.assertNotIn('gold_candidate',source)
 def test_gpu_recheck_rejects_different_tokens_or_failed_cpu_gate(self):
  keys=['model','revision','transformers_git_commit','input_sha256','prompt_sha256','preflight_core_sha256','tokenizer_and_template_file_sha256']
  info={k:k for k in keys};records=[{'case_id':str(i),'input_token_ids':[i]} for i in range(8)]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   def write(status):
    (root/'TOKEN_PREFLIGHT.json').write_text(json.dumps({**info,'status':status,'cases':8}))
    (root/'actual_model_inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    (root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256((root/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['TOKEN_PREFLIGHT.json','actual_model_inputs.jsonl']))
   write('PASS');verify_cpu_reference(records,info,root)
   with self.assertRaisesRegex(ValueError,'token ID mismatch'):verify_cpu_reference([{**records[0],'input_token_ids':[99]}]+records[1:],info,root)
   write('FAIL_TOKEN_BUDGET')
   with self.assertRaisesRegex(ValueError,'gate not passed'):verify_cpu_reference(records,info,root)
class RunnerTests(unittest.TestCase):
 def test_generation_suffix_unchanged(self):
  old=(STAGE.parent/'scripts/run_direct_v14.py').read_text()
  suffix=old[old.index('from transformers import AutoModelForMultimodalLM'):]
  new=(STAGE/'scripts/run_direct_v14_checked.py').read_text()
  self.assertTrue(new.endswith(suffix))
  self.assertLess(new.index('cpu_manifest_sha=verify_cpu_reference('),new.index('from transformers import AutoModelForMultimodalLM'))
 def test_comparison_reason_not_misclassified_after_schema_failure(self):
  from compare_results_extended import metrics,aggregate
  packet={'claim_id':'C','source_refs':[],'observations':[]}
  score={'json_valid':True,'schema_valid':False,'action_correct':True,'strict_pass':False,'error':'unexpected answer fields','reason_applicable':True}
  raw={'raw_output':'{"action":"CHALLENGE","claim_id":"C","evidence_refs":[],"reason_code":"METHOD_INTERPRETATION_ERROR"}',
       'generation_seconds':1,'prompt_tokens':100,'generated_tokens':20}
  result=metrics(score,raw,packet)
  self.assertTrue(result['OUTPUT_CONTRACT_FIELD_ERROR'])
  self.assertEqual(result['reason_status'],'NOT_EVALUATED_SCHEMA_ERROR')
  self.assertIsNone(result['reason_correct']);self.assertIsNone(result['reference_exact'])
  self.assertEqual(aggregate([result])['parsed_action_correct'],1)
  self.assertEqual(aggregate([result])['schema_qualified_action_correct'],0)
if __name__=='__main__':unittest.main()
