# 원문 기반 기대정답 검토 카드

상태: SOURCE_GROUNDED_AI_CANDIDATE. 작성 모델의 원문 대조와 프로그램 검사를 거친 후보이며 독립 사람 검토는 미수행이다.
모든 장비, 실측처럼 보이는 숫자, 관측과 제안은 합성 사례다. 원문에는 검토 원리만 귀속한다.

## SR13-TIRS | Lessons Learned during Instrument Testing for the Thermal Infrared Sensor (TIRS)
출처: https://ntrs.nasa.gov/citations/20160000799
자료 범위: 12-page conference paper; use body sections IV, V, VI

### SR13-TIRS-GSE
원문 위치: IV. TIRS TV Testing Setup Lessons Learned / PDF 페이지 [4]
근거 요약: Thin, partly blanketed heater panels developed temperature gradients; coarse panel nodes could not represent measured boundaries and heater placement.

#### CASE-4ad9ed95e2
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Reject the request to examine local boundary mapping: agreement of the one-node value with the arithmetic mean already demonstrates agreement at all three sensor locations.

관측 OBS-7236530f53: A one-node panel representation outputs 300 K. The review concerns whether this node reproduces the three local measured boundary temperatures, not whether its area mean matches.
관측 OBS-bad8f81d5f: A synthetic chamber heater panel has calibrated sensors at 281 K, 300 K and 319 K.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-2d838504f6",
  "evidence_refs": [
    "REF-184ff72326",
    "OBS-bad8f81d5f",
    "OBS-7236530f53"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH"
}
```
평균 일치와 각 위치의 일치는 다른 비교다. 해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다. 입력 준비 검토에서는 위치 대응표의 실제 존재만 판단한다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-d0190c27bc

#### CASE-79c814ab47
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Retain the mean-temperature match and flag the unresolved local temperature mapping before using the node for location-specific correlation.

관측 OBS-6d2db00e53: A one-node panel representation outputs 300 K. The review concerns whether this node reproduces the three local measured boundary temperatures, not whether its area mean matches.
관측 OBS-014b0801ff: A synthetic chamber heater panel has calibrated sensors at 281 K, 300 K and 319 K.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-eb3c247483",
  "evidence_refs": [
    "REF-e1b9e353e0",
    "OBS-014b0801ff",
    "OBS-6d2db00e53"
  ]
}
```
평균 일치와 각 위치의 일치는 다른 비교다. 해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다. 입력 준비 검토에서는 위치 대응표의 실제 존재만 판단한다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-d0190c27bc

#### CASE-424419171a
**질문:** Is the supplied record sufficient to compare the model temperature at each of the three sensor locations? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-c270132c17: The three sensor temperatures and one-node mean are supplied. No sensor coordinates or model-to-sensor sampling map is included; there is no alternative local mapping in this packet.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-dfe5a42600",
  "evidence_refs": [
    "REF-86ba769f51",
    "OBS-c270132c17"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH",
  "requested_evidence": [
    "SENSOR_NODE_MAP"
  ]
}
```
평균 일치와 각 위치의 일치는 다른 비교다. 해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다. 입력 준비 검토에서는 위치 대응표의 실제 존재만 판단한다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-d0190c27bc

#### CASE-e00c7fe02d
**질문:** Is the supplied record sufficient to compare the model temperature at each of the three sensor locations? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-30f3093d41: Three calibrated local temperatures, sensor coordinates and the model sampling map are supplied. The model exports a separate temperature at every mapped sensor location. The requested check is input readiness only.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-4af1003cb9",
  "evidence_refs": [
    "REF-b2f2d4fb0c",
    "OBS-30f3093d41"
  ]
}
```
평균 일치와 각 위치의 일치는 다른 비교다. 해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다. 입력 준비 검토에서는 위치 대응표의 실제 존재만 판단한다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-d0190c27bc

### SR13-TIRS-ASBUILT
원문 위치: V.A. Pre-Test Model Audit / PDF 페이지 [5, 6]
근거 요약: The TIRS audit found model differences in geometry, material, radiator area and mass relative to as-built hardware; correlation changes were not solely uncertain parameter adjustments.

#### CASE-589fb4eb03
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Treat the discrepancy as uniquely caused by uncertain emissivity and leave the known area mismatch outside the correlation review.

관측 OBS-e1a7680686: Material-property uncertainty has not yet been quantified.
관측 OBS-11d9a9bf35: A synthetic thermal correlation package records a 0.18 m2 exposed radiator in the analytical model and a measured 0.12 m2 exposed area in the tested configuration.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-7ad8281f2a",
  "evidence_refs": [
    "REF-429060d5de",
    "OBS-11d9a9bf35",
    "OBS-e1a7680686"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
확인된 형상 차이가 있는 상태에서 물성 하나를 유일한 원인으로 특정할 근거가 없다. 먼저 알려진 형상 차이를 비교하는 제안은 제한된 검토 범위에서 타당하다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-9f5d1a8add

#### CASE-199314f362
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Reconcile the known exposed-area mismatch and preserve uncertainty in the remaining cause; this check does not identify emissivity uniquely.

관측 OBS-fb6a751c2c: Material-property uncertainty has not yet been quantified.
관측 OBS-a3039e2d43: A synthetic thermal correlation package records a 0.18 m2 exposed radiator in the analytical model and a measured 0.12 m2 exposed area in the tested configuration.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-a483a84bb2",
  "evidence_refs": [
    "REF-eaa79b1941",
    "OBS-a3039e2d43",
    "OBS-fb6a751c2c"
  ]
}
```
확인된 형상 차이가 있는 상태에서 물성 하나를 유일한 원인으로 특정할 근거가 없다. 먼저 알려진 형상 차이를 비교하는 제안은 제한된 검토 범위에서 타당하다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-9f5d1a8add

#### CASE-555ca15e0e
**질문:** Are the geometry records ready for an as-built radiator-area comparison? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-db9763621c: The model area is available, but the as-tested exposed area and blanket-edge geometry have not been supplied. No equivalent as-built inspection is present.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-783ac16b73",
  "evidence_refs": [
    "REF-dabc5e621f",
    "OBS-db9763621c"
  ],
  "reason": "CONFIGURATION_SCOPE_UNRESOLVED",
  "requested_evidence": [
    "AS_TESTED_RADIATOR_GEOMETRY"
  ]
}
```
확인된 형상 차이가 있는 상태에서 물성 하나를 유일한 원인으로 특정할 근거가 없다. 먼저 알려진 형상 차이를 비교하는 제안은 제한된 검토 범위에서 타당하다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-9f5d1a8add

