이 문서는 완료된 direct_v14 DEV8 실험의 **사후 AI 정책 검토**다. 두 버전의 모델 출력과 후보 정답을 이미 본 상태에서 작성했으며, 독립 사람 검토·블라인드 검토·정답 승인에 해당하지 않는다. 기대정답은 SOURCE_GROUNDED_AI_CANDIDATE, human_review_performed=false, training_eligible=false를 유지한다. 원문 출력, gold, scorer, prompt, 기존 점수와 완료 상태는 변경하지 않았다. 새 모델 점수를 만들거나 v13 reason을 소급 정답 채점하지 않았다.

핵심 판단은 다음과 같다. 두 버전의 실질 선택 필드값은 동일하다. reason 두 건은 구체적 코드와 일반적 해석 오류의 정의가 겹치고 우선순위가 명시되지 않아 경계 검토가 필요하다. b40f92306b의 일반 결손 코드는 명시된 fallback 제한과 충돌한다고 판단하되, 요청한 IR_PATH_CALIBRATION 자체의 일치는 별도로 보존한다. reference 두 건은 관측만으로 좁은 입력 준비 판단이 가능하며, 논문 인용을 항상 필수로 만드는 정책은 확인한 지침에서 명확하지 않아 필수 인용 정책 검토가 필요하다. 이 판단으로 허용 reason을 늘리거나 필수 reference를 줄이지 않는다.

검토 근거와 범위

- A1: [실제 v13 DEV8 메시지](../../../results/source_review_v13_qwen27/inputs/dev8_hypso_public_v13_source_available_v1.jsonl) 및 [실제 v14 DEV8 메시지](../inputs/dev8_direct_v14.jsonl). 두 system 지침과 해당 user packet을 읽었다.
- A2: [reason 정의](../../../research/DoriLab_SourceReview_v13/schemas/reason_definitions_v13.json), [주석 정책](../../../research/DoriLab_SourceReview_v13/ANNOTATION_POLICY.md), [출력 JSON Schema](../../../research/DoriLab_SourceReview_v13/schemas/action_v13.json), [기존 scorer 소스](../../../research/DoriLab_SourceReview_v13/packtool.py). scorer는 읽기만 했고 호출하지 않았다.
- A3: [DEV 후보](../../../research/DoriLab_SourceReview_v13/data/dev/gold_candidate.jsonl), [TRAIN 후보](../../../research/DoriLab_SourceReview_v13/data/train/gold_candidate.jsonl), 각 split의 inputs/metadata. 후보의 expected·acceptable_reason_codes·reference_requirement·review_note를 구분해 읽었다.
- A4: [HYPSO 확보 원문 PDF](../../../results/source_review_v13_qwen27/cpu_source_audit/verified_sources/SR13-HYPSO.pdf), [해당 본문 추출 p3](../../../results/source_review_v13_qwen27/cpu_source_audit/pdf_review/SR13-HYPSO.page03.txt). §2 Experimental set-up, PDF 3쪽/인쇄395쪽. [기존 locator 감사](../../../results/source_review_v13_qwen27/SOURCE_SPAN_REVIEW_v2.json)의 RANGE·IR span을 대조했다.
- A5: [TIRS 확보 원문 PDF](../../../results/source_review_v13_qwen27/cpu_source_audit/verified_sources/SR13-TIRS.pdf), [본문 추출 p4](../../../results/source_review_v13_qwen27/cpu_source_audit/pdf_review/SR13-TIRS.page04.txt). §IV, PDF/인쇄4쪽. [검토 카드](../../../research/DoriLab_SourceReview_v13/REVIEW_CARDS_KO.md), [기존 보고서](../../../results/source_review_v13_qwen27/FINAL_REPORT_KO.md), [기존 대기 상태](../../../results/source_review_v13_qwen27/LABEL_REVIEW_STATUS.json)를 함께 읽었다.
- A6: [v13 원문 출력](../../../results/source_review_v13_qwen27/baseline_direct/predictions.jsonl), [v14 원문 출력](../runs/direct_v14_checked_01/predictions.jsonl), [봉인된 완료 상태](../runs/direct_v14_checked_01_control/COMPLETION.json).

HYPSO 원문은 실온에서 위쪽으로 가열하는 제한된 장치 범위와, 창·반사로 생기는 IR 온도 불확실성 및 접촉 센서 대조를 설명한다. 이것은 출처의 제한된 원리다. -15°C, 22~48°C의 합성 측정, IR 경로 기록의 결손, 내부 Action/reason 코드와 필수 인용 집합은 논문의 실제 실험 결과가 아니라 패키지의 합성 사례·업무 정책이다. 특히 emissivity 설정/보정 자료의 구체적 결손은 해당 user packet과 request_catalog에 명시된 합성 전제이며 §2 문장만으로 그 결손 사실을 입증했다고 하지 않는다.

