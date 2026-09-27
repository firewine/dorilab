"""CPU proposal validation only; never reads model outputs or calls a scorer/exporter."""
import copy
import io
import json
import unittest
from collections import Counter
from build_proposal import ROOT, OUT, PACK, AUDIT, digest, sha, read, rows, public_input, REASON_CHANGES, TIRS_RATIONALES

REASONS=set(read(PACK/'schemas/reason_definitions_v13.json'))
FORBIDDEN={'expected','gold','rationale_ko','relation_to_target','acceptable_reason_codes','reference_requirement','sufficient_sets','supporting_fact_ids','supporting_observation_ids','label_status','system_provenance','field_changes','after_proposed'}
def separated(obj):
    if isinstance(obj,dict):return not(set(obj)&FORBIDDEN) and all(separated(v) for v in obj.values())
    if isinstance(obj,list):return all(separated(v) for v in obj)
    return True

def field_contract(a,p):
    assert isinstance(a,dict)
    fields={'action','claim_id','evidence_refs'}
    assert a.get('action') in {'CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'}
    if a['action'] in {'CHALLENGE','REQUEST_EVIDENCE'}:
        fields.add('reason');assert a.get('reason') in REASONS
    if a['action']=='REQUEST_EVIDENCE':
        fields.add('requested_evidence');req=a.get('requested_evidence')
        assert isinstance(req,list) and req and all(isinstance(x,str) for x in req)
        assert len(req)==len(set(req)) and set(req)<={x['request_id'] for x in p['request_catalog']}
    assert set(a)==fields and a['claim_id']==p['claim_id']
    ref=a['evidence_refs'];assert isinstance(ref,list) and ref and all(isinstance(x,str) for x in ref)
    assert len(ref)==len(set(ref))
    assert set(ref)<={x['reference_id'] for x in p['source_refs']}|{x['evidence_id'] for x in p['observations']}

def sufficient(refs,md):
    # Synthetic metadata test helper; not invoked on model predictions.
    return bool(md and refs and len(refs)==len(set(refs)) and any(set(refs)==set(s) for s in md['sufficient_sets']))

