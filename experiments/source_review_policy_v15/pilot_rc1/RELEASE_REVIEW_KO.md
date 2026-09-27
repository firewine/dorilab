# v15 첫 Qwen27 파일럿 후속 릴리스 검토본 — RC1

기준 문서: [기존 RELEASE_REVIEW_KO.md](../RELEASE_REVIEW_KO.md). 원래 v15 개정안과 218행 제안을 보존했다. 이번 후보는 **205행 = contract150 + legacy physics19 + 새 TRAIN36**이며 학습 사용 승인 완료는 **0행**이다. 정책 반영, 사례의 의미 검토, 학습 사용 승인, 공학적 승인을 별도로 기록했다. 이번 지시는 CPU 준비에 대한 권한이며 학습 승인이 아니다.

## 이번에 반영한 정책

[POLICY_v15_RC1.md](POLICY_v15_RC1.md)에 Action 우선, 적용 조건이 충족되는 구체 reason 우선, 일반 코드 fallback, 판단 근거/provenance 분리, 충분 reference 집합의 평가 metadata 관리, 정답/해설의 입력 분리를 반영했다. TIRS 세 rationale 방향은 그대로 유지했다. 이는 사용자 지시로 RC에 반영한 정책이지 v13의 과거 지침에 대한 소급 주장이 아니다.

AS_RUN의 계산 실행 결과로의 확대는 적용하지 않았다. RC reason 파일에서 AS_RUN 정의 문자열은 v13과 같다. 해당 논점이 있는 TIRS BASELINE family 전체가 보류됐다. 물리 시험에 대한 변경은 아래 두 건을 실제 질문/관측과 대조했으며 **AI 적용성 검토 후보**로만 남겼다.

| 사례 | 판단 근거 | 개별 승인 상태 |
|---|---|---|
| CASE-c51cdfeccd | 설치에 맞는 진공 구동 평가의 입력 질문이며 관측에 physical vacuum-powered motion data 부재가 명시됨 | AS_RUN 후보, 사람 검토/학습 사용 승인 없음 |
| CASE-6de39fe5d2 | 예정된 physical cold-vacuum retest와 승인된 설계를 실행 완료로 취급한 제안. 개정 하드웨어 실행 기록은 없음 | AS_RUN 후보, 사람 검토/학습 사용 승인 없음 |

CASE-c83a53985e의 기존 AS_RUN은 물리 재시험의 run identity/log/results 결손으로 유지한다. CASE-7e2ce553dd의 진동→진공 실증 확장에는 MODEL_SCOPE 후보를 유지한다. 이런 변경은 Action을 바꾸지 않으며 성능에 유리하도록 일반 reason 허용집합을 넓히지 않는다.

## 포함·보류와 후보 행수

[PILOT_TRAIN_MEMBERSHIP.json](PILOT_TRAIN_MEMBERSHIP.json)은 206행 상한 membership과 205행 선정 후보, 보류 13행을 모두 보존한다. 원본 행/label hash 및 parent218 파일 hash를 연결했다. 선정 후보도 모두 승인 대기다. 현재 실제 export 가능 행수는 0이다.

| 구성 | 상한 | 선정 후보 | 추가 보류 | 승인된 학습 행 |
|---|---:|---:|---:|---:|
| contract replay | 150 | 150 | 0 | 0 |
| legacy physics 고유 상태 | 20 | 19 | 1 | 0 |
| 새 TRAIN | 36 | 36 | 0 (별도로 family 12건 제외) | 0 |
| 합계 | 206 | 205 | 1 | 0 |

각 선정 membership의 데이터 반복 횟수는 1이다. legacy physics parent20에서 19상태를 선택했고, 새 TRAIN36은 관련 family9개다. 공학 상태 키는 19+36=55개이며 독립 관측 55건이라는 뜻이 아니다. contract150의 서로 다른 입력 내용 역시 의미적 독립성을 자동 보장하지 않는다. 학습 epoch/step 수는 아직 승인하지 않았다.

