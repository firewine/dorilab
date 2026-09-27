# 문헌 기반 경량 모델 학습 실습서
## DoriLab Source Curriculum v0.2 · Windows/WSL2 · Qwen3.5-2B

**출처를 확인하고, 사례를 검토하고, LoRA를 학습한 뒤, 같은 조건에서 비교하는 전체 과정**

사용자 환경에서는 Qwen3.5-2B의 language-only LoRA 학습과 추론이 이미 성공했다. 이 실습서는 설치를 처음부터 반복하지 않는다. 기존 `~/dorilab-ai/.venv`와 `adapters/dorilab-qwen35-2b-v01`을 보존한 상태에서 문헌 기반 검토 학습을 추가한다.

### 이번에 실제로 만들 결과

검토한 Physics 사례와 기존 Contract150을 결합한 학습 JSONL, 새 LoRA adapter, 같은 프롬프트·원문으로 비교한 평가 결과, 사용 출처·데이터·코드·환경의 manifest다. 새 adapter는 먼저 clean Qwen3.5-2B에서 시작한다. 기존 v0.1 위에 계속 학습하는 방식은 별도 실험으로 구분한다.

### 먼저 알아둘 상태

40개 후보는 모두 사람 검토 대기다. 자동 검사를 통과했다는 것은 JSON 구조·참조·쌍의 구성에 관한 확인이다. 공학적 정답의 확정은 사용자가 원문과 가상 사례를 검토한 뒤 기록한다. 신규 코드의 GPU 학습은 이 제작 환경에서 실행하지 않았다. 첫 실행은 반드시 5-step으로 확인하도록 구성했다.

### 빠른 길찾기

환경과 개념은 1~3절, 출처·정답 검토는 4~6절, 학습 파일과 실행은 7~10절, 평가와 확장은 11~14절, 오류 해결과 배포는 15~17절이다. 모든 실행 블록은 **WSL Ubuntu의 Bash**에 붙여넣는다. Python 파일은 ZIP에 이미 들어 있으므로 코드를 별도로 복사할 필요가 없다.

**전체 흐름**

원문·사례 검토 → 승인 기록 → 학습파일 export → 토큰·loss 마스크 확인 → 5-step → 새 1-epoch 학습 → Base/v0.1/v0.2 비교 → 미사용 프로그램 평가 → 실행 보드 연결.

<!-- PAGE -->
## 1. 지금 하는 학습은 무엇인가

| 용어 | 이 실습에서의 의미 |
|---|---|
| Base model | 이미 공개된 Qwen3.5-2B. 학습마다 이 본체에서 출발 |
| LoRA | 본체를 동결하고 일부 추가 행렬만 업데이트하는 방법 |
| SFT | 주어진 입력에서 정답 출력을 만들도록 학습하는 방법 |
| 예제 한 개 | 관련 원문 원리 + 가상 시험상태 + 검토 질문 + 정답 행동 |
| Epoch | 준비한 학습 예제를 한 차례 읽는 단위 |
| Step | 누적한 gradient로 파라미터를 한 번 업데이트하는 단위 |
| Token | 모델이 처리하는 텍스트 조각. 긴 문헌과 짧은 JSON의 길이 단위 |
| Loss | 정답 토큰을 예측하는 훈련 오차. 실제 업무 성공률과는 별도 |
| Adapter | 학습한 추가 가중치 파일. Base와 함께 로드 |
| RAG | 필요한 원문을 찾아 모델 입력에 제공하는 경로 |
| Dev / Eval | 개발하면서 보는 사례 / 구성 동결 후 평가할 사례 |

LoRA를 붙여 새 2B foundation model을 처음부터 만드는 것이 아니다. 기존 공개 모델이 DoriLab의 문헌 검토 행동을 더 잘 수행하도록 특화한다. PEFT는 LoRA 추가·저장·재로딩을 제공한다. [T01]

## 2. 무엇을 학습하고 무엇을 외부에 남기는가

**학습 대상:** 측정의 의미 비교, 적용범위 구분, 주장과 근거의 연결, 추가 자료 선택, 구조화된 결과 작성. **외부 원문:** 논문·규격·현재 판본·고객자료. **도구:** 계산과 데이터 품질검사. **보드:** 현재 형상·근거·실행 이력·승인·미해결 문제.

