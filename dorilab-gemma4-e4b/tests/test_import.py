from __future__ import annotations
import json, shutil, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dorilab_gemma.common import *
from dorilab_gemma.importer import build

class ImportTests(unittest.TestCase):
    def test_full_snapshot_import_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);oldparent=t/'old';src=oldparent/'DoriLab_SourceCurriculum_v02';new=t/'new'
            new.mkdir();shutil.copytree(ROOT/'dorilab_gemma',new/'dorilab_gemma',ignore=shutil.ignore_patterns('__pycache__'))
            (src/'dcurr').mkdir(parents=True);(oldparent/'eval').mkdir()
            (src/'dcurr/__init__.py').write_text('')
            (src/'dcurr/prompts.py').write_text("import json\ndef build_messages(role,packet,answer=None):\n r=[{'role':'system','content':'S'},{'role':'user','content':json.dumps({'role':role,'packet':packet})}]\n if answer is not None:r.append({'role':'assistant','content':json.dumps(answer)})\n return r\n")
            (src/'dcurr/prompts_legacy.py').write_text("SYSTEM={'CRITIC':'S'}\n")
            (src/'dcurr/common.py').write_text('def validate_answer(answer,case):\n assert answer["claim_id"]==case["packet"]["claim_id"]\n')
            (src/'data/reason_coverage_v12/results').mkdir(parents=True)
            def msgs(c):return [{'role':'system','content':'S'},{'role':'user','content':json.dumps({'role':c['role'],'packet':c['packet']})}]
            train=[{'id':f'TR-{i}','messages':[{'role':'system','content':'S'},{'role':'user','content':f'train {i}'},{'role':'assistant','content':'{"action":"NO_ACTION_REQUIRED"}'}]} for i in range(246)]
            trainpath=src/'data/reason_coverage_v12/repeat246.jsonl';write_jsonl(trainpath,train)
            write_json(trainpath.with_suffix('.manifest.json'),{'records':246,'data_sha256':sha(trainpath),'prompt_file_sha256':sha(src/'dcurr/prompts.py'),'legacy_prompt_sha256':sha(src/'dcurr/prompts_legacy.py')})
            evs={}
            for suite,n in [('ns10',24),('before',40)]:
                cs=[]
                for i in range(n):
                    c={'case_id':f'{suite}-{i}','pair_id':f'{suite}-{i//2}','role':'CRITIC','packet':{'claim_id':f'C-{i}','reference_context':[{'reference_id':'S'}],'case_packet':{'evidence':[{'evidence_id':'O'}]},'allowed_request_ids':[]},'expected':{'action':'NO_ACTION_REQUIRED','claim_id':f'C-{i}','evidence_refs':['S','O']}}
                    cs.append(c)
                evs[suite]=cs;write_jsonl(src/f'data/{suite}.jsonl',cs)
                write_jsonl(src/f'data/reason_coverage_v12/results/repeat_{suite}.jsonl',[{'case_id':c['case_id'],'raw_output':json.dumps(c['expected']),'contract_pass':True} for c in cs])
            write_jsonl(src/'data/ns10_inputs.jsonl',[{'case_id':c['case_id'],'messages':msgs(c)} for c in evs['ns10']])
            write_json(src/'data/action_schema_v02.json',{'type':'object'})
            write_json(src/'data/reason_coverage_v12/manifest.json',{'arms':{'repeat':{'data':'data/reason_coverage_v12/repeat246.jsonl'}},'v10_cases':'data/ns10.jsonl','v10_inputs':'data/ns10_inputs.jsonl','before_cases':'data/before.jsonl'})
            code="""import argparse,json,torch
from pathlib import Path
from transformers import AutoProcessor,AutoModelForImageTextToText
p=argparse.ArgumentParser();p.add_argument('--split');p.add_argument('--label');a=p.parse_args()
proc=AutoProcessor.from_pretrained('dummy');model=AutoModelForImageTextToText.from_pretrained('dummy')
rows=[]
for i in range(20):
 ms=[{'role':'system','content':'S'},{'role':'user','content':f'eval {i}'}]
 text=proc.apply_chat_template(ms,tokenize=False,add_generation_prompt=True)
 x=proc(text=text,return_tensors='pt')
 y=model.generate(**x)
 raw=proc.decode(y[0,3:])
 rows.append({'id':f'DEV-{i}','role':'CRITIC','expected':{'action':'NO_ACTION_REQUIRED'},'raw_output':raw,'pass':False})
Path('eval/results').mkdir(exist_ok=True)
Path('eval/results/'+a.label+'_dev.jsonl').write_text(''.join(json.dumps(x)+'\\n' for x in rows))
"""
            (oldparent/'eval/run_eval40_qwen35.py').write_text(code)
            write_jsonl(src/'data/reason_coverage_v12/results/repeat_contract.jsonl',[{'id':f'DEV-{i}','raw_output':'{"action":"NO_ACTION_REQUIRED"}','pass':True} for i in range(20)])
            before={str(p):sha(p) for p in oldparent.rglob('*') if p.is_file()}
            try:m=build(src,new)
            finally:
                for k in list(sys.modules):
                    if k=='dcurr' or k.startswith('dcurr.'):del sys.modules[k]
            after={str(p):sha(p) for p in oldparent.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertEqual(m['training_rows'],246)
            self.assertEqual(m['baseline_2b_rescored']['contract20']['strict_contract_pass'],20)
            self.assertEqual(len(read_jsonl(new/'data/eval_ns10.jsonl')),24)
            self.assertEqual(sha(trainpath),sha(new/'data/train.jsonl'))
            self.assertFalse(m['old_adapter_imported'])
if __name__=='__main__':unittest.main()