#### CASE-a6135d12df
**질문:** Are the geometry records ready for an as-built radiator-area comparison? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-4722c39a0f: A revision-matched as-tested blanket-edge inspection and exposed-area calculation are supplied alongside the model geometry. This establishes comparison readiness, not temperature accuracy.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-4a08f72a69",
  "evidence_refs": [
    "REF-fb54001029",
    "OBS-4722c39a0f"
  ]
}
```
확인된 형상 차이가 있는 상태에서 물성 하나를 유일한 원인으로 특정할 근거가 없다. 먼저 알려진 형상 차이를 비교하는 제안은 제한된 검토 범위에서 타당하다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-9f5d1a8add

### SR13-TIRS-BASELINE
원문 위치: V.C. Pre-Correlation Check / PDF 페이지 [6]
근거 요약: The authors recommend retaining a pre-test model with only known test powers and GSE conditions updated, for hot and cold baseline comparisons before further correlation changes.

#### CASE-a7e82e186e
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Label the B residual table as the pre-test-model error because it uses the latest measured GSE temperatures.

관측 OBS-37c13f900d: Version A of a synthetic thermal model is the pre-test model. Version B changes contact conductance, geometry and GSE temperatures. Only B residuals are in the draft table; the question is the error of the original pre-test model under measured test conditions.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-9ccadb94e5",
  "evidence_refs": [
    "REF-faacdc56b7",
    "OBS-37c13f900d"
  ],
  "reason": "METHOD_INTERPRETATION_ERROR"
}
```
비교 대상 버전을 바꾸면 사전 예측 오차와 상관 후 오차가 섞인다. 필요한 비교 run이 없으면 자료를 요청하고, 해당 run과 변경 기록이 있으면 비교를 시작할 수 있다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-43933f27b5

#### CASE-fe8f8cbdf7
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Keep B as a correlated-model result and obtain an A-derived run that updates only measured test inputs for the pre-test comparison.

관측 OBS-3c7b9c4608: Version A of a synthetic thermal model is the pre-test model. Version B changes contact conductance, geometry and GSE temperatures. Only B residuals are in the draft table; the question is the error of the original pre-test model under measured test conditions.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-543c5a57fb",
  "evidence_refs": [
    "REF-d99ef46538",
    "OBS-3c7b9c4608"
  ]
}
```
비교 대상 버전을 바꾸면 사전 예측 오차와 상관 후 오차가 섞인다. 필요한 비교 run이 없으면 자료를 요청하고, 해당 run과 변경 기록이 있으면 비교를 시작할 수 있다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-43933f27b5

#### CASE-acec2b7b89
**질문:** Can the original pre-test model error be compared at both balance points using the supplied versions? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-a00bfe924b: The original A archive and measured powers are available, but no A-derived hot/cold runs with only measured boundary inputs updated have been provided.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-e8d0d5b69d",
  "evidence_refs": [
    "REF-49085bb122",
    "OBS-a00bfe924b"
  ],
  "reason": "SUPPORTING_EVIDENCE_MISSING",
  "requested_evidence": [
    "PRETEST_COMPARISON_RUNS"
  ]
}
```
비교 대상 버전을 바꾸면 사전 예측 오차와 상관 후 오차가 섞인다. 필요한 비교 run이 없으면 자료를 요청하고, 해당 run과 변경 기록이 있으면 비교를 시작할 수 있다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-43933f27b5

#### CASE-d400650f82
**질문:** Can the original pre-test model error be compared at both balance points using the supplied versions? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-cf5917d55a: The immutable A archive, measured test inputs and A-derived hot/cold runs are supplied; their diff confirms that only those measured inputs changed. The task is readiness of this comparison.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-34d810ae51",
  "evidence_refs": [
    "REF-31de070f93",
    "OBS-cf5917d55a"
  ]
}
```
비교 대상 버전을 바꾸면 사전 예측 오차와 상관 후 오차가 섞인다. 필요한 비교 run이 없으면 자료를 요청하고, 해당 run과 변경 기록이 있으면 비교를 시작할 수 있다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-43933f27b5

### SR13-TIRS-CULL
원문 위치: VI. TIRS TV Analysis Techniques Lessons Learned / PDF 페이지 [7]
근거 요약: Small radiative couplings can still carry relevant heat when temperature differences are large. Coupling removal needs verification rather than a magnitude threshold alone.

#### CASE-88b5d13600
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Discard the path solely because k is numerically small; no heat-flow calculation is needed to apply the supplied omission criterion.

관측 OBS-3bbdfddc83: A synthetic model uses q=k*(Th^4-Tc^4), with k=1.0e-10 W/K4, Th=300 K and Tc=100 K. The case-specific review threshold for an omitted path is 0.5 W. These are supplied toy-model assumptions, not values or limits from the paper.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-c65be13b96",
  "evidence_refs": [
    "REF-40fab2f07a",
    "OBS-3bbdfddc83"
  ],
  "reason": "METHOD_INTERPRETATION_ERROR"
}
```
판정식의 입력과 임계값은 합성 사례가 명시한다. 작은 계수만으로 생략하지 않고 열류를 계산해 조건과 비교해야 한다. 논문에 새 합격 기준을 부여하지 않는다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-bffe89a7f0

#### CASE-4196d4ddc2
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Retain the path for this review because its computed heat flow exceeds the supplied omission threshold; record the formula and assumed temperatures.

관측 OBS-6772b1460a: A synthetic model uses q=k*(Th^4-Tc^4), with k=1.0e-10 W/K4, Th=300 K and Tc=100 K. The case-specific review threshold for an omitted path is 0.5 W. These are supplied toy-model assumptions, not values or limits from the paper.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-a6a904c885",
  "evidence_refs": [
    "REF-a9a0f06520",
    "OBS-6772b1460a"
  ]
}
```
판정식의 입력과 임계값은 합성 사례가 명시한다. 작은 계수만으로 생략하지 않고 열류를 계산해 조건과 비교해야 한다. 논문에 새 합격 기준을 부여하지 않는다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-bffe89a7f0

#### CASE-9c036b2503
**질문:** Are the inputs sufficient to compute this path heat flow under the stated formula? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-18ed1cb86d: The coupling coefficient and hot-side temperature are supplied; the cold-side temperature is missing and no bounding value has been authorized.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-b7ee0af3bb",
  "evidence_refs": [
    "REF-c22adc2fb8",
    "OBS-18ed1cb86d"
  ],
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "requested_evidence": [
    "PATH_TEMPERATURES"
  ]
}
```
판정식의 입력과 임계값은 합성 사례가 명시한다. 작은 계수만으로 생략하지 않고 열류를 계산해 조건과 비교해야 한다. 논문에 새 합격 기준을 부여하지 않는다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-bffe89a7f0

#### CASE-1bdc9a0a66
**질문:** Are the inputs sufficient to compute this path heat flow under the stated formula? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-5cd59645be: The coefficient, both absolute temperatures, the formula and their units are supplied. This input-readiness check does not by itself authorize model reduction.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-c932299089",
  "evidence_refs": [
    "REF-d73ad09675",
    "OBS-5cd59645be"
  ]
}
```
판정식의 입력과 임계값은 합성 사례가 명시한다. 작은 계수만으로 생략하지 않고 열류를 계산해 조건과 비교해야 한다. 논문에 새 합격 기준을 부여하지 않는다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-bffe89a7f0

## SR13-NEA | Testing and Maturing a Mass Translating Mechanism for a Deep Space CubeSat
출처: https://ntrs.nasa.gov/citations/20180005148
자료 범위: 3-page Executive Summary, not the final full proceedings paper

### SR13-NEA-LEVELS
원문 위치: Executive Summary, opening paragraph / PDF 페이지 [1, 2]
근거 요약: AMT functional and workmanship vibration checks passed before subsequent vacuum motor failures. Passing one test type did not resolve the different vacuum failure mechanism.

#### CASE-7e2ce553dd
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Record powered motion in vacuum as demonstrated using the workmanship-vibration pass alone.

관측 OBS-b2527a454b: A synthetic translation stage has a completed workmanship-vibration report with no recorded anomaly. No vacuum-powered motion run has been performed for the current motor installation. The review is the evidence basis for a claim of demonstrated vacuum motion.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-9071fa44be",
  "evidence_refs": [
    "REF-1b7ee7fdb4",
    "OBS-b2527a454b"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
시험 종류와 환경 범위를 구분한다. 한 종류의 시험 통과를 다른 환경에서의 실증으로 옮겨 적지 않는다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f10ef0e47e

#### CASE-ed9b08cbf4
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Retain the vibration pass within its own scope and leave powered vacuum motion unverified until relevant evidence is available.

관측 OBS-f03d8d5eaa: A synthetic translation stage has a completed workmanship-vibration report with no recorded anomaly. No vacuum-powered motion run has been performed for the current motor installation. The review is the evidence basis for a claim of demonstrated vacuum motion.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-17e6bfb490",
  "evidence_refs": [
    "REF-1a193e0347",
    "OBS-f03d8d5eaa"
  ]
}
```
시험 종류와 환경 범위를 구분한다. 한 종류의 시험 통과를 다른 환경에서의 실증으로 옮겨 적지 않는다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f10ef0e47e

