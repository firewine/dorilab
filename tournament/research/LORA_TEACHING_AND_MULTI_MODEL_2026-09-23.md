# DoriLab 학습 방식·다중 모델 검토 분석

기준일: 2026-09-23. 기존 학습·평가 기록과 설치 소스, 2025~2026 논문 및 공식 기술 문서를 확인했다. 새 학습, baseline 재실행, 데이터·정답·환경 변경은 하지 않았다. 아래에서 관측 사실, 원인 가설, 제안 실험을 구분한다.

## 판단

LoRA 자체가 잘못됐다는 증거는 없다. 이번 다섯 모델은 모두 adapter 없는 baseline이므로 Markdown JSON 출력 실패를 LoRA의 부작용으로 해석할 수 없다. 기존 E4B LoRA는 strict 42/84 → 73/84, Action 74/84 → 83/84, reference exact 40/64 → 64/64로 개선됐다. 개선 33건·회귀 2건이다. 이 두 회귀만으로 광범위한 catastrophic forgetting이라고 확정할 수 없다.

현재 우선순위는 공통 계약을 안정시키고, 새로운 출처의 판단 경계 사례를 검토해 학습 신호를 개선하고, 독립 검토를 선택적으로 붙이는 것이다. 분야별 모델을 여러 개 만드는 것은 데이터가 충분해진 뒤 판단한다.

## 1. 로컬 자료에서 확인한 원인과 한계

### 데이터 규모와 다양성

`repeat246.manifest.json`: 246행 중 contract 150행, physics 96행이며, physics는 고유 합성 상태 20개/관련 pair 10개, source 4개를 반복한다. 246개의 독립적인 공학 문제를 가르친 것이 아니다.

실제 assistant 답변의 Action 분포는 NO_ACTION_REQUIRED 113, REQUEST_EVIDENCE 57, CHALLENGE 51, PROPOSE_FINDING 15, CALL_TOOL 10이다. 이 분포만으로 정상 판정 편향의 원인이라고 단정할 수는 없다. 정상 사례도 유지해야 하며 무조건 CHALLENGE를 늘리는 것으로 해결하지 않는다.

평가 expected.reason에는 있으나 repeat246의 assistant 정답 reason에는 없는 코드는 다음 9개다. 시스템 프롬프트 정의에 나올 수 있으므로 모델이 전혀 본 적 없다는 뜻은 아니다.

- MEASUREMENT_MAPPING_MISMATCH
- EXPOSURE_METADATA_UNRESOLVED
- CONFIGURATION_SCOPE_UNRESOLVED
- MODAL_INPUTS_MISSING
- METHOD_INTERPRETATION_ERROR
- STABILITY_UNRESOLVED
- TEST_ARTIFACT_UNMODELED
- MODEL_SCOPE_EXCEEDED
- RADIOMETRIC_EQUIVALENCE_UNRESOLVED

E4B 회귀 두 사례는 METHOD_INTERPRETATION_ERROR → EVIDENCE_INTERPRETATION_ERROR, MODEL_SCOPE_EXCEEDED → FORCE_LIMIT_BASIS_UNRESOLVED다. 올바른 두 코드 모두 학습 정답에서 빠졌고 바뀐 코드는 학습 정답에 있다. 이는 학습 분포에 따른 분류 경계 이동 가설을 지지하지만 인과 확정은 아니다.

기존 coverage246은 고유 공학 상태 56개로 늘렸지만 2B의 NS10 strict는 19/24로 같고 before40 strict는 repeat 36/40에서 coverage 34/40으로 낮았다. 따라서 이미 끝난 coverage 실험을 반복하거나 reason 이름만 골고루 추가하는 것으로 해결됐다고 주장하지 않는다. 새 출처·검토된 근거·상반된 판단 경계가 필요하다.

### 학습 구현

