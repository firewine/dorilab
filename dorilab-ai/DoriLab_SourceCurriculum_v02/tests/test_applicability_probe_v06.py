import contextlib
import copy
import importlib.util
import io
import os
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'applicability_probe_v06.py'
SPEC = importlib.util.spec_from_file_location('app_probe', SOURCE)
p = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(p)


def parents_fixture():
    out = []
    for i, t in enumerate(p.TOPICS):
        domain = ('THERMAL', 'THERMAL', 'VIBRATION', 'VIBRATION', 'EEE', 'EEE')[i]
        source = ('TH-01', 'TH-01', 'VB-X1', 'VB-X1', 'EE-02', 'EE-03')[i]
        ans = {'action': t['negative_action'], 'reason': t['reason'], 'claim_id': f'CLM-OLD-{i}', 'evidence_refs': [f'SF-OLD-{i}', 'OBS-1']}
        if t['request_ids']: ans['requested_evidence'] = t['request_ids'][:]
        out.append({'case_id': t['parent'], 'pair_id': t['parent'].removeprefix('PHY-').removesuffix('-A'),
                    'role': 'EVIDENCE' if t['request_ids'] else 'CRITIC', 'domain': domain, 'source_id': source,
                    'source_program_groups': ['TEST_FIXTURE_ONLY'], 'source_fact_ids': [f'SF-OLD-{i}'],
                    'packet': {'claim_id': f'CLM-OLD-{i}', 'reference_context': [{'reference_id': f'SF-OLD-{i}', 'source_id': source,
                               'text': f'UNIT TEST PLACEHOLDER {i}; not a reviewed source excerpt.', 'section': 'unit-test fixture'}],
                               'case_packet': {'evidence': [{'evidence_id':'OBS-1','text':'Old fixture observation'}], 'proposal':'Old fixture proposal'},
                               'allowed_request_ids': t['request_ids'][:]}, 'expected': ans})
    return out

