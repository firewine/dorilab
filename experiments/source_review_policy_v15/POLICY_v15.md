# SourceReview v15 정책 개정안

상태: `POST_OUTPUT_AI_DRAFT / HUMAN_REVIEW_PENDING`. v13/v14 모델 출력을 관측한 뒤 만든 정책 제안이다. v13에 이 우선순위와 인용 정책이 이미 있었다고 소급하지 않는다. 기존 exact-set 결과, 공식 점수, 완료 기록은 유지한다. 이 문서는 학습 또는 공학적 승인이 아니다.

## R1. Action과 reason을 분리한다

먼저 질문이 제안 자체의 적절성(`PROPOSED_DISPOSITION`)인지, 지정된 판단의 입력 준비(`INPUT_READINESS`)인지 식별한다. 제공 사실이 제안의 핵심 주장을 반박하면 CHALLENGE, 요청된 판단의 필수 입력이 없으면 REQUEST_EVIDENCE, 해당 제안에 반박할 점이 없거나 지정된 입력이 있으면 NO_ACTION_REQUIRED를 선택한다. 적절한 자료 확보 제안에 대한 NO_ACTION_REQUIRED는 자료 준비 완료를 뜻하지 않는다. 입력 준비 완료도 요구조건 충족·시험 실행·공학적 승인과 다르다.

그 다음 CHALLENGE와 REQUEST_EVIDENCE의 reason을 분류한다. reason을 고르기 위해 Action을 바꾸지 않는다. 요청 항목은 실제 결손에 맞춰 별도로 고른다.

## R2. 구체 코드의 적용 조건을 먼저 검사한다

질문과 제공 사실이 적용 조건을 충족하는 구체 코드를 일반 코드보다 우선한다. 키워드만 일치하거나 사례가 특정 출처에 속한다는 이유로 코드를 선택하지 않는다.

| 코드 | v15 적용 조건 |
|---|---|
| MODEL_SCOPE_EXCEEDED | 모델 또는 실험에서 확인한 범위를 넘어 적용 가능하거나 이미 실증됐다고 주장한다. 모델뿐 아니라 시험 종류·환경·조건의 확인 범위를 포함한다. 단순 자료 부재만 있고 범위를 넘는 주장이 없다면 자동 적용하지 않는다. |
| MEASUREMENT_MAPPING_MISMATCH | 관측/모델의 위치나 물리량이 판단 대상에 대응하지 않거나 필요한 대응 자료가 없다. 공간 대응뿐 아니라 측정 신호에서 대상 물리량으로 가는 변환·보정 관계와 그 결손을 포함한다. 측정 대상 자체의 혼동과 관측 범위 부족이 겹치면 R4를 적용한다. |
| METHOD_INTERPRETATION_ERROR | 제안 절차가 명시된 방법·가정·계산 규칙과 충돌한다. 논문의 방법과 사례에서 주어진 합성 규칙을 구분한다. |
| CONFIGURATION_SCOPE_UNRESOLVED | 해당 구성·연결관계를 확정할 정보가 부족하다. 구성 정보가 이미 명확하고 그 내용을 잘못 읽은 경우까지 자동 확장하지 않는다. |
| BOUNDARY_CONDITION_UNRESOLVED | 필요한 환경·기계 경계조건이 없거나, 문서화된 경계 차이를 무시한 동등성 주장이 있다. |
| MONITORING_COVERAGE_INSUFFICIENT | 기록한 관측량·획득 범위가 요청된 관찰/귀속 판단을 지원하지 못한다. |
| AS_RUN_MISSING | 실행 식별자·실제 조건·실행 결과가 빠져 있다. 물리 시험과 계산 실행을 포함한다는 확장은 이번 v15의 명시적 제안이며 승인 대상이다. 대체 가능한 해석 자료까지 모두 없다는 이유만으로 모든 자료 결손을 이 코드로 바꾸지는 않는다. |
| TEST_ARTIFACT_UNMODELED | 식별된 시험 장치 효과를 표현하거나 구분해야 하는데 해당 추론에서 무시한다. 가능한 원인일 뿐 확정되지 않았다면 식별됐다고 단정하지 않는다. |
| MODAL_INPUTS_MISSING | 지정된 모달 분석의 모드 형상·좌표 대응 등 필수 자료가 없다. |
| MODE_SELECTION_MISMATCH | 제안된 모드 대응/선택이 지정된 식별 근거와 충돌한다. |

## R3. 일반 코드는 fallback이다

`EVIDENCE_INTERPRETATION_ERROR`: 제안 추론이 제공 관측이나 출처의 지원 범위를 잘못 해석하지만, 적용 가능한 구체 코드가 없는 경우에 쓴다. 독립 원인 분별 없이 원인을 유일하게 확정하는 경우도 구체 코드의 조건부터 확인한다.

`SUPPORTING_EVIDENCE_MISSING`: 필요한 지원 기록이 없고, 적용 가능한 구체 코드가 없는 경우에 쓴다. 요청 이름에 calibration, run 등이 포함된다는 이유만으로 분류하지 않는다. 원자료 또는 승인된 대체 분석 중 하나가 필요한 질문에서 둘 다 없다는 사실과, 특정 실행 결과만 없는 사실을 구분한다.

## R4. 구체 코드끼리 겹치는 경우

