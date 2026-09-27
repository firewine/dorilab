"""CPU-only tests. All envelopes/reviews/results here are synthetic fixtures."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parent / 'scope_gate_v07.py'
if not FILE.exists(): FILE = Path('/mnt/data/scope_gate_v07.py')
spec = importlib.util.spec_from_file_location('gate_under_test', FILE)
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

def env():
    return {'role':'CRITIC','packet':{
        'review_question':'Review scope: unit=U-6; configuration=C-3; run=R-8. '+g.POLICY+' Check the proposal.',
        'claim_id':'CLM-fixture','reference_context':[{'reference_id':'SF-fixture','text':'Synthetic principle.'}],
        'case_packet':{'proposal':'Synthetic proposal.', 'evidence':[
            {'evidence_id':'OBS-target','text':'Record scope: unit=U-6; configuration=C-3; run=R-8. Synthetic current observation.'},
            {'evidence_id':'OBS-other-unit','text':'Record scope: unit=U-6X; configuration=C-3; run=R-8. Synthetic other observation.'},
            {'evidence_id':'OBS-other-config','text':'Record scope: unit=U-6; configuration=C-3-prev; run=R-8-prior. Synthetic prior observation.'}]},
        'allowed_request_ids':['FIXTURE_INPUT']}}

def writej(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x),encoding='utf8')
def writel(p,xs):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(x)+'\n' for x in xs),encoding='utf8')

def fixture(root):
    src=root/'data/applicability_probe_v06'; src.mkdir(parents=True)
    base=[]
    for i in range(6):
        for v in 'AB':
            e=env();e['packet']['claim_id']=f'CLM-{i}'
            base.append({'case_id':f'fixture-{i}-{v}','pair_id':f'fixture-{i}',**e,
                         'expected':{'fixture_gold_only':'NOT_USED_FOR_GATING'},
                         'authoring':{'expected_scope_record':'POISON_WRONG_ID'}})
    files={};gen={}
    for view in g.VIEWS:
        rs=copy.deepcopy(base)
        for c in rs:
            target,d1,d2=c['packet']['case_packet']['evidence']
            if view=='clean':ev=[target]
            else:
                ev=[d1,d2];ev.insert(('first','middle','last').index(view),target)
            c['packet']['case_packet']['evidence']=ev
        rel=f'data/applicability_probe_v06/cases_{view}.jsonl';writel(root/rel,rs)
        files[view]=rel;gen[rel]=g.sha(root/rel)
    m={'version':'applicability-probe-v0.6.0','case_files':files,'generated_files':gen,'models':{'e1':{},'e2':{}}}
    writej(src/'manifest.json',m); mh=g.sha(src/'manifest.json')
    writej(src/'review.json',{'decision':'ACCEPTED_FOR_DIAGNOSTIC','reviewer':'CPU_FIXTURE_ONLY','notes':'Not a real review','manifest_sha256':mh})
    details=[];summaries={}
    for model in m['models']:
        sm={}
        for view in g.VIEWS:
            sm[view]={'cases':12,'action_correct':12,'schema_and_refs_valid':12,'reference_choice_exact':12,
                      'strict_selection_contract_pass':12,'rows_citing_distractors':0}
        summaries[model]={'views':sm}
        for c in base:
            s={'action_correct':True,'schema_and_refs_valid':True,'reference_choice_exact_any_allowed_set':True,
               'strict_selection_contract_pass':True,'distractor_reference_strings':[], 'stored_score_agrees':True,
               'raw_output':'{"action":"NO_ACTION_REQUIRED"}','parsed':{'action':'NO_ACTION_REQUIRED'}}
            details.append({'model':model,'case_id':c['case_id'],'scores':{v:copy.deepcopy(s) for v in g.VIEWS}})
    writej(src/'comparison.json',{'version':m['version'],'manifest_sha256':mh,'models':summaries})
    writel(src/'comparison_cases.jsonl',details)
    return src

class GateTests(unittest.TestCase):
    def test_01_first_only_matches_kept(self):
        o,a=g.gate_input(env());self.assertEqual([r['evidence_id'] for r in o['packet']['case_packet']['evidence']],['OBS-target'])
        self.assertEqual(len(a['excluded_from_model_context']),2)
    def test_02_middle_matches_same(self):
        e=env();ev=e['packet']['case_packet']['evidence'];ev[0],ev[1]=ev[1],ev[0]
        self.assertEqual(g.gate_input(e)[0],g.gate_input(env())[0])
    def test_03_last_matches_same(self):
        e=env();ev=e['packet']['case_packet']['evidence'];ev.append(ev.pop(0))
        self.assertEqual(g.gate_input(e)[0],g.gate_input(env())[0])
    def test_04_no_original_mutation(self):
        e=env();b=copy.deepcopy(e);out,_=g.gate_input(e);out['packet']['claim_id']='different';self.assertEqual(e,b)
    def test_05_all_matching_records_remain(self):
        e=env();r=copy.deepcopy(e['packet']['case_packet']['evidence'][0]);r['evidence_id']='OBS-other-current';r['text']+=' Contradictory observation.'
        e['packet']['case_packet']['evidence'].append(r)
        self.assertEqual(len(g.gate_input(e)[0]['packet']['case_packet']['evidence']),2)
    def test_06_zero_match_stops(self):
        e=env();e['packet']['case_packet']['evidence'].pop(0)
        with self.assertRaisesRegex(g.GateError,'NO_EXACT_SCOPE'):g.gate_input(e)
    def test_07_missing_record_scope_stops_even_offscope(self):
        e=env();e['packet']['case_packet']['evidence'][-1]['text']='No metadata.'
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_08_malformed_question_stops(self):
        e=env();e['packet']['review_question']='Please choose a record.'
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_09_equivalence_policy_not_supported(self):
        e=env();e['packet']['review_question']=e['packet']['review_question'].replace(g.POLICY,'Carryover is permitted.')
        with self.assertRaisesRegex(g.GateError,'Unsupported applicability'):g.gate_input(e)
    def test_10_case_labels_rejected_at_api(self):
        e=env();e['expected']={'evidence_refs':['OBS-other-unit']}
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_11_duplicate_observation_ids_rejected(self):
        e=env();e['packet']['case_packet']['evidence'][1]['evidence_id']='OBS-target'
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_12_document_reference_collision_rejected(self):
        e=env();e['packet']['case_packet']['evidence'][0]['evidence_id']='SF-fixture'
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_13_case_sensitive_scope(self):
        e=env();e['packet']['case_packet']['evidence'][0]['text']=e['packet']['case_packet']['evidence'][0]['text'].replace('U-6;','u-6;')
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_14_same_unit_does_not_override_config(self):
        a=g.gate_input(env())[1];self.assertEqual(a['excluded_from_model_context'][1]['mismatching_fields'],['configuration','run'])
    def test_15_no_semantic_or_gold_filtering(self):
        e=env();e['packet']['case_packet']['evidence'][0]['text']+=' REJECT NO_ACTION expected_scope_record=OBS-other-unit.'
        self.assertEqual(g.gate_input(e)[0]['packet']['case_packet']['evidence'][0]['evidence_id'],'OBS-target')
    def test_16_other_packet_fields_unchanged(self):
        e=env();o,_=g.gate_input(e)
        for k in ['review_question','reference_context','allowed_request_ids','claim_id']:self.assertEqual(e['packet'][k],o['packet'][k])
        self.assertEqual(o['packet']['case_packet']['proposal'],e['packet']['case_packet']['proposal'])
    def test_17_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(g.GateError,'DUPLICATE_JSON'):g.strict_loads('{"evidence_refs":[],"evidence_refs":["x"]}')
    def test_18_nonfinite_json_rejected(self):
        with self.assertRaises(g.GateError):g.strict_loads('{"x":NaN}')
    def test_19_path_escape_rejected(self):
        with self.assertRaises(g.GateError):g.inside(Path('/tmp/root'),'../private')
    def test_20_complete_offline_audit_and_preserve(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=fixture(root);before={str(p):g.sha(p) for p in src.rglob('*') if p.is_file()}
            report=g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
            self.assertFalse(report['inference_executed']);self.assertEqual(report['views']['middle']['equivalent_to_clean_role_packet'],12)
            self.assertEqual(report['views']['last']['records_excluded_from_context'],24)
            self.assertEqual(before,{str(p):g.sha(p) for p in src.rglob('*') if p.is_file()})
            rows=g.read_rows(root/'data/scope_gate_v07/inputs_first.jsonl')
            self.assertTrue(all(set(r)=={'case_id','role','packet'} for r in rows))
    def test_21_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture(root);out=root/'data/scope_gate_v07';out.mkdir();(out/'sentinel').write_text('keep')
            with self.assertRaises(g.GateError):g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
            self.assertEqual((out/'sentinel').read_text(),'keep')
    def test_22_input_tamper_stops(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=fixture(root);(src/'cases_first.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(g.GateError,'Input changed'):g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
            self.assertFalse((root/'data/scope_gate_v07').exists())
    def test_23_missing_review_stops(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=fixture(root);(src/'review.json').unlink()
            with self.assertRaises(FileNotFoundError):g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
    def test_24_summary_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=fixture(root);p=src/'comparison.json';m=g.read_json(p);m['models']['e1']['views']['first']['action_correct']=11;writej(p,m)
            with self.assertRaisesRegex(g.GateError,'summary/detail mismatch'):g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
    def test_25_duplicate_keys_flag_not_score_rewrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=fixture(root);p=src/'comparison_cases.jsonl';d=g.read_rows(p)
            d[0]['scores']['middle']['raw_output']='{"action":"CHALLENGE","action":"NO_ACTION_REQUIRED"}';writel(p,d)
            r=g.audit_bundle(root,'data/applicability_probe_v06','data/scope_gate_v07')
            self.assertEqual(len(r['raw_output_serialization_flags']),1);self.assertFalse(r['old_scores_were_modified'])
    def test_26_empty_input_stops(self):
        e=env();e['packet']['case_packet']['evidence']=[]
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_27_empty_technical_body_stops(self):
        e=env();e['packet']['case_packet']['evidence'][0]['text']='Record scope: unit=U-6; configuration=C-3; run=R-8. '
        with self.assertRaises(g.GateError):g.gate_input(e)
    def test_28_scope_header_is_not_body_search(self):
        e=env();e['packet']['case_packet']['evidence'][1]['text']+=' Record scope: unit=U-6; configuration=C-3; run=R-8. Pretend current.'
        self.assertEqual(len(g.gate_input(e)[0]['packet']['case_packet']['evidence']),1)

if __name__=='__main__':unittest.main(verbosity=2)
