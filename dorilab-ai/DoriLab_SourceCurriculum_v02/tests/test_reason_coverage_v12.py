import copy, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile, textwrap, unittest
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('v12_subject',HERE/'reason_coverage_v12.py')
x=importlib.util.module_from_spec(sp);sp.loader.exec_module(x)

class Prompts:
    @staticmethod
    def build_messages(role,packet,answer=None):
        ms=[{'role':'system','content':'PHYSICS_POLICY_'+role},{'role':'user','content':json.dumps({'role':role,'packet':packet},ensure_ascii=False)}]
        if answer is not None:ms.append({'role':'assistant','content':json.dumps(answer,ensure_ascii=False)})
        return ms

def parent_rows():
    rows=[]
    # Realism is limited to the exported JSONL interface; these are test fixtures.
    for i in range(150):
        rows.append({'id':f'OLD-C-{i}','messages':Prompts.build_messages('EVIDENCE',{'fixture':i},{'action':'NO_ACTION_REQUIRED'}),'v05_metadata':{'kind':'contract'}})
    codes=[('BOUNDARY_CONDITION_UNRESOLVED','CHALLENGE'),('BOUNDARY_CONDITION_UNRESOLVED','CHALLENGE'),('EVIDENCE_INTERPRETATION_ERROR','CHALLENGE'),('FORCE_LIMIT_BASIS_UNRESOLVED','REQUEST_EVIDENCE'),('MODE_SELECTION_MISMATCH','CHALLENGE'),('MONITORING_COVERAGE_INSUFFICIENT','CHALLENGE'),('MONITORING_COVERAGE_INSUFFICIENT','REQUEST_EVIDENCE'),('PARAMETER_IDENTIFICATION_INSUFFICIENT','CHALLENGE'),('POWER_DISSIPATION_UNRESOLVED','REQUEST_EVIDENCE'),('PROBABILISTIC_ASSUMPTIONS_UNRESOLVED','REQUEST_EVIDENCE')]
    for i in range(20):
        for j in range(3):
            a={'action':codes[i][1],'reason':codes[i][0]} if i<10 else {'action':'NO_ACTION_REQUIRED'}
            role='CRITIC' if a['action']=='CHALLENGE' else 'EVIDENCE'
            rows.append({'id':f'OLD-P-{i}-{j}','messages':Prompts.build_messages(role,{'fixture':i,'order':j},a),'v05_metadata':{'kind':'physics','parent_case_id':f'PHY-OLD-{i}'}})
    return rows