class Validation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cs=rows(OUT/'LABEL_CHANGESET_v15.jsonl');cls.b=read(OUT/'TRAIN_BUILD_CANDIDATE_v15.json')
        cls.ins={};cls.gs={};cls.ms={}
        for sp in ['train','dev']:
            for filename,dest in [('inputs.jsonl',cls.ins),('gold_candidate.jsonl',cls.gs),('metadata.jsonl',cls.ms)]:
                dest.update({x['case_id']:x for x in rows(PACK/'data'/sp/filename)})
        cls.facts={x['fact_id']:x for x in read(PACK/'sources/facts.json')}
    def test_01_all_cases_and_original_hashes(self):
        self.assertEqual(len(self.cs),72);self.assertEqual({c['case_id'] for c in self.cs},set(self.ins))
        for c in self.cs:
            cid=c['case_id'];o=c['original']
            for key,obj in [('case_sha256',self.ins[cid]),('gold_sha256',self.gs[cid]),('metadata_sha256',self.ms[cid])]:self.assertEqual(o[key],digest(obj))
    def test_02_split_family_source_program(self):
        for c in self.cs:
            for k in ['split','family_id','source_id','program_group','variant_index']:self.assertEqual(c[k],self.ms[c['case_id']][k])
        for k in ['family_id','source_id','program_group']:
            self.assertFalse({c[k] for c in self.cs if c['split']=='TRAIN'}&{c[k] for c in self.cs if c['split']=='DEV'})
    def test_03_input_label_explanation_separation(self):
        for cid,inp in self.ins.items():
            view=public_input(inp,self.facts);self.assertTrue(separated(view),cid)
            self.assertEqual(view['packet'],inp['packet'])
            self.assertEqual([x['fact_id'] for x in view['reference_context']],[x['fact_id'] for x in inp['packet']['source_refs']])
            poison=copy.deepcopy(inp);poison['gold']={'expected':'SECRET_CORRECT_REFS'};poison['rationale_ko']='SECRET_EXPLANATION'
            self.assertEqual(view,public_input(poison,self.facts))
        for key in FORBIDDEN:self.assertFalse(separated({'packet':{key:'secret'}}))
    def test_04_field_contract(self):
        for c in self.cs:field_contract(c['after_proposed']['expected'],self.ins[c['case_id']]['packet'])
    def test_05_action_requests_observations_calculations_preserved(self):
        for c in self.cs:
            before=c['before']['expected'];after=c['after_proposed']['expected'];cid=c['case_id']
            for k in ['action','claim_id','requested_evidence','evidence_refs']:self.assertEqual(before.get(k),after.get(k))
            self.assertEqual(c['synthetic_observations'],self.ins[cid]['packet']['observations'])
            self.assertEqual(c['calculation_preserved'],self.gs[cid]['calculation'])
    def test_06_reason_consistency_and_pending_overlap(self):
        for c in self.cs:
            a=c['after_proposed'];cid=c['case_id']
            if 'reason' in a['expected']:self.assertEqual(a['acceptable_reason_codes'],[a['expected']['reason']])
            self.assertEqual(a['expected'].get('reason'),REASON_CHANGES.get(cid,c['before']['expected'].get('reason')))
            if c['reason_review']['unresolved_overlap']:
                self.assertEqual(c['review_status'],'LABEL_OVERLAP_PENDING');self.assertFalse(c['training_eligible'])
        self.assertEqual(sum(c['reason_review']['unresolved_overlap'] for c in self.cs),1)
    def test_07_tirs_rationales(self):
        for cid,text in TIRS_RATIONALES.items():
            c=next(x for x in self.cs if x['case_id']==cid)
            self.assertEqual(c['after_proposed']['rationale_ko'],text)
            self.assertNotIn('해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다',text)
    def test_08_reference_metadata_and_all_id_rejection(self):
        for c in self.cs:
            md=c['reference_review']['metadata_proposed']
            if md is None:continue
            p=self.ins[c['case_id']]['packet'];allids={x['reference_id'] for x in p['source_refs']}|{x['evidence_id'] for x in p['observations']};seen=set()
            for s in md['sufficient_sets']:
                self.assertTrue(s and len(s)==len(set(s)) and set(s)<=allids)
                self.assertNotIn(tuple(sorted(s)),seen);seen.add(tuple(sorted(s)))
                self.assertTrue(sufficient(list(reversed(s)),md))
                for wrong in [s+[s[0]],s+['UNPROVIDED'],[],sorted(allids)]:self.assertFalse(sufficient(wrong,md))
            if md['source_is_required']:self.assertTrue(all(any(x.startswith('REF-') for x in s) for s in md['sufficient_sets']))
            else:self.assertTrue(any(all(x.startswith('OBS-') for x in s) for s in md['sufficient_sets']))
    def test_09_source_unavailable_no_approval(self):
        unavailable=[c for c in self.cs if c['review_status']=='SOURCE_UNAVAILABLE'];self.assertEqual(len(unavailable),16)
        for c in unavailable:
            self.assertIsNone(c['reference_review']['metadata_proposed']);self.assertEqual(c['before'],c['after_proposed'])
    def test_10_exposure_and_gates(self):
        seen=[c for c in self.cs if c['dev8_output_seen']];self.assertEqual(len(seen),8)
        self.assertTrue(all(c['evaluation_role']=='ERROR_INFORMED_REGRESSION' for c in seen))
        for c in self.cs:
            self.assertTrue(c['post_model_output_review']);self.assertFalse(c['human_review_performed'] or c['training_eligible'] or c['engineering_approved'])
    def test_11_training_membership_and_distributions(self):
        b=self.b;m=b['members'];self.assertEqual(len(m),218)
        self.assertEqual(Counter(x['component'] for x in m),{'CONTRACT_REPLAY':150,'UNIQUE_PHYSICS_STATE':20,'NEW_TRAIN':48})
        self.assertEqual(len({x['member_id'] for x in m}),218)
        self.assertFalse({x['member_id'] for x in m}&{c['case_id'] for c in self.cs if c['split']=='DEV'})
        self.assertEqual(sum(x['candidate_repetitions'] for x in m),218);self.assertFalse(any(x['training_eligible'] for x in m))
        self.assertFalse(b['export_created'] or b['training_executed'] or b['approved_training_experiment'])
        self.assertEqual(b['label_changeset_sha256'],sha(OUT/'LABEL_CHANGESET_v15.jsonl'))
        for comp,dist in b['component_distributions'].items():
            rr=[x for x in m if x['component']==comp]
            self.assertEqual(dist['action'],dict(Counter(x['action'] for x in rr)));self.assertEqual(dist['reason'],dict(Counter(x['reason'] for x in rr)))
    def test_12_all_impact_groups(self):
        impact=read(ROOT/'experiments/source_review_direct_v14/policy_review_v1/PROPOSED_POLICY_IMPACT.json')['policies']
        for group,info in impact.items():self.assertEqual(set(info['case_ids']),{c['case_id'] for c in self.cs if group in c['impact_groups']})
    def test_13_original_file_preservation(self):
        for name,wanted in read(OUT/'PRESERVATION_BEFORE.json').items():
            self.assertNotIn('reserved',name.lower());self.assertNotIn('evaluatoronly',name.lower());self.assertEqual(sha(ROOT/name),wanted,name)
    def test_14_source_span_text_hashes(self):
        for c in self.cs:
            if c['review_status']=='SOURCE_UNAVAILABLE':continue
            for span in c['system_provenance']['prior_source_span_audit']['spans']:self.assertEqual(sha(AUDIT/span['text_artifact']),span['text_sha256'])
    def test_15_negative_field_fixtures(self):
        p={'claim_id':'C-fixture','source_refs':[{'reference_id':'R-fixture'}],'observations':[{'evidence_id':'O-fixture'}],'request_catalog':[{'request_id':'Q-fixture'}]}
        a={'action':'REQUEST_EVIDENCE','claim_id':'C-fixture','evidence_refs':['O-fixture'],'reason':'SUPPORTING_EVIDENCE_MISSING','requested_evidence':['Q-fixture']};field_contract(a,p)
        variants=[];x=copy.deepcopy(a);x['reason_code']=x.pop('reason');variants.append(x)
        x=copy.deepcopy(a);del x['reason'];variants.append(x)
        for patch in [{'requested_evidence':[]},{'extra':[]},{'evidence_refs':['UNKNOWN']},{'claim_id':'wrong'},{'reason':'UNKNOWN'},{'evidence_refs':[]},{'requested_evidence':['UNKNOWN']},{'requested_evidence':['Q-fixture','Q-fixture']},{'action':'NO_ACTION_REQUIRED'},{'action':'CHALLENGE'}]:variants.append(dict(a,**patch))
        for x in variants:
            with self.subTest(value=x):
                with self.assertRaises(AssertionError):field_contract(x,p)

