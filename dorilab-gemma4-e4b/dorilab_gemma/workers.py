from __future__ import annotations
import contextlib, copy, json, os, subprocess, time
from pathlib import Path
from .common import *
from .modeling import *
from .scoring import score, aggregate
SUITES=('ns10','before40','contract20')

def verify_import(root):
    m=read_json(root/'data/IMPORT_MANIFEST.json')
    require(m['settings']==SETTINGS,'Settings changed after import; use a new experiment folder')
    for rel,h in m['frozen_data'].items():require(sha(root/rel)==h,'Frozen input changed: '+rel)
    return m

def locked_model(root):
    m=read_json(root/'reports/model_lock.json')
    require(m['model']==MODEL_ID,'Wrong model lock')
    return m

def preflight(root):
    import torch
    from transformers import AutoConfig
    m=verify_import(root)
    gpu=check_gpu()
    p=root/'reports/model_lock.json'
    if p.exists():lock=locked_model(root)
    else:
        cfg=AutoConfig.from_pretrained(MODEL_ID,trust_remote_code=False)
        rev=getattr(cfg,'_commit_hash',None)
        require(isinstance(rev,str) and re.fullmatch('[0-9a-f]{40}',rev),'Cannot resolve immutable Gemma revision')
        require(cfg.model_type=='gemma4' and cfg.text_config.num_hidden_layers==42,'Unexpected Gemma E4B configuration')
        lock={'model':MODEL_ID,'revision':rev,'at_utc':now(),'settings':SETTINGS,'config':cfg.to_dict()}
        write_json(p,lock)
    processor=load_processor(MODEL_ID,lock['revision'])
    processor.save_pretrained(root/'assets/processor')
    encoded=[];stats=[]
    for row in read_jsonl(root/'data/train.jsonl'):
        enc,s=encoded_answer(processor,row['messages'],SETTINGS['max_length'])
        encoded.append(enc);stats.append(dict(id=row['id'],**s))
    # Encoding cache is for the current model/template only, not transplanted Qwen IDs.
    for suite in SUITES:
        for item in read_jsonl(root/f'data/eval_{suite}.jsonl'):
            text=prompt_text(processor,item['messages'])
            ids=tokenize_text(processor.tokenizer,text)
            require(len(ids)+SETTINGS['max_new_tokens']<=SETTINGS['max_length'],f'{suite}/{item["case_id"]}: eval input+budget > max_length')
    result={'at_utc':now(),'environment':environment(),'gpu':gpu,'model_lock_sha256':sha(p),
            'data_sha256':sha(root/'data/train.jsonl'),'rows':len(encoded),'row_stats':stats,
            'max_tokens':max(x['total_tokens'] for x in stats),
            'prompt_tokens':sum(x['prompt_tokens'] for x in stats),
            'supervised_tokens':sum(x['answer_and_end_tokens'] for x in stats),
            'label_policy':'system/user and model prefix = -100; assistant JSON and native turn-end supervised',
            'truncated':False,'processor_files':{str(x.relative_to(root)):sha(x) for x in (root/'assets/processor').rglob('*') if x.is_file()}}
    write_json(root/'reports/preflight.json',result)
    write_jsonl(root/'data/encoded_train.jsonl',encoded)
    # Keep one short and one long rendering for debugging without loading weights.
    write_json(root/'reports/mask_examples.json',[
       {'id':stats[i]['id'],'stats':stats[i],
        'masked_prompt':processor.tokenizer.decode(encoded[i]['input_ids'][:stats[i]['prompt_tokens']],skip_special_tokens=False),
        'supervised_answer':processor.tokenizer.decode(encoded[i]['input_ids'][stats[i]['prompt_tokens']:],skip_special_tokens=False)}
       for i in sorted({0,max(range(len(stats)),key=lambda n:stats[n]['total_tokens'])})])
    print('PREFLIGHT PASS:',{k:result[k] for k in ('rows','max_tokens','prompt_tokens','supervised_tokens','truncated')})