#### CASE-c51cdfeccd
**질문:** Is the evidence package ready for the requested powered-vacuum-motion assessment? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-9c78258aa7: The vibration report and ambient functional log are supplied. Vacuum-powered motion data for this installation are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-69be756572",
  "evidence_refs": [
    "REF-b2fa724323",
    "OBS-9c78258aa7"
  ],
  "reason": "SUPPORTING_EVIDENCE_MISSING",
  "requested_evidence": [
    "VACUUM_MOTION_RUN"
  ]
}
```
시험 종류와 환경 범위를 구분한다. 한 종류의 시험 통과를 다른 환경에서의 실증으로 옮겨 적지 않는다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f10ef0e47e

#### CASE-493773aa90
**질문:** Is the evidence package ready for the requested powered-vacuum-motion assessment? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-c2a2b27f8a: A configuration-matched vacuum-powered motion run includes pressure, temperature, commands and measured stage travel. The task only asks whether those assessment inputs are available.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-a8d0fd18f1",
  "evidence_refs": [
    "REF-3886967cf0",
    "OBS-c2a2b27f8a"
  ]
}
```
시험 종류와 환경 범위를 구분한다. 한 종류의 시험 통과를 다른 환경에서의 실증으로 옮겨 적지 않는다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f10ef0e47e

### SR13-NEA-COIL
원문 위치: Executive Summary, second and third TVAC campaigns / PDF 페이지 [2, 3]
근거 요약: External thermal readings remained below a motor limit while failures persisted. The team investigated the internal heat path and measured coil temperature immediately after operation.

#### CASE-02caf2a304
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Exclude internal-coil overheating from the investigation because the housing reading is below the internal-coil limit.

관측 OBS-5271066c70: A synthetic motor test records housing temperature of 42 C and a stalled stage during vacuum operation.
관측 OBS-b90c09bd56: The stated internal-coil limit is 95 C. Neither coil temperature nor a validated housing-to-coil model is available.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-288f5e020f",
  "evidence_refs": [
    "REF-6fe83a7012",
    "OBS-5271066c70",
    "OBS-b90c09bd56"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH"
}
```
42 C는 하우징 관측이고 95 C는 코일 기준이다. 대응 관계가 없으면 직접 비교로 내부 과열을 배제할 수 없다. 실제 코일의 과열 발생 여부는 미확정으로 남긴다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-a23c98c073

#### CASE-2f88f50fa1
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Keep internal-coil temperature unresolved and distinguish the housing measurement from the quantity to which the limit applies.

관측 OBS-0d621e75e1: The stated internal-coil limit is 95 C. Neither coil temperature nor a validated housing-to-coil model is available.
관측 OBS-1c77c75e7d: A synthetic motor test records housing temperature of 42 C and a stalled stage during vacuum operation.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-65c8fbbdde",
  "evidence_refs": [
    "REF-13fbdafc97",
    "OBS-1c77c75e7d",
    "OBS-0d621e75e1"
  ]
}
```
42 C는 하우징 관측이고 95 C는 코일 기준이다. 대응 관계가 없으면 직접 비교로 내부 과열을 배제할 수 없다. 실제 코일의 과열 발생 여부는 미확정으로 남긴다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-a23c98c073

#### CASE-07dbc2c8c4
**질문:** Are the supplied temperatures sufficient to compare internal-coil temperature with its stated limit? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-057cea5fcd: Only a calibrated housing sensor trace is supplied. No coil measurement or validated mapping to coil temperature is available.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-1109eabc0b",
  "evidence_refs": [
    "REF-149db96c66",
    "OBS-057cea5fcd"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH",
  "requested_evidence": [
    "COIL_TEMPERATURE_BASIS"
  ]
}
```
42 C는 하우징 관측이고 95 C는 코일 기준이다. 대응 관계가 없으면 직접 비교로 내부 과열을 배제할 수 없다. 실제 코일의 과열 발생 여부는 미확정으로 남긴다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-a23c98c073

#### CASE-61ef0e9728
**질문:** Are the supplied temperatures sufficient to compare internal-coil temperature with its stated limit? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-6576498025: A documented coil-temperature measurement with timing and calibration is supplied for the reviewed operation, alongside the coil-specific limit. Other failure causes are outside this readiness check.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-e93e8079e6",
  "evidence_refs": [
    "REF-a3b8f2ad7d",
    "OBS-6576498025"
  ]
}
```
42 C는 하우징 관측이고 95 C는 코일 기준이다. 대응 관계가 없으면 직접 비교로 내부 과열을 배제할 수 없다. 실제 코일의 과열 발생 여부는 미확정으로 남긴다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-a23c98c073

### SR13-NEA-TRANSLATION
원문 위치: Executive Summary, third TVAC campaign / PDF 페이지 [3]
근거 요약: Motors operated nominally in the third campaign while translation degraded at low temperature. Motor function and mechanism translation were distinct observations.

#### CASE-d5e287468e
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Accept the stage travel requirement as met because the motor completed its rotation command.

관측 OBS-e8fdbb348b: The encoder check is valid for this run; the cause of lost travel is not yet established.
관측 OBS-9472cee2d3: In a synthetic cold run the motor completes its commanded rotations, but an independent stage encoder measures 4 mm travel against a specified 12 mm travel.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-f95e6bcfae",
  "evidence_refs": [
    "REF-747dfed5a3",
    "OBS-9472cee2d3",
    "OBS-e8fdbb348b"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
모터 회전 완료가 실제 이송 거리 충족을 대신하지 않는다. 이송량을 관측하는 채널이 있어야 해당 성능을 비교할 수 있다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f6088ffdf8

#### CASE-6d4be78aae
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Record motor rotation and stage travel separately, and retain the travel shortfall for investigation without assigning its cause.

관측 OBS-19bb334631: In a synthetic cold run the motor completes its commanded rotations, but an independent stage encoder measures 4 mm travel against a specified 12 mm travel.
관측 OBS-ce88812c09: The encoder check is valid for this run; the cause of lost travel is not yet established.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-9dee4f8f35",
  "evidence_refs": [
    "REF-c294cc376c",
    "OBS-19bb334631",
    "OBS-ce88812c09"
  ]
}
```
모터 회전 완료가 실제 이송 거리 충족을 대신하지 않는다. 이송량을 관측하는 채널이 있어야 해당 성능을 비교할 수 있다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f6088ffdf8

#### CASE-cf088dcb3c
**질문:** Is the measurement package ready to assess stage travel against the commanded distance? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-696dfaffa2: The motor rotation command and supply current are recorded, but measured stage displacement is absent and there is no validated kinematic mapping for this loaded configuration.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-376bd5f7e9",
  "evidence_refs": [
    "REF-c37339296b",
    "OBS-696dfaffa2"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT",
  "requested_evidence": [
    "STAGE_DISPLACEMENT_TRACE"
  ]
}
```
모터 회전 완료가 실제 이송 거리 충족을 대신하지 않는다. 이송량을 관측하는 채널이 있어야 해당 성능을 비교할 수 있다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f6088ffdf8