원문 PDF 두 개와 기존 locator의 해당 page text hash가 과거 SOURCE_AUDIT/SOURCE_SPAN_REVIEW_v2와 일치함을 확인했다. 이번에는 확보된 본문 추출과 locator를 읽었으며, 표/그림의 새 화면 감사나 모든 수치의 재검증을 했다고 주장하지 않는다. 원래 packet의 pdf_pages_1based=[]도 채워 넣지 않았다. 원문·정책·검토 입력 hash는 SOURCE_AND_INPUT_HASHES.json에 기록했다.

선택 필드의 동일성 검사

`compare_selected_fields.py`는 보존된 두 predictions 파일만 읽고 JSON을 파싱한다. gold와 scorer는 이 검사 코드의 입력이 아니다. action·claim_id는 문자열 그대로, evidence_refs는 순서만 제외한 집합, v13 reason_code와 v14 reason은 문자열 그대로, REQUEST_EVIDENCE의 requested_evidence는 실제 배열값으로 대조했다. 없는 필드를 빈 배열로 보정하지 않았다. 중복 여부를 숨기기 위해 raw 배열을 대체하지도 않았으며, JSON 기록에는 양쪽 원래 배열과 필드 존재 여부가 남아 있다.

| 사례 | action | claim_id | evidence_refs 집합 | v13 reason_code / v14 reason 문자열 | REQUEST_EVIDENCE 요청 |
|---|---|---|---|---|---|
| CASE-8261f9621f | 동일 | 동일 | 동일 | 양쪽 없음 | 비적용 |
| CASE-ec0f24fd6c | 동일 | 동일 | 동일 | `EVIDENCE_INTERPRETATION_ERROR` = `EVIDENCE_INTERPRETATION_ERROR` | 비적용 |
| CASE-f49f3d339e | 동일 | 동일 | 동일 | `SUPPORTING_EVIDENCE_MISSING` = `SUPPORTING_EVIDENCE_MISSING` | `LOW_TEMPERATURE_RESPONSE` 동일 |
| CASE-18d7b891b1 | 동일 | 동일 | 동일 | `EVIDENCE_INTERPRETATION_ERROR` = `EVIDENCE_INTERPRETATION_ERROR` | 비적용 |
| CASE-5bf8af5346 | 동일 | 동일 | 동일 | 양쪽 없음 | 비적용 |
| CASE-d48966c293 | 동일 | 동일 | 동일 | 양쪽 없음 | 비적용 |
| CASE-b40f92306b | 동일 | 동일 | 동일 | `SUPPORTING_EVIDENCE_MISSING` = `SUPPORTING_EVIDENCE_MISSING` | `IR_PATH_CALIBRATION` 동일 |
| CASE-a18319c1d2 | 동일 | 동일 | 동일 | 양쪽 없음 | 비적용 |

8건의 action·claim_id·reference 집합이 모두 동일하고, reason을 출력한 4건의 문자열도 동일하며, 요청 Action 2건의 요청 배열도 동일하다. 이 수는 **출력값 동일성 검사 건수**이며 성능 점수·정답 일치 수가 아니다. reason의 key 이름이 바뀐 것은 네 건이고, 두 CHALLENGE(ec0f24fd6c, 18d7b891b1)에서 v13의 불필요한 requested_evidence=[]가 v14에서는 생략됐다. 이 사실을 원문 수정으로 만들지 않고 별도 관찰로만 기록한다. 상세는 OUTPUT_SELECTION_IDENTITY.json에 있다.

reason 사례 R1 — CASE-ec0f24fd6c (DEV, F-0f0474efec, variant0)

질문은 제안 자체의 적절성이다. 제안은 가열만 수행한 campaign으로 -15°C 광학 응답이 실험적으로 입증됐다고 표시하자는 것이다. OBS-5ad19b8542는 측정이 22~48°C에만 있고 sub-ambient run은 입증되지 않았다고 명시한다. REF-7443d87285(SR13-HYPSO-RANGE)는 장치의 가열 범위 제한을 뒷받침한다. 두 출력 모두 CHALLENGE이며 이 관측과 source를 인용했다. [A1, A3, A4, A6]

