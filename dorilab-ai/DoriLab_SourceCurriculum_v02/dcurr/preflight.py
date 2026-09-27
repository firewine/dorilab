import argparse,json,statistics
from pathlib import Path
from .common import ROOT,load_jsonl,sha256,write_json
from .model_io import DEFAULT_MODEL,load_processor,encode_record,environment

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path);p.add_argument('--max-length',type=int,default=2048);p.add_argument('--model',default=DEFAULT_MODEL);p.add_argument('--revision');a=p.parse_args()
    print(json.dumps(environment(),indent=2))
    if not a.data:return
    rows=load_jsonl(a.data)
    if not rows:raise SystemExit('Empty training data')
    processor=load_processor(a.model,a.revision);stats=[]
    for r in rows:
        try:encoded,st=encode_record(processor,r,a.max_length)
        except Exception as e:raise ValueError(f'Record {r.get("id")}: {e}') from e
        if not any(x!=-100 for x in encoded['labels']):raise ValueError('No answer labels')
        stats.append(st)
    out={'status':'PASS','data_sha256':sha256(a.data),'records':len(stats),'max_total_tokens':max(x['total_tokens'] for x in stats),'total_prompt_tokens':sum(x['prompt_tokens'] for x in stats),'total_answer_tokens':sum(x['answer_tokens'] for x in stats),'silent_truncation':False,'mask':'prompt=-100; answer+message-end supervised','records_stats':stats}
    write_json(ROOT/'reports/preflight_latest.json',out)
    print(json.dumps({k:v for k,v in out.items() if k!='records_stats'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