### 사용자 지시로 보류한 12건

| family / 원리 | 네 variant 사례 |
|---|---|
| SR13-TIRS-BASELINE | CASE-a7e82e186e, CASE-fe8f8cbdf7, CASE-acec2b7b89, CASE-d400650f82 |
| SR13-NEA-TRANSLATION | CASE-d5e287468e, CASE-6d4be78aae, CASE-cf088dcb3c, CASE-879754a57b |
| SR13-RHOBC-BOOT | CASE-13e084e68e, CASE-5616686acf, CASE-9d61b185f8, CASE-d029eccb5c |

### 추가 호환성 보류

`PHY-EE02-P01-A`: 자극 중 기능 변화가 기록됐는데 사후 baseline 복구를 근거로 susceptibility event가 없었다고 하는 제안이다. legacy target은 EVIDENCE_INTERPRETATION_ERROR다. 명시된 source 평가 절차(자극 중 기록을 전후 baseline 및 sweep timing과 함께 검토)를 무시했다는 METHOD_INTERPRETATION_ERROR 적용 가능성과 경계가 남는다. **확정 오류라고 단정하지 않고 잠정 충돌로 보류**했다. target과 messages는 재작성하지 않았다. 짝 B는 자극 중 관측과 사후 복구를 구분하는 적절한 제안이라 후보로 유지했다. pair 불균형(10쌍 중 한쪽 1건 보류)은 사용자가 확인해야 한다.

모든 후보에는 source/이용권/label·학습 사용 승인 대기가 남아 있다. 205행은 호환성 검토를 반영한 후보 크기이며 검토 완료 학습량이 아니다. 위 1건을 재포함하거나 추가 보류하면 다음 membership manifest에서 수와 분포를 다시 고정해야 한다.

### Action 분포 (모델 점수 아님)

| 구성 | CALL_TOOL | CHALLENGE | NO_ACTION_REQUIRED | PROPOSE_FINDING | REQUEST_EVIDENCE | 행수 |
|---|---:|---:|---:|---:|---:|---:|
| CONTRACT_REPLAY | 10 | 25 | 65 | 15 | 35 | 150 |
| UNIQUE_PHYSICS_STATE | 0 | 5 | 10 | 0 | 4 | 19 |
| NEW_TRAIN | 0 | 9 | 18 | 0 | 9 | 36 |
| 상한206 | 10 | 40 | 93 | 15 | 48 | 206 |
| 선정후보205 | 10 | 39 | 93 | 15 | 48 | 205 |

### reason 분포 (각 실제 입력 계약의 enum 유지)

| reason | 상한206 | 후보205 |
|---|---:|---:|
| AS_RUN_MISSING | 8 | 8 |
| BOUNDARY_CONDITION_UNRESOLVED | 3 | 3 |
| CONFIGURATION_MISMATCH | 12 | 12 |
| CONFIGURATION_SCOPE_UNRESOLVED | 2 | 2 |
| DURATION_INPUT_MISSING | 10 | 10 |
| EVIDENCE_CONTRADICTION | 8 | 8 |
| EVIDENCE_INTERPRETATION_ERROR | 4 | 3 |
| FORCE_LIMIT_BASIS_UNRESOLVED | 1 | 1 |
| MEASUREMENT_MAPPING_MISMATCH | 4 | 4 |
| METHOD_INTERPRETATION_ERROR | 1 | 1 |
| MODEL_SCOPE_EXCEEDED | 1 | 1 |
| MODE_SELECTION_MISMATCH | 1 | 1 |
| MONITORING_COVERAGE_INSUFFICIENT | 5 | 5 |
| NOT_APPLICABLE | 118 | 118 |
| PARAMETER_IDENTIFICATION_INSUFFICIENT | 1 | 1 |
| POWER_DISSIPATION_UNRESOLVED | 1 | 1 |
| PROBABILISTIC_ASSUMPTIONS_UNRESOLVED | 1 | 1 |
| REVISION_MISMATCH | 5 | 5 |
| SCOPE_ERROR | 10 | 10 |
| SUPPORTING_EVIDENCE_MISSING | 10 | 10 |