이번 Physics 계약은 `CHALLENGE`, `REQUEST_EVIDENCE`, `NO_ACTION_REQUIRED`의 세 행동으로 범위를 제한한다. 기존 Contract150에는 도구 호출 등 다른 행동이 있고, replay할 때 원래 system prompt를 보존한다. 단순히 모든 행동 enum을 한 목록으로 섞는 방식이 아니다.

`NO_ACTION_REQUIRED`는 **이번 검토 질문의 수정이 불필요함**이다. 제품 전체 합격이나 시험 운전 권한을 뜻하지 않는다. 자료 요청이 필요한 경우에는 존재하지 않는 결과를 만들지 않고 요청 ID를 반환한다.

<!-- PAGE -->
## 3. 작업 환경과 패키지 설치

### 사용할 장비

주 학습·추론은 Windows PC의 WSL2와 RTX5080으로 유지한다. Mac mini Pro24GB는 문서 검토·코드 편집·원격 접속에 사용한다. 두 장비의 GPU 메모리는 하나로 합쳐지지 않는다. Mac 단독 학습은 MLX-LM이라는 별도 경로가 있으나 이번 실험의 기준 환경은 WSL CUDA다. [T04, T05]

사용자가 확인한 버전은 Python3.14.4, torch2.14.0+cu132, transformers5.17.0, peft0.20.0, trl1.13.0이다. 이 실습 때문에 패키지 전체를 업데이트하지 않는다. 새로 필요한 CPU 스키마 검증 라이브러리만 확인한다.

### ZIP을 프로젝트로 옮기기

Windows에서 ZIP을 다운로드한 뒤 WSL에서 다음을 실행한다. Explorer로 열린 폴더에 ZIP을 복사한다.

```bash
cd ~/dorilab-ai
source .venv/bin/activate
explorer.exe .
```

파일명은 `DoriLab_SourceCurriculum_v02.zip`이다. 다음 명령은 새 하위 폴더를 만든다. 기존 `runtime/`, `training/`, `adapters/`는 변경하지 않는다.

```bash
python -m zipfile -e DoriLab_SourceCurriculum_v02.zip .
cd DoriLab_SourceCurriculum_v02
python -m pip install 'jsonschema>=4,<5'
python -m dcurr.validate
python -m unittest discover -s tests -v
python -m dcurr.preflight
```

검증 결과는 27 sources, 40 candidate cases, 20 pairs, legacy unchanged와 테스트 통과다. `dcurr.preflight`는 현재 Python·패키지 버전을 출력한다.

### 경로 기준

이후 명령은 모두 `~/dorilab-ai/DoriLab_SourceCurriculum_v02`에서 실행한다. 부모 폴더의 기존 자료는 `../data/...`, 기존 adapter는 `../adapters/...`로 지정한다. `python -m dcurr.train`처럼 모듈 실행을 사용한다.

<!-- PAGE -->
## 4. 기존 두 문헌과 첫 EEE 사례 검토

첫 검토는 모든 40개를 한 번에 승인하는 것이 아니라 **열1쌍·진동1쌍·전기전자1쌍**에서 시작한다.

```bash
python -m dcurr.review --show-pair TH01-P07
python -m dcurr.review --show-pair VBX1-P03
python -m dcurr.review --show-pair EE03-P01
explorer.exe docs
```

`docs/CASE_REVIEW.html`을 열면 A/B 상황, 근거, 정답 후보, 한국어 이유가 함께 보인다. 출력량이 긴 CLI 대신 HTML로 읽어도 된다.

### 원문 받기

```bash
python -m dcurr.fetch_sources --ids TH-01 VB-X1 EE-02 EE-03
```

도구는 PDF 서명을 확인한 뒤 `sources/originals/`에 저장하고 `reports/downloads_*.json`에 SHA-256을 남긴다. NASA 요청이 차단되거나 HTML이 반환되면 실패를 기록하고 공식 상세 주소를 보여준다. 이 경우 브라우저에서 원문을 받아 파일을 보관하고 해당 위치를 기록한다. 파일이 없는 상태에서 다운로드 성공으로 처리하지 않는다.

### 한 쌍의 검토 질문

원문 요약이 해당 절의 뜻과 일치하는가? 가상 관측이 원문에서 실제로 일어난 사건처럼 표시되지 않았는가? A/B에서 바꾼 항목이 행동 차이를 설명하는가? 정답에 필요한 근거가 모두 입력에 있는가? 다른 타당한 행동이 있다면 우선순위나 허용 답안을 정했는가?

