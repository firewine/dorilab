# DoriLab baseline 완료 및 LoRA 후보 제안

다섯 baseline의 각 84건, 총 420건 저장 결과를 검증했다. 정상 완료 모델의 추론은 반복하지 않았다. Qwen3.8-27B만 최초 다운로드의 디스크 부족을 복구한 뒤 동일 revision으로 추론했다. frozen 입력과 정답, scorer, BF16, adapter 없음, greedy, native tokenizer/chat template 조건은 유지했다. LoRA는 아직 실행하지 않았다.

## 공식 지표

| 모델 | 잘못된 정상 판정 | Action /84 | reference exact /64 | strict /84 | reason joint /41 | 유효 출력 /84 | 생성 초 | peak allocated GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-9B | 1 | 77 | 64 | 60 | 20 | 83 | 118.89 | 17.92 |
| Gemma 4 12B | 0* | 19 | 0 | 16 | 9 | 19 | 152.04 | 22.84 |
| Mistral Small 3.2 24B | 0* | 19 | 0 | 17 | 9 | 20 | 199.44 | 45.19 |
| Gemma 4 26B-A4B | 0* | 19 | 0 | 18 | 9 | 20 | 202.28 | 48.70 |
| Qwen3.8-27B | 1 | 82 | 60 | 69 | 30 | 84 | 286.32 | 51.61 |

`*` NS10와 before40의 64건 모두 코드 블록으로 감싸져 공식 JSON 파싱에 실패했다. 파싱 실패에서 집계된 오수용 0은 안전성 우위의 근거가 아니다. Gemma 12B는 Contract20의 channel 표식 포함 출력 1건도 파싱에 실패했다. 표의 Action·reference·strict는 원본 채점을 유지했다.

Reference exact 대상은 NS10+before40의 64건이다. Contract20의 유효 출력은 legacy 검사이며 필수 도구 인자까지 완전하다는 뜻은 아니다. 시간은 로딩 제외 생성 합계이고 warmup을 포함한다. peak allocated는 PyTorch 측정치이며 시스템 전체 VRAM 점유와 다르다.

## 사례별 의미 오류 진단

코드 블록과 실제 관찰된 빈 channel prefix를 분리해 내부 JSON을 읽었다. 이 작업은 원본 점수 수정, 재실행 또는 공식 통과 처리가 아니다. 아래 수치는 진단이며 단순한 공식 지표 대체에 사용하지 않는다. 오류 범주는 중첩된다.

| 모델 | 잘못된 정상 판정 | Action 불일치 | reference 불일치 | reason 불일치 | 의미 해석 미완결 |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-9B | 1 | 6 | 0 | 17 | 1 |
| Gemma 4 12B | 1 | 12 | 1 | 18 | 0 |
| Mistral Small 3.2 24B | 1 | 4 | 9 | 14 | 0 |
| Gemma 4 26B-A4B | 0 | 11 | 15 | 17 | 0 |
| Qwen3.8-27B | 1 | 2 | 4 | 11 | 0 |

- **잘못된 정상 판정:** Qwen 9B·Qwen 27B·Mistral은 `PHY-VBX1-P04-A`에서 서로 다른 주파수의 최대값을 허용하는 식 (2)의 계산을 기각하자는 제안을 수용했다. Gemma 12B는 `PHY-EE02-P01-A`에서 시험 후 복귀만으로 시험 중 간섭 이상이 없었다는 제안을 수용했다. Gemma 26B는 이 두 사례를 CHALLENGE했으며, 진단 가능한 전체 84건에서 해당 오수용은 없었다.
- **Qwen 9B:** REQUEST_EVIDENCE 대신 CHALLENGE 4건, 누락된 duration 입력에서 CALL_TOOL 1건, 위 오수용 1건. `DEV-CR-007`은 384-token 제한으로 JSON이 미완결이다. `DEV-AN-001/002`는 tool/arguments 구조가 빠졌다. 경계조건·모드·시험 인공효과·모델 범위를 METHOD_INTERPRETATION_ERROR로 분류하는 오류가 많다.
- **Gemma 12B:** 요청해야 할 자료를 반박으로 바꾸는 오류가 많고 request 필드 불일치가 9건이다. 근거 누락 외에도 CALL_TOOL 필드명과 valid_scope 누락이 있다. 이유 분류에서 관측 해석·모달 입력·파라미터 식별을 혼동한다.
- **Mistral 24B:** Action 오류는 4건이나 원문 source reference를 9건 누락한다. CALL_TOOL arguments 불일치 2건, force-limit 근거를 configuration scope로 바꾸는 등의 reason 혼동이 있다. Qwen 계열과 동일한 잘못된 정상 판정이 남는다.
- **Gemma 26B-A4B:** 잘못된 정상 판정은 없지만 CHALLENGE와 REQUEST_EVIDENCE 혼동을 포함해 Action 오류 11건이다. reference 오류 15건 중 14건은 누락만, 1건은 다른 참조 구성이다. reason 오류 17건은 주로 EVIDENCE_INTERPRETATION_ERROR·METHOD_INTERPRETATION_ERROR로 구체적인 원인을 뭉뚱그리는 형태다. Contract20은 valid_scope 누락과 정상 사례 과잉 개입이 남는다.
- **Qwen 27B:** Action 오류는 위 오수용과 `DEV-AN-005` 정상 사례에서 DURATION_INPUT_MISSING을 요청한 2건이다. NS10 `T4-B/E1-B/M3-A/M3-B`의 source reference가 빠졌다. reason은 configuration scope ↔ exposure metadata, power dissipation ↔ monitoring coverage, method ↔ evidence interpretation 등을 혼동한다.

