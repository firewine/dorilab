from __future__ import annotations
import copy, importlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dorilab_gemma.common import *
from dorilab_gemma.modeling import encoded_answer,prompt_text,selected_loss,single_collator,generation_stops
from dorilab_gemma.scoring import score,matches,aggregate

class Tokenizer:
    pad_token_id=0
    def get_vocab(self):return {'<turn|>':9}
    def convert_tokens_to_ids(self,text):return self.get_vocab().get(text,-1)
    def __call__(self,text,**kw):
        out=[]
        while text:
            if text.startswith('<turn|>'):out.append(9);text=text[7:]
            else:out.append(ord(text[0])+100);text=text[1:]
        return {'input_ids':out}
    def decode(self,ids,**kw):return ''.join('<turn|>' if t==9 else chr(t-100) for t in ids)
class Processor:
    tokenizer=Tokenizer()
    def apply_chat_template(self,msgs,add_generation_prompt=False,**kw):
        text='<bos>'
        for m in msgs:
            role='model' if m['role']=='assistant' else m['role']
            text+='<|turn>'+role+'\n'+m['content'].strip()+'<turn|>\n'
        if add_generation_prompt:text+='<|turn>model\n'
        return text

def messages():return [{'role':'system','content':'policy'},{'role':'user','content':'current observation'},{'role':'assistant','content':'{"action":"NO_ACTION_REQUIRED"}'}]
def item():
    return {'suite':'ns10','case_id':'X','messages':messages()[:2],
            'case':{'expected':{'action':'CHALLENGE','reason':'R','claim_id':'C','evidence_refs':['S','O']},
                    'packet':{'claim_id':'C','reference_context':[{'reference_id':'S','source_id':'DOC'}],
                              'case_packet':{'evidence':[{'evidence_id':'O'},{'evidence_id':'DIST'}]},'allowed_request_ids':['REQUEST']}}}
SCHEMA={'type':'object','required':['action','claim_id','evidence_refs'],'properties':{'action':{'type':'string'},'claim_id':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}}}}

