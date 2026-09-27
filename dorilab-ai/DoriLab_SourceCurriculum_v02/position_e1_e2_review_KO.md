# DoriLab position e1 vs e2 결과 검토

2026-09-19 · 업로드된 원출력 재계산 · 새 학습/추론 없음

## 결론
e2를 현재 개발용 비교 기준으로 보존한다. e1도 유지한다. 동일40개에서 3epoch·추가 학습률 탐색은 멈추고 새로운 시나리오/출처군 평가로 이동한다. 전체 계약은 개선됐지만, 학습에 사용하지 않은 같은 출처20개에서는 개선이 제한적이며 새로운 정상 사례 오경고도 발생했다.

## 조건별 비교
| 조건 | e1 action | e2 action | e1 전체 계약 | e2 전체 계약 | e1 정확 근거 | e2 정확 근거 |
|---|---:|---:|---:|---:|---:|---:|
| 대조 입력 | 35/40 | 37/40 | 30/40 | 33/40 | 40/40 | 40/40 |
| 무관 관측 뒤 | 34/40 | 37/40 | 29/40 | 33/40 | 40/40 | 40/40 |
| 무관 관측 앞 | 31/40 | 36/40 | 25/40 | 31/40 | 40/40 | 39/40 |

정확 근거: 현재 정답의 evidence_refs 집합과 정확히 일치하며 중복이 없는 출력. e1은 기존 보고서, e2는 raw JSONL의 expected와 parsed로 재계산했다. 이번 출력에서는 strict 선택 점수와 저장된 contract_pass가 같다. 이는 일반적인 두 지표의 동일성을 의미하지 않는다.

## 학습대상20 vs 같은 출처 나머지20
| 조건 | 학습대상 e1 → e2 | 같은 출처 나머지 e1 → e2 |
|---|---:|---:|
| 대조 입력 | 17/20 → 20/20 | 13/20 → 13/20 |
| 무관 관측 뒤 | 16/20 → 20/20 | 13/20 → 13/20 |
| 무관 관측 앞 | 14/20 → 19/20 | 11/20 → 12/20 |

세 입력 변형은 독립 표본이 아니다. 나머지20은 기존 출력으로 선택한 같은 출처의 개발용 진단이다. e2의 학습대상20 성공은 원문 읽기 능력의 독립 일반화 성능이 아니다.

## 앞쪽 무관 관측 조건의 실패 9개
4개 action 오류 + 4개 reason-only 오류 + 1개 근거 ID 오류. 다른 오류와 중복 없는 주 분류다.
| 사례 | 실패 유형 | 기준 정답 | 출력 |
|---|---|---|---|
| PHY-TH01-P08-A | REASON | TEST_ARTIFACT_UNMODELED | BOUNDARY_CONDITION_UNRESOLVED |
| PHY-VBX1-P08-A | REASON | MODEL_SCOPE_EXCEEDED | PROBABILISTIC_ASSUMPTIONS_UNRESOLVED |
| PHY-TH01-P01-B | ACTION | NO_ACTION_REQUIRED | CHALLENGE |
| PHY-TH01-P04-B | ACTION | NO_ACTION_REQUIRED | REQUEST_EVIDENCE |
| PHY-TH01-P07-B | ACTION | NO_ACTION_REQUIRED | CHALLENGE |
| PHY-VBX1-P04-A | ACTION | CHALLENGE | NO_ACTION_REQUIRED |
| PHY-VBX1-P06-A | REASON | MODEL_SCOPE_EXCEEDED | MODE_SELECTION_MISMATCH |
| PHY-VBX1-P05-A | REASON | MODAL_INPUTS_MISSING | PARAMETER_IDENTIFICATION_INSUFFICIENT |
| PHY-EE03-P01-A | REFERENCE | SF-5591, OBS-7590 | SF-5591, OBS-7595 |

## 추가로 확인한 성능과 한계
- 세 조건 모두 정확 통과한 고유 사례: e1 25/40 → e2 30/40.
- 앞/뒤 순서만 다른 조건에서 action 변경: e1 3건 → e2 1건(TH01-P01-B).
- 앞/뒤 인용 근거 변경: e1 0건 → e2 1건(EE03-P01-A).
- EE03-P01-A의 앞 조건: OBS-7590 대신 OBS-7595를 출력. 저장된 검증기가 unprovided evidence reference로 거부했다. 무관 관측을 선택한 오류가 아니라 입력에 없는 ID 출력이다.
- 기존 Contract20: e1 20/20; e2도 이전 업로드 콘솔에서20/20. 최신6개 파일에는 Contract 원시 JSONL이 없어 이 점수는 이번에 행별 재계산하지 않았다.
- 학습 가중치 본체·adapter는 여기로 업로드되지 않았다. 명시된 adapter hash는 평가 summary에서 일치함을 확인한 값이다.
- source packet과 dcurr schema 실행환경이 이번 입력에 없어 실제 물리 근거와 라벨의 타당성을 새로 판정하지 않았다. reason 이름의 유사성만으로 대체 정답을 추가하지 않았다.

