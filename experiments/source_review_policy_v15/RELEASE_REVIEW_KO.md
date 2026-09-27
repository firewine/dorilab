# SourceReview v15 릴리스 검토안

상태: **POST_OUTPUT_AI_DRAFT / NOT_RELEASED**. 이번 결과는 정책·label·학습 membership 제안이다. 기존 v13/v14는 변경하지 않았고, 모델 출력의 새 점수는 만들지 않았다. 출력 관측 후의 AI 검토이므로 독립 사람 승인으로 간주하지 않는다.

## 사용자가 결정할 항목

| 항목 | 제안 | 승인 전 남은 판단 |
|---|---|---|
| reason 분류 | Action 먼저, 구체 코드 우선, 일반 코드는 fallback | [POLICY_v15.md](POLICY_v15.md) R1~R4 승인. 모델/실험 범위 및 신호→물리량 변환을 포함한다는 명시적 v15 개정 |
| AS_RUN 적용 범위 | 물리 시험뿐 아니라 계산 실행 결과 결손 포함 | 계산 run까지 포함하는 정의와 아래 7건 변경을 승인할지 결정 |
| 중첩 | 질문에 직접 연결되는 구체 문제로 구분 | CASE-cf088dcb3c mapping/monitoring 미해결. 단일 정답으로 릴리스하지 않음 |
| 인용과 provenance | 판단용 근거와 작성 출처·입력 목록 분리 | 충분 집합을 사례별 승인. source가 항상 필수라는 기존 규칙을 가정하지 않음 |
| 인용 평가 | 순서 무시, 사전 승인된 충분 집합 중 하나와 exact 일치 | 임의 추가 인용 허용 없음. TIRS BASELINE 4건의 원문 필수성을 별도 확인 |
| TIRS 설명 | 질문별 rationale 3건 수정 | Action·관측·계산값 변경 없이 설명만 수정하는 안 검토 |
| 학습 구성 | 150 contract + 20 고유 physics + 새 TRAIN48, 각 1회 | 218행은 후보. 원문/이용권/split/label/legacy 호환성 검토 후 포함을 확정 |

## 범위와 보존

P1~P4를 출발점으로 TRAIN48/DEV24, 18개 family의 네 variant를 모두 비교했다. 구체 reason 보강과 인용 정책을 실패 DEV8 다섯 건에만 적용하지 않았다. 정책은 사례 ID를 조건으로 삼지 않으며, changeset의 ID별 결정은 일반 조항을 사례에 적용한 검토 기록이다.

[변경안 72행](LABEL_CHANGESET_v15.jsonl)은 변경하지 않는 대조 사례와 원문 미확보 사례도 포함한다. 각 행에 원본 case/gold/metadata SHA256, 변경 전후 필드, 정책 조항, 질문·관측·합성 가정, 원문 원리와 기존 span 감사 기록, 판단 이유, 노출·검토 상태를 넣었다. JSON object hash는 UTF-8, ensure_ascii=false, sort_keys=true, 구분자 comma/colon의 canonical 직렬화다. 원본 파일 byte hash는 [보존 목록](PRESERVATION_BEFORE.json)에 별도로 있다.

원본 입력·gold·scorer·prompt·raw output·공식 점수·완료 기록 및 이전 정책 검토 파일을 포함한 336개 추적 파일의 hash가 유지됐다. RESERVED/EvaluatorOnly는 내용도 hash 검사 대상으로도 열지 않았다. 기존 34개 단위검사와 과거 CPU 토큰 검사를 반복하거나 변경하지 않았다. 이번 CPU 15개 검사는 별도 기록이다.

## 바뀌는 reason 후보

다음 7건은 모두 TRAIN이다. DEV8의 기존 canonical reason은 그대로다. 허용 reason을 여러 개로 늘리지 않았다. 표시된 변경은 원본 gold에 적용되지 않았다.