전체 사례별 기대값·실제값·원문 출력은 `analysis_20260923/case_analysis.jsonl`, 읽기용 표는 `analysis_20260923/CASE_ANALYSIS_KO.md`에 있다.

## 기존 LoRA와 비교

| 모델 | Action /84 | reference /64 | strict /84 | 잘못된 정상 판정 |
|---|---:|---:|---:|---:|
| 기존 Qwen3.5-2B LoRA repeat | 82 | 64 | 75 | 2 |
| 기존 Gemma 4 E4B LoRA | 83 | 64 | 73 | 1 |

새 baseline만으로 기존 LoRA를 전반적으로 능가했다고 할 수 없다. Qwen 27B는 9B 대비 Action +5, strict +9, reason joint +10이지만 reference -4이고 생성 2.41배, peak VRAM 2.88배다. 단순 용량 증가로 고질적인 오수용이 해소되지 않았다. 기존 E4B LoRA에는 학습 전 정답이던 reason을 오답으로 바꾼 NS10-T3-B와 PHY-VBX1-P08-A 사례도 있어 학습 후 회귀를 별도로 검사해야 한다.

기존 LoRA의 속도·메모리는 다른 환경/정밀도 기록이다. E4B는 NF4로 생성 270.97초·peak 9.15 GiB였다. 2B의 NS10+before40은 113.18초·peak 4.39 GiB이고 Contract20 시간은 누락돼 있다. 현재 BF16 후보의 운영 효율과 직접 순위 비교하지 않는다.

## 추천: 두 모델을 각각 고정 조건으로 한 번만 학습

1. **Gemma 4 26B-A4B:** 사용자의 최우선 기준인 잘못된 정상 판정에서 유일하게 다른 실패 양상을 보인다. 코드 블록 내부 JSON에서도 오수용이 없었다. 출력 형식·근거·Action을 LoRA가 개선할 수 있는지 확인할 가치가 있다. 현재 공식 계약 실패가 크므로 제품 연결 후보로 확정하지 않는다. 오수용 0은 이 개발 세트 안의 관찰일 뿐 일반적인 안전성 증명이 아니다.
2. **Qwen3.8-27B:** 공식 출력 유효 84/84, Action 82/84, reason joint 30/41이며 다섯 baseline 중 현재 계약에서 가장 완성도가 높다. 9B 대비 개선된 다섯 Action과 Contract20의 필드 준수는 의미가 있다. 다만 오수용 1건과 source reference 누락 4건은 학습 후 반드시 재검사한다.

Qwen 9B는 속도와 VRAM, 근거 정확도가 강한 비용 절감 대안이다. 이번 최대 2개 실험에서는 오수용 실패 양상이 다른 Gemma 26B와 더 높은 Action 정확도의 Qwen 27B를 우선한다. 작은 모델의 비용상 이점을 놓치지 않도록 학습 후에도 9B baseline과 함께 비교한다. Gemma 12B와 Mistral은 출력 계약 위반에 더해 오수용도 남아 두 후보보다 우선할 근거가 부족하다.

## 승인 후 실행할 고정 비교 조건

- 데이터: `/workspace/dorilab/dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl`, 246행.
- SHA256: `fc94a57e1f01999b366a4ae1b9af16ec0db64e8c0fdf87df9f71bc47b039ad0d`.
- rank 16, alpha 32, dropout 0.05, learning rate 5e-5, epochs 2, max length 2048, seed 42, response-only loss.
- 실제 모델 구조에서 target module을 확인하고 해당 native chat template을 사용한다. 초기 비교는 각 모델 1회이며 LR/epoch sweep은 하지 않는다.
- 학습 후 같은 frozen 84건으로 baseline 대비 gain/loss, 잘못된 정상 판정, Action·reference·reason 회귀를 기록한다.
- 학습 실행은 사용자 후보 확인 이후다. 모델 선택은 제품 배포/공학 승인과 별개다.

최종 Model Router와 공통 입출력 계약을 유지한다. Scope·형상·권한은 deterministic governed layer, 의미 해석은 Specialist LLM, 계산은 수치 도구, 승인은 프로젝트 권한자의 역할로 유지한다. KASA/ECSS/NASA 프로파일, 상위 생애주기와 ReviewGate, 14단계 시험 생애주기, BM1/NTR/BM2, Governed Blackboard 구조를 변경하지 않는다. 이 84건은 개발·회귀 세트이며 최종 제품 모델 확정에는 새로운 독립 평가가 필요하다.
