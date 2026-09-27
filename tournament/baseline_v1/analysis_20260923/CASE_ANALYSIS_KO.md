# 저장된 baseline 검증 및 사례 분석

공식 점수는 원본 그대로다. 코드 블록 내부 JSON은 오류 분류를 위한 진단에만 사용하며 공식 성공으로 재채점하지 않았다. 파싱 불가 사례의 잘못된 정상 판정 0건은 안전성 증거가 아니다.

| 모델 | Action /84 | refs /64 | strict /84 | 공식 잘못된 수용 | 진단상 잘못된 수용 | 생성 초 | peak GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen35_9b | 77 | 64 | 60 | 1 | 1 | 118.89 | 17.92 |
| gemma4_12b | 19 | 0 | 16 | 0 | 1 | 152.04 | 22.84 |
| mistral32_24b | 19 | 0 | 17 | 0 | 1 | 199.44 | 45.19 |
| gemma4_26b_a4b | 19 | 0 | 18 | 0 | 0 | 202.28 | 48.70 |
| qwen38_27b | 82 | 60 | 69 | 1 | 1 | 286.32 | 51.61 |

reference exact의 대상은 NS10와 before40 64건이다. Contract20은 별도의 legacy 필드 비교다. 시간은 모델 로딩을 제외한 생성 시간이며 최초 warmup을 포함한다. VRAM은 PyTorch peak allocated 값이다. 기존 E4B LoRA는 다른 환경의 NF4 기록이므로 속도와 메모리를 직접 순위 비교하지 않는다.

## qwen35_9b

오류 분류: `{"reason_mismatch": 17, "action_mismatch": 6, "field_mismatch:requested_evidence": 4, "wrong_acceptance": 1, "field_mismatch:tool": 2, "field_mismatch:arguments": 2, "output_contract_invalid": 1, "generation_limit": 1, "semantic_unresolved": 1}`

| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |
|---|---|---|---|
| NS10-E2-A | reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → EVIDENCE_INTERPRETATION_ERROR |
| NS10-E4-A | action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | CONFIGURATION_SCOPE_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| NS10-T2-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | BOUNDARY_CONDITION_UNRESOLVED → RADIOMETRIC_EQUIVALENCE_UNRESOLVED |
| NS10-M4-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | FORCE_LIMIT_BASIS_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| NS10-T4-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → MONITORING_COVERAGE_INSUFFICIENT |
| NS10-M1-B | reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P02-A | reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P02-A | action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | FORCE_LIMIT_BASIS_UNRESOLVED → FORCE_LIMIT_BASIS_UNRESOLVED |
| PHY-VBX1-P01-A | reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P08-A | reason_mismatch | CHALLENGE → CHALLENGE | TEST_ARTIFACT_UNMODELED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P03-A | reason_mismatch | CHALLENGE → CHALLENGE | PARAMETER_IDENTIFICATION_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P04-A | action_mismatch, wrong_acceptance, reason_mismatch | CHALLENGE → NO_ACTION_REQUIRED | METHOD_INTERPRETATION_ERROR → — |
| PHY-VBX1-P06-A | reason_mismatch | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P04-A | action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | RADIOMETRIC_EQUIVALENCE_UNRESOLVED → RADIOMETRIC_EQUIVALENCE_UNRESOLVED |
| PHY-VBX1-P03-A | reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P05-A | action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | POWER_DISSIPATION_UNRESOLVED → POWER_DISSIPATION_UNRESOLVED |
| PHY-VBX1-P05-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MODAL_INPUTS_MISSING → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| PHY-EE02-P02-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MONITORING_COVERAGE_INSUFFICIENT → MEASUREMENT_MAPPING_MISMATCH |
| PHY-EE03-P01-A | reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| DEV-AN-001 | field_mismatch:tool, field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-AN-002 | field_mismatch:tool, field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-AN-003 | action_mismatch, reason_mismatch | REQUEST_EVIDENCE → CALL_TOOL | DURATION_INPUT_MISSING → — |
| DEV-CR-003 | reason_mismatch | CHALLENGE → CHALLENGE | EVIDENCE_CONTRADICTION → SCOPE_ERROR |
| DEV-CR-007 | output_contract_invalid, generation_limit, semantic_unresolved | NO_ACTION_REQUIRED → 해석 불가 | — → — |

## gemma4_12b

오류 분류: `{"output_contract_invalid": 65, "reason_mismatch": 18, "action_mismatch": 12, "field_mismatch:requested_evidence": 9, "reference_mismatch": 1, "unnecessary_intervention": 2, "wrong_acceptance": 1, "field_mismatch:tool": 2, "field_mismatch:arguments": 2, "field_mismatch:valid_scope": 1}`

| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |
|---|---|---|---|
| NS10-E2-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → EVIDENCE_INTERPRETATION_ERROR |
| NS10-T1-B | output_contract_invalid | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| NS10-T2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E3-B | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | EXPOSURE_METADATA_UNRESOLVED → MODAL_INPUTS_MISSING |
| NS10-E4-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | CONFIGURATION_SCOPE_UNRESOLVED → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| NS10-T4-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | MODAL_INPUTS_MISSING → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| NS10-T2-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → MODAL_INPUTS_MISSING |
| NS10-T3-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | FORCE_LIMIT_BASIS_UNRESOLVED → FORCE_LIMIT_BASIS_UNRESOLVED |
| NS10-T3-B | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-T4-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → POWER_DISSIPATION_UNRESOLVED |
| NS10-E3-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-B | output_contract_invalid | CHALLENGE → CHALLENGE | EVIDENCE_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M3-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-T1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M3-B | output_contract_invalid, reason_mismatch, reference_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M1-B | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → EVIDENCE_INTERPRETATION_ERROR |
| NS10-E2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E4-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P02-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P02-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | FORCE_LIMIT_BASIS_UNRESOLVED → FORCE_LIMIT_BASIS_UNRESOLVED |
| PHY-TH01-P06-A | output_contract_invalid | CHALLENGE → CHALLENGE | STABILITY_UNRESOLVED → STABILITY_UNRESOLVED |
| PHY-VBX1-P01-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P08-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | TEST_ARTIFACT_UNMODELED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P08-A | output_contract_invalid | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → MODEL_SCOPE_EXCEEDED |
| PHY-TH01-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P07-A | output_contract_invalid | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| PHY-TH01-P07-B | output_contract_invalid, action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → CHALLENGE | — → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P01-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | CONFIGURATION_SCOPE_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| PHY-VBX1-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P03-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | PARAMETER_IDENTIFICATION_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P04-A | output_contract_invalid | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P06-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | RADIOMETRIC_EQUIVALENCE_UNRESOLVED → RADIOMETRIC_EQUIVALENCE_UNRESOLVED |
| PHY-TH01-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P03-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P05-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | POWER_DISSIPATION_UNRESOLVED → POWER_DISSIPATION_UNRESOLVED |
| PHY-VBX1-P07-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | MODAL_INPUTS_MISSING → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P07-A | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | PROBABILISTIC_ASSUMPTIONS_UNRESOLVED → MODAL_INPUTS_MISSING |
| PHY-TH01-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P01-A | output_contract_invalid, action_mismatch, wrong_acceptance, reason_mismatch | CHALLENGE → NO_ACTION_REQUIRED | EVIDENCE_INTERPRETATION_ERROR → — |
| PHY-EE02-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P02-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MONITORING_COVERAGE_INSUFFICIENT → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE02-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE03-P01-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-EE03-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE03-P02-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | EXPOSURE_METADATA_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| PHY-EE03-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| DEV-AN-001 | field_mismatch:tool, field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-AN-002 | field_mismatch:tool, field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-CR-003 | field_mismatch:valid_scope | CHALLENGE → CHALLENGE | EVIDENCE_CONTRADICTION → EVIDENCE_CONTRADICTION |
| DEV-CR-007 | output_contract_invalid, action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → CHALLENGE | — → EVIDENCE_CONTRADICTION |

## mistral32_24b

오류 분류: `{"output_contract_invalid": 64, "reference_mismatch": 9, "reason_mismatch": 14, "action_mismatch": 4, "wrong_acceptance": 1, "unnecessary_intervention": 2, "field_mismatch:arguments": 2}`

| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |
|---|---|---|---|
| NS10-E2-A | output_contract_invalid | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → MONITORING_COVERAGE_INSUFFICIENT |
| NS10-T1-B | output_contract_invalid | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| NS10-T2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E3-B | output_contract_invalid, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | EXPOSURE_METADATA_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| NS10-E4-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | CONFIGURATION_SCOPE_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| NS10-T4-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-A | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MODAL_INPUTS_MISSING → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| NS10-T2-A | output_contract_invalid, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | BOUNDARY_CONDITION_UNRESOLVED → BOUNDARY_CONDITION_UNRESOLVED |
| NS10-T3-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-A | output_contract_invalid, reason_mismatch, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | FORCE_LIMIT_BASIS_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| NS10-T3-B | output_contract_invalid | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → METHOD_INTERPRETATION_ERROR |
| NS10-T4-A | output_contract_invalid, reason_mismatch, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → MONITORING_COVERAGE_INSUFFICIENT |
| NS10-E3-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-B | output_contract_invalid | CHALLENGE → CHALLENGE | EVIDENCE_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M3-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-T1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M3-B | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M1-B | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → EVIDENCE_INTERPRETATION_ERROR |
| NS10-E2-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E4-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P02-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P02-A | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | FORCE_LIMIT_BASIS_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| PHY-TH01-P06-A | output_contract_invalid | CHALLENGE → CHALLENGE | STABILITY_UNRESOLVED → STABILITY_UNRESOLVED |
| PHY-VBX1-P01-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P08-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | TEST_ARTIFACT_UNMODELED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P08-A | output_contract_invalid | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → MODEL_SCOPE_EXCEEDED |
| PHY-TH01-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P07-A | output_contract_invalid | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| PHY-TH01-P07-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P01-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | CONFIGURATION_SCOPE_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| PHY-VBX1-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P03-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | PARAMETER_IDENTIFICATION_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P04-A | output_contract_invalid, action_mismatch, wrong_acceptance, reason_mismatch | CHALLENGE → NO_ACTION_REQUIRED | METHOD_INTERPRETATION_ERROR → — |
| PHY-VBX1-P06-A | output_contract_invalid | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → MODEL_SCOPE_EXCEEDED |
| PHY-VBX1-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | RADIOMETRIC_EQUIVALENCE_UNRESOLVED → RADIOMETRIC_EQUIVALENCE_UNRESOLVED |
| PHY-TH01-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P03-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P05-A | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| PHY-VBX1-P07-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MODAL_INPUTS_MISSING → MODAL_INPUTS_MISSING |
| PHY-VBX1-P07-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | PROBABILISTIC_ASSUMPTIONS_UNRESOLVED → PROBABILISTIC_ASSUMPTIONS_UNRESOLVED |
| PHY-TH01-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P01-A | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → REQUEST_EVIDENCE | EVIDENCE_INTERPRETATION_ERROR → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE02-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P02-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MONITORING_COVERAGE_INSUFFICIENT → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE02-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE03-P01-A | output_contract_invalid | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE03-P01-B | output_contract_invalid, action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → CHALLENGE | — → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE03-P02-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | EXPOSURE_METADATA_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| PHY-EE03-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| DEV-AN-001 | field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-AN-002 | field_mismatch:arguments | CALL_TOOL → CALL_TOOL | — → — |
| DEV-CR-002 | action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → CHALLENGE | — → EVIDENCE_CONTRADICTION |

## gemma4_26b_a4b

오류 분류: `{"output_contract_invalid": 64, "reason_mismatch": 17, "reference_mismatch": 15, "action_mismatch": 11, "field_mismatch:requested_evidence": 4, "field_mismatch:valid_scope": 1, "unnecessary_intervention": 1}`

| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |
|---|---|---|---|
| NS10-E2-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → EVIDENCE_INTERPRETATION_ERROR |
| NS10-T1-B | output_contract_invalid, reference_mismatch | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| NS10-T2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E3-B | output_contract_invalid, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | EXPOSURE_METADATA_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| NS10-E4-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | CONFIGURATION_SCOPE_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| NS10-T4-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-A | output_contract_invalid, action_mismatch, reason_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | MODAL_INPUTS_MISSING → METHOD_INTERPRETATION_ERROR |
| NS10-T2-A | output_contract_invalid, reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | BOUNDARY_CONDITION_UNRESOLVED → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| NS10-T3-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M1-A | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M4-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | FORCE_LIMIT_BASIS_UNRESOLVED → FORCE_LIMIT_BASIS_UNRESOLVED |
| NS10-T3-B | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → EVIDENCE_INTERPRETATION_ERROR | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-T4-A | output_contract_invalid, reason_mismatch, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → PARAMETER_IDENTIFICATION_INSUFFICIENT |
| NS10-E3-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M2-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-B | output_contract_invalid, reference_mismatch | CHALLENGE → CHALLENGE | EVIDENCE_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M3-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-T1-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M3-B | output_contract_invalid, reason_mismatch, reference_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M1-B | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → EVIDENCE_INTERPRETATION_ERROR | MODE_SELECTION_MISMATCH → EVIDENCE_INTERPRETATION_ERROR |
| NS10-E2-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E4-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-E1-A | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P02-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P06-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P02-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | FORCE_LIMIT_BASIS_UNRESOLVED → FORCE_LIMIT_BASIS_UNRESOLVED |
| PHY-TH01-P06-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | STABILITY_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P01-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-TH01-P08-A | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → METHOD_INTERPRETATION_ERROR | TEST_ARTIFACT_UNMODELED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-TH01-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P08-A | output_contract_invalid | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → MODEL_SCOPE_EXCEEDED |
| PHY-TH01-P05-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P01-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P07-A | output_contract_invalid | CHALLENGE → CHALLENGE | MEASUREMENT_MAPPING_MISMATCH → MEASUREMENT_MAPPING_MISMATCH |
| PHY-TH01-P07-B | output_contract_invalid, reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P01-A | output_contract_invalid, reference_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | CONFIGURATION_SCOPE_UNRESOLVED → CONFIGURATION_SCOPE_UNRESOLVED |
| PHY-VBX1-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P03-A | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → METHOD_INTERPRETATION_ERROR | PARAMETER_IDENTIFICATION_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P04-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P06-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODEL_SCOPE_EXCEEDED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P04-A | output_contract_invalid, action_mismatch, field_mismatch:requested_evidence | REQUEST_EVIDENCE → CHALLENGE | RADIOMETRIC_EQUIVALENCE_UNRESOLVED → RADIOMETRIC_EQUIVALENCE_UNRESOLVED |
| PHY-TH01-P08-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P03-A | output_contract_invalid, reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P03-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-TH01-P05-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → POWER_DISSIPATION_UNRESOLVED |
| PHY-VBX1-P07-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-VBX1-P05-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MODAL_INPUTS_MISSING → MODAL_INPUTS_MISSING |
| PHY-VBX1-P07-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | PROBABILISTIC_ASSUMPTIONS_UNRESOLVED → PROBABILISTIC_ASSUMPTIONS_UNRESOLVED |
| PHY-TH01-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P01-A | output_contract_invalid, action_mismatch | CHALLENGE → EVIDENCE_INTERPRETATION_ERROR | EVIDENCE_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| PHY-EE02-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE02-P02-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | MONITORING_COVERAGE_INSUFFICIENT → MONITORING_COVERAGE_INSUFFICIENT |
| PHY-EE02-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE03-P01-A | output_contract_invalid, action_mismatch, reason_mismatch | CHALLENGE → EVIDENCE_INTERPRETATION_ERROR | MONITORING_COVERAGE_INSUFFICIENT → EVIDENCE_INTERPRETATION_ERROR |
| PHY-EE03-P01-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| PHY-EE03-P02-A | output_contract_invalid | REQUEST_EVIDENCE → REQUEST_EVIDENCE | EXPOSURE_METADATA_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| PHY-EE03-P02-B | output_contract_invalid | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| DEV-CR-003 | field_mismatch:valid_scope | CHALLENGE → CHALLENGE | EVIDENCE_CONTRADICTION → EVIDENCE_CONTRADICTION |
| DEV-CR-007 | action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → CHALLENGE | — → EVIDENCE_CONTRADICTION |

## qwen38_27b

오류 분류: `{"reason_mismatch": 11, "reference_mismatch": 4, "action_mismatch": 2, "wrong_acceptance": 1, "unnecessary_intervention": 1}`

| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |
|---|---|---|---|
| NS10-E2-A | reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → EVIDENCE_INTERPRETATION_ERROR |
| NS10-E4-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | CONFIGURATION_SCOPE_UNRESOLVED → EXPOSURE_METADATA_UNRESOLVED |
| NS10-T4-B | reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-T4-A | reason_mismatch | REQUEST_EVIDENCE → REQUEST_EVIDENCE | POWER_DISSIPATION_UNRESOLVED → MONITORING_COVERAGE_INSUFFICIENT |
| NS10-E1-B | reference_mismatch | CHALLENGE → CHALLENGE | EVIDENCE_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M3-A | reference_mismatch | NO_ACTION_REQUIRED → NO_ACTION_REQUIRED | — → — |
| NS10-M3-B | reason_mismatch, reference_mismatch | CHALLENGE → CHALLENGE | METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR |
| NS10-M1-B | reason_mismatch | CHALLENGE → CHALLENGE | MODE_SELECTION_MISMATCH → EVIDENCE_INTERPRETATION_ERROR |
| PHY-TH01-P02-A | reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → EVIDENCE_INTERPRETATION_ERROR |
| PHY-VBX1-P01-A | reason_mismatch | CHALLENGE → CHALLENGE | BOUNDARY_CONDITION_UNRESOLVED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P08-A | reason_mismatch | CHALLENGE → CHALLENGE | TEST_ARTIFACT_UNMODELED → METHOD_INTERPRETATION_ERROR |
| PHY-TH01-P03-A | reason_mismatch | CHALLENGE → CHALLENGE | PARAMETER_IDENTIFICATION_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| PHY-VBX1-P04-A | action_mismatch, wrong_acceptance, reason_mismatch | CHALLENGE → NO_ACTION_REQUIRED | METHOD_INTERPRETATION_ERROR → — |
| PHY-EE03-P01-A | reason_mismatch | CHALLENGE → CHALLENGE | MONITORING_COVERAGE_INSUFFICIENT → METHOD_INTERPRETATION_ERROR |
| DEV-AN-005 | action_mismatch, unnecessary_intervention | NO_ACTION_REQUIRED → REQUEST_EVIDENCE | — → DURATION_INPUT_MISSING |