- 후보 MODEL_SCOPE_EXCEEDED를 선택한 이유: 정의가 model뿐 아니라 experimental coverage 밖으로 적용성·입증 범위를 확대하는 결론을 포함한다. 측정 범위 밖 -15°C를 실험 입증이라고 부르는 이 제안은 그 구체적인 사례다. 후보 rationale도 측정 조건과 결론 범위를 맞추라고 설명한다.
- 실제 EVIDENCE_INTERPRETATION_ERROR와 겹치는 부분: 정의상 제공 관측·출처가 뒷받침하는 내용을 잘못 진술한 추론이다. 가열 구간만 측정했는데 -15°C를 실증했다는 진술은 이 넓은 정의에도 해당한다. 일반 해석 오류라는 분류만으로 제안을 수용했거나 외삽을 검증했다고 해석할 수 없다.
- 우선순위: reason 정의와 두 실제 system 지침에는 MODEL_SCOPE_EXCEEDED가 EVIDENCE_INTERPRETATION_ERROR보다 항상 우선한다는 조항이 없다. 주석 정책의 “Action 우선순위”는 reason 간 우선순위가 아니다. canonical 한 개라는 후보 작성 방침도 두 정의의 중첩을 해소하는 tie-break 규칙은 아니다. SUPPORTING_EVIDENCE_MISSING의 fallback 조항을 이 두 코드의 전체 계층 규칙으로 확대 적용하지 않는다.
- 후속 조치: 저장된 출력의 Action은 모두 CHALLENGE, reference 집합도 같다. CHALLENGE는 이번 계약상 요청 배열을 생략하므로 실제 추가 요청 항목의 차이는 없다. 두 코드 모두 이 잘못된 입증 표시를 이의 제기한다는 검토점에서는 같은 방향이다. reason별 외부 라우팅·승인 절차는 자료에 없으므로 실제 시스템에서 완전히 같은 후속 처리가 된다고 단정하지 않는다.
- 판단: 후보가 더 구체적이고 설명력이 높지만, 실제 코드가 넓은 정의를 명백히 위반했다고 볼 근거는 부족하다. **기존 정의의 경계가 불명확함**. 후보 정답 불일치와 정의상 명확한 위반을 구분한다.

reason 사례 R2 — CASE-18d7b891b1 (DEV, F-57ad3ec434, variant0)

제안은 IR camera 수치가 자동으로 진짜 표면 온도이므로 광학 측정 경로 조사를 거부하자는 것이다. OBS-583e28d330에는 창 투과율1 가정, 반사 무시, 그 가정의 보정 근거 부재, 접촉 센서와 차이가 있지만 원인 미해결이라는 사실이 있다. REF-a33a228d37(SR13-HYPSO-IR)와 원문은 창/반사에 의한 측정 불확실성과 접촉 측정 대조를 뒷받침한다. 두 출력 모두 CHALLENGE다. [A1, A3, A4, A6]

- 후보 MEASUREMENT_MAPPING_MISMATCH를 선택한 이유: 창을 통해 얻은 신호/IR-derived 온도에서 판단 대상 표면 온도로 가는 대응을 확인하지 않고 동일시한다. 정의는 측정·모델 quantity/location 불일치뿐 아니라 필요한 mapping 부재도 포함한다. 후보 rationale은 측정 경로의 가정을 검증한 뒤 차이를 해석하도록 요구한다.
- 실제 EVIDENCE_INTERPRETATION_ERROR와 겹치는 부분: “IR 수치는 자동으로 진실”이라는 추론은 현재 관측과 source의 지지 범위를 잘못 해석한다는 넓은 정의에도 맞는다. METHOD_INTERPRETATION_ERROR의 가정/절차 불일치 문구와도 일부 접점이 있으나, 그것을 이번에 허용 reason으로 추가하지 않는다. 이 사례의 실제 검토 대상은 잘못된 단정과 조사 거부이지, 어느 센서가 고장인지 확정하는 일이 아니다.
- 우선순위: MEASUREMENT_MAPPING_MISMATCH를 EVIDENCE_INTERPRETATION_ERROR보다 우선한다는 명시적 tie-break는 없다. 정의의 상세성에서 우선순위를 자동 도출하지 않는다. 방사량→표면 온도의 대응을 mapping으로 부를지, 범용 해석 오류와 어떤 경계로 나눌지 명시하는 보완이 필요하다.
- 후속 조치: 저장된 Action과 reference 집합은 같다. 두 코드 모두 자동 동일시를 근거로 조사를 거부하는 제안에 이의를 제기한다. 실제 출력에 특정 센서 고장 확정이나 새 요청은 없고, 코드만으로 추가 동작이 실행되지 않는다. downstream reason router는 제공되지 않았다.
- 판단: 후보의 기계적 원인 설명은 타당하지만 실제 넓은 분류도 문구상 포섭된다. **기존 정의의 경계가 불명확함**. 이유 문자열을 바꿔 기존 점수를 올리지 않는다.

reason 사례 R3 — CASE-b40f92306b (DEV, F-57ad3ec434, variant2)