| 사례 | 변경 전 → 변경 후보 | 정책·근거 | 상태 |
|---|---|---|---|
| CASE-acec2b7b89 | SUPPORTING_EVIDENCE_MISSING → AS_RUN_MISSING | R2~R4: A-derived 실행 결과가 없으므로 AS_RUN을 제안한다. 계산 실행 포함 여부는 v15 승인 항목이다. 자료가 모두 있으면 준비 완료다. | HUMAN_REVIEW_PENDING |
| CASE-7e2ce553dd | EVIDENCE_INTERPRETATION_ERROR → MODEL_SCOPE_EXCEEDED | R2~R4: 진동 통과를 진공 구동 실증으로 확장하므로 MODEL_SCOPE를 제안한다. 실증 범위를 한정하는 반대 variant도 함께 확인한다. | HUMAN_REVIEW_PENDING |
| CASE-c51cdfeccd | SUPPORTING_EVIDENCE_MISSING → AS_RUN_MISSING | R2~R4: 해당 설치의 진공 구동 실행 자료 결손은 AS_RUN을 제안한다. 해당 run의 압력/온도/명령/이송이 있으면 준비 완료다. | HUMAN_REVIEW_PENDING |
| CASE-d5e287468e | EVIDENCE_INTERPRETATION_ERROR → MEASUREMENT_MAPPING_MISMATCH | R2~R4: 회전 완료를 별도 물리량인 실제 이송 요구 충족으로 대체하므로 mapping을 제안한다. 유효 encoder의 4 mm 대 12 mm 결손을 보존한다. | HUMAN_REVIEW_PENDING |
| CASE-cf088dcb3c | MONITORING_COVERAGE_INSUFFICIENT → MEASUREMENT_MAPPING_MISMATCH | R2~R4: 이송 측정도 검증된 운동학 대응도 없으므로 mapping과 monitoring이 모두 직접 관련된다. mapping은 후보이나 LABEL_OVERLAP_PENDING으로 보류한다. 이송/명령/보정이 있으면 준비 완료다. | LABEL_OVERLAP_PENDING |
| CASE-6de39fe5d2 | EVIDENCE_INTERPRETATION_ERROR → AS_RUN_MISSING | R2~R4: 승인된 재설계/예정표로 재시험 완료를 주장한다. 현재 질문의 직접 결손인 실행 이력에 따라 AS_RUN을 제안한다. MODEL_SCOPE와 겹치나 실행 기록 결손을 직접 지목할 수 있다. | HUMAN_REVIEW_PENDING |
| CASE-9d61b185f8 | SUPPORTING_EVIDENCE_MISSING → CONFIGURATION_SCOPE_UNRESOLVED | R2~R4: power-control 연결 부재에는 configuration이 구체 적용되므로 일반 missing 대신 후보로 제안한다. fault-clear behavior 결손도 요청에 남기며, 단일 코드 대표성은 사람 검토가 필요하다. | HUMAN_REVIEW_PENDING |

CASE-cf088dcb3c의 mapping은 검토용 대안이며 확정 label이 아니다. 두 구체 코드 중 직접적인 문제가 무엇인지 합의 전에는 제외/대기한다. CASE-9d61b185f8은 연결관계 결손에 구체 코드를 적용하지만 fault-clear behavior도 빠져 있으므로 요청 항목 전체는 보존한다. 단일 코드가 전체 질문을 대표하는지 검토자가 확인해야 한다.

유지한 일반 코드도 검토했다. TIRS as-built 사례는 이미 알려진 구성 차이로부터 방사율을 유일 원인으로 단정한 문제이며 구성 정보 부재는 아니다. RHOBC rail 사례도 연결관계가 명시돼 있고, effects 사례는 두 interruption 관측이 실제로 존재하므로 관측 결손으로 바꾸지 않았다. HYPSO 저온 준비 사례는 측정 **또는** 승인된 검증 외삽이 없다는 질문이므로 특정 실행 결과 결손으로 한정하지 않았다. 원문 미확보 PROBA-V 두 CHALLENGE에는 monitoring 대안을 기록했지만 적용·승인하지 않았다.

## 인용 변경안

