import copy,csv,importlib.util,io,json,random,shutil,sys,tempfile,unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import evidence_training_v05 as v

PAIRS=sorted(v.PAIRS)+['TH01-P01','TH01-P04','TH01-P06','TH01-P07','TH01-P08','VBX1-P04','VBX1-P05','VBX1-P06','VBX1-P08','EE03-P02']
def fixtures():
    cases=[]
    for i,p in enumerate(PAIRS):
        source='TH-01' if p.startswith('TH') else ('VB-X1' if p.startswith('VB') else ('EE-02' if p.startswith('EE02') else 'EE-03'))
        for variant in ['A','B']:
            fact={'reference_id':'SF-'+p,'source_id':source,'text':'Fixture principle for '+p+'.'}
            action='CHALLENGE' if variant=='A' else 'NO_ACTION_REQUIRED'
            packet={'review_question':'Check '+p,'claim_id':'C'+str(i),'reference_context':[fact],
               'case_packet':{'evidence':[{'evidence_id':'OBS-1','text':'Synthetic unit observation for '+p}],
                              'proposal':'Test fixture proposal '+variant},'allowed_request_ids':[]}
            ans={'action':action,'claim_id':packet['claim_id'],'evidence_refs':[fact['reference_id'],'OBS-1']}
            if variant=='A':ans['reason']='TEST_REASON'
            c={'case_id':'PHY-'+p+'-'+variant,'pair_id':p,'source_id':source,'source_program_groups':['GROUP-'+source],
               'role':'CRITIC','packet':packet,'expected':ans,'rationale_ko':'UNIT TEST ONLY','human_review_status':'PENDING'}
            cases.append(c)
    contract=[{'id':'LEGACY'+str(i),'messages':[{'role':'system','content':'Fixture common prompt'}, {'role':'user','content':'fixture '+str(i)},{'role':'assistant','content':'{"action":"NO_ACTION_REQUIRED"}'}]} for i in range(150)]
    physics=[]
    for c in cases:
        if c['pair_id'] not in v.PAIRS:continue
        physics.append({'id':c['case_id'],'messages':[{'role':'system','content':'Frozen fixture physics prompt'},
            {'role':'user','content':json.dumps({'role':c['role'],'packet':c['packet']},ensure_ascii=False,indent=2)},
            {'role':'assistant','content':json.dumps(c['expected'],ensure_ascii=False,separators=(',',':'))}]})
    mixed=copy.deepcopy(contract+physics);random.Random(12).shuffle(mixed)
    return cases,contract,mixed

COMMON='''from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def validate_answer(a,c):
    if not isinstance(a,dict):raise ValueError('not dict')
    if a.get('action') not in ['CHALLENGE','NO_ACTION_REQUIRED','REQUEST_EVIDENCE']:raise ValueError('action')
    if a.get('claim_id')!=c['packet']['claim_id']:raise ValueError('claim')
    refs=a.get('evidence_refs')
    if not isinstance(refs,list) or not refs or any(not isinstance(x,str) for x in refs):raise ValueError('refs')
    ids={x['reference_id'] for x in c['packet']['reference_context']}|{x['evidence_id'] for x in c['packet']['case_packet']['evidence']}
    if len(refs)!=len(set(refs)) or not set(refs)<=ids:raise ValueError('refs')
def answer_matches(a,b):
    if not isinstance(b,dict):return False
    return all((set(x)<=set(b.get(k,[]))) if k=='evidence_refs' else x==b.get(k) for k,x in a.items())
'''

