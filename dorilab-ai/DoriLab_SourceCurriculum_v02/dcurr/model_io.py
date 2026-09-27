"""One renderer for training/inference. Text-only inputs to a multimodal backbone."""
from __future__ import annotations
import hashlib,json,platform,importlib.metadata
from .common import mask_completion
DEFAULT_MODEL='Qwen/Qwen3.5-2B'

def environment():
    packages={}
    for p in ['torch','transformers','peft','trl','datasets','accelerate','jsonschema']:
        try:packages[p]=importlib.metadata.version(p)
        except importlib.metadata.PackageNotFoundError:packages[p]='NOT_INSTALLED'
    return {'python':platform.python_version(),'platform':platform.platform(),'packages':packages}

def load_processor(model=DEFAULT_MODEL,revision=None):
    from transformers import AutoProcessor
    kw={'revision':revision} if revision else {}
    return AutoProcessor.from_pretrained(model,**kw)

def render_prompt(processor,messages):
    if any(x['role']=='assistant' for x in messages):raise ValueError('For this single-step task pass system/user only to inference')
    return processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)

def prompt_tokens(processor,messages):
    text=render_prompt(processor,messages)
    ids=processor.tokenizer(text,add_special_tokens=False)['input_ids']
    direct=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False)['input_ids'][0].tolist()
    if ids!=direct:raise ValueError('Tokenizer/processor prompt mismatch. Inspect chat-template and special token settings.')
    return text,ids

def stop_id(processor):
    t=processor.tokenizer
    # Match the assistant message terminator, not an arbitrary corpus terminator.
    vocab=t.get_vocab()
    if '<|im_end|>' not in vocab:raise ValueError('Expected Qwen message end token is absent; inspect tokenizer before training')
    return int(vocab['<|im_end|>'])

def encode_record(processor,row,max_length):
    m=row['messages']
    if [x['role'] for x in m]!=['system','user','assistant']:raise ValueError('Expected one system/user/assistant record')
    text,pids=prompt_tokens(processor,m[:-1])
    aids=processor.tokenizer(m[-1]['content'],add_special_tokens=False)['input_ids']
    out=mask_completion(pids,aids,stop_id(processor),max_length)
    # Appending answer tokens never changes the frozen inference prefix.
    if out['input_ids'][:len(pids)]!=pids:raise AssertionError('Prompt prefix changed')
    return out,{'id':row.get('id'),'prompt_tokens':len(pids),'answer_tokens':len(aids)+1,'total_tokens':len(out['input_ids']),'system_sha256':hashlib.sha256(m[0]['content'].encode()).hexdigest()}

def model_class():
    import transformers
    cls=getattr(transformers,'AutoModelForMultimodalLM',None)
    if cls is None:cls=getattr(transformers,'Qwen3_5ForConditionalGeneration',None)
    if cls is None:raise ImportError('Installed Transformers does not expose the already-tested Qwen3.5 loader')
    return cls

def load_model(model=DEFAULT_MODEL,revision=None,inference=False):
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable. Use the working Windows/WSL venv on RTX 5080.')
    if not torch.cuda.is_bf16_supported():raise RuntimeError('BF16 unavailable')
    kw={'dtype':torch.bfloat16}
    if revision:kw['revision']=revision
    if inference:kw['device_map']={'':0}
    return model_class().from_pretrained(model,**kw)
