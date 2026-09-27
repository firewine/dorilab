# v15 첫 파일럿 릴리스 후보 — RC1

상위 [v15 초안](../POLICY_v15.md)을 보존하고 이번 사용자 지시를 적용한 제한된 후보이다. 새 대규모 정책 버전이 아니다. 정책 채택 범위는 USER_DIRECTED_RC_POLICY, 개별 label·학습자료 사용·공학적 승인은 모두 PENDING이다. `human_review_performed=false`를 유지한다.

## 적용 정책

1. Action을 질문과 관측으로 먼저 결정한다. 그 뒤 적용 조건을 충족하는 구체 reason을 우선한다. EVIDENCE_INTERPRETATION_ERROR와 SUPPORTING_EVIDENCE_MISSING은 적용 가능한 구체 코드가 없을 때만 쓴다. 구체 코드가 겹치면 현재 질문에 직접 연결되는 문제로 선택하고 미해결 중첩은 보류한다.
2. MODEL_SCOPE_EXCEEDED는 모델과 실험의 확인 범위를 넘는 적용성·실증 주장을 포함한다. MEASUREMENT_MAPPING_MISMATCH는 공간·물리량 대응, 신호→판단 대상 물리량의 변환/보정 및 필요한 대응 자료 결손을 포함한다.
3. AS_RUN_MISSING은 기존 문구 `Execution identity, actual conditions or execution results are missing.`을 유지한다. 계산 실행까지 확대하는 해석은 이 파일럿에 적용하지 않는다. 물리 시험의 실행 기록 부재도 실제 질문과 조건을 개별 검토하며 자동 승인하지 않는다.
4. 판단용 evidence_refs와 시스템 provenance를 분리한다. 작성 출처·source span·입력 전체 목록은 모델이 인용한 근거가 아니다. 질문에 충분한 관측 집합 또는 필요한 원문 방법/조건과 관측의 집합을 사례별 평가 metadata로 관리한다.
5. 사전 검토된 충분 집합 중 하나와 순서를 제외하고 정확히 일치해야 한다. 제공되지 않은 ID, 중복, 무관한 추가 ID는 거부한다. **선택 집합이 제공 전체 집합과 같다는 사실은 독립 실패 조건이 아니다.** 제공 전체가 승인된 충분 집합과 정확히 같으면 허용한다. 단, 이 RC의 충분 집합은 AI 검토 후보이며 사람 승인된 운영 evaluator로 배포하지 않는다.
6. 충분 집합·정답·rationale은 모델 입력에서 제외한다. packet과 입력에 지정된 모든 source fact를 입력 전용 renderer로 조립한다. 필요한 source만 gold에서 선택해 넣지 않는다.
7. TIRS 세 rationale의 제안 검토/입력 결손/입력 준비 구분을 유지한다. Action·합성 관측·계산값은 바꾸지 않는다.

## 첫 학습 후보 범위

SR13-TIRS-BASELINE, SR13-NEA-TRANSLATION, SR13-RHOBC-BOOT의 네 variant씩 12건은 모두 보류한다. 기존 TRAIN48 및 218행 후보는 수정하지 않는다. 별도 상한은 새 TRAIN36 + legacy physics20 + contract150 = 206행이다. 개별 호환성 보류를 추가 적용한 행수와 분포는 PILOT_TRAIN_MEMBERSHIP.json을 따른다. 후보 선정은 학습 사용 승인이 아니다.

## 입력 계약 라우팅

legacy contract와 legacy physics는 원래 messages 및 출력 계약을 그대로 유지한다. v15에는 명시적인 system 내용 `DoriLab SourceReview v15 pilot RC1`과 그 정책·reason 정의·필드 안내를 넣는다. legacy 입력에 v15 정책을 앞붙이지 않는다. 모델에는 각 행의 system/user 메시지가 전달된다. metadata 버전만으로 구분했다고 주장하지 않는다. 동일 role/context별 실제 system 문자열과 hash 및 내용 차이는 CONTRACT_COMPATIBILITY.json에서 검토한다.

legacy physics의 기존 정의와 v15가 실질적으로 충돌할 가능성이 있는 label은 보류하며 자동 재작성하지 않는다. 기존 contract의 다른 Action/필드/enum은 legacy system 지시로 유지한다. system 프롬프트별 계약 라우팅은 CPU 문자열 검사로 검증할 수 있지만 모델이 이를 잘 따르는지는 미검증이다.

## 승인과 동결

실제 사람 검토·검토자·시간·승인 이력은 만들어 넣지 않는다. 후보 정답과 충분 근거는 다음 모델 출력을 보기 전 hash로 동결하되 이것은 AI 후보 동결이지 사람 label 승인이나 학습 릴리스가 아니다. 수정 필요 시 새 동결 기록으로 사유를 남긴다. v13/v14 scorer·공식 점수는 변경하지 않는다. DEV8은 이미 관측한 회귀 자료이며 학습 또는 추가 추론에 포함하지 않는다. RESERVED/EvaluatorOnly는 열지 않는다. 원 exporter의 승인 검사를 우회하거나 승인 전 SFT export를 만들지 않는다.
