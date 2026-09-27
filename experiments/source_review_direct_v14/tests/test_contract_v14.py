import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parents[1]
PACK=WORK/'research/DoriLab_SourceReview_v13'
sys.path[:0]=[str(ROOT/'scripts'),str(PACK)]
import packtool as p
import prepare_inputs as prep
from contract import FIELDS,assert_public,violations

class ContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.schema=json.loads((PACK/'schemas/action_v13.json').read_text())
  cls.validator=Draft202012Validator(cls.schema)
  cls.reasons=json.loads((PACK/'schemas/reason_definitions_v13.json').read_text())
  cls.prompt=(ROOT/'prompts/direct_v14.txt').read_text()
  cls.saved=p.rows(prep.BASE/'inputs/dev8_hypso_public_v13_source_available_v1.jsonl')
  cls.new=p.rows(ROOT/'inputs/dev8_direct_v14.jsonl')
 def fixture(self,action='CHALLENGE'):
  packet={'claim_id':'CLM-FORMAT-DEMO','source_refs':[{'reference_id':'REF-FORMAT-DEMO'}],
   'observations':[{'evidence_id':'OBS-FORMAT-DEMO'}],'request_catalog':[{'request_id':'REQ-FORMAT-DEMO'}]}
  a={'action':action,'claim_id':packet['claim_id'],'evidence_refs':['OBS-FORMAT-DEMO']}
  if action in {'CHALLENGE','REQUEST_EVIDENCE'}:a['reason']='METHOD_INTERPRETATION_ERROR'
  if action=='REQUEST_EVIDENCE':a['requested_evidence']=['REQ-FORMAT-DEMO']
  if action=='CALL_TOOL':a.update(tool='FORMAT_DEMO_TOOL',arguments={'record':'FORMAT_DEMO'})
  if action=='PROPOSE_FINDING':a['finding_type']='FORMAT_DEMO_FINDING'
  return packet,a
 def score(self,packet,answer,expected=None):
  # Handwritten synthetic schema fixtures; no evaluation gold copied or loaded.
  expected=expected or self.fixture(answer['action'])[1]
  gold={'expected':expected,'acceptable_reason_codes':[expected['reason']] if 'reason' in expected else []}
  return p.evaluate_output({'case_id':'CASE-FORMAT-DEMO','packet':packet},gold,json.dumps(answer),self.reasons,normalize=False)
 def test_01_all_five_field_lists_match_schema_and_prompt(self):
  common=set(self.schema['required'])
  for action,fields in FIELDS.items():
   extra=set()
   for rule in self.schema['allOf']:
    if rule['if']['properties']['action']['const']==action:extra.update(rule['then']['required'])
   self.assertEqual(common|extra,fields)
   line=next(x for x in self.prompt.splitlines() if x.startswith(action+':'))
   self.assertEqual(set(line.split(': ',1)[1].rstrip('.').split(', ')),fields)
 def test_02_all_five_synthetic_examples_pass_schema_and_scorer(self):
  for action in FIELDS:
   packet,a=self.fixture(action);self.validator.validate(a);p.check_answer(a,packet,self.reasons)
   self.assertTrue(self.score(packet,a)['strict_pass']);self.assertEqual(violations(a,packet),[])
 def test_03_prompt_example_is_valid_synthetic_json(self):
  examples=[json.loads(line) for line in self.prompt.splitlines() if line.startswith('{"action"')]
  self.assertEqual(len(examples),1)
  packet,_=self.fixture()
  for a in examples:
   self.validator.validate(a);p.check_answer(a,packet,self.reasons)
   self.assertTrue(self.score(packet,a)['strict_pass'])
 def test_04_reason_code_rejected_without_repair(self):
  packet,a=self.fixture();a['reason_code']=a.pop('reason');raw=json.dumps(a)
  self.assertFalse(self.validator.is_valid(a));r=self.score(packet,a)
  self.assertFalse(r['schema_valid']);self.assertEqual(r['raw_output'],raw)
  self.assertIn('reason_code',violations(a,packet))
 def test_05_missing_reason_for_both_actions(self):
  for action in ['CHALLENGE','REQUEST_EVIDENCE']:
   packet,a=self.fixture(action);del a['reason']
   self.assertFalse(self.validator.is_valid(a));self.assertFalse(self.score(packet,a)['schema_valid'])
 def test_06_empty_request_rejected(self):
  packet,a=self.fixture('REQUEST_EVIDENCE');a['requested_evidence']=[]
  self.assertFalse(self.validator.is_valid(a));self.assertFalse(self.score(packet,a)['schema_valid'])
  self.assertIn('empty_or_missing_request',violations(a,packet))
 def test_07_unnecessary_allowed_field_schema_vs_strict(self):
  packet,a=self.fixture('NO_ACTION_REQUIRED');a['tool']='UNNEEDED'
  self.validator.validate(a);self.assertTrue(self.score(packet,a)['schema_valid'])
  self.assertFalse(self.score(packet,a)['strict_pass']);self.assertIn('unnecessary:tool',violations(a,packet))
 def test_08_empty_optional_request_exposes_existing_validator_difference(self):
  packet,a=self.fixture();a['requested_evidence']=[]
  self.assertFalse(self.validator.is_valid(a)) # JSON Schema minItems applies whenever present.
  self.assertTrue(self.score(packet,a)['schema_valid']) # Legacy check_answer only requires nonempty on REQUEST.
  self.assertFalse(self.score(packet,a)['strict_pass'])
  self.assertIn('unnecessary:requested_evidence',violations(a,packet))
 def test_09_unknown_field_rejected(self):
  packet,a=self.fixture();a['explanation']='unneeded'
  self.assertFalse(self.validator.is_valid(a));self.assertFalse(self.score(packet,a)['schema_valid'])
 def test_10_unprovided_reference_scorer_rejects(self):
  packet,a=self.fixture();a['evidence_refs']=['REF-ABSENT']
  self.validator.validate(a) # ID membership is a packet-dependent scorer check.
  self.assertFalse(self.score(packet,a)['schema_valid']);self.assertIn('unprovided_reference',violations(a,packet))
 def test_11_wrong_claim_id_scorer_rejects(self):
  packet,a=self.fixture();a['claim_id']='CLM-ABSENT';self.assertFalse(self.score(packet,a)['schema_valid'])
 def test_12_unprovided_request_scorer_rejects(self):
  packet,a=self.fixture('REQUEST_EVIDENCE');a['requested_evidence']=['REQ-ABSENT'];self.assertFalse(self.score(packet,a)['schema_valid'])
 def test_13_duplicate_refs_rejected(self):
  packet,a=self.fixture();a['evidence_refs']*=2
  self.assertFalse(self.validator.is_valid(a));self.assertFalse(self.score(packet,a)['schema_valid'])
 def test_14_unconditional_all_ref_citation_is_not_strict_success(self):
  packet,a=self.fixture();a['evidence_refs'].append('REF-FORMAT-DEMO')
  self.assertTrue(self.score(packet,a)['schema_valid']);self.assertFalse(self.score(packet,a)['strict_pass'])
 def test_15_one_json_no_markdown(self):
  packet,a=self.fixture();g={'expected':a,'acceptable_reason_codes':[a['reason']]}
  for raw in ['```json\n'+json.dumps(a)+'\n```',json.dumps(a)+'\n{}']:
   self.assertFalse(p.evaluate_output({'case_id':'DEMO','packet':packet},g,raw,self.reasons)['json_valid'])
 def test_16_saved_case_membership_and_user_bytes_unchanged(self):
  self.assertEqual([x['case_id'] for x in self.saved],[x['case_id'] for x in self.new])
  for old,new in zip(self.saved,self.new):
   self.assertEqual(old['messages'][1],new['messages'][1]);self.assertEqual(new['messages'][0]['content'],self.prompt)
   self.assertEqual(prep.digest(new['messages']),new['messages_sha256'])
 def test_17_build_reads_no_gold_or_case_results(self):
  # Whole input builder runs under an explicit read allowlist, output in a temporary directory.
  allowed={prep.BASE/'EXPERIMENT_LOCK.json',prep.BASE/'RUN_MANIFEST.json',prep.BASE/'inputs/dev8_hypso_public_v13_source_available_v1.jsonl',PACK/'prompts/direct_v13.txt',PACK/'packtool.py'}
  original=Path.open
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'inputs').mkdir();(root/'prompts').mkdir();(root/'prompts/direct_v14.txt').write_text(self.prompt)
   allowed.update({root/'prompts/direct_v14.txt',root/'inputs/dev8_direct_v14.jsonl'})
   def guarded(path,mode='r',*a,**kw):
    if not any(c in mode for c in 'wax+'):self.assertIn(path,allowed)
    return original(path,mode,*a,**kw)
   with patch.object(prep,'ROOT',root),patch.object(Path,'open',guarded):prep.main()
   self.assertEqual(p.rows(root/'inputs/dev8_direct_v14.jsonl'),self.new)
 def test_18_gold_rationale_reference_set_leakage_blocked(self):
  for key in ['gold','rationale','rationale_ko','reference_requirement','acceptable_reason_codes','correct_references','expected']:
   with self.subTest(key=key),self.assertRaises(ValueError):assert_public({'nested':[{'nested':{key:['SECRET']}}]})
 def test_19_all_messages_are_public_with_no_assistant_answer(self):
  for row in self.new:
   self.assertEqual([x['role'] for x in row['messages']],['system','user'])
   assert_public(json.loads(row['messages'][1]['content']))
 def test_20_prompt_ids_are_disjoint_from_case_ids(self):
  # No label reads required: fabricated IDs occur in no public DEV packet.
  text=(PACK/'data/dev/inputs.jsonl').read_text()
  for identifier in ['CLM-FORMAT-DEMO','OBS-FORMAT-DEMO','REF-FORMAT-DEMO','REQ-FORMAT-DEMO']:self.assertNotIn(identifier,text)
 def test_21_semantic_prefix_suffix_and_reason_definitions_unchanged(self):
  old=(PACK/'prompts/direct_v13.txt').read_text();prefix=old.split('Use claim_id exactly as supplied.')[0]
  suffix=old.split('No tool execution is authorized by a model answer.',1)[1]
  self.assertTrue(self.prompt.startswith(prefix));self.assertTrue(self.prompt.endswith('No tool execution is authorized by a model answer.'+suffix))
  self.assertEqual(json.loads(self.prompt.split('Reason definitions:\n')[1]),self.reasons)
 def test_22_no_support_empty_refs_is_schema_allowed(self):
  packet,a=self.fixture('NO_ACTION_REQUIRED');a['evidence_refs']=[]
  self.validator.validate(a);p.check_answer(a,packet,self.reasons)
 def test_23_action_agreement_separated_from_schema(self):
  packet,a=self.fixture();a['reason_code']=a.pop('reason');r=self.score(packet,a)
  self.assertTrue(r['action_correct']);self.assertFalse(r['schema_valid'] and r['action_correct'])
if __name__=='__main__':unittest.main()
