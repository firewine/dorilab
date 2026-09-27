"""Generate once from frozen system/user inputs only; never reads gold targets."""
import argparse,time,traceback
from run_common import *
def main(kind):
    release,records,cfg=gate()
    require(read(RUN/'GPU_VALIDATION_RECEIPT.json')['status']=='PASS','GPU validation missing')
    plan=read(RUN/'EVALUATION_PLAN.json')
    require(sha(RUN/'EVALUATION_INPUTS.jsonl')==plan['input_file_sha256'],'eval input changed')
    inputs=rows(RUN/'EVALUATION_INPUTS.jsonl');tokens={r['id']:r for r in read(RUN/'EVALUATION_TOKEN_BINDINGS.json')}
    outfile=RUN/(kind+'_RAW.jsonl');require(not outfile.exists(),'raw output exists; no regeneration')
    import torch
    from transformers import Qwen3_5ForConditionalGeneration,set_seed
    from tokenization import processor,inference
    from train_once import verify_checkpoint
    verify_checkpoint(SNAPSHOT);proc,env=processor();set_seed(cfg['seed'])
    model=Qwen3_5ForConditionalGeneration.from_pretrained(SNAPSHOT,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':0})
    if kind=='lora':
        from peft import PeftModel
        receipt=read(RUN/'ADAPTER_SAVED.json')
        for path,h in receipt['file_sha256'].items():require(sha(path)==h,'adapter changed')
        model=PeftModel.from_pretrained(model,RUN/'training/adapter',is_trainable=False)
        require(not any(p.requires_grad for p in model.parameters()),'reloaded inference model trainable')
        save('ADAPTER_RELOADED.json',dict(status='PASS',source=str(RUN/'training/adapter'),adapter_receipt_sha256=sha(RUN/'ADAPTER_SAVED.json'),new_process=True,loaded_at=now()))
    model.eval();torch.cuda.reset_peak_memory_stats()
    generation=dict(max_new_tokens=cfg['comparison']['max_new_tokens'],do_sample=False,use_cache=True,
        pad_token_id=proc.tokenizer.pad_token_id,eos_token_id=proc.tokenizer.convert_tokens_to_ids('<|im_end|>'))
    save(kind+'_INFERENCE_RUNTIME.json',dict(model=cfg['model'],revision=cfg['revision'],runtime=env,generation=generation,thinking=False,
        plan_sha256=sha(RUN/'EVALUATION_PLAN.json'),code_sha256=sha(__file__),input_sha256=plan['input_file_sha256'],started_at=now()))
    status('RC3_'+kind.upper()+'_EVALUATION_RUNNING',['동결 입력·token hash 검사','동일 revision과 native contract 사용'],['출력 생성 중; 채점 전'],steps=104 if kind=='lora' else 0)
    with outfile.open('x') as f:
      for idx,row in enumerate(inputs):
        rendered,ids=inference(proc,row['messages']);require(digest(ids)==tokens[row['id']]['token_ids_sha256'],'inference token mismatch')
        tensor=torch.tensor([ids],dtype=torch.long,device='cuda');start=time.monotonic()
        with torch.inference_mode():
          result=model.generate(input_ids=tensor,attention_mask=torch.ones_like(tensor),**generation)
        outids=result[0,len(ids):].tolist();raw=proc.tokenizer.decode(outids,skip_special_tokens=False)
        # Preserve both raw (with terminator) and ordinary tokenizer decode, never repair text.
        text=proc.tokenizer.decode(outids,skip_special_tokens=True)
        obj=dict(id=row['id'],cohort=row['cohort'],contract_route=row['contract_route'],input_sha256=digest(row['messages']),
            prompt_token_ids_sha256=digest(ids),generated_token_ids=outids,raw_text=raw,text=text,
            output_text_sha256=hashlib.sha256(raw.encode()).hexdigest(),generated_tokens=len(outids),
            ended_with_native_terminator=bool(outids and outids[-1]==generation['eos_token_id']),
            elapsed_seconds=time.monotonic()-start,recorded_at=now())
        f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        print(kind,idx+1,len(inputs),row['id'],len(outids),flush=True)
        del tensor,result
    save(kind+'_RAW_SEALED.json',dict(status='COMPLETE_UNSCORED',raw_path=str(outfile),raw_sha256=sha(outfile),count=len(inputs),
        memory=memory(torch),completed_at=now(),output_repaired=False,regeneration_count=0))
    status('RC3_'+kind.upper()+'_RAW_SAVED',['원문 출력과 token 및 hash 보존 완료'],['채점 미실행'],steps=104 if kind=='lora' else 0)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['base','lora']);a=p.parse_args()
    try:main(a.kind)
    except Exception as e:
      save(a.kind+'_INFERENCE_FAILURE.json',dict(error=repr(e),traceback=traceback.format_exc(),recorded_at=now(),raw_outputs_preserved=True,automatic_regeneration=False))
      status('RC3_INFERENCE_STOPPED',['실패 및 원문 출력 보존'],[repr(e)],['INFERENCE_FAILED'],104 if a.kind=='lora' else 0)
      raise
