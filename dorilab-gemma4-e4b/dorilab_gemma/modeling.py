from __future__ import annotations
import inspect, re, time
from pathlib import Path
from .common import *

LORA_SUFFIXES={'q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'}
END_TOKENS=('<turn|>','<|fim_suffix|>','<end_of_turn>')

def prompt_text(processor,messages):
    messages_ok(messages,False)
    text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
    require(isinstance(text,str) and text,'Empty model prompt')
    require('<|im_start|>' not in text and '<|im_end|>' not in text,'Qwen template leaked into Gemma')
    require('<|turn>system' in text and '<|turn>model' in text,'Unexpected Gemma 4 template roles')
    require('<|think|>' not in text,'Thinking must remain disabled')
    return text

def tokenize_text(tok,text):
    result=tok(text,add_special_tokens=False,truncation=False)
    ids=result['input_ids'];require(isinstance(ids,list) and ids and isinstance(ids[0],int),'Expected flat token IDs')
    return ids

def encoded_answer(processor,messages,max_length):
    messages_ok(messages,True);tok=processor.tokenizer
    prefix=prompt_text(processor,messages[:-1])
    whole=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=False,enable_thinking=False)
    target=messages[-1]['content'].strip()
    require(whole.startswith(prefix+target),'Gemma training/inference prefix mismatch; no masking guess allowed')
    prefix_ids=tokenize_text(tok,prefix);ids=tokenize_text(tok,whole)
    require(ids[:len(prefix_ids)]==prefix_ids,'Token-boundary mismatch; refusing to train the wrong labels')
    terminal_ids={tok.convert_tokens_to_ids(s) for s in END_TOKENS if s in tok.get_vocab()}
    require(terminal_ids,'No known Gemma turn-end token in tokenizer')
    terminals=[i for i in range(len(prefix_ids),len(ids)) if ids[i] in terminal_ids]
    require(len(terminals)==1,'Expected one terminal in the final assistant turn')
    end=terminals[0]
    require(not tok.decode(ids[end+1:],skip_special_tokens=False).strip(),'Non-whitespace after answer terminal')
    # Drop only the template separator newline, never user/answer content.
    ids=ids[:end+1]
    require(len(ids)<=max_length,f'Input requires {len(ids)} tokens > {max_length}; no silent truncation')
    require(tok.decode(ids[len(prefix_ids):end],skip_special_tokens=False).strip()==target,'Decoded supervised answer differs')
    labels=[-100]*len(prefix_ids)+ids[len(prefix_ids):]
    require(any(x!=-100 for x in labels),'Fully masked training example')
    return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels}, {
        'prompt_tokens':len(prefix_ids),'answer_and_end_tokens':len(ids)-len(prefix_ids),
        'total_tokens':len(ids),'terminal_id':ids[-1],'prefix_sha256':digest(prefix),
        'messages_sha256':digest(messages[:-1])}

def generation_stops(processor,config):
    tok=processor.tokenizer;stops=set()
    for obj in (config,getattr(config,'text_config',None)):
        v=getattr(obj,'eos_token_id',None)
        if isinstance(v,int):stops.add(v)
        elif isinstance(v,list):stops.update(v)
    for name in END_TOKENS:
        if name in tok.get_vocab():stops.add(tok.convert_tokens_to_ids(name))
    require(stops,'No stopping IDs')
    return sorted(stops)

def load_processor(model_id,revision):
    from transformers import AutoProcessor
    processor=AutoProcessor.from_pretrained(model_id,revision=revision,trust_remote_code=False)
    require(getattr(processor,'tokenizer',None) is not None,'Processor missing tokenizer')
    tok=processor.tokenizer
    require(tok.pad_token_id is not None,'Gemma tokenizer has no padding token; refusing implicit vocabulary changes')
    return processor

def selected_loss(model,inputs):
    """Exact next-token CE for response targets, batch size 1. Keeps all context.
    Only materializes vocabulary logits at positions that predict target tokens.
    This is NOT truncation and does not change the underlying cross-entropy.
    """
    import torch
    import torch.nn.functional as F
    labels=inputs['labels'];require(labels.ndim==2 and labels.shape[0]==1,'Response-only loss supports microbatch=1')
    positions=torch.nonzero(labels[0,1:]!=-100,as_tuple=False).flatten()
    require(positions.numel()>0,'No next-token targets')
    kwargs={k:v for k,v in inputs.items() if k!='labels'}
    out=model(**kwargs,logits_to_keep=positions,use_cache=False)
    logits=out.logits
    require(logits.shape[1]==positions.numel(),'Model did not honor logits_to_keep; refusing full-logit memory fallback')
    target=labels[0,positions+1]
    loss=F.cross_entropy(logits[0].float(),target)
    return loss,out

def single_collator(rows):
    import torch
    require(len(rows)==1,'microbatch must be 1')
    return {key:torch.tensor([rows[0][key]],dtype=torch.long) for key in ('input_ids','attention_mask','labels')}

