import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
if not (BASE/'scoped_review_v08.py').is_file():
    BASE = HERE.parent
sys.path.insert(0,str(BASE))
import scoped_review_v08 as s
GATE_PATH = HERE/'fixtures/helpers/scope_gate_v07.py'
HELPER_PATH = HERE/'fixtures/helpers/evidence_probe_v04.py'
gate = s.load_module(GATE_PATH,'test_real_gate_v07')

COMMON = '''from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent

def validate_answer(a,c):
    if not isinstance(a,dict): raise ValueError('not object')
    if a.get('action') not in ['NO_ACTION_REQUIRED','CHALLENGE','REQUEST_EVIDENCE']: raise ValueError('bad action')
    if a.get('claim_id')!=c['packet']['claim_id']: raise ValueError('claim mismatch')
    refs=a.get('evidence_refs')
    if not isinstance(refs,list) or not all(isinstance(x,str) for x in refs): raise ValueError('bad refs')
    allowed={r['reference_id'] for r in c['packet']['reference_context']}|{r['evidence_id'] for r in c['packet']['case_packet']['evidence']}
    if not set(refs)<=allowed: raise ValueError('unprovided evidence reference')
    req=a.get('requested_evidence',[])
    if not isinstance(req,list) or not all(isinstance(x,str) for x in req):raise ValueError('bad requests')
    if not set(req)<=set(c['packet']['allowed_request_ids']):raise ValueError('bad request id')

def answer_matches(e,a):
    if not isinstance(a,dict):return False
    for k,v in e.items():
        if k=='evidence_refs':
            if not isinstance(a.get(k),list) or not all(x in a[k] for x in v):return False
        elif a.get(k)!=v:return False
    return True
'''

EVALUATOR = '''# CPU MOCK ONLY: never a real model measurement.
import argparse,json,hashlib
from pathlib import Path
from .common import validate_answer,answer_matches
p=argparse.ArgumentParser()
for k in ['cases','adapter','out','model','revision','max-new-tokens','purpose']:p.add_argument('--'+k)
a=p.parse_args()
rows=[json.loads(x) for x in Path(a.cases).read_text().splitlines() if x.strip()]
result=[]
for c in rows:
    pkt=c['packet']
    obj={'action':'NO_ACTION_REQUIRED','claim_id':pkt['claim_id'], 'evidence_refs':[pkt['reference_context'][0]['reference_id'],pkt['case_packet']['evidence'][0]['evidence_id']]}
    validate_answer(obj,{'role':c['role'],'packet':pkt})
    result.append({'case_id':c['case_id'],'parsed':obj,'raw_output':json.dumps(obj),'strict_json_valid':True,'schema_and_refs_valid':True,'action_ok':obj['action']==c['expected']['action'],'contract_pass':answer_matches(c['expected'],obj),'hit_generation_limit':False})
with Path(a.out).open('x') as f:
    for r in result:f.write(json.dumps(r)+'\\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary={'records':len(rows),'model':a.model,'adapter_sha256':sha(Path(a.adapter)/'adapter_model.safetensors'),'case_file_sha256':sha(a.cases),'prompt_sha256':sha('dcurr/prompts.py'),'purpose':a.purpose,'strict_json_valid':len(rows),'schema_and_refs_valid':len(rows),'action_correct':sum(r['action_ok'] for r in result),'contract_pass':sum(r['contract_pass'] for r in result)}
Path(a.out).with_suffix('.summary.json').write_text(json.dumps(summary))
'''

