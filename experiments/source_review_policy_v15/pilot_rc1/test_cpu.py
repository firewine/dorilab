import copy,io,json,re,unittest
from collections import Counter
from build_pilot import ROOT,OUT,V15,PACK,LEGACY,HOLD_FACTS,LEGACY_HOLD,rows,read,digest,sha,input_messages
from reference_contract import matches_sufficient_set as match,evaluate_approved_metadata as gate

BAD={'expected','gold','rationale_ko','acceptable_reason_codes','reference_requirement','sufficient_sets','relation_to_target','supporting_fact_ids','supporting_observation_ids','training_eligible'}
def separated(obj):
 if isinstance(obj,dict):return not(set(obj)&BAD) and all(separated(x) for x in obj.values())
 if isinstance(obj,list):return all(separated(x) for x in obj)
 return True

def check_fields(a,p):
 fields={'action','claim_id','evidence_refs'}
 assert a['action'] in {'CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'}
 if a['action'] in {'CHALLENGE','REQUEST_EVIDENCE'}:
  fields.add('reason');assert a['reason'] in read(OUT/'reason_definitions_rc1.json')
 if a['action']=='REQUEST_EVIDENCE':
  fields.add('requested_evidence');r=a['requested_evidence'];assert r and len(r)==len(set(r))
  assert set(r)<={x['request_id'] for x in p['request_catalog']}
 assert set(a)==fields and a['claim_id']==p['claim_id']
 refs=a['evidence_refs'];assert isinstance(refs,list) and refs and len(refs)==len(set(refs))
 assert set(refs)<={x['reference_id'] for x in p['source_refs']}|{x['evidence_id'] for x in p['observations']}

