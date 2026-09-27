"""Native Qwen rendering; explicit response-only labels, no truncation, no GPU work."""
import importlib.metadata as metadata
from common import *
from exporter import require,inference_messages

def processor():
 allow=read(ASSET_ROOT/'ASSET_ALLOWLIST.json')
 for name,record in allow['files'].items():require(sha(ASSETS/name)==record['sha256'],'tokenizer asset changed: '+name)
 from transformers import AutoProcessor
 proc=AutoProcessor.from_pretrained(ASSETS,local_files_only=True,trust_remote_code=False)
 require(proc.chat_template==(ASSETS/'chat_template.jinja').read_text(),'native template differs')
 return proc,{'asset_sha256':{str(ASSETS/name):v['sha256'] for name,v in allow['files'].items()},'transformers':metadata.version('transformers'),'tokenizers':metadata.version('tokenizers'),'torch':metadata.version('torch'),'transformers_direct_url':json.loads(metadata.distribution('transformers').read_text('direct_url.json') or '{}')}

def inference(proc,messages):
 messages=inference_messages({'messages':messages})
 rendered=proc.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
 ids=proc.tokenizer(rendered,add_special_tokens=False,truncation=False)['input_ids']
 direct=proc.apply_chat_template(messages,tokenize=True,return_dict=True,add_generation_prompt=True,enable_thinking=False)['input_ids']
 if direct and isinstance(direct[0],list):
  require(len(direct)==1,'unexpected multi-example native batch')
  direct=direct[0]
 require(ids==direct,'native direct tokenization mismatch')
 return rendered,ids

def encode(proc,record,max_length):
 messages=record['messages'];prompt,pids=inference(proc,messages[:-1]);answer=messages[-1]['content'].strip()
 full=proc.apply_chat_template(messages,tokenize=False,add_generation_prompt=False,enable_thinking=False)
 require(full==prompt+answer+'<|im_end|>\n','native single-turn serialization changed')
 tok=proc.tokenizer;ids=tok(full,add_special_tokens=False,truncation=False)['input_ids']
 completion_end=tok(prompt+answer+'<|im_end|>',add_special_tokens=False,truncation=False)['input_ids']
 require(ids[:len(pids)]==pids and ids[:len(completion_end)]==completion_end,'native token boundary mismatch')
 end_id=tok.convert_tokens_to_ids('<|im_end|>');require(completion_end[-1]==end_id,'assistant terminator not found')
 require(len(ids)<=max_length,f'no silent truncation: {record["member_id"]} length {len(ids)} > {max_length}')
 labels=[-100]*len(pids)+ids[len(pids):len(completion_end)]+[-100]*(len(ids)-len(completion_end))
 require(tok.decode([x for x in labels if x!=-100],skip_special_tokens=False)==answer+'<|im_end|>','supervised target differs')
 require(labels[len(completion_end)-1]==end_id,'intended EOS must receive loss')
 require(all(x==-100 for x in labels[:len(pids)]),'system/user/header must be masked')
 return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels},{'member_id':record['member_id'],'prompt_tokens':len(pids),'target_plus_end_tokens':len(completion_end)-len(pids),'total_tokens':len(ids),'assistant_end_token_id':end_id,'masked_native_trailing_tokens':len(ids)-len(completion_end),'token_ids_sha256':digest(ids),'labels_sha256':digest(labels),'rendered_native_sha256':digest(full)}

def collate(records,pad_id,tensors=False):
 require(bool(records),'empty batch');n=max(len(r['input_ids']) for r in records);out={k:[] for k in ('input_ids','attention_mask','labels')}
 for row in records:
  pad=n-len(row['input_ids'])
  for k,fill in [('input_ids',pad_id),('attention_mask',0),('labels',-100)]:out[k].append(row[k]+[fill]*pad)
 if tensors:
  import torch
  return {k:torch.tensor(v,dtype=torch.long) for k,v in out.items()}
 return out
