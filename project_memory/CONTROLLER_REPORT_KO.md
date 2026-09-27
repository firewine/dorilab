# Qwen 검색 제어기 적용 결과

2026-09-27 UTC, **개발·실제 Qwen 연결·RC3 연속 검증 완료**.

## 구현

- `controller.py`: 제한된 search/inspect/finish 계획 실행, schema 검사, 반복·시간·검색 횟수 제한, 오류 시 baseline 복귀.
- `planner_contract.py`: 서비스 소유의 고정 검색 제어 prompt와 SHA256 계약.
- `model_runtime.py`: planner 계약만 상주 Qwen의 base 모드로 생성. PEFT context manager에서 RC3 adapter를 잠시 비활성화하고 정상/예외 종료 후 복구. 단일 generation executor 사용.
- `bridge.py`, `__main__.py`: 제어기 근거를 기존 RC3 observations로 연결. CLI는 기본 qwen, 명시적으로 rules/off 선택 가능.
- 모델 답변을 기억에 자동 반영하지 않으며 요청 간 KV도 공유하지 않는다. 계획 원문과 최종 검토 원문은 별도 증적으로 보존한다.

고정 planner 계약 ID:
`f2d9430c098d13096434f4100b1e507568c8b14da43b360592181e52e17593d3`

검색 제어기에는 다른 프로젝트/scope로 이동하거나 shell·임의 파일·URL·기억 변경을 실행하는 도구가 없다. 생성된 계획의 ID를 검증하고 원문 source hash/snapshot을 다시 대조한다. 모델이 제시하는 충분성은 참고 판단이며 공학 승인으로 취급하지 않는다.

## 검사 결과

| 검사 | 결과 |
|---|---|
| 기억·제어기 CPU 회귀 | 33개 통과 |
| 기존 서비스 회귀 | 4개 통과 |
| 실제 작은 PEFT CPU 모델 | base→RC3 전환, 생성 오류 후 adapter 복구 확인 |
| 실제 Qwen 기본 흐름 | inspect → finish, fallback 없음 |
| 실제 Qwen 재검색 | 첫 검색 근거 없음 → search → inspect → finish, fallback 없음 |
| 실제 최종 검토 | RC3 adapter 활성 상태로 202 → completed |
| 출력·식별자 검사 | 원문 SHA256, native EOS, token 한도, 동일 boot/model receipt, 제공한 근거 ID 확인 |
| 단일 GPU 모델 | nvidia-smi compute process 1개 확인 |

실제 검증은 새 합성 프로젝트 `synthetic-lme-v2`를 사용했다. 재검색 검사는 최초 질의를 일부러 무관하게 지정한 후 Qwen이 scope 관련 검색어를 만들어 3개 pool에서 근거를 다시 찾도록 했다. 학습 정답, gold, 전체 DEV/legacy 데이터는 사용하지 않았다.

기본 흐름의 제어기 시간은 약14.86초, 이어진 RC3 생성은 약5.28초였다. RC3 입력1,753/출력56토큰. 별도 재검색 흐름은 약20.82초였다. 소수 합성 실행의 관측치이며 운영 지연시간 보장이나 벤치마크 점수가 아니다.

RC3 모델 원문을 파싱한 결과:

```json
{"action":"NO_ACTION_REQUIRED","claim_id":"SYN-MEMORY-01","evidence_refs":["MEM-77a2687584ce0260542f7b0a806abcf7"]}
```

## 현재 서비스

| 항목 | 실제 값 |
|---|---|
| PID | 28751 |
| boot_id | `6ded0350-ad57-4b92-932b-78d1668029ba` |
| 주소 | `127.0.0.1:8080` |
| /health, /readyz | 모두200, ready |
| GPU 사용량 | 55,666 MiB, PID28751 한 개 |
| model receipt | `b96e72897a27c3a6a0eee4db7c04d55efba10bbd373efe0a83f56221d8a2a847` |
| 로그 | `/workspace/dorilab/inference/run/server-20260927T101526Z.log` |

서비스 프로세스만 한 번 교체했다. 종료 직후 TIME_WAIT 때문에 첫 launcher가 기동을 보류했고, listener 부재를 확인한 뒤 기존 launcher로 재시도해 정상 준비됐다. 다른 프로세스를 종료하거나 launcher 충돌 검사를 우회하지 않았다. Pod 재시작, Start Command 변경, 모델 다운로드, 재학습, adapter merge, GPU 런타임 업그레이드는 하지 않았다. API lock 검사에서 기존 패키지 유지와 pip check 통과를 확인했다.

## 증적과 제한

`artifacts/controller_v1/verification.json`에 최종 검증 항목과 상태가 있다.

- `cpu_tests.log`, `service_tests.log`: CPU/mock 회귀 결과
- `live_plans/*/result.json`: 실제 Qwen base 계획 원문, token 수, 종료 이유, 지연시간, 실행 모드
- `live_review/`: 기억 묶음, RC3 요청·202·결과·receipt
- `requery.json`, `requery_plans/`: 실제 검색어 변경과 원문 확인 증적
- `prechange/`, `service_before.json`: 적용 전 코드와 서비스 identity

현재 검색기는 BM25+한국어 bigram이다. Qwen이 pool별 질의를 계획하고 원문 확인·종료를 결정한다. 공식 AgentRunbook의 dense retrieval/멀티모달 데이터 처리까지 재현한 것은 아니며 공식 LongMemEval-V2 점수를 측정하지 않았다.

계획 생성도 서버의 일반 generation job 한 개를 소비한다. 기존 boot당256 job 제한이 유지되므로 한 번의 사용자 검토에 여러 job이 사용될 수 있다. 전체 제어기 기본90초 제한과 planner output384토큰 제한을 지킨다. timeout 시 접수된 job이 아직 실행 중이면 다음 요청은429가 될 수 있으므로 accepted ID를 확인하고 자동 재제출하지 않는다.

Mac 연결은 아직 실기 검증하지 않았다. 현재 RunPod 내부 검증만 완료했으며 서비스는 기동 상태로 유지한다. [실행 방법](CONTROLLER_KO.md)을 참고한다.
