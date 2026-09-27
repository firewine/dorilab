"""CPU-only release boundary tests. Synthetic approvals stay in memory, never become receipts."""
import copy,io,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from common import *
from analysis_contract import decide,current_usable
from exporter import ReleaseBlocked,load_candidates,validate_record,inference_messages,approval_check,export_release
from evaluation_gate import accepted_membership

def state(**kwargs):return {'task':'CHECK_AXIS_DURATION',**kwargs}
def current(verdict='COMPLIANT',axes=None):return {'status':'CURRENT','verdict':verdict,'affected_axes':axes or []}
def synthetic_approval():
 # Pure in-memory test fixture, not a user review and never written to an approval file.
 a=copy.deepcopy(read(OUT/'RELEASE_APPROVAL_PENDING.json'))
 a.update(status='APPROVED_FOR_EXPERIMENTAL_TRAINING',reviewer='UNIT_TEST_FIXTURE_ONLY',reviewed_at='2099-01-01T00:00:00Z')
 for k in ('source_program_split_audit_pass','legacy_corpus_audit_pass','candidate_label_policy_accepted','approved_training_experiment','analysis_contract_change_accepted','prior_review_reuse_accepted'):a[k]=True
 for r in a['case_reviews']:r.update(decision='APPROVED_FOR_TRAINING',reviewer=a['reviewer'],reviewed_at=a['reviewed_at'])
 for r in a['source_reviews']:r.update(content_verified=True,rights_approved=True,split_novelty_verified=True,reviewer=a['reviewer'],reviewed_at=a['reviewed_at'])
 return a

class Analysis(unittest.TestCase):
 def test_alias_equivalence_and_canonical_tool_argument(self):
  expected={'action':'CALL_TOOL','tool':'compare_axis_durations','arguments':{'required_s':10,'actual_by_axis':{'X':9}}}
  for aliases in ({'requirement_s':10},{'required_s':10},{'requirement_s':10,'required_s':10}):self.assertEqual(decide(state(**aliases,actual_by_axis={'X':9})),expected)
 def test_alias_conflict_never_chooses_including_current(self):
  self.assertEqual(decide(state(requirement_s=10,required_s=11,actual_by_axis={'X':10},tool_result=current()))['action'],'REQUEST_EVIDENCE')
 def test_invalid_alias_values_not_coerced(self):
  for x in (True,-1,float('nan'),float('inf'),'10'):
   self.assertEqual(decide(state(required_s=x,actual_by_axis={'X':10}))['action'],'REQUEST_EVIDENCE')
 def test_current_reused_with_inputs_missing(self):
  self.assertEqual(decide(state(tool_result=current())),{'action':'NO_ACTION_REQUIRED'})
 def test_noncompliant_current_is_no_extra_calculation(self):
  self.assertEqual(decide(state(required_s=10,actual_by_axis={'X':9},tool_result=current('NON_COMPLIANT',['X']))),{'action':'NO_ACTION_REQUIRED'})
 def test_stale_result_not_reused(self):
  r=dict(current(),status='STALE')
  self.assertEqual(decide(state(required_s=10,actual_by_axis={'X':10},tool_result=r))['action'],'CALL_TOOL')
 def test_current_contradiction_not_reused(self):
  self.assertEqual(decide(state(required_s=10,actual_by_axis={'X':9},tool_result=current()))['action'],'CALL_TOOL')
 def test_malformed_result_and_missing_inputs_request(self):
  self.assertEqual(decide(state(tool_result={'status':'CURRENT'}))['action'],'REQUEST_EVIDENCE')
  self.assertEqual(decide(state(tool_result=current(),actual_by_axis={'X':'unknown'}))['action'],'REQUEST_EVIDENCE')
 def test_unknown_or_duplicate_axes_not_reused(self):
  for axes in (['Y'],['X','X']):
   self.assertEqual(decide(state(required_s=10,actual_by_axis={'X':9},tool_result=current('NON_COMPLIANT',axes)))['action'],'CALL_TOOL')