def check_gpu():
    import torch, bitsandbytes as bnb
    require(torch.cuda.is_available(),'CUDA is not available in the NEW environment')
    require(torch.cuda.is_bf16_supported(),'This recipe requires BF16 support')
    require(torch.cuda.device_count()>=1,'No GPU')
    require(str(torch.version.cuda).startswith('12.8'),'Expected isolated cu128 runtime; do not reuse old cu132 venv')
    # Real CUDA NF4 forward + backward, not just import success.
    layer=bnb.nn.Linear4bit(32,16,bias=False,compute_dtype=torch.bfloat16,quant_type='nf4',compress_statistics=True).to('cuda')
    x=torch.randn(2,32,device='cuda',dtype=torch.bfloat16,requires_grad=True)
    y=layer(x).float().square().mean();y.backward();torch.cuda.synchronize()
    require(x.grad is not None and torch.isfinite(x.grad).all().item(),'NF4 CUDA backward test failed')
    report={'gpu':torch.cuda.get_device_name(0),'capability':list(torch.cuda.get_device_capability(0)),
            'total_GiB':torch.cuda.get_device_properties(0).total_memory/1024**3,
            'free_GiB':torch.cuda.mem_get_info()[0]/1024**3,'cuda_runtime':torch.version.cuda,'nf4_backward':'PASS'}
    del layer,x,y;torch.cuda.empty_cache()
    return report

def load_model(model_id,revision,training=False,adapter=None):
    import torch
    from transformers import Gemma4ForConditionalGeneration,BitsAndBytesConfig
    from peft import LoraConfig,get_peft_model,PeftModel
    kwargs=dict(revision=revision,trust_remote_code=False,dtype=torch.bfloat16,
                device_map={'':0},attn_implementation='sdpa',low_cpu_mem_usage=True,
                quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_use_double_quant=True,
                 bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.bfloat16,
                 bnb_4bit_quant_storage=torch.uint8))
    model=Gemma4ForConditionalGeneration.from_pretrained(model_id,**kwargs)
    require(model.config.model_type=='gemma4','Wrong architecture')
    require(getattr(model.config.text_config,'num_hidden_layers',None)==42,'This recipe is for Gemma 4 E4B')
    require('logits_to_keep' in inspect.signature(model.forward).parameters,'Installed Gemma implementation lacks selected logits')
    require(getattr(model,'is_loaded_in_4bit',False),'4-bit loading did not take effect')
    # Keep large frozen PLE tables/embeddings BF16. prepare_model_for_kbit_training
    # generically casts nonquantized weights to FP32 and is NOT used here.
    # Gemma4 RMSNorm itself computes in float32; non-reentrant checkpointing
    # preserves LoRA gradients without requiring trainable embedding tables.
    for p in model.parameters():p.requires_grad_(False)
    report={'class':type(model).__name__,'revision':revision,'loaded_4bit':True,
            'frozen_embeddings':[],'lora_targets':[],'trainable_parameters':0,
            'preparation':'explicit_freeze_bf16_embeddings_nonreentrant_checkpointing'}
    for name,module in model.named_modules():
        if isinstance(module,torch.nn.Embedding):
            require(module.weight.dtype==torch.bfloat16,'Frozen embedding unexpectedly not BF16: '+name)
            report['frozen_embeddings'].append({'name':name,'parameters':module.weight.numel(),'dtype':str(module.weight.dtype)})
    if training:
        targets=[]
        for name,module in model.named_modules():
            if '.language_model.layers.' in '.'+name and name.rsplit('.',1)[-1] in LORA_SUFFIXES and isinstance(module,torch.nn.Linear):
                targets.append(name)
        require(targets,'No language LoRA targets found')
        require(all('vision' not in n and 'audio' not in n and 'lm_head' not in n for n in targets),'Non-language adapter target')
        cfg=LoraConfig(r=SETTINGS['rank'],lora_alpha=SETTINGS['alpha'],lora_dropout=SETTINGS['dropout'],
                       bias='none',task_type='CAUSAL_LM',target_modules=targets)
        model=get_peft_model(model,cfg)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model.config.use_cache=False
        if hasattr(model.config,'text_config'):model.config.text_config.use_cache=False
        report['lora_targets']=targets
        for name,p in model.named_parameters():
            if p.requires_grad:
                require('.lora_' in name and '.language_model.' in name,'Unexpected trainable parameter: '+name)
                report['trainable_parameters']+=p.numel()
        require(report['trainable_parameters']>0,'No trainable LoRA weights')
        model.train()
    elif adapter:
        ac=read_json(Path(adapter)/'adapter_config.json')
        require(ac.get('base_model_name_or_path')==model_id,'Adapter belongs to another base model')
        model=PeftModel.from_pretrained(model,str(adapter),is_trainable=False)
        model.eval()
    else:model.eval()
    report['allocated_GiB']=torch.cuda.memory_allocated()/1024**3
    report['model_memory_footprint_GiB']=model.get_memory_footprint()/1024**3
    return model,report