예를 들어 EE03-P01은 공급전류만 관측한 상황에서 SET까지 특성화했다고 보는지를 묻는다. 원문은 SEL 감시에 공급전류를, SET 감시에 출력파형을 사용한다. 이 사례는 실제 OPA855 시험의 결과값을 복제하는 것이 아니라 관측 경로를 구분하는 합성 사례다. [EE-03 §6, PDF7쪽]

### 승인 전 수정이 필요하면

`REVISE`로 기록하고 후보의 다음 버전을 만든다. 현재 파일을 수정하면 기존 해시와 리뷰가 더 이상 같은 데이터에 대응하지 않는다. source_fact와 rationale, expected를 함께 갱신한 뒤 새 ID/버전으로 재검토한다.

<!-- PAGE -->
## 5. 사람 검토 기록을 남기기

출처별 권리 검토와 사례별 공학 검토는 서로 다른 CSV에 저장한다. 출처의 권리 표시를 확인하고 실제 이용 범위를 검토한 뒤 source review를 기록한다. 다음은 검토를 끝낸 경우의 명령 예다.

```bash
python -m dcurr.review --source TH-01 \
  --decision REVIEWED_OK --reviewer firewine \
  --notes "NTRS 표시와 사용할 본문 범위 확인"
```

TH01-P07 두 사례를 실제로 읽고 정답 후보에 동의한 경우 각각 기록한다.

```bash
python -m dcurr.review --case PHY-TH01-P07-A \
  --decision APPROVED --reviewer firewine \
  --notes "측정 위치와 모델 표현 비교 확인"
python -m dcurr.review --case PHY-TH01-P07-B \
  --decision APPROVED --reviewer firewine \
  --notes "대응 노드에 한정한 비교 범위 확인"
```

정답을 수정할 때는 `--decision REVISE`, 사용할 수 없는 경우에는 `REJECTED`로 남긴다. 이 명령은 원문·가중치·정답 파일을 바꾸지 않고 검토 CSV만 갱신한다. 쌍의 한쪽만 승인하면 export가 멈춘다. A/B의 대조 관계를 유지하기 위해서다.

## 6. Astra로 다음 사례를 만들 때

교사 모델은 정답을 자동 확정하는 심판이 아니라 **근거가 연결된 후보와 표현 변형을 만드는 도구**로 사용한다. `templates/TEACHER_PROMPT_KO.md`에 복사해서 쓸 지시문을 넣었다. 입력에는 검토한 source fact·원문 위치·허용 행동·가상값 규칙을 준다. 출력에는 A/B 차이, 정답 후보, 근거 ID, 불확실한 부분을 요구한다.

교사에게 사용할 자료의 이용권과 교사 서비스의 출력 재학습 조건은 따로 확인한다. OpenAI 모델은 현재 모델 카탈로그와 서비스 약관을 기준으로 사용한다. 이번 패키지는 API 키나 자동 호출을 포함하지 않으며, 비용은 사용자가 선택한 교사 호출에서 발생한다. [T06, T07]

초기에는 한 문헌에서 독립적인 주제 2~4개, 주제당 대조쌍1~2개를 만든다. 같은 의미의 문장을 숫자만 바꿔 수백 개 만드는 것보다, 서로 다른 실패 원인·정상근거·미확정 상태를 분리하는 것이 이번 작업의 목표다.

<!-- PAGE -->
## 7. 정답 형식과 원문 근거를 함께 관리하기

예제에는 두 층이 있다. 학습용 `messages`는 모델이 읽고 생성할 내용이고, metadata는 출처·분할·사람 검토를 관리하는 기록이다. 정답·검토 이유·split 이름은 추론 입력에 섞지 않는다.

```json
{
  "source_id": "EE-03",
  "program_group": "AOS_OPAMP_SEE_LBNL_2022",
  "basis": "SYNTHETIC_COUNTERFACTUAL",
  "pair_id": "EE03-P01",
  "role": "CRITIC",
  "human_review_status": "PENDING"
}
```

모델 입력의 `reference_context`는 원문의 자체 요약과 출처 ID를 가진다. `case_packet`에는 가상 관측과 검토할 제안이 있다. 모델 출력은 action, claim_id, evidence_refs와 필요할 때 reason·requested_evidence를 포함한다. 별도 `rationale_ko`는 사람이 검토할 설명이며 학생의 입력은 아니다.

### 같은 단어라도 다른 역할