class DataTests(unittest.TestCase):
    def setUp(self): self.parents = parents_fixture(); self.views, self.topics = p.make_cases(self.parents)
    def test_01_counts(self):
        self.assertEqual({v:len(x) for v,x in self.views.items()}, {v:12 for v in p.VIEWS})
    def test_02_design(self): self.assertTrue(p.design_check(self.views,self.parents))
    def test_03_classes(self):
        self.assertEqual(Counter(c['expected']['action'] for c in self.views['clean']), {'CHALLENGE':3,'REQUEST_EVIDENCE':3,'NO_ACTION_REQUIRED':6})
    def test_04_no_parent_mutation(self): self.assertEqual(self.parents, parents_fixture())
    def test_05_source_verbatim(self):
        for c in self.views['clean']:
            old=next(x for x in self.parents if x['case_id']==c['authoring']['parent_case_id'])['packet']['reference_context'][0]
            new=copy.deepcopy(c['packet']['reference_context'][0]);new['reference_id']=old['reference_id']; self.assertEqual(old,new)
    def test_06_proposal_and_question_constant(self):
        for i in range(1,7):
            cs=[c for c in self.views['clean'] if c['pair_id']==f'AP06-{i:02d}']
            self.assertEqual(cs[0]['packet']['review_question'],cs[1]['packet']['review_question'])
            self.assertEqual(cs[0]['packet']['case_packet']['proposal'],cs[1]['packet']['case_packet']['proposal'])
    def test_07_only_target_body_changes(self):
        for i in range(1,7):
            cs=[copy.deepcopy(c['packet']) for c in self.views['first'] if c['pair_id']==f'AP06-{i:02d}']
            for c in cs:c['case_packet']['evidence'][0].pop('text')
            self.assertEqual(*cs)
    def test_08_view_positions(self):
        for v in p.POSITION_VIEWS:
            for c in self.views[v]: self.assertEqual(c['packet']['case_packet']['evidence'][p.POSITION_VIEWS.index(v)]['evidence_id'],c['authoring']['expected_scope_record'])
    def test_09_clean_removes_only_offscope(self):
        for c in self.views['clean']:
            self.assertEqual(len(c['packet']['case_packet']['evidence']),1)
            b=next(x for x in self.views['first'] if x['case_id']==c['case_id'])
            self.assertEqual(c['packet']['case_packet']['evidence'][0],b['packet']['case_packet']['evidence'][0])
    def test_10_balanced_variant_direction(self):
        for v in ['A','B']:self.assertEqual(sum(c['expected']['action']=='NO_ACTION_REQUIRED' for c in self.views['first'] if c['variant']==v),3)
    def test_11_reason_and_request_preserved(self):
        byid={c['case_id']:c for c in self.parents}
        for c in self.views['first']:
            if c['expected']['action']=='NO_ACTION_REQUIRED':continue
            e=byid[c['authoring']['parent_case_id']]['expected']; self.assertEqual(c['expected']['reason'],e['reason'])
            self.assertEqual(c['expected'].get('requested_evidence'),e.get('requested_evidence'))
    def test_12_no_unreviewed_autoapproval(self):
        self.assertTrue(all(c['human_review_status']=='PENDING' for c in self.views['first']))
    def test_13_strict_set_gold(self):
        for c in self.views['first']:
            self.assertEqual(len(c['expected']['evidence_refs']),2)
            self.assertFalse(set(c['expected']['evidence_refs']) & set(c['authoring']['off_scope_record_ids']))
    def test_14_parent_enum_mismatch_stops(self):
        self.parents[0]['expected']['reason']='OTHER'
        with self.assertRaises(ValueError):p.make_cases(self.parents)
    def test_15_source_rewrite_detected(self):
        self.views['first'][0]['packet']['reference_context'][0]['text']='altered'
        with self.assertRaises(ValueError):p.design_check(self.views,self.parents)
    def test_16_order_changes_no_content(self):
        base={c['case_id']:c for c in self.views['first']}
        for c in self.views['last']:
            self.assertEqual({x['evidence_id']:x['text'] for x in c['packet']['case_packet']['evidence']}, {x['evidence_id']:x['text'] for x in base[c['case_id']]['packet']['case_packet']['evidence']})
    def test_17_deterministic(self): self.assertEqual(p.make_cases(self.parents)[0],self.views)
    def test_18_different_seed_new_ids(self):
        b=p.make_cases(self.parents,99)[0];self.assertNotEqual(b['first'],self.views['first'])
    def test_19_no_target_or_gold_in_input_metadata(self):
        for c in self.views['first']:
            self.assertFalse({'expected','rationale_ko','authoring','variant'} & set(c['packet']))
    def test_20_review_html(self):
        s=p.review_html(self.views,self.topics)
        self.assertIn('전부 가상',s);self.assertIn('AP06-01-A',s);self.assertIn('48개',s)
    def test_21_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):p.strict('{"x":1,"x":2}')
    def test_22_nonfinite_rejected(self):
        with self.assertRaises(ValueError):p.strict('{"x":NaN}')
    def test_23_path_escape(self):
        with self.assertRaises(ValueError):p.local(Path('/tmp'),Path('../bad'))
    def test_24_malformed_output_helpers(self):
        self.assertIsNone(p.action_of({'parsed':[]}));self.assertEqual(p.refs_of({'parsed':{'evidence_refs':None}}),'null')

