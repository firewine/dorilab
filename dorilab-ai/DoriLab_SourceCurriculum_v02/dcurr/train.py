"""Qwen3.5 text-only LoRA with explicit assistant labels and immutable run directories.
GPU execution must be validated locally with --max-steps 5 first.
"""
import argparse,math,json,dataclasses
from pathlib import Path
from .common import ROOT,load_jsonl,sha256,write_json,collate_rows
from .model_io import DEFAULT_MODEL,load_processor,encode_record,load_model,environment,stop_id

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-length',type=int,default=2048);p.add_argument('--max-steps',type=int,default=-1)
    p.add_argument('--epochs',type=float,default=1.0);p.add_argument('--lr',type=float,default=5e-5);p.add_argument('--rank',type=int,default=16)
    p.add_argument('--model',default=DEFAULT_MODEL);p.add_argument('--revision');a=p.parse_args()
    if a.out.exists():raise SystemExit('Output exists. Use a new run directory; no overwrite or implicit resume.')
    mf=a.data.with_suffix('.manifest.json')
    if not mf.exists():raise SystemExit('Run dcurr.prepare first; data manifest missing')
    manifest=json.loads(mf.read_text())
    if manifest['data_sha256']!=sha256(a.data):raise SystemExit('Training data hash changed')
    if manifest['prompt_file_sha256']!=sha256(ROOT/'dcurr/prompts.py') or manifest['legacy_prompt_sha256']!=sha256(ROOT/'dcurr/prompts_legacy.py'):raise SystemExit('Prompt changed since build. Rebuild with a new version.')
    import torch
    from transformers import Trainer,TrainingArguments,set_seed
    from peft import LoraConfig,get_peft_model
    set_seed(42)
    processor=load_processor(a.model,a.revision);rows=load_jsonl(a.data)
    encoded=[];stats=[]
    for row in rows:
        e,st=encode_record(processor,row,a.max_length);encoded.append(e);stats.append(st)
    model=load_model(a.model,a.revision,inference=False)
    targets=[name for name,mod in model.named_modules() if name.startswith('model.language_model.layers.') and isinstance(mod,torch.nn.Linear)]
    if not targets:raise RuntimeError('No language Linear modules found; inspect actual model structure')
    for param in model.parameters():param.requires_grad=False
    cfg=LoraConfig(r=a.rank,lora_alpha=2*a.rank,lora_dropout=.05,target_modules=targets,bias='none',task_type='CAUSAL_LM')
    model=get_peft_model(model,cfg)
    bad=[name for name,p0 in model.named_parameters() if p0.requires_grad and ('lora_' not in name or 'visual' in name or 'lm_head' in name or 'language_model' not in name)]
    if bad:raise RuntimeError('Unexpected trainable parameters: '+str(bad[:10]))
    model.config.use_cache=False
    if hasattr(model.config,'text_config'):model.config.text_config.use_cache=False
    model.generation_config.eos_token_id=stop_id(processor)
    model.print_trainable_parameters();print('Vision/non-LoRA trainable parameters: 0')
    print('Target Linear layers:',len(targets))
    steps=a.max_steps if a.max_steps>0 else max(1,math.ceil(len(encoded)/4)*math.ceil(a.epochs))
    kwargs=dict(output_dir=str(a.out),per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=a.lr,num_train_epochs=a.epochs,max_steps=a.max_steps,warmup_steps=min(4,max(1,math.ceil(steps*.05))),weight_decay=.01,bf16=True,gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False},logging_steps=1 if a.max_steps>0 else 5,save_strategy='no' if a.max_steps>0 else 'epoch',save_total_limit=2,report_to='none',seed=42,remove_unused_columns=False,optim='adamw_torch',dataloader_num_workers=0)
    supported={f.name for f in dataclasses.fields(TrainingArguments)}
    unsupported=set(kwargs)-supported
    if unsupported:raise RuntimeError('Unsupported TrainingArguments in current environment: '+str(unsupported)+'. Preserve environment and inspect arguments.')
    args=TrainingArguments(**kwargs)
    tok=processor.tokenizer;pad=tok.pad_token_id
    if pad is None:pad=stop_id(processor)
    trainer=Trainer(model=model,args=args,train_dataset=encoded,data_collator=lambda rs:collate_rows(rs,pad),processing_class=tok)
    a.out.mkdir(parents=True,exist_ok=True)
    run={'environment':environment(),'base_model':a.model,'base_revision_requested':a.revision,'base_revision_resolved':getattr(model.config,'_commit_hash',None),'data_manifest':manifest,'encoding':'explicit-prompt-mask-v0.2','encoding_module_sha256':sha256(ROOT/'dcurr/model_io.py'),'prompt_file_sha256':sha256(ROOT/'dcurr/prompts.py'),'legacy_prompt_file_sha256':sha256(ROOT/'dcurr/prompts_legacy.py'),'stop_token_id':stop_id(processor),'max_length':a.max_length,'rank':a.rank,'lr':a.lr,'epochs_requested':a.epochs,'max_steps':a.max_steps,'targets':targets,'token_counts':stats,'test_status':'GPU runtime measured by the user, not by the package producer'}
    write_json(a.out/'RUN_MANIFEST.json',run,exclusive=True)
    result=trainer.train()
    trainer.save_model(str(a.out));processor.save_pretrained(str(a.out))
    write_json(a.out/'TRAIN_RESULT.json',result.metrics,exclusive=True)
    print('Saved:',a.out)
if __name__=='__main__':main()