문헌의 관측은 해당 시험의 사실이고, 고객의 요구조건은 비교 기준이며, AI의 추론은 잠정 해석이다. 학습 중 `APPROVED`라는 단어만 보고 통과하는 지름길을 만들지 않도록, 승인 범위가 맞는 사례와 다른 사례를 같이 둔다. `CURRENT`라는 표기도 적용 시점·제품·Scope와 연결해 검토한다.

### 후보의 출처 계보

Source ID → source_fact ID → pair ID → case ID → review record → build manifest → adapter manifest의 순서를 유지한다. 같은 프로그램의 여러 논문은 `program_groups`로 연결한다. PDF 페이지와 인쇄 페이지는 다를 수 있으므로 각각 기록한다.

### 새로 주석한 사례 등록

`templates/example_case_record.json`은 채워진 형식 참고다. 새 원문을 읽어 동일 형식의 A/B JSON을 한 줄씩 `data/new_pairs_draft.jsonl`에 저장한다. 페이지·절·근거 ID와 프로그램 그룹은 실제 검토한 것으로 채운다. `source_facts_verification`은 직접 본문 확인을 마친 경우 `USER_CHECKED_BODY`로 기록한다.

```bash
python -m dcurr.add_candidates --file data/new_pairs_draft.jsonl
python -m dcurr.add_candidates --file data/new_pairs_draft.jsonl --commit
```

첫 명령은 검사만 하고, 두 번째가 PENDING 후보와 검토표를 추가한다. 등록 전 파일은 reports에 백업된다. 기존 40개 원본은 유지되고 신규 사례는 additional_candidates.jsonl에 쌓인다. 이후 사람 검토→prepare를 같은 경로로 진행한다.

### 새 분야의 스키마 확장

현재 추가한 EEE 이유 코드는 모니터링 범위, 노출 메타데이터, 증거 해석의 세 종류다. 새로운 domain마다 action 이름을 늘리지 않고 필요한 reason과 tool contract를 검토한다. 스키마를 바꾸면 prompt·학습 export·평가기에도 같은 버전을 적용한다.

<!-- PAGE -->
## 8. 승인 사례를 학습 JSONL로 내보내기

검토한 사례만 export한다. 기존 Contract150은 별도 `--contract` 인자로 넣으면 원래 messages를 유지하며 replay 데이터로 합쳐진다.

```bash
python -m dcurr.prepare \
  --contract ../data/train150_v01.jsonl \
  --out build/train_v02.jsonl
```

출력은 `build/train_v02.jsonl`과 `build/train_v02.manifest.json`이다. 현재 승인한 Physics 쌍 수에 따라 레코드 수가 달라진다. 40개를 모두 승인했고 Contract150이 있으면 **190개**, 열1쌍만 승인했다면 **152개**다. 출력 숫자는 프로그램이 실제 읽은 데이터로 계산한다.

`No fully reviewed pairs`는 오류가 아니라 아직 승인된 완전한 A/B가 없다는 뜻이다. `source permission review pending`은 해당 출처의 source review가 남았다는 뜻이다. 이미 같은 이름의 build가 있으면 새 파일명으로 만든다.

### mix 비율의 시작점

첫 소규모 실험은 중복 없이 approved Physics40 + Contract150을 사용한다. 이후 물리 사례가 늘면 Common / Mechanics / Thermal / EEE의 샘플 수뿐 아니라 **정답 토큰 수**를 같이 본다. 긴 reasoning 설명이 한 분야에 몰리면 레코드 수가 같아도 학습 비중이 달라진다.

확장 실험의 시작 가설은 Common20~30%, Mechanics25~35%, Thermal25~35%, EEE15~25% 수준이다. 합계100%가 되도록 하나의 조합을 택하고 Dev에서 회귀와 신규 영역 개선을 확인한다. 이는 사전에 입증된 최적 비율이 아니라 비교할 실험 설계다. 초기 190개 실습에서 이 비율을 맞추려고 예제를 무조건 복제하지 않는다.

### clean base에서 시작하는 이유

Contract-only v0.1은 그대로 보존한다. 새로운 mix를 clean base에 학습하면 데이터 구성의 차이를 비교하기 쉽다. adapter 이어학습은 비용을 줄일 수 있는 별도 선택이지만, 이력과 샘플 노출 횟수를 따로 남겨야 한다.

<!-- PAGE -->
## 9. Train과 Inference의 입력을 같게 만들기

