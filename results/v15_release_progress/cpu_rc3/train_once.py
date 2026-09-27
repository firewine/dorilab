"""Guarded single-config trainer. Never execute this during CPU preparation."""
import argparse,json,os
from pathlib import Path
from common import *
from exporter import require,verify_training_release

def check_training_entry(release_path,gpu_receipt=None):
 release,records=verify_training_release(release_path)
 require(gpu_receipt is not None,'GPU memory/module validation receipt missing')
 gpu=read(gpu_receipt)
 require(gpu.get('status')=='PASS' and gpu.get('optimizer_steps')==0,'GPU receipt must be no-update validation')
 for k,h in {'release_manifest_sha256':sha(release_path),'training_configuration_sha256':sha(OUT/'LORA_SINGLE_CONFIG.json'),'cpu_preflight_sha256':sha(PREFLIGHT),'trainer_sha256':sha(OUT/'train_once.py')}.items():require(gpu.get(k)==h,'GPU validation binding changed: '+k)
 for key in ['runtime_modules_match','trainable_parameters_lora_language_only','longest_sample_forward_backward_pass','memory_margin_including_optimizer_state_pass']:require(gpu.get(key) is True,'GPU validation missing '+key)
 return release,records

def verify_checkpoint(snapshot):
 snapshot=Path(snapshot)
 require(sha(snapshot/'config.json')==sha(ASSETS/'config.json'),'checkpoint config mismatch')
 oldindex=ROOT/'results/source_review_v13_qwen27/model_lock_assets/model.safetensors.index.json'
 require(sha(snapshot/'model.safetensors.index.json')==sha(oldindex),'checkpoint index mismatch')
 shards=set(read(oldindex)['weight_map'].values());receipts={}
 for name in shards:
  p=ROOT/'experiments/source_review_direct_v14/gpu_batch_v1/audit'/('verified_'+name+'.json')
  r=read(p);require('/'+REVISION+'/' in r['source'],'shard receipt wrong revision')
  require((snapshot/name).stat().st_size==r['bytes'] and sha(snapshot/name)==r['sha256'],'checkpoint shard mismatch: '+name);receipts[name]=r['sha256']
 return receipts

def run(release_path,gpu_receipt,snapshot,output):
 # All release, current input/gold and receipt checks occur BEFORE torch/model imports.
 release,records=check_training_entry(release_path,gpu_receipt)
 cfg=read(OUT/'LORA_SINGLE_CONFIG.json');output=Path(output);require(not output.exists(),'output exists; no implicit resume')
 require(int(os.environ.get('WORLD_SIZE','1'))==1,'fixed configuration is single GPU')
 checkpoint=verify_checkpoint(snapshot)
 import torch
 from transformers import Qwen3_5ForConditionalGeneration,Trainer,TrainingArguments,set_seed
 from peft import LoraConfig,get_peft_model
 from tokenization import processor,encode,collate
 require(torch.cuda.is_available() and torch.cuda.is_bf16_supported(),'CUDA BF16 required')
 proc,env=processor();require(env['transformers_direct_url'].get('vcs_info',{}).get('commit_id')==read(ASSET_ROOT/'ASSET_ALLOWLIST.json')['transformers_commit'],'runtime Transformers commit changed')
 set_seed(cfg['seed']);encoded=[]
 for r in records:encoded.append(encode(proc,r,cfg['max_length'])[0])
 model=Qwen3_5ForConditionalGeneration.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':0})
 expected=read(OUT/'LORA_TARGET_MODULES.json')['target_modules']
 actual=sorted(n for n,m in model.named_modules() if n.startswith('model.language_model.layers.') and isinstance(m,torch.nn.Linear))
 require(actual==expected,'runtime Linear target names differ from approved indexed list')
 for p in model.parameters():p.requires_grad=False
 model=get_peft_model(model,LoraConfig(r=cfg['rank'],lora_alpha=cfg['alpha'],lora_dropout=cfg['dropout'],target_modules=expected,bias='none',task_type='CAUSAL_LM'))
 trainables=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
 require(all('lora_' in n and 'language_model.layers.' in n and 'visual' not in n and 'lm_head' not in n for n,p in trainables),'non-language/non-LoRA parameter trainable')
 require(sum(p.numel() for n,p in trainables)==cfg['estimated_lora_parameters'],'adapter parameter count differs')
 model.config.use_cache=False;model.config.text_config.use_cache=False
 if hasattr(model,'enable_input_require_grads'):model.enable_input_require_grads()
 output.mkdir(parents=True,exist_ok=False)
 args=TrainingArguments(output_dir=str(output),per_device_train_batch_size=cfg['per_device_train_batch_size'],gradient_accumulation_steps=cfg['gradient_accumulation_steps'],num_train_epochs=cfg['epochs'],max_steps=-1,learning_rate=cfg['learning_rate'],
  warmup_steps=cfg['warmup_steps'],lr_scheduler_type=cfg['scheduler'],weight_decay=cfg['weight_decay'],adam_beta1=cfg['adam_beta1'],adam_beta2=cfg['adam_beta2'],adam_epsilon=cfg['adam_epsilon'],max_grad_norm=cfg['max_grad_norm'],optim=cfg['optimizer'],bf16=True,seed=cfg['seed'],data_seed=cfg['data_seed'],
  gradient_checkpointing=cfg['gradient_checkpointing'],gradient_checkpointing_kwargs={'use_reentrant':cfg['gradient_checkpointing_use_reentrant']},dataloader_drop_last=cfg['dataloader_drop_last'],dataloader_num_workers=0,remove_unused_columns=False,save_strategy='no',logging_steps=1,report_to='none')
 pad=proc.tokenizer.pad_token_id
 if pad is None:pad=proc.tokenizer.convert_tokens_to_ids('<|im_end|>')
 trainer=Trainer(model=model,args=args,train_dataset=encoded,data_collator=lambda rs:collate(rs,pad,tensors=True),processing_class=proc.tokenizer)
 with (output/'RUN_INPUTS.json').open('x') as f:json.dump({'release':release,'configuration':cfg,'checkpoint_shards':checkpoint,'gpu_validation':read(gpu_receipt),'training_started_at':now()},f,ensure_ascii=False,indent=2)
 result=trainer.train(resume_from_checkpoint=None)
 require(trainer.state.global_step==cfg['total_optimizer_steps'],'unexpected optimizer step count; do not promote adapter')
 trainer.save_model(str(output/'adapter'));proc.save_pretrained(output/'adapter')
 with (output/'TRAIN_RESULT.json').open('x') as f:json.dump({'metrics':result.metrics,'optimizer_steps':trainer.state.global_step,'engineering_approval':False},f,indent=2)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True,type=Path);p.add_argument('--gpu-validation',type=Path);p.add_argument('--snapshot',type=Path);p.add_argument('--output',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:check_training_entry(a.release,a.gpu_validation);print('release checks passed; no training requested')
 else:
  require(a.snapshot and a.output,'snapshot and new output required');run(a.release,a.gpu_validation,a.snapshot,a.output)