#### CASE-879754a57b
**질문:** Is the measurement package ready to assess stage travel against the commanded distance? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-8a2a49b8ff: The stage encoder calibration, time-aligned displacement and commanded distance are supplied for the reviewed configuration. The question is measurement availability rather than the resulting pass/fail.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-9797f10ccb",
  "evidence_refs": [
    "REF-dae2c5f155",
    "OBS-8a2a49b8ff"
  ]
}
```
모터 회전 완료가 실제 이송 거리 충족을 대신하지 않는다. 이송량을 관측하는 채널이 있어야 해당 성능을 비교할 수 있다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-f6088ffdf8

### SR13-NEA-PLANNED
원문 위치: Executive Summary, final paragraph / PDF 페이지 [3]
근거 요약: Bearing and differential-expansion issues were still under investigation. A redesign and a fourth TVAC test were described as future work, not demonstrated closure.

#### CASE-6de39fe5d2
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Close the cold-operation finding as verified on the basis of the approved redesign and scheduled retest.

관측 OBS-0d45eca060: A synthetic change record says a bearing redesign is approved for manufacture and a cold-vacuum retest is scheduled for next month. There is no execution record for the revised hardware in this dossier.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-4c130d9c28",
  "evidence_refs": [
    "REF-a6c374a3fe",
    "OBS-0d45eca060"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
미래 일정과 승인된 절차는 실측 결과와 별개다. 승인 계획을 보존하면서 실제 run의 근거가 확보될 때 종결 검토로 넘어간다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-94b82e4196

#### CASE-332bc07aa7
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Keep the finding open, retain the approved plan and link closure to later as-run results for the revised configuration.

관측 OBS-0720f9fbf4: A synthetic change record says a bearing redesign is approved for manufacture and a cold-vacuum retest is scheduled for next month. There is no execution record for the revised hardware in this dossier.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-b79807d1dc",
  "evidence_refs": [
    "REF-f5e5cd1843",
    "OBS-0720f9fbf4"
  ]
}
```
미래 일정과 승인된 절차는 실측 결과와 별개다. 승인 계획을 보존하면서 실제 run의 근거가 확보될 때 종결 검토로 넘어간다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-94b82e4196

#### CASE-c83a53985e
**질문:** Are execution records available to review the revised hardware after its planned retest? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-73c50ff2b9: Only the retest procedure and schedule are supplied. The run identity, execution log and measured results are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-23d3637a19",
  "evidence_refs": [
    "REF-17c9bbe648",
    "OBS-73c50ff2b9"
  ],
  "reason": "AS_RUN_MISSING",
  "requested_evidence": [
    "RETEST_AS_RUN"
  ]
}
```
미래 일정과 승인된 절차는 실측 결과와 별개다. 승인 계획을 보존하면서 실제 run의 근거가 확보될 때 종결 검토로 넘어간다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-94b82e4196

#### CASE-48f4545a71
**질문:** Are execution records available to review the revised hardware after its planned retest? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-ef9928441d: A new run ID, revised hardware configuration, as-run log and measured results are supplied. This check establishes that review inputs exist; formal closure still requires project authority.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-17ac1f74f5",
  "evidence_refs": [
    "REF-defd734484",
    "OBS-ef9928441d"
  ]
}
```
미래 일정과 승인된 절차는 실측 결과와 별개다. 승인 계획을 보존하면서 실제 run의 근거가 확보될 때 종결 검토로 넘어간다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-94b82e4196

## SR13-RHOBC | Vorago RH-OBC-1 Single Event Effect Characterization Test Report
출처: https://ntrs.nasa.gov/citations/20205006200
자료 범위: 11-page test report, body sections 1, 3.1 and 6

### SR13-RHOBC-RAILS
원문 위치: 1 Introduction / PDF 페이지 [2]
근거 요약: The board could gate power to the CAN transceiver rails; other standard-board peripherals lacked that independent power-cycle path.

#### CASE-54a9474954
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Describe the watchdog as able to power-cycle the Boot FRAM because the board contains a power-gating switch.

관측 OBS-55926b6494: The Boot FRAM is wired directly to the main rail. The watchdog output drives only the CAN-rail switch and the MCU reset pin.
관측 OBS-f096b6319b: A synthetic board schematic shows a switch on a CAN rail.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-2a8b129407",
  "evidence_refs": [
    "REF-002a709ed7",
    "OBS-f096b6319b",
    "OBS-55926b6494"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
전원 스위치의 존재보다 실제 연결 대상이 중요하다. CAN 레일 제어 경로를 Boot FRAM 제어로 확대할 수 없다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-053c3d8988

#### CASE-d3f978cae1
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Limit the power-cycle claim to the switched CAN rail and keep Boot FRAM recovery as a separate architectural question.

관측 OBS-c80a88c923: The Boot FRAM is wired directly to the main rail. The watchdog output drives only the CAN-rail switch and the MCU reset pin.
관측 OBS-2260537e8e: A synthetic board schematic shows a switch on a CAN rail.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-c69ec9e5a0",
  "evidence_refs": [
    "REF-75749ffd58",
    "OBS-2260537e8e",
    "OBS-c80a88c923"
  ]
}
```
전원 스위치의 존재보다 실제 연결 대상이 중요하다. CAN 레일 제어 경로를 Boot FRAM 제어로 확대할 수 없다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-053c3d8988

#### CASE-08ee9d45a5
**질문:** Are connectivity records sufficient to identify which peripheral rails the watchdog can cycle? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-51ce4cc302: The watchdog part number and a block label called power gating are supplied, but the switch-to-rail wiring and peripheral power assignments are missing.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-ce53f902c9",
  "evidence_refs": [
    "REF-521e601e69",
    "OBS-51ce4cc302"
  ],
  "reason": "CONFIGURATION_SCOPE_UNRESOLVED",
  "requested_evidence": [
    "POWER_RESET_NETLIST"
  ]
}
```
전원 스위치의 존재보다 실제 연결 대상이 중요하다. CAN 레일 제어 경로를 Boot FRAM 제어로 확대할 수 없다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-053c3d8988

