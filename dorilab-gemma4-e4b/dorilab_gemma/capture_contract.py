"""Run a COPIED legacy reader with inert model/tokenizer doubles.
This exports its actual system/user messages, ids and expected answers. It is
NOT model inference and its dummy scores are never reported. No HF/network or
CUDA model load occurs. All output stays in the new project's snapshot.
"""
from __future__ import annotations
import argparse, contextlib, copy, json, os, runpy, sys, types
from pathlib import Path
from .common import require, write_jsonl, read_jsonl, messages_ok

def capture(mirror: Path, dest: Path):
    import torch
    calls=[]
    class Batch(dict):
        def to(self,*a,**kw): return self
    class Processor:
        def __init__(self):
            self.tokenizer=self; self.pad_token_id=0; self.eos_token_id=2; self.bos_token_id=1
            self.eos_token='<end>';self.pad_token='<pad>';self.padding_side='left'
        @classmethod
        def from_pretrained(cls,*args,**kw): return cls()
        def apply_chat_template(self,messages,tokenize=False,**kw):
            messages_ok(messages,False);calls.append(copy.deepcopy(messages))
            if tokenize:
                if kw.get('return_dict'):return self('placeholder')
                if kw.get('return_tensors'):return torch.tensor([[1,3,4]])
                return [1,3,4]
            return 'EXPORT_PLACEHOLDER'
        def __call__(self,*args,**kw):
            return Batch(input_ids=torch.tensor([[1,3,4]]),attention_mask=torch.ones((1,3),dtype=torch.long))
        def decode(self,*a,**kw):return '{}'
        def batch_decode(self,*a,**kw):return ['{}']
        def parse_response(self,*a,**kw):return {'content':'{}'}
    class Model:
        device=torch.device('cpu')
        dtype=torch.float32
        config=types.SimpleNamespace(use_cache=True,_commit_hash='EXPORT_NO_MODEL',pad_token_id=0,eos_token_id=2,text_config=types.SimpleNamespace(pad_token_id=0,eos_token_id=2))
        generation_config=types.SimpleNamespace(pad_token_id=0,eos_token_id=2)
        @classmethod
        def from_pretrained(cls,*args,**kw):return cls()
        def eval(self):return self
        def to(self,*a,**kw):return self
        def parameters(self):return iter([])
        def generate(self,*args,**kw):
            ids=kw.get('input_ids',args[0] if args else None)
            require(ids is not None,'Legacy runner generate input unsupported')
            return torch.cat([ids,torch.tensor([[7,2]])],dim=1)
    t=types.ModuleType('transformers')
    for name in ('AutoProcessor','AutoTokenizer'):setattr(t,name,Processor)
    for name in ('AutoModelForImageTextToText','AutoModelForMultimodalLM','AutoModelForCausalLM','Qwen3_5ForConditionalGeneration'):
        setattr(t,name,Model)
    t.set_seed=lambda *a,**k:None
    t.__version__='EXPORT_ONLY'
    t.logging=types.SimpleNamespace(set_verbosity_error=lambda:None,set_verbosity_warning=lambda:None)
    sys.modules['transformers']=t
    p=types.ModuleType('peft');p.PeftModel=Model;sys.modules['peft']=p
    # Redirect any tensor .to('cuda') used by the reader to CPU. Only this child.
    original_to=torch.Tensor.to
    def cpu_to(self,*args,**kw):
        args=list(args)
        if args and (isinstance(args[0],str) and args[0].startswith('cuda') or isinstance(args[0],torch.device) and args[0].type=='cuda'):
            args[0]=torch.device('cpu')
        if isinstance(kw.get('device'),(str,torch.device)) and str(kw['device']).startswith('cuda'):kw['device']='cpu'
        return original_to(self,*args,**kw)
    torch.Tensor.to=cpu_to
    torch.cuda.is_available=lambda:True
    torch.cuda.is_bf16_supported=lambda:True
    for name in ('empty_cache','synchronize','reset_peak_memory_stats','manual_seed','manual_seed_all','set_device'):
        setattr(torch.cuda,name,lambda *a,**k:None)
    for name in ('memory_allocated','memory_reserved','max_memory_allocated','max_memory_reserved','current_device'):
        setattr(torch.cuda,name,lambda *a,**k:0)
    torch.cuda.get_device_name=lambda *a:'EXPORT_ONLY_CPU_NO_MODEL'
    torch.cuda.get_device_properties=lambda *a:types.SimpleNamespace(total_memory=16*1024**3,major=12,minor=0)
    torch.cuda.get_device_capability=lambda *a:(12,0)
    torch.autocast=lambda *a,**k:contextlib.nullcontext()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
    # A Python audit hook prevents the copied reader from writing to an old
    # hard-coded project path. Allowed writes stay inside the new project.
    allowed_root=dest.resolve().parent.parent
    def audit(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            mode=args[1] or '';flags=args[2] or 0
            writing=any(x in str(mode) for x in ('w','a','+','x')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing:
                require(Path(os.fsdecode(args[0])).resolve().is_relative_to(allowed_root),'Legacy reader attempted write outside new project')
        if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
            paths=args[:2] if event=='os.rename' else args[:1]
            for path in paths:
                if isinstance(path,(str,bytes,os.PathLike)):
                    require(Path(os.fsdecode(path)).resolve().is_relative_to(allowed_root),'Legacy reader attempted filesystem mutation outside new project')
        if event=='socket.connect':raise ValueError('Network is disabled during legacy message export')
    os.chdir(mirror);sys.path.insert(0,str(mirror));sys.addaudithook(audit)
    label='_GEMMA_MESSAGE_EXPORT_NOT_INFERENCE'
    runner=mirror/'eval/run_eval40_qwen35.py'
    sys.argv=[str(runner),'--split','dev','--label',label]
    try:runpy.run_path(str(runner),run_name='__main__')
    except SystemExit as ex:
        require(ex.code in (None,0),f'Legacy reader stopped: {ex.code}')
    results=read_jsonl(mirror/'eval/results'/f'{label}_dev.jsonl')
    require(len(calls)==len(results)==20,f'Expected exactly 20 prompt captures; got {len(calls)} / {len(results)}')
    rows=[]
    for ms,r in zip(calls,results):
        cid=r.get('id',r.get('case_id'))
        require(isinstance(cid,str) and cid.startswith('DEV-'),'Unexpected Contract id')
        require(isinstance(r.get('expected'),dict),'Legacy reader did not export expected answer')
        rows.append({'case_id':cid,'suite':'contract20','messages':ms,
                     'case':{'case_id':cid,'role':r.get('role'),'expected':r['expected']},
                     'prompt_capture':'copied_legacy_reader_with_inert_model_not_inference'})
    write_jsonl(dest,rows)
    print('CONTRACT MESSAGE EXPORT: 20 captured; no model inference')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mirror',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();capture(a.mirror.resolve(),a.out.resolve())
if __name__=='__main__':main()
