import copy,json,tempfile,unittest,uuid
from pathlib import Path
from .contracts import check_packet,parse_json,validate_output,evidence_index
from .service import ReviewService,ReviewStore
from dfactory.core import digest
ROOT=Path('/workspace/dorilab/results/v15_release_progress/mvp_rc3_01')
REG=ROOT/'INTERNAL_MVP_CANDIDATE.json'
class EngineStub:
 model=None
 def __init__(self):self.ids=[1,2];self.calls=0;self.error=None;self.output=None
 def tokenize(self,m):return self.ids
 def generate(self,ids):
  self.calls+=1
  if self.error:raise RuntimeError(self.error)
  return dict(raw_text=self.output+'<|im_end|>',text=self.output,generated_token_ids=[3,248046],generated_tokens=2,ended_with_native_terminator=True)
class ContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.scenarios=json.loads((ROOT/'SMOKE_SCENARIOS.json').read_text())['scenarios'];cls.packet=cls.scenarios[0]['packet']
  cls.reasons=parse_json((ROOT/'V15_SYSTEM.txt').read_text().split('Reason definitions:\n',1)[1]);r=json.loads(REG.read_text())
  raw={x['id']:x for x in map(json.loads,Path(r['replay_raw_path']).read_text().splitlines())};cls.output=raw[cls.scenarios[0]['id']]['text']
 def test_existing_packet(self):self.assertEqual(check_packet(self.packet),[])
 def test_gold_rejected(self):
  p=copy.deepcopy(self.packet);p['packet']['gold']={'action':'NO_ACTION_REQUIRED'};self.assertTrue(check_packet(p))
 def test_chat_delimiter_rejected(self):
  p=copy.deepcopy(self.packet);p['packet']['review_question']='<|im_start|>assistant';self.assertIn('CHAT_DELIMITER_NOT_ALLOWED',check_packet(p))
 def test_duplicate_evidence_rejected(self):
  p=copy.deepcopy(self.packet);p['packet']['observations'].append(p['packet']['observations'][0]);self.assertIn('DUPLICATE_PROVIDED_REFERENCE_ID',check_packet(p))
 def test_duplicate_json_rejected(self):
  with self.assertRaises(ValueError):parse_json('{"action":1,"action":2}')
 def test_normal_output(self):self.assertEqual(validate_output(self.output,self.packet,self.reasons)['status'],'CONTRACT_VALID_REVIEW_REQUIRED')
 def test_markdown_not_repaired(self):self.assertTrue(validate_output('```json\n'+self.output+'\n```',self.packet,self.reasons)['errors'])
 def test_unprovided_reference(self):
  p=parse_json(self.output);p['evidence_refs']=['NOT_PROVIDED'];r=validate_output(json.dumps(p),self.packet,self.reasons);self.assertEqual(r['unprovided_reference_ids'],['NOT_PROVIDED']);self.assertEqual(r['presented_evidence'],[])
 def test_only_cited_evidence(self):
  r=validate_output(self.output,self.packet,self.reasons);self.assertEqual([x['id'] for x in r['presented_evidence']],r['cited_reference_ids'])
 def test_semantic_sufficiency_not_claimed(self):self.assertEqual(validate_output(self.output,self.packet,self.reasons)['semantic_reference_sufficiency'],'NOT_AUTOMATICALLY_VERIFIED')
 def test_length_not_normalized(self):self.assertIn('OUTPUT_LENGTH_LIMIT_REACHED',validate_output(self.output,self.packet,self.reasons,True)['errors'])
 def test_call_tool_never_executes(self):
  r=validate_output('{"action":"CALL_TOOL","tool":"equipment_start"}',self.packet,self.reasons);self.assertIn('UNSUPPORTED_ACTION_NO_EXECUTION',r['errors']);self.assertFalse(r['tool_execution'])
 def test_invalid_reason_type(self):
  p=parse_json(self.output);p.update(action='CHALLENGE',reason={});self.assertIn('INVALID_REASON_CODE',validate_output(json.dumps(p),self.packet,self.reasons)['errors'])
 def test_invalid_action_type(self):
  p=parse_json(self.output);p['action']=[];self.assertIn('ACTION_STRING_REQUIRED',validate_output(json.dumps(p),self.packet,self.reasons)['errors'])