질문은 IR-derived 온도와 접촉 온도를 보정해 비교할 만큼 측정 경로 자료가 있는지다. OBS-021192a3c5에는 IR frame과 접촉 온도는 있지만 창 투과 보정, 표면 emissivity 설정, 반사 처리가 없다고 명시돼 있다. REF-f8b978aa75(SR13-HYPSO-IR)는 경로 불확실성을 고려해야 하는 원리다. 후보는 MEASUREMENT_MAPPING_MISMATCH, 실제는 SUPPORTING_EVIDENCE_MISSING이다. [A1, A3, A4, A6]

- 후보 선택 이유: 단순히 아무 문서가 없는 것이 아니라, IR 측정값을 목표 표면 온도와 보정 비교하는 데 필요한 변환/대응 자료가 특정돼 있다. 정의의 “required mapping is missing”에 해당한다고 보는 것이 후보의 구체적인 근거다. 이는 센서 고장이나 이미 존재하는 온도값의 오류를 확정하는 분류가 아니다.
- 겹치는 부분과 제한: 필요한 지원 자료가 없다는 앞부분만 보면 SUPPORTING_EVIDENCE_MISSING과 겹친다. 그러나 실제 정의에는 “and a more specific code is not applicable”이라는 조건이 붙어 있다. 이 제한은 실제 모델 system에도 포함돼 있다. 따라서 일반 코드를 무조건 구체 코드의 동의어로 취급할 수 없다.
- 우선순위: 이 쌍에는 위 fallback 조건이 명시돼 있다. 현재 입력은 보정된 측정량 대응의 결손을 특정하고, 구체적인 mapping 코드는 결손까지 정의에 포함한다. 이 검토에서는 구체 코드가 적용 가능한데 일반 fallback을 선택한 것으로 판단한다. mapping을 좌표 대응에만 한정한다는 정의는 없으며, 추후 사람이 그 범위를 좁히기로 결정한다면 그것은 새 정의/label revision의 문제다.
- 요청과 reason은 별개: 실제 requested_evidence는 **["IR_PATH_CALIBRATION"]**이고 후보도 정확히 같은 배열이다. request_catalog의 해당 ID는 창 투과율·emissivity·반사 처리를 포함한다. Action=REQUEST_EVIDENCE, claim_id, reference 집합 및 요청 항목은 후보의 선택과 일치한다는 사실을 확인했다. 이것은 선택 내용 대조이며 새로운 정답 점수를 산출한 것이 아니다. reason의 일반성이 낮다고 해서 “IR 보정을 요청하지 않았다”, “잘못된 자료를 요청했다”고 기록하면 안 된다.
- 후속 조치: 명시적으로 요청할 자료는 바뀌지 않는다. 더 구체적 원인 표기와 사후 집계는 달라질 수 있지만, 제공되지 않은 실제 운영 시스템의 라우팅 차이는 판정하지 못한다.
- 판단: 위 mapping 적용 해석과 현재 fallback 문구를 기준으로 **기존 계약상 명확한 모델 오류**로 분류한다. 범위는 reason의 구체성 조건 위반이다. 올바른 요청 자체를 오류로 바꾸지 않으며, 이것도 독립 사람 승인 전의 AI 정책 판단이다. 검토자는 최종 승인 전 radiometric conversion이 현재 mapping 정의에 포함되는지 확인해야 한다.

reference 사례 E1 — CASE-8261f9621f (DEV, F-0f0474efec, variant3)

질문은 -15°C 평가 입력의 준비 여부이며 최종 적합성/승인을 묻지 않는다. OBS-10eaf600a5 자체가 별도의 configuration-matched -15°C run에서 optical response, local temperatures, calibration을 제공한다고 명시한다. 모델이 인용한 집합은 {OBS-10eaf600a5}; 후보 필수 집합은 {REF-9ed1803ca5, OBS-10eaf600a5}이다. 원문을 읽어 현재 합성 run이 존재한다고 입증할 수는 없으며, 그 존재의 입력 내 근거는 관측 기록이다. [A1, A3, A4]

- 판단 충분성: 공개 packet을 전제로 한 좁은 readiness 판단은 이 관측만으로 가능하다. 이 문장은 입력의 공급을 명시하므로 NO_ACTION_REQUIRED는 engineering acceptance가 아니다. 실제 시험 기록의 진위/교정 품질을 물리적으로 검증했다는 뜻도 아니다.
- 논문 reference의 역할: REF-9ed1803ca5는 기존 장치의 가열 범위를 설명하는 배경/출처 원리다. 별도 -15°C run의 준비 사실을 입증하는 필수 전제는 아니다. 원문이 가열만 했다고 해서 합성 별도 run의 명시적 준비 사실이 취소되지 않는다.
- 감사 추적 가능성: 사례를 만든 원리의 provenance를 모든 답에 연결하려는 정책이라면 source 인용을 필수로 정할 수 있다. 그러나 그런 역할을 공통 출력 지침에서 “모든 사례는 source+observation”으로 명시한 조항은 확인하지 못했다. gold의 required 집합만으로 그 정책을 역으로 확정하지 않는다.
- 판단: 현재 exact-set scorer가 후보 source 누락을 실패로 처리한다는 사실과, 그 source가 readiness 결론에 논리적으로 필수라는 주장은 다르다. **정답 또는 필수 인용 정책의 재검토가 필요함**. 이번에는 REF를 gold에서 제거하거나 기존 결과를 통과로 바꾸지 않는다.