class Tests(unittest.TestCase):
    def test_01_duplicate_json(self):
        with self.assertRaises(ValueError):strict_json('{"x":1,"x":2}')
    def test_02_nonfinite(self):
        with self.assertRaises(ValueError):strict_json('{"x":NaN}')
    def test_03_trailing_rejected(self):
        with self.assertRaises(ValueError):strict_json('{} junk')
    def test_04_messages_no_gold(self):
        with self.assertRaises(ValueError):messages_ok(messages(),False)
    def test_05_no_qwen_tokens(self):
        m=messages();m[0]['content']='<|im_start|>system'
        with self.assertRaises(ValueError):messages_ok(m,True)
    def test_06_assistant_json_required(self):
        m=messages();m[-1]['content']='not json'
        with self.assertRaises(ValueError):messages_ok(m,True)
    def test_07_native_mask(self):
        p=Processor();enc,stat=encoded_answer(p,messages(),2048)
        self.assertTrue(all(x==-100 for x in enc['labels'][:stat['prompt_tokens']]))
        self.assertEqual(enc['labels'][-1],9)
        self.assertEqual(p.tokenizer.decode(enc['input_ids'][stat['prompt_tokens']:-1]),messages()[-1]['content'])
    def test_08_no_truncation(self):
        with self.assertRaises(ValueError):encoded_answer(Processor(),messages(),10)
    def test_09_training_inference_prefix(self):
        p=Processor();enc,st=encoded_answer(p,messages(),2048)
        self.assertEqual(p.tokenizer(prompt_text(p,messages()[:2]))['input_ids'],enc['input_ids'][:st['prompt_tokens']])
    def test_10_template_mismatch(self):
        class Bad(Processor):
            def apply_chat_template(self,msgs,**kw):
                s=super().apply_chat_template(msgs,**kw)
                return ('different'+s) if len(msgs)==3 else s
        with self.assertRaises(ValueError):encoded_answer(Bad(),messages(),2048)
    def test_11_selected_loss_full_equivalence(self):
        torch.manual_seed(1)
        logits=torch.randn(1,7,13,requires_grad=True)
        class Dummy:
            def __call__(self,logits_to_keep,**kw):return type('Output',(),{'logits':logits[:,logits_to_keep,:]})()
        labels=torch.tensor([[-100,-100,-100,3,4,6,2]])
        inputs={'input_ids':torch.ones((1,7),dtype=torch.long),'labels':labels}
        loss,_=selected_loss(Dummy(),inputs)
        full=torch.nn.functional.cross_entropy(logits[:,:-1,:].reshape(-1,13),labels[:,1:].reshape(-1),ignore_index=-100)
        self.assertTrue(torch.allclose(loss,full))
        grad1=torch.autograd.grad(loss,logits,retain_graph=True)[0]
        grad2=torch.autograd.grad(full,logits)[0]
        self.assertTrue(torch.allclose(grad1,grad2))
    def test_12_microbatch_constraint(self):
        with self.assertRaises(ValueError):single_collator([{},{}])
    def test_13_all_masked_rejected(self):
        with self.assertRaises(ValueError):selected_loss(None,{'labels':torch.full((1,4),-100)})
    def test_14_good_physics_score(self):
        c=item();r=score(c,json.dumps(c['case']['expected']),SCHEMA)
        self.assertTrue(r['strict_contract_pass'])
    def test_15_no_metadata_reference(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['evidence_refs'].append('DOC')
        r=score(c,json.dumps(a),SCHEMA);self.assertFalse(r['schema_and_refs_valid'])
    def test_16_distractor_not_exact(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['evidence_refs'].append('DIST')
        r=score(c,json.dumps(a),SCHEMA);self.assertTrue(r['schema_and_refs_valid']);self.assertFalse(r['strict_contract_pass'])
    def test_17_request_namespace(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['requested_evidence']=['O']
        self.assertFalse(score(c,json.dumps(a),SCHEMA)['schema_and_refs_valid'])
    def test_18_id_order_invariant(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['evidence_refs'].reverse()
        self.assertTrue(score(c,json.dumps(a),SCHEMA)['strict_contract_pass'])
    def test_19_duplicate_refs_rejected(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['evidence_refs'].append('O')
        self.assertFalse(score(c,json.dumps(a),SCHEMA)['strict_contract_pass'])
    def test_20_hit_budget_fail(self):
        c=item();self.assertFalse(score(c,json.dumps(c['case']['expected']),SCHEMA,True)['strict_contract_pass'])
    def test_21_reason_error_not_action(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['reason']='wrong'
        r=score(c,json.dumps(a),SCHEMA);self.assertTrue(r['action_correct']);self.assertFalse(r['strict_contract_pass'])
    def test_22_claim_mismatch(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['claim_id']='bad'
        self.assertFalse(score(c,json.dumps(a),SCHEMA)['schema_and_refs_valid'])
    def test_23_path_traversal(self):
        with self.assertRaises(ValueError):inside('/tmp/a','../../escape')
    def test_24_no_output_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x';write_json(p,{})
            with self.assertRaises(FileExistsError):write_json(p,{})
    def test_25_gold_change_not_input_change(self):
        x=item();y=copy.deepcopy(x);y['case']['expected']['action']='NO_ACTION_REQUIRED'
        self.assertEqual(prompt_text(Processor(),x['messages']),prompt_text(Processor(),y['messages']))
    def test_26_contract_scalar_list_distinction(self):
        self.assertFalse(matches({'valid_scope':['X']},{'valid_scope':'X'}))
    def test_27_parsed_objects_not_hash_crash(self):
        c=item();a=copy.deepcopy(c['case']['expected']);a['evidence_refs']=[{'id':'O'}]
        self.assertFalse(score(c,json.dumps(a),SCHEMA)['strict_contract_pass'])
    def test_28_stop_ids(self):
        cfg=type('Cfg',(),{'eos_token_id':[1,9]})();self.assertEqual(generation_stops(Processor(),cfg),[1,9])
    def test_29_contract_export_child(self):
        with tempfile.TemporaryDirectory() as t:
            mirror=Path(t)/'mirror';(mirror/'eval/results').mkdir(parents=True)
            code='''import argparse,json,torch\nfrom pathlib import Path\nfrom transformers import AutoProcessor,AutoModelForImageTextToText\np=argparse.ArgumentParser();p.add_argument('--split');p.add_argument('--label');a=p.parse_args()\nprocessor=AutoProcessor.from_pretrained('ignored');model=AutoModelForImageTextToText.from_pretrained('ignored')\nrows=[]\nfor i in range(20):\n ms=[{'role':'system','content':'system'},{'role':'user','content':'case '+str(i)}]\n text=processor.apply_chat_template(ms,tokenize=False,add_generation_prompt=True)\n batch=processor(text=text,return_tensors='pt').to('cuda')\n output=model.generate(**batch)\n raw=processor.decode(output[0,batch['input_ids'].shape[-1]:])\n rows.append({'id':'DEV-X-'+str(i),'role':'CRITIC','expected':{'action':'NO_ACTION_REQUIRED'},'raw_output':raw,'pass':False})\nPath('eval/results/'+a.label+'_dev.jsonl').write_text(''.join(json.dumps(x)+'\\n' for x in rows))\n'''
            (mirror/'eval/run_eval40_qwen35.py').write_text(code)
            dest=Path(t)/'out.jsonl'
            proc=subprocess.run([sys.executable,'-m','dorilab_gemma.capture_contract','--mirror',str(mirror),'--out',str(dest)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            rows=read_jsonl(dest);self.assertEqual(len(rows),20)
            self.assertEqual(rows[3]['messages'][1]['content'],'case 3')
            self.assertEqual(rows[3]['case']['expected'],{'action':'NO_ACTION_REQUIRED'})
    def test_30_repo_identity_no_old_model(self):
        self.assertEqual(MODEL_ID,'google/gemma-4-E4B-it')
        self.assertNotIn('Qwen',MODEL_ID)
if __name__=='__main__':unittest.main()
