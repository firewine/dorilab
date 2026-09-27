# v12 — reason 분류 학습 공백 보강 실험

## 먼저 확인한 사실

v11은 실제 position210 export와 e2 RUN_MANIFEST의 데이터 hash를 연결했다.
이 export는 Contract150 + Physics60회 제시이며 고유 Physics 상태는 20개다.
NS10 baseline 오류 6건 중 4건이 사용하는 정답 reason 3종은 학습 정답에 0회 등장했다.
나머지 2건의 코드도 각 3행이지만 원래 사례 한 개의 위치 변형이다.
반면 MEASUREMENT_MAPPING_MISMATCH와 MODAL_INPUTS_MISSING은 정답 노출 0회인데 NS10에서 맞혔다.
따라서 직접 분류 예제의 누락을 확인했을 뿐, 원인·2B 용량 한계·개선 가능성을 확정한 것은 아니다.

## 실험 목적

계속 설명을 덧붙이거나 기존 평가문제를 정답으로 학습시키지 않고,
기존 출처의 새 가상 사례를 이용해 누락된 코드와 혼동하는 코드를 대비한다.
현재 e2와 프롬프트·범위 게이트는 보존한다. 모델 입력에 v09 reason guide를 추가하지 않는다.

| 항목 | repeat 대조군 | coverage 보강군 |
|---|---|---|
| 기존 자료 | position210 그대로 | 동일 |
| 추가 행 | 기존 Physics의 action 분포를 맞춘 반복 36행 | AI 작성 새 36상태 / 18쌍 |
| 합계 | 246행 | 246행 |
| 추가 action | CHALLENGE8 / REQUEST10 / NO_ACTION18 | 동일 |
| 학습 | 원본 Qwen3.5-2B에서 새 LoRA, rank16, lr5e-5, 2epoch | 동일 |
| 평가 | 기존 NS10 baseline 입력24 + before40 회귀 + Contract20 | 동일 |

추가 학습량이 늘어난 효과와 새 예제의 효과를 일부 분리하기 위해 repeat 대조군을 둔다.
두 군은 슬롯/행/action 분포를 맞추지만 입력 길이·정답 길이·정답 reason 분포는 동일하지 않다.
새 내용과 분류 label의 공동 변경이다. 특정 요인의 순수 인과 효과나 독립 통계실험을 뜻하지 않는다.

## 신규 36개 구성

각 코드마다 서로 다른 상황의 2쌍을 작성했다. 각 쌍은 문제/정상 상태로 구성된다.
reason이 있는 18상태, reason 없는 NO_ACTION 18상태다.
고유 사례 수는 전체 물리시험의 독립성을 뜻하지 않는다.

- 누락 5종: CONFIGURATION_SCOPE_UNRESOLVED, EXPOSURE_METADATA_UNRESOLVED,
  METHOD_INTERPRETATION_ERROR, MEASUREMENT_MAPPING_MISMATCH, MODAL_INPUTS_MISSING
- 단일 유형에 집중됐던 2종: FORCE_LIMIT_BASIS_UNRESOLVED, POWER_DISSIPATION_UNRESOLVED
- 혼동되는 기존 유형 2종: MONITORING_COVERAGE_INSUFFICIENT, EVIDENCE_INTERPRETATION_ERROR

출처는 기존 TH-01 / VB-X1 / EE-02 / EE-03이다.
NS10의 MRO / CM-2 / RTG4 문헌, 사례/정답 텍스트를 새 학습행 생성에 넣지 않았다.
평가파일은 생성 후 정확한 중복 검사와 추론/채점에만 사용한다.
NS10은 이미 결과를 본 뒤 이 계획을 설계한 개발 회귀 세트다. 계속 독립 holdout이라고 부르지 않는다.
향후 최종 성능은 별도로 동결한 새 사례에서 확인한다.

source fact는 기존 제공·AI 검토 패킷의 발췌를 재사용했다.
새 METHOD 사례는 기존 VB-X1 출판사 HTML §2 Eq.(2)의 독립 최댓값과 질량 제곱 항을 확인해 작성했다.
원문의 표·그래프 수치는 가져오지 않았다. 실제 시험 로그·측정치 검증이나 원문 전체 재검증은 아니다.
reason은 DoriLab 분류 규약이다. 논문이 대문자 코드를 지정한 것은 아니다.

## 설치

필수 새 파일은 `reason_coverage_v12.py` 하나다.
`~/dorilab-ai/DoriLab_SourceCurriculum_v02/`에 복사한다.
이미 실행한 `new_source_reason_v10.py`, v11 audit, 기존 dcurr 및 데이터가 같은 프로젝트에 있어야 한다.
ZIP의 tests를 프로젝트 기존 tests 위에 덮어쓸 필요는 없다. pip 설치 없음.

## 실행

```bash
cd ~/dorilab-ai/DoriLab_SourceCurriculum_v02
python reason_coverage_v12.py prepare --accept-ai-authored-training-candidates
python reason_coverage_v12.py train
python reason_coverage_v12.py evaluate
python reason_coverage_v12.py compare
explorer.exe data/reason_coverage_v12
```

