"""Finalize the CPU review snapshot and seal it without touching prior runs or pod state."""
from pathlib import Path
from build_release import ROOT, OUT, PROGRESS, RC1, PACK, read, sha, write, textfile, status, now

def main():
    validation=read(OUT/'CPU_VALIDATION.json')
    assert validation['status']=='PASS_CPU_ARTIFACT_VALIDATION'
    before=read(OUT/'INPUT_PRESERVATION_BEFORE.json')['files']
    after={p:sha(p) for p in before};assert before==after
    write('INPUT_PRESERVATION_AFTER.json',{'checked_at_utc':now(),'tracked_file_count':len(before),'all_preserved':True,'files':after,
          'scope':'Same explicit allowlist as BEFORE. No recursive reading of reserved/evaluator/pod-control paths.'})
    model_path=ROOT/'results/source_review_v13_qwen27/model_lock_assets/MODEL_LOCK.json'
    model=read(model_path)
    readiness={'created_at_utc':now(),'state':'NOT_READY_FOR_TRAINING_OR_NEW_GPU_EVALUATION','cpu_release_review_complete':True,
               'model_identity_from_existing_artifact':{'path':str(model_path),'sha256':sha(model_path),'model':model['model'],'revision':model['revision']},
               'counts':read(OUT/'TRAIN_RELEASE_CANDIDATE_v15.json')['counts'],'dev_source_ready':16,'dev_reason_review_held':1,
               'blocking_decisions':['B01_GENERAL_SPECIFIC_REASON','B02_ANALYSIS_FIELD_ALIAS','B03_EXISTING_RELEASE_GATES','B04_EXPORT_AND_PREFLIGHT','B05_DEV_GENERAL_SPECIFIC_REASON'],
               'training_configuration_frozen':False,'configuration_freeze_condition':'Resolve content/release blockers, implement/check the native-message export and preflight; then freeze and report ONE configuration before training.',
               'future_configuration_fields':['approved membership and data hash','LoRA rank/alpha/dropout/target_modules','optimizer/lr/scheduler/warmup','batch/accumulation/epochs/max_steps','seed/precision/max_length/packing','assistant loss mask/EOS','base/adapter DEV16 comparison conditions'],
               'authorized_scope':'Current Pod may run necessary GPU validation once prerequisites are met. No additional model comparison, sweep, DPO/RL or new prompt search.',
               'pod_stop_or_lock_change_authorized':False,'model_loaded':False,'training_executed':False,'gpu_inference_executed':False,
               'reason_execution_not_started':'Content and output-contract release prerequisites are unresolved, not lack of CPU/GPU availability.'}
    write('FIRST_QWEN27_LORA_READINESS.json',readiness)
    textfile('RELEASE_BLOCKERS_KO.md',f'''# SourceReview v15 release blockers — RC2

최종 판정 시각: {now()}. CPU 검토 완료와 학습 실행 준비 완료를 구분한다. 현재 실행 가능한 SFT는 **0행**이다. 상한206행 중 이번 행 단위 검사에서 blocker 미발견은185행, 잠정보류는21행이다. DEV16은 원문 확보가 완료됐으나 reason 중첩 1건과 기존 검토 gate가 남는다.

| ID | 범위 / 상태 | 실제 근거 | 해소 조건 |
|---|---|---|---|
| B01_GENERAL_SPECIFIC_REASON | legacy physics 1행, 잠정 | PHY-EE02-P01-A: legacy 일반 코드는 source 방법 위반까지 포함; v15는 구체 코드 우선. 자극 중 변화+사후 복구를 무사건으로 해석한 제안 | 기존 reason 유지 또는 method reason 적용의 근거 판정. 변경/포함 결정은 새 버전으로 기록 |
| B02_ANALYSIS_FIELD_ALIAS | contract20행, 잠정. 별도10행 warning | 실제 user는 requirement_s, system은 required_s. 10 CALL_TOOL과 10 CURRENT-result NO_ACTION은 alias/우선순위에 따라 다른 Action 가능 | alias 및 missing-input/CURRENT 우선순위 판정. 기존 label 자동 수정 금지 |
| B03_EXISTING_RELEASE_GATES | TRAIN 후보 전체 / DEV 평가 후보 | RC1 후보의 training_eligible=false, 충분 reference approved=false; 승인 identity/time/hash 없음 | 실제 현행 후보에 대한 source·case·정책·실험 사용 검토와 hash 결합. 사람 이름/시각/승인 이력 생성 금지 |
| B04_EXPORT_AND_PREFLIGHT | 실행 경로 미완료 | 기존 v13 exporter는 TRAIN 전체와 direct_v13 공통 system을 사용하며 혼합206 및 family 보류를 처리하지 않음 | 승인된 membership만 native system/user/assistant로 export, conversation 경계·assistant-only loss/EOS·token 길이 검사. 그 후 필요한 같은-Pod GPU 검증 및 단일 설정안 고정/보고 |
| B05_DEV_GENERAL_SPECIFIC_REASON | DEV1행, 잠정 | CASE-RC1-1a26698cec의 알려진 restraint 변화 배제에 TEST_ARTIFACT_UNMODELED 적용 가능; 현행 일반 reason과 중첩 | reason fallback 타당성 검토 후 필요 시 새 DEV freeze. CHALLENGE Action/기존 label 자동 수정 없음 |

B01/B02의 사례별 실제 system/user/assistant는 [메시지 감사](LEGACY_V15_MESSAGE_AUDIT.json), 정의·출력 계약 차이는 [호환성 보고서](LEGACY_V15_COMPATIBILITY.md)에 있다. B05의 원문/입력 관계는 [DEV16 보고서](DEV16_SOURCE_RELEASE_CANDIDATE.md)와 [의미 검토](dev16/SEMANTIC_REVIEW_RC2.json)에 있다. 잠정 blocker는 확정 오답 판정이 아니다.

B03은 이번 작업에서 새로 만든 승인 정책이 아니다. 기존 [packtool.py](/workspace/dorilab/research/DoriLab_SourceReview_v13/packtool.py:215)의 `export_sft`는 source_program_split_audit_pass, legacy_corpus_audit_pass, candidate_label_policy_accepted, approved_training_experiment 및 reviewer/reviewed_at을 요구한다. source content/rights/split 승인과 case의 APPROVED_FOR_TRAINING, 현행 case/gold hash도 요구한다. 이 v13 exporter를 RC2에 그대로 실행할 수 있다는 뜻은 아니며, 후속 RC2 exporter에서 이 gate를 우회하지 않아야 한다.

## 명시적 보류와 해소된 항목

- 사용자 지시의 SR13-TIRS-BASELINE / SR13-NEA-TRANSLATION / SR13-RHOBC-BOOT, 각4건 총12건은 206행 manifest에서 제외했다. 이 보류를 자동 해제하지 않는다.
- CANYVAL/PROBA-V source-unavailable 문제는 실제 PDF HTTP200 재확보·DOI/본문 검증으로 해소했다. 대체 source 후보를 추가할 필요가 없다.
- contract150의 v15와 다른 Action·필드, physics 전용 reason은 원래 system 라우팅 아래 유효한 계약 차이다. 단순 enum 차이로 모두 blocker 처리하지 않았다.
- 185행을 임의로 실제 학습 subset으로 확정하지 않았다. 기존 RC1의205행 선정 이력도 그대로 보존한다.
- 공개 TRAIN/DEV/legacy metadata의 source/program/family 중복 검사는 통과했다. 접근하지 않은 외부 corpus나 evaluator 자료에 대한 전체 독립성은 주장하지 않는다.

## 다음 작업 순서

1. B01/B02/B05를 현재 메시지·본문 근거로 판정하고 membership/label이 바뀌면 새 버전과 freeze를 만든다.
2. B03의 실제 release 검토 기록을 현행 hashes에 연결한다.
3. B04의 혼합 계약 export 및 CPU token/loss/EOS 검증을 완료한다. 필요한 GPU 검증은 준비 조건을 충족한 뒤 현재 Pod에서 수행 가능하다.
4. 첫 Qwen27 단일 LoRA의 데이터 hash·rank/alpha/dropout·target modules·optimizer/LR·batch/steps·precision/seed·평가 조건을 고정하여 먼저 보고한다. 현재는 학습 가능한 상태가 아니므로 이 설정의 최종 고정도 보류한다.

이번에 LoRA 학습, GPU 추론, 추가 모델 비교, sweep, DPO/RL, prompt 탐색은 실행하지 않았다. Pod lock/STOP은 읽거나 변경하지 않았고 Pod 중지 요청도 하지 않았다.
''')
    textfile('CPU_STAGE_FINAL_REPORT_KO.md',f'''# SourceReview v15 CPU 단계 최종 보고 — RC2

작성 시각: {now()}. **요청한 CPU release candidate 산출물을 새 버전으로 저장했다. 실행 준비 상태는 BLOCKED이며 학습·추론은 시작하지 않았다.** CPU/GPU 부족을 이유로 멈춘 것이 아니며 남은 조건은 데이터/출력 계약과 release 검토다.

| 수량 구분 | contract | legacy physics | 새 TRAIN | 합계 |
|---|---:|---:|---:|---:|
| 요청 상한 manifest |150|20|36|206|
| 행 단위 잠정 compatibility 보류 |20|1|0|21|
| 이번 행 단위 검사에서 blocker 미발견 |130|19|36|185|
| 현행 release gate를 통과한 실행 가능 행 |0|0|0|0|

185행은 학습 승인이나 확정 SFT 크기가 아니다. 206행 전부를 manifest에 남겨 각 blocker를 추적한다. 사용자 보류 3 family ×4 =12건은 별도 excluded 목록으로 보존한다. 반복 횟수는 후보 member당1회이다. epoch/학습 step은 아직 정하지 않았다. RC1의205행 선정안과 parent218을 덮어쓰지 않았다.

## 호환성 결과

legacy 실제 system/user/assistant170행과 v15 실제 system/user 및 candidate expected36행을 대조했다. legacy system5종과 v15 system1종을 구분했다. 동일 system+user에 다른 target이 연결된 그룹은0개였다. 메타데이터 버전만 보는 검사로 대체하지 않았다.

- PHY-EE02-P01-A의 일반/방법 reason 경계1건을 계속 잠정 보류했다.
- Analysis 입력의 requirement_s와 system의 required_s 간 미선언 alias를 발견했다. 10 CALL_TOOL과10 NO_ACTION_REQUIRED는 Action 또는 지시 우선순위가 달라질 수 있어 잠정 보류했다. 다른10 REQUEST_EVIDENCE는 양쪽 해석의 Action이 같아 warning으로 남겼다.
- contract Action/필드 및 legacy 고유 reason 차이는 원래 system을 보존하는 조건으로 구분했다. 자동 relabel·필드 추가·prompt 변경은 하지 않았다.

## DEV16 원문 결과

CANYVAL 25쪽 PDF와 PROBA-V 15쪽 PDF를 실제 공개 asset URL에서 재확보했다(둘 다 HTTP200). 제목·DOI·본문을 확인했고 SHA256은 기존 RC1과 일치했다. 40쪽을 새로 추출하고6개 fact의8개 anchor를 검증했다. 대체 source는 불필요하다.

DEV16은 기존 RC1의 input/label/metadata/prompt bytes를 유지한 새 snapshot이다. 방법 의존8건과 관측 충분 대조8건이며 공개 TRAIN/legacy metadata 범위에서 source/program/family 교집합0을 재확인했다. 검색 snippet으로 label을 승인하지 않았다. CANYVAL 인과 판단1건의 일반 reason과 TEST_ARTIFACT_UNMODELED 중첩 가능성은 B05로 남겼다. 원문 확보16건과 평가 승인16건을 혼동하지 않는다.

## 검증·보존

- CPU 검사 **{validation['tests_run']}개 PASS**, 실패0/오류0. Membership, 전체 family 제외, 실제 legacy assistant 보존, candidate target binding, blocker 영향 범위, source bytes/anchor, DEV freeze/split, 입력 정답 분리, reference 경계, 기존 입력 hash를 확인했다.
- 이번에 명시적으로 추적한 기존 입력/RC1 파일 **{len(before)}개**의 전후 SHA256이 일치한다. 기존 raw output·점수·학습 데이터는 수정하지 않았다.
- 최종 산출물 SHA256은 `SHA256SUMS.txt`와 `CHECKSUM_VERIFICATION.json`에 기록한다. Checksums는 CPU 산출물의 무결성 증거이며 label 의미 승인이나 모델 성능 증거가 아니다.
- 기존 상태를 덮어쓰지 않도록 각 단계는 `../status_versions/STATUS.NNN.md/json`에 저장했다. 요청 경로 STATUS.md/STATUS.json은 최신 immutable snapshot을 가리키는 symlink다. 이 릴리스에는 최종 상태 snapshot과 상태 이력 hash도 포함했다.

## 산출물

1. [TRAIN_RELEASE_CANDIDATE_v15.json](TRAIN_RELEASE_CANDIDATE_v15.json)
2. [LEGACY_V15_COMPATIBILITY.md](LEGACY_V15_COMPATIBILITY.md)
3. [DEV16_SOURCE_RELEASE_CANDIDATE.md](DEV16_SOURCE_RELEASE_CANDIDATE.md)
4. [RELEASE_BLOCKERS_KO.md](RELEASE_BLOCKERS_KO.md)
5. [CPU_STAGE_FINAL_REPORT_KO.md](CPU_STAGE_FINAL_REPORT_KO.md)
6. [SHA256SUMS.txt](SHA256SUMS.txt)

보조 증거: [실제 메시지 감사](LEGACY_V15_MESSAGE_AUDIT.json), [CPU 검증](CPU_VALIDATION.json), [원문 검증](sources/PRIMARY_SOURCE_VERIFICATION.json), [DEV16 freeze](dev16/PRE_OUTPUT_FREEZE_RC2.json), [학습 준비 상태](FIRST_QWEN27_LORA_READINESS.json).

읽기 전용 재검증:

```sh
python3 -m unittest discover -s /workspace/dorilab/results/v15_release_progress/cpu_rc2 -p validate_release.py -v
sha256sum --check --quiet /workspace/dorilab/results/v15_release_progress/cpu_rc2/SHA256SUMS.txt
```

두 번째 명령은 `cpu_rc2` 디렉터리를 작업 경로로 사용한다. build/review/seal 스크립트는 생성 이력을 보존한 것으로, 완료 디렉터리에 재실행하면 exclusive-write 보호로 중단한다. 변경 시 새 revision을 만든다.

## 첫 Qwen27 LoRA 준비 상태와 대기

기존 모델 고정값은 `{model['model']}` / `{model['revision']}`이며 로드하지 않았다. 구체적인 rank/LR/step 등의 학습 설정은 데이터·평가·export 준비 조건이 끝나기 전에 최종 고정하지 않았다. B01/B02/B05 판정, 기존 검토 gate, native-message exporter와 token/loss/EOS 검사가 끝나면 **단일 설정안을 먼저 고정해 보고**한다. 승인되지 않은 추가 모델 비교·sweep·DPO/RL·새 prompt 탐색은 실행하지 않는다.

현재 단계는 CPU 산출물 저장 후 대기다. 같은 Pod의 CPU/GPU는 후속 준비 조건 충족 시 사용 가능하다. 이번에 LoRA·GPU 추론은 실행하지 않았고 RESERVED/EvaluatorOnly를 열지 않았으며 Pod lock과 STOP도 건드리지 않았다.
''')
    required=['TRAIN_RELEASE_CANDIDATE_v15.json','LEGACY_V15_COMPATIBILITY.md','DEV16_SOURCE_RELEASE_CANDIDATE.md','RELEASE_BLOCKERS_KO.md','CPU_STAGE_FINAL_REPORT_KO.md','SHA256SUMS.txt']
    for name in required[:-1]:assert (OUT/name).is_file()
    # Validate every current payload before publishing the final status.
    payloads=sorted(p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    provisional={str(p.relative_to(OUT)):sha(p) for p in payloads}
    assert all(sha(OUT/p)==h for p,h in provisional.items())
    status('CPU_STAGE_COMPLETE_WAITING_RELEASE_BLOCKERS',
           ['CPU 산출물 6종 및 보조 증거 새 RC2 저장','상한206 / TRAIN 잠정보류21 / 행 blocker 미발견185 / 현재 실행가능0 확정','CANYVAL/PROBA-V 원문 재확보, DEV16 새 source freeze','CPU 10/10 PASS, 기존 추적파일 전후 hash 일치'],
           ['B01: legacy physics reason 경계1건','B02: Analysis alias/우선순위20건; 추가10건 warning','B05: DEV reason 경계1건','B03/B04: 기존 release gate, native exporter·token/loss/EOS 검증 미충족','학습 설정안 최종 고정·LoRA/GPU 실행은 준비 조건 충족 전 보류'],
           [str(OUT/name) for name in required]+[str(OUT/'FIRST_QWEN27_LORA_READINESS.json')],
           ['B01/B02/B05 판정과 실제 release 검토를 새 버전에 연결','native-message export·CPU preflight 완료 후 필요한 GPU 검증','실행 가능 상태가 되면 첫 Qwen27 LoRA 단일 설정안을 먼저 고정·보고','현재 Pod 유지, CPU 산출물 저장 후 대기'],
           ['B01_GENERAL_SPECIFIC_REASON','B02_ANALYSIS_FIELD_ALIAS','B03_EXISTING_RELEASE_GATES','B04_EXPORT_AND_PREFLIGHT','B05_DEV_GENERAL_SPECIFIC_REASON'])
    for ext in ['md','json']:
        textfile(f'STATUS_FINAL_SNAPSHOT.{ext}',(PROGRESS/f'STATUS.{ext}').read_text())
    histories=sorted((PROGRESS/'status_versions').glob('STATUS.*'))
    write('STATUS_HISTORY.json',{'created_at_utc':now(),'latest_status_version':read(PROGRESS/'STATUS.json')['version'],'immutable_revisions':{str(p):sha(p) for p in histories},'stable_paths_are_symlinks':True})
    write('CHECKSUM_VERIFICATION.json',{'checked_at_utc':now(),'status':'PASS','method':'SHA256 each final payload; after creating SHA256SUMS, re-read each listed file and assert hash equality. Independent sha256sum --check follows.',
          'self_inclusion_rule':'SHA256SUMS.txt excludes itself. Python __pycache__ files are non-deliverable caches and excluded. Final status snapshot is included; future status updates do not change this release.',
          'prior_tracked_files_preserved':len(before),'cpu_tests_passed':validation['tests_run']})
    payloads=sorted(p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='SHA256SUMS.txt')
    textfile('SHA256SUMS.txt',''.join(f'{sha(p)}  {p.relative_to(OUT)}\n' for p in payloads))
    for line in (OUT/'SHA256SUMS.txt').read_text().splitlines():
        h,name=line.split('  ',1);assert sha(OUT/name)==h,name
    assert all((OUT/n).is_file() for n in required)
    print({'status':'CPU_COMPLETE_WAITING','sha256_files':len(payloads),'original_files_preserved':len(before),'release_directory':str(OUT)})

if __name__=='__main__':main()