#### CASE-d723874b9f
**질문:** Are connectivity records sufficient to identify which peripheral rails the watchdog can cycle? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-d6defde1b1: A revision-matched netlist identifies switch outputs, reset nets and peripheral rail assignments. The requested task is identifying control reachability, not assuming that recovery works in all faults.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-bf0e3b8266",
  "evidence_refs": [
    "REF-530c44b21c",
    "OBS-d6defde1b1"
  ]
}
```
전원 스위치의 존재보다 실제 연결 대상이 중요하다. CAN 레일 제어 경로를 Boot FRAM 제어로 확대할 수 없다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-053c3d8988

### SR13-RHOBC-MONITOR
원문 위치: 3.1 Hardware / PDF 페이지 [3]
근거 요약: Per-component voltage and current monitoring was added to help locate faults that blocked board communication.

#### CASE-9df6407dbd
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Identify the ADC as the unique cause of the communication loss from this evidence alone.

관측 OBS-d29024ea64: A synthetic board loses its serial heartbeat.
관측 OBS-3155ae94b7: Only whole-board current is logged; no peripheral voltage, current or local status was captured. The packet supplies no other evidence that identifies a failed component.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-95b22177f3",
  "evidence_refs": [
    "REF-5caf61c165",
    "OBS-d29024ea64",
    "OBS-3155ae94b7"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT"
}
```
통신 상실 관측은 확보됐지만 특정 부품 원인은 아직 분리되지 않았다. 추가 관측을 요구하는 절차와 원인을 단정하는 주장을 구분한다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c84e3089cd

#### CASE-0ca276ca1e
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Preserve the communication-loss observation and leave component attribution unresolved pending discriminating evidence.

관측 OBS-84df289fa5: A synthetic board loses its serial heartbeat.
관측 OBS-3b531c423c: Only whole-board current is logged; no peripheral voltage, current or local status was captured. The packet supplies no other evidence that identifies a failed component.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-6f28319467",
  "evidence_refs": [
    "REF-35c9b9dedc",
    "OBS-84df289fa5",
    "OBS-3b531c423c"
  ]
}
```
통신 상실 관측은 확보됐지만 특정 부품 원인은 아직 분리되지 않았다. 추가 관측을 요구하는 절차와 원인을 단정하는 주장을 구분한다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c84e3089cd

#### CASE-f235c491ee
**질문:** Is the packet sufficient for component-level fault localization during the communication outage? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-6a5bf1f7fa: The host timeout and board-current trace are supplied. Component-level status or electrical observations covering the outage are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-147828a5f8",
  "evidence_refs": [
    "REF-1ce637026d",
    "OBS-6a5bf1f7fa"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT",
  "requested_evidence": [
    "PERIPHERAL_EVENT_MONITORING"
  ]
}
```
통신 상실 관측은 확보됐지만 특정 부품 원인은 아직 분리되지 않았다. 추가 관측을 요구하는 절차와 원인을 단정하는 주장을 구분한다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c84e3089cd

#### CASE-703b0ad936
**질문:** Is the packet sufficient for component-level fault localization during the communication outage? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-22a29707cc: Time-aligned per-component voltage/current records and local status during the outage are supplied with channel mapping. The task only asks whether localization inputs exist.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-464bbf97e3",
  "evidence_refs": [
    "REF-a19f53f822",
    "OBS-22a29707cc"
  ]
}
```
통신 상실 관측은 확보됐지만 특정 부품 원인은 아직 분리되지 않았다. 추가 관측을 요구하는 절차와 원인을 단정하는 주장을 구분한다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c84e3089cd

### SR13-RHOBC-EFFECTS
원문 위치: 6 Conclusions / PDF 페이지 [11]
근거 요약: No destructive effects were reported under the tested proton exposure, but functional interruptions occurred in peripheral FRAM devices.

#### CASE-8822d424f6
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Summarize the run as showing no functional interruptions because it left no permanent damage.

관측 OBS-81638fb5c6: It also records two temporary peripheral functional interruptions, each requiring recovery. Both records refer to the same board and run.
관측 OBS-8c6555a219: A synthetic irradiation report records no permanent electrical damage after the run.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-1de212fcdd",
  "evidence_refs": [
    "REF-b95512151e",
    "OBS-8c6555a219",
    "OBS-81638fb5c6"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
영구 손상이 관측되지 않은 것과 일시 기능 중단이 없었던 것은 다른 진술이다. 회복된 사건도 실행 이력에 남긴다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-cdd6fc4b87

#### CASE-bbdb74ad02
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Report the absence of observed permanent damage and the two functional interruptions as separate outcomes.

관측 OBS-c4b6bd47d4: It also records two temporary peripheral functional interruptions, each requiring recovery. Both records refer to the same board and run.
관측 OBS-da0e54232e: A synthetic irradiation report records no permanent electrical damage after the run.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-e2d71359e0",
  "evidence_refs": [
    "REF-146cd2bfd2",
    "OBS-da0e54232e",
    "OBS-c4b6bd47d4"
  ]
}
```
영구 손상이 관측되지 않은 것과 일시 기능 중단이 없었던 것은 다른 진술이다. 회복된 사건도 실행 이력에 남긴다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-cdd6fc4b87

#### CASE-185d4a0c91
**질문:** Are the records ready to distinguish persistent damage from recoverable interruptions in this run? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-0418393ad8: A post-run electrical checkout is present; time-resolved functional status during irradiation and recovery records are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-cb26df0721",
  "evidence_refs": [
    "REF-4c3e0ed297",
    "OBS-0418393ad8"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT",
  "requested_evidence": [
    "FUNCTIONAL_RECOVERY_LOG"
  ]
}
```
영구 손상이 관측되지 않은 것과 일시 기능 중단이 없었던 것은 다른 진술이다. 회복된 사건도 실행 이력에 남긴다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-cdd6fc4b87

#### CASE-b94839f32b
**질문:** Are the records ready to distinguish persistent damage from recoverable interruptions in this run? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-933faf1346: During-run functional status, recovery records and a post-run electrical checkout are all supplied for the same board. The check concerns evidence availability for these two outcome categories.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-652d837079",
  "evidence_refs": [
    "REF-36b05e4326",
    "OBS-933faf1346"
  ]
}
```
영구 손상이 관측되지 않은 것과 일시 기능 중단이 없었던 것은 다른 진술이다. 회복된 사건도 실행 이력에 남긴다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-cdd6fc4b87

### SR13-RHOBC-BOOT
원문 위치: 6 Conclusions / PDF 페이지 [11]
근거 요약: A persistent Boot FRAM interruption could prevent code reload after MCU reset. Without FRAM power cycling, external board intervention was needed; piece-part tests could miss this fault combination.

#### CASE-13e084e68e
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Accept automatic boot recovery from the stated persistent-FRAM fault using repeated MCU reset alone.

관측 OBS-49753d6f03: The watchdog can reset the MCU but cannot cycle that FRAM. Boot code is read from it after every MCU reset.
관측 OBS-2a3296e983: For a synthetic board, the fault model states that a latched Boot FRAM interruption persists through MCU reset and clears only on FRAM power cycling.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-fa1c5e660c",
  "evidence_refs": [
    "REF-e1953bdba9",
    "OBS-2a3296e983",
    "OBS-49753d6f03"
  ],
  "reason": "METHOD_INTERPRETATION_ERROR"
}
```
주어진 고장 모델에서 reset은 FRAM 상태를 지우지 않는다. 필요한 입력이 모두 있다는 상태와 설계가 복구 목표를 만족한다는 상태를 분리한다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0b24c9f95e

#### CASE-5616686acf
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Flag the missing recovery path for the persistent FRAM fault and distinguish it from faults that an MCU reset can clear.

관측 OBS-eacf3dca7a: The watchdog can reset the MCU but cannot cycle that FRAM. Boot code is read from it after every MCU reset.
관측 OBS-351c0bdbff: For a synthetic board, the fault model states that a latched Boot FRAM interruption persists through MCU reset and clears only on FRAM power cycling.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-dd9bfe6d2a",
  "evidence_refs": [
    "REF-0e8ffd697f",
    "OBS-351c0bdbff",
    "OBS-eacf3dca7a"
  ]
}
```
주어진 고장 모델에서 reset은 FRAM 상태를 지우지 않는다. 필요한 입력이 모두 있다는 상태와 설계가 복구 목표를 만족한다는 상태를 분리한다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0b24c9f95e