`dorilab_gemma/modeling.py`는 native chat template의 학습/추론 prefix와 token 경계를 검사하고, 사용자/시스템 토큰을 -100으로 마스킹하며, 답변과 종료 토큰에만 loss를 준다. selected logits의 위치는 다음 토큰 label에 대응한다. 입력은 잘리지 않고 초과 시 실패한다.

기존 manifest는 유한한 nonzero LoRA gradient, 34,881,536 trainable parameters, attention+MLP targets를 기록한다. train loss 0.0425는 기록돼 있지만 이것이 공학 판단의 정확성이나 일반화를 보장하지 않는다. 이번 확인은 소스·기존 실행 기록 검토이며 대형 모델로 수치 재실험한 것은 아니다. 명백한 loss shift/masking 오류는 발견하지 못했다.

Assistant-only loss는 현재 [TRL SFT 공식 문서](https://huggingface.co/docs/trl/sft_trainer)에서도 지원하는 방식이다. 이를 full-sequence loss로 바꾸는 것이 우선 해결책이라는 근거는 없다.

### 앞으로의 모델 구조별 주의점

기존 E4B trainer는 E4B 42층 전용이다. 26B에 그대로 적용하는 코드는 아니다. 현재 설치된 Gemma4TextExperts는 gate_up_proj/down_proj를 nn.Parameter로 보관한다. nn.Linear만 고르는 방식으로 옮기면 routed expert를 놓칠 수 있다. Qwen3_5의 GatedDeltaNet은 in_proj_qkv/z/b/a와 out_proj를 사용하므로 q_proj/v_proj라는 이름만 찾으면 이 경로가 빠진다.

학습 전에 target 목록·각 영역의 trainable 수·gradient를 검증해야 한다. MoE parameter 대상 지원은 [PEFT LoRA 공식 문서](https://huggingface.co/docs/peft/v0.21.0/package_reference/lora)에 명시돼 있다. 모든 파라미터를 무차별 학습하라는 뜻은 아니며 vision/audio/embedding/router 처리도 명시해야 한다. 이 문제는 다음 학습에서 방지할 위험이지, 아직 학습하지 않은 26B/27B baseline 오류의 원인이 아니다.

## 2. 최신 연구가 시사하는 개선 방향

| 자료 | 확인한 내용 | DoriLab 적용과 한계 |
|---|---|---|
| [LoRA Without Regret](https://thinkingmachines.ai/blog/lora/), Thinking Machines, 2025-09 | 조사한 소·중규모 post-training 조건에서 적절한 LoRA가 full FT와 비슷한 학습 성능을 보였으며 MLP/MoE 포함 target 범위가 중요했다 | LoRA를 버리거나 rank/LR만 올리기보다 target과 데이터부터 검증. 연구의 loss 중심 결과를 DoriLab 안전성 증명으로 확대하지 않는다 |
| [Rethinking Generalization in Reasoning SFT](https://arxiv.org/abs/2604.06628), COLM 2026, 2026-08 개정 | SFT 일반화는 데이터 구조·품질·최적화·기본 모델 역량에 따라 달랐고, 검증된 long-CoT에서 이득을 관찰 | “SFT는 암기만 한다”는 결론은 지나치다. 본 연구는 주로 수학 long-CoT이며 DoriLab short JSON에 긴 사고문이나 epoch를 그대로 적용하지 않는다 |
| [Mitigating Forgetting in Low Rank Adaptation](https://arxiv.org/abs/2512.17720), 2025-12 프리프린트 | LaLoRA는 LoRA 가중치 변화에 정규화를 적용해 학습과 보존의 균형을 연구 | 우선 검토된 보존 사례를 학습에 섞고 회귀를 측정. 추가 복잡성이 있는 LaLoRA는 첫 선택이 아니다 |
| [On-Policy Distillation](https://thinkingmachines.ai/blog/on-policy-distillation/), Thinking Machines, 2025-10 | 학생이 실제로 생성하는 경로에서 교사 피드백을 받는 학습을 제안 | 새로운 training 전용 문제에서 실제 오답을 수집하고 검토된 수정 예제를 만들 가치. 단순 오답 교정 SFT를 논문의 token-level on-policy distillation과 동일하다고 부르지 않는다 |
| [JSONSchemaBench](https://arxiv.org/abs/2501.10868), 2025 | constrained decoding을 구조 준수·지원 범위·생성 품질로 나눠 평가 | 문법은 decoder와 validator가 담당하게 하되 Action 의미 정확성은 별도로 측정 |
| [Debate or Vote](https://arxiv.org/abs/2508.17536), NeurIPS 2025 Spotlight | 연구한 7개 benchmark에서 상당한 MAD 이득을 독립 표결이 설명 | 긴 토론을 기본값으로 삼지 말고 독립 검토와 같은 계산 예산으로 비교 |
| [Talk Isn't Always Cheap](https://arxiv.org/abs/2509.05396), ICML MAS Workshop 2025 | 다른 에이전트의 잘못된 주장으로 정답을 오답으로 바꾸는 현상을 관찰 | 먼저 답변을 독립 확정하고 변경 시 원문 근거를 요구. 합의를 승인으로 사용하지 않는다 |
| [Multi-Agent Reasoning Improves Compute Efficiency](https://arxiv.org/abs/2605.01566), 2026-05 프리프린트 | MMLU-Pro/BBH의 동일 계산 예산 비교에서 debate/MoA의 효율 개선을 관찰 | 토론이 항상 손해인 것도 아니다. 우리 데이터에서 오수용·지연·검토부담을 같이 확인해야 한다 |

위 자료는 2026-09-23 현재 확인한 관련 연구의 선별이며 전 분야의 포괄적인 최신성 보증은 아니다. 수학/일반 추론 benchmark의 효과를 공학 승인 업무에 바로 전이시키지 않는다.

## 3. 추천하는 티칭 변경

1. **출력 계약과 의미 판단의 성능을 분리한다.** 제품용 생성에는 JSON Schema constrained decoding을 검토한다. action/reason enum, 입력에 주어진 ref/request ID, 필수 필드를 제한하되 정답의 올바른 ref 선택 집합을 decoder에 주지 않는다. 기존 baseline은 그대로 유지하고 새로운 serving 조건으로 별도 기록한다. 문법 제약으로 의미 오류까지 해결되지는 않는다. [XGrammar 공식 구현 설명](https://github.com/mlc-ai/xgrammar/blob/main/docs/start/constrained_decoding.md).
2. **정답 코드 외에 검증 가능한 짧은 판단 근거를 데이터 제작 단계에서 관리한다.** review target, 원문 span, 관측 사실, 누락 선행조건, 제안에 대한 반박 관계를 구조화한다. 장문의 자유 사고문을 제품 JSON에 붙이지 않는다. 보조 추출 학습을 할 경우 별도 명시된 내부 계약을 정의한다.
3. **경계가 다른 사례를 짝으로 검토한다.** 동일 물리 사실에서 “계산을 수용하라/기각하라”는 제안이 바뀌는 경우, 관측된 이상과 자료 부족의 차이, 시험 후 회복과 시험 중 이상 부재의 차이를 가르친다. 정상 판정/자료 요청/반박 세 상태를 함께 포함해 과잉 반박을 막는다. 기존 frozen 84건의 문구·정답을 학습에 옮기지 않고 새로운 출처와 시나리오를 사용한다.
4. **공학 근거로 검토한 학생 오답을 교육 자료로 만든다.** 두 교사 모델은 서로의 답을 보기 전에 독립 판단하고, 불일치 사례만 원문·도구·사람으로 검토한다. agreement만으로 TRAINABLE 승격하지 않는다. DPO는 신뢰할 수 있는 chosen/rejected 쌍이 확보된 후 별도 후보이며, 첫 SFT와 동시에 바꾸지 않는다. [TRL DPO 공식 문서](https://huggingface.co/docs/trl/dpo_trainer).
5. **평가 분리를 먼저 만든다.** 기존 84건은 회귀로 유지하고 source/program/pair 단위로 새 검증·독립 평가를 분리한다. 같은 출처의 재표현을 다른 split에 넣지 않는다. 반복 LR/epoch 탐색 대신 검토된 데이터와 설정을 고정한 비교 한 번을 한다. 독립 평가 정답은 학습·검색 색인·프롬프트 개발에 쓰지 않는다.

## 4. 두세 모델 토론의 실제 가능성

기존 저장 출력의 내부 JSON Action을 비교했다. 공식 scoring 변경 없이 오류 상관을 진단한 결과다.

| 조합 | 같은 Action | 다른 Action | 둘 다 Action 오답 | 둘 중 하나 이상 정답 |
|---|---:|---:|---:|---:|
| Qwen27 + Gemma26 | 71 | 13 | 0 | 84 |
| Qwen9 + Gemma26 | 73 | 11 | 4 | 80 |
| Qwen27 + Qwen9 | 77 | 7 | 1 | 83 |

이는 정답을 알고 계산한 사후 upper bound다. “ensemble 84/84” 또는 실제 adjudicator 성능이 아니다. Gemma26의 원본 형식 실패를 포함해 제품 계약 문제도 남는다. Action이 맞아도 reason/ref는 틀릴 수 있고, 개발 데이터이므로 새 문제에서 오류 중복이 없으리라는 보장도 없다.

그럼에도 Qwen27+Gemma26는 Qwen 두 개보다 판단 오류를 상호 검토할 근거가 있다. 반면 Qwen9+Qwen27+Mistral을 다수결하면 PHY-VBX1-P04-A에서 셋 모두 잘못된 정상 판정이므로 해결되지 않는다.

추천 절차는 `Scope Gate → 분야별 근거 패킷 → 독립 검토 A/B → 구조 검증 및 불일치 비교 → 필요할 때 원문 근거로 1회 재검토 → 미해결 사항과 함께 Human Review`다. 제3 모델은 모든 요청에 호출하지 않고 불일치 정리 또는 별도 수치 검증 결과 해석에 제한한다. 합의를 강제하지 않는다. 모델 confidence 자체는 교정된 확률이 아니므로 단독 라우팅 기준으로 삼지 않는다. 고위험 사례에서는 두 모델이 같은 답이라도 근거 검증과 사람 확인을 생략하지 않는다.

## 5. 시간과 GPU 비용

동일 서버의 기존 84건 생성 기록이다. 입력은 짧은 frozen packet이고 토론 문맥·RAG·도구·로딩 시간은 포함하지 않는다.

| 모델 | 평균 초/건 | p95 초/건 (nearest rank) | 로딩 직후 allocated GiB |
|---|---:|---:|---:|
| Qwen9 | 1.42 | 2.05 | 17.53 |
| Gemma26 | 2.41 | 3.78 | 48.08 |
| Qwen27 | 3.41 | 5.22 | 50.96 |

Qwen27+Gemma26 독립 1회씩의 생성 시간 합은 약 5.82초다. 같은 길이라고 가정하면 각각 2회씩 생성할 때 약 11.63초이며, 판정 모델과 길어진 입력·출력은 추가된다. 이는 단순 합산 추정이고 실제 토론 지연 측정이 아니다. 별도 GPU에서 병렬 처리하면 다를 수 있지만 현재 한 GPU에 그대로 적용할 수 없다.

두 큰 모델은 로딩만 합쳐 99.03 GiB로 현재 가용 총량 약 94.97 GiB를 넘는다. KV cache 없이도 함께 올리기 어렵다. Qwen9+Gemma26의 로딩 합은 65.60 GiB로 메모리 여유는 있으나 동시 처리 속도와 토론 효과는 미측정이다. Qwen27+Gemma26+Qwen9는 약 116.56 GiB다.

BF16 모델 교체 로딩은 요청별 비용이 추가된다. 기존 load_seconds에는 다운로드가 포함돼 있어 hot-swap 시간으로 재사용하지 않는다. 양자화·CPU offload·추가 GPU는 다른 조건의 검증이 필요하며 아직 변경하지 않았다. 두 큰 모델은 현재 서버에서 오프라인 일괄 독립 검토·데이터 제작에 먼저 쓰는 편이 현실적이다. 원문에 근거한 검토 결과를 단일 specialist에 증류하면 토론 비용을 교육 단계에서 지불하고 제품 추론 비용을 낮출 수 있다.

## 6. 공학 분야별로 어떻게 나눌 것인가

데이터와 retrieval은 열/구조·진동/전기·EMC·방사선/시스템 검증으로 구분하되, 처음부터 각 분야 모델을 따로 훈련하지 않는 것을 제안한다. 현재 20개의 고유 공학 상태를 더 쪼개면 분야별 판단 경계를 학습할 근거가 더 작아진다.

공통 학습은 Action 계약, 사실/제안 구분, evidence/ref 연결, missing/conflicting evidence, tool-call, human approval boundary를 맡긴다. 분야별 packet은 관련 원문·적용 범위·관측치·전문 용어·수치 도구를 제공한다. 문서 최신 revision이나 프로젝트 형상을 모델 가중치에 암기시키지 않는다.

독립 평가에서 특정 분야의 지속적인 간섭이 관측되고 충분한 검토 데이터가 모이면 같은 base의 분야별 adapter를 Model Router로 선택할 수 있다. PEFT는 [여러 adapter 및 hotswap](https://huggingface.co/docs/peft/main/package_reference/hotswap)을 지원하지만 adapter 종류·target·runtime별 호환성은 확인해야 한다. 같은 base의 여러 adapter는 완전히 독립된 모델이 아니므로 오류 독립성을 가정하지 않는다. 동일 adapter를 열→진동→전기로 계속 덮어쓰는 순차 학습보다 버전이 분리된 비교가 낫다.

## 권고하는 다음 단계

기존 후보 두 개는 유지하되, Gemma26의 84건 중 오수용 0이라는 결과만으로 최종 우위를 확정하지 않는다. 먼저 source가 분리된 데이터와 판단 경계를 검토하고 architecture별 LoRA target 및 loss 마스킹 검사를 학습 전 조건으로 둔다. 기존 repeat246은 재현 기준으로 보존한다. 새로운 데이터와 decoding 조건은 별도 버전으로 관리하며, 이미 끝난 실험을 덮어쓰지 않는다.

실험은 하나의 모델에서 SFT·DPO·새 decoder·토론을 한꺼번에 바꾸지 않는다. 1) 계약 준수, 2) 학습 효과, 3) 독립 검토 효과를 분리해 원인을 판단한다. 새 학습 실행과 데이터 변경은 아직 하지 않았으며, 이전에 요청한 사용자 확인 전 단계다.

## 추가 검토: 새 논문에서 정답을 모르는 문제와 과적합

사용자 지적에 따라 불일치 검토의 역할을 명확히 제한한다. 불일치 자체에는 정답 정보가 없으며, 제3 LLM도 독립적인 진실 판별기가 아니다. 앞의 두 모델 중 하나가 맞았다는 수치는 gold를 이용한 사후 분석이다. 합의한 Action 71건이 이 데이터에서 맞았어도 다른 source의 정확성을 보증하지 않는다.

로컬 source 분포를 추가 확인했다. before40의 40건은 TH-01(16), VB-X1(16), EE-02(4), EE-03(4)로, repeat246의 source ID 네 개와 겹친다. 이는 source-overlap이며 모든 평가 행이 학습에 그대로 들어갔다는 주장과는 다르다. NS10은 RTG4/MRO/CM2의 다른 source에서 각 8건이지만 이미 오류 분석과 개발 의사결정에 사용돼 sealed test가 아니다. 따라서 현재 수치로 새 논문에 대한 일반화를 확정할 수 없다.

NS10 authoring에는 AI 생성 및 human_review_performed=false가 기록돼 있다. 정답은 고정된 개발 기준으로 유지하지만 공학 전문가가 확정한 보편적인 진실과 같다고 가정하지 않는다. 판단 경계의 모호성과 모델 오류를 구분하려면 모델 출력을 보기 전에 원문 기반 독립 검토와 불일치 adjudication이 필요하다. 불명확한 사례는 임의 단일 정답으로 강제하지 않고 별도 검토 상태로 둔다. 기존 gold는 이 분석 과정에서 수정하지 않는다.

새 논문 판단은 세 수준으로 나눈다.

1. **원문 충실성:** 인용 span/표/수식이 실제 존재하는지, 수치·단위·부호·조건을 정확히 옮겼는지. 원문 대조와 수치 도구로 일부 검증 가능하다. 인용이 존재한다는 사실만으로 문장이 결론을 뒷받침한다는 entailment가 증명되지는 않는다.
2. **해석과 적용성:** 수식의 전제, 경계조건, 관측 가능량이 현재 claim에 해당하는지. 전문 지식과 별도 분석이 필요하고 제2 LLM은 반례를 제시하는 보조 수단이다.
3. **현실에서의 타당성 및 승인:** 논문의 방법 자체가 옳은지, 새로운 장비/형상에서도 성립하는지. 독립 실험·재현·수치 검증·프로젝트 권한자의 판단이 필요하다. 모델 합의로 대체하지 않는다.

운영에서는 구조 검사가 통과해도 semantic correctness 미확정 상태를 유지할 수 있어야 한다. 자료가 충분한데 모델끼리 의견만 다르다는 이유로 REQUEST_EVIDENCE를 만들어내지 않는다. 실제 필수자료가 빠진 경우에만 그 Action을 사용하고, 해석 불일치는 기존 Human Review/workflow 상태로 전달한다. NO_ACTION_REQUIRED는 해당 검토점에 대한 제안일 뿐 공학 승인과 연결하지 않는다. 새 source 고위험 검토는 두 모델 일치 여부와 무관하게 검증 대상으로 둔다.

과적합을 판별할 다음 평가 설계는 다음과 같다.

- 학습에 쓰지 않은 source/program을 먼저 정하고 해당 source에서 나온 변형·pair 전체를 동일 split에 둔다. 시험 입력·정답을 본 다음 training 예제로 돌리지 않는다.
- 모델 출력 전에 원문과 독립 계산을 근거로 기대 Action과 허용 이유를 검토한다. 의미적으로 여러 답이 가능한 사례는 버전이 분리된 새 평가의 adjudication 기록에 명시한다.
- 같은 모델의 baseline과 LoRA를 같은 새 평가로 비교한다. 새 source에서만 악화되면 익숙한 출처에 대한 적응/과적합 가설이 강해지며, 기존 84건 향상만으로는 이를 반박할 수 없다.
- 모델 토론도 단일 모델, 독립 2개 검토, 제한된 재검토를 같은 입력과 계산 예산으로 비교한다. 오수용뿐 아니라 둘 다 동의하며 틀린 비율, 정답→오답 변경, 사람 검토 요청률, 처리 coverage, 분야별 정확도, 지연을 기록한다.
- 정답 마련이 불가능한 실제 새 논문 사례는 자동 승인 성능 집계에 넣지 않고 근거 정리·검토 보조 업무로 취급한다. 이는 제품의 Human Review와 Governed Blackboard 설계에 맞는다.

외부 검증 없이 다시 생각하라고 하는 방식의 한계는 [ICLR 2024 연구](https://arxiv.org/abs/2310.01798)와 [2025 다중 모델 토론 실패 분석](https://arxiv.org/abs/2509.05396)에서도 관찰됐다. 이 결과가 모든 self-correction이 불가능하다는 정리는 아니며, 외부 근거와 검증 장치가 없는 토론을 정답 보증으로 삼지 말아야 한다는 근거로 사용한다.