reference 사례 E2 — CASE-f49f3d339e (DEV, F-0f0474efec, variant2)

질문은 동일한 -15°C 입력 준비 여부다. OBS-8b847ae6ae는 warm-range 기록은 있지만 -15°C 측정도 authorized validated extrapolation도 제공되지 않았다고 명시한다. 모델은 {OBS-8b847ae6ae}와 LOW_TEMPERATURE_RESPONSE 요청을 선택했고, 후보는 추가로 REF-c665a0b48f(SR13-HYPSO-RANGE)를 필수로 둔다. [A1, A3, A4]

- 판단 충분성: 평가 조건이 질문에 명시돼 있고 필요한 두 대안이 모두 미제공이라는 관측이 있다. 좁은 readiness 부족 판단과 해당 자료 요청은 그 관측에서 직접 지지된다. 모델이 외삽을 임의 인정하거나 누락 자료를 추정해서 채운 것은 아니다.
- 논문 reference의 역할: 가열 장치의 제한은 왜 따뜻한 구간만으로 저온 실증을 대체할 수 없는지 설명하는 보조 원리다. 이 사례에서는 관측이 이미 필요한 저온 측정/검증된 대안의 부재를 직접 명시하므로, 가용성 결론을 도출할 때 그 논문 진술을 반드시 추가 전제로 사용할 필요는 없다.
- 감사 정책: 출처 원리를 항상 추적하려는 정책 선택은 가능하지만 그것이 결론에 필요한 근거와 동일하지는 않다. 현재 모델에게 감사용 출처 인용을 항상 포함하라고 명확히 안내했는지는 재검토해야 한다. 후보가 reference를 포함한다는 사실만으로 전역 규칙을 추정하지 않는다.
- 판단: **정답 또는 필수 인용 정책의 재검토가 필요함**. 누락됐다고 기록된 source reference를 사후로 삭제하거나 기존 점수를 수정하지 않는다.

reference 계약을 읽은 방식

v13은 실제 판단을 지지하는 “source and observation IDs”를 나열하라고 했고, v14는 제공된 source reference_id **or** observation evidence_id 중 판단을 지지하는 ID를 고르라고 명시한다. 두 지침 모두 모든 ID를 기본값으로 인용하지 말라고 한다. v13의 and 문구가 양 종류의 활용을 기대한다고 읽힐 여지는 있으므로 아무 source도 필요 없다는 전역 규칙으로 반대 방향 추정도 하지 않는다. 다만 어느 문구도 모든 답에 종류별 최소 한 개씩 반드시 포함하라는 명시적 정량 조건은 아니다.

주석 정책의 “필수 참조 수가 2 또는 3”이라는 문장도 확인했다. 이는 작성된 사례의 근거 수에 대한 설명이지만, 어떤 source가 논리적 필수인지와 audit provenance만을 위한 것인지의 기준이나 모든 answer의 source+observation 최소 조합을 설명하지 않는다. 모델 실제 입력에는 그 정책 문서 전체가 삽입되지 않았다. JSON Schema에도 source/observation 종류별 최소 개수 조건이 없고, check_answer는 제공 ID 여부·중복 등을 검사할 뿐 source를 최소 하나 요구하지 않는다. exact reference와 strict는 후보 expected의 정확한 집합에 의존한다. 따라서 “현재 scorer가 요구하는 후보 집합”은 명확하지만 “그 집합이 readiness에서 반드시 필요한 이유”는 별도 정책 판단이다. 이번 작업은 이 간극을 기록할 뿐 scorer를 대체하지 않는다.

TIRS 기존 대기 항목을 같은 목록에 포함

기존 HUMAN_REVIEW_PENDING인 F-d0190c27bc의 세 rationale 문제를 그대로 대기 상태로 유지한다. source는 TIRS §IV/PDF4쪽의 얇은 패널 온도 구배와 거친 nodalization의 한계다. 평균/위치 구분의 원리는 source와 합성 사례가 지지하지만, 모든 variant가 제안을 반박하는 것은 아니다. [A5]

