"""CPU token measurements for NOT_RELEASED previews. Never loads model weights."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
from common import *
from exporter import load_candidates,require
from tokenization import processor,encode,inference,collate

def main():
 manifest,records=load_candidates();proc,environment=processor();encoded=[];stats=[]
 for r in records:
  value,stat=encode(proc,r,4096);encoded.append(value);stat['contract_route']=r['contract_route'];stats.append(stat)
 tok=proc.tokenizer;pad=tok.pad_token_id if tok.pad_token_id is not None else tok.convert_tokens_to_ids('<|im_end|>')
 shortest=min(encoded,key=lambda x:len(x['input_ids']));longest=max(encoded,key=lambda x:len(x['input_ids']))
 batch=collate([shortest,longest],pad)
 for i,row in enumerate([shortest,longest]):
  end=len(row['input_ids']);require(all(v==-100 for v in batch['labels'][i][end:]),'padding loss leak');require(all(v==0 for v in batch['attention_mask'][i][end:]),'padding attention leak')
 dev=[]
 for r in rows(RC2/'dev16/MODEL_INPUT_PREVIEWS.jsonl'):
  rendered,ids=inference(proc,r['messages']);require(len(ids)+384<=4096,'DEV prompt + budget exceeds fixed length')
  dev.append({'case_id':r['case_id'],'prompt_tokens':len(ids),'reserved_with_384':len(ids)+384,'token_ids_sha256':digest(ids),'rendered_native_sha256':digest(rendered)})
 # Test one below the longest actual length; rejection must be explicit.
 try:encode(proc,records[max(range(len(stats)),key=lambda i:stats[i]['total_tokens'])],max(s['total_tokens'] for s in stats)-1)
 except ValueError:truncation_rejected=True
 else:truncation_rejected=False
 require(truncation_rejected,'oversized sample silently accepted')
 paths=[OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json',OUT/'NOT_RELEASED_MESSAGE_PREVIEWS.jsonl',OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json',OUT/'exporter.py',OUT/'tokenization.py',OUT/'analysis_contract.py',OUT/'run_preflight.py',OUT/'common.py',OUT/'train_once.py']
 report={'created_at_utc':now(),'status':'PASS','training_rows':len(records),'dev_rows':len(dev),'fixed_max_length':4096,'train_max_tokens':max(s['total_tokens'] for s in stats),'train_min_tokens':min(s['total_tokens'] for s in stats),'dev_max_prompt_tokens':max(s['prompt_tokens'] for s in dev),'dev_max_reserved_tokens':max(s['reserved_with_384'] for s in dev),'environment':environment,'input_file_sha256':{**{str(p):sha(p) for p in paths},**environment['asset_sha256']},'training_token_stats':stats,'dev_inference_token_stats':dev,'native_template_equivalence':True,'system_user_and_assistant_header_masked':True,'assistant_target_and_im_end_supervised':True,'native_trailing_newline_masked':True,'padding_mask_pass':True,'no_silent_truncation_test_pass':truncation_rejected,'pad_token_id':pad,'model_weights_loaded':False,'gpu_execution':False,'sft_export_created':False}
 put(PREFLIGHT.name,report)
 status('RC3_EXPORTER_CPU_PREFLIGHT_COMPLETE',[f'NOT_RELEASED206행 tokenizer 검증: 최대 {report["train_max_tokens"]} tokens',f'DEV16 prompt 최대 {report["dev_max_prompt_tokens"]}; 응답384 포함 최대 {report["dev_max_reserved_tokens"]}','native 경계·assistant/EOS loss·padding·no-truncation PASS'],['GPU 메모리/실행 검증 미실행','release 승인 전 실제 SFT export 차단'],[PREFLIGHT.name,'exporter.py','tokenization.py'],['승인 묶음·단일 학습 설정','실행 gate 및 회귀 테스트'],['B03','GPU_MEMORY_UNVERIFIED'])
 print(json.dumps({k:v for k,v in report.items() if k not in ('environment','input_file_sha256','training_token_stats','dev_inference_token_stats')},ensure_ascii=False))
if __name__=='__main__':main()