class ReleaseBoundaries(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.manifest,cls.records=load_candidates()
 def test_all_30_old_targets_match_new_common_contract(self):
  r=read(OUT/'B02_COMPARISON_30.json');self.assertEqual(r['row_count'],30);self.assertEqual(r['mismatches'],[])
  self.assertEqual(len({x['new_system_sha256'] for x in r['rows']}),1)
 def test_206_and_call_tool10_not_185(self):
  self.assertEqual(len(self.records),206);self.assertEqual(self.manifest['action_distribution']['CALL_TOOL'],10)
  self.assertEqual(self.manifest['call_tool_check']['rc2_185_count'],0)
 def test_no_dev_or_excluded_families(self):
  ids={r['member_id'] for r in self.records};plan=read(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json')
  self.assertFalse(ids&{r['case_id'] for r in plan['members']})
  self.assertFalse(ids&{r['member_id'] for r in self.manifest['excluded_family_members']})
 def test_mutated_input_and_gold_fail(self):
  for pos in (0,1,2):
   r=copy.deepcopy(self.records[0]);r['messages'][pos]['content']+=' '
   with self.assertRaises(ReleaseBlocked):validate_record(r)
 def test_assistant_cannot_be_used_as_inference_input(self):
  with self.assertRaises(ReleaseBlocked):inference_messages({'messages':self.records[0]['messages']})
 def test_inference_rejects_gold_metadata(self):
  r=copy.deepcopy(next(r for r in self.records if r['contract_route']=='v15_rc1'))
  inp=json.loads(r['messages'][1]['content']);inp['gold']={'expected':'sentinel'};r['messages'][1]['content']=json.dumps(inp)
  with self.assertRaises(ReleaseBlocked):inference_messages({'messages':r['messages'][:-1]})
 def test_pending_approval_cannot_export(self):
  with tempfile.TemporaryDirectory() as d:
   output=Path(d)/'release'
   with self.assertRaises(ReleaseBlocked):export_release(OUT/'RELEASE_APPROVAL_PENDING.json',output)
   self.assertFalse(output.exists())
 def test_all_required_approval_gates_and_positive_in_memory_fixture(self):
  a=synthetic_approval();approval_check(a,self.manifest,self.records,sha(OUT/'LORA_SINGLE_CONFIG.json'))
  for field in ('approved_training_experiment','candidate_label_policy_accepted','source_program_split_audit_pass','legacy_corpus_audit_pass','analysis_contract_change_accepted','prior_review_reuse_accepted'):
   bad=copy.deepcopy(a);bad[field]=False
   with self.assertRaises(ReleaseBlocked):approval_check(bad,self.manifest,self.records,sha(OUT/'LORA_SINGLE_CONFIG.json'))
 def test_approval_cannot_select_dev_or_change_hashes(self):
  a=synthetic_approval()
  for changed in ('membership','input','gold','source','bundle','config'):
   bad=copy.deepcopy(a)
   if changed=='membership':bad['approved_member_ids'][0]='RESERVED_TEST_SENTINEL_NO_FILE_ACCESS'
   elif changed in ('input','gold'):bad['case_reviews'][0][changed+'_sha256']='0'*64
   elif changed=='source':bad['source_reviews'][0]['rights_approved']=False
   elif changed=='bundle':bad['approval_bundle_sha256']='0'*64
   else:bad['training_configuration_sha256']='0'*64
   with self.assertRaises(ReleaseBlocked):approval_check(bad,self.manifest,self.records,sha(OUT/'LORA_SINGLE_CONFIG.json'))
 def test_trainer_rejects_not_released_before_checkpoint_or_gpu(self):
  from train_once import run
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'pending.json';p.write_text('{"status":"NOT_RELEASED"}')
   with patch('train_once.verify_checkpoint',side_effect=AssertionError('must not reach model assets')):
    with self.assertRaises(ReleaseBlocked):run(p,None,Path(d),Path(d)/'output')
   self.assertFalse((Path(d)/'output').exists())
 def test_evaluation_denominators_and_complete_families(self):
  plan=read(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json');a=read(OUT/'EVALUATION_APPROVAL_PENDING.json')
  with self.assertRaises(ReleaseBlocked):accepted_membership(a)
  a.update(status='APPROVED_FOR_EVALUATION',reviewer='UNIT_TEST_FIXTURE_ONLY',reviewed_at='2099-01-01T00:00:00Z',accepted_primary_strict_ids=plan['primary_strict_ids'],accepted_reason_review_ids=plan['primary_reason_applicable_ids'])
  result=accepted_membership(a);self.assertEqual(result['strict_denominator'],15);self.assertEqual(result['reason_denominator'],7);self.assertEqual(len(result['complete_family_ids']),3)
  a['accepted_reason_review_ids']=a['accepted_reason_review_ids']+plan['diagnostic_ids']
  with self.assertRaises(ReleaseBlocked):accepted_membership(a)
 def test_historical_review_reuse_is_actual_and_scoped(self):
  b=read(OUT/'APPROVAL_BUNDLE.json');history=b['historical_review_reuse']
  self.assertTrue(all(history['matching_checks'].values()));self.assertEqual(len(history['physics_case_reviews']),20)
  for r in history['physics_case_reviews']:
   self.assertTrue(r['original_review']['reviewer']);self.assertIn('position',r['augmentation_exact_match']);self.assertTrue(r['original_review']['reviewed_at'].startswith('2026-09-18'))
  self.assertFalse(b['new_human_review_performed']);self.assertFalse(b['experimental_training_approved'])
 def test_single_configuration_steps_and_modules(self):
  c=read(OUT/'LORA_SINGLE_CONFIG.json');self.assertEqual(c['total_optimizer_steps'],math.ceil(206/4)*2);self.assertEqual(c['total_example_presentations'],412)
  targets=read(OUT/'LORA_TARGET_MODULES.json')['target_modules'];self.assertEqual(len(targets),496)
  self.assertTrue(all(n.startswith('model.language_model.layers.') for n in targets));self.assertFalse(c['gpu_memory_fit_verified'])
 def test_prior_artifacts_preserved(self):
  for p,h in read(OUT/'PRESERVATION_BEFORE.json')['files'].items():self.assertEqual(sha(p),h,p)

class TokenBoundaries(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from tokenization import processor
  cls.proc,_=processor();cls.records=load_candidates()[1]
 def test_native_mask_padding_eos_and_no_truncation(self):
  from tokenization import encode,collate
  selected=[self.records[0],next(r for r in self.records if r['contract_route']=='analysis_alias_rc3'),next(r for r in self.records if r['contract_route']=='v15_rc1')]
  enc=[]
  for row in selected:
   value,st=encode(self.proc,row,4096);enc.append(value)
   self.assertTrue(all(x==-100 for x in value['labels'][:st['prompt_tokens']]))
   supervised=[x for x in value['labels'] if x!=-100];self.assertEqual(supervised[-1],self.proc.tokenizer.convert_tokens_to_ids('<|im_end|>'))
   with self.assertRaises(ReleaseBlocked):encode(self.proc,row,len(value['input_ids'])-1)
  batch=collate(enc,self.proc.tokenizer.pad_token_id,tensors=True)
  for i,r in enumerate(enc):
   self.assertTrue(all(x==-100 for x in batch['labels'][i,len(r['input_ids']):].tolist()))
  self.assertEqual(str(batch['labels'].device),'cpu')

if __name__=='__main__':
 stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
 d=OUT/'tests';d.mkdir(exist_ok=True);serial=len(list(d.glob('run_*.json')))+1
 text(f'tests/run_{serial:03d}.log',stream.getvalue())
 put(f'tests/run_{serial:03d}.json',{'created_at_utc':now(),'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'synthetic_approvals_in_memory_only':True,'actual_release_exports':0,'gpu_training_or_inference_executed':False})
 status('RC3_IMPLEMENTATION_TESTS_COMPLETE' if result.wasSuccessful() else 'RC3_IMPLEMENTATION_TESTS_FAILED',[f'CPU boundary tests {result.testsRun}, failures {len(result.failures)}, errors {len(result.errors)}'],['실제 승인 및 GPU fit 검증 대기'],[f'tests/run_{serial:03d}.json',f'tests/run_{serial:03d}.log'],['최종 보고·checksum 봉인'],['B03_USER_REVIEW','GPU_MEMORY_UNVERIFIED'])
 print(stream.getvalue());raise SystemExit(not result.wasSuccessful())
