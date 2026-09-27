import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import packtool as p
from metamorphic import rename_input,remap_gold_for_offline_score

class PackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.ins,cls.gold,cls.meta=p.load_split(ROOT,'TRAIN');cls.facts={f['fact_id']:f for f in p.read_json(ROOT/'sources/facts.json')};cls.reasons=p.read_json(ROOT/'schemas/reason_definitions_v13.json')
 def item(self,action='CHALLENGE'):
  i=next(i for i in self.ins if self.gold[i['case_id']]['expected']['action']==action);return copy.deepcopy(i),copy.deepcopy(self.gold[i['case_id']])
 def test_01_structural_validate(self):self.assertEqual(p.validate(ROOT)['cases'],72)
 def test_02_duplicate_key_rejected(self):
  with self.assertRaises(ValueError):p.strict_json('{"a":1,"a":2}')
 def test_03_nan_rejected(self):
  with self.assertRaises(ValueError):p.strict_json('{"a":NaN}')
 def test_04_array_not_answer(self):
  i,g=self.item();self.assertFalse(p.evaluate_output(i,g,'[]',self.reasons)['strict_pass'])
 def test_05_all_candidate_gold_self_consistent(self):
  for split in ['TRAIN','DEV']:
   ii,gg,_=p.load_split(ROOT,split)
   for i in ii:self.assertTrue(p.evaluate_output(i,gg[i['case_id']],json.dumps(gg[i['case_id']]['expected']),self.reasons)['strict_pass'])
 def test_06_object_refs_do_not_crash(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['evidence_refs']=[{'id':'x'}];self.assertFalse(p.evaluate_output(i,g,json.dumps(x),self.reasons)['strict_pass'])
 def test_07_duplicate_ref_rejected(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['evidence_refs']*=2;self.assertFalse(p.evaluate_output(i,g,json.dumps(x),self.reasons)['schema_valid'])
 def test_08_unprovided_ref_rejected(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['evidence_refs'].append('SECRET');self.assertFalse(p.evaluate_output(i,g,json.dumps(x),self.reasons)['schema_valid'])
 def test_09_missing_request(self):
  i,g=self.item('REQUEST_EVIDENCE');x=copy.deepcopy(g['expected']);del x['requested_evidence'];self.assertFalse(p.evaluate_output(i,g,json.dumps(x),self.reasons)['schema_valid'])
 def test_10_claim_mismatch(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['claim_id']='wrong';self.assertFalse(p.evaluate_output(i,g,json.dumps(x),self.reasons)['schema_valid'])
 def test_11_raw_fence_fails(self):
  i,g=self.item();raw='```json\n'+json.dumps(g['expected'])+'\n```';self.assertFalse(p.evaluate_output(i,g,raw,self.reasons)['json_valid'])
 def test_12_exact_fence_diagnostic(self):
  i,g=self.item();raw='```json\n'+json.dumps(g['expected'])+'\n```';r=p.evaluate_output(i,g,raw,self.reasons,True);self.assertTrue(r['strict_pass']);self.assertEqual(r['raw_output'],raw)
 def test_13_fence_plus_explanation_not_repaired(self):
  raw='Here is the answer\n```json\n{}\n```';self.assertEqual(p.exact_fence_unwrap(raw),(raw,False))
 def test_14_multiple_json_not_selected(self):
  i,g=self.item();self.assertFalse(p.evaluate_output(i,g,'{}\n{}',self.reasons,True)['json_valid'])
 def test_15_truncation_not_completed(self):
  i,g=self.item();self.assertFalse(p.evaluate_output(i,g,'{"action":',self.reasons,True)['json_valid'])
 def test_16_no_gold_in_render(self):
  for i in self.ins:
   msgs=p.messages_for_input(i,self.facts,'POLICY');self.assertEqual([m['role'] for m in msgs],['system','user']);self.assertFalse(p.forbidden_fields(json.loads(msgs[1]['content'])))
 def test_17_render_avoids_gold_file(self):
  original=Path.read_text
  def checked(path,*a,**kw):
   self.assertNotIn('gold_candidate',str(path));return original(path,*a,**kw)
  with tempfile.TemporaryDirectory() as d,patch.object(Path,'read_text',checked):p.render(ROOT,'DEV',Path(d)/'public.jsonl')
 def test_18_context_is_all_public_source_refs(self):
  i,g=self.item();msg=p.messages_for_input(i,self.facts,'POLICY');x=json.loads(msg[1]['content']);self.assertEqual(len(x['source_refs']),len(i['packet']['source_refs']));self.assertGreater(len(x['source_refs']),1)
 def test_19_id_rename_gold_kept_offline(self):
  for i in self.ins:
   g=self.gold[i['case_id']];ii,m=rename_input(i);gg=remap_gold_for_offline_score(g,m);self.assertTrue(p.evaluate_output(ii,gg,json.dumps(gg['expected']),self.reasons)['strict_pass']);self.assertEqual(g['expected']['action'],gg['expected']['action'])
 def test_20_export_without_review_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'release.json').write_text(json.dumps({'status':'PENDING'}))
   with self.assertRaises(ValueError):p.export_sft(ROOT,r,r/'train.jsonl')
   self.assertFalse((r/'train.jsonl').exists())
 def test_21_new_output_exclusive(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'x.json';p.write_new(f,{});
   with self.assertRaises(FileExistsError):p.write_new(f,{'replace':True})
 def test_22_invalid_not_counted_safe(self):
  i,g=self.item();r=p.evaluate_output(i,g,'invalid',self.reasons);self.assertIsNone(r['false_normal']);self.assertFalse(r['strict_pass'])
 def test_23_false_accept_detected(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['action']='NO_ACTION_REQUIRED';del x['reason'];self.assertTrue(p.evaluate_output(i,g,json.dumps(x),self.reasons)['false_normal'])
 def test_24_missing_key_name_in_prose_is_allowed(self):self.assertFalse(p.forbidden_fields({'text':'The expected physical range is uncertain.'}))
 def test_25_reason_denominator_excludes_normal(self):
  i,g=self.item('NO_ACTION_REQUIRED');r=p.evaluate_output(i,g,json.dumps(g['expected']),self.reasons);self.assertFalse(r['reason_applicable']);self.assertIsNone(r['reason_correct'])
 def test_26_orderless_refs(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['evidence_refs'].reverse();self.assertTrue(p.evaluate_output(i,g,json.dumps(x),self.reasons)['strict_pass'])
 def test_27_source_program_split(self):
  seen={}
  for s in p.read_json(ROOT/'sources/source_manifest.json'):
   self.assertNotIn(s['program_group'],seen);seen[s['program_group']]=s['split']
 def test_28_required_ref_count_varies(self):self.assertEqual({len(x['expected']['evidence_refs']) for x in self.gold.values()},{2,3})
 def test_29_workflow_not_action_sft(self):
  w=p.rows(ROOT/'workflow_probes/gold_candidate.jsonl');self.assertEqual(len(w),6);self.assertTrue(all(x['expected_action'] is None and not x['training_eligible'] for x in w))
 def test_30_human_review_claim_is_false(self):self.assertTrue(all(not x['human_review_performed'] for x in self.gold.values()))
 def test_31_generation_limit_never_passes(self):
  ii,gg,_=p.load_split(ROOT,'DEV')
  predictions=[{'case_id':i['case_id'],'raw_output':json.dumps(gg[i['case_id']]['expected']),'hit_generation_limit':True} for i in ii]
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p.write_new(d/'pred.jsonl',predictions,jsonl=True);s=p.score(ROOT,'DEV',d/'pred.jsonl',d/'score.json');self.assertEqual(s['counts']['strict_pass'],0)
 def test_32_missing_predictions_rejected(self):
  ii,gg,_=p.load_split(ROOT,'DEV')
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p.write_new(d/'pred.jsonl',[{'case_id':ii[0]['case_id'],'raw_output':json.dumps(gg[ii[0]['case_id']]['expected'])}],jsonl=True)
   with self.assertRaises(ValueError):p.score(ROOT,'DEV',d/'pred.jsonl',d/'score.json')
 def test_33_duplicate_predictions_rejected(self):
  i,g=self.item()
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p.write_new(d/'pred.jsonl',[{'case_id':i['case_id'],'raw_output':json.dumps(g['expected'])}]*2,jsonl=True)
   with self.assertRaises(ValueError):p.score(ROOT,'TRAIN',d/'pred.jsonl',d/'score.json')
 def test_34_unknown_action_not_accepted(self):
  i,g=self.item();x=copy.deepcopy(g['expected']);x['action']='APPROVED';r=p.evaluate_output(i,g,json.dumps(x),self.reasons);self.assertFalse(r['schema_valid']);self.assertFalse(r['strict_pass'])
if __name__=='__main__':unittest.main()