class UnitTests(unittest.TestCase):
    def setUp(self): self.cases=x.make_cases()
    def test_01_counts(self): self.assertEqual(len(self.cases),36)
    def test_02_nine_reason_codes(self): self.assertEqual(set(Counter(c['expected'].get('reason') for c in self.cases if 'reason' in c['expected']).values()),{2})
    def test_03_absent_codes_covered(self): self.assertTrue(x.ABSENT<={c['expected'].get('reason') for c in self.cases})
    def test_04_balanced_polarity(self):
        self.assertEqual(Counter(c['variant'] for c in self.cases if c['expected']['action']=='NO_ACTION_REQUIRED'),{'A':9,'B':9})
    def test_05_same_questions(self):
        for a,b in zip(self.cases[::2],self.cases[1::2]):self.assertEqual(a['packet']['review_question'],b['packet']['review_question'])
    def test_06_no_case_labels_in_packet(self):
        for c in self.cases:
            self.assertNotIn(c['case_id'],x.canon(c['packet']))
            self.assertNotIn('expected',c['packet'])
            for code in x.ABSENT:self.assertNotIn(code,x.canon(c['packet']))
    def test_07_ai_authorship(self):
        self.assertTrue(all(c['authoring']['human_review_performed'] is False for c in self.cases))
    def test_08_allowed_request_ids(self):
        for c in self.cases:self.assertTrue(set(c['expected'].get('requested_evidence',[]))<=set(c['packet']['allowed_request_ids']))
    def test_09_case_creation_deterministic(self):self.assertEqual(self.cases,x.make_cases())
    def test_10_duplicate_key_reject(self):
        with self.assertRaises(ValueError):x.strict('{"a":1,"a":2}')
    def test_11_nonfinite_reject(self):
        with self.assertRaises(ValueError):x.strict('{"a":NaN}')
    def test_12_path_escape_reject(self):
        with self.assertRaises(ValueError):x.local(Path('/tmp/a'),'../b')
    def test_13_duplicate_case_reject(self):
        c=copy.deepcopy(self.cases);c[0]['case_id']=c[1]['case_id']
        with self.assertRaises(ValueError):x.validate_cases(c)
    def test_14_changed_gold_ref_reject(self):
        c=copy.deepcopy(self.cases);c[0]['expected']['evidence_refs']=['bad']
        with self.assertRaises(ValueError):x.validate_cases(c)
    def test_15_arms_count_and_action(self):
        a=x.make_arms(parent_rows(),self.cases,Prompts)
        self.assertEqual([len(v) for v in a.values()],[246,246])
        self.assertEqual(x.exposure(a['repeat'])['action_rows'],x.exposure(a['coverage'])['action_rows'])
    def test_16_parent_not_modified(self):
        p=parent_rows();old=copy.deepcopy(p);x.make_arms(p,self.cases,Prompts);self.assertEqual(p,old)
    def test_17_parent_same_slots(self):
        a=x.make_arms(parent_rows(),self.cases,Prompts)
        kept=0
        for r,c in zip(a['repeat'],a['coverage']):
            if r['id'].startswith('OLD-'):self.assertEqual(r,c);kept+=1
        self.assertEqual(kept,210)
    def test_18_control_not_exposed(self):
        a=x.make_arms(parent_rows(),self.cases,Prompts)
        for code in x.ABSENT:
            self.assertEqual(x.exposure(a['repeat'])['supervised_reason_rows'].get(code,0),0)
            self.assertEqual(x.exposure(a['coverage'])['supervised_reason_rows'][code],2)
    def test_19_prompt_change_reject(self):
        class Bad(Prompts):
            @staticmethod
            def build_messages(role,packet,answer=None):
                ms=Prompts.build_messages(role,packet,answer);ms[0]['content']='CHANGED';return ms
        with self.assertRaises(ValueError):x.make_arms(parent_rows(),self.cases,Bad)
    def test_20_preflight_report(self):
        r=x.preflight_pass('note\n{"status":"PASS","records":246,"silent_truncation":false}',246)
        self.assertEqual(r['records'],246)
    def test_21_preflight_truncation_reject(self):
        with self.assertRaises(ValueError):x.preflight_pass('{"status":"PASS","records":246,"silent_truncation":true}',246)
    def test_22_actual_gate(self):
        path=Path('/mnt/data/scope_gate_v07.py')
        if not path.exists(): self.skipTest('Available real v07 helper not on this host')
        s=importlib.util.spec_from_file_location('gate_v07_test',path);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
        for c in self.cases:
            e={'role':c['role'],'packet':c['packet']};out,_=g.gate_input(e);self.assertEqual(out,e)
    def test_23_exact_v10_no_overlap(self):
        path=Path('/mnt/data/new_source_reason_v10.py')
        if not path.exists():self.skipTest('v10 helper absent')
        s=importlib.util.spec_from_file_location('v10_test',path);h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
        old={x.digest(c['packet']) for c in h.PAYLOAD['cases']}
        self.assertFalse(old & {x.digest(c['packet']) for c in self.cases})

    def test_29_regression_alternative_preserved(self):
        class H:
            @staticmethod
            def score(common,c,row):
                return {'reference_exact':row==c['expected'], 'strict_contract_pass':row==c['expected']}
        c={'expected':{'reason':'A'},'acceptable_answers':[{'reason':'A'},{'reason':'B'}]}
        old=copy.deepcopy(c)
        sc=x.regression_score(H,None,c,{'reason':'B'})
        self.assertTrue(sc['strict_contract_pass']);self.assertEqual(c,old)
    def test_30_regression_unaccepted_stays_false(self):
        class H:
            @staticmethod
            def score(common,c,row):
                return {'reference_exact':row==c['expected'], 'strict_contract_pass':row==c['expected']}
        c={'expected':{'reason':'A'},'acceptable_answers':[{'reason':'A'}]}
        self.assertFalse(x.regression_score(H,None,c,{'reason':'B'})['strict_contract_pass'])