- CASE-79c814ab47, TRAIN variant1: 제안 자체가 평균 일치와 국소 mapping 미해결을 구분하고 추가 검토를 남긴다. 후보 Action은 NO_ACTION_REQUIRED인데 공통 rationale에는 “해당 제안은 국소 차이를 평균값으로 덮으므로 반박한다”가 반복된다. 제안 문구와 이 문장이 충돌하는지 사람이 확인하고, 다음 label revision에서 rationale만 고칠지 결정해야 한다. 현 Action을 바꾼다는 제안이 아니다.
- CASE-424419171a, TRAIN variant2: 좌표·model-to-sensor sampling map이 없는 readiness 문제이며 후보는 REQUEST_EVIDENCE / MEASUREMENT_MAPPING_MISMATCH / SENSOR_NODE_MAP이다. 명시된 반박 제안이 없는데 같은 “해당 제안 … 반박” 문장이 남아 있다. 요청의 원인인 mapping 결손과 일반 지원자료 결손의 경계도 R3의 fallback 검토와 함께 확인한다.
- CASE-e00c7fe02d, TRAIN variant3: 보정 local temperatures·좌표·sampling map·각 위치의 모델 온도가 공급돼 있다. 후보는 readiness의 NO_ACTION_REQUIRED이다. 공통의 “평균값으로 덮으므로 반박” 문장은 현 입력 상태를 설명하지 못한다. readiness와 국소 적합성 판정을 섞지 않는 rationale인지 검토해야 한다.

비교용 CASE-4ad9ed95e2(variant0)는 실제로 평균값 일치를 모든 위치의 일치로 주장하는 제안이므로 반박 문구의 본래 적용 범위를 보여 준다. 이 네 건의 기대값·입력·계산·rationale를 수정하거나 모델을 새로 실행하지 않았다. 기존 세 대기 항목을 자동 해결 처리하지 않는다.

변경 제안만 기록 — 적용·새 채점 없음

- P1: MODEL_SCOPE_EXCEEDED/EVIDENCE_INTERPRETATION_ERROR와 MEASUREMENT_MAPPING_MISMATCH/EVIDENCE_INTERPRETATION_ERROR의 경계 및 둘이 동시에 적용될 때 선택 기준을 명문화할지 사람이 결정한다. 구체 코드 우선이라는 새 규칙을 검토할 수 있으나 현재 존재하는 규칙이라고 소급하지 않는다. radiometric conversion과 spatial mapping의 포괄 범위도 명시할지 검토한다. 허용 코드 집합 자동 확대는 제안하지 않는다.
- P2: 이미 있는 SUPPORTING_EVIDENCE_MISSING의 fallback 조건을 실제 결손 종류별로 일관되게 적용하는지 검토한다. REQUEST_EVIDENCE에서 “기록이 없으니 항상 generic”으로 처리하지 않도록 한다. 잘 맞는 요청 ID와 reason 구체성은 독립 항목으로 유지한다. 모든 REQUEST 후보를 검토 범위에 포함하는 것은 현재 후보가 모두 틀렸다는 뜻이 아니다.
- P3: evidence_refs를 결론의 최소 충분 근거로 요구할지, 출처 원리의 감사 추적까지 항상 담을지 선택하고 문서화한다. 최소 충분 근거 정책을 택하면 여러 유효 집합을 어떻게 정의할지, 감사 정책을 택하면 source의 논리적 기여와 provenance 역할을 어떻게 설명할지 검토한다. source+observation 무조건 인용을 기존 규칙으로 발명하지 않는다. 어떤 선택도 이번 gold/scorer/prompt에 반영하지 않는다.
- P4: TIRS variant1/2/3의 공통 rationale 재사용을 해당 질문·제안 상태에 맞게 다음 label revision에서 고칠지 검토한다. 논문이 내부 Action/reason을 지시했다고 쓰지 않는다.

이 제안은 모델 출력을 본 뒤 나온 사후 제안이다. 주석 정책이 요구하는 “모델 출력 보기 전 freeze” 상태를 이번 자료에서 다시 얻었다고 주장할 수 없다. 독립 검토자를 선정한다면 가능한 한 새 판단을 먼저 기록하게 하고, 누가 기존 출력·후보를 봤는지 함께 남겨야 한다. 향후 정책/label revision은 별도 버전·변경 사유·노출 이력·case/gold hash와 연결한다. 이미 본 DEV8에서 추가 prompt 탐색·추론을 돌려 제안을 선택하지 않는다.

제안의 영향 범위 (TRAIN/DEV만, RESERVED 미접근)

영향 범위는 재검토 대상 목록이며 label 오류나 점수 변화 예측이 아니다. 실제 변경을 하려면 case별 영향 확정이 추가로 필요하다.

P1 reason 경계의 직접 검토 후보:

- TRAIN (10건): `CASE-4ad9ed95e2`, `CASE-424419171a`, `CASE-589fb4eb03`, `CASE-7e2ce553dd`, `CASE-02caf2a304`, `CASE-07dbc2c8c4`, `CASE-d5e287468e`, `CASE-6de39fe5d2`, `CASE-54a9474954`, `CASE-8822d424f6`.
- DEV (6건): `CASE-ec0f24fd6c`, `CASE-18d7b891b1`, `CASE-b40f92306b`, `CASE-1800223793`, `CASE-fc0864226a`, `CASE-c45ab2fec7`.

P2 generic fallback의 직접 검토 후보:

- TRAIN (12건): `CASE-424419171a`, `CASE-555ca15e0e`, `CASE-acec2b7b89`, `CASE-9c036b2503`, `CASE-c51cdfeccd`, `CASE-07dbc2c8c4`, `CASE-cf088dcb3c`, `CASE-c83a53985e`, `CASE-08ee9d45a5`, `CASE-f235c491ee`, `CASE-185d4a0c91`, `CASE-9d61b185f8`.
- DEV (6건): `CASE-f49f3d339e`, `CASE-b40f92306b`, `CASE-df8ed0a5e6`, `CASE-a00c710b3f`, `CASE-71262c17f4`, `CASE-82a92a1c28`.

P3 readiness 우선 범위는 TRAIN24 + DEV12이며 아래 표의 variant2/3 전부다. 전역 인용 정책까지 변경한다면 TRAIN48 + DEV24 전체가 잠재적 영향 범위이므로 네 variant를 모두 나열한다. P4는 TIRS 첫 family의 variant1/2/3 세 건이다. MDPI 출처 SR13-CANYVAL/SR13-PROBAV의 원문 미확보 상태는 유지하며, 아래 ID 나열을 그 원문·정답 검증으로 해석하지 않는다. 세부 선택 규칙과 ID는 PROPOSED_POLICY_IMPACT.json에도 있다.

| split/source/family | variant0 | variant1 | variant2: readiness, P3 | variant3: readiness, P3 |
|---|---|---|---|---|
| TRAIN / SR13-TIRS / F-d0190c27bc | CASE-4ad9ed95e2 | CASE-79c814ab47 | CASE-424419171a | CASE-e00c7fe02d |
| TRAIN / SR13-TIRS / F-9f5d1a8add | CASE-589fb4eb03 | CASE-199314f362 | CASE-555ca15e0e | CASE-a6135d12df |
| TRAIN / SR13-TIRS / F-43933f27b5 | CASE-a7e82e186e | CASE-fe8f8cbdf7 | CASE-acec2b7b89 | CASE-d400650f82 |
| TRAIN / SR13-TIRS / F-bffe89a7f0 | CASE-88b5d13600 | CASE-4196d4ddc2 | CASE-9c036b2503 | CASE-1bdc9a0a66 |
| TRAIN / SR13-NEA / F-f10ef0e47e | CASE-7e2ce553dd | CASE-ed9b08cbf4 | CASE-c51cdfeccd | CASE-493773aa90 |
| TRAIN / SR13-NEA / F-a23c98c073 | CASE-02caf2a304 | CASE-2f88f50fa1 | CASE-07dbc2c8c4 | CASE-61ef0e9728 |
| TRAIN / SR13-NEA / F-f6088ffdf8 | CASE-d5e287468e | CASE-6d4be78aae | CASE-cf088dcb3c | CASE-879754a57b |
| TRAIN / SR13-NEA / F-94b82e4196 | CASE-6de39fe5d2 | CASE-332bc07aa7 | CASE-c83a53985e | CASE-48f4545a71 |
| TRAIN / SR13-RHOBC / F-053c3d8988 | CASE-54a9474954 | CASE-d3f978cae1 | CASE-08ee9d45a5 | CASE-d723874b9f |
| TRAIN / SR13-RHOBC / F-c84e3089cd | CASE-9df6407dbd | CASE-0ca276ca1e | CASE-f235c491ee | CASE-703b0ad936 |
| TRAIN / SR13-RHOBC / F-cdd6fc4b87 | CASE-8822d424f6 | CASE-bbdb74ad02 | CASE-185d4a0c91 | CASE-b94839f32b |
| TRAIN / SR13-RHOBC / F-0b24c9f95e | CASE-13e084e68e | CASE-5616686acf | CASE-9d61b185f8 | CASE-d029eccb5c |
| DEV / SR13-HYPSO / F-0f0474efec | CASE-ec0f24fd6c | CASE-d48966c293 | CASE-f49f3d339e | CASE-8261f9621f |
| DEV / SR13-HYPSO / F-57ad3ec434 | CASE-18d7b891b1 | CASE-5bf8af5346 | CASE-b40f92306b | CASE-a18319c1d2 |
| DEV / SR13-CANYVAL / F-e14546bbe1 | CASE-870c379fa0 | CASE-e7386f7ddf | CASE-df8ed0a5e6 | CASE-4e774a1974 |
| DEV / SR13-CANYVAL / F-e6c49196e6 | CASE-1800223793 | CASE-0bf2f59697 | CASE-a00c710b3f | CASE-1fb4ec74a4 |
| DEV / SR13-PROBAV / F-c7a41a91dd | CASE-fc0864226a | CASE-d05caa3edc | CASE-71262c17f4 | CASE-15d397cc74 |
| DEV / SR13-PROBAV / F-e5cd6d3740 | CASE-c45ab2fec7 | CASE-2346b4ee7f | CASE-82a92a1c28 | CASE-e8a8b979ca |