#### CASE-9d61b185f8
**질문:** Are the design and fault records sufficient to assess recovery from the stated persistent-FRAM fault? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-af7f54d0a2: MCU reset behavior is documented, but FRAM fault-clear behavior and its power-control connectivity are missing. The packet provides no equivalent recovery evidence.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-5ce040ad0c",
  "evidence_refs": [
    "REF-56907ce188",
    "OBS-af7f54d0a2"
  ],
  "reason": "SUPPORTING_EVIDENCE_MISSING",
  "requested_evidence": [
    "BOOT_RECOVERY_FAULT_MODEL"
  ]
}
```
주어진 고장 모델에서 reset은 FRAM 상태를 지우지 않는다. 필요한 입력이 모두 있다는 상태와 설계가 복구 목표를 만족한다는 상태를 분리한다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0b24c9f95e

#### CASE-d029eccb5c
**질문:** Are the design and fault records sufficient to assess recovery from the stated persistent-FRAM fault? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-91fc25681e: Boot dependency, FRAM fault-clear behavior and power/reset connectivity are documented for this fault class. Assessment inputs are complete even if the design may fail the recovery goal.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-33aea2e815",
  "evidence_refs": [
    "REF-67328ee7a2",
    "OBS-91fc25681e"
  ]
}
```
주어진 고장 모델에서 reset은 FRAM 상태를 지우지 않는다. 필요한 입력이 모두 있다는 상태와 설계가 복구 목표를 만족한다는 상태를 분리한다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0b24c9f95e

## SR13-HYPSO | Experimental set-up of a thermal vacuum chamber for thermal model in-house correlation and characterization of the HYPSO hyperspectral imager
출처: https://link.springer.com/article/10.1007/s12567-023-00501-3
자료 범위: HTML sections 1 and 2, including chamber and temperature measurement description

### SR13-HYPSO-RANGE
원문 위치: 2 Experimental set-up, opening paragraph / PDF 페이지 HTML 절 기준
근거 요약: The described chamber control heated the imager from room temperature upward. The reported apparatus had a restricted thermal control range.

#### CASE-ec0f24fd6c
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Mark the -15 C optical response as experimentally demonstrated by the heating-only campaign.

관측 OBS-5ad19b8542: A synthetic optical payload has measurements only from 22 C to 48 C. The chamber used for those runs has heating control but no demonstrated sub-ambient run. The claim under review is experimentally demonstrated response at -15 C.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-03d61f56b6",
  "evidence_refs": [
    "REF-7443d87285",
    "OBS-5ad19b8542"
  ],
  "reason": "MODEL_SCOPE_EXCEEDED"
}
```
입력 조건 범위와 결론 범위를 맞춘다. 측정되지 않은 저온 조건을 따뜻한 구간의 실증 결과로 표시할 수 없다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0f0474efec

#### CASE-d48966c293
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Keep -15 C response outside the demonstrated range and label any extrapolation separately from the measured warm-range results.

관측 OBS-5e4d764bd3: A synthetic optical payload has measurements only from 22 C to 48 C. The chamber used for those runs has heating control but no demonstrated sub-ambient run. The claim under review is experimentally demonstrated response at -15 C.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-aba36cdafa",
  "evidence_refs": [
    "REF-74972362d4",
    "OBS-5e4d764bd3"
  ]
}
```
입력 조건 범위와 결론 범위를 맞춘다. 측정되지 않은 저온 조건을 따뜻한 구간의 실증 결과로 표시할 수 없다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0f0474efec

#### CASE-f49f3d339e
**질문:** Are data available for the requested assessment at -15 C? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-8b847ae6ae: The warm-range records are present, but neither a -15 C measurement nor an authorized validated extrapolation is supplied.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-a7fe2f7f10",
  "evidence_refs": [
    "REF-c665a0b48f",
    "OBS-8b847ae6ae"
  ],
  "reason": "SUPPORTING_EVIDENCE_MISSING",
  "requested_evidence": [
    "LOW_TEMPERATURE_RESPONSE"
  ]
}
```
입력 조건 범위와 결론 범위를 맞춘다. 측정되지 않은 저온 조건을 따뜻한 구간의 실증 결과로 표시할 수 없다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0f0474efec

#### CASE-8261f9621f
**질문:** Are data available for the requested assessment at -15 C? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-10eaf600a5: A separate configuration-matched run at -15 C supplies optical response, local temperatures and calibration. This is evidence readiness for that condition, not automatic acceptance.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-13500f3f1d",
  "evidence_refs": [
    "REF-9ed1803ca5",
    "OBS-10eaf600a5"
  ]
}
```
입력 조건 범위와 결론 범위를 맞춘다. 측정되지 않은 저온 조건을 따뜻한 구간의 실증 결과로 표시할 수 없다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-0f0474efec

### SR13-HYPSO-IR
원문 위치: 2 Experimental set-up, temperature measurement description / PDF 페이지 HTML 절 기준
근거 요약: Infrared measurements through the chamber window required attention to window transmission, reflections and surface properties; contact temperature measurements supported interpretation.

#### CASE-18d7b891b1
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Reject investigation of the optical measurement path because an infrared camera reading is automatically the true surface temperature.

관측 OBS-583e28d330: A synthetic imager is viewed by an infrared camera through a window. The processing assumes transmission one and ignores reflected radiation; no calibration establishes that those assumptions hold. Contact sensors show a different surface temperature, but the cause is unresolved.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-6e78fe53a3",
  "evidence_refs": [
    "REF-a33a228d37",
    "OBS-583e28d330"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH"
}
```
관측 경로의 가정을 검증한 뒤 온도 차이를 해석한다. 두 센서 차이만으로 모델 오차나 센서 고장을 유일 원인으로 확정하지 않는다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-57ad3ec434

#### CASE-5bf8af5346
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Keep the measurement discrepancy and assess window transmission, reflections and surface settings before attributing it to the thermal model.

관측 OBS-d9c218291e: A synthetic imager is viewed by an infrared camera through a window. The processing assumes transmission one and ignores reflected radiation; no calibration establishes that those assumptions hold. Contact sensors show a different surface temperature, but the cause is unresolved.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-fa475769a1",
  "evidence_refs": [
    "REF-3f39265aaf",
    "OBS-d9c218291e"
  ]
}
```
관측 경로의 가정을 검증한 뒤 온도 차이를 해석한다. 두 센서 차이만으로 모델 오차나 센서 고장을 유일 원인으로 확정하지 않는다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-57ad3ec434

