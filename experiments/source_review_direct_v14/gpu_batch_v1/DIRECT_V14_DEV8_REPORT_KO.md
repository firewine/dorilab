direct_v14 DEV8을 지정 GPU 환경에서 한 번 실행하여 8건 모두 정상 보존했다. 출력 필드 계약 오류는 4→0건, 기존 scorer의 check_answer 통과는 4/8→8/8로 바뀌었다. **strict는 3/8→3/8로 그대로다.** 출력 안내 수정의 관측 효과는 이번 DEV8의 필드 계약 준수 개선이며 의미 판단·strict 개선으로 확대하지 않는다.

사용자의 마지막 지시에 따라 Pod 잠금을 변경하지 않았고 STOP·STOP 재시도를 실행하지 않았다. Pod는 조회 결과 RUNNING이다. 다른 설정 변경·리셋·DELETE/TERMINATE도 실행하지 않았다. 중지와 잠금 관리는 사용자가 별도로 처리한다.

실행과 보존

- 모델: Qwen/Qwen3.8-27B, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- `/root/hf-cache`에 필요한 가중치18개·설정10개, 총 55,586,036,499 bytes를 복원했다. 28개 모두 기존에 기록된 SHA256/크기와 일치했다. 복원 전 `/root` 가용 공간은 약168.7GB였고 필요한 용량은 약55.6GB였다. 기존 파일을 삭제하지 않았다. main/다른 revision/다른 모델을 받지 않았다.
- 생성 Python: `/root/venvs/dorilab-tournament/bin/python`. Transformers 5.18.0.dev0 / commit `002e1edf5b5198488297f401dd853056b6521d02`, torch2.8.0+cu128, CUDA12.8, PEFT0.21.0, accelerate1.15.0을 확인했다.
- BF16, SDPA, greedy, seed42, enable_thinking=false, 응답384/전체2048, native template를 유지했다. adapter 없이 base 전체 frozen 상태로 생성했다. LoRA·ledger·constrained decoding·출력 보정·추가 모델 실험은 없었다.
- 완료한 CPU token 검사는 다시 실행하지 않았다. GPU에서만 필수 입력 대조를 수행했다. 입력 hash, prompt hash, tokenizer/template hash, 렌더링 문자열과 입력 token ID 전체가 보존된 CPU 사전검사와 정확히 일치했다. 최대 입력1628+384=2012였다.
- 실제 준비된 `execute_once.py` → `run_direct_v14_checked.py` 경로를 한 번 실행했다. 기존 생성 코드 부분은 변경하지 않았다. launch 명령·현재 Pod ID는 control/LAUNCH.json에 남겼다. 8개 case ID가 정확히 한 번씩 저장됐고 종료코드는0, pending case0, 부분 JSON0, 자동 재시도0이다.
- 원문 출력 SHA256: `c7945aa970aa327524538286ded154be1e760e3dc2e79b98ba00787af03f6a7e`. 이 hash를 gold 결합 전에 봉인했다. 이후 `/tmp/sr14_cpu_env/bin/python`의 별도 CPU 프로세스로 새 raw 출력만 채점했다. GPU 생성에 CPU 환경을 사용하지 않았다.
- 과거 v13 결과는 재추론·재채점하지 않고 저장된 RAW_OFFICIAL_CASE_RESULTS를 비교 기준으로 읽었다. 기존 원본·준비 파일223개 및 봉인된 CPU 산출물 hash가 그대로다.

기존 대비 비교

| 항목 | 기존 direct_v13 | 새 direct_v14 |
|---|---:|---:|
| JSON 유효 | 8/8 | 8/8 |
| 기존 check_answer 통과(schema_valid) | 4/8 | 8/8 |
| OUTPUT_CONTRACT_FIELD_ERROR | 4/8 | 0/8 |
| reason_code key 사용 | 4/8 | 0/8 |
| 파싱된 Action 일치 | 8/8 | 8/8 |
| schema 통과 후 Action 일치 | 4/8 | 8/8 |
| reason 적용대상 | 4건 | 4건 |
| reason 평가 가능 | 0/4(schema 실패) | 4/4 |
| reason 결과 | 미평가4 | 후보와 일치1 / 불일치3 |
| reference exact | 일치3 / 불일치1 / 미평가4 | 일치6 / 불일치2 / 미평가0 |
| strict | 3/8 | 3/8 |
| 응답 token 한도 도달 | 0/8 | 0/8 |
| 생성 시간 총합 | 38.684초 | 39.785초 |
| 입력 token 합계 | 10505 | 12561 |
| 출력 token 합계 | 694 | 674 |

reason의 과거 미평가를 의미 오답으로 바꾸지 않는다. 새 실행에서 세 건이 미승인 후보 reason 분류와 불일치함을 관측했지만 이를 과거 대비 의미 회귀로 집계하지 않는다. reference의 미평가4건이 평가 가능해진 것과 실제 reference 판단 개선도 구분한다. 새 scorer의 strict 성공 사례는 기존과 같은 세 건이다. strict 개선0·회귀0이다. schema 개선은 ec0f24fd6c, f49f3d339e, 18d7b891b1, b40f92306b 네 건이며 schema 회귀는 없다.

사례별 상세

