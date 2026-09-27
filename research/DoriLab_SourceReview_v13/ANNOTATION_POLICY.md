# v13 정답 작성과 검토 정책

## 근거를 세 층으로 구분

1. `SOURCE_REPORTED`: 논문 본문에서 확인한 제한된 진술. 제목, 판본, 원문 절/페이지에 연결한다.
2. `SYNTHETIC_CASE_RECORD`: 이 패키지에서 만든 관측, 조건과 제안. 실제 임무에서 일어난 사건으로 귀속하지 않는다.
3. `DORILAB_REVIEW_POLICY`: 어떤 질문에 CHALLENGE, REQUEST_EVIDENCE, NO_ACTION_REQUIRED를 선택하는지 정하는 업무 계약.

정답은 세 층의 결합으로 설명한다. paper에 Action enum이나 내부 reason taxonomy가 있었다고 서술하지 않는다.

## 질문의 대상

`PROPOSED_DISPOSITION`은 제안 자체를 평가한다. 누락 자료를 확보하자는 적절한 제안에는 추가 반박이 없을 수 있다. 그때 자료 상태는 여전히 미완료다.

`INPUT_READINESS`는 명시된 평가에 필요한 입력이 공급됐는지 판단한다. 입력이 충분해도 나중에 요구조건 부적합이 나올 수 있다. 입력 준비를 제품 합격으로 바꾸지 않는다.

`review_note.relation_to_target`은 평가자 정답 또는 새 내부 기록 모델의 출력이다. 정답의 relation을 모델 입력에 넣지 않는다. `render`는 입력에 지정된 해당 source의 모든 fact를 조립하며 gold의 required fact만 골라주지 않는다.

## Action 우선순위

- 자료가 제안의 핵심 주장을 반박하면 CHALLENGE. 추가 자료를 얻을 수 있다는 이유만으로 이미 확인된 반박을 숨기지 않는다.
- 요청된 판단의 필수 입력이 실제로 없으면 REQUEST_EVIDENCE. 요청 항목은 허용 목록 중 필요한 항목만 고른다.
- 제안이 근거 범위에 맞거나, 입력 준비 질문의 필수 자료가 있으면 해당 검토점의 NO_ACTION_REQUIRED.
- 자료는 있으나 의미/방법/권위가 해결되지 않은 상황은 별도 workflow의 NEEDS_HUMAN_REVIEW로 보낸다. 기존 Action에 임의 새 enum을 추가하지 않는다.
- CALL_TOOL/PROPOSE_FINDING은 기존 계약 회귀에서 유지한다. 기본 v13 96건은 세 가지 검토 Action에 집중하며, 완전한 tool argument 검증은 기존 도구 계약의 별도 검사로 연결한다.

## reason의 처리

`reason_definitions_v13.json`은 새 실험용 정의다. 현재 모든 정답은 canonical reason 한 개를 가진다. 이는 작성자의 제안이며 사람 간 코드 경계 재현성까지 검증한 상태가 아니다. 독립 검토에서 의미상 다른 코드도 타당하면 새 label revision에 허용 집합과 선정 근거를 기록하고, 모델 출력을 보기 전에 freeze한다. 성능표를 본 뒤 유리한 reason만 허용하지 않는다.

Action, 근거와 reason을 따로 채점한다. Action이 맞고 reason이 다른 경우, 그 차이가 실제 후속 요청/검토에 영향을 주는지 별도로 분류한다. 학습 후 일반 reason으로 구체적 원인을 뭉뚱그리는 회귀를 추적한다.

## 참조

관측 ID는 매 사례 새로 배정한다. source reference도 고정된 OBS-1/SF-1 위치에 기대지 않는다. 동일 source의 불필요한 fact와 같은 scope의 무관 기록이 입력에 함께 존재한다. 일부 문제는 두 개의 관측을 결합해야 하므로 필수 참조 수가 2 또는 3이다.

그럼에도 일부 무관 기록은 쉬운 distractor다. 실제 문서에서의 관련성 검색 검증을 대신하지 않는다. 어려운 distractor 추가는 TRAIN/DEV의 새 버전으로 진행하고 현재 gold를 몰래 바꾸지 않는다.

## 검토표 작성 순서

출처를 읽은 검토자는 가능한 한 모델 출력과 작성자 기대값을 보지 않은 상태에서 먼저 Action과 필요한 근거를 기록한다. 이어서 기존 초안과 차이를 비교한다. 해석이 모호한 문제는 단일 정답으로 억지 확정하지 말고 quarantine 또는 workflow probe로 이동한다.

`reviews/*.template.json`은 실제 검토 후 새 파일로 복사해 채운다. source review에는 실제 로컬 원문 경로, SHA256, 이용권 확인, 전체 기존 corpus와 source/program 중복 점검을 기록한다. case review에는 입력/gold hash, 검토자, 시각, 수정 이유를 남긴다. 익명 AI 재검사를 독립 사람 승인으로 기록하지 않는다.

## 제한

현재 원문 PDF의 표/그림은 화면 대조를 완료하지 못했다. 본문 기반 정답 초안은 제공하지만, 원문 visual check와 사람이 수행하는 독립 의미 검토를 대체했다고 주장하지 않는다. 새 source라는 표현은 DoriLab의 알려진 이전 출처에 대한 상대적 구분이며 base model 사전학습 미노출을 보장하지 않는다.