def make_project(tmp):
    root=Path(tmp)/'project'/'DoriLab_SourceCurriculum_v02';root.mkdir(parents=True)
    (root/'dcurr').mkdir();(root/'dcurr/__init__.py').write_text('')
    (root/'dcurr/common.py').write_text(COMMON)
    for name in ['train','preflight','prompts','prompts_legacy','model_io','prepare','review','evaluate']:(root/f'dcurr/{name}.py').write_text('# CPU fixture only\n')
    (root.parent/'eval').mkdir();(root.parent/'eval/run_eval40_qwen35.py').write_text('# CPU fixture only\n')
    (root.parent/'data').mkdir();(root/'data').mkdir()
    shutil.copy(ROOT/'evidence_probe_v04.py',root/'evidence_probe_v04.py')
    cases,contract,mixed=fixtures()
    v.write_bytes(root/v.CASES,v.jsonl_bytes(cases));v.write_bytes(root/v.TRAIN,v.jsonl_bytes(mixed))
    v.write_bytes(root.parent/'data/train150_v01.jsonl',v.jsonl_bytes(contract))
    for name,key,rows in [('review_decisions.csv','case_id',[{'case_id':c['case_id'],'decision':'APPROVED' if c['pair_id'] in v.PAIRS else 'PENDING'} for c in cases]),
                         ('source_review.csv','source_id',[{'source_id':s,'permission_review':'REVIEWED_OK'} for s in ['TH-01','VB-X1','EE-02','EE-03']])]:
        with (root/'data'/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for n in list(sys.modules):
        if n=='dcurr' or n.startswith('dcurr.'):del sys.modules[n]
    h=v.load_helper(root)
    # ID probe control uses different handles from original approved train.
    ctrl=[]
    for i,c in enumerate(cases):
        mapping={x:('SF-' if p=='SF-' else 'OBS-')+str(1000+i*3+k) for k,(x,p) in enumerate(v.definitions(c).items())}
        new=copy.deepcopy(c);new['packet']=v.swap(new['packet'],mapping);new['expected']=v.swap(new['expected'],mapping);ctrl.append(new)
    views,distractors=h.make_views(ctrl,17);viewcases={'control':ctrl,**views}
    files={};specs={};report={'version':h.VERSION,'generation_result_hashes':{},'models':{}}
    for view,cs in viewcases.items():
        files[view]='data/prior_'+view+'.jsonl';v.write_bytes(root/files[view],v.jsonl_bytes(cs))
    for label in ['lr5e5','lr2e5']:
        adapter='runs/prior_'+label;(root/adapter).mkdir(parents=True)
        v.write_bytes(root/adapter/'adapter_model.safetensors',b'FAKE PRIOR WEIGHTS')
        v.write_json(root/adapter/'adapter_config.json',{'r':16})
        spec={'adapter':adapter,'weight_sha256':v.sha(root/adapter/'adapter_model.safetensors'),'result_files':{}}
        for view,cs in viewcases.items():
            fname='reports/prior_'+label+'_'+view+'.jsonl';spec['result_files'][view]=fname
            rs=[{'case_id':c['case_id'],'parsed':c['expected'],'contract_pass':True,'raw_output':json.dumps(c['expected'])} for c in cs]
            v.write_bytes(root/fname,v.jsonl_bytes(rs));report['generation_result_hashes'][label+'/'+view]=v.sha(root/fname)
        specs[label]=spec
    prior={'version':h.VERSION,'script_sha256':v.sha(root/'evidence_probe_v04.py'),'frozen_files':{},
           'files':files,'file_sha256':{view:v.sha(root/f) for view,f in files.items()},'model_specs':specs,'distractor_ids_by_case':distractors}
    v.write_json(root/v.PRIOR,prior);v.write_json(root/Path(v.PRIOR).parent/'comparison.json',report)
    return root

class UnitTests(unittest.TestCase):
    def setUp(self):self.cases,self.contract,self.mixed=fixtures();self.selected=v.recover_selected(self.mixed,self.contract,self.cases)
    def test_01_match_twenty(self):self.assertEqual(len(self.selected),20)
    def test_02_ten_pairs(self):self.assertEqual({x['case']['pair_id'] for x in self.selected.values()},v.PAIRS)
    def test_03_originals_immutable(self):
        before=copy.deepcopy(self.selected);v.data_variants(self.selected,self.contract,15,{x for c in self.cases for x in v.definitions(c)});self.assertEqual(before,self.selected)
    def test_04_exact_210(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set());self.assertEqual({len(r) for r in rows.values()},{210})
    def test_05_target_text_equal(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set())
        self.assertTrue(all(a['messages'][-1]==b['messages'][-1] for a,b in zip(rows['repeat'],rows['position'])))
    def test_06_system_equal(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set())
        self.assertTrue(all(a['messages'][0]==b['messages'][0] for a,b in zip(rows['repeat'],rows['position'])))
    def test_07_common_messages_unchanged(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set())
        for arm in rows:
            msgs=Counter(v.canon(r['messages']) for r in rows[arm] if r['v05_metadata']['kind']=='contract')
            self.assertEqual(msgs,Counter(v.canon(r['messages']) for r in self.contract))
    def test_08_position_balance(self):
        _,derived,details,_=v.data_variants(self.selected,self.contract,15,set());counts=Counter()
        for (cid,pos),c in derived['position'].items():
            refs=set(c['expected']['evidence_refs']);obs=c['packet']['case_packet']['evidence']
            counts[next(i for i,x in enumerate(obs) if x['evidence_id'] in refs)]+=1
        self.assertEqual(counts,{0:20,1:20,2:20})
    def test_09_repeat_messages_identical(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set());groups={}
        for r in rows['repeat']:
            if r['v05_metadata']['kind']=='physics':groups.setdefault(r['v05_metadata']['parent_case_id'],set()).add(v.canon(r['messages']))
        self.assertTrue(all(len(vv)==1 for vv in groups.values()))
    def test_10_exclude_noise_from_target(self):
        _,derived,details,_=v.data_variants(self.selected,self.contract,15,set())
        for c in derived['position'].values():self.assertFalse(set(c['expected']['evidence_refs'])&{x['evidence_id'] for x in details[c['pair_id']]['synthetic_administrative_observations']})
    def test_11_fresh_handles(self):
        forbidden={x for c in self.cases for x in v.definitions(c)}
        _,d,_,_=v.data_variants(self.selected,self.contract,15,forbidden)
        for c in d['position'].values():self.assertFalse(set(v.definitions(c))&forbidden)
    def test_12_pair_shares_ids(self):
        _,d,_,_=v.data_variants(self.selected,self.contract,15,set())
        for p in v.PAIRS:self.assertEqual(set(v.definitions(d['position'][('PHY-'+p+'-A',0)])),set(v.definitions(d['position'][('PHY-'+p+'-B',0)])))
    def test_13_schedule_aligned(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set());self.assertEqual([r['id'] for r in rows['repeat']],[r['id'] for r in rows['position']])
    def test_14_no_eval_case_added(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set())
        used={r['v05_metadata']['parent_case_id'] for r in rows['position'] if r['v05_metadata']['kind']=='physics'}
        self.assertEqual(used,set(self.selected))
    def test_15_same_seed_same_data(self):
        self.assertEqual(v.data_variants(self.selected,self.contract,15,set()),v.data_variants(self.selected,self.contract,15,set()))
    def test_16_format_roundtrip(self):
        for indent in (None,2,4):
            text=json.dumps({'x':['한글']},ensure_ascii=False,indent=indent)
            self.assertEqual(v.render_like(text,{'x':['한글']},{'x':['new']}),json.dumps({'x':['new']},ensure_ascii=False,indent=indent))
    def test_17_packet_inside_wrapper(self):
        t='ROLE: EVIDENCE\n'+json.dumps({'packet':self.cases[0]['packet']},indent=2)
        i,j,o=v.json_span(t,self.cases[0]['packet']);self.assertEqual(json.loads(t[i:j]),self.cases[0]['packet'])
    def test_18_missing_packet_fails(self):
        with self.assertRaises(ValueError):v.json_span('{}',self.cases[0]['packet'])
    def test_19_duplicate_packet_fails(self):
        t=json.dumps(self.cases[0]['packet'])
        with self.assertRaises(ValueError):v.json_span(t+t,self.cases[0]['packet'])
    def test_20_missing_contract_fails(self):
        with self.assertRaises(ValueError):v.recover_selected(self.mixed[1:],self.contract,self.cases)
    def test_21_gold_changed_fails(self):
        rows=copy.deepcopy(self.mixed)
        for r in rows:
            if r['id'].startswith('PHY-'):r['messages'][-1]['content']='{}';break
        with self.assertRaises(ValueError):v.recover_selected(rows,self.contract,self.cases)
    def test_22_no_metadata_in_messages(self):
        rows,*_=v.data_variants(self.selected,self.contract,15,set())
        for r in rows['position']:self.assertNotIn('v05_metadata',v.canon(r['messages']))
    def test_23_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):v.strict('{"x":1,"x":2}')
    def test_24_nan_rejected(self):
        with self.assertRaises(ValueError):v.strict('{"x":NaN}')
    def test_25_traversal_rejected(self):
        with self.assertRaises(ValueError):v.relpath(Path('/tmp'),Path('../secret'))
    def test_26_html_contains_twenty_targets(self):
        _,_,d,_=v.data_variants(self.selected,self.contract,15,set());t=v.review_html(d);self.assertEqual(t.count('<section>'),20)