원문 감사 자료가 있는 56건(TRAIN48 + DEV8)에 충분 집합 metadata를 제안했다. 기존 `expected.evidence_refs`의 canonical 예시는 유지하고, v15 평가 전용 `reference_requirement`를 교체하는 제안이다. 기존 v13의 required/permitted_extra와 새 sufficient_sets는 다른 계약이므로 기존 scorer에서 그대로 사용하지 않는다.

| 대상 | 건수 | 제안 |
|---|---:|---|
| 관측 자체로 전제가 충분한 TRAIN | 44 | 관련 관측 집합 또는 동일 관측+직접 관련 source 하나 |
| 관측 자체로 전제가 충분한 HYPSO DEV | 8 | 같은 기준 적용. 성공 사례와 불일치 사례 모두 포함 |
| TIRS pre-test 비교 방법 | 4 | 원문의 V.C 비교 방법이 전제라는 보수적 안: 해당 source+관련 관측 필요 |
| CANYVAL/PROBA-V DEV | 16 | SOURCE_UNAVAILABLE, 충분 집합 제안 없음, 기존 필드만 보존 |

전체 52건에 관측만의 집합을 제안한 것은 단순히 gold에서 source를 일괄 삭제한 결과가 아니다. 각 질문/관측과 관련 원리를 확인하고, 의미 없는 문서 인덱스·표지 기록을 제외한 관련 관측을 선택해 기존 supporting observation과도 대조했다. 따라서 기존 gold 선택의 영향을 받은 사후 검토이며 독립적인 새 정답 구축이라고 주장하지 않는다. 각 행의 observation_support와 source_role을 검토할 수 있다. source+관측 집합 역시 해당 원리 하나만 명시적으로 열거하며 모든 source ID를 허용하지 않는다.

준비 여부 사례 중 26건에는 관측만의 집합, TIRS BASELINE 준비 2건에는 방법 source 결합 집합을 제안했다. 후자는 비교 방법이 관측에 충분히 재진술됐다고 보는 검토자가 있을 수 있다. 특히 준비 완료 variant의 관측은 A archive·측정 입력·A-derived run·diff를 모두 기술한다. 이에 source가 실제 필수 전제인지 **미확정 승인 항목**으로 남긴다. 임의로 source 의무를 모든 사례에 확장하지 않는다.

문서 source span과 입력에 제공한 전체 ID 목록은 `system_provenance`에만 보존한다. 모델이 사용한 근거로 표시하지 않는다. sufficient_sets, 정답 reason, rationale은 모델 입력에 들어가지 않는다. 무관 ID, 미제공 ID, 중복, 모든 ID 일괄 인용은 허용하지 않는다. 이번 작업에서 어떤 모델 출력도 이 새 계약으로 채점하지 않았다.

## TIRS rationale 수정문

### CASE-79c814ab47

질문은 제안 자체의 적절성이다. 281/300/319 K의 평균과 300 K 단일 노드의 일치는 유지하되, 제안은 위치별 상관에 사용하기 전에 국소 대응의 미확정을 표시한다. 따라서 이 제안을 반박할 이유가 없어 NO_ACTION_REQUIRED다. 국소 대응 자료가 완비됐다거나 위치별 온도가 일치한다는 결론은 아니다.

### CASE-424419171a

질문은 국소 온도 상관을 위한 입력 준비 여부다. 세 센서 온도와 단일 노드 평균은 있으나 센서 좌표와 모델-센서 샘플링 대응표가 없고 대체 국소 대응도 제공되지 않았다. 필요한 대응 자료가 결손됐으므로 REQUEST_EVIDENCE / MEASUREMENT_MAPPING_MISMATCH로 SENSOR_NODE_MAP을 요청한다. 부적절한 제안이 있었다고 가정해 반박하지 않는다.

### CASE-e00c7fe02d

질문은 입력 준비 여부다. 보정된 국소 온도, 센서 좌표, 모델 샘플링 대응표와 각 대응 위치의 별도 모델 출력이 제공됐다. 해당 비교를 시작할 입력이 있으므로 NO_ACTION_REQUIRED다. 단일 평균으로 국소 차이를 덮었다고 설명하지 않는다. 계산된 일치도, 요구조건 충족 및 공학적 승인은 이 준비 판단의 결론이 아니다.