보존과 검토의 한계

이 검토는 기존 점수 파일을 읽거나 인용할 수 있어도 scorer를 실행하지 않는다. 기존 official/diagnostic 점수를 새로 산출하지 않았으며, permissive reason·reduced reference로 과거 결과를 보정하지 않았다. 모든 기존 파일의 시작·종료 SHA256 대조를 PRESERVATION_BEFORE.json/PRESERVATION_AFTER.json에 남긴다. direct_v14 생성 완료 상태는 그대로 보존한다. CPU token 재검사, 새 추론·학습, ledger·constrained decoding, Pod 조회/잠금 변경/STOP도 하지 않았다.

실제 운영 시스템이 reason별로 어떤 담당자·도구·필수 검토 경로를 선택하는지는 제공 자료에 없다. 저장된 Action/요청 항목의 동일성은 확인할 수 있지만, code 차이가 배포 시스템의 후속 조치를 전혀 바꾸지 않는다는 보장은 하지 못한다. 이 한계는 아래 독립 항목으로 분류한다.

사용자가 확인할 통합 검토 목록과 최종 분류

아래 분류는 이 사후 AI 검토의 결론이며 승인 기록이 아니다. 사람 검토 완료란은 만들거나 채우지 않았다. 각 행은 하나의 최종 분류를 가지며, 후속 결정은 새 버전에만 적용한다.

| 항목 | 사용자가 실제로 확인할 결정 | 최종 분류 |
|---|---|---|
| R1 — CASE-ec0f24fd6c | 실험 범위 초과와 넓은 증거 해석 오류가 겹칠 때 구체 코드 우선을 새로 명시할지; 기존 정의만으로 단일 canonical을 강제할 근거가 있는지 | 기존 정의의 경계가 불명확함 |
| R2 — CASE-18d7b891b1 | IR-derived 값→표면 온도의 대응을 mapping으로 명시할지; 그 오류를 지적하는 EVIDENCE_INTERPRETATION_ERROR와의 경계를 어떻게 정의할지 | 기존 정의의 경계가 불명확함 |
| R3 — CASE-b40f92306b | IR 경로 보정 결손이 현재 mapping 정의에 해당함을 확인하고, 적용 가능한 구체 코드가 있는데 generic을 고른 fallback 위반인지 승인 여부 결정; IR_PATH_CALIBRATION 요청 일치는 별도 유지 | 기존 계약상 명확한 모델 오류 |
| E1 — CASE-8261f9621f | 명시적으로 공급된 별도 -15°C run의 readiness에서 논문 REF가 결론 필수 근거인지 감사용 provenance인지 결정 | 정답 또는 필수 인용 정책의 재검토가 필요함 |
| E2 — CASE-f49f3d339e | 관측이 필요한 저온 측정/검증 대안 부재를 직접 말할 때 source REF를 필수로 둘 실제 계약 근거 확인 | 정답 또는 필수 인용 정책의 재검토가 필요함 |
| T1 — CASE-79c814ab47 | 제한을 인정하는 제안의 NO_ACTION_REQUIRED와 “해당 제안을 반박” 공통 rationale의 충돌을 다음 revision에서 해소할지 | 정답 또는 필수 인용 정책의 재검토가 필요함 |
| T2 — CASE-424419171a | mapping 결손 REQUEST와 무관한 제안 반박 문구를 제거/교체할지; SENSOR_NODE_MAP과 mapping reason의 관계 확인 | 정답 또는 필수 인용 정책의 재검토가 필요함 |
| T3 — CASE-e00c7fe02d | 위치 대응 입력이 모두 공급된 readiness 정상 사례에 평균값 반박 rationale가 남은 이유 확인 | 정답 또는 필수 인용 정책의 재검토가 필요함 |
| O1 — reason별 실제 운영 후속 조치 | reason→담당자·도구·승인 경로의 실제 계약/구현을 제공해 코드 차이의 운영 영향을 확인; 이번에는 출력 요청 동일성까지만 확정 | 확보한 자료만으로 판정 불가 |