현재 검토 질문에 직접 연결되는 결함을 기준으로 고른다. 같은 현상도 질문이 실증 범위, 측정량 변환, 실행 이력, 원인 관찰 범위 중 무엇을 묻는지에 따라 달라질 수 있다. 판단 경로와 배제한 대안의 이유를 평가 metadata에 남긴다. 그래도 둘 이상의 코드가 동등하게 직접 연결되면 `LABEL_OVERLAP_PENDING`으로 남기고 학습/평가 릴리스를 막는다. 코드 집합을 사후에 넓혀 모델 출력을 정답으로 만드는 방식은 사용하지 않는다. 개별 사례 ID, 특정 모델 출력 또는 성공 여부를 조건으로 하는 정책은 없다.

## C1. 판단 근거와 provenance를 분리한다

`evidence_refs`는 이번 판단을 직접 뒷받침하는 **입력에 제공된 ID**만 포함한다. 사례 작성에 사용한 논문, source span, 파일 hash, 입력 자료 전체 목록은 `system_provenance`에 보존한다. provenance 목록은 모델이 실제 사용하거나 인용했다는 기록이 아니다. 출력에 나타난 인용 역시 내부 사고 과정의 증명으로 표현하지 않는다.

## C2. 충분한 근거 집합을 사례별로 정한다

관측이 질문에 필요한 자료의 존재·부재와 적용 범위를 명시하면 관측만으로 준비 여부를 판단하는 집합을 허용할 수 있다. 제안 검토에서도 관측에 필요한 관계·계산 규칙이 모두 있으면 같은 원칙을 적용한다. 원문의 특정 방법·정의·조건이 결론의 필수 전제라면 그 source reference와 사례 관측을 함께 요구한다. 모든 사례에 source+observation을 강제하지 않으며, 모든 source reference를 선택적으로 허용하지도 않는다.

여러 충분한 집합이 있으면 평가 전용 `reference_requirement.sufficient_sets`에 각각 ID 집합과 충분성 이유를 기록한다. 집합별 source ID의 역할(필수 방법 전제, 직접 관련된 보강 근거)도 설명한다. 모델 입력에는 이 집합, 필수 참조 목록, 정답 reason, rationale을 넣지 않는다.

## C3. 새 평가 metadata의 의미

제안 방식은 `SUFFICIENT_EXACT_SETS_V15_DRAFT`다. 순서만 무시하며 중복 ID, 제공되지 않은 ID, 빈 집합, 무관한 추가 인용은 거부한다. 출력 집합이 사전 승인된 충분 집합 중 하나와 정확히 같아야 한다. 임의 상위 집합이나 모든 ID 일괄 인용은 성공으로 처리하지 않는다. 충분 집합이 확정되지 않은 사례는 미평가로 남긴다. 여기서 수행하는 것은 metadata 자체의 CPU 검사이며 모델 재채점이 아니다. 기존 scorer와 기존 exact-set 점수는 변경하지 않는다. 새 evaluator 구현 및 릴리스는 별도 승인 후 작업이다.

## F1. 출력 필드 계약

기존 direct_v14의 세 가지 검토 Action 계약을 유지한다. 출력은 Markdown 없는 JSON 객체 하나다.

| Action | 필수 필드 | 생략 필드 |
|---|---|---|
| NO_ACTION_REQUIRED | action, claim_id, evidence_refs | reason, requested_evidence, tool, arguments, finding_type |
| CHALLENGE | action, claim_id, evidence_refs, reason | requested_evidence, tool, arguments, finding_type |
| REQUEST_EVIDENCE | action, claim_id, evidence_refs, reason, requested_evidence | tool, arguments, finding_type |

이유 필드명은 `reason`이며 `reason_code`가 아니다. claim_id를 그대로 복사한다. REQUEST_EVIDENCE의 요청 배열은 비어 있지 않고 제공된 request_catalog의 필요한 ID만 포함한다. 불필요한 필드·빈 배열을 추가하지 않는다. 기존 contract replay의 CALL_TOOL/PROPOSE_FINDING은 해당 legacy 계약을 보존하며 이 세 Action의 필드 규칙을 덮어씌우지 않는다.

## D1. label·입력·해설 분리 및 승인

새 changeset은 원본 case/gold hash, 변경 전후 값, 정책 조항, 원문 원리와 합성 관측, 출력 노출, 검토 상태를 기록한다. 모델용 자료는 원본 packet과 그 packet에 지정된 **모든** source fact를 입력 전용 경로로 조립한다. 정답이 고른 fact만 조립하지 않는다. 평가 metadata와 rationale은 별도 보관한다. 이번에는 학습 messages나 SFT export를 만들지 않는다.

모든 변경은 `SOURCE_GROUNDED_AI_CANDIDATE`의 후속 초안이다. `human_review_performed=false`, `training_eligible=false`, `engineering_approved=false`를 유지한다. 원문 미확보 사례는 `SOURCE_UNAVAILABLE`로 격리하며 요약문을 원문 확인으로 승격하지 않는다. 기존 시각 검토 기록은 provenance일 뿐 이번 작업의 독립 사람 검토가 아니다.

## D2. split과 학습 후보

TRAIN/DEV의 case·family·source·program split을 유지한다. 관측한 DEV8은 `ERROR_INFORMED_REGRESSION`이다. 다른 DEV도 학습에 포함하지 않는다. RESERVED/EvaluatorOnly 내용은 열지 않으며, 필요 split 감사는 권한 있는 평가자의 metadata 수준 확인을 승인 조건으로 남긴다.

실험용 학습 승인과 공학적 승인은 별개다. 기존 exporter의 manifest 고정, source 내용·이용권·split 감사, reviewer/시각, case/gold hash 고정, 개별 학습 승인 조건을 우회하지 않는다. v15 metadata가 기존 v13 exporter와 자동 호환된다고 주장하지 않는다. 승인 후 별도 버전의 export 경로를 구현하고 동일하거나 더 엄격한 승인 검사를 검증해야 한다.
