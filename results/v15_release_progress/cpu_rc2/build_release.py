"""Auditable CPU release review; never imports a model, trains, or controls a pod."""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import urllib.request
import sys
from pathlib import Path

ROOT = Path('/workspace/dorilab')
OUT = Path(__file__).resolve().parent
PROGRESS = OUT.parent
RC1 = ROOT / 'experiments/source_review_policy_v15/pilot_rc1'
V15 = RC1.parent
PACK = ROOT / 'research/DoriLab_SourceReview_v13'
LEGACY = ROOT / 'dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl'
HOLDS = {'SR13-TIRS-BASELINE', 'SR13-NEA-TRANSLATION', 'SR13-RHOBC-BOOT'}

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def write(name, obj):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def textfile(name, text):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        f.write(text)

def status(stage, completed, pending, paths, next_tasks, blockers):
    directory = PROGRESS / 'status_versions'
    directory.mkdir(parents=True, exist_ok=True)
    serial = len(list(directory.glob('STATUS.*.json'))) + 1
    stamp = now()
    obj = dict(version=serial, release_directory=str(OUT), current_stage=stage,
               completed_items=completed, failed_or_held_items=pending, file_paths=paths,
               next_tasks=next_tasks, gpu_required=False,
               gpu_status='현재 단계는 CPU 작업. 준비 조건 충족 시 같은 Pod GPU 사용 가능. 학습 설정안 보고 전 학습 실행 안 함.',
               blockers=blockers, last_updated_utc=stamp,
               constraints=dict(existing_results_preserved=True, reserved_evaluatoronly_opened=False,
                                pod_lock_touched=False, stop_touched=False, lora_executed=False, gpu_inference_executed=False))
    jp = directory / f'STATUS.{serial:03d}.json'
    mp = directory / f'STATUS.{serial:03d}.md'
    jp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    parts = [f'# SourceReview v15 진행 상태 — {serial:03d}', f'최종 수정: {stamp}',
             f'현재 단계: {stage}', 'GPU 필요 여부: 현재 단계 불필요; 준비 조건 충족 시 현재 Pod에서 사용 가능.',
             '학습·GPU 추론 미실행. Pod lock/STOP 미접촉. RESERVED/EvaluatorOnly 미열람.']
    for heading, values in [('완료 항목', completed), ('실패/보류 항목', pending), ('파일 경로', paths), ('다음 작업', next_tasks), ('Blocker', blockers)]:
        parts += [f'## {heading}', '\n'.join('- ' + x for x in values) or '- 없음']
    mp.write_text('\n\n'.join(parts) + '\n')
    # Stable requested paths point to immutable revisions; every prior status remains accessible.
    for extension, destination in [('json', jp), ('md', mp)]:
        pointer = PROGRESS / f'STATUS.{extension}'
        if pointer.exists() and not pointer.is_symlink():
            raise RuntimeError(f'Refusing to replace existing ordinary file: {pointer}')
        temporary = PROGRESS / f'.STATUS.{extension}.next'
        temporary.symlink_to(destination.relative_to(PROGRESS))
        os.replace(temporary, pointer)
    print(json.dumps({'stage': stage, 'status_version': serial, 'time': stamp}, ensure_ascii=False))