#### CASE-b40f92306b
**질문:** Are measurement-path records sufficient for a calibrated comparison of IR-derived and contact temperatures? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-021192a3c5: IR frames and contact temperatures are present. The window transmission calibration, surface emissivity setting and reflection treatment are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-1997ad4989",
  "evidence_refs": [
    "REF-f8b978aa75",
    "OBS-021192a3c5"
  ],
  "reason": "MEASUREMENT_MAPPING_MISMATCH",
  "requested_evidence": [
    "IR_PATH_CALIBRATION"
  ]
}
```
관측 경로의 가정을 검증한 뒤 온도 차이를 해석한다. 두 센서 차이만으로 모델 오차나 센서 고장을 유일 원인으로 확정하지 않는다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-57ad3ec434

#### CASE-a18319c1d2
**질문:** Are measurement-path records sufficient for a calibrated comparison of IR-derived and contact temperatures? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-47f58243dd: The window calibration, emissivity setting, reflection treatment and co-located contact comparison are supplied. The task is readiness of the measurement comparison.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-0e5bd6c964",
  "evidence_refs": [
    "REF-c3cee0e200",
    "OBS-47f58243dd"
  ]
}
```
관측 경로의 가정을 검증한 뒤 온도 차이를 해석한다. 두 센서 차이만으로 모델 오차나 센서 고장을 유일 원인으로 확정하지 않는다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-57ad3ec434

## SR13-CANYVAL | Novel Structure and Thermal Design and Analysis for CubeSats in Formation Flying
출처: https://www.mdpi.com/2226-4310/8/6/150
자료 범위: Publisher body text, section 6 Conclusions and reported vibration/correlation discussion

### SR13-CANYVAL-PRELOAD
원문 위치: 6 Conclusions / PDF 페이지 HTML 절 기준
근거 요약: The deployable-panel frequency depended on nylon-wire tightening and workmanship; the analysis represented changes in the restraint condition.

#### CASE-870c379fa0
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Treat that comparison as an identical-boundary-condition validation merely because the panel serial number is the same.

관측 OBS-ff0f7db6e0: Two synthetic tests use the same panel but different restraint preloads. The first resonance differs. A model using the first preload is compared against the second test without representing or bounding the changed restraint.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-ff14a3a7a4",
  "evidence_refs": [
    "REF-540c116e14",
    "OBS-ff0f7db6e0"
  ],
  "reason": "BOUNDARY_CONDITION_UNRESOLVED"
}
```
같은 패널 식별자가 같은 구속 상태를 뜻하지는 않는다. 경계조건 기록을 맞춘 뒤 모달 차이를 해석한다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e14546bbe1

#### CASE-e7386f7ddf
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Record the restraint change and represent or bound it before interpreting the comparison as a same-condition validation.

관측 OBS-6f9777586f: Two synthetic tests use the same panel but different restraint preloads. The first resonance differs. A model using the first preload is compared against the second test without representing or bounding the changed restraint.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-6831a26328",
  "evidence_refs": [
    "REF-107efdd1b6",
    "OBS-6f9777586f"
  ]
}
```
같은 패널 식별자가 같은 구속 상태를 뜻하지는 않는다. 경계조건 기록을 맞춘 뒤 모달 차이를 해석한다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e14546bbe1

#### CASE-df8ed0a5e6
**질문:** Are the restraint-condition records ready for comparing the model and modal test? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-94fab28a53: The panel identity and frequencies are supplied, but the as-tested restraint/preload record is missing.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-6b51048b82",
  "evidence_refs": [
    "REF-316d1824f8",
    "OBS-94fab28a53"
  ],
  "reason": "BOUNDARY_CONDITION_UNRESOLVED",
  "requested_evidence": [
    "RESTRAINT_PRELOAD_RECORD"
  ]
}
```
같은 패널 식별자가 같은 구속 상태를 뜻하지는 않는다. 경계조건 기록을 맞춘 뒤 모달 차이를 해석한다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e14546bbe1

#### CASE-4e774a1974
**질문:** Are the restraint-condition records ready for comparing the model and modal test? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-82d3f6e9b4: The tested restraint/preload record and the model boundary representation are supplied for comparison. Their eventual agreement is a later check.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-0801bb65b2",
  "evidence_refs": [
    "REF-dda07125fc",
    "OBS-82d3f6e9b4"
  ]
}
```
같은 패널 식별자가 같은 구속 상태를 뜻하지는 않는다. 경계조건 기록을 맞춘 뒤 모달 차이를 해석한다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e14546bbe1

### SR13-CANYVAL-DAMAGE
원문 위치: 6 Conclusions / PDF 페이지 HTML 절 기준
근거 요약: Panel frequency changed during the vibration campaign while the authors reported no structural or functional damage. A frequency change alone was not a unique diagnosis of damage.

#### CASE-1800223793
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Conclude that structural cracking is the unique cause of the frequency shift and close the alternative-cause review.

관측 OBS-89b23fc1fb: A synthetic panel frequency changes after vibration. A restraint-tension change is also recorded. Visual and functional checks find no abnormality, but no discriminating investigation has yet established the cause of the frequency shift.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-dfebe4fe03",
  "evidence_refs": [
    "REF-80ae6e8dd6",
    "OBS-89b23fc1fb"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
변화 관측과 특정 원인의 확정을 구분한다. 외관 정상만으로 모든 손상을 배제하지 않고, 주파수 변화만으로 균열을 단정하지 않는다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e6c49196e6

#### CASE-0bf2f59697
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Retain the shift as an observation and investigate restraint condition and damage hypotheses without treating either as established by frequency alone.

관측 OBS-7bae0441ad: A synthetic panel frequency changes after vibration. A restraint-tension change is also recorded. Visual and functional checks find no abnormality, but no discriminating investigation has yet established the cause of the frequency shift.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-9be37a6324",
  "evidence_refs": [
    "REF-1a3096629d",
    "OBS-7bae0441ad"
  ]
}
```
변화 관측과 특정 원인의 확정을 구분한다. 외관 정상만으로 모든 손상을 배제하지 않고, 주파수 변화만으로 균열을 단정하지 않는다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e6c49196e6

#### CASE-a00c710b3f
**질문:** Is the evidence sufficient to distinguish restraint change from structural damage as the cause? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-ffcf465b8e: Before/after frequency measurements are supplied. Restraint inspection and a damage-discriminating examination are not available.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-608f1a99fc",
  "evidence_refs": [
    "REF-53c5ce19a8",
    "OBS-ffcf465b8e"
  ],
  "reason": "SUPPORTING_EVIDENCE_MISSING",
  "requested_evidence": [
    "MODAL_CHANGE_INVESTIGATION"
  ]
}
```
변화 관측과 특정 원인의 확정을 구분한다. 외관 정상만으로 모든 손상을 배제하지 않고, 주파수 변화만으로 균열을 단정하지 않는다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e6c49196e6

