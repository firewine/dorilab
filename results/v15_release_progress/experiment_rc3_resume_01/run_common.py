import datetime,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path('/workspace/dorilab');RUN=pathlib.Path(__file__).resolve().parent
RC3=RUN.parent/'cpu_rc3';PRIOR=RUN.parent/'experiment_rc3_01'
RECOVERY=ROOT/'runtime/recovery_rc3_20260926_01'
RELEASE=PRIOR/'release/RELEASE_MANIFEST.json'
SNAPSHOT=pathlib.Path('/root/hf-cache/hub/models--Qwen--Qwen3.8-27B/snapshots/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0')
PY='/root/venvs/dorilab-tournament/bin/python'
sys.path.insert(0,str(RC3))
from common import sha,read,digest,rows,now
from exporter import verify_training_release,require
os.environ.update(TMPDIR='/root/tmp',PIP_CACHE_DIR='/root/pip-cache',HF_HOME='/root/hf-cache',HF_HUB_CACHE='/root/hf-cache/hub',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
def save(name,obj):
    path=RUN/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def append(name,obj):
    with (RUN/name).open('a') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def status(stage,done,held=(),blockers=(),steps=0):
    p=RUN.parent;d=p/'status_versions';n=max(int(x.name.split('.')[1]) for x in d.glob('STATUS.*.json'))+1
    o=dict(version=n,current_stage=stage,last_updated_utc=now(),release_directory=str(RUN),completed_items=list(done),failed_or_held_items=list(held),
      file_paths=[str(RUN),str(RECOVERY),str(RELEASE)],next_tasks=['승인된 GPU 검증/base/LoRA 1회/저장 및 reload 평가 순서로 진행; 오류 시 기록 후 중단'],gpu_required=True,blockers=list(blockers),optimizer_steps=steps,
      prior_stopped_result=str(PRIOR/'FINAL_RESULT.json'),pod_lock_touched=False,stop_touched=False,reserved_evaluatoronly_opened=False)
    for ext,txt in [('json',json.dumps(o,ensure_ascii=False,indent=2)),('md','\n\n'.join(['# RC3 승인 실험 재개','현재 단계: '+stage,'최종 수정: '+o['last_updated_utc'],'GPU 필요: 예','완료: '+'; '.join(done),'보류/실패: '+'; '.join(held),'파일: '+'; '.join(o['file_paths']),'다음: '+o['next_tasks'][0],'Blocker: '+'; '.join(blockers),f'실제 optimizer step: {steps}']))]:
      q=d/f'STATUS.{n:03d}.{ext}'
      with q.open('x') as f:f.write(txt+'\n')
      tmp=p/f'.STATUS.{ext}.resume-next';tmp.symlink_to(q.relative_to(p));os.replace(tmp,p/f'STATUS.{ext}')
    print(stage,flush=True)
def gate():
    require(sys.executable==PY and sys.prefix=='/root/venvs/dorilab-tournament','explicit fixed runtime required')
    require(read(RECOVERY/'RUNTIME_READY.json')['status']=='READY','runtime not ready')
    require(sha(RELEASE)=='c805c403585a000191e9456f35d581051732c0b9484eb25ffe99023cf4a90d70','release manifest mismatch')
    rel,rec=verify_training_release(RELEASE)
    require(sha(rel['data_path'])=='e1015b2f04051a50e8691afde069d143e623c2fdfe2c00c1f77e5a0275df76b6','release data mismatch')
    return rel,rec,read(RC3/'LORA_SINGLE_CONFIG.json')
def memory(torch):
    torch.cuda.synchronize();free,total=torch.cuda.mem_get_info()
    return dict(allocated=torch.cuda.memory_allocated(),reserved=torch.cuda.memory_reserved(),peak_allocated=torch.cuda.max_memory_allocated(),peak_reserved=torch.cuda.max_memory_reserved(),device_free=free,device_total=total)

