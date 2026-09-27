"""Execute the SEALED trainer with observational Trainer callbacks only.

No optimizer, schedule, dataloader, loss, update, or sealed-code implementation is
replaced. Forward hooks and the additional callback audit actual behavior.
"""
import collections,math,traceback
from run_common import *
COUNTS=dict(microbatches=0,presentations=0,optimizer_steps=0,optimizer_step_attempted=0)
def main():
    release,records,cfg=gate()
    require(read(RUN/'base_RAW_SEALED.json')['status']=='COMPLETE_UNSCORED','frozen base output missing')
    from train_once import check_training_entry,run
    check_training_entry(RELEASE,RUN/'GPU_VALIDATION_RECEIPT.json')
    import torch,transformers.trainer
    from transformers import TrainerCallback
    from tokenization import processor,encode
    proc,_=processor();lookup=collections.defaultdict(list)
    for r in records:lookup[digest(encode(proc,r,cfg['max_length'])[0]['input_ids'])].append(r['member_id'])
    expected=collections.Counter({h:len(ids) for h,ids in lookup.items()})
    class Audit(TrainerCallback):
      def __init__(self):self.epoch_seen=collections.Counter();self.epoch_micro=0;self.groups=[];self.group_micro=0;self.handles=[]
      def on_train_begin(self,args,state,control,model=None,**kwargs):
        require(state.global_step==0,'must start fresh at step0')
        bs=[p for n,p in model.named_parameters() if p.requires_grad and '.lora_B.' in n]
        require(all(torch.count_nonzero(p).item()==0 for p in bs),'initial B not zero; validation/trained adapter reused')
        save('FORMAL_INITIALIZATION.json',dict(seed=args.seed,data_seed=args.data_seed,global_step=state.global_step,
            clean_initial_adapter_B_zero=True,separate_process_from_validation=True,validation_rng_gradients_adapter_reused=False,
            sealed_trainer_sha256=sha(RC3/'train_once.py'),callback_source_sha256=sha(__file__),started_at=now(),
            approved_args=dict(rank=cfg['rank'],alpha=cfg['alpha'],dropout=cfg['dropout'],lr=args.learning_rate,epochs=args.num_train_epochs,
               batch=args.per_device_train_batch_size,accumulation=args.gradient_accumulation_steps,optim=str(args.optim),
               warmup=args.warmup_steps,max_steps=args.max_steps,drop_last=args.dataloader_drop_last)))
        def before(module,inputs,kwargs):
          if not module.training:return
          ids=kwargs.get('input_ids');require(ids is not None,'missing train input IDs')
          count=ids.shape[0];require(count==1,'microbatch configuration changed')
          for tensor in ids:
            h=digest(tensor.detach().cpu().tolist());require(h in lookup,'unapproved training input')
            self.epoch_seen[h]+=1
            append('TRAIN_PRESENTATIONS.jsonl',dict(microbatch=COUNTS['microbatches']+1,epoch_index=int(state.epoch or 0),
                matching_member_ids=lookup[h],token_ids_sha256=h,tokens=tensor.numel()))
          COUNTS['microbatches']+=1;COUNTS['presentations']+=count;self.epoch_micro+=1;self.group_micro+=1
        def after(module,inputs,kwargs,output):
          if module.training:
            require(output.loss is not None and torch.isfinite(output.loss).item(),'NaN/Inf formal forward loss')
        self.handles=[model.register_forward_pre_hook(before,with_kwargs=True),model.register_forward_hook(after,with_kwargs=True)]
        torch.cuda.reset_peak_memory_stats()
      def on_epoch_begin(self,args,state,control,**kwargs):
        self.epoch_seen.clear();self.epoch_micro=0;self.groups=[];self.group_micro=0
      def on_pre_optimizer_step(self,args,state,control,model=None,optimizer=None,**kwargs):
        COUNTS['optimizer_step_attempted']=state.global_step+1
        grads=[p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
        require(grads and torch.isfinite(torch.stack([g.norm() for g in grads])).all().item(),'NaN/Inf formal gradient')
      def on_optimizer_step(self,args,state,control,optimizer=None,**kwargs):
        COUNTS['optimizer_steps']=state.global_step+1
        opt=getattr(optimizer,'optimizer',optimizer)
        state_bytes=sum(v.numel()*v.element_size() for s in opt.state.values() for v in s.values() if torch.is_tensor(v))
        require(state_bytes>0,'Adam optimizer states absent after step')
        info=dict(step=COUNTS['optimizer_steps'],microbatches_in_update=self.group_micro,total_presentations=COUNTS['presentations'],
                  optimizer_state_tensor_bytes=state_bytes,memory=memory(torch),recorded_at=now())
        require(all(torch.isfinite(v).all().item() for s in opt.state.values() for v in s.values() if torch.is_tensor(v)),'NaN/Inf optimizer state')
        append('OPTIMIZER_STEPS.jsonl',info);self.groups.append(self.group_micro);self.group_micro=0
        if COUNTS['optimizer_steps']==1:
          save('FIRST_OPTIMIZER_STEP_MEMORY.json',dict(status='PASS_ACTUAL_STEP_AND_ADAM_STATES',**info))
          status('RC3_FIRST_OPTIMIZER_STEP_PASSED',['정식 첫 optimizer step 및 실제 Adam state 메모리 검증 PASS'],['승인104 steps 중 1 완료'],steps=1)
      def on_epoch_end(self,args,state,control,**kwargs):
        require(self.epoch_micro==206 and self.epoch_seen==expected,'epoch membership/presentation count mismatch')
        require(self.groups==[4]*51+[2],'epoch accumulation remainder mismatch')
        append('EPOCH_AUDIT.jsonl',dict(epoch=state.epoch,global_step=state.global_step,microbatches=self.epoch_micro,
               member_multiplicity_verified=True,update_group_sizes=self.groups,total_presentations=COUNTS['presentations']))
      def on_log(self,args,state,control,logs=None,**kwargs):
        logs=logs or {};require(all(math.isfinite(v) for v in logs.values() if isinstance(v,float)),'nonfinite logged metric')
        append('TRAIN_LOGS.jsonl',dict(step=state.global_step,epoch=state.epoch,logs=logs,recorded_at=now()))
      def on_train_end(self,args,state,control,**kwargs):
        require(state.global_step==104 and COUNTS['presentations']==412,'final step/presentation mismatch')
        for h in self.handles:h.remove()
    # Official extension point used by Trainer.__init__, keeping all existing callbacks.
    transformers.trainer.DEFAULT_CALLBACKS = list(transformers.trainer.DEFAULT_CALLBACKS)+[Audit]
    status('RC3_SINGLE_LORA_TRAINING',['기존 승인 gate와 no-update receipt 재검증','base 원문 봉인 완료','봉인 학습기에 관측 callback 추가'],['정식 단일 학습 시작; 첫 optimizer 메모리 아직 미검증'])
    run(RELEASE,RUN/'GPU_VALIDATION_RECEIPT.json',SNAPSHOT,RUN/'training')
    require(COUNTS['optimizer_steps']==104 and COUNTS['presentations']==412,'actual training counts differ')
    files={str(p):sha(p) for p in sorted((RUN/'training/adapter').rglob('*')) if p.is_file()}
    require(any(p.endswith('adapter_model.safetensors') for p in files),'saved adapter missing')
    save('ADAPTER_SAVED.json',dict(status='SAVED',file_sha256=files,actual_counts=COUNTS,
        training_result=read(RUN/'training/TRAIN_RESULT.json'),memory=memory(torch),saved_at=now()))
    status('RC3_LORA_SAVED',['104 optimizer steps·412 presentations 확인','epoch별 206행 및 잔여 누적2 처리 확인','adapter 저장 및 hash 기록'],['별도 프로세스 reload 평가 대기'],steps=104)
if __name__=='__main__':
    try:main()
    except Exception as e:
      save('TRAINING_FAILURE.json',dict(status='STOPPED',error=repr(e),traceback=traceback.format_exc(),actual_counts=COUNTS,recorded_at=now(),automatic_retry=False))
      status('RC3_TRAINING_STOPPED',['실제 실행 기록 보존'],[repr(e)],['TRAINING_FAILED'],COUNTS['optimizer_steps'])
      raise