#### CASE-1fb4ec74a4
**질문:** Is the evidence sufficient to distinguish restraint change from structural damage as the cause? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-5769f2f5b3: Restraint inspection, a documented damage-discriminating examination and before/after modal data are supplied. This establishes inputs for investigation, not a predetermined cause.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-80a0711446",
  "evidence_refs": [
    "REF-36db2ca7a3",
    "OBS-5769f2f5b3"
  ]
}
```
변화 관측과 특정 원인의 확정을 구분한다. 외관 정상만으로 모든 손상을 배제하지 않고, 주파수 변화만으로 균열을 단정하지 않는다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e6c49196e6

## SR13-PROBAV | Investigation of Single-Event Effects for Space Applications: Instrumentation for In-Depth System Monitoring
출처: https://www.mdpi.com/2079-9292/13/10/1822
자료 범위: Publisher-indexed full section text: 3.1, 4.1 and 5

### SR13-PROBAV-SYNC
원문 위치: 3.1 Test Setup and Instrumentation; 5 Discussion / PDF 페이지 HTML 절 기준
근거 요약: Synchronized memory-error and current records enabled event association. Independent totals without coherent timestamps lack that temporal linkage.

#### CASE-fc0864226a
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Assign every memory burst to one overcurrent event based solely on the equal totals.

관측 OBS-5a267a07db: A synthetic irradiation run reports six overcurrent events and six memory-error bursts. The two logs use unaligned clocks; only aggregate totals are available. No mapping between individual events is supplied.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-9ad4a3ab89",
  "evidence_refs": [
    "REF-1cf368c1c8",
    "OBS-5a267a07db"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
같은 개수는 같은 시각이나 같은 원인을 뜻하지 않는다. 시간 연결을 확인할 수 있는 자료가 준비됐는지 따로 평가한다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c7a41a91dd

#### CASE-d05caa3edc
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Report the totals separately and defer one-to-one temporal attribution until aligned event records are available.

관측 OBS-1509c71e68: A synthetic irradiation run reports six overcurrent events and six memory-error bursts. The two logs use unaligned clocks; only aggregate totals are available. No mapping between individual events is supplied.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-968667b0bb",
  "evidence_refs": [
    "REF-bcfba15d16",
    "OBS-1509c71e68"
  ]
}
```
같은 개수는 같은 시각이나 같은 원인을 뜻하지 않는다. 시간 연결을 확인할 수 있는 자료가 준비됐는지 따로 평가한다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c7a41a91dd

#### CASE-71262c17f4
**질문:** Are the inputs ready for a time-coincident association of current events and memory errors? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-93a024c280: Current-event and error counts are supplied, but their timestamp alignment and per-event records are absent.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-28f18be09e",
  "evidence_refs": [
    "REF-b0777733b6",
    "OBS-93a024c280"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT",
  "requested_evidence": [
    "SYNCHRONIZED_EVENT_LOGS"
  ]
}
```
같은 개수는 같은 시각이나 같은 원인을 뜻하지 않는다. 시간 연결을 확인할 수 있는 자료가 준비됐는지 따로 평가한다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c7a41a91dd

#### CASE-15d397cc74
**질문:** Are the inputs ready for a time-coincident association of current events and memory errors? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-8bc7e564ff: Both per-event logs, a common time reference and timing uncertainty are documented. This is sufficient to start the association check, not proof of its result.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-f308ed1853",
  "evidence_refs": [
    "REF-ad5de44fe0",
    "OBS-8bc7e564ff"
  ]
}
```
같은 개수는 같은 시각이나 같은 원인을 뜻하지 않는다. 시간 연결을 확인할 수 있는 자료가 준비됐는지 따로 평가한다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-c7a41a91dd

### SR13-PROBAV-CENSOR
원문 위치: 4.1 SEE Cross Sections / PDF 페이지 HTML 절 기준
근거 요약: Frequent latch-up recovery restarts at high LET reduced the ability to retrieve all induced bit errors, artificially reducing the reported SEU cross section.

#### CASE-c45ab2fec7
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Conclude that the device is intrinsically more resistant in the high-intensity run using the lower recorded error count alone.

관측 OBS-818368dbbb: A synthetic high-intensity run has fewer logged bit errors per exposure than a lower-intensity run. Its controller frequently power-cycles the memory; logs confirm that bit-error acquisition is unavailable during these recovery intervals. No correction for missed events is supplied.

기대 출력:
```json
{
  "action": "CHALLENGE",
  "claim_id": "CLM-f8223996fd",
  "evidence_refs": [
    "REF-c02722a2a4",
    "OBS-818368dbbb"
  ],
  "reason": "EVIDENCE_INTERPRETATION_ERROR"
}
```
기록된 사건의 감소와 실제 감수성 감소를 구분한다. 회복 중 누락되는 관측을 확인하지 않고 물리적 개선으로 결론 내리지 않는다. 관측이 제안의 핵심 주장을 반박하므로 CHALLENGE한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e5cd6d3740

#### CASE-2346b4ee7f
**질문:** Assess the proposed disposition against the supplied observations and reference scope. Decide whether to object to the proposal itself.
**검토 대상:** Retain the recorded counts but flag recovery-related observation loss before interpreting a change in intrinsic susceptibility.

관측 OBS-0e7d2943da: A synthetic high-intensity run has fewer logged bit errors per exposure than a lower-intensity run. Its controller frequently power-cycles the memory; logs confirm that bit-error acquisition is unavailable during these recovery intervals. No correction for missed events is supplied.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-17bf56edab",
  "evidence_refs": [
    "REF-b710982ab6",
    "OBS-0e7d2943da"
  ]
}
```
기록된 사건의 감소와 실제 감수성 감소를 구분한다. 회복 중 누락되는 관측을 확인하지 않고 물리적 개선으로 결론 내리지 않는다. 제안 자체의 제한과 후속 검토 방향이 적절하므로 이 검토점에서는 NO_ACTION_REQUIRED다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e5cd6d3740

#### CASE-82a92a1c28
**질문:** Are the records sufficient to assess observation loss caused by recovery cycles? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-e20223cfdf: The total exposure and logged errors are supplied. Recovery timing, acquisition availability and readout coverage are missing.

기대 출력:
```json
{
  "action": "REQUEST_EVIDENCE",
  "claim_id": "CLM-a6e5986bd3",
  "evidence_refs": [
    "REF-9d0b8802b4",
    "OBS-e20223cfdf"
  ],
  "reason": "MONITORING_COVERAGE_INSUFFICIENT",
  "requested_evidence": [
    "ACQUISITION_RECOVERY_TIMELINE"
  ]
}
```
기록된 사건의 감소와 실제 감수성 감소를 구분한다. 회복 중 누락되는 관측을 확인하지 않고 물리적 개선으로 결론 내리지 않는다. 검토에 명시적으로 필요한 입력이 빠졌으므로 허용 목록의 해당 자료를 요청한다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e5cd6d3740

#### CASE-e8a8b979ca
**질문:** Are the records sufficient to assess observation loss caused by recovery cycles? Judge availability of the requested assessment inputs, not final compliance or approval.
**검토 대상:** Complete the stated input-readiness review and record the next review action.

관측 OBS-aacd6fee23: Recovery timing, acquisition availability and readout coverage are supplied with exposure and event logs. Their presence supports a loss assessment without assuming its correction result.

기대 출력:
```json
{
  "action": "NO_ACTION_REQUIRED",
  "claim_id": "CLM-0fe5c964db",
  "evidence_refs": [
    "REF-7b411c8857",
    "OBS-aacd6fee23"
  ]
}
```
기록된 사건의 감소와 실제 감수성 감소를 구분한다. 회복 중 누락되는 관측을 확인하지 않고 물리적 개선으로 결론 내리지 않는다. 필요한 입력이 공급됐으므로 입력 준비 검토에는 추가 조치가 없다.
정답 작성 근거: 원문 원리 + 명시한 합성 관측 + v13 검토 정책. 가족 ID: F-e5cd6d3740