def packet(i=0):
    return {'role':'CRITIC','packet':{'review_question':f'Review scope: unit=U-{i}; configuration=C-1; run=R-1. '+gate.POLICY+' Is the proposal supported?',
        'claim_id':f'C{i}', 'reference_context':[{'reference_id':f'SF-{i}','source_id':'S','text':'Synthetic test principle.'}],
        'case_packet':{'evidence':[{'evidence_id':f'O-{i}-OTHER','text':f'Record scope: unit=OTHER; configuration=C-1; run=R-1. Off-scope synthetic record.'},
                                  {'evidence_id':f'O-{i}-OLD','text':f'Record scope: unit=U-{i}; configuration=C-OLD; run=R-OLD. Old synthetic record.'},
                                  {'evidence_id':f'O-{i}','text':f'Record scope: unit=U-{i}; configuration=C-1; run=R-1. Current synthetic record.'}],
                       'proposal':'Synthetic test proposal.'}, 'allowed_request_ids':[]}}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        for name in list(sys.modules):
            if name=='dcurr' or name.startswith('dcurr.'):
                del sys.modules[name]
        self.oldsha=s.E2_SHA
        self.out='data/scoped_review_v08'
        self.fixture()
        self.common=s.helpers(self.root)[2]
        self.env=gate.gate_input(packet())[0]
        self.answer={'action':'NO_ACTION_REQUIRED','claim_id':'C0','evidence_refs':['SF-0','O-0']}
    def tearDown(self):
        s.E2_SHA=self.oldsha
        for name in list(sys.modules):
            if name=='dcurr' or name.startswith('dcurr.'):
                del sys.modules[name]
        sys.path[:]=[p for p in sys.path if p!=str(self.root)]
        self.tmp.cleanup()
    def fixture(self):
        r=self.root
        shutil.copy2(GATE_PATH,r/'scope_gate_v07.py')
        shutil.copy2(HELPER_PATH,r/'evidence_probe_v04.py')
        d=r/'dcurr'; d.mkdir(); (d/'__init__.py').write_text('')
        (d/'common.py').write_text(COMMON); (d/'evaluate.py').write_text(EVALUATOR);(d/'prompts.py').write_text('# MOCK ONLY\n')
        ad=r/'runs/e2';ad.mkdir(parents=True);(ad/'adapter_model.safetensors').write_bytes(b'CPU MOCK WEIGHTS')
        s.E2_SHA=s.sha(ad/'adapter_model.safetensors')
        raw=[];clean=[]
        for i in range(12):
            c={'case_id':f'T-{i}','pair_id':f'P-{i//2}','domain':'THERMAL','source_id':'S',**packet(i)}
            c['expected']={'action':'NO_ACTION_REQUIRED','claim_id':f'C{i}','evidence_refs':[f'SF-{i}',f'O-{i}']}
            c['acceptable_answers']=[copy.deepcopy(c['expected'])]
            raw.append(c); cc=copy.deepcopy(c);cc.update(gate.gate_input(s.envelope(c))[0]);clean.append(cc)
        app=r/s.APP;app.mkdir(parents=True)
        s.writel(app/'cases_last.jsonl',raw);s.writel(app/'cases_clean.jsonl',clean)
        (app/'results').mkdir();res=[]
        for c in clean:
            ob=c['expected']
            res.append({'case_id':c['case_id'],'parsed':ob,'raw_output':json.dumps(ob)})
        s.writel(app/'results/e2_clean.jsonl',res)
        s.writej(app/'results/e2_clean.summary.json',{'adapter_sha256':s.E2_SHA,'records':12,'case_file_sha256':s.sha(app/'cases_clean.jsonl')})
        rawpaths={f'dcurr/{p.name}':s.sha(p) for p in d.iterdir() if p.is_file()}
        m={'version':'applicability-probe-v0.6.0','frozen_files':rawpaths,
           'generated_files':{str((app/f'cases_{v}.jsonl').relative_to(r)):s.sha(app/f'cases_{v}.jsonl') for v in ('clean','last')},
           'models':{'e2':{'adapter':'runs/e2','weight_sha256':s.E2_SHA,'outputs':{'clean':str((app/'results/e2_clean.jsonl').relative_to(r))}}},
           'model':'CPU-MOCK','base_revision':'MOCK-REV','generation_budget':384,
           'case_files':{v:str((app/f'cases_{v}.jsonl').relative_to(r)) for v in ('clean','last')}}
        s.writej(app/'manifest.json',m)
        s.writej(app/'review.json',{'decision':'ACCEPTED_FOR_DIAGNOSTIC','reviewer':'mock test','manifest_sha256':s.sha(app/'manifest.json')})
        s.writej(app/'comparison.json',{'models':{'e2':{'views':{'clean':{'cases':12,'action_correct':12,'strict_selection_contract_pass':12}}}},
                                      'result_sha256':{'e2/clean':s.sha(app/'results/e2_clean.jsonl')}})
        ar=r/s.AUDIT;ar.mkdir(parents=True)
        s.writel(ar/'inputs_last.jsonl',[{'case_id':c['case_id'],**s.envelope(c)} for c in clean])
        audit={'version':'scope-gate-v0.7.0','status':'PASS','gold_used_for_selection':False,'script_sha256':s.sha(r/'scope_gate_v07.py'),
               'input_sha256':{str(p.relative_to(r)):s.sha(p) for p in [app/'manifest.json',app/'review.json',app/'comparison.json',app/'cases_clean.jsonl',app/'cases_last.jsonl']}}
        s.writej(ar/'audit.json',audit)
    def prep(self):
        with contextlib.redirect_stdout(io.StringIO()):s.prepare(self.root,self.out)
        return self.root/self.out
    def output(self,obj,limit=False):return s.check_output(self.common,self.env,json.dumps(obj),limit)
    def test01_valid_not_engineering_approval(self):
        v=self.output(self.answer); self.assertEqual(v['status'],'OUTPUT_VALIDATED');self.assertFalse(v['engineering_approved']);self.assertTrue(v['human_review_required'])
    def test02_duplicate_json_rejected(self):
        v=s.check_output(self.common,self.env,'{"action":"X","action":"Y"}');self.assertEqual(v['status'],'OUTPUT_REJECTED')
    def test03_nonfinite_rejected(self):
        for x in ['NaN','Infinity','-Infinity']:
            with self.assertRaises(ValueError):s.strict_loads('{"x":'+x+'}')
    def test04_trailing_text_rejected(self):
        self.assertEqual(s.check_output(self.common,self.env,json.dumps(self.answer)+' extra')['status'],'OUTPUT_REJECTED')
    def test05_code_fence_rejected(self):
        self.assertEqual(s.check_output(self.common,self.env,'```json\n'+json.dumps(self.answer)+'\n```')['status'],'OUTPUT_REJECTED')
    def test06_unprovided_reference_rejected(self):
        o=copy.deepcopy(self.answer);o['evidence_refs'].append('S');self.assertEqual(self.output(o)['status'],'OUTPUT_REJECTED')
    def test07_excluded_reference_rejected(self):
        o=copy.deepcopy(self.answer);o['evidence_refs'].append('O-0-OLD');self.assertEqual(self.output(o)['status'],'OUTPUT_REJECTED')
    def test08_duplicate_reference_rejected(self):
        o=copy.deepcopy(self.answer);o['evidence_refs'].append('O-0');self.assertEqual(self.output(o)['status'],'OUTPUT_REJECTED')
    def test09_generation_limit_rejected(self):
        self.assertEqual(self.output(self.answer,True)['status'],'OUTPUT_REJECTED')
    def test10_validator_rejects_gold_envelope(self):
        x=copy.deepcopy(self.env);x['expected']=self.answer
        with self.assertRaises(ValueError):s.check_output(self.common,x,'{}')
    def test11_raw_unchanged(self):
        text=json.dumps(self.answer,indent=2);v=s.check_output(self.common,self.env,text);self.assertEqual(v['raw_output'],text)
    def test12_wrong_but_valid_action_not_claimed_correct(self):
        o=copy.deepcopy(self.answer);o['action']='CHALLENGE';v=self.output(o);self.assertEqual(v['status'],'OUTPUT_VALIDATED');self.assertFalse(v['engineering_approved'])
    def test13_gate_guards(self):
        rs=s.guard_checks(gate,packet());self.assertEqual(len(rs),8);self.assertTrue(all(x['pass'] for x in rs))
    def test14_path_escape_rejected(self):
        for x in ['../bad','/tmp/bad']:
            with self.assertRaises(ValueError):s.local(self.root,x)
    def test15_duplicate_case_rejected(self):
        with self.assertRaises(ValueError):s.index([{'case_id':'x'},{'case_id':'x'}])
    def test16_prepare_keeps_labels_separate(self):
        p=self.prep();r=s.readl(p/'inputs12.jsonl');self.assertEqual(len(r),12);self.assertTrue(all(set(x)=={'case_id','role','packet'} for x in r))
        self.assertEqual(sum(len(n['excluded_from_model_context']) for n in s.readl(p/'gate_events.jsonl')),24)
    def test17_old_files_unchanged(self):
        old={p:s.sha(p) for p in self.root.rglob('*') if p.is_file()};self.prep();self.assertTrue(all(s.sha(p)==h for p,h in old.items()))
    def test18_prepare_no_overwrite(self):
        self.prep()
        with self.assertRaises(ValueError):s.prepare(self.root,self.out)
    def test19_source_edit_detected(self):
        p=self.root/s.APP/'cases_last.jsonl';p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):self.prep()
    def test20_prepared_edit_detected(self):
        p=self.prep();q=p/'inputs12.jsonl';q.write_text(q.read_text()+'\n')
        with self.assertRaises(ValueError):s.plan(self.root,self.out)
    def test21_wrong_weights_blocked(self):
        (self.root/'runs/e2/adapter_model.safetensors').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prep()
    def test22_guard_gold_not_used(self):
        c=packet();before=copy.deepcopy(c);gate.gate_input(c);self.assertEqual(c,before)
    def test23_incomplete_run_cannot_summarize(self):
        self.prep()
        with self.assertRaises(ValueError):s.summarize(self.root,self.out)
    def test24_full_mock_run(self):
        p=self.prep()
        with contextlib.redirect_stdout(io.StringIO()):s.run(self.root,self.out)
        result=s.readj(p/'comparison.json');self.assertEqual(result['counts']['cases'],12)
        self.assertEqual(result['counts']['strict_contract_pass'],12)
        self.assertEqual(result['counts']['cites_excluded_records'],0)
        rows=s.readl(p/'review_records.jsonl');self.assertTrue(all('expected' not in x and not x['engineering_approved'] for x in rows))
    def test25_completed_mock_run_not_reexecuted(self):
        p=self.prep()
        with contextlib.redirect_stdout(io.StringIO()):s.run(self.root,self.out)
        before=s.sha(p/'run_completed.json')
        with contextlib.redirect_stdout(io.StringIO()):s.run(self.root,self.out)
        self.assertEqual(s.sha(p/'run_completed.json'),before)
    def test26_incomplete_files_not_overwritten(self):
        p=self.prep();(p/'model_outputs.jsonl').write_text('')
        with self.assertRaises(ValueError):s.run(self.root,self.out)
        self.assertEqual((p/'model_outputs.jsonl').read_text(),'')
    def test27_prior_output_edit_detected(self):
        p=self.root/s.APP/'results/e2_clean.jsonl';p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):self.prep()
    def test28_completed_result_edit_detected(self):
        p=self.prep()
        with contextlib.redirect_stdout(io.StringIO()):s.run(self.root,self.out)
        q=p/'model_outputs.jsonl';q.write_text(q.read_text()+'\n')
        with self.assertRaises(ValueError):s.summarize(self.root,self.out)

if __name__=='__main__':unittest.main()
