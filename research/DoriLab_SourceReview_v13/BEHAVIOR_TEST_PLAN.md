# 행동 검사와 근거 개입

## 이미 포함한 대조

24개 가족마다 동일 관측의 부당한 제안과 적절한 제한 제안, 그리고 동일 입력 준비 질문의 자료 누락/자료 준비 상태가 있다. family metadata는 모델에 제공하지 않는다.

이 변형은 96개의 독립 과학 사실을 늘리는 것이 아니라 판단 경계 24개를 여러 상태에서 검사한다. 관측을 고정해 제안만 바꿀 때 Action의 대상이 맞는지 확인한다. 준비된 입력에 이미 부적합 관측이 있어도 INPUT_READINESS의 NO_ACTION_REQUIRED가 나올 수 있는 사례를 포함했다.

## Codex 추가 구현 범위

ID 이름 변경과 record 순서 변경은 결정적 변환으로 만들고 모든 ref/claim 연결을 일관되게 변환한다. gold는 평가 프로세스에서만 같은 ID 매핑을 적용한다. 입력을 만드는 함수에 gold를 전달하지 않는다.

새 source/program은 TRAIN/DEV/RESERVED 배정을 그대로 유지한다. reserve 변형 생성기는 조건이 freeze된 뒤 평가자만 실행한다. 생성한 view를 독립 샘플로 분모에 더하지 않는다.

## 우선 검사

| 검사 | 바꿀 것 | 기대 |
|---|---|---|
| ID invariance | source/obs/claim ID와 배열 순서 | Action/reason 유지, 참조는 매핑에 따라 변환 |
| Irrelevant record | 같은 scope의 무관한 문서-control 기록 | 결론 유지, 해당 기록을 근거로 채택하지 않음 |
| Review-target contrast | 관측 고정, 처분 제안 변경 | 질문 대상에 맞게 판단 변경 |
| Missing vs available | 질문 고정, 실제 필수 입력 보완 | RQ->NO 상태 전이 |
| Evidence intervention | 핵심 관측 또는 전제 한 개를 검토된 반대 상태로 수정 | 새 gold를 출력 전에 확정한 경우만 민감도 채점 |
| Metadata-only probe | 의미 본문을 가림 | shortcut 진단. 원래 gold로 정상 제품 성능을 주장하지 않음 |

근거 삭제가 항상 Action 반전을 뜻하지는 않는다. 남은 근거가 충분한지 별도로 확인한다. `allowed_request_ids`를 조작하면 실제 실행 가능성이 달라질 수 있으므로 임의 shuffle 외의 내용 변경은 의미 불변으로 간주하지 않는다.

## 코드 블록 adapter

정확히 한 개의 code fence만 전체 응답을 감쌀 때 제거하는 결정적 adapter를 제공했다. 여러 JSON이나 외부 설명, 깨진 JSON을 추출/복구하지 않는다. raw strict와 adapter diagnostic을 함께 기록한다. 새 constrained decoder는 이 도구에 포함되지 않았으며, runtime 지원과 의미 회귀 검증 후 별도 arm으로만 추가한다.

## Human Review 경계

`workflow_probes`의 6건은 해석 또는 권위 판단이 남을 때 자료 요청을 꾸며내지 않는 상태 흐름 예시다. Action gold 대신 workflow 기대값을 가진다. 기본 Action scorer에 억지로 넣지 않는다. 프로브로 설계한 명시적 정책 경계와 실제 모델의 불확실성 교정 성능은 따로 평가한다.