COMMON = '''from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def validate_answer(a,c):
    if not isinstance(a,dict):raise ValueError('dict required')
    if a.get('claim_id')!=c['packet']['claim_id']:raise ValueError('claim mismatch')
    if a.get('action') not in ('CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'):raise ValueError('action')
    refs=a.get('evidence_refs')
    if not isinstance(refs,list) or not all(isinstance(x,str) for x in refs):raise ValueError('string refs')
    allowed={x['reference_id'] for x in c['packet']['reference_context']} | {x['evidence_id'] for x in c['packet']['case_packet']['evidence']}
    if not set(refs)<=allowed:raise ValueError('unprovided ref')
    if a['action']!='NO_ACTION_REQUIRED' and not a.get('reason'):raise ValueError('reason required')
    if a['action']=='REQUEST_EVIDENCE' and not a.get('requested_evidence'):raise ValueError('request required')
    if not set(a.get('requested_evidence',[]))<=set(c['packet']['allowed_request_ids']):raise ValueError('request not allowed')

def answer_matches(e,a):
    if not isinstance(a,dict):return False
    for k,v in e.items():
        z=a.get(k)
        if isinstance(v,list):
            if not isinstance(z,list):return False
            if k=='evidence_refs':
                if not all(x in z for x in v):return False
            elif sorted(v)!=sorted(z):return False
        elif z!=v:return False
    return True
'''
EVALUATOR = '''import argparse,json,hashlib
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser()
for k in ['cases','adapter','out','model','revision','purpose','max-new-tokens']:p.add_argument('--'+k,required=True)
a=p.parse_args();rs=[json.loads(x) for x in Path(a.cases).read_text().splitlines() if x]
out=Path(a.out)
rows=[dict(case_id=c['case_id'],pair_id=c['pair_id'],expected=c['expected'],parsed=c['expected'],raw_output=json.dumps(c['expected']),strict_json_valid=True,schema_and_refs_valid=True,action_ok=True,contract_pass=True) for c in rs]
with out.open('x') as f:
    for r in rows:f.write(json.dumps(r)+'\\n')
s={'purpose':a.purpose,'model':a.model,'records':len(rows),'case_file_sha256':sha(a.cases),'adapter_sha256':sha(Path(a.adapter)/'adapter_model.safetensors'),'prompt_sha256':sha('dcurr/prompts.py'),'strict_json_valid':len(rows),'schema_and_refs_valid':len(rows),'action_correct':len(rows),'contract_pass':len(rows)}
with out.with_suffix('.summary.json').open('x') as f:json.dump(s,f)
print('FAKE TEST EVALUATOR: no model loaded',len(rows))
'''

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for key in list(sys.modules):
            if key=='dcurr' or key.startswith('dcurr.'):sys.modules.pop(key)
        r=self.root;(r/'dcurr').mkdir();(r/'data').mkdir();(r/'dcurr/__init__.py').write_text('')
        (r/'dcurr/common.py').write_text(COMMON)
        (r/'dcurr/evaluate.py').write_text(EVALUATOR)
        for n in ['model_io.py','prompts.py','prompts_legacy.py']:(r/'dcurr'/n).write_text('# fake test fixture only\n')
        (r/'data/action_schema_v02.json').write_text('{}')
        p.writel(r/p.PARENT,parents_fixture())
        shutil.copy(HERE/'evidence_probe_v04.py',r/'evidence_probe_v04.py')
        models=copy.deepcopy(p.MODELS)
        for label,s in models.items():
            d=r/s['adapter'];d.mkdir(parents=True)
            (d/'adapter_model.safetensors').write_text('FAKE WEIGHTS '+label)
            (d/'adapter_config.json').write_text(json.dumps({'base_model_name_or_path':p.MODEL}))
            s['weight_sha256']=p.sha(d/'adapter_model.safetensors')
        self.ps=mock.patch.object(p,'PARENT_SHA',p.sha(r/p.PARENT));self.pm=mock.patch.object(p,'MODELS',models)
        self.ps.start();self.pm.start();self.log=io.StringIO()
        with contextlib.redirect_stdout(self.log):p.build(r,Path(p.OUT),62026)
    def tearDown(self):
        self.ps.stop();self.pm.stop()
        for key in list(sys.modules):
            if key=='dcurr' or key.startswith('dcurr.'):sys.modules.pop(key)
        self.temp.cleanup()
    def accept(self):
        with contextlib.redirect_stdout(self.log):p.review(self.root,Path(p.OUT),'TEST','synthetic fixture review only')
    def execute(self):
        # Stand-in child evaluator: exercises invocation/files/summary contracts,
        # not Transformers, CUDA or the user's actual dcurr implementation.
        class FakeChild:
            def __init__(child, command, cwd, **kwargs):
                previous_cwd = Path.cwd(); previous_argv = sys.argv[:]
                try:
                    os.chdir(cwd); sys.argv = ['dcurr.evaluate'] + command[3:]
                    with contextlib.redirect_stdout(io.StringIO()):
                        exec(compile(EVALUATOR, 'CPU_FAKE_EVALUATOR', 'exec'), {'__name__':'__main__'})
                finally:
                    os.chdir(previous_cwd); sys.argv = previous_argv
                child.stdout = io.StringIO('FAKE CPU EVALUATOR; no model execution\n')
            def __enter__(child): return child
            def __exit__(child,*args): child.stdout.close()
            def wait(child): return 0
        with contextlib.redirect_stdout(self.log), mock.patch.object(p.subprocess,'Popen',FakeChild):
            p.evaluate(self.root,Path(p.OUT),None)
    def test_25_build_creates_no_approval_or_weights(self):
        d=self.root/p.OUT
        self.assertFalse((d/'review.json').exists());self.assertFalse((d/'comparison.json').exists())
        self.assertEqual(len(list(d.glob('cases_*.jsonl'))),4)
    def test_26_review_gate_blocks(self):
        with self.assertRaises(FileNotFoundError):p.plan(self.root,Path(p.OUT),True)
    def test_27_build_no_overwrite(self):
        with self.assertRaises(ValueError):p.build(self.root,Path(p.OUT),62026)
    def test_28_review_manifest_bound(self):
        self.accept();ap=p.readj(self.root/p.OUT/'review.json');self.assertEqual(ap['manifest_sha256'],p.sha(self.root/p.OUT/'manifest.json'))
    def test_29_code_change_detected(self):
        (self.root/'dcurr/prompts.py').write_text('change')
        with self.assertRaises(ValueError):p.plan(self.root,Path(p.OUT))
    def test_30_data_change_detected(self):
        with (self.root/p.OUT/'cases_clean.jsonl').open('a') as f:f.write('\n')
        with self.assertRaises(ValueError):p.plan(self.root,Path(p.OUT))
    def test_31_full_fake_pipeline(self):
        self.accept();self.execute()
        with contextlib.redirect_stdout(self.log):p.compare(self.root,Path(p.OUT))
        d=self.root/p.OUT;m=p.readj(d/'comparison.json');self.assertEqual(len(p.readl(d/'comparison_cases.jsonl')),24)
        for label in p.MODELS:
            self.assertEqual(m['models'][label]['both_states_all_views_strict_pairs'],6)
            self.assertEqual(m['models'][label]['all_views_strict_pass_cases'],12)
            self.assertEqual(m['models'][label]['order_changed_action_cases'],0)
    def test_32_existing_complete_outputs_skip(self):
        self.accept();self.execute();self.execute()
        self.assertIn('SKIP VERIFIED COMPLETE',self.log.getvalue())
    def test_33_extra_ref_old_pass_strict_fail(self):
        h=p.helper(self.root);common=h.runtime_common(self.root)
        c=p.readl(self.root/p.OUT/'cases_first.jsonl')[0];a=copy.deepcopy(c['expected']);a['evidence_refs'].append(c['authoring']['off_scope_record_ids'][0])
        s=h.score(common,c,{'parsed':a,'contract_pass':True},c['authoring']['off_scope_record_ids'])
        self.assertTrue(s['legacy_subset_contract_pass']);self.assertFalse(s['strict_selection_contract_pass'])
    def test_34_partial_result_rejected(self):
        self.accept();self.execute();f=self.root/p.OUT/'results/e1_clean.jsonl';ls=f.read_text().splitlines();f.write_text('\n'.join(ls[:-1])+'\n')
        with self.assertRaises(ValueError):p.checked_results(self.root,p.readj(self.root/p.OUT/'manifest.json'),'e1','clean',p.helper(self.root))
    def test_35_adapter_hash_mismatch_rejected(self):
        self.accept();self.execute();f=self.root/p.OUT/'results/e1_clean.summary.json';s=p.readj(f);s['adapter_sha256']='wrong';f.write_text(json.dumps(s))
        with self.assertRaises(ValueError):p.checked_results(self.root,p.readj(self.root/p.OUT/'manifest.json'),'e1','clean',p.helper(self.root))
    def test_36_review_does_not_modify_sources(self):
        a=p.sha(self.root/p.PARENT);self.accept();self.assertEqual(p.sha(self.root/p.PARENT),a)
    def test_37_no_automatic_training(self):
        self.accept();self.execute()
        inv=[p.readj(x)['command'] for x in (self.root/p.OUT/'results').glob('*.invocation.json')]
        self.assertEqual(len(inv),8)
        self.assertTrue(all(x[1:3]==['-m','dcurr.evaluate'] for x in inv))

if __name__=='__main__':unittest.main()