세 건의 Action, synthetic observations, calculation 레코드는 동일하다. 기존 계산 레코드가 준비 완료 variant의 실제 국소 출력값까지 입증한다고 사용하지 않았다. 현재 자료에서 이를 함께 바꿔야 한다는 결론은 내리지 않았다. 사람이 다른 Action/관측/계산 변경이 필요하다고 판단하면 별도 changeset과 hash를 만들어 재검토해야 한다.

## 학습 포함·제외 후보와 반복

[TRAIN_BUILD_CANDIDATE_v15.json](TRAIN_BUILD_CANDIDATE_v15.json)에 실제 파일/행 인덱스/hash로 membership을 기록했다. 기존 v13에서 보존한 repeat246 구성안을 계승했다. 다른 coverage246나 다른 corpus를 묵시적으로 합치지 않았다.

| 구성 | 원래 occurrence | 고유 상태 해석 | 후보 반복/행 | 현재 상태 |
|---|---:|---|---:|---|
| legacy contract | 150 | 입력 내용 hash 150개. 의미적 독립 상태 수는 미확정 | 각 1회 / 150 | legacy 계약·승인 호환성 검토 대기 |
| legacy physics | 96 | parent_case_id 20개 | 각 1회 / 20 | 대표 행과 과거 검토 이력 재확인 대기 |
| 새 TRAIN | 48 | 질문/variant 상태 48개, 관련 family 12개 | 각 1회 / 48 | 사람 검토 대기; 그중 mapping 중첩 1건 별도 보류 |
| DEV | 24 | 학습 제외 | 0 | DEV8은 error-informed regression, 나머지 16은 원문 미확보 |

legacy physics는 기존에 3회 반복 2상태, 4회 6상태, 5회 6상태, 6회 6상태로 96행이었다. 후보는 대표 20행만 선택하고 나머지 76 occurrence는 제외한다. 원본은 삭제하지 않는다. 공학 상태 키는 20+48=68개이며 독립 관측 68건이 아니다. 전체 후보는 218 membership key/218행, 현재 학습 승인 완료 행은 **0**이다. 모든 후보 repetition=1은 데이터 중복 횟수이며 optimizer epoch/step 계획을 뜻하지 않는다.

### Action 분포 (후보 구성 통계, 모델 점수 아님)

| 구성 | CALL_TOOL | CHALLENGE | NO_ACTION_REQUIRED | PROPOSE_FINDING | REQUEST_EVIDENCE | 합계 |
|---|---:|---:|---:|---:|---:|---:|
| CONTRACT_REPLAY | 10 | 25 | 65 | 15 | 35 | 150 |
| UNIQUE_PHYSICS_STATE | 0 | 6 | 10 | 0 | 4 | 20 |
| NEW_TRAIN | 0 | 12 | 24 | 0 | 12 | 48 |
| 합계 | 10 | 43 | 99 | 15 | 51 | 218 |

### reason 분포

legacy와 v15의 reason 문자열은 namespace/계약이 다를 수 있다. 같은 표에 세었다고 동일한 의미로 병합하거나 legacy 정답을 자동 변환한 것이 아니다. legacy EVIDENCE_INTERPRETATION_ERROR 등이 새 구체 우선 정책과 충돌하는지 승인 전에 따로 검토해야 한다.