이전 실험에서 prompt 불일치가 큰 결과 차이를 만들었다. 이번에는 `dcurr/prompts.py`와 `dcurr/model_io.py`가 학습·평가의 공용 경로다. 기존 Seed32 prompt를 승계한 파일도 해시로 묶는다.

학습은 `prompt token IDs + answer token IDs + message-end token`을 직접 만든다. prompt 위치의 label은 **-100**, answer와 종료 위치는 정답 token ID다. 여기서 -100은 모델이 생성할 정답으로 학습하지 않을 위치라는 뜻이다. [T02, T03]

```text
input_ids : [system/user/prompt ...] [answer JSON ...] [im_end]
labels    : [-100, -100, ...      ] [answer IDs ... ] [im_end]
```

평가에서는 같은 processor로 prompt까지만 만든 뒤 그 이후를 생성한다. 입력 토큰에 정답이 들어가지 않는다. padding 위치 역시 -100으로 두되, 실제 정답의 종료 토큰은 학습한다.

**이번 코드는 TRL 자동 전처리 대신 Transformers Trainer에 명시적 labels를 전달한다.** SFT와 LoRA의 목적은 같고, 바뀐 것은 토큰과 loss 마스크를 눈으로 확인하기 쉬운 구현 경로다. 이 때문에 기존 GPU 성공 이력과 별도로 5-step을 다시 확인한다. [T02]

### 토큰 사전검사

```bash
python -m dcurr.preflight \
  --data build/train_v02.jsonl \
  --max-length 2048
```

검사기는 processor가 직접 만든 prompt와 tokenizer로 만든 prompt의 토큰 일치를 확인하고, 모든 사례에 정답 label이 있는지 검사한다. 길이를 넘는 사례는 조용히 자르지 않고 ID와 길이를 알려준다. 정답을 잘라 학습하는 상황을 방지하기 위한 동작이다.

`max_total_tokens`가2048을 넘으면 해당 근거 묶음을 줄이거나4096을 별도 실험한다. 먼저 원문을 무차별 삭제하기보다 현재 검토 질문과 관계없는 문맥을 분리한다. `reports/preflight_latest.json`에는 사례별 길이와 전체 prompt/answer 토큰 수가 남는다.

<!-- PAGE -->
## 10. 5-step 확인 후 새 LoRA 학습

### 언어모델만 학습

Qwen3.5는 language model과 vision 부분이 분리된 멀티모달 모델이다. 기존에 확인한 `model.language_model.layers.*` 아래의 실제 Linear 모듈 이름을 코드가 수집한다. Vision, lm_head, embedding과 본체는 동결하고 LoRA 행렬만 학습 대상으로 검사한다. [T01, T03]

```bash
python -m dcurr.train \
  --data build/train_v02.jsonl \
  --out ../adapters/dorilab-curriculum-v02-smoke \
  --max-steps 5 --max-length 2048
```

확인할 출력은 trainable parameter 수, `Vision/non-LoRA trainable parameters: 0`, 5step 완료, adapter 저장이다. 폴더가 이미 있으면 새 이름을 쓴다. Smoke가 완료되면 그 가중치에 이어 학습하지 않고 새 실행을 시작한다.

### 첫 정식 실행: 1 epoch

```bash
python -m dcurr.train \
  --data build/train_v02.jsonl \
  --out ../adapters/dorilab-curriculum-v02-e1 \
  --epochs 1 --lr 5e-5 --rank 16 --max-length 2048
```

기본값은 BF16, batch1, gradient accumulation4, rank16, alpha32, dropout0.05다. warmup은 정수 `warmup_steps`를 사용한다. 이미 사용자 환경에서 문제가 난 `warmup_ratio`는 사용하지 않는다.

190개라면 대략 ceil(190/4)=48 optimizer steps가1epoch의 계획값이다. 실제 step수와 runtime은 Trainer 출력에 기록된다. 문헌 사례는 기존 JSON 예제보다 길기 때문에 이전105초와 같은 시간을 전제하지 않는다.

2epoch 비교가 필요하면 같은 데이터에서 clean base로 새 폴더 `...-e2`를 만든다. 더 낮은 train loss가 아니라 검토한 Dev의 오류·완료율·회귀를 기준으로 선택한다.

<!-- PAGE -->
## 11. 기본 모델·기존 v0.1·새 v0.2를 비교하기