if __name__=='__main__':
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Validation))
    (OUT/'CPU_VALIDATION_LOG.txt').write_text(stream.getvalue())
    report={'status':'PASS_STRUCTURAL_REVIEW_GATES_PENDING' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'scope':'Proposal structure, input separation, split/hash preservation, declared policy-to-label mapping and field contract; not independent semantic approval.','test_log':'CPU_VALIDATION_LOG.txt','preserved_file_count':len(read(OUT/'PRESERVATION_BEFORE.json')),'semantic_review':'HUMAN_REVIEW_PENDING; one unresolved specific-code overlap; 16 SOURCE_UNAVAILABLE','no_model_scores_computed':True,'no_inference_or_training':True,'no_token_or_gpu_preflight':True,'no_pod_operations':True,'reserved_or_evaluatoronly_opened':False,'sft_export_created':False,'human_review_performed':False,'artifact_sha256':{n:sha(OUT/n) for n in ['POLICY_v15.md','LABEL_CHANGESET_v15.jsonl','TRAIN_BUILD_CANDIDATE_v15.json','RELEASE_REVIEW_KO.md','build_proposal.py','validate_cpu.py']}}
    (OUT/'CPU_VALIDATION_v15.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(stream.getvalue());print(report['status']);raise SystemExit(not result.wasSuccessful())