| reason | contract150 | physics20 | 새 TRAIN48 | 전체218 |
|---|---:|---:|---:|---:|
| AS_RUN_MISSING | 5 | 0 | 4 | 9 |
| BOUNDARY_CONDITION_UNRESOLVED | 0 | 2 | 1 | 3 |
| CONFIGURATION_MISMATCH | 12 | 0 | 0 | 12 |
| CONFIGURATION_SCOPE_UNRESOLVED | 0 | 0 | 3 | 3 |
| DURATION_INPUT_MISSING | 10 | 0 | 0 | 10 |
| EVIDENCE_CONTRADICTION | 8 | 0 | 0 | 8 |
| EVIDENCE_INTERPRETATION_ERROR | 0 | 1 | 3 | 4 |
| FORCE_LIMIT_BASIS_UNRESOLVED | 0 | 1 | 0 | 1 |
| MEASUREMENT_MAPPING_MISMATCH | 0 | 0 | 6 | 6 |
| METHOD_INTERPRETATION_ERROR | 0 | 0 | 3 | 3 |
| MODEL_SCOPE_EXCEEDED | 0 | 0 | 1 | 1 |
| MODE_SELECTION_MISMATCH | 0 | 1 | 0 | 1 |
| MONITORING_COVERAGE_INSUFFICIENT | 0 | 2 | 3 | 5 |
| NOT_APPLICABLE | 90 | 10 | 24 | 124 |
| PARAMETER_IDENTIFICATION_INSUFFICIENT | 0 | 1 | 0 | 1 |
| POWER_DISSIPATION_UNRESOLVED | 0 | 1 | 0 | 1 |
| PROBABILISTIC_ASSUMPTIONS_UNRESOLVED | 0 | 1 | 0 | 1 |
| REVISION_MISMATCH | 5 | 0 | 0 | 5 |
| SCOPE_ERROR | 10 | 0 | 0 | 10 |
| SUPPORTING_EVIDENCE_MISSING | 10 | 0 | 0 | 10 |

`NOT_APPLICABLE`는 reason 필드가 없는 행의 분모다. pending mapping 후보도 위 218행 계획 분포에 포함돼 있으므로 승인 후 제외하면 분포와 manifest를 새로 고정해야 한다. 현재 상태를 승인된 학습량으로 사용하면 안 된다.

## 미확정·릴리스 차단 항목

- TRAIN48의 독립 source/case 의미 검토, 이용권, 검토자/시각과 case/gold hash 고정. 기존 AI source audit 또는 metadata.reviewed를 사람 승인으로 승격하지 않는다.
- AS_RUN의 계산 실행 포함 여부, mapping/monitoring 중첩 1건, Boot recovery의 복합 결손을 configuration으로 대표할지 여부, TIRS BASELINE 4건의 source 필수성.
- CANYVAL/PROBA-V 원문 미확보 16건. 입력에 든 요약문으로 원문 확인·label 승인·평가 릴리스를 대신하지 않는다.
- legacy20 대표 상태 및 contract150의 기존 system prompt/reason/출력 계약과 v15의 학습 호환성. 새 정책으로 old label을 자동 재작성하지 않는다.
- 전체 기존 corpus 및 외부/미위치 RAG의 source/program 중복 감사, 권한 있는 평가자의 RESERVED metadata 감사. 구현자는 RESERVED/EvaluatorOnly를 열지 않는다.
- v15 changeset은 SFT exporter 입력 패키지가 아니다. 원래 exporter의 source 승인, release 승인, reviewer/time, 원문 파일 hash, case/gold hash 검사를 보존하는 별도 버전 경로가 필요하다. exporter를 호출하거나 승인 필드를 위조하지 않았다.

## 승인 후 Qwen27 단일 LoRA 비교 계획 (이번에 실행하지 않음)