def init():
    inputs = [LEGACY, V15 / 'TRAIN_BUILD_CANDIDATE_v15.json', V15 / 'LABEL_CHANGESET_v15.jsonl']
    inputs += sorted(p for p in RC1.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    inputs += [PACK / 'data/train' / n for n in ['inputs.jsonl','metadata.jsonl','gold_candidate.jsonl']]
    inputs += [PACK / 'sources/facts.json', PACK / 'schemas/reason_definitions_v13.json']
    write('INPUT_PRESERVATION_BEFORE.json', {'created_at_utc': now(), 'scope': 'Explicit public TRAIN/DEV RC1 and legacy repeat246 allowlist; no evaluator files, pod locks or STOP read.', 'files': {str(p): sha(p) for p in inputs}})
    status('01_COMPATIBILITY_IN_PROGRESS', ['기존 RC1과 실제 메시지 원본 경로 확인', '새 cpu_rc2 디렉터리 생성 및 입력 hash 보존'],
           ['3 family 12건 보류 유지', '기존 PHY-EE02-P01-A 호환성 잠정 blocker 재검토 중'],
           [str(OUT / 'INPUT_PRESERVATION_BEFORE.json')],
           ['system/user/assistant 실물 대조', '206행 manifest 확정', '원문 재확보 및 본문 대조'], ['호환성 검사 진행 중'])

def inspect():
    membership = read(RC1 / 'PILOT_TRAIN_MEMBERSHIP.json')
    legacy = rows(LEGACY)
    print('MEMBERSHIP', json.dumps({k:v for k,v in membership.items() if k not in ['ceiling_206_members','selected_candidates','held_members']}, ensure_ascii=False))
    print('MEMBER_EXAMPLES', json.dumps([membership['ceiling_206_members'][0], next(m for m in membership['ceiling_206_members'] if m['component']=='UNIQUE_PHYSICS_STATE'), next(m for m in membership['ceiling_206_members'] if m['component']=='NEW_TRAIN')], ensure_ascii=False))
    seen = set()
    for m in membership['ceiling_206_members']:
        if m['component'] == 'NEW_TRAIN':
            continue
        r = legacy[m['source_row_index_0based']]
        system = r['messages'][0]['content']
        if system not in seen:
            print('SYSTEM_EXAMPLE', m['member_id'], json.dumps(r,ensure_ascii=False))
            seen.add(system)
    print('LEGACY_SYSTEM_COUNT', len(seen))
    print('TRAIN_LABEL_EXAMPLE',json.dumps(rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')[0],ensure_ascii=False))
    print('SOURCE_AUDIT',json.dumps(read(RC1/'sources/SOURCE_AUDIT_RC1.json'),ensure_ascii=False))
    print('FETCH_LOG',json.dumps(read(RC1/'sources/FETCH_LOG.json'),ensure_ascii=False))

def review_inputs(kind='physics'):
    legacy=rows(LEGACY)
    members=read(RC1/'PILOT_TRAIN_MEMBERSHIP.json')['ceiling_206_members']
    grouped=collections.defaultdict(list)
    for m in members:
        if m['component']=='NEW_TRAIN': continue
        r=legacy[m['source_row_index_0based']]
        user=next(x['content'] for x in r['messages'] if x['role']=='user')
        target=json.loads(next(x['content'] for x in r['messages'] if x['role']=='assistant'))
        if m['component']=='UNIQUE_PHYSICS_STATE' and kind=='physics':
            u=json.loads(user)
            print('PHYSICS',m['member_id'],json.dumps({'question':u['review_question'],'source':u['reference_context'],'proposal':u['case_packet']['proposal'],'observations':[e for e in u['case_packet']['evidence'] if e['evidence_id'] in target['evidence_refs']],'target':target},ensure_ascii=False))
        elif m['component']=='UNIQUE_PHYSICS_STATE': continue
        else:
            role=re.search(r'<ROLE>(.*?)</ROLE>',user).group(1)
            state=json.loads(user.split('STATE:',1)[1])
            key=(role,target['action'],target.get('reason'),tuple(sorted(target)))
            grouped[key].append({'id':m['member_id'],'state':state,'target':target})
    if kind=='contract':
        for key,values in grouped.items():
            print('CONTRACT_GROUP',key,'COUNT',len(values),'EXAMPLES',json.dumps(values[:2],ensure_ascii=False))
    for inp,lab in zip(rows(RC1/'TRAIN36_INPUTS.jsonl'),rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')):
        assert inp['case_id']==lab['case_id']
        if kind=='v15' and lab['expected']['action']!='NO_ACTION_REQUIRED':
            p=inp['packet']
            print('V15_CASE',json.dumps({'id':inp['case_id'],'question':p['review_question'],'proposal':p['review_target'],'observations':[o['text'] for o in p['observations'] if o['evidence_id'] in lab['expected']['evidence_refs']],'expected':lab['expected']},ensure_ascii=False))

def inspect_contract(): review_inputs('contract')
def inspect_v15(): review_inputs('v15')

def record_fetch():
    logs=read(OUT/'sources/FETCH_LOG_RC2.json')
    status('01_COMPATIBILITY_IN_PROGRESS_SOURCE_FETCH_DONE', ['CANYVAL/PROBA-V 실제 PDF 2개 HTTP 200 재확보', '두 PDF SHA256이 RC1과 일치', 'legacy 실제 system 5종 확인'],
           ['legacy 일반/구체 reason 충돌 검토', 'Analysis required_s/requirement_s 이름 불일치 검토'],
           [str(OUT/'sources/FETCH_LOG_RC2.json')]+[l['local_path'] for l in logs],
           ['legacy 의미 대조 완료', '새 PDF에서 본문 재추출'], ['호환성 판정 미완료; label 자동 수정 없음'])

def extract_sources():
    sys.path.insert(0,'/tmp/dorilab_v15_pdf_rc2')
    from pypdf import PdfReader
    logs=read(OUT/'sources/FETCH_LOG_RC2.json')
    audit=read(RC1/'sources/SOURCE_AUDIT_RC1.json')
    reports=[]
    for source,log in zip(audit['sources'],logs):
        assert log['source_id']==source['source_id'] and log['status']=='PRIMARY_PDF_REACQUIRED'
        name=source['pdf'].split('_')[0]
        reader=PdfReader(log['local_path'])
        assert len(reader.pages)==source['pages']
        extracts=[]
        for i,page in enumerate(reader.pages,1):
            content=page.extract_text()
            namepath=f'sources/{name}.page{i:02d}.txt'
            textfile(namepath,content)
            extracts.append({'pdf_page_1based':i,'path':namepath,'sha256':sha(OUT/namepath)})
        first=(OUT/extracts[0]['path']).read_text()
        assert source['doi'] in first
        source_facts=[f for f in audit['original_fact_review']+audit['new_method_facts'] if name in f['fact_id']]
        anchors=[]
        for fact in source_facts:
            for span in fact['spans']:
                path=OUT/span['text_artifact'];norm=' '.join(path.read_text().split())
                anchor=span['normalized_anchor'];assert anchor in norm
                start=norm.index(anchor)
                anchors.append({'fact_id':fact['fact_id'],'pdf_page_1based':span['pdf_page_1based'],'page_sha256':sha(path),'normalized_anchor':anchor,'normalized_character_start':start,'same_page_text_as_rc1':sha(path)==span['text_sha256'],'path':str(path)})
                print(name,'PAGE',span['pdf_page_1based'],norm[max(0,start-80):start+1700])
        reports.append({'source':source,'reacquisition':log,'page_count':len(reader.pages),'identity_doi_verified':True,'page_artifacts':extracts,'anchor_checks':anchors,'body_review':'AI reading of primary body prose, not search snippets or human label approval','table_numeric_transcription':False})
    write('sources/PRIMARY_SOURCE_VERIFICATION.json',{'created_at_utc':now(),'sources':reports,'tool':'pypdf 6.1.0 in /tmp/dorilab_v15_pdf_rc2','replacement_sources_needed':False,'labels_modified':False,'search_snippets_used':False})
    status('SOURCE_BODY_REACQUISITION_DONE_COMPATIBILITY_IN_PROGRESS', ['원문 PDF 2개 재확보, DOI·쪽수 확인', '40쪽 신규 본문 추출과 기존 fact anchor 8건 재검증'],
           ['호환성 blocker 판정 진행', 'DEV16 label은 기존 AI 후보 상태 유지'],
           [str(OUT/'sources/PRIMARY_SOURCE_VERIFICATION.json')], ['호환성 보고서·206행 manifest 확정','DEV16 동결 파일 검증'], ['일반/구체 reason 경계 및 Analysis 필드 alias 검토 중'])

def fetch():
    logs=[]
    for source in read(RC1/'sources/SOURCE_AUDIT_RC1.json')['sources']:
        entry={'source_id':source['source_id'],'url':source['download_url'],'started_at_utc':now()}
        path=OUT/'sources'/source['pdf'];path.parent.mkdir(parents=True,exist_ok=True)
        try:
            req=urllib.request.Request(source['download_url'],headers={'User-Agent':'DoriLab-SourceReview-CPU/1.0'})
            with urllib.request.urlopen(req,timeout=35) as response:
                data=response.read(16*1024*1024)
                entry.update(http_status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type'))
            if not data.startswith(b'%PDF-'): raise ValueError('response is not a PDF')
            with path.open('xb') as f:f.write(data)
            entry.update(status='PRIMARY_PDF_REACQUIRED',bytes=len(data),local_path=str(path),sha256=sha(path),identical_to_rc1=sha(path)==source['pdf_sha256'])
        except Exception as exc:
            entry.update(status='FETCH_FAILED',error=str(exc),verified_local_fallback=str(RC1/source['local_pdf']),fallback_sha256=sha(RC1/source['local_pdf']))
        entry['completed_at_utc']=now();logs.append(entry)
        print(json.dumps(entry,ensure_ascii=False),flush=True)
    write('sources/FETCH_LOG_RC2.json',logs)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('stage', choices=['init','inspect','review_inputs','inspect_contract','inspect_v15','fetch','record_fetch','extract_sources'])
    args=parser.parse_args(); globals()[args.stage]()