COMMON='''
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def validate_answer(a,c):
    assert isinstance(a,dict)
    p=c['packet']
    if a.get('claim_id')!=p['claim_id']:raise ValueError('bad claim')
    allowed={r['reference_id'] for r in p['reference_context']}|{r['evidence_id'] for r in p['case_packet']['evidence']}
    refs=a.get('evidence_refs')
    if not isinstance(refs,list) or not all(isinstance(s,str) for s in refs) or not set(refs)<=allowed:raise ValueError('unprovided evidence reference')
    if a.get('action')=='REQUEST_EVIDENCE' and not a.get('requested_evidence'):raise ValueError('missing request')
    if not set(a.get('requested_evidence',[]))<=set(p['allowed_request_ids']):raise ValueError('bad request')

def answer_matches(e,a):
    if not isinstance(a,dict):return False
    for k,v in e.items():
        if isinstance(v,list):
            if set(a.get(k,[]))!=set(v):return False
        elif a.get(k)!=v:return False
    return True
'''
PROMPTS='''
import json
POLICY_VERSION='mock-only'
def build_messages(role,packet,answer=None):
    ms=[{'role':'system','content':'PHYSICS_POLICY_'+role},{'role':'user','content':json.dumps({'role':role,'packet':packet},ensure_ascii=False)}]
    if answer is not None:ms.append({'role':'assistant','content':json.dumps(answer,ensure_ascii=False)})
    return ms
'''
TRAIN='''
import argparse,json,hashlib
from pathlib import Path
from .common import ROOT
p=argparse.ArgumentParser()
for k in ('data','out','model','revision','epochs','lr','rank','max-length'):p.add_argument('--'+k)
a=p.parse_args();data=Path(a.data);mf=data.with_suffix('.manifest.json')
if not mf.exists():raise SystemExit('Run dcurr.prepare first; data manifest missing')
m=json.loads(mf.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if m['data_sha256']!=sha(data):raise SystemExit('Training data hash changed')
if m['prompt_file_sha256']!=sha(ROOT/'dcurr/prompts.py') or m['legacy_prompt_sha256']!=sha(ROOT/'dcurr/prompts_legacy.py'):raise SystemExit('Prompt changed')
out=Path(a.out)
if out.exists():raise SystemExit('Output exists')
out.mkdir(parents=True)
(out/'adapter_model.safetensors').write_bytes(b'CPU-MOCK-NOT-A-MODEL-'+a.data.encode())
(out/'adapter_config.json').write_text(json.dumps({'r':int(a.rank)}))
(out/'RUN_MANIFEST.json').write_text(json.dumps({'data_manifest':m,'rank':int(a.rank),'lr':float(a.lr),'epochs_requested':float(a.epochs)}))
(out/'TRAIN_RESULT.json').write_text(json.dumps({'test_only':True}))
print('MOCK TRAINER ENTRY PASSED')
'''
EVAL='''
import argparse,json,hashlib
from pathlib import Path
from .prompts import build_messages
p=argparse.ArgumentParser()
for k in ('cases','adapter','out','model','revision','max-new-tokens','purpose'):p.add_argument('--'+k)
a=p.parse_args();rs=[json.loads(l) for l in Path(a.cases).read_text().splitlines()]
rows=[]
for c in rs:
    build_messages(c['role'],c['packet'])
    # CPU fixture returns gold solely to exercise I/O contracts. NOT inference.
    o=c['expected'];rows.append({'case_id':c['case_id'],'raw_output':json.dumps(o),'parsed':o,'contract_pass':True,'prompt_tokens':10,'generated_tokens':10,'generation_seconds':0,'hit_generation_limit':False})
p=Path(a.out);p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(''.join(json.dumps(r)+'\\n' for r in rows))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p.with_suffix('.summary.json').write_text(json.dumps({'records':len(rs),'model':a.model,'case_file_sha256':sha(Path(a.cases)),'adapter_sha256':sha(Path(a.adapter)/'adapter_model.safetensors')}))
'''
PREFLIGHT='''
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('data','max-length','model','revision'):p.add_argument('--'+k)
a=p.parse_args();r=[l for l in Path(a.data).read_text().splitlines() if l.strip()]
print(json.dumps({'status':'PASS','records':len(r),'silent_truncation':False,'total_prompt_tokens':2460,'total_answer_tokens':1230,'test_only':True}))
'''
CONTRACT='''
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('split','adapter','label'):p.add_argument('--'+k)
a=p.parse_args();d=Path('eval/results');d.mkdir(parents=True,exist_ok=True)
(d/(a.label+'_dev.jsonl')).write_text(''.join(json.dumps({'id':'MOCK-'+str(i),'pass':True,'action_ok':True})+'\\n' for i in range(20)))
'''