1. 사용자가 정책·개별 label·학습 membership을 승인한 뒤 v15 manifest와 출력 계약을 freeze한다. 실험 학습 승인과 공학적 승인 필드는 별개다. 불확정 사례는 제외 또는 해결하며 승인된 행수/분포를 다시 고정한다.
2. 고정 Qwen/Qwen3.8-27B revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Transformers commit `002e1edf5b5198488297f401dd853056b6521d02`을 사용한다. 기존 torch/CUDA runtime을 확인한 후 사용하며 다른 모델/메인 revision으로 대체하지 않는다.
3. 새로 승인된 데이터로 **LoRA adapter 하나**만 학습하는 안이다. rank/alpha/dropout, optimizer/LR, batch/accumulation, epoch/step, target modules를 실행 전에 한 구성으로 고정하고 승인받는다. 이 문서에서 검증하지 않은 CLI/아키텍처 옵션을 만들어 실행 명령으로 제시하지 않는다. 탐색·반복 seed·중간 결과에 따른 prompt 수정은 하지 않는다.
4. 별도 승인 단계에서 tokenizer/template, 응답 mask/EOS, 길이, BF16/SDPA 호환성, frozen base, finite gradient와 저장/reload를 확인한다. 이번 작업에서는 토큰화나 GPU 사전검사를 실행하지 않았다.
5. 비교는 같은 동결 v15 입력·정책·평가 metadata에서 base와 이 adapter를 한 번씩 적용하는 사전 등록안이다. 현재 DEV8은 추가 추론 없이 보존한다. 새 비교용 DEV는 학습에서 제외한 나머지 DEV 중 **원문 확보와 label 검토가 완료된 사례만** 사용한다. 현재 그 16건은 원문 미확보이므로 이 비교도 실행 준비 완료가 아니다. legacy contract 회귀도 별도로 분리하고 일반화 평가라고 부르지 않는다. RESERVED 접근은 제안하지 않는다.
6. 평가 지표는 JSON/기존 check_answer 의미의 schema 유효, 별도 필드 계약, 파싱 Action/계약 통과 Action, 평가 가능한 reason, reference 충분 집합, strict, 사례별 개선/회귀, 시간/입출력 token을 분리한다. v15 정책에서 새로 생성한 base/adapter끼리만 같은 정의로 비교하며 v13/v14의 공식 exact-set 점수와 직접 개선율을 계산하지 않는다. 두 모델의 원문/입력/token/manifest/hash는 별도 경로에 보존하고 사후 출력 보정하지 않는다.

## CPU 검증과 재현

[CPU_VALIDATION_v15.json](CPU_VALIDATION_v15.json): 15개 검사 통과. 입력/정답/해설 분리, 모든 source fact 입력 제공 유지, P1~P4 범위, split/family/source/program 보존, case/gold hash, 변경안의 필드/선언된 reason 대응, source-unavailable 차단, 충분 인용 집합, 학습 DEV 배제와 분포, 기존 336개 파일 보존을 확인했다. 합성 음성 fixtures로 reason_code, 누락 reason, 빈 요청, 불필요 필드, 잘못된 claim/reference/request를 거부하는 것도 확인했다.

CPU PASS는 구조 및 선언된 정책 적용의 검사다. 의미적 정답 확정, 독립 사람 검토, 모델 성능 향상을 의미하지 않는다. 이 validator는 scorer를 import/호출하지 않고 예측 파일을 읽지 않는다. source span의 기존 텍스트 hash를 대조했으며 새로운 시각 검토를 완료했다고 주장하지 않는다.

재검증 명령(CPU만):

```sh
python experiments/source_review_policy_v15/validate_cpu.py
```

`build_proposal.py`는 이 폴더의 초안을 재생성하는 도구이며 기존 v13/v14를 쓰지 않는다. 승인 후 frozen 릴리스 위에 재실행하는 용도로 사용하지 않는다. 새 입력 messages/SFT/학습파일은 생성하지 않았다. 추가 추론, LoRA, ledger, constrained decoding, GPU 사전검사, Pod 잠금 변경과 STOP은 실행하지 않았다.

## 전체 family 검토 목록

다음 표의 네 사례는 variant 0(문제 제안), 1(범위에 맞는 제안), 2(입력 결손), 3(입력 준비)의 순서다. 원문 미확보도 누락 없이 대기 항목으로 표시했다. 상세 전후 필드와 rationale은 changeset의 해당 case_id에서 확인한다.