NOT_APPLICABLE은 reason 필드가 없는 행의 수다. 다른 legacy enum을 v15 enum으로 통일한 통계가 아니다. component별 Action/reason 분포는 membership JSON에 함께 있다.

## 실제 메시지의 계약 호환성

[CONTRACT_COMPATIBILITY.json](CONTRACT_COMPATIBILITY.json)과 [MODEL_INPUT_PREVIEWS.jsonl](MODEL_INPUT_PREVIEWS.jsonl)은 모델이 받게 될 system/user 내용을 보존한 CPU 미리보기다. assistant 정답을 합친 SFT export는 아니다. 상한206 중 보류 legacy 1건도 감사용 입력 미리보기를 남기되 candidate_selected=false로 표시했다.

- contract150은 기존 세 role별 system과 user를 그대로 보존했다. 기존 CALL_TOOL/PROPOSE_FINDING, claim/evidence 필드 유무와 reason enum도 해당 원래 계약을 유지한다.
- legacy physics20은 원래 system의 allowed-output 예시·reason 정의와 user의 reference_context/case_packet을 유지했다. 실제 system에 해당 target reason이 선언돼 있는지도 확인했다. v15에 없는 FORCE_LIMIT_BASIS_UNRESOLVED, PROBABILISTIC_ASSUMPTIONS_UNRESOLVED 등의 문자열만으로 충돌이라고 판정하지 않는다.
- 새 TRAIN36과 DEV16은 실제 system에 `DoriLab SourceReview v15 pilot RC1` 표제, Action/구체 reason 우선순위와 필드 안내를 넣었다. [RC prompt](prompts/direct_v15_pilot_rc1.txt)는 새 파일이며 기존 direct_v14는 바꾸지 않았다. 단일 CPU 작성안으로 모델을 돌려 prompt를 탐색하지 않았다.
- 따라서 계약 차이는 metadata에만 존재하지 않는다. 모델의 system 입력 내용에 있다. 기존 messages의 hash를 대조했고 legacy 입력 앞에 v15 system을 추가하지 않았다. 모델이 실제로 이 구분을 잘 따르는지는 미실행 상태라 주장하지 않는다.
- 후속 exporter/collator는 행마다 원래 system/user 및 별도 검토된 target을 보존해야 한다. 공통 system으로 덮거나 packing 중 대화 경계를 섞으면 이번 CPU 계약 검사를 무효화한다. 승인 후 이 경로의 검사까지 완료해야 학습할 수 있다.

### legacy physics 검토 목록

| 고유 상태 | reason/Action | 판정 |
|---|---|---|
| PHY-VBX1-P02-A | REQUEST_EVIDENCE / FORCE_LIMIT_BASIS_UNRESOLVED | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE02-P02-A | REQUEST_EVIDENCE / MONITORING_COVERAGE_INSUFFICIENT | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE02-P02-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P07-A | REQUEST_EVIDENCE / PROBABILISTIC_ASSUMPTIONS_UNRESOLVED | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE02-P01-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-TH01-P05-A | REQUEST_EVIDENCE / POWER_DISSIPATION_UNRESOLVED | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-TH01-P03-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P01-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-TH01-P03-A | CHALLENGE / PARAMETER_IDENTIFICATION_INSUFFICIENT | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-TH01-P02-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE03-P01-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P02-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-TH01-P05-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P07-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P03-B | NO_ACTION_REQUIRED / NOT_APPLICABLE | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE03-P01-A | CHALLENGE / MONITORING_COVERAGE_INSUFFICIENT | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P01-A | CHALLENGE / BOUNDARY_CONDITION_UNRESOLVED | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-EE02-P01-A | CHALLENGE / EVIDENCE_INTERPRETATION_ERROR | 잠정 충돌, 보류 |
| PHY-TH01-P02-A | CHALLENGE / BOUNDARY_CONDITION_UNRESOLVED | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |
| PHY-VBX1-P03-A | CHALLENGE / MODE_SELECTION_MISMATCH | 기존 입력 계약 아래 차단할 충돌 미발견; 사용 승인 대기 |

