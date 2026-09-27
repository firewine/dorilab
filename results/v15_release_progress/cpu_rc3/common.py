"""RC3 filesystem helpers. Only explicit public input paths; no model/pod operations."""
import datetime, hashlib, json, os
from pathlib import Path
ROOT=Path('/workspace/dorilab')
OUT=Path(__file__).resolve().parent
PROGRESS=OUT.parent
RC2=PROGRESS/'cpu_rc2'
RC1=ROOT/'experiments/source_review_policy_v15/pilot_rc1'
PACK=ROOT/'research/DoriLab_SourceReview_v13'
LEGACY=ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl'
REVISION='1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
ASSET_ROOT=ROOT/'experiments/source_review_direct_v14/cpu_token_preflight_v1'
ASSETS=ASSET_ROOT/'assets'/REVISION
PREFLIGHT=OUT/'CPU_PREFLIGHT_v4.json'
BUNDLE=OUT/'APPROVAL_BUNDLE_v2.json'
PENDING_APPROVAL=OUT/'RELEASE_APPROVAL_PENDING_v2.json'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
def put(name,x):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def text(name,x):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(x)
def jsonl(name,items):text(name,''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items))
def status(stage,done,held,paths,next_tasks,blockers):
 d=PROGRESS/'status_versions';n=max(int(p.name.split('.')[1]) for p in d.glob('STATUS.*.json'))+1
 obj=dict(version=n,current_stage=stage,last_updated_utc=now(),release_directory=str(OUT),completed_items=done,failed_or_held_items=held,file_paths=[str(OUT/p) for p in paths],next_tasks=next_tasks,blockers=blockers,gpu_required=False,gpu_status='현재 CPU 기술 준비; GPU 메모리/실행 검증 미실행, 정식 학습 금지',constraints=dict(lora_executed=False,gpu_inference_executed=False,pod_lock_touched=False,stop_touched=False,reserved_evaluatoronly_opened=False))
 for ext in ['json','md']:
  p=d/f'STATUS.{n:03d}.{ext}'
  content=json.dumps(obj,ensure_ascii=False,indent=2)+'\n' if ext=='json' else '\n\n'.join(['# SourceReview v15 RC3 상태',f'현재 단계: {stage}',f'최종 수정: {obj["last_updated_utc"]}','GPU: CPU 준비 단계. 메모리 검증 미실행. 정식 학습/Pod 조작 없음.']+[f'## {h}\n\n'+'\n'.join('- '+v for v in vals) for h,vals in [('완료',done),('실패/보류',held),('파일 경로',obj['file_paths']),('다음 작업',next_tasks),('Blocker',blockers)]])+'\n'
  with p.open('x') as f:f.write(content)
  temp=PROGRESS/f'.STATUS.{ext}.next';temp.symlink_to(p.relative_to(PROGRESS));os.replace(temp,PROGRESS/f'STATUS.{ext}')
 print(json.dumps({'stage':stage,'version':n},ensure_ascii=False),flush=True)
def initialize():
 paths=[RC2/'SHA256SUMS.txt']+[RC2/line.split('  ',1)[1] for line in (RC2/'SHA256SUMS.txt').read_text().splitlines()]
 before=read(RC2/'INPUT_PRESERVATION_BEFORE.json')['files']
 for p,h in before.items():assert sha(p)==h
 for line in (RC2/'SHA256SUMS.txt').read_text().splitlines():
  h,p=line.split('  ',1);assert sha(RC2/p)==h
 put('PRESERVATION_BEFORE.json',{'created_at_utc':now(),'files':{**before,**{str(p):sha(p) for p in paths}}})
 status('RC3_CONTRACT_REVIEW_IN_PROGRESS',['RC2 checksum 확인 및 후속 cpu_rc3 생성'],['학습 release 미승인'],['PRESERVATION_BEFORE.json'],['B01/B02 검토','혼합 exporter/token preflight','DEV 범위·승인 묶음·단일 설정안'],['B03','B04'])
if __name__=='__main__':initialize()