첫 옵션은 AI 작성 후보를 이번 개발 학습에 사용하겠다는 명시적 선택이다.
사람의 공학적 승인·출처 사용 권한 승인으로 기록하지 않는다. 기존 승인 CSV를 변경하지 않는다.
새 `AI_REVIEW_KO.md`에 모든 질문·근거·가상 관측·정답과 분류 이유를 넣었다.

### prepare

현재 parent210 hash, v11 audit→e2 RUN_MANIFEST 연결, 프롬프트 hash,
기존 v10 frozen artifact와 e2 가중치, 새 정답의 현재 schema 적합성을 확인한다.
실제 `prompts.build_messages`의 학습/추론 입력이 동일한지 검사한다.

**repeat246.manifest.json 및 coverage246.manifest.json도 함께 만든다.**
기존 trainer의 sidecar 검사를 제거하지 않는다.
기존 210행의 메시지와 메타데이터를 수정하지 않고 두 군의 동일 슬롯에 넣는다.
새 정답 코드 5종이 실제 coverage export에 각각 2회 존재하는지도 확인한다.

### train

두 데이터의 preflight를 먼저 실행한 뒤 기존 `python -m dcurr.train`을 순차 호출한다.
현재 e2 adapter를 이어 학습하지 않는다. 동일 원본 revision에서 두 새 LoRA를 만든다.
입력·정답 토큰 수, 데이터/모델/로그 해시를 기록한다.
preflight의 전체 길이가 초과하면 멈춘다. 임의 truncate하지 않는다.

새 adapter 위치:
`runs/reason_coverage_v12_repeat_e2/`
`runs/reason_coverage_v12_coverage_e2/`

### evaluate

각 모델마다 NS10 24, 앞쪽 무관관측 회귀40, Contract20을 순차 실행한다.
총 새 생성은 168회다. 새 독립 사례 168개를 뜻하지 않는다.
NS10은 기존 v10의 baseline 시스템/사용자 메시지 해시와 정확히 대조한다.
reason 설명은 붙이지 않는다. 입력에 정답이 전달되면 메시지 훅에서 거부한다.
Contract 평가는 기존 부모 프로젝트 평가기를 쓰며 결과 사본을 새 폴더에 모은다.
기존 v10 점수/정답/모델 출력은 변경하지 않는다.

### compare

원래 e2의 v10 baseline과 새 두 군을 비교한다.
reason을 제외해 점수를 올리거나, 잘못된 ID를 비슷한 ID로 바꾸지 않는다.
NS10의 action, action+reason, 근거 정확 선택, 전체 계약, 잘못된 proposal 수용,
불필요한 개입을 따로 기록한다. before40와 Contract20 회귀도 함께 본다.
원래 e2는 24 action / 24 refs / 18 full-contract였다. 신규 결과는 실제 실행 후에만 존재한다.

## 결과 폴더

`~/dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/`

- comparison.json
- comparison_cases.jsonl
- RESULTS_KO.md
- AI_REVIEW_KO.md
- preflight.json
- repeat246.jsonl / coverage246.jsonl 및 각각의 manifest
- results/: 신규 모델의 원출력·summary·NS10 프롬프트 trace·Contract 결과 사본
- logs/: 사전검사·학습·평가 로그

스크립트는 기존 산출물을 덮어쓰지 않는다. 완료 receipt가 맞으면 검증 후 skip한다.
중간 파일이나 실패 로그만 있으면 중단한다. 이를 지우고 재시작하라고 자동 처리하지 않는다.
새 실험 outdir를 사용할 수 있으며 run 폴더와 Contract label도 해당 이름을 따른다.

## 해석 기준

1. coverage가 repeat보다 reason과 full contract를 개선하고 기존 action/참조/회귀를 유지하면
   해당 데이터 구성의 유용성을 지지한다. 성공이 사전에 보장된 것은 아니다.
2. 둘 다 비슷하게 개선되면 추가 학습 노출 효과가 포함됐다고 본다.
3. repeat보다 reason은 높지만 action 또는 근거 정확성이 낮아지면 자동 채택하지 않는다.
4. 이번 NS10 결과에 맞춰 계속 label을 바꾸지 않는다. 새 동결 평가에서 확인할 단계는 따로 둔다.

## 검증 범위

배포 파일에 CPU unittest와 로그가 포함된다.
테스트에는 실제 사용 가능한 v07 게이트, 기존 v10 메시지 훅/채점 함수를 사용한다.
**dcurr trainer / evaluator / tokenizer preflight와 transformers.set_seed는 임시 CPU 모의 코드다.**
모의 evaluator가 정답을 반환하는 부분은 입출력 연결 테스트 전용이며 실제 모델 성능이 아니다.
실제 Qwen weights, RTX GPU, 사용자 dcurr 실행은 제작 환경에서 수행하지 않았다.
`prepare`의 실제 API/스키마 검증과 `train/evaluate`의 사용자 GPU 실행이 남아 있다.