각 state의 질문·reason 해석 근거는 compatibility JSON의 semantic_review에 있다. 이 검토는 AI CPU 내용 대조이며 legacy 원문을 모두 새로 사람 검토했다는 기록이 아니다.

## reference 검사 보완

[reference_contract.py](reference_contract.py)는 selected==all_provided를 독립 실패 조건으로 쓰지 않는다. 제공된 ID의 부분집합이고, 중복이 없고, 승인된 충분 집합과 정확히 같으면 통과한다. 순서는 무시한다. 무관한 ID가 들어간 all-provided 출력은 충분 집합에 없으므로 실패한다.

CPU fixtures는 평가 사례 정답 복사가 아닌 S-demo/O-demo/NOISE 예제로 검사했다.

| 경계 | 결과 |
|---|---|
| 제공 전체={S,O}, 승인 충분 집합={S,O}, 선택 전체 | PASS |
| 제공 전체={S,O,NOISE}, 승인 충분 집합={S,O}, 선택 전체 | REJECT |
| 승인 관측 충분 집합={O}, 선택 {O} | PASS |
| 미제공·중복·불충분 부분집합·빈 집합 | REJECT |
| approved=false인 AI 후보 metadata | 미평가(None), 공식 점수 생성 안 함 |

기존 v13/v14 scorer와 점수는 보존했다. 새 DEV와 TRAIN의 충분 집합은 AI 검토 후보이며 아직 approved=false다. 이번 코드와 검사는 계약 경계의 CPU 검증이며 기존 모델 출력 재채점이 아니다.

## 비교용 원문 확보

출판사 landing/PDF redirect는 403/429였지만, 정상적인 공개 asset URL에서 두 PDF를 HTTP 200으로 받았다. 로그인·차단 우회·snippet 대체는 사용하지 않았다. 과거 SOURCE_UNAVAILABLE 기록은 그대로 두고 이번 새 확보 결과를 [SOURCE_AUDIT_RC1.json](sources/SOURCE_AUDIT_RC1.json)에 기록했다.

