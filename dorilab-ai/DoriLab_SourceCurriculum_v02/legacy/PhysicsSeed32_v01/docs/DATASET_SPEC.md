# Physics Seed32 데이터 명세 v0.1

## 1. 목적과 구성 원리

학습 목표는 `reference_context + case_packet → source-grounded review action`이다. 입력 문헌은 공학적 원리를 제공하고, 관측은 사례에 주어진 가상 기록에서 가져온다. 출처 문장이 사례의 실측 사실을 대신하지 않는다.

이 버전은 2개 문헌 × 8개 검토주제 × 2개 대조상태 = 32개다. 표본의 기본 묶음은 사례 하나보다 **pair_id와 source_program_groups**다. 대조쌍마다 다른 leaf가 하나인지 `tools.validate_pack`이 확인한다. 한 leaf가 문장 전체인 경우, 의미상 여러 정보를 동시에 포함할 수 있으므로 사람 검토에서는 '하나의 검토 증거/제안'으로 봐야 한다.

## 2. 출처와 사례의 분리

| 계층 | 파일/필드 | 성격 |
|---|---|---|
| 문서 식별 | source_manifest | 저자·문서번호·권리표시·접근상태 |
| 사실 요약 | source_facts | 원문 페이지와 연결한 영/한 paraphrase |
| 가상 상태 | case.packet.case_packet | 문헌 원리를 적용하도록 새로 만든 상황 |
| 판단 라벨 | case.expected | DoriLab 검토 정책으로 만든 정답 후보 |
| 설명 | rationale_ko | 사람이 라벨을 검토하기 위한 이유 |
| SFT 입력/출력 | sft.messages | system/user/assistant 3개 메시지 |

`source_facts.verification=PDF_TEXT_CHECKED`는 PDF 텍스트를 확인했다는 뜻이다. 표·그림의 시각 검수, 저자나 시험책임자의 정답 확인을 의미하지 않는다. 원문에 없는 수치·승인은 `synthetic_assumptions` 또는 사례의 가상 기록으로 구분했다.

## 3. 입력 packet

- `review_question`: 이번 호출이 답할 한 가지 검토 질문
- `claim_id`: 검토 대상 식별자
- `reference_context`: fact ID, source ID, PDF 1-based page, printed page, section, paraphrase
- `case_packet.evidence`: ID와 텍스트를 가진 가상 관측·제공 기록
- `case_packet.proposal`: 검토할 결론·계획·해석
- `allowed_request_ids`: 추가 확인으로 요청할 수 있는 자료 식별자

학습용 user 메시지에는 정답, A/B 표식, 작성자 해설, pair ID를 넣지 않았다. 원천 문헌의 원리와 수치·상태 정보는 문제를 해결하는 근거로 제공한다.

## 4. 행동 의미

**CHALLENGE:** 제공된 자료만으로 제안의 특정 결함을 확인할 수 있다.

**REQUEST_EVIDENCE:** 검토를 끝내는 데 필요한 선행 근거가 없다. 데이터의 존재와 내용이 확인된 뒤 결론을 갱신할 수 있다.

**NO_ACTION_REQUIRED:** 해당 한정 검토점에서 제안을 수정할 이유가 없다. 제품의 합격, 시험 개시 허가, 요구사항 전체 종결과는 별개다.

현재는 실제 계산 도구를 실행하는 예제가 없으므로 CALL_TOOL을 억지로 넣지 않았다. 수치 계산 및 LangGraph 연결은 검증된 계산 함수와 입력 계약을 정의한 다음 버전에서 추가한다.

## 5. 출력 계약과 평가

항상 `action`, `claim_id`, `evidence_refs`를 출력한다. CHALLENGE에는 `reason`, REQUEST_EVIDENCE에는 `reason`과 `requested_evidence`가 추가된다. `action_schema_v01.json`이 허용 필드를 정한다.

문법 검사는 수학·공학 타당성 판정과 별도다. 제공 도구는 허용 key, reason, 참조 ID, 대상 claim의 일치를 검사한다. 의미 평가는 검토한 gold 후보와 비교한다.

baseline은 다음을 구분해 저장한다.

1. **Strict JSON:** 코드블록 제거·중괄호 부분 추출 없이 전체 출력이 JSON 객체인지
2. **Schema validity:** 필수 필드와 참조가 맞는지
3. **Action match:** 행동 종류가 라벨 후보와 같은지
4. **Full match:** 필수 필드·이유·근거/요청 ID가 맞는지. ID 배열 순서는 무시
5. **Pair success:** 같은 쌍의 양쪽 상태에서 모두 맞는지
6. **False interventions:** NO_ACTION 후보를 잘못 CHALLENGE/REQUEST로 처리한 건수
7. **실행 자원:** 입력/출력 토큰, generation 시간, GPU 최대 allocated 메모리

레이블은 원문에 들어 있는 API 응답이 아니라, 저자의 원리와 DoriLab 검토정책을 조합한 후보이므로 실제 엔지니어 검토를 거친다. 임의의 라벨을 정답으로 강제해 점수만 높이는 문제를 피하려면, 동등한 타당한 행동이 있는지도 검토 기록에 남기는 것이 좋다.

## 6. 대조쌍 목록

열: 시험형상 대응, 배경복사/열용량 구분, 정상·과도시험의 목적, 복사계 코팅 대응, 개별 전력 소산, 노드별 평형, 센서/모델 노드 매핑, 시험장치의 복사면 차폐.

진동: 지지조건의 동적 차이, C² 선정 근거, f0 모드 정의, Eq.(2)의 서로 다른 최대값 주파수, CSMA 입력, 비결합 모델 적용범위, 확률 입력의 가정, 두 사례의 검증 범위.

## 7. 후속 확장과 독립 평가

원래 12개 후보를 바로 8/2/2로 확정하지 않았다. 전문을 확보한 문헌부터 원문 근거를 검토하고, 동일 프로그램·원실험·인용 데이터의 중복을 조사한 뒤 그룹 단위로 분리한다.

첫 32개는 전부 TRAIN_CANDIDATE다. 다른 자료에서 만든 예제가 독립 평가에 쓰일 때, 그 자료를 훈련에 썼는지뿐 아니라 문헌의 원 실험이 같은지도 확인한다. 예를 들어 JWST 관련 출처끼리는 전체 임무 수준으로 보수적으로 그룹을 묶는 방식과 하위 시험 프로그램 수준 분리의 장단점을 별도로 기록한다.

기존 Eval40은 기존 구조화 계약의 회귀 자료로 유지한다. 새 문헌 기반 평가가 기존 20개보다 얼마나 어려운지는 실제 baseline에서 확인한다. 현재 Seed에는 한 검토점과 한 출처 사실이 주어지므로 아직 복수 문서 탐색·다단계 도구실행·변경 후 부분 재검토 전체를 시험하지 않는다.