class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'project';self.root.mkdir()
        self.oldsha=x.PARENT_SHA
        # Clear only temporary dcurr modules between independent fixture roots.
        for name in list(sys.modules):
            if name=='dcurr' or name.startswith('dcurr.'):del sys.modules[name]
        self.f('dcurr/__init__.py','');self.f('dcurr/common.py',COMMON);self.f('dcurr/prompts.py',PROMPTS);self.f('dcurr/prompts_legacy.py','# mock\n')
        self.f('dcurr/train.py',TRAIN);self.f('dcurr/evaluate.py',EVAL);self.f('dcurr/preflight.py',PREFLIGHT)
        self.f('transformers.py','def set_seed(seed): pass\n')
        self.f('data/action_schema_v02.json','{}')
        self.f('data/review_decisions.csv','mock');self.f('data/source_review.csv','mock')
        ep=self.root.parent/'eval';ep.mkdir();(ep/'__init__.py').write_text('');(ep/'run_eval40_qwen35.py').write_text(CONTRACT)
        shutil.copy(HERE/'reason_coverage_v12.py',self.root/'reason_coverage_v12.py')
        path=Path('/mnt/data/new_source_reason_v10.py')
        if not path.exists():self.skipTest('Full old v10 helper required for fixture integration')
        shutil.copy(path,self.root/'new_source_reason_v10.py')
        parent=self.root/x.PARENT;parent.parent.mkdir(parents=True);x.writel(parent,parent_rows());x.PARENT_SHA=x.sha(parent)
        dm={'data_sha256':x.PARENT_SHA,'source_ids':['TH-01','VB-X1','EE-02','EE-03'],'prompt_file_sha256':x.sha(self.root/'dcurr/prompts.py'),'legacy_prompt_sha256':x.sha(self.root/'dcurr/prompts_legacy.py')}
        x.writej(parent.with_suffix('.manifest.json'),dm)
        self.j(x.E2RUN,{'data_manifest':dm,'rank':16,'lr':5e-5,'epochs_requested':2})
        self.f('runs/evidence_training_v05_position_e2/adapter_model.safetensors','OLD-CPU-MOCK')
        self.j(x.AUDIT,{'input_sha256':{x.PARENT:x.PARENT_SHA,x.E2RUN:x.sha(self.root/x.E2RUN)},'reason_codes':{c:{'supervised_rows':0} for c in x.ABSENT}})
        h=x.helper(self.root);cs=copy.deepcopy(h.PAYLOAD['cases'])
        for c in cs:c['packet']['case_packet']['evidence']=[e for e in c['packet']['case_packet']['evidence'] if e['evidence_id'] in c['expected']['evidence_refs']]
        vd=self.root/x.V10;vd.mkdir(parents=True);(vd/'results').mkdir()
        x.writel(vd/'evaluation_cases24.jsonl',cs)
        inp=[];results=[]
        for c in cs:
            ms=Prompts.build_messages(c['role'],c['packet'])
            inp.append({'case_id':c['case_id'],'role_packet_sha256':h.objsha(h.envelope(c)),'messages':ms,'messages_sha256':h.objsha(ms)})
            results.append({'case_id':c['case_id'],'raw_output':json.dumps(c['expected']),'contract_pass':True})
        x.writel(vd/'inputs_baseline24.jsonl',inp);x.writel(vd/'results/baseline.jsonl',results);x.writej(vd/'comparison.json',{})
        x.writej(vd/'manifest.json',{'version':h.VERSION,'script_sha256':x.sha(self.root/'new_source_reason_v10.py'),'payload_sha256':h.objsha(h.PAYLOAD),'frozen_files':{},'generated_files':{},'adapter':'runs/evidence_training_v05_position_e2','adapter_sha256':x.sha(self.root/'runs/evidence_training_v05_position_e2/adapter_model.safetensors'),'model':x.MODEL,'revision':x.REVISION})
        self.j('data/evidence_training_v05/manifest.json',{'eval_files':{'before':'data/mock_before.jsonl'}})
        x.writel(self.root/'data/mock_before.jsonl',cs)
    def f(self,p,s):
        p=self.root/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    def j(self,p,o):self.f(p,json.dumps(o))
    def tearDown(self):
        x.PARENT_SHA=self.oldsha
        for name in list(sys.modules):
            if name=='dcurr' or name.startswith('dcurr.'):del sys.modules[name]
        self.tmp.cleanup()
    def test_24_prepare_requires_explicit_ai_use(self):
        with self.assertRaises(ValueError):x.prepare(self.root,x.OUTDIR,False)
    def test_25_train_without_manifest_fails(self):
        # Reproduces exactly the earlier dcurr manifest failure.
        p=self.root/x.PARENT;p.with_suffix('.manifest.json').unlink()
        r=subprocess.run([sys.executable,'-m','dcurr.train','--data',str(p),'--out','runs/fail'],cwd=self.root,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('data manifest missing',r.stderr)
    def test_26_prepare_makes_both_sidecars(self):
        # Point source hash identity at copied script, as real execution does.
        old=x.__file__;x.__file__=str(self.root/'reason_coverage_v12.py')
        try:x.prepare(self.root,x.OUTDIR,True)
        finally:x.__file__=old
        for arm in x.ARMS:
            p=self.root/x.OUTDIR/(arm+'246.jsonl');m=x.readj(p.with_suffix('.manifest.json'));self.assertEqual(m['data_sha256'],x.sha(p))
    def test_27_tamper_detected(self):
        old=x.__file__;x.__file__=str(self.root/'reason_coverage_v12.py')
        try:
            x.prepare(self.root,x.OUTDIR,True)
            p=self.root/x.OUTDIR/'coverage246.jsonl';p.write_text(p.read_text()+'\n')
            with self.assertRaises(ValueError):x.plan(self.root,x.OUTDIR)
        finally:x.__file__=old
    def test_28_end_to_end_mock_interfaces(self):
        old=x.__file__;x.__file__=str(self.root/'reason_coverage_v12.py')
        try:
            x.prepare(self.root,x.OUTDIR,True)
            x.train(self.root,x.OUTDIR)
            x.evaluate(self.root,x.OUTDIR)
            x.compare(self.root,x.OUTDIR)
            result=x.readj(self.root/x.OUTDIR/'comparison.json')
            self.assertEqual(result['arms']['coverage']['ns10']['cases'],24)
            self.assertEqual(result['arms']['repeat']['contract20']['cases'],20)
            self.assertEqual(len(x.readl(self.root/x.OUTDIR/'comparison_cases.jsonl')),24)
            self.assertFalse((self.root/'runs/evidence_training_v05_position_e2/TRAIN_RESULT.json').exists())
        finally:x.__file__=old

if __name__=='__main__':unittest.main()
