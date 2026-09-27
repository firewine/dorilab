import time,traceback
from run_common import *
def main():
    release,records,cfg=gate()
    save('RESUME_PROVENANCE.json',dict(started_at=now(),previous_stop_path=str(PRIOR/'FINAL_RESULT.json'),previous_stop_sha256=sha(PRIOR/'FINAL_RESULT.json'),
      initial_optimizer_steps=0,initial_example_presentations=0,approval_path=release['approval_path'],approval_sha256=release['approval_sha256'],
      release_manifest_sha256=sha(RELEASE),runtime_ready_sha256=sha(RECOVERY/'RUNTIME_READY.json'),configuration_sha256=sha(RC3/'LORA_SINGLE_CONFIG.json'),
      sealed_code_changed=False,existing_data_regenerated=False,new_approval_created=False))
    status('RC3_GPU_NO_UPDATE_VALIDATION',['runtime 복구 및 기존 승인·release 무결성 PASS'],['모델 shard/target/forward-backward 검사 중'])
    from train_once import verify_checkpoint
    shards=verify_checkpoint(SNAPSHOT)
    save('CHECKPOINT_HASHES.json',dict(model=cfg['model'],revision=cfg['revision'],snapshot=str(SNAPSHOT),shards=shards))
    import torch
    from transformers import Qwen3_5ForConditionalGeneration,set_seed
    from peft import LoraConfig,get_peft_model
    from tokenization import processor,encode,collate
    proc,env=processor();encoded={r['member_id']:encode(proc,r,cfg['max_length'])[0] for r in records}
    representatives={}
    for r in records:
      route=r['contract_route'];old=representatives.get(route)
      if old is None or len(encoded[r['member_id']]['input_ids'])>len(encoded[old['member_id']]['input_ids']):representatives[route]=r
    selected=list(representatives.values());longest=max(records,key=lambda r:len(encoded[r['member_id']]['input_ids']))
    require(longest['member_id'] in [r['member_id'] for r in selected],'longest example missing')
    save('NO_UPDATE_SELECTION.json',dict(longest_id=longest['member_id'],max_length=len(encoded[longest['member_id']]['input_ids']),
       cases=[dict(id=r['member_id'],contract=r['contract_route'],tokens=len(encoded[r['member_id']]['input_ids'])) for r in selected],selection='longest TRAIN case in each native contract; no DEV targets'))
    set_seed(cfg['seed']);torch.cuda.reset_peak_memory_stats()
    model=Qwen3_5ForConditionalGeneration.from_pretrained(SNAPSHOT,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':0})
    expected=read(RC3/'LORA_TARGET_MODULES.json')['target_modules']
    actual=sorted(n for n,m in model.named_modules() if n.startswith('model.language_model.layers.') and isinstance(m,torch.nn.Linear))
    modules=[dict(name=n,type=type(m).__module__+'.'+type(m).__qualname__,in_features=m.in_features,out_features=m.out_features) for n,m in model.named_modules() if n in expected]
    save('ACTUAL_TARGET_MODULES.json',dict(expected=expected,actual=actual,module_types_shapes=modules,names_match=actual==expected))
    require(actual==expected,'actual target module mismatch')
    for p in model.parameters():p.requires_grad=False
    model=get_peft_model(model,LoraConfig(r=cfg['rank'],lora_alpha=cfg['alpha'],lora_dropout=cfg['dropout'],target_modules=expected,bias='none',task_type='CAUSAL_LM'))
    trainables=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    require(all('lora_' in n and 'language_model.layers.' in n and not any(x in n for x in ['visual','embed_tokens','lm_head']) for n,p in trainables),'non-LoRA/base/vision/embedding/lm_head trainable')
    count=sum(p.numel() for n,p in trainables);require(count==cfg['estimated_lora_parameters'],'LoRA parameter count mismatch')
    save('TRAINABLE_PARAMETERS.json',dict(count=count,parameters=[dict(name=n,shape=list(p.shape),dtype=str(p.dtype)) for n,p in trainables],base_vision_embedding_lm_head_frozen=True))
    model.config.use_cache=False;model.config.text_config.use_cache=False
    model.enable_input_require_grads();model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.train()
    tests=[]
    for record in selected:
      model.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats();start=time.monotonic()
      batch={k:v.to('cuda') for k,v in collate([encoded[record['member_id']]],proc.tokenizer.pad_token_id,tensors=True).items()}
      with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch).loss
      require(torch.isfinite(loss).item(),'NaN/Inf no-update loss');loss.backward()
      gradients=[]
      for n,p in trainables:
        g=p.grad
        gradients.append(dict(name=n,present=g is not None,finite=bool(torch.isfinite(g).all().item()) if g is not None else None,nonzero=bool(torch.count_nonzero(g).item()) if g is not None else False))
      require(all(x['finite'] for x in gradients if x['present']),'NaN/Inf gradients')
      require(any(x['nonzero'] and '.lora_B.' in x['name'] for x in gradients),'no nonzero B gradient')
      mem=memory(torch);optim_est=count*8
      available=mem['device_total']-mem['peak_reserved']
      test=dict(id=record['member_id'],contract=record['contract_route'],loss=float(loss.detach()),elapsed_seconds=time.monotonic()-start,
        memory=mem,gradients=gradients,adam_state_bytes_estimate=optim_est,estimated_margin_bytes=available-optim_est,
        optimizer_state_memory_measured=False,optimizer_steps=0)
      append('NO_UPDATE_CASES.jsonl',test);tests.append(test)
      print('NO_UPDATE_PASS',record['member_id'],test['loss'],mem,flush=True)
      require(available>optim_est+2*1024**3,'insufficient estimated optimizer-state memory margin')
      del batch,loss
    save('GPU_VALIDATION_RECEIPT.json',dict(status='PASS',optimizer_steps=0,
      release_manifest_sha256=sha(RELEASE),training_configuration_sha256=sha(RC3/'LORA_SINGLE_CONFIG.json'),cpu_preflight_sha256=sha(RC3/'CPU_PREFLIGHT_v4.json'),trainer_sha256=sha(RC3/'train_once.py'),
      runtime_modules_match=True,trainable_parameters_lora_language_only=True,longest_sample_forward_backward_pass=True,memory_margin_including_optimizer_state_pass=True,
      memory_margin_semantics='estimate from peak reserved plus 2 FP32 Adam states; NOT proof of actual optimizer step fit. First formal step must be instrumented.',
      first_actual_optimizer_step_memory_verified=False,trainable_parameters=count,
      longest_train_id=longest['member_id'],cases=[r['member_id'] for r in selected],runtime_ready_sha256=sha(RECOVERY/'RUNTIME_READY.json'),
      validation_adapter_disposition='process exits; adapter, gradients and RNG discarded. Formal training in separate process with seed42 and freshly initialized adapter.',completed_at=now()))
    status('RC3_GPU_NO_UPDATE_PASSED',['정확한 target496/LoRA116727808 및 동결 base 검사 PASS','TRAIN 최장·계약별 4사례 forward/backward finite PASS'],['optimizer state 포함 실제 메모리는 정식 첫 step에서 확인'])
if __name__=='__main__':
    try:main()
    except Exception as e:
      save('GPU_VALIDATION_FAILURE.json',dict(status='STOPPED',error=repr(e),traceback=traceback.format_exc(),optimizer_steps=0,recorded_at=now()))
      status('RC3_GPU_VALIDATION_STOPPED',['실제 검사 및 실패 근거 보존'],[repr(e)],['GPU_VALIDATION_FAILED'])
      raise