첫 실행은 `--limit 4`로 로딩·생성을 확인할 수 있다. 전체 비교에서는 같은40개, 같은 prompt·reference_context·출력 한도로 세 구성을 돌린다.

```bash
python -m dcurr.evaluate \
  --out reports/base_physics40.jsonl
python -m dcurr.evaluate \
  --adapter ../adapters/dorilab-qwen35-2b-v01 \
  --out reports/contract_v01_physics40.jsonl
python -m dcurr.evaluate \
  --adapter ../adapters/dorilab-curriculum-v02-e1 \
  --out reports/physics_v02_e1_physics40.jsonl
```

현재 기본 목적은 `CANDIDATE_DIAGNOSTIC`이다. 공개된 후보40개에 대한 개발 진단이며, 훈련에 들어간 사례에서는 재현 여부만 본다. 별도 미사용 사례가 준비되면 `--cases`로 파일을 바꾸고 검토·동결 상태를 기록한다.

### 결과를 읽는 순서

| 지표 | 뜻 |
|---|---|
| strict_json_valid | 원문 출력이 추가 문구 없이 JSON object인가 |
| schema_and_refs_valid | 필수 key, enum, claim와 근거 ID가 유효한가 |
| action_correct | 행동 이름을 맞혔는가 |
| contract_pass | 스키마·근거와 검토한 정답 조건을 함께 만족하는가 |
| both_variants_pass | A/B 두 상황을 모두 맞힌 쌍은 몇 개인가 |
| by_gold_action | 정상·이견·자료요청 중 어느 쪽이 약한가 |

이 평가기는 `status`를 몰래 `action`으로 바꾸지 않는다. Markdown fence나 끝에 붙은 문자가 있으면 strict JSON은 실패다. 이전 느슨한 parser의 JSON100%와 직접 비교하지 않고 새 평가기 버전을 같이 기록한다.

같은 정답에 필요한 근거 ID의 순서는 바뀌어도 된다. 입력에 없는 ID는 실패다. 정답이 여러 가지로 타당하면 엔지니어가 `acceptable_answers`를 기록한 후 평가한다. 결과를 보고 정답을 임의로 넓히는 대신 변경 이유와 버전을 남긴다.

<!-- PAGE -->
## 12. 진짜 미사용 평가를 만드는 방법

### 기존 행동의 회귀 확인

새 adapter를 원래 eval40에 넣어 Contract150에서 배운 행동이 유지되는지도 별도로 확인한다. legacy 평가기의 방식은 그대로 유지하여 v0.1과 비교한다.

```bash
cd ~/dorilab-ai
python -m eval.run_eval40_qwen35 \
  --split dev \
  --adapter adapters/dorilab-curriculum-v02-e1 \
  --label curriculum_v02_contract_regression
cd DoriLab_SourceCurriculum_v02
```



이 패키지의 40개는 읽고 검토하고 학습할 자료다. 그 자체가 독립 평가셋은 아니다. 자료 그룹을 다음처럼 나누는 것은 향후 작성 계획이다.

| 묶음 | 추천 자료 | 관리 방식 |
|---|---|---|
| Training | TH-01, VB-X1, EE-02, 필요한 P1 자료 | 사례·정답을 학습 개발에 사용 |
| Development | TH-D1, MEC-06 등 | 반복 평가하고 오류 분석 가능 |
| Evaluation reserved | TH-S1, VB-S1, EE-04, MAT-02, FL-03, SW-04 | 별도 작성자가 새 사례와 기준 답안 준비 |

같은 프로그램의 자료가 서로 다른 묶음으로 넘어가면 문헌 ID가 달라도 시험 데이터가 겹칠 수 있다. `program_groups`를 먼저 확인한다. 권리 미확인 자료는 학습·평가 export 전에 출처 검토를 해결한다.

### 독립성은 hash만으로 만들어지지 않는다

Hash는 파일이 바뀌지 않았다는 확인이다. 이미 읽은 정답을 이용해 모델을 수정했다면 그 세트는 개발용이다. 숫자만 바꾼 사례, 같은 A/B의 반쪽, 번역본, 같은 실험의 후속 논문을 각기 다른 독립 표본처럼 계산하지 않는다.

### 평가 문헌을 RAG에 넣어도 되는가

새 문헌을 읽고 검토하는 open-book 업무에서는 평가 문헌의 원문을 제공할 수 있다. 이때 원문은 작업 입력이고, 평가 정답·해설·숨겨진 미래자료는 별도다. 원문이 있는 평가와 없는 평가를 혼합해 하나의 점수로 만들지 않는다.