## 판정 유지 및 다음 단계 (제안)
1. e2와 e1의 가중치·현재 프롬프트·평가 코드·210행 데이터·원출력 해시를 보존한다. 같은 40개에서 더 높은 수치를 얻기 위한 추가epoch는 진행하지 않는다.
2. 새로운 평가 질문을 사람이 정의하고 동결한다. 첫 범위는 새 형상/판본 대응, 필요한 자료가 정말 빠진 조건, 근거와 proposal의 반증 관계를 포함한다. 정상 사례와 부적절한 사례를 균형 있게 둔다.
3. 같은 새 평가에 e1/e2를 한 번씩 적용한다. 이후 상위 모델 비교도 같은 업무·출력 계약에서 수행하며 모델별 template/추론 예산/양자화를 별도 기록한다.
4. 새로운 평가 결과를 보고 학습자료에 넣었다면 그 세트는 다음부터 개발·회귀용으로 바꾼다.

## 사례별 출력과 개선/퇴행 상세

### 대조 입력

새 통과 5건: PHY-TH01-P06-A, PHY-TH01-P01-A, PHY-TH01-P03-A, PHY-VBX1-P07-A, PHY-EE02-P01-A
새 실패 2건: PHY-TH01-P06-B, PHY-TH01-P04-B

#### PHY-TH01-P06-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-006",
  "evidence_refs": [
    "SF-9760",
    "OBS-4784"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "STABILITY_UNRESOLVED",
  "claim_id": "CLM-006",
  "evidence_refs": [
    "SF-9760",
    "OBS-4784"
  ]
}
```
#### PHY-TH01-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "TEST_ARTIFACT_UNMODELED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
#### PHY-VBX1-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "PROBABILISTIC_ASSUMPTIONS_UNRESOLVED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
#### PHY-TH01-P04-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "RADIOMETRIC_EQUIVALENCE_UNRESOLVED",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ],
  "requested_evidence": [
    "SPECTRAL_ABSORPTANCE_OR_COATING_MAPPING"
  ]
}
```
#### PHY-VBX1-P04-A · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "METHOD_INTERPRETATION_ERROR",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
e2:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
#### PHY-VBX1-P06-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "MODE_SELECTION_MISMATCH",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ]
}
```
#### PHY-VBX1-P05-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "MODAL_INPUTS_MISSING",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "PARAMETER_IDENTIFICATION_INSUFFICIENT",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```

### 무관 관측 뒤

새 통과 6건: PHY-VBX1-P02-A, PHY-TH01-P06-A, PHY-TH01-P03-A, PHY-VBX1-P07-A, PHY-EE02-P01-A, PHY-EE03-P02-A
새 실패 2건: PHY-TH01-P04-B, PHY-TH01-P07-B

#### PHY-TH01-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "TEST_ARTIFACT_UNMODELED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
#### PHY-VBX1-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "PROBABILISTIC_ASSUMPTIONS_UNRESOLVED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
#### PHY-TH01-P04-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ],
  "reason": "RADIOMETRIC_EQUIVALENCE_UNRESOLVED",
  "requested_evidence": [
    "SPECTRAL_ABSORPTANCE_OR_COATING_MAPPING"
  ]
}
```
#### PHY-TH01-P07-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-007",
  "evidence_refs": [
    "SF-5382",
    "OBS-1385"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "MEASUREMENT_MAPPING_MISMATCH",
  "claim_id": "CLM-007",
  "evidence_refs": [
    "SF-5382",
    "OBS-1385"
  ]
}
```
#### PHY-VBX1-P04-A · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "METHOD_INTERPRETATION_ERROR",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
e2:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
#### PHY-VBX1-P06-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ],
  "reason": "MODE_SELECTION_MISMATCH"
}
```
#### PHY-VBX1-P05-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "MODAL_INPUTS_MISSING",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "PARAMETER_IDENTIFICATION_INSUFFICIENT",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```

### 무관 관측 앞

