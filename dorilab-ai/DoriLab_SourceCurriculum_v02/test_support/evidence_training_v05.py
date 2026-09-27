#!/usr/bin/env python3
"""DoriLab v02: matched repeat vs position-balanced evidence training.

Copy beside dcurr/, data/, runs/, evidence_probe_v04.py. Uses the user's existing
trainer, tokenizer preflight and evaluators; does not install packages or change
original data, model weights, review CSVs, prompts, schemas, or evaluator code.
Build/approve are CPU operations. train/evaluate run only when explicitly invoked.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import html
import importlib.util
import json
import os
import random
import re
import runpy
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 'evidence-training-v0.5.0'
OUTDIR = 'data/evidence_training_v05'
PRIOR = 'data/evidence_probe_v04/manifest.json'
TRAIN = 'data/train_curriculum_physics20_v02_r1.jsonl'
TRAIN_SHA = 'a87be2c3094c7e66b7dce06ca34961cd26e240d763c5cecc66df67d8b9514a68'
CONTRACT_SHA = 'b2c79f844e0e301597b8f433ca74c34505fb814fb2245ad3996b551e630cca58'
CASES = 'data/physics_candidates40_v02.jsonl'
CASES_SHA = 'f0a5641a1b4ee64964b2e39b2aafbf779da2fb1cb6cdc1528d62cd115eed83e8'
ARMS = ('repeat', 'position')
VIEWS = ('control', 'after', 'before')
PAIRS = {'TH01-P02','TH01-P03','TH01-P05','VBX1-P01','VBX1-P02',
         'VBX1-P07','VBX1-P03','EE02-P01','EE02-P02','EE03-P01'}
# Authored synthetic administrative records, not facts from any engineering source.
# These deliberately differ from v04's meal-voucher and spare-chair sentences.
NOISE_PAIRS = (
 ('The staff book-club register lists a historical novel selected for the next monthly reading meeting.',
  'The company art-club newsletter announces a watercolor exhibition at the local community gallery.'),
 ('The reception mail log records a packet of museum postcards addressed to the employee social club.',
  'The staff walking-club calendar lists a weekend visit to a public botanical garden.'),
 ('The employee volunteer newsletter lists the opening date of a neighborhood used-book collection.',
  'The company photography-club register records a request for prints of landscape photographs.'),
 ('The staff music-club notice lists the title of a piano recital at the municipal arts hall.',
  'The employee chess-club register lists the names of entrants for its monthly social tournament.'),
 ('The office social committee records the chosen cover image for the annual staff holiday greeting.',
  'The reception visitor brochure describes the public sculpture garden beside the city museum.'),
 ('The staff language-club calendar announces a lunchtime conversation session about travel literature.',
  'The employee hiking-club newsletter records a suggested picnic location at a public country park.'),
 ('The company drama-club notice lists a community theater production recommended for a social outing.',
  'The staff gardening-club register records an exchange of flower-seed packets among its members.'),
 ('The employee history-club newsletter announces a walking tour of the old municipal market district.',
  'The reception library catalog lists a donated collection of travel essays for staff leisure reading.'),
 ('The office social committee lists a suggested puzzle theme for its next staff recreation evening.',
  'The employee painting-club calendar records the opening hours of a public portrait exhibition.'),
 ('The staff astronomy-club newsletter names a public planetarium show scheduled for a social visit.',
  'The company crafts-club notice describes a weekend paper-folding workshop at the town library.'),
)


def now(): return datetime.now(timezone.utc).isoformat()

def strict(text):
    def unique(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('Duplicate JSON key: '+str(k))
            d[k]=v
        return d
    def invalid(v): raise ValueError('Invalid JSON constant: '+v)
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)

def read_jsonl(path):
    rows=[]
    for i,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip(): continue
        x=strict(line)
        if not isinstance(x,dict): raise ValueError(f'{path}:{i}: object required')
        rows.append(x)
    return rows

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def object_sha(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def jsonl_bytes(rows): return (''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)).encode()

def write_json(path,x):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f: json.dump(x,f,ensure_ascii=False,indent=2); f.write('\n')

def write_bytes(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(b)

def relpath(root,s):
    p=Path(s)
    if p.is_absolute() or '..' in p.parts: raise ValueError('Expected project-relative path: '+str(s))
    result=root/p
    if not result.resolve().is_relative_to(root.resolve()): raise ValueError('Path escapes project')
    return result

def load_helper(root):
    p=root/'evidence_probe_v04.py'
    if not p.is_file(): raise ValueError('Keep the already used evidence_probe_v04.py beside this script.')
    spec=importlib.util.spec_from_file_location('_dori_existing_evidence_probe',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    if m.VERSION!='evidence-probe-v0.4.0': raise ValueError('Unexpected v04 helper version')
    return m

def definitions(c):
    out={}
    for rows,k,prefix in ((c['packet']['reference_context'],'reference_id','SF-'),
                         (c['packet']['case_packet']['evidence'],'evidence_id','OBS-')):
        for r in rows:
            ident=r.get(k)
            if not isinstance(ident,str) or not ident.startswith(prefix) or ident in out:
                raise ValueError('Missing/duplicate/unexpected local ID')
            out[ident]=prefix
    return out

def swap(value,mapping):
    if isinstance(value,str):return mapping.get(value,value)
    if isinstance(value,list):return [swap(v,mapping) for v in value]
    if isinstance(value,dict):return {k:swap(v,mapping) for k,v in value.items()}
    return value

def all_strings(value):
    if isinstance(value,str):return [value]
    if isinstance(value,list):return [s for v in value for s in all_strings(v)]
    if isinstance(value,dict):return [s for v in value.values() for s in all_strings(v)]
    return []

def json_span(text,expected):
    """Locate exactly one JSON object equal to the packet, even inside a wrapper.
    Does not guess the package's prompt-factory function or alter surrounding text.
    """
    decoder=json.JSONDecoder();hits=[]
    for i,ch in enumerate(text):
        if ch!='{':continue
        try:obj,n=decoder.raw_decode(text[i:])
        except json.JSONDecodeError:continue
        if isinstance(obj,dict) and obj==expected:hits.append((i,i+n,obj))
    if len(hits)!=1:raise ValueError(f'Expected one exact embedded packet; found {len(hits)}')
    return hits[0]

def render_like(original,parsed,replacement):
    # A packet may sit inside a larger indented JSON object. Its closing brace
    # retains the wrapper's indentation even though its first brace starts at 0.
    tail=re.match(r'^([ \t]*)[}\]]$', original.split('\n')[-1])
    prefixes=['']
    if tail and tail.group(1):prefixes.append(tail.group(1))
    def shift(text,prefix):
        parts=text.split('\n')
        return parts[0]+''.join('\n'+prefix+line for line in parts[1:])
    for indent in (None,2,4,1):
        for ascii_ in (False,True):
            for sep in (None,(',',':'),(', ',': '),(',',': ')):
                kw={'ensure_ascii':ascii_,'indent':indent}
                if sep is not None:kw['separators']=sep
                old=json.dumps(parsed,**kw)
                for prefix in prefixes:
                    if shift(old,prefix)==original:return shift(json.dumps(replacement,**kw),prefix)
    raise ValueError('Unrecognised packet JSON formatting; inspect the accepted training row, not its labels.')

def rewrite_messages(row,old_case,new_case):
    messages=copy.deepcopy(row['messages'])
    if messages[-1].get('role')!='assistant': raise ValueError('Final assistant answer required')
    matches=[]
    for i,m in enumerate(messages[:-1]):
        if m.get('role')!='user' or not isinstance(m.get('content'),str):continue
        try:span=json_span(m['content'],old_case['packet'])
        except ValueError:continue
        matches.append((i,span))
    if len(matches)!=1:raise ValueError('Cannot uniquely match accepted input packet to case '+old_case['case_id'])
    i,(start,end,parsed)=matches[0];old=messages[i]['content']
    # Key order follows the accepted serialized packet, not external metadata.
    packet=copy.deepcopy(parsed)
    for k in packet:packet[k]=new_case['packet'][k]
    messages[i]['content']=old[:start]+render_like(old[start:end],parsed,packet)+old[end:]
    answer=strict(messages[-1]['content'])
    if answer!=old_case['expected']:raise ValueError('Accepted training target differs from primary gold: '+old_case['case_id'])
    out=copy.deepcopy(answer)
    for k in out:out[k]=new_case['expected'][k]
    lead=len(messages[-1]['content'])-len(messages[-1]['content'].lstrip())
    raw=messages[-1]['content'];stop=len(raw.rstrip())
    messages[-1]['content']=raw[:lead]+render_like(raw[lead:stop],answer,out)+raw[stop:]
    return messages

def recover_selected(mixed,contract,cases):
    remaining=Counter(canon(r['messages']) for r in contract)
    extra=[]
    for r in mixed:
        if not isinstance(r.get('messages'),list): raise ValueError('Training row lacks messages')
        key=canon(r['messages'])
        if remaining[key]>0:remaining[key]-=1
        else:extra.append(r)
    if any(remaining.values()):raise ValueError('Released mixture does not preserve all Contract150 messages')
    selected={}
    for r in extra:
        found=[]
        for c in cases:
            for msg in r['messages'][:-1]:
                if msg.get('role')!='user' or not isinstance(msg.get('content'),str):continue
                try:json_span(msg['content'],c['packet'])
                except ValueError:continue
                if strict(r['messages'][-1]['content'])==c['expected']:found.append(c)
        if len(found)!=1:raise ValueError('Released physics row cannot be unambiguously traced to an approved case')
        c=found[0]
        if c['case_id'] in selected:raise ValueError('Duplicate physics case in released training data')
        selected[c['case_id']]={'case':c,'row':r}
    if len(selected)!=20 or {v['case']['pair_id'] for v in selected.values()}!=PAIRS:
        raise ValueError('Expected the previously approved 20 cases / 10 pairs; do not silently change selection')
    return selected

def check_reviews(root,selected):
    def read(name,key):
        with (root/name).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        if any(key not in r for r in rows):raise ValueError(name+': expected '+key)
        return {r[key]:r for r in rows}
    cases=read('data/review_decisions.csv','case_id');sources=read('data/source_review.csv','source_id')
    for cid,v in selected.items():
        if cases.get(cid,{}).get('decision')!='APPROVED':raise ValueError('Case is not currently approved: '+cid)
        sid=v['case']['source_id']
        if sources.get(sid,{}).get('permission_review')!='REVIEWED_OK':raise ValueError('Source review not complete: '+sid)

def data_variants(selected,contract,seed,forbidden_ids):
    rng=random.Random(seed);used=set(forbidden_ids)
    groups=defaultdict(list)
    for v in selected.values():groups[v['case']['pair_id']].append(v)
    if len(groups)!=10 or any(len(v)!=2 for v in groups.values()):raise ValueError('Complete ten pairs required')
    noise=list(NOISE_PAIRS);rng.shuffle(noise);details={};cases_by_arm={a:{} for a in ARMS}
    def fresh(prefix):
        for _ in range(30000):
            ident=prefix+str(rng.randrange(1000,10000))
            if ident not in used:used.add(ident);return ident
        raise ValueError('Local ID space exhausted')
    for i,pid in enumerate(sorted(groups)):
        defs={}
        for v in groups[pid]:defs.update(definitions(v['case']))
        mapping={old:fresh(prefix) for old,prefix in sorted(defs.items())}
        additions=[{'evidence_id':fresh('OBS-'),'text':text} for text in noise[i]]
        details[pid]={'mapping_shared_both_arms':mapping,'synthetic_administrative_observations':additions,'cases':[]}
        for v in groups[pid]:
            c=v['case']
            if len(c['packet']['case_packet']['evidence'])!=1:raise ValueError('Current design requires one original observation')
            for text in all_strings(c['packet']):
                if any(old!=text and old in text for old in mapping):raise ValueError('Local ID embedded in prose needs manual treatment')
            mapped=copy.deepcopy(c)
            for key in ('packet','expected','acceptable_answers'):
                if key in mapped:mapped[key]=swap(mapped[key],mapping)
            origin=mapped['packet']['case_packet']['evidence'][0]
            details[pid]['cases'].append({'parent_case_id':c['case_id'],'mapped_case':mapped})
            for pos in range(3):
                repeat=copy.deepcopy(mapped);multi=copy.deepcopy(mapped)
                others=copy.deepcopy(additions);others.insert(pos,copy.deepcopy(origin))
                multi['packet']['case_packet']['evidence']=others
                for arm,derived in [('repeat',repeat),('position',multi)]:
                    # Recover packet exactly when only synthetic additions and shared rename are undone.
                    restored=copy.deepcopy(derived['packet'])
                    restored['case_packet']['evidence']=[e for e in restored['case_packet']['evidence'] if e['evidence_id']==origin['evidence_id']]
                    if swap(restored,{n:o for o,n in mapping.items()})!=c['packet']:
                        raise ValueError('Augmentation changed source prose, original evidence or proposal')
                    cases_by_arm[arm][(c['case_id'],pos)]=derived
    schedule=[('contract',i,0) for i in range(len(contract))]+[('physics',cid,pos) for cid in sorted(selected) for pos in range(3)]
    rng.shuffle(schedule);rows={a:[] for a in ARMS};sidecar=[]
    for slot,(kind,key,pos) in enumerate(schedule):
        rid='EV05-'+f'{slot+1:03d}'
        meta={'row_id':rid,'kind':kind,'parent_case_id':key if kind=='physics' else None,'copy_index':pos,'relevant_observation_position_1based':pos+1 if kind=='physics' else None}
        for arm in ARMS:
            if kind=='contract':new=copy.deepcopy(contract[key])
            else:
                v=selected[key];derived=cases_by_arm[arm][(key,pos)]
                new=copy.deepcopy(v['row']);new['messages']=rewrite_messages(new,v['case'],derived)
                for field in ('packet','expected'):
                    if field in new and new[field]==v['case'][field]:new[field]=copy.deepcopy(derived[field])
            new['id']=rid
            if 'case_id' in new:new['case_id']=rid
            new['v05_metadata']={'arm':arm,**meta,'human_augmentation_review':'PENDING_IN_SEPARATE_APPROVAL_FILE'}
            rows[arm].append(new)
        if rows['repeat'][-1]['messages'][-1]!=rows['position'][-1]['messages'][-1]:raise ValueError('Target text differs between arms')
        if rows['repeat'][-1]['messages'][0]!=rows['position'][-1]['messages'][0]:raise ValueError('System prompts differ')
        sidecar.append(meta)
    if any(len(v)!=210 for v in rows.values()):raise ValueError('Expected 210 rows per arm')
    return rows,cases_by_arm,details,sidecar

def review_html(details):
    out=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DoriLab v05 augmentation review</title>',
         '<style>body{font:16px/1.65 system-ui,sans-serif;max-width:1100px;margin:auto;padding:28px;color:#213442;background:#f5f7f8}article{background:white;padding:24px;margin:22px 0;border:1px solid #d4dfe3}pre{white-space:pre-wrap;background:#f0f4f6;padding:14px;font-size:13px}h2{margin-top:0}.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}.notice{background:#e7f1f2;padding:18px}</style>',
         '<h1>Evidence training v05 · 증강 내용 검토</h1><p class="notice">기존 승인 20개 / 10쌍만 사용합니다. 아래 두 사무 기록은 이번에 작성한 가상 자료이며 논문의 사실이 아닙니다. 반복 대조군과 다중 근거군은 동일한 새 SF/OBS ID와 정답을 사용합니다. 다중 근거군에서만 기존 관측의 위치를 첫째·둘째·셋째로 바꿉니다. 기존 리뷰 CSV는 변경하지 않습니다.</p>']
    for pid,d in details.items():
        out.append('<article><h2>'+html.escape(pid)+'</h2><h3>추가할 가상 관측 — 이 검토 질문과 무관한지 확인</h3>')
        for x in d['synthetic_administrative_observations']:out.append('<p><b>'+html.escape(x['evidence_id'])+'</b> '+html.escape(x['text'])+'</p>')
        out.append('<p>배치: [원 관측, 추가1, 추가2] / [추가1, 원 관측, 추가2] / [추가1, 추가2, 원 관측]</p><div class="cols">')
        for x in d['cases']:
            c=x['mapped_case'];p=c['packet']
            out.append('<section><h3>'+html.escape(x['parent_case_id'])+'</h3>')
            out.append('<p><b>질문:</b> '+html.escape(p['review_question'])+'</p>')
            for fact in p['reference_context']:out.append('<p><b>문헌 근거:</b> '+html.escape(fact['text'])+'</p>')
            out.append('<p><b>현재 관측:</b> '+html.escape(p['case_packet']['evidence'][0]['text'])+'</p>')
            out.append('<p><b>검토할 제안:</b> '+html.escape(p['case_packet']['proposal'])+'</p>')
            out.append('<pre>'+html.escape(json.dumps(c['expected'],ensure_ascii=False,indent=2))+'</pre>')
            out.append('<p>'+html.escape(c.get('rationale_ko',''))+'</p></section>')
        out.append('</div></article>')
    return '\n'.join(out)

def verify_prior(root,h,prior):
    if prior.get('version')!='evidence-probe-v0.4.0':raise ValueError('Expected completed v04 probe')
    h.freeze_check(root,prior['frozen_files'])
    if sha(root/'evidence_probe_v04.py')!=prior['script_sha256']:raise ValueError('Prior helper changed')
    for view in VIEWS:
        if sha(relpath(root,prior['files'][view]))!=prior['file_sha256'][view]:raise ValueError('Prior view changed: '+view)
    report_path=relpath(root,Path(PRIOR).parent/'comparison.json');report=strict(report_path.read_text())
    for model,spec in prior['model_specs'].items():
        for view in VIEWS:
            path=relpath(root,spec['result_files'][view])
            if sha(path)!=report['generation_result_hashes'][model+'/'+view]:raise ValueError('Prior prediction changed')
    return report

def build(root,outdir,seed):
    target=relpath(root,outdir)
    if target.exists():raise ValueError('Output directory exists; preserve it, do not overwrite')
    h=load_helper(root);common=h.runtime_common(root)
    prior=strict(relpath(root,PRIOR).read_text());oldreport=verify_prior(root,h,prior)
    mixed_path=relpath(root,TRAIN);contract_path=root.parent/'data/train150_v01.jsonl';cases_path=relpath(root,CASES)
    for p,d in [(mixed_path,TRAIN_SHA),(contract_path,CONTRACT_SHA),(cases_path,CASES_SHA)]:
        if not p.is_file() or sha(p)!=d:raise ValueError('Expected original released input hash differs: '+str(p))
    mixed=read_jsonl(mixed_path);contract=read_jsonl(contract_path);cases=read_jsonl(cases_path)
    if (len(mixed),len(contract),len(cases))!=(170,150,40):raise ValueError('Expected 170 / 150 / 40 rows')
    selected=recover_selected(mixed,contract,cases);check_reviews(root,selected)
    forbidden=set()
    for c in cases:forbidden.update(definitions(c))
    for view in VIEWS:
        for c in read_jsonl(relpath(root,prior['files'][view])):forbidden.update(definitions(c))
    if any(t in h.DISTRACTOR_TEXTS for pair in NOISE_PAIRS for t in pair):raise ValueError('Training distractor copied from v04 evaluation')
    rows,derived,details,sidecar=data_variants(selected,contract,seed,forbidden)
    for arm in ARMS:
        for c in derived[arm].values():
            common.validate_answer(c['expected'],c)
            for a in h.answer_variants(c):common.validate_answer(a,c)
    for c in derived['position'].values():
        if any(set(a['evidence_refs'])&{e['evidence_id'] for e in details[c['pair_id']]['synthetic_administrative_observations']} for a in h.answer_variants(c)):
            raise ValueError('Distractor became gold evidence')
    frozen=dict(prior['frozen_files']);frozen[PRIOR]=sha(relpath(root,PRIOR))
    frozen[str(Path(PRIOR).parent/'comparison.json')]=sha(relpath(root,Path(PRIOR).parent/'comparison.json'))
    for v,p in prior['files'].items():frozen[p]=sha(relpath(root,p))
    for sp in prior['model_specs'].values():
        for p in sp['result_files'].values():frozen[p]=sha(relpath(root,p))
    for p in [mixed_path,cases_path,root/'evidence_probe_v04.py',root/'data/review_decisions.csv',root/'data/source_review.csv',*sorted((root/'dcurr').glob('*.py'))]:
        frozen[str(p.relative_to(root))]=sha(p)
    legacy_runner=root.parent/'eval/run_eval40_qwen35.py'
    if not legacy_runner.is_file():raise ValueError('Existing Contract Eval40 runner missing')
    slug=Path(outdir).name
    if not re.fullmatch('[A-Za-z0-9_]+',slug):raise ValueError('Simple alphanumeric outdir basename required')
    arms={}
    for arm in ARMS:
        arms[arm]={'candidate':str(Path(outdir)/f'{arm}210_candidate.jsonl'),
                   'training_data':str(Path(outdir)/f'{arm}210.jsonl'),
                   'adapter':f'runs/{slug}_{arm}_e1',
                   'result_files':{v:f'reports/{slug}_{arm}_{v}.jsonl' for v in VIEWS},
                   'contract_label':f'{slug}_{arm}_contract',
                   'contract_result':str(root.parent/f'eval/results/{slug}_{arm}_contract_dev.jsonl')}
        if relpath(root,arms[arm]['adapter']).exists():raise ValueError('Run path already exists')
        if any(relpath(root,p).exists() for p in arms[arm]['result_files'].values()) or Path(arms[arm]['contract_result']).exists():
            raise ValueError('New experiment result path already exists; use a new outdir/version')
    m={'version':VERSION,'created_at_utc':now(),'script_sha256':sha(Path(__file__)),
       'prior_probe':PRIOR,'prior_model_specs':prior['model_specs'],'eval_files':prior['files'],
       'eval_distractor_ids_by_case':prior['distractor_ids_by_case'],'prior_summary':oldreport,
       'frozen_files':frozen,'external_frozen_files':{str(contract_path.resolve()):sha(contract_path),str(legacy_runner.resolve()):sha(legacy_runner)},
       'augmentation_seed':seed,'training_seed_at_worker_entry':42,'model':'Qwen/Qwen3.5-2B',
       'epochs':1,'lr':5e-5,'rank':16,'max_length':2048,
       'arms':arms,'selected_case_ids':sorted(selected),'selected_pair_ids':sorted(PAIRS),
       'rows_per_arm':210,'contract_rows':150,'physics_presentations':60,'independent_physics_cases':20,'positions_in_treatment':{'first':20,'middle':20,'last':20},
       'candidate_sha256':{a:hashlib.sha256(jsonl_bytes(rows[a])).hexdigest() for a in ARMS},
       'policy':'Same gold answer strings and common task prompts in both arms; local SF/OBS IDs are newly renamed identically in both arms. No new action/reason or source fact.',
       'interpretation':'Matched presentation-budget intervention: repeat vs irrelevant-observation+position augmentation. Input token count is NOT matched. Known same-case v04 development diagnostic, not independent new-program generalization.',
       'review_status':'DERIVED_AUGMENTATIONS_PENDING_REVIEW','gpu_tested_during_package_build':False}
    target.mkdir(parents=True,exist_ok=False)
    for a in ARMS:write_bytes(relpath(root,arms[a]['candidate']),jsonl_bytes(rows[a]))
    write_json(target/'augmentation_details.json',details);write_json(target/'row_alignment.json',sidecar)
    write_bytes(target/'REVIEW.html',review_html(details).encode())
    m['review_files_sha256']={n:sha(target/n) for n in ['augmentation_details.json','row_alignment.json','REVIEW.html']}
    write_json(target/'manifest.json',m)
    print('EVIDENCE TRAINING BUILD: PASS')
    print('Two candidate datasets: 150 Contract + 20 Physics x 3 = 210 each.')
    print('Relevant position in position arm: first20 / middle20 / last20.')
    print('Same common prompts, target answers, row schedule and per-case exposure counts in both arms.')
    print('New local SF/OBS handles are common to both arms. No v04 distractor sentence was used in training.')
    print('Review:',target/'REVIEW.html');print('No approval, training, or original-file mutation performed.')

def load_plan(root,outdir,approved=False):
    target=relpath(root,outdir);m=strict((target/'manifest.json').read_text())
    if m.get('version')!=VERSION or sha(Path(__file__))!=m['script_sha256']:raise ValueError('Build script/version changed')
    h=load_helper(root);h.freeze_check(root,m['frozen_files'])
    for p,d in m['external_frozen_files'].items():
        if sha(Path(p))!=d:raise ValueError('External frozen input changed: '+p)
    for a in ARMS:
        if sha(relpath(root,m['arms'][a]['candidate']))!=m['candidate_sha256'][a]:raise ValueError('Candidate data changed')
    for n,d in m['review_files_sha256'].items():
        if sha(target/n)!=d:raise ValueError('Review artifact changed')
    if approved:
        ap=strict((target/'approval.json').read_text())
        if ap.get('decision')!='APPROVED' or not ap.get('reviewer') or not ap.get('notes'):raise ValueError('Augmentation approval missing')
        if ap['manifest_sha256']!=sha(target/'manifest.json'):raise ValueError('Approval was for a different manifest')
        for a in ARMS:
            if sha(relpath(root,m['arms'][a]['training_data']))!=m['candidate_sha256'][a]:raise ValueError('Released data changed')
    return target,m,h

def approve(root,outdir,reviewer,notes):
    target,m,h=load_plan(root,outdir)
    if not reviewer.strip() or not notes.strip():raise ValueError('Actual reviewer and notes required')
    if (target/'approval.json').exists():raise ValueError('Approval already exists; preserved')
    for a in ARMS:
        if relpath(root,m['arms'][a]['training_data']).exists():raise ValueError('Released path already exists')
    for a in ARMS:write_bytes(relpath(root,m['arms'][a]['training_data']),relpath(root,m['arms'][a]['candidate']).read_bytes())
    write_json(target/'approval.json',{'decision':'APPROVED','reviewer':reviewer,'notes':notes,'at_utc':now(),
         'manifest_sha256':sha(target/'manifest.json'),'dataset_sha256':m['candidate_sha256'],
         'scope':'Synthetic irrelevant-observation augmentation of the previously approved Physics20; no new source approval.'})
    print('AUGMENTATION RELEASE: 210 repeat / 210 position. Original review CSVs unchanged.')

def run_logged(root,target,label,args,cwd=None,env=None):
    logs=target/'logs';logs.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    path=logs/f'{label}_{stamp}.log';parts=[]
    print('\nRUN:',shlex.join([str(x) for x in args]),flush=True)
    with path.open('x',encoding='utf-8') as f:
        f.write('COMMAND '+shlex.join([str(x) for x in args])+'\n');f.flush()
        p=subprocess.Popen(args,cwd=cwd or root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
        for line in p.stdout:
            print(line,end='',flush=True);f.write(line);f.flush();parts.append(line)
        code=p.wait()
    if code:raise RuntimeError(f'{label} failed ({code}); preserved log: {path}')
    return ''.join(parts),path

def extract_json_reports(text):
    decoder=json.JSONDecoder();out=[]
    for i,ch in enumerate(text):
        if ch!='{':continue
        try:obj,_=decoder.raw_decode(text[i:])
        except ValueError:continue
        if isinstance(obj,dict):out.append(obj)
    return out

def resolve_revision(root,target,model):
    path=target/'base_revision.json'
    if path.exists():return strict(path.read_text())['revision']
    code=('from transformers import AutoConfig; import json; '
          f'c=AutoConfig.from_pretrained({model!r},local_files_only=True); '
          'r=getattr(c,"_commit_hash",None); print("DORILAB_REVISION="+json.dumps(r))')
    text,_=run_logged(root,target,'resolve_cached_base',[sys.executable,'-c',code])
    lines=[x.split('DORILAB_REVISION=',1)[1] for x in text.splitlines() if x.startswith('DORILAB_REVISION=')]
    revision=strict(lines[-1]) if lines else None
    if not isinstance(revision,str) or not re.fullmatch('[0-9a-f]{40}',revision):
        raise ValueError('Cannot pin a cached base-model revision. No training started; inspect resolve_cached_base log.')
    write_json(path,{'model':model,'revision':revision,'resolved_at_utc':now(),'source':'Installed Transformers AutoConfig, local_files_only=True'})
    return revision

def training_record(target,arm):return target/f'train_{arm}_complete.json'

def check_trained(root,target,m,arm):
    p=training_record(target,arm)
    if not p.exists():raise ValueError('Training completion record missing: '+arm)
    r=strict(p.read_text());weight=relpath(root,m['arms'][arm]['adapter'])/'adapter_model.safetensors'
    if sha(weight)!=r['adapter_sha256']:raise ValueError('Trained adapter changed: '+arm)
    if r['training_data_sha256']!=m['candidate_sha256'][arm]:raise ValueError('Run data mismatch')
    if r['base_revision']!=strict((target/'base_revision.json').read_text())['revision']:
        raise ValueError('Pinned base revision changed since training')
    return r

def train(root,outdir):
    target,m,h=load_plan(root,outdir,True);rev=resolve_revision(root,target,m['model'])
    stats={}
    for arm in ARMS:
        text,log=run_logged(root,target,f'preflight_{arm}',[sys.executable,'-m','dcurr.preflight','--data',m['arms'][arm]['training_data'],
              '--max-length',str(m['max_length']),'--model',m['model'],'--revision',rev])
        found=[r for r in extract_json_reports(text) if r.get('status')=='PASS' and r.get('records')==210]
        if not found:raise ValueError('Preflight did not report PASS and 210 records: '+arm)
        stats[arm]=found[-1]
        if stats[arm].get('silent_truncation') is not False:raise ValueError('No-truncation preflight record required')
    if stats['repeat'].get('total_answer_tokens')!=stats['position'].get('total_answer_tokens'):
        raise ValueError('Supervised token counts differ across arms; inspect preflight before training')
    audit=target/'preflight_pair.json'
    if not audit.exists():write_json(audit,{'at_utc':now(),'arms':stats,'note':'Answer-token counts equal; prompt-token counts are intentionally different.'})
    for arm in ARMS:
        if training_record(target,arm).exists():check_trained(root,target,m,arm);print('PRESERVED completed training:',arm);continue
        out=relpath(root,m['arms'][arm]['adapter'])
        if out.exists():raise ValueError(f'Incomplete/unregistered run exists: {out}. Preserve it; do not overwrite.')
        env=dict(os.environ);env['PYTHONHASHSEED']=str(m['training_seed_at_worker_entry'])
        _,log=run_logged(root,target,f'train_{arm}',[sys.executable,str(Path(__file__).resolve()),'_train-worker','--root',str(root),'--outdir',str(outdir),'--arm',arm],env=env)
        weight=out/'adapter_model.safetensors';config=strict((out/'adapter_config.json').read_text())
        if config.get('r')!=m['rank']:raise ValueError('Saved LoRA rank differs from plan')
        write_json(training_record(target,arm),{'completed_at_utc':now(),'adapter_sha256':sha(weight),
               'adapter_config_sha256':sha(out/'adapter_config.json'),'base_revision':rev,'arm':arm,
               'training_data_sha256':m['candidate_sha256'][arm],'seed_at_entry':m['training_seed_at_worker_entry'],'log':str(log.relative_to(root))})
    print('BOTH TRAINING RUNS COMPLETE. Next: evaluate, then compare.')

def train_worker(root,outdir,arm):
    target,m,h=load_plan(root,outdir,True)
    rev=strict((target/'base_revision.json').read_text())['revision']
    from transformers import set_seed
    set_seed(m['training_seed_at_worker_entry'])
    sys.path.insert(0,str(root));os.chdir(root)
    sys.argv=['dcurr.train','--data',m['arms'][arm]['training_data'],'--out',m['arms'][arm]['adapter'],
              '--max-length',str(m['max_length']),'--epochs',str(m['epochs']),'--lr',str(m['lr']),
              '--rank',str(m['rank']),'--model',m['model'],'--revision',rev]
    runpy.run_module('dcurr.train',run_name='__main__')

def eval_identity(root,target,m,arm,view,case_path,result_path):
    trained=check_trained(root,target,m,arm)
    return {'arm':arm,'view':view,'adapter_sha256':trained['adapter_sha256'],
            'case_file_sha256':sha(case_path) if case_path is not None else None,
            'result_path':str(result_path.resolve()),'base_revision':trained['base_revision']}

def start_evaluation(target,identity,result_path):
    stem='eval_'+identity['arm']+'_'+identity['view']
    start=target/(stem+'_started.json');done=target/(stem+'_complete.json')
    if start.exists():
        if strict(start.read_text())['identity']!=identity:raise ValueError('Evaluation identity changed: '+stem)
    else:
        if result_path.exists():raise ValueError('Unregistered result exists: '+str(result_path))
        write_json(start,{'identity':identity,'started_at_utc':now()})
    if done.exists():
        d=strict(done.read_text())
        if d['identity']!=identity or not result_path.exists() or d['result_sha256']!=sha(result_path):
            raise ValueError('Previously completed evaluation changed: '+stem)
    return done

def finish_evaluation(done,identity,path):
    if not done.exists():write_json(done,{'identity':identity,'completed_at_utc':now(),'result_sha256':sha(path)})

def verify_evaluation(target,identity,path):
    done=target/('eval_'+identity['arm']+'_'+identity['view']+'_complete.json')
    if not done.exists():raise ValueError('Evaluation completion record missing: '+str(done))
    r=strict(done.read_text())
    if r['identity']!=identity or r['result_sha256']!=sha(path):raise ValueError('Evaluation result/provenance changed')

def evaluate(root,outdir):
    target,m,h=load_plan(root,outdir,True);common=h.runtime_common(root)
    rev=strict((target/'base_revision.json').read_text())['revision']
    for arm in ARMS:
        check_trained(root,target,m,arm)
        for view in VIEWS:
            results=relpath(root,m['arms'][arm]['result_files'][view]);case_path=relpath(root,m['eval_files'][view]);cases=h.read_jsonl(case_path)
            identity=eval_identity(root,target,m,arm,view,case_path,results)
            done=start_evaluation(target,identity,results)
            if not results.exists():
                run_logged(root,target,f'eval_{arm}_{view}',[sys.executable,'-m','dcurr.evaluate','--cases',m['eval_files'][view],
                  '--adapter',m['arms'][arm]['adapter'],'--out',m['arms'][arm]['result_files'][view],
                  '--purpose','CANDIDATE_DIAGNOSTIC','--model',m['model'],'--revision',rev])
            rows=h.result_ids(h.read_jsonl(results),cases)
            for c in cases:
                sc=h.score(common,c,rows[c['case_id']],[] if view=='control' else m['eval_distractor_ids_by_case'][c['case_id']])
                if not sc['stored_score_agrees']:raise ValueError('Stored/current evaluator score mismatch')
            finish_evaluation(done,identity,results)
            print('COMPLETE:',arm,view,'40 cases')
        path=Path(m['arms'][arm]['contract_result'])
        identity=eval_identity(root,target,m,arm,'legacy',None,path)
        done=start_evaluation(target,identity,path)
        if not path.exists():
            run_logged(root,target,'contract_'+arm,[sys.executable,'-m','eval.run_eval40_qwen35','--split','dev',
                 '--adapter',str(relpath(root,m['arms'][arm]['adapter']).resolve()),'--label',m['arms'][arm]['contract_label']],cwd=root.parent)
        rows=read_jsonl(path);ids=[r.get('id',r.get('case_id')) for r in rows]
        if len(rows)!=20 or len(set(ids))!=20 or None in ids or any(not isinstance(r.get('pass'),bool) for r in rows):
            raise ValueError('Contract regression result incomplete or unknown format')
        finish_evaluation(done,identity,path)
        print('CONTRACT:',arm,sum(r['pass'] for r in rows),'/20')
    print('All evaluations complete. Next: compare.')

def compare(root,outdir):
    target,m,h=load_plan(root,outdir,True);common=h.runtime_common(root)
    if (target/'comparison.json').exists() or (target/'comparison_cases.jsonl').exists():raise ValueError('Comparison already exists; preserved')
    case_sets={v:h.by_id(h.read_jsonl(relpath(root,m['eval_files'][v]))) for v in VIEWS}
    selected=set(m['selected_case_ids']);specs={}
    for name,sp in m['prior_model_specs'].items():specs['prior_'+name]=sp['result_files']
    for arm in ARMS:check_trained(root,target,m,arm);specs[arm]=m['arms'][arm]['result_files']
    report={'version':VERSION,'created_at_utc':now(),'rows_per_training_arm':210,'unique_physics_cases_used_for_training':20,
       'purpose':'REPEATED_KNOWN_CASE_DEVELOPMENT_DIAGNOSTIC_NOT_FINAL_HOLDOUT',
       'intervention':'repeat vs position-balanced unrelated-observation augmentation; same renamed IDs/target texts and per-case exposure counts; input tokens not matched',
       'models':{},'result_sha256':{},'base_revision':strict((target/'base_revision.json').read_text())['revision']}
    details=[]
    for model,files in specs.items():
        scored={};metrics={}
        for view in VIEWS:
            result_path=relpath(root,files[view])
            if model in ARMS:
                identity=eval_identity(root,target,m,model,view,relpath(root,m['eval_files'][view]),result_path)
                verify_evaluation(target,identity,result_path)
            result=h.result_ids(h.read_jsonl(result_path),list(case_sets[view].values()))
            scores={}
            for cid,c in case_sets[view].items():
                sc=h.score(common,c,result[cid],[] if view=='control' else m['eval_distractor_ids_by_case'][cid])
                if not sc['stored_score_agrees']:raise ValueError('Saved/current score differs: '+cid)
                scores[cid]=sc
            scored[view]=scores
            metric_rows=[{'pair_id':case_sets[view][cid]['pair_id'],'score':sc} for cid,sc in scores.items()]
            metrics[view]=h.summarise(metric_rows)
            metrics[view]['selected20']=h.summarise([{'pair_id':case_sets[view][cid]['pair_id'],'score':sc} for cid,sc in scores.items() if cid in selected])
            metrics[view]['remainder_same_source20']=h.summarise([{'pair_id':case_sets[view][cid]['pair_id'],'score':sc} for cid,sc in scores.items() if cid not in selected])
            report['result_sha256'][model+'/'+view]=sha(relpath(root,files[view]))
        records=[]
        for cid,c in case_sets['control'].items():
            sc={v:scored[v][cid] for v in VIEWS}
            row={'model':model,'case_id':cid,'pair_id':c['pair_id'],'partition':'selected20' if cid in selected else 'remainder_same_source20',
                 'scores':sc,'position_changed_action':h.action_value(sc['after'])!=h.action_value(sc['before']),
                 'position_changed_reference_choice':h.reference_signature(sc['after'])!=h.reference_signature(sc['before']),
                 'all_three_views_strict_pass':all(sc[v]['strict_selection_contract_pass'] for v in VIEWS)}
            records.append(row)
        summary={'views':metrics,'position_changed_action':sum(r['position_changed_action'] for r in records),
                 'position_changed_reference_choice':sum(r['position_changed_reference_choice'] for r in records),
                 'all_three_views_strict_pass':sum(r['all_three_views_strict_pass'] for r in records)}
        if model in ARMS:
            cr_path=Path(m['arms'][model]['contract_result'])
            identity=eval_identity(root,target,m,model,'legacy',None,cr_path)
            verify_evaluation(target,identity,cr_path)
            cr=read_jsonl(cr_path)
            if len(cr)!=20 or any(not isinstance(r.get('pass'),bool) for r in cr):raise ValueError('Contract results incomplete')
            summary['legacy_contract_dev']={'pass':sum(r['pass'] for r in cr),'total':20,
                  'failed_ids':[r.get('id',r.get('case_id')) for r in cr if not r['pass']],
                  'sha256':sha(Path(m['arms'][model]['contract_result'])),'rows':cr}
            summary['training_run']=check_trained(root,target,m,model)
        report['models'][model]=summary;details.extend(records)
    a=report['models']['repeat'];b=report['models']['position']
    report['position_minus_repeat']={v:{k:b['views'][v][k]-a['views'][v][k] for k in ['action_correct','reference_choice_exact','strict_selection_contract_pass','rows_citing_distractors']} for v in VIEWS}
    report['position_minus_repeat']['contract_dev_pass']=b['legacy_contract_dev']['pass']-a['legacy_contract_dev']['pass']
    write_json(target/'comparison.json',report);write_bytes(target/'comparison_cases.jsonl',jsonl_bytes(details))
    print('model            view     action   exact-refs strict-pass irrelevant-refs')
    for name,s in report['models'].items():
        for v,mt in s['views'].items():
            print(f"{name:16s} {v:8s} {mt['action_correct']:2}/40    {mt['reference_choice_exact']:2}/40     {mt['strict_selection_contract_pass']:2}/40       {mt['rows_citing_distractors']:2}")
        if 'legacy_contract_dev' in s:print('   Contract Dev:',s['legacy_contract_dev']['pass'],'/20')
    print(json.dumps(report['position_minus_repeat'],ensure_ascii=False,indent=2))
    print('Saved:',target/'comparison.json');print('Raw per-case details:',target/'comparison_cases.jsonl')

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    for cmd in ('build','approve','train','evaluate','compare','_train-worker'):
        q=sp.add_parser(cmd);q.add_argument('--root',type=Path,default=Path.cwd());q.add_argument('--outdir',type=Path,default=Path(OUTDIR))
        if cmd=='build':q.add_argument('--seed',type=int,default=2026091905)
        if cmd=='approve':q.add_argument('--reviewer',required=True);q.add_argument('--notes',required=True)
        if cmd=='_train-worker':q.add_argument('--arm',choices=ARMS,required=True)
    a=p.parse_args();root=a.root.resolve()
    if not (root/'dcurr/common.py').is_file():raise ValueError('Run in ~/dorilab-ai/DoriLab_SourceCurriculum_v02')
    if a.command=='build':build(root,a.outdir,a.seed)
    elif a.command=='approve':approve(root,a.outdir,a.reviewer,a.notes)
    elif a.command=='train':train(root,a.outdir)
    elif a.command=='evaluate':evaluate(root,a.outdir)
    elif a.command=='compare':compare(root,a.outdir)
    elif a.command=='_train-worker':train_worker(root,a.outdir,a.arm)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,ImportError,RuntimeError) as exc:
        raise SystemExit('STOP: '+str(exc)+'\nExisting source/data/review/model files were not intentionally overwritten. Preserve logs before retrying.')