### 점수를 보고 다음 버전으로 갈 때

중요 오류 유형을 한두 개 정해 새로운 학습 사례를 작성하고, 기존 분야의 정상/문제 대조쌍을 replay한다. Dev로 모델·프롬프트를 선택한 뒤 freeze하고 독립 평가를 수행한다. 평가 뒤 수정하면 모델 버전과 평가 이력을 새로 남긴다.

<!-- PAGE -->
## 13. 여섯 영역으로 확장하는 실무 규칙

현재 2B 하나를 Thermal로 학습한 다음 Mechanics로 덮고, 다시 EEE로 덮는 방식보다 **검토된 사례를 누적한 혼합 데이터로 release를 만든다.** 다음 domain의 추가가 기존 domain의 성능을 바꾸는지 확인할 수 있기 때문이다.

| Release | 학습 구성의 예 | 평가에서 볼 것 |
|---|---|---|
| 현재 v0.1 | Contract150 | 정형 상태→행동 회귀 |
| 문헌 v0.2 | Contract + 승인된 Thermal/Mechanics/EEE 후보 | 원문 의미·정상/문제 대조·근거 ID |
| 후속 v0.3 | 더 많은 프로그램 + Materials/Fluid 일부 | 새로운 조건·다른 시험 수준의 적용범위 |
| Episode 후보 | 단일 분야 + 교차 분야 실행기록 | 다음 도구, 자료 추가, 부분 재검토 |

기록할 것은 분야별 사례 수, 독립 source/program 수, action 분포, pair 분포, 입력·정답 토큰 수, 전문가 수정 이유다. 학습 중 특정 domain만 반복적으로 실패하면 데이터의 정답 충돌·원문 매핑·맥락 누락부터 확인한다.

### 별도 adapter를 고려할 때

같은 입력 계약과 충분한 정상/문제 사례를 제공해도 하나의 domain을 개선할 때 다른 domain이 반복적으로 악화되는 경우, 공통 LoRA와 domain 전용 LoRA를 동일 예산에서 비교한다. 전문 adapter의 수 자체를 목표로 두지 않는다.

### 교차영역 사례의 예

진동 중 전원 reset이 발생한 경우에는 진동 입력 유효성과 기능 이상을 따로 기록한다. 저온 기동 시 전압강하가 있으면 온도 이력·전원 조건·부하 상태·시간 정렬을 묶는다. 이 사례는 새 관측과 실제 도구의 결과를 갖춘 이후 Episode 학습으로 확장한다. 지금 40개 후보는 이 전체 경로의 학습자료가 아니다.

<!-- PAGE -->
## 14. 두 논문부터 다음 자료까지 실제 읽기 작업

한 문헌에 대해 첫날에 해야 할 일은 전체 텍스트의 자동요약보다 **시험목적, 실제 시험품, 조작한 입력, 측정한 출력, 비교 모델, 보고서가 한정한 범위**의 여섯 줄을 채우는 것이다. `templates/*_worksheet.md`가 그 양식이다.

두 번째로 후보 원리 2~4개를 뽑고 각기 다른 종류의 대조쌍을 만든다. 열에서는 측정 위치·경계조건·안정화·파라미터 식별, 기계에서는 치구·모드·입력·응답·시험품 형상, EEE에서는 감시채널·전원 조건·자극 시간·fault 유형이 우선 과제다.

세 번째로 반례를 만든다. 필요한 근거가 이미 있는 정상 사례, 일부 Scope만 승인된 사례, 자료가 없어서 판단이 열린 사례, 같은 용어지만 다른 물리량인 사례를 포함한다. 수치가 합성이면 값을 만들었다는 사실과 단위를 기록한다.

교사 모델이 만든 한 쌍을 검토할 때는 ‘왜 A에는 이견이 필요하고 B에는 필요하지 않은가’를 자신의 말로 설명할 수 있어야 한다. 설명이 되지 않으면 라벨을 유보하고 source fact를 더 읽는다. 이 작업을 통해 명확한 지도학습 데이터와 앞으로 필요한 실험 데이터를 구분할 수 있다.

## 15. 자주 발생하는 오류와 대응