class CPU(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.m=read(OUT/'PILOT_TRAIN_MEMBERSHIP.json');cls.legacy=rows(LEGACY)
  cls.train=rows(OUT/'TRAIN36_INPUTS.jsonl');cls.tgold=rows(OUT/'TRAIN36_LABEL_CANDIDATE.jsonl')
  cls.dev=rows(OUT/'dev16/INPUTS.jsonl');cls.dgold=rows(OUT/'dev16/GOLD_AI_CANDIDATE.jsonl')
  cls.dm=rows(OUT/'dev16/METADATA.jsonl');cls.pre=rows(OUT/'MODEL_INPUT_PREVIEWS.jsonl')
 def test_01_original_files_preserved(self):
  for p,h in read(OUT/'PRESERVATION_BEFORE.json').items():self.assertEqual(sha(ROOT/p),h,p)
 def test_02_three_whole_families_held(self):
  held=[x for x in self.m['held_members'] if x['pilot_status']=='FAMILY_HELD_BY_USER']
  self.assertEqual(len(held),12);self.assertEqual(Counter(x['held_fact_family'] for x in held),{f:4 for f in HOLD_FACTS})
  ids={m['member_id'] for m in self.m['selected_candidates']};self.assertFalse(ids&{m['member_id'] for m in held})
 def test_03_actual_counts_and_pending_approvals(self):
  self.assertEqual(self.m['ceiling_distribution']['rows'],206);self.assertEqual(self.m['selected_candidate_rows'],205)
  self.assertEqual(self.m['approved_or_exportable_rows'],0)
  self.assertEqual(Counter(m['component'] for m in self.m['selected_candidates']),{'CONTRACT_REPLAY':150,'UNIQUE_PHYSICS_STATE':19,'NEW_TRAIN':36})
  self.assertFalse(any(x['training_eligible'] for x in self.m['selected_candidates']))
  for k,d in self.m['component_distributions'].items():
   rr=[m for m in self.m['selected_candidates'] if m['component']==k]
   self.assertEqual(d['reason'],dict(Counter(m['reason'] for m in rr)));self.assertEqual(d['action'],dict(Counter(m['action'] for m in rr)))
 def test_04_legacy_actual_messages_preserved(self):
  plan=read(V15/'TRAIN_BUILD_CANDIDATE_v15.json');orig={m['member_id']:m for m in plan['members']}
  for r in self.pre:
   if r['component']=='NEW_TRAIN':continue
   m=orig[r['member_id']];row=self.legacy[m['source_row_index_0based']]
   self.assertEqual(digest(row),m['source_row_sha256'])
   self.assertEqual(r['messages'],[x for x in row['messages'] if x['role']!='assistant'])
   self.assertEqual(r['messages_sha256'],digest(r['messages']))
 def test_05_contract_in_actual_system_not_metadata(self):
  for r in self.pre:
   system='\n'.join(x['content'] for x in r['messages'] if x['role']=='system')
   self.assertTrue(system)
   if r['component']=='NEW_TRAIN':
    self.assertIn('DoriLab SourceReview v15 pilot RC1',system);self.assertIn('First decide action',system);self.assertIn('no specific code applies',system)
    self.assertIn('reason, never reason_code',system)
   else:self.assertNotIn('DoriLab SourceReview v15 pilot RC1',system)
 def test_06_all_input_previews_have_no_label_or_rationale(self):
  for r in self.pre+rows(OUT/'dev16/MODEL_INPUT_PREVIEWS.jsonl'):
   self.assertTrue(all(x['role'] in {'system','user'} for x in r['messages']))
   if r.get('component','NEW_TRAIN')=='NEW_TRAIN':
    u=json.loads(r['messages'][1]['content']);self.assertTrue(separated(u))
  facts=read(OUT/'dev16/INPUT_FACTS.json')
  for inp in self.dev:
   orig=input_messages(inp,facts);poison=copy.deepcopy(inp);poison['gold']={'sufficient_sets':['SECRET']};poison['rationale_ko']='SECRET'
   self.assertEqual(orig,input_messages(poison,facts))
   u=json.loads(orig[1]['content']);self.assertEqual(len(u['reference_context']),len(inp['packet']['source_refs']))
 def test_07_no_as_run_computational_extension(self):
  old=read(PACK/'schemas/reason_definitions_v13.json');new=read(OUT/'reason_definitions_rc1.json')
  self.assertEqual(old['AS_RUN_MISSING'],new['AS_RUN_MISSING'])
  for g in self.tgold:
   if g['expected'].get('reason')=='AS_RUN_MISSING':
    inp=next(x for x in self.train if x['case_id']==g['case_id']);txt=json.dumps(inp).lower()
    self.assertTrue('vacuum' in txt or 'retest' in txt)
  for cid in ['CASE-c51cdfeccd','CASE-6de39fe5d2']:
   g=next(x for x in self.tgold if x['case_id']==cid);self.assertFalse(g['physical_as_run_fit_review']['human_approval'])
 def test_08_tirs_rationales_preserved(self):
  originals={g['case_id']:g for g in rows(V15/'LABEL_CHANGESET_v15.jsonl')}
  for cid in ['CASE-79c814ab47','CASE-424419171a','CASE-e00c7fe02d']:
   g=next(x for x in self.tgold if x['case_id']==cid);self.assertEqual(g['rationale_ko'],originals[cid]['after_proposed']['rationale_ko'])
 def test_09_reference_all_provided_exact_approved_is_allowed(self):
  md={'approved':True,'sufficient_sets':[['S-demo','O-demo']]}
  self.assertTrue(gate(['O-demo','S-demo'],['S-demo','O-demo'],md))
 def test_10_reference_all_provided_with_distractor_is_rejected(self):
  md={'approved':True,'sufficient_sets':[['S-demo','O-demo']]}
  self.assertFalse(gate(['S-demo','O-demo','DISTRACTOR'],['S-demo','O-demo','DISTRACTOR'],md))
 def test_11_reference_negative_boundaries(self):
  md={'approved':True,'sufficient_sets':[['O-demo'],['S-demo','O-demo']]};provided=['O-demo','S-demo','NOISE']
  self.assertTrue(gate(['O-demo'],provided,md))
  for bad in [[],['UNKNOWN'],['S-demo'],['O-demo','O-demo'],['O-demo','NOISE']]:self.assertFalse(gate(bad,provided,md))
  self.assertIsNone(gate(['O-demo'],provided,dict(md,approved=False)))
 def test_12_dev16_identity_fields_and_candidate_sets(self):
  self.assertEqual(len(self.dev),16);self.assertEqual(len({x['case_id'] for x in self.dev}),16)
  for inp,g in zip(self.dev,self.dgold):
   self.assertEqual(inp['case_id'],g['case_id']);check_fields(g['expected'],inp['packet'])
   refs=[x['reference_id'] for x in inp['packet']['source_refs']]+[x['evidence_id'] for x in inp['packet']['observations']]
   self.assertTrue(match(g['expected']['evidence_refs'],refs,g['reference_requirement']['sufficient_sets']))
   self.assertIsNone(gate(g['expected']['evidence_refs'],refs,g['reference_requirement']))
   self.assertFalse(g['human_review_performed'] or g['training_eligible'] or g['model_outputs_seen_for_this_candidate'])
  for inp,g in zip(self.train,self.tgold):check_fields(g['expected'],inp['packet'])
 def test_13_split_exclusion(self):
  olddev={m['case_id'] for m in rows(PACK/'data/dev/metadata.jsonl')};newdev={m['case_id'] for m in self.dm}
  selected={m['member_id'] for m in self.m['selected_candidates']};self.assertFalse(selected&(olddev|newdev))
  audit=read(OUT/'dev16/SPLIT_AUDIT.json')
  for k in ['source_overlap','program_overlap','family_overlap']:self.assertEqual(audit[k],[])
  self.assertFalse(audit['reserved_evaluatoronly_opened'])
 def test_14_source_bytes_and_spans(self):
  a=read(OUT/'sources/SOURCE_AUDIT_RC1.json')
  self.assertEqual(len(a['sources']),2)
  for s in a['sources']:
   p=OUT/s['local_pdf'];self.assertTrue(p.read_bytes().startswith(b'%PDF'));self.assertEqual(sha(p),s['pdf_sha256'])
  for f in a['original_fact_review']+a['new_method_facts']:
   for sp in f['spans']:
    p=OUT/sp['text_artifact'];self.assertEqual(sha(p),sp['text_sha256']);norm=' '.join(p.read_text().split());self.assertTrue(norm[sp['normalized_character_start']:].startswith(sp['normalized_anchor']))
 def test_15_source_dependency_inventory_not_inference_claim(self):
  self.assertEqual(sum(m['source_required'] for m in self.dm),8)
  self.assertEqual(Counter(m['kind'] for m in self.dm),{'METHOD_DEPENDENT_REVISION':8,'OBSERVATION_SUFFICIENT_CONTROL':8})
  for m,g in zip(self.dm,self.dgold):
   if m['source_required']:
    self.assertTrue(all(any(x.startswith('REF-') for x in s) for s in g['reference_requirement']['sufficient_sets']))
    self.assertIn('not model ablation',m['removal_check_method'])
 def test_16_pre_output_freeze_integrity(self):
  f=read(OUT/'dev16/PRE_OUTPUT_FREEZE.json')
  for name,h in f['file_sha256'].items():self.assertEqual(sha(OUT/name),h)
  self.assertFalse(f['model_inference_executed'] or f['human_review_performed'])
 def test_17_legacy_conflict_not_rewritten(self):
  holds={m['member_id']:m for m in self.m['held_members']}
  for mid in LEGACY_HOLD:
   self.assertEqual(holds[mid]['reason'],'EVIDENCE_INTERPRETATION_ERROR')
   self.assertEqual(holds[mid]['pilot_status'],'HELD_LEGACY_LABEL_COMPATIBILITY')
   self.assertFalse(next(p['candidate_selected'] for p in self.pre if p['member_id']==mid))
if __name__=='__main__':
 stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CPU))
 (OUT/'CPU_TEST_LOG.txt').write_text(stream.getvalue())
 report={'status':'PASS_CPU_ONLY_APPROVALS_PENDING' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'selected_candidates':205,'training_approved_rows':0,'source_pdfs_acquired':2,'dev_candidates':16,'source_dependency_status':'AI_COUNTERFACTUAL_AUTHOR_REVIEW_NOT_MODEL_ABLATION_OR_HUMAN_APPROVAL','reference_boundary_tests':'all-provided exact approved sufficient set passes; all-provided with irrelevant ID fails','existing_scorer_or_scores_changed':False,'training_export_created':False,'model_inference_or_training_executed':False,'token_or_gpu_preflight_executed':False,'pod_operations_executed':False}
 (OUT/'CPU_VALIDATION_RC1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(stream.getvalue());raise SystemExit(not result.wasSuccessful())