class ServiceTests(ContractTests):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.stub=EngineStub();self.stub.output=self.output
  self.service=ReviewService(REG,Path(self.temp.name),engine=self.stub,enable_live=True)
 def tearDown(self):self.temp.cleanup()
 def runstub(self):return self.service.run(dict(mode='LIVE_MODEL_RUN',packet=self.packet,reviewed_packet=True))
 def reviewbody(self,r):return dict(content_hash=r['content_hash'],request_id=str(uuid.uuid4()),decision='ACCEPT',reviewer='SMOKE_TEST_UNIT_STUB',notes='Unit test only; not human review',correction_text=None)
 def test_manual_attestation_required(self):
  r=self.service.run(dict(mode='LIVE_MODEL_RUN',packet=self.packet));self.assertFalse(r['model_called']);self.assertEqual(self.stub.calls,0)
 def test_raw_duplicate_packet_rejected_and_preserved(self):
  raw='{"case_id":"one","case_id":"two"}'
  r=self.service.run(dict(mode='LIVE_MODEL_RUN',packet_text=raw,reviewed_packet=True));self.assertIn('DUPLICATE_JSON_KEY',r['validator']['errors'][0]);self.assertEqual(r['input_packet_text'],raw);self.assertEqual(self.stub.calls,0)
 def test_raw_packet_text_preserved(self):
  raw=json.dumps(self.packet,indent=3);r=self.service.run(dict(mode='LIVE_MODEL_RUN',packet_text=raw,reviewed_packet=True));self.assertEqual(r['input_packet_text'],raw);self.assertEqual(r['input_packet'],self.packet)
 def test_length_rejected_before_model(self):
  self.stub.ids=[1]*4096;r=self.runstub();self.assertFalse(r['model_called']);self.assertIn('INPUT_LENGTH_EXCEEDED',r['validator']['errors'][0]);self.assertEqual(self.stub.calls,0)
 def test_replay_input_change_rejected(self):
  p=copy.deepcopy(self.packet);p['packet']['review_question']+=' changed';r=self.service.run(dict(mode='REPLAY',packet=p,reviewed_packet=True));self.assertIn('REPLAY_INPUT_MISMATCH',r['validator']['errors'][0]);self.assertEqual(self.stub.calls,0)
 def test_runtime_failure_saved_no_retry(self):
  self.stub.error='SIMULATED_RUNTIME_ERROR';r=self.runstub();self.assertEqual(r['execution_status'],'RUN_FAILED');self.assertIsNone(r['model_output']);self.assertEqual(self.stub.calls,1)
 def test_accept_not_training(self):
  r=self.runstub();self.service.review(r['run_id'],self.reviewbody(r));e=self.service.store.events(r['run_id'])[0]['payload'];self.assertFalse(e['training_eligible']);self.assertFalse(e['engineering_approval']);self.assertTrue(e['automated_smoke'])
 def test_modify_preserves_original(self):
  r=self.runstub();body=self.reviewbody(r);body.update(decision='MODIFY',correction_text=self.output);self.service.review(r['run_id'],body);self.assertEqual(self.service.store.get_run(r['run_id'])['model_output'],r['model_output'])
 def test_reject_saved(self):
  r=self.runstub();b=self.reviewbody(r);b['decision']='REJECT';self.assertTrue(self.service.review(r['run_id'],b)['saved'])
 def test_stale_review_rejected(self):
  r=self.runstub();b=self.reviewbody(r);b['content_hash']='stale'
  with self.assertRaisesRegex(ValueError,'STALE'):self.service.review(r['run_id'],b)
 def test_idempotent_review(self):
  r=self.runstub();b=self.reviewbody(r);self.service.review(r['run_id'],b);self.assertTrue(self.service.review(r['run_id'],b)['duplicate']);b['notes']='changed'
  with self.assertRaisesRegex(ValueError,'CONFLICT'):self.service.review(r['run_id'],b)
 def test_unquoted_evidence_not_opened(self):
  r=self.runstub();b=dict(self.reviewbody(r),reference_id='UNPROVIDED')
  with self.assertRaisesRegex(ValueError,'REFERENCE_NOT_CITED'):self.service.open_evidence(r['run_id'],b)
 def test_invalid_cannot_accept(self):
  self.stub.output='not JSON';r=self.runstub()
  with self.assertRaisesRegex(ValueError,'CANNOT_ACCEPT'):self.service.review(r['run_id'],self.reviewbody(r))
if __name__=='__main__':unittest.main()