| split / 원리 | variant 0 / 1 / 2 / 3 | 검토 상태 |
|---|---|---|
| TRAIN / SR13-TIRS-GSE: 국소값과 평균 | CASE-4ad9ed95e2 / CASE-79c814ab47 / CASE-424419171a / CASE-e00c7fe02d | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-TIRS-ASBUILT: as-built 면적과 원인 단정 | CASE-589fb4eb03 / CASE-199314f362 / CASE-555ca15e0e / CASE-a6135d12df | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-TIRS-BASELINE: pre-test 비교 방법 | CASE-a7e82e186e / CASE-fe8f8cbdf7 / CASE-acec2b7b89 / CASE-d400650f82 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-TIRS-CULL: 복사 경로 생략 | CASE-88b5d13600 / CASE-4196d4ddc2 / CASE-9c036b2503 / CASE-1bdc9a0a66 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-NEA-LEVELS: 시험 종류의 실증 범위 | CASE-7e2ce553dd / CASE-ed9b08cbf4 / CASE-c51cdfeccd / CASE-493773aa90 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-NEA-COIL: 하우징과 코일 | CASE-02caf2a304 / CASE-2f88f50fa1 / CASE-07dbc2c8c4 / CASE-61ef0e9728 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-NEA-TRANSLATION: 회전과 실제 이송 | CASE-d5e287468e / CASE-6d4be78aae / CASE-cf088dcb3c / CASE-879754a57b | 사후 AI 초안, 사람 검토 대기 / mapping 중첩 포함 |
| TRAIN / SR13-NEA-PLANNED: 계획과 실행 | CASE-6de39fe5d2 / CASE-332bc07aa7 / CASE-c83a53985e / CASE-48f4545a71 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-RHOBC-RAILS: 제어 도달 범위 | CASE-54a9474954 / CASE-d3f978cae1 / CASE-08ee9d45a5 / CASE-d723874b9f | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-RHOBC-MONITOR: 부품별 고장 관찰 | CASE-9df6407dbd / CASE-0ca276ca1e / CASE-f235c491ee / CASE-703b0ad936 | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-RHOBC-EFFECTS: 비파괴와 기능중단 | CASE-8822d424f6 / CASE-bbdb74ad02 / CASE-185d4a0c91 / CASE-b94839f32b | 사후 AI 초안, 사람 검토 대기 |
| TRAIN / SR13-RHOBC-BOOT: 복구 경로와 fault model | CASE-13e084e68e / CASE-5616686acf / CASE-9d61b185f8 / CASE-d029eccb5c | 사후 AI 초안, 사람 검토 대기 |
| DEV / SR13-HYPSO-RANGE: 실험 온도 범위 | CASE-ec0f24fd6c / CASE-d48966c293 / CASE-f49f3d339e / CASE-8261f9621f | 사후 AI 초안, 사람 검토 대기 |
| DEV / SR13-HYPSO-IR: 측정 신호와 표면 온도 | CASE-18d7b891b1 / CASE-5bf8af5346 / CASE-b40f92306b / CASE-a18319c1d2 | 사후 AI 초안, 사람 검토 대기 |
| DEV / SR13-CANYVAL-PRELOAD: 구속 조건 | CASE-870c379fa0 / CASE-e7386f7ddf / CASE-df8ed0a5e6 / CASE-4e774a1974 | SOURCE_UNAVAILABLE |
| DEV / SR13-CANYVAL-DAMAGE: 주파수 변화와 원인 | CASE-1800223793 / CASE-0bf2f59697 / CASE-a00c710b3f / CASE-1fb4ec74a4 | SOURCE_UNAVAILABLE |
| DEV / SR13-PROBAV-SYNC: 이벤트 시간 연결 | CASE-fc0864226a / CASE-d05caa3edc / CASE-71262c17f4 / CASE-15d397cc74 | SOURCE_UNAVAILABLE |
| DEV / SR13-PROBAV-CENSOR: 관측 손실 | CASE-c45ab2fec7 / CASE-2346b4ee7f / CASE-82a92a1c28 / CASE-e8a8b979ca | SOURCE_UNAVAILABLE |

최종 결정 칸: 정책 승인 ___ / case별 label 승인 기록 ___ / 학습 membership 확정 ___ / 실험용 학습 승인 ___ / 공학적 승인 **별도**. 이 빈칸이나 AI 작성 기록을 승인 완료로 해석하지 않는다.