class IntegrationTests(unittest.TestCase):
    def test_27_end_to_end_mocked_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=make_project(tmp);od=Path(v.OUTDIR);target=root/od
            before={p:v.sha(p) for p in root.rglob('*') if p.is_file()}
            with patch.multiple(v,TRAIN_SHA=v.sha(root/v.TRAIN),CONTRACT_SHA=v.sha(root.parent/'data/train150_v01.jsonl'),CASES_SHA=v.sha(root/v.CASES)),redirect_stdout(io.StringIO()):
                v.build(root,od,14)
                for p,h in before.items():self.assertEqual(v.sha(p),h)
                with self.assertRaises(FileNotFoundError):v.load_plan(root,od,True)
                with self.assertRaises(ValueError):v.approve(root,od,'','bad')
                v.approve(root,od,'UNIT_TEST_ONLY','Synthetic administrative rows reviewed only in temporary fixture')
                with self.assertRaises(ValueError):v.approve(root,od,'TEST','duplicate')
                for p,h in before.items():self.assertEqual(v.sha(p),h)
                plan=v.strict((target/'manifest.json').read_text());rev='a'*40
                v.write_json(target/'base_revision.json',{'revision':rev,'model':plan['model']})
                def fake_run(root_,target_,label,args,cwd=None,env=None):
                    log=target_/('testlog_'+label+'.txt');log.write_text('MOCK SUBPROCESS: NO GPU EXECUTION')
                    if '-m' in args and 'dcurr.preflight' in args:
                        return json.dumps({'status':'PASS','records':210,'silent_truncation':False,'total_answer_tokens':5000}),log
                    if '_train-worker' in args:
                        arm=args[args.index('--arm')+1];d=root_/plan['arms'][arm]['adapter'];d.mkdir(parents=True)
                        v.write_bytes(d/'adapter_model.safetensors',('FAKE WEIGHTS '+arm).encode());v.write_json(d/'adapter_config.json',{'r':16});return '',log
                    if 'dcurr.evaluate' in args:
                        cs=v.read_jsonl(root_/args[args.index('--cases')+1]);rs=[]
                        for c in cs:
                            obj=copy.deepcopy(c['expected']);rs.append({'case_id':c['case_id'],'parsed':obj,'raw_output':json.dumps(obj),'contract_pass':True})
                        v.write_bytes(root_/args[args.index('--out')+1],v.jsonl_bytes(rs));return '',log
                    if 'eval.run_eval40_qwen35' in args:
                        label_=args[args.index('--label')+1];path=root_.parent/f'eval/results/{label_}_dev.jsonl'
                        v.write_bytes(path,v.jsonl_bytes([{'id':'DEV-'+str(i),'pass':True,'action_ok':True} for i in range(20)]));return '',log
                    raise AssertionError(args)
                with patch.object(v,'run_logged',side_effect=fake_run):
                    v.train(root,od);v.evaluate(root,od);v.compare(root,od)
                    # Rerunning completed stages verifies files and never trains again.
                    v.train(root,od);v.evaluate(root,od)
                r=v.strict((target/'comparison.json').read_text());self.assertEqual(r['models']['position']['views']['before']['strict_selection_contract_pass'],40)
                self.assertEqual(r['models']['position']['views']['before']['selected20']['cases'],20)
                self.assertEqual(r['models']['position']['legacy_contract_dev']['pass'],20)
                with self.assertRaises(ValueError):v.compare(root,od)
                for p,h in before.items():self.assertEqual(v.sha(p),h)
                # Frozen artifact edits must stop the experiment.
                (root/'dcurr/train.py').write_text('changed')
                with self.assertRaises(ValueError):v.load_plan(root,od,True)
        for name in list(sys.modules):
            if name=='dcurr' or name.startswith('dcurr.'):del sys.modules[name]

if __name__=='__main__':unittest.main()