| case_id | JSON | check_answer | 필드 오류 | 파싱 Action/계약 후 Action | reason | reference | strict | 변화 | 생성초 | 입력/출력 token |
|---|---|---|---|---|---|---|---|---|---:|---:|
| CASE-8261f9621f | 통과 | 통과 | 없음 | 일치/일치 | 비적용 | 불일치 | 실패 | 동일 | 4.345 | 1609/62 |
| CASE-ec0f24fd6c | 통과 | 통과 | 없음 | 일치/일치 | 후보와 불일치 | 일치 | 실패 | schema 개선; strict 동일 | 5.385 | 1628/93 |
| CASE-f49f3d339e | 통과 | 통과 | 없음 | 일치/일치 | 후보와 일치 | 불일치 | 실패 | schema 개선; strict 동일 | 5.382 | 1598/93 |
| CASE-18d7b891b1 | 통과 | 통과 | 없음 | 일치/일치 | 후보와 불일치 | 일치 | 실패 | schema 개선; strict 동일 | 5.342 | 1534/92 |
| CASE-5bf8af5346 | 통과 | 통과 | 없음 | 일치/일치 | 비적용 | 일치 | 통과 | 동일 | 4.494 | 1535/76 |
| CASE-d48966c293 | 통과 | 통과 | 없음 | 일치/일치 | 비적용 | 일치 | 통과 | 동일 | 4.282 | 1628/73 |
| CASE-b40f92306b | 통과 | 통과 | 없음 | 일치/일치 | 후보와 불일치 | 일치 | 실패 | schema 개선; strict 동일 | 6.249 | 1514/111 |
| CASE-a18319c1d2 | 통과 | 통과 | 없음 | 일치/일치 | 비적용 | 일치 | 통과 | 동일 | 4.306 | 1515/74 |

CASE-8261f9621f는 source reference 누락이 그대로 남았다. CASE-f49f3d339e는 필드 계약을 통과하고 reason은 후보와 일치하지만 source reference 누락으로 strict 실패했다. CASE-ec0f24fd6c, CASE-18d7b891b1, CASE-b40f92306b는 필드 계약과 reference를 통과했으나 reason이 허용 후보 분류와 달라 strict 실패했다. 나머지 세 건은 기존과 동일하게 strict 통과했다.

`schema_valid`는 기존 packtool.check_answer 결과라는 정의를 유지했다. 문서 JSON Schema와 scorer의 차이는 이번에 수정하지 않았다. 문서 schema는 선택 requested_evidence에도 minItems1을 적용하지만 check_answer는 REQUEST_EVIDENCE에만 비어 있지 않은 요청을 강제한다. 또한 정적 schema에 없는 실제 제공 ID·claim_id 일치 검사는 check_answer가 수행한다. 추가 필드 진단은 공식 scorer를 대체하지 않는다.

새 생성 시간은 약1.100초 증가했다. 입력 길이와 실행 시점의 영향이 있으므로 한 번의 실행으로 속도 향상·저하의 일반적 결론을 내리지 않는다. 로딩 12.364초, runner 전체 56.315초다. 이미지 processor docstring 경고와 최적화 kernel 부재 경고 등 실제 로그는 그대로 보존했으며 숨기거나 재실행하지 않았다.

후보 정답은 SOURCE_GROUNDED_AI_CANDIDATE, human_review_performed=false, training_eligible=false이다. DEV8은 이미 관측한 한 출처·두 관련 family의 출력 안내 진단이며 독립 일반화 평가나 학습 데이터가 아니다. 이번 결과로 추가 학습 필요성을 입증했다고 결론 내리지 않는다. 추가 추론·학습을 시작하지 않고 대기한다.

산출물 위치

- [원문 출력](../runs/direct_v14_checked_01/predictions.jsonl)
- [실제 렌더링·입력 token ID](../runs/direct_v14_checked_01/actual_model_inputs.jsonl)
- [GPU/CPU 대조 결과](../runs/direct_v14_checked_01/TOKEN_PREFLIGHT.json)
- [실행 manifest](../runs/direct_v14_checked_01/RUN_MANIFEST.json), [출력 봉인](../runs/direct_v14_checked_01/OUTPUT_SEAL.json)
- [완료·재개 정보](../runs/direct_v14_checked_01_control/COMPLETION.json), [실행 로그](../runs/direct_v14_checked_01_control/run.log)
- [사례별 새 채점](../runs/direct_v14_checked_01/comparison/CASE_RESULTS.jsonl), [사례별 비교](../runs/direct_v14_checked_01/comparison/CASE_COMPARISON.jsonl), [집계](../runs/direct_v14_checked_01/comparison/SUMMARY.json)
- [가중치 복원 기록](MODEL_CACHE_RESTORE.json), [GPU 환경](audit/GPU_ENVIRONMENT.json), [현재 Pod 상태](audit/POD_STATE_AFTER_BATCH.json)

RUN_MANIFEST의 STARTED는 실행 시작시 작성된 원본으로 보존했고, 최종 완료 여부는 control/COMPLETION.json과 OUTPUT_SEAL.json이 기록한다. 완료 상태를 덮어쓰거나 과거 실패를 지우지 않았다. Mac 회수는 연결 정보가 없어 미수행이며, 모든 결과를 /workspace에 저장하고 checksum을 검증했다. Pod 중지는 사용자 지시로 수행하지 않았다.