| 원문 | 확보 상태 | PDF SHA256 |
|---|---|---|
| [CANYVAL 논문](https://mdpi-res.com/d_attachment/aerospace/aerospace-08-00150/article_deploy/aerospace-08-00150.pdf) | 25쪽 PDF, 4,273,373 bytes | 701d6dd4de8b37c9ad4e585984d79b12e40d4766933d8c2cf92fa352abcb3244 |
| [PROBA-V 계측 논문](https://mdpi-res.com/d_attachment/electronics/electronics-13-01822/article_deploy/electronics-13-01822.pdf) | 15쪽 PDF, 2,093,262 bytes | 7b093f35ebb98307d97e413ae1ca9fc9c2bd102c666ec05acbcca5aa6ebba284 |

본문에서 CANYVAL §5.1/§6의 HRM 구속 표현과 주파수 변화, PROBA-V §2.4/§3.1/§3.2/§4.1/§5의 동기 계측·test mode·복구 중 오류 획득 한계를 대조했다. 특히 source-specific 방법 정의에 사용할 부분은 CANYVAL PDF18쪽과 PROBA-V PDF6쪽이다. 실제 PDF 제목·DOI와 본문을 확인했고, 각 텍스트 page hash 및 anchor를 저장했다. PDF metadata 제목 하나로 동일성을 판정하지 않았다.

두 원문이 확보되어 대체 출처 2개를 추가하지 않았다. 첫 페이지 CC BY 표시는 provenance에 기록했지만 기관의 데이터 사용 승인으로 승격하지 않았다. 그림/표 수치를 새 사례로 전사하지 않았으며 이번 시각 검토 완료도 주장하지 않는다. 기존 source 원리와 합성 사례 사실·수치는 구분한다.

## 별도 DEV16 후보와 source 의존성

[dev16/INPUTS.jsonl](dev16/INPUTS.jsonl), [후보 정답](dev16/GOLD_AI_CANDIDATE.jsonl), [metadata](dev16/METADATA.jsonl)는 **새 RC 후보**다. 원래 DEV16을 덮어쓰지 않고 parent case/gold hash를 연결했다. 원래 CANYVAL/PROBA-V 출처만 사용하며 4 family × 4 variant = 16건 범위를 유지한다. 두 family의 방법 대조를 구체화한 8건과 관측 충분 대조 8건이다. 새 버전 ID를 부여했으므로 과거 실행 원본 입력으로 표시하지 않는다.

| 후보 묶음 | 건수 | source의 실제 역할 |
|---|---:|---|
| CANYVAL HRM 표현 재현 | 4 | 원문의 strongly bounded/direct contact와 간접 wire connection(edge-to-edge 등) 정의를 합성 geometry 기록과 대조. 원문 정의 없이는 논문 고유 명명/재현 여부를 결정할 수 없음 |
| CANYVAL 원인 분별 대조 | 4 | 합성 관측이 직접 지지하는 결론. 관측만의 충분 집합 허용 |
| PROBA-V 시간 귀속 대조 | 4 | per-event/time alignment 결손·준비 상태가 관측에 명시됨. 관측 충분 집합 허용 |
| PROBA-V static/dynamic 모드 재현 | 4 | 원문의 static write-wait-read와 dynamic 반복 read/write 정의 및 관찰 경로를 사용. 단순 최종 image와 방법 재현 자료를 구분 |

방법 의존 8건은 관측에서 source-specific 정의를 알려주고 source citation만 강제하는 방식으로 만들지 않았다. 관측에는 합성 구현/기록만 두고 mode/HRM 정의는 제공 source fact에 둔다. source-removal 판단의 이유는 metadata에 있다. **AI 저자의 반사실적 내용 검토**이며 모델 ablation 또는 독립 사람 검증은 아니다. 검토자가 관측만으로 충분하다고 판단하면 필수 source를 억지로 유지하지 말고 다음 동결본에서 사례/충분 집합을 재검토해야 한다.

PROBA-V 시간 귀속 CHALLENGE는 구체 monitoring 코드 후보를 제안했다. 원문 확보 후 같은 정책을 적용한 AI label 변경이며 어떤 새 모델 출력도 보지 않았다. 새 후보 Action은 CHALLENGE4 / REQUEST_EVIDENCE4 / NO_ACTION_REQUIRED8이다. 공학적 합격 기준이나 원문 수치를 새로 발명하지 않았다.

[PRE_OUTPUT_FREEZE.json](dev16/PRE_OUTPUT_FREEZE.json)에 입력·후보 정답·reference 집합·prompt·source 감사 hash를 다음 모델 출력 전에 동결했다. 상태는 AI_CANDIDATE_CONTENT_FROZEN이며 학습/평가 승인 완료를 뜻하지 않는다. 사람 검토로 바뀌면 실행 전에 새 freeze를 만들고 지금 기록을 보존해야 한다.

공개 TRAIN48과 실제 legacy repeat246 source/program metadata에 대해 후보 DEV16의 source/program/family 교집합이 없음을 확인했다. [split audit](dev16/SPLIT_AUDIT.json)은 이 범위를 명시한다. 외부 corpus·미위치 RAG·평가자 관리 자료에 대한 전체 독립성 감사는 미완료이며 RESERVED/EvaluatorOnly는 열지 않았다. DEV16도 알려진 출처에서 만든 개발 후보이지 독립 일반화 평가가 아니다. DEV8은 학습·이번 후보·추가 추론에서 제외했다.

## 사용자가 확인해야 할 실제 승인 항목

1. **정책 반영 확인**: RC1의 구체 우선/fallback, provenance 분리, all-provided reference 경계를 의도한 정책으로 사용할지 확인. AS_RUN 계산 확대는 이번 범위에서 제외됨.
2. **개별 사례 검토**: TRAIN36의 Action/reason/충분 근거와 TIRS rationale 3건, 물리 AS_RUN 후보 2건을 hash에 연결해 실제 검토. legacy 잠정 충돌 1건을 계속 보류할지 결정. DEV16 방법 의존성·정답·reference 집합도 실제 검토.
3. **학습자료 사용 승인**: source 내용/이용권, 기존 corpus source/program 중복 감사, legacy messages 유지, 205행 포함·반복·분포를 검토한 뒤 별도 실험용 사용 승인. 현재는 전부 미승인이다.
4. **실행 계획 승인**: 고정 Qwen27 단일 LoRA 구성, export 경로 승인 검사, 향후 GPU 시간/자원 사용은 별도 승인. 이번 준비 요청을 실행 승인으로 사용하지 않는다.
5. **공학적 승인**: 모델·label·학습 승인과 독립적인 프로젝트 권한. 이 산출물로 시험 실행·설계 수락·finding closure를 승인하지 않는다.

사람 검토자 이름/시각이나 human_review_performed=true를 만들어 넣지 않았다. PILOT_APPROVAL_BOUNDARIES.json은 미승인 경계 상태표이며 학습 승인서가 아니다. 기존 exporter의 승인 검사도 호출·우회하지 않았다.

## 승인 후 단일 LoRA 비교 계획

- 모델은 Qwen/Qwen3.8-27B, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Transformers commit `002e1edf5b5198488297f401dd853056b6521d02`를 유지한다. 별도 모델 비교·추가 adapter·hyperparameter 탐색을 제안하지 않는다.
- 사례/사용 승인이 끝난 membership과 native 메시지 계약을 동결한다. 원래 승인 gate를 보존한 별도 exporter에서만 SFT를 만들고, legacy system 보존과 응답-only mask/EOS·대화 경계를 확인한다. 이 단계는 아직 실행하지 않았다.
- adapter 하나의 rank/alpha/dropout, target modules, optimizer/LR, batch/accumulation, step/epoch를 결과 관측 전에 한 구성으로 정해 승인받는다. 계산 run AS_RUN 정책은 적용하지 않는다. 훈련 데이터량을 맞추려고 보류 family나 DEV를 추가하지 않는다.
- 승인된 동일 DEV16 입력·prompt·tokenizer·reference metadata로 고정 base와 학습 후 adapter를 한 번씩 비교하는 안이다. BF16/SDPA, greedy, seed42, 응답384/전체2048 조건을 계획 기준으로 유지한다. 새 입력 token 길이는 **후속 실행 승인 단계에서** 확인하며 초과하면 중단하고 별도 결정한다. 이번에는 tokenizer나 GPU 사전검사를 실행하지 않았다.
- DEV8을 재추론하지 않는다. legacy 회귀는 해당 기존 입력 계약으로 별도 구분한다. JSON, 기존 check_answer 의미의 schema 유효와 별도 필드 계약, parsed/contract-qualified Action, 평가 가능한 reason/reference/strict, 사례별 회귀, 시간/token을 분리한다. 새 정책의 base/adapter를 같은 조건으로 비교하며 과거 v13/v14 점수를 새 정책으로 바꿔 개선율을 만들지 않는다.
- 실제 실행·실패 산출물은 새 폴더에 저장한다. 이번 지시로 추가 추론·학습·Pod 조작을 시작하지 않는다.

## CPU 결과와 산출물

[CPU_VALIDATION_RC1.json](CPU_VALIDATION_RC1.json): **17개 검사 통과**. family 전체 보류, 206→205 membership/분포, 원본 hash, 실제 메시지 계약과 legacy 보존, 입력/정답/해설 분리, AS_RUN 정의 유지, TIRS 방향 유지, all-provided reference 양쪽 경계, DEV source/split/hash 동결을 검사했다. PASS는 CPU 구조 검사이며 모델 성능이나 사람 정답 승인이 아니다.

기존 추적 파일 347개(v13/v14 및 최초 v15 포함)를 보존했다. 비교용 원문 추출은 별도 `/tmp/sr15_policy_cpu`의 pypdf 6.1.0으로 수행했다. 가중치·tokenizer·CUDA 환경을 준비하거나 실행하지 않았다. 추가 추론, LoRA, ledger, constrained decoding, 반복 prompt 탐색, Pod 잠금 변경과 STOP도 실행하지 않았다.

CPU 검사 재현:

```sh
python experiments/source_review_policy_v15/pilot_rc1/test_cpu.py
```

build 스크립트는 초안 생성 이력으로 보존한다. 이미 동결된 DEV16 위에 재실행해 내용을 덮지 말고 변경 시 별도 revision 폴더를 사용한다.

## 새 TRAIN36 선정 후보 목록

- F-d0190c27bc: CASE-4ad9ed95e2, CASE-79c814ab47, CASE-424419171a, CASE-e00c7fe02d
- F-9f5d1a8add: CASE-589fb4eb03, CASE-199314f362, CASE-555ca15e0e, CASE-a6135d12df
- F-bffe89a7f0: CASE-88b5d13600, CASE-4196d4ddc2, CASE-9c036b2503, CASE-1bdc9a0a66
- F-f10ef0e47e: CASE-7e2ce553dd, CASE-ed9b08cbf4, CASE-c51cdfeccd, CASE-493773aa90
- F-a23c98c073: CASE-02caf2a304, CASE-2f88f50fa1, CASE-07dbc2c8c4, CASE-61ef0e9728
- F-94b82e4196: CASE-6de39fe5d2, CASE-332bc07aa7, CASE-c83a53985e, CASE-48f4545a71
- F-053c3d8988: CASE-54a9474954, CASE-d3f978cae1, CASE-08ee9d45a5, CASE-d723874b9f
- F-c84e3089cd: CASE-9df6407dbd, CASE-0ca276ca1e, CASE-f235c491ee, CASE-703b0ad936
- F-cdd6fc4b87: CASE-8822d424f6, CASE-bbdb74ad02, CASE-185d4a0c91, CASE-b94839f32b

## DEV16 parent → RC 후보 대응

| 원본 case | 새 RC case | variant | 역할 |
|---|---|---:|---|
| CASE-870c379fa0 | CASE-RC1-a12e0ea391 | 0 | METHOD_DEPENDENT_REVISION |
| CASE-e7386f7ddf | CASE-RC1-2969416c37 | 1 | METHOD_DEPENDENT_REVISION |
| CASE-df8ed0a5e6 | CASE-RC1-a14b803063 | 2 | METHOD_DEPENDENT_REVISION |
| CASE-4e774a1974 | CASE-RC1-4c1f22081f | 3 | METHOD_DEPENDENT_REVISION |
| CASE-1800223793 | CASE-RC1-1a26698cec | 0 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-0bf2f59697 | CASE-RC1-715e076e01 | 1 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-a00c710b3f | CASE-RC1-1cdfbd536d | 2 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-1fb4ec74a4 | CASE-RC1-976b75a909 | 3 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-fc0864226a | CASE-RC1-47b8196220 | 0 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-d05caa3edc | CASE-RC1-1c1f745956 | 1 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-71262c17f4 | CASE-RC1-a89c9fdaf2 | 2 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-15d397cc74 | CASE-RC1-fcba98f7e7 | 3 | OBSERVATION_SUFFICIENT_CONTROL |
| CASE-c45ab2fec7 | CASE-RC1-a006de0cbd | 0 | METHOD_DEPENDENT_REVISION |
| CASE-2346b4ee7f | CASE-RC1-62f858f89b | 1 | METHOD_DEPENDENT_REVISION |
| CASE-82a92a1c28 | CASE-RC1-3613224989 | 2 | METHOD_DEPENDENT_REVISION |
| CASE-e8a8b979ca | CASE-RC1-cf94ad1f14 | 3 | METHOD_DEPENDENT_REVISION |