def evaluate(root,which):
    import torch
    from transformers import set_seed
    verify_import(root);lock=locked_model(root);set_seed(SETTINGS['seed'])
    adapter=None
    if which=='finetuned':
        receipt=read_json(root/'reports/training_receipt.json');adapter=root/receipt['adapter']
        for name,h in receipt['files'].items():require(sha(adapter/name)==h,'Adapter file changed: '+name)
    processor=load_processor(MODEL_ID,lock['revision'])
    model,load_report=load_model(MODEL_ID,lock['revision'],adapter=adapter)
    tok=processor.tokenizer;stops=generation_stops(processor,model.config)
    outdir=root/'reports'/which;outdir.mkdir(parents=True,exist_ok=True)
    schema=read_json(root/'data/action_schema.json')
    summary={}
    for suite in SUITES:
        dest=outdir/f'{suite}.jsonl';require(not dest.exists(),'Evaluation output already exists: '+str(dest))
        rows=[]
        for item in read_jsonl(root/f'data/eval_{suite}.jsonl'):
            text=prompt_text(processor,item['messages']);ids=tokenize_text(tok,text)
            x=torch.tensor([ids],dtype=torch.long,device='cuda');mask=torch.ones_like(x)
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
            with torch.inference_mode():
                generated=model.generate(input_ids=x,attention_mask=mask,max_new_tokens=SETTINGS['max_new_tokens'],
                    do_sample=False,eos_token_id=stops,pad_token_id=tok.pad_token_id,use_cache=True,logits_to_keep=1)
            torch.cuda.synchronize();elapsed=time.perf_counter()-start
            new=generated[0,len(ids):].tolist();terminal=next((i for i,t in enumerate(new) if t in stops),None)
            hit_limit=terminal is None and len(new)>=SETTINGS['max_new_tokens']
            content=new[:terminal] if terminal is not None else new
            raw=tok.decode(content,skip_special_tokens=False)
            s=score(item,raw,schema,hit_limit)
            row={'case_id':item['case_id'],'pair_id':item['case'].get('pair_id'),'suite':suite,
                 'model':MODEL_ID,'revision':lock['revision'],'arm':which,
                 'messages_sha256':digest(item['messages']),'rendered_prompt_sha256':digest(text),
                 'prompt_tokens':len(ids),'generated_tokens':len(new),'generation_seconds':elapsed,
                 'peak_allocated_GiB':torch.cuda.max_memory_allocated()/1024**3,
                 'raw_output':raw,'raw_with_terminal':tok.decode(new,skip_special_tokens=False),
                 'hit_generation_limit':hit_limit,'score':s,
                 'engineering_approved':False,'human_review_required':True}
            with dest.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            rows.append(row)
            print(f'{which} {suite} {len(rows):02d}: {item["case_id"]} '+('PASS' if s['strict_contract_pass'] else 'FAIL'),flush=True)
        summary[suite]=aggregate(rows)
    write_json(outdir/'summary.json',{'arm':which,'model':MODEL_ID,'revision':lock['revision'],
       'quantization':SETTINGS['quantization'],'enable_thinking':False,'suites':summary,
       'load_report':load_report,'environment':environment(),'inference_executed':True,
       'timing_note':'Generation timings include first-case warmup; not full workflow cost',
       'evaluation_status':'Existing development/regression suites; not independent holdout'})
    print(json.dumps(summary,indent=2))

