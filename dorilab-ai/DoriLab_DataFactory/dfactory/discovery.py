"""Bounded Crossref metadata search. Does not fetch paywalled files or grant rights."""
from __future__ import annotations
import json
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from .core import write_jsonl

DOMAINS={'MECHANICS','THERMAL','EEE','MATERIALS','FLUID_PRESSURE','SOFTWARE_HIL'}

def normalize(item: dict, domain: str, query: str) -> dict:
    doi=item.get('DOI','').strip().lower()
    return {'source_id':'doi:'+doi if doi else 'crossref:'+str(item.get('URL','')),
      'doi':doi or None,'title':' '.join(item.get('title',[])),
      'authors':[(' '.join([a.get('given',''),a.get('family','')])).strip() for a in item.get('author',[])],
      'publication_date':item.get('published',{}).get('date-parts'),
      'document_type':item.get('type'),'domain_candidate':domain,'query':query,
      'landing_url':item.get('URL'),'fulltext_link_candidates':item.get('link',[]),
      'rights_metadata':item.get('license',[]),'program_group':'UNASSIGNED',
      'rights_decision':'PENDING','body_status':'NOT_FETCHED','split':'UNASSIGNED',
      'checked_at':datetime.now(timezone.utc).isoformat()}

def discover(query: str, domain: str, out: Path, rows: int=10, mailto: str|None=None) -> int:
    if domain not in DOMAINS: raise ValueError('Unknown domain')
    if not 1<=rows<=100: raise ValueError('rows must be 1..100 (bounded pilot)')
    if out.exists(): raise FileExistsError(out)
    params={'query.bibliographic':query,'rows':rows}
    if mailto:params['mailto']=mailto
    url='https://api.crossref.org/works?'+urlencode(params)
    req=Request(url,headers={'User-Agent':'DoriLab-DataFactory-Prototype/0.1'+(f' (mailto:{mailto})' if mailto else ''),
                              'Accept':'application/json'})
    raw=None
    for attempt in range(3):
        try:
            with urlopen(req,timeout=30) as r:raw=r.read(20_000_000)
            break
        except HTTPError as e:
            if e.code not in {429,500,502,503,504} or attempt==2:raise
            retry=e.headers.get('Retry-After','')
            delay=min(30,int(retry)) if retry.isdigit() else 2**attempt
            time.sleep(delay)
        except URLError:
            if attempt==2:raise
            time.sleep(2**attempt)
    if raw is None:raise RuntimeError('No response')
    data=json.loads(raw);items=data['message']['items']
    seen=set();records=[]
    for item in items:
        c=normalize(item,domain,query)
        if c['source_id'] not in seen:records.append(c);seen.add(c['source_id'])
    write_jsonl(out,records)
    out.with_suffix('.request.json').write_text(json.dumps({'url':url,'count':len(records),
        'note':'Metadata only. Rank relevance, rights and campaign identity before downloading.'},indent=2),encoding='utf-8')
    return len(records)
