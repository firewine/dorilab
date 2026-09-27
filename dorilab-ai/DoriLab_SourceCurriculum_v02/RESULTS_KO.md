# DoriLab v10 비교 검토 — reason 설명은 기본 경로에 추가하지 않음

## 결론

제공된 두 결과 파일을 다시 집계했다. 현재 범위 게이트 + position e2 + 기존 프롬프트를 개발 기준으로 유지한다. v09 reason 설명은 이번 조건에서 전체 계약 18/24에서 16/24, action 24/24에서 22/24로 내려갔으므로 기본 입력에 추가하지 않는다. 기존 dcurr 파일은 v10에서도 수정되지 않았으므로 프롬프트 코드를 되돌리는 패치가 필요한 것은 아니다.

이것은 현재 가이드의 채택 여부에 대한 결정이다. 모든 reason 설명이 유해하거나 작은 모델은 설명을 읽지 못한다는 결론은 아니다.

## 재집계

|지표|기본 e2|e2 + v09 설명|
|---|---:|---:|
|Action|24/24|22/24|
|Schema + 허용 참조|24/24|23/24|
|근거 집합 정확 일치|24/24|24/24|
|전체 계약|18/24|16/24|
|정답이 reason을 요구하는 12건의 action+reason 동시 정답|6/12|5/12|
|A/B 양쪽 전체 통과|6/12쌍|5/12쌍|

가이드의 조건부 reason 지표는 5/11이다. action을 틀린 reason 사례가 분모에서 빠지므로 기본 6/12와 같은 분모의 비교는 joint 5/12를 사용한다.

전체 계약 새 통과 1건, 새 실패 3건. 구조화 출력이 달라진 것은 5건이다. 그중 NS10-T3-B는 틀린 reason에서 다른 틀린 reason으로 변해 통과 수에는 영향이 없다.

설명이 직접 다루는 세 주제의 6개 사례는 양쪽 모두 6/6 통과다. reason이 필요한 해당 3개 사례도 기본부터 3/3이다. 이 표본에서는 핵심 목표 주제에서 개선 여지가 없었다. baseline 오류 6개는 모두 다른 주제다.

각 사례의 입력은 설명 추가로 정확히 327 tokens 늘었다. 입력 길이와 가이드 내용이 함께 달라졌으며, 단일 실행으로 특정 내부 메커니즘이나 통계적 일반화를 확정하지 않는다.

## 변화가 중요한 네 사례

|사례|기본|가이드|해석|
|---|---|---|---|
|NS10-E2-A|CHALLENGE, 올바른 reason|REQUEST_EVIDENCE, requested_evidence에 OBS-6623|이미 없는 관측을 있다고 한 coverage 주장에 대한 반박이 자료 요청으로 바뀜. 허용 요청 ID도 위반|
|NS10-T2-A|BOUNDARY_CONDITION_UNRESOLVED|MONITORING_COVERAGE_INSUFFICIENT|Action과 요청자료는 맞지만 reason 퇴행|
|NS10-T3-A|NO_ACTION_REQUIRED|CHALLENGE|패킷이 설명한 정상 RMS 처리에 불필요한 개입|
|NS10-M4-A|CONFIGURATION_SCOPE_UNRESOLVED|FORCE_LIMIT_BASIS_UNRESOLVED|Action·근거·자료요청은 유지하며 reason 하나 개선|

NS10-E2-A는 잘못된 proposal을 그대로 수용한 NO_ACTION은 아니므로 summary의 wrongly_accepts_refuted_proposal=0으로 표시된다. 그렇다고 이 출력이 옳다는 뜻은 아니다. action별 분류와 참조 요청의 유효성을 함께 봐야 한다.

## baseline의 6개 미통과

아래는 기준 라벨 대비 불일치다. action·claim·근거 집합·요청자료는 같으며 reason만 다르다. 원출력과 점수는 변경하지 않는다.

|사례|기준 reason|모델 reason|
|---|---|---|
|NS10-T3-B|METHOD_INTERPRETATION_ERROR|EVIDENCE_INTERPRETATION_ERROR|
|NS10-T4-A|POWER_DISSIPATION_UNRESOLVED|MONITORING_COVERAGE_INSUFFICIENT|
|NS10-M3-B|METHOD_INTERPRETATION_ERROR|FORCE_LIMIT_BASIS_UNRESOLVED|
|NS10-M4-A|FORCE_LIMIT_BASIS_UNRESOLVED|CONFIGURATION_SCOPE_UNRESOLVED|
|NS10-E3-B|EXPOSURE_METADATA_UNRESOLVED|MONITORING_COVERAGE_INSUFFICIENT|
|NS10-E4-A|CONFIGURATION_SCOPE_UNRESOLVED|MONITORING_COVERAGE_INSUFFICIENT|

이들은 DoriLab 분류 표현이다. 일부 폭넓은 reason 간 경계의 타당성은 별도로 검토할 수 있으나, 그 사실을 이유로 기존 평가의 허용 정답을 조용히 넓히지 않는다.

## 100% action의 범위

3개 프로그램의 12쌍/24개 합성 시나리오에서, 정리된 문헌 원리와 현재 관측을 입력으로 받는 action 선택이 맞았다. 실제 PDF에서 근거 추출, 메타데이터 신뢰성, 여러 현재 기록의 충돌, 수치해석과 시험 승인을 수행한 결과는 아니다. 정답은 모델 실행 전에 AI가 작성·검토했으며 독립 사람 진실값이 아니다. 원자료나 문헌을 이번에 새로 검증하지 않았다.

## 다음 액션 — 실제 학습 정답의 코드 분포 점검

`audit_reason_exposure_v11.py`를 기존 프로젝트 루트에 복사하고 실행한다. GPU·모델 다운로드·pip 설치가 없다.

```bash
cd ~/dorilab-ai/DoriLab_SourceCurriculum_v02
python audit_reason_exposure_v11.py
explorer.exe data/reason_exposure_v11
```

읽는 파일:
- data/evidence_training_v05/position210.jsonl
- data/evidence_training_v05/position210.manifest.json
- runs/evidence_training_v05_position_e2/RUN_MANIFEST.json
- data/new_source_reason_v10/comparison_cases.jsonl

생성: data/reason_exposure_v11/audit.json, RESULTS_KO.md.

출력의 정답 코드 행 수와 고유 Physics parent 사례 수를 구분한다. system 프롬프트에서 이름이 발견되는 것과 supervised answer에 그 코드가 등장하는 것은 따로 기록한다. row count는 epoch 반복이나 token별 gradient weight가 아니다.

코드 정답 예가 0이면 해당 export가 그 분류명을 직접 정답으로 보여주지 않았다는 뜻이다. 베이스 모델이 해당 개념을 모른다는 뜻은 아니다. 정답 예가 있는데 혼동하면 예제 다양성·코드 구분 정의를 검토한다. 그 뒤 새 학습 후보와 새로운 평가를 분리해서 설계한다. 이 24개 평가를 자동으로 train에 넣지 않는다.

## 구현 검증

표준 라이브러리만 사용한다. CPU 테스트 14개가 통과했다. 임시 데이터에서 해시 일치·누락/충돌·중복 JSON·row와 parent count 분리를 확인했다. 실제 사용자 position210 파일과 RUN_MANIFEST는 이번 첨부에 없으므로 그 데이터 분포 자체를 아직 측정하지 않았다. 실제 값은 로컬 실행 결과가 필요하다.