| 현상 | 우선 확인 |
|---|---|
| `No module named dcurr` | 새 패키지 폴더에서 `python -m ...` 실행했는가 |
| `No module named jsonschema` | 활성 venv에서 jsonschema만 설치 |
| `Unsupported TrainingArguments` | 이미 작동한 라이브러리를 유지하고 인자 이름 확인 |
| `warmup_ratio` 오류 | 본 코드는 `warmup_steps` 사용; 이전 파일 실행 여부 확인 |
| 토큰 길이초과 | 해당case의 근거묶음 검토, max-length 실험; 정답 자동 절단 없음 |
| reference kernel fallback | 현재는 동작 확인 후 시간 측정. 커널설치는 별도 환경 실험 |
| Vision trainable 감지 | 실제 모듈 이름·target 범위 확인 후 재시도 |
| JSON은 맞지만 action 누락 | train/inference prompt·schema hash와 raw 출력 확인 |
| train은 잘 맞고 Dev 실패 | 입력 계약·문맥정보·원리조합·그룹분리 순으로 분석 |
| 정상 사례마다 경고 | 양성/정상 대조, 요청사유, 승인 Scope와 토큰 분포 확인 |

<!-- PAGE -->
## 16. GPU 메모리, 저장, 재현

RTX 5080에서 이미 확인한 2B 추론·짧은 학습 경로를 유지한다. 문헌 사례는 길이가 늘어나므로 실제 최대 VRAM을 측정한다. 메모리가 부족하면 학습 외 GPU 프로세스, batch 1, gradient checkpointing, 문맥 길이 순으로 확인한다. 다음으로 rank 8·양자화 등을 별도 실험하되 기존 BF16 결과와 환경을 보존한다.

학습 스크립트는 `RUN_MANIFEST.json`에 base 모델명, 확인 가능한 base 모델 revision, 데이터·prompt·renderer 해시, target 모듈, 설정, 환경을 남긴다. `TRAIN_RESULT.json`에는 실제 학습 실행시간과 loss가 남는다. 평가 결과는 raw 출력·스키마검사·근거검사·토큰·생성시간을 기록한다.

생성시간은 모델 로딩·문서 파싱·검색·사람 검토를 제외하며 첫 호출의 warmup이 포함된다. 따라서 그것만으로 전체 업무비용을 계산하지 않는다. 제품 평가에서는 실패·재시도와 엔지니어 검토시간을 함께 측정한다.

## 17. Mac 활용과 LangGraph 연결

Mac에서는 HTML 사례 검토, Markdown/코드 편집, source registry 관리, 평가 결과 분석을 할 수 있다. 학습은 Windows에서 실행하고 필요한 파일만 공유한다. Mac MLX 경로는 별도 모델 변환·동작 검증이 필요하므로 이번 5주에서는 보조 장비로 두는 것을 권한다. [T05]

LangGraph 노드는 `build_messages`로 만든 입력 묶음을 모델에 전달하고, 출력은 스키마·참조·권한 검사를 거쳐 보드 수정안으로 반영한다. 현재 Physics 학습은 한 번의 검토 행동을 연습하는 단계다. 자료 조회·계산 도구·사람 승인·새 자료 도착을 연결한 Episode 평가는 그다음이다.

### 이번 패키지 테스트 범위

CPU 단위시험 24개와 구조검사가 통과했다. 신규 GPU 학습·모델 추론·교사 API 호출은 제작 환경에서 실행하지 않았다. 자동 원문 PDF 다운로드도 접속 환경에 따라 실패할 수 있다. 테스트 증거는 reports 폴더에 있고, 원본 문서와 학습 가중치는 포함하지 않았다.

### 기술 참고문서

[T01] Hugging Face PEFT / LoRA: https://huggingface.co/docs/peft/v0.20.0/package_reference/lora

[T02] Transformers Trainer 및 labels: https://huggingface.co/docs/transformers/main_classes/trainer

[T03] Qwen3.5 Transformers 문서: https://huggingface.co/docs/transformers/model_doc/qwen3_5

[T04] NVIDIA CUDA on WSL: https://docs.nvidia.com/cuda/wsl-user-guide/index.html

[T05] Apple MLX-LM: https://github.com/ml-explore/mlx-lm

[T06] OpenAI 모델 카탈로그: https://developers.openai.com/api/docs/models

[T07] OpenAI 서비스 약관: https://openai.com/policies/services-agreement/

공학 문헌의 식별번호·원문·확인범위는 SOURCE_REGISTER.md를 따른다. 위 기술참고는 2026-09-14 확인 기준이다.