새 통과 9건: PHY-VBX1-P02-A, PHY-TH01-P06-A, PHY-TH01-P07-A, PHY-TH01-P01-A, PHY-TH01-P03-A, PHY-TH01-P05-A, PHY-VBX1-P07-A, PHY-EE02-P01-A, PHY-EE03-P02-A
새 실패 3건: PHY-TH01-P01-B, PHY-TH01-P04-B, PHY-TH01-P07-B

#### PHY-TH01-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "TEST_ARTIFACT_UNMODELED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "claim_id": "CLM-008",
  "evidence_refs": [
    "SF-3719",
    "OBS-9800"
  ]
}
```
#### PHY-VBX1-P08-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "PROBABILISTIC_ASSUMPTIONS_UNRESOLVED",
  "claim_id": "CLM-016",
  "evidence_refs": [
    "SF-1191",
    "OBS-5162"
  ]
}
```
#### PHY-TH01-P01-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-001",
  "evidence_refs": [
    "SF-2523",
    "OBS-8012"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "claim_id": "CLM-001",
  "evidence_refs": [
    "SF-2523",
    "OBS-8012"
  ]
}
```
#### PHY-TH01-P04-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "RADIOMETRIC_EQUIVALENCE_UNRESOLVED",
  "claim_id": "CLM-004",
  "evidence_refs": [
    "SF-1062",
    "OBS-7280"
  ],
  "requested_evidence": [
    "SPECTRAL_ABSORPTANCE_OR_COATING_MAPPING"
  ]
}
```
#### PHY-TH01-P07-B · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-007",
  "evidence_refs": [
    "SF-5382",
    "OBS-1385"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "reason": "MEASUREMENT_MAPPING_MISMATCH",
  "claim_id": "CLM-007",
  "evidence_refs": [
    "SF-5382",
    "OBS-1385"
  ]
}
```
#### PHY-VBX1-P04-A · remainder_same_source20
유형: ACTION_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "METHOD_INTERPRETATION_ERROR",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
e2:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-012",
  "evidence_refs": [
    "SF-1221",
    "OBS-1068"
  ]
}
```
#### PHY-VBX1-P06-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "CHALLENGE",
  "reason": "MODEL_SCOPE_EXCEEDED",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ]
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-014",
  "evidence_refs": [
    "SF-2325",
    "OBS-3542"
  ],
  "reason": "MODE_SELECTION_MISMATCH"
}
```
#### PHY-VBX1-P05-A · remainder_same_source20
유형: REASON_ONLY_WRONG
Expected:
```json
{
  "action": "REQUEST_EVIDENCE",
  "reason": "MODAL_INPUTS_MISSING",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```
e2:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-013",
  "evidence_refs": [
    "SF-5237",
    "OBS-4417"
  ],
  "reason": "PARAMETER_IDENTIFICATION_INSUFFICIENT",
  "requested_evidence": [
    "RESIDUAL_MASS_AND_DAMPING"
  ]
}
```
#### PHY-EE03-P01-A · selected20
유형: REFERENCE_SET_WRONG, SCHEMA_OR_REFERENCE_INVALID
Expected:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-EE03-P01",
  "evidence_refs": [
    "SF-5591",
    "OBS-7590"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT"
}
```
e2:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-EE03-P01",
  "evidence_refs": [
    "SF-5591",
    "OBS-7595"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT"
}
```

## 재계산 근거 파일
- `comparison.json` / SHA256 `f0cb629a6cc88a8cd37c0a93b480c275f9cc8ba372cb01632e0f5e30f56245ca`
- `comparison_cases.jsonl` / SHA256 `45c939c1b87ba994a95369ed6e1be9ed29ba3011054acc21510ba9ab603d943b`
- `evidence_training_v05_position_e2_control.jsonl` / SHA256 `f4606f55204a84d9e0277942c82c4ca96138f856e7ce83645fc60af957d544b2`
- `evidence_training_v05_position_e2_control.summary.json` / SHA256 `7bebd878cc396d269ca4841a839d2d66c93d17aaf6de80437099ba9c3c366bed`
- `evidence_training_v05_position_e2_after.jsonl` / SHA256 `3139b9bb824a15f59e785b821a24e9a5f7ebccacc56f340ee3205230789fd942`
- `evidence_training_v05_position_e2_after.summary.json` / SHA256 `d3cca90ec8d5e6fdf756b092a17aa6663e856d46879871618ba1b331999fee53`
- `evidence_training_v05_position_e2_before.jsonl` / SHA256 `0287dee5ff5c6285deb4c0d6700591bbc2e79ae4e6b93c875981ea04f353a9c8`
- `evidence_training_v05_position_e2_before.summary.json` / SHA256 `494d0ce94591516f3bb20540dbafb4828af7342e090425ba7e86fd5b245e1a7d`