def train(root):
    import torch
    from transformers import Trainer,TrainingArguments,set_seed,TrainerCallback
    verify_import(root);lock=locked_model(root);set_seed(SETTINGS['seed'])
    out=root/'runs/gemma4_e4b_repeat246_e2'
    require(not out.exists(),'Training directory exists; do not overwrite an incomplete run. Preserve it and use a fresh project or explicit retry.')
    processor=load_processor(MODEL_ID,lock['revision'])
    rows=read_jsonl(root/'data/encoded_train.jsonl')
    pf=read_json(root/'reports/preflight.json')
    require(sha(root/'data/train.jsonl')==pf['data_sha256'],'Dataset changed after tokenization')
    for rel,h in pf['processor_files'].items():require(sha(root/rel)==h,'Processor snapshot changed')
    model,report=load_model(MODEL_ID,lock['revision'],training=True)
    # Real longest-example forward/backward; no optimizer update. A failed smoke
    # cannot silently proceed to full training. The untouched base+LoRA init stays.
    model.zero_grad(set_to_none=True)
    longest=max(rows,key=lambda r:len(r['input_ids']))
    batch={k:v.to('cuda') for k,v in single_collator([longest]).items()}
    torch.cuda.reset_peak_memory_stats()
    with torch.autocast('cuda',dtype=torch.bfloat16):loss,_=selected_loss(model,batch)
    require(torch.isfinite(loss).item(),'Nonfinite smoke loss')
    loss.backward();torch.cuda.synchronize()
    grads=[(n,p.grad) for n,p in model.named_parameters() if p.requires_grad]
    require(any(g is not None and torch.isfinite(g).all().item() and g.abs().sum().item()>0 for n,g in grads),'No nonzero finite LoRA gradients')
    require(all(g is None or torch.isfinite(g).all().item() for n,g in grads),'Nonfinite LoRA gradient')
    smoke={'loss':float(loss.detach()),'longest_tokens':len(longest['input_ids']),
           'finite_nonzero_adapter_gradient':True,'optimizer_steps':0,
           'peak_allocated_GiB':torch.cuda.max_memory_allocated()/1024**3}
    # Released references are important with 16GB GPUs.
    del grads,loss,_,batch
    model.zero_grad(set_to_none=True);torch.cuda.empty_cache();set_seed(SETTINGS['seed'])
    out.mkdir(parents=True)
    write_json(out/'RUN_MANIFEST.json',{'version':VERSION,'settings':SETTINGS,'model_revision':lock['revision'],
       'train_data_sha256':sha(root/'data/train.jsonl'),'tokenized_data_sha256':sha(root/'data/encoded_train.jsonl'),
       'import_manifest_sha256':sha(root/'data/IMPORT_MANIFEST.json'),'model_report':report,
       'smoke':smoke,'environment':environment(),'resume_from_qwen_adapter':False,
       'large_embedding_policy':'Frozen BF16; no vocabulary expansion; no FP32 embedding copy',
       'loss_policy':'Only supervised next-token positions have vocabulary logits; full input context is retained'})
    class ResponseTrainer(Trainer):
        def compute_loss(self,model,inputs,return_outputs=False,num_items_in_batch=None):
            loss,outputs=selected_loss(model,inputs)
            return (loss,outputs) if return_outputs else loss
    class FiniteLoss(TrainerCallback):
        def on_log(self,args,state,control,logs=None,**kw):
            if logs and 'loss' in logs:
                import math
                require(math.isfinite(float(logs['loss'])),'Nonfinite training loss')
    args=TrainingArguments(output_dir=str(out),num_train_epochs=SETTINGS['epochs'],
        per_device_train_batch_size=1,gradient_accumulation_steps=SETTINGS['gradient_accumulation_steps'],
        learning_rate=SETTINGS['learning_rate'],warmup_steps=4,lr_scheduler_type='linear',
        optim='adamw_torch',weight_decay=0.0,max_grad_norm=1.0,bf16=True,fp16=False,
        logging_steps=5,save_strategy='no',report_to='none',remove_unused_columns=False,
        dataloader_num_workers=0,dataloader_pin_memory=False,seed=42,data_seed=42,
        gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
    trainer=ResponseTrainer(model=model,args=args,train_dataset=rows,data_collator=single_collator,
                            processing_class=processor.tokenizer,callbacks=[FiniteLoss()])
    trainer.model_accepts_loss_kwargs=False
    result=trainer.train()
    # Native adapter only. Never merge into quantized weights here.
    model.save_pretrained(out,safe_serialization=True)
    processor.save_pretrained(out)
    write_json(out/'TRAIN_RESULT.json',result.metrics)
    require((out/'adapter_model.safetensors').is_file(),'Adapter weights not saved')
    ac=read_json(out/'adapter_config.json')
    require(ac['base_model_name_or_path']==MODEL_ID and ac['r']==SETTINGS['rank'],'Wrong saved adapter identity')
    write_json(root/'reports/training_receipt.json',{'adapter':str(out.relative_to(root)),
        'files':{n:sha(out/n) for n in ('adapter_model.safetensors','adapter_config.json','RUN_MANIFEST.json','TRAIN_RESULT.json')},
        'smoke':smoke,'metrics':result.metrics,'at_utc':now()})
    print('GEMMA TRAINING SAVED:',out,flush=True)

def compare(root):
    imported=verify_import(root)
    before=read_json(root/'reports/baseline/summary.json')
    after=read_json(root/'reports/finetuned/summary.json')
    detail=[];models={'qwen2b_historical':imported['baseline_2b_rescored'],
                     'gemma4_e4b_before':before['suites'],'gemma4_e4b_after':after['suites']}
    for suite in SUITES:
        a=index(read_jsonl(root/f'reports/baseline/{suite}.jsonl'));b=index(read_jsonl(root/f'reports/finetuned/{suite}.jsonl'))
        require(set(a)==set(b),'Evaluation set differs across Gemma stages')
        for cid in a:
            require(a[cid]['messages_sha256']==b[cid]['messages_sha256'],'Evaluation content changed')
            detail.append({'case_id':cid,'suite':suite,'before':a[cid],'after':b[cid],
               'gain':not a[cid]['score']['strict_contract_pass'] and b[cid]['score']['strict_contract_pass'],
               'loss':a[cid]['score']['strict_contract_pass'] and not b[cid]['score']['strict_contract_pass']})
    obj={'version':VERSION,'at_utc':now(),'models':models,'settings':SETTINGS,
         'gain':sum(x['gain'] for x in detail),'loss':sum(x['loss'] for x in detail),
         'inference_executed':True,'training_executed':True,
         'limits':['Development/regression data already inspected, not an untouched holdout.',
                   'Qwen historical BF16 vs Gemma NF4 is a model-family+precision comparison, not capacity-only evidence.',
                   'Same message contents, but different tokenizer/native chat template/LoRA target geometry.',
                   '12/40/24 cases are partly related; do not pool into independent engineering tests.',
                   'Scope gate behavior is inherited in NS10 frozen inputs, not newly validated extraction.',
                   'No automatic deployment or engineering approval.']}
    write_json(root/'reports/comparison.json',obj);write_jsonl(root/'reports/comparison_cases.jsonl',detail)
    lines=['# Gemma 4 E4B — 학습 전후 및 기존 2B 비교','',
       '모델 자체는 새로 학습했고, 기존 작업 프롬프트·데이터는 재사용했습니다. 자동 승격/공학 승인 아님.','',
       '|평가|2B 기존|Gemma 학습 전|Gemma 학습 후|','|---|---:|---:|---:|']
    for suite in SUITES:
        vals=[f"{models[k][suite]['strict_contract_pass']}/{models[k][suite]['cases']}" for k in models]
        lines.append('|'+suite+' 전체 계약|'+'|'.join(vals)+'|')
    lines+=['','## 상세 집계','```json',json.dumps(models,ensure_ascii=False,indent=2),'```','',
        '학습 전/후는 같은 NF4 로딩·no-thinking·greedy 조건입니다. 기존 Qwen과는 모델 계열·토크나이저·정밀도가 달라 순수한 크기 비교가 아닙니다.',
        '마지막 모델이 항상 더 좋다는 보장은 없습니다. action/근거/거짓 수용/회귀 성능을 함께 보고 채택합니다.',
        'baseline/ 및 finetuned/는 24+40+20건의 실제 원출력을 포함합니다.']
    (root/'reports/RESULTS_KO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('COMPLETE: reports/RESULTS_KO.md and reports/comparison.json')
