# DoriLab — Gemma 4 E4B 새 프로젝트

## 바로 시작

기존 `~/dorilab-ai`는 보존한다. 새 빈 폴더에서 이 ZIP을 풀고 `start.sh`를 실행한다.

```bash
mkdir -p ~/dorilab-gemma4-e4b
cd ~/dorilab-gemma4-e4b
explorer.exe .
```

열린 탐색기에 `DoriLab_Gemma4_E4B.zip`을 복사한다. 이 ZIP은 최상위에 `start.sh`가 있는 평평한 구조다.

```bash
python3 -m zipfile -e DoriLab_Gemma4_E4B.zip .
bash start.sh --source ~/dorilab-ai/DoriLab_SourceCurriculum_v02
```

위 명령은 새 폴더에 Python 환경 설치, 데이터 가져오기, Gemma 자체의 학습 전 평가, 실제 QLoRA 1회 학습, adapter 재로딩, 학습 후 평가, 비교 요약까지 순차 실행한다. 단계별 사용자 승인이나 반복적인 2B 실험을 요구하지 않는다. 네트워크·모델 권한·메모리 문제까지 성공을 보장하는 명령은 아니다.

## 사용하는 모델

`google/gemma-4-E4B-it` instruction-tuned checkpoint에서 새 adapter를 학습한다. 이름이 비슷한 `gemma-3n-E4B-it`가 아니며 Qwen adapter를 적용하지 않는다. 모델의 현재 revision을 처음 받아 고정한 뒤 전후 평가·학습에 같은 revision을 사용한다.

Google 문서에서 E4B는 effective 약 4.5B, 임베딩 포함 약 8B이다. 일반적인 BF16 4B 모델처럼 메모리를 예상하면 안 된다. 이 레시피는 RTX 5080 16GB를 대상으로 NF4 양자화·BF16 계산·microbatch 1·gradient checkpointing을 사용한다. 실제 전체 학습 VRAM은 로컬 실행에서 확인한다.

## 가져오는 것 / 가져오지 않는 것

|가져오는 것|처리|
|---|---|
|v12 `repeat246.jsonl`|기존 246행의 메시지·정답·메타데이터를 보존|
|업무 system/user 프롬프트|Qwen 모델용 special-token 문자열이 아닌 메시지 원문을 재사용|
|NS10 24건|기존 범위 게이트를 거친 입력과 메시지 trace를 확인|
|무관 관측 앞 배치 40건|기존 근거 선택 회귀를 재사용|
|Contract Dev20|이전 읽기/프롬프트 코드를 복사한 격리 영역에서 메시지·정답만 추출|
|스키마·리뷰·manifest|스냅샷과 해시로 출처 연결|
|2B 과거 결과|같은 채점 방식으로 재집계해 참고 비교|

Qwen 본체·LoRA·옵티마이저·토큰 ID·Qwen EOS·Qwen chat template·기존 `.venv`는 가져오지 않는다. Gemma의 토큰화와 native chat template로 다시 인코딩한다. 기존 실패한 reason 설명도 추가하지 않는다. 모든 평가 데이터를 학습에 합치지 않는다.

기본 선택이 repeat인 이유는 현재 v12에서 repeat가 NS10 19/24, 근거40 36/40, Contract20 20/20으로 비교 기준이었기 때문이다. coverage도 NS10 19/24였지만 근거40은 34/40이었다. 새로운 Gemma가 coverage에서 더 나아질 가능성은 별개이며 이번에는 변수를 늘리지 않는다. 반드시 coverage로 시작하려면 **새 폴더에서 처음 실행할 때만** `--arm coverage`를 사용한다. 두 파일을 합치지 않는다.

## 독립 환경

프로젝트 내부에 `.bootstrap`, `.python`, `.venv`, `.uv-cache`를 만든다. 기존 시스템 Python과 Qwen 환경의 패키지·드라이버·CUDA Toolkit을 수정하지 않는다.

선택한 기본 조합:

- 별도 managed Python 3.12
- PyTorch 2.10.0 + CUDA 12.8 wheel, torchvision 0.25.0
- Transformers 5.10.1, PEFT 0.19.0, bitsandbytes 0.49.2
- 기타 의존성은 requirements 범위 내에서 설치 후 `reports/requirements_resolved.txt`에 전체 버전 보존

이는 최신 버전을 무조건 따라가는 구성이 아니라 문서에 존재하는 고정 시작 조합이다. 공식 bitsandbytes 설치표가 CUDA 12.8~12.9의 sm120을 표시하기 때문에 이전 cu132 환경과 분리한 cu128 경로를 택했다. 버전의 존재와 실제 조합의 GPU 동작 보장은 다르므로 로컬에서 NF4 CUDA forward/backward부터 검사한다.

HF 계정 권한 오류(401/403)가 날 때만 같은 새 환경에서 다음을 실행한다. 토큰을 코드나 공유할 로그에 쓰지 않는다.

```bash
.venv/bin/hf auth login
```

모델 다운로드·Python·PyTorch·설치 캐시 때문에 수십 GB의 추가 디스크가 필요할 수 있다. 약 40GB 이상 여유를 계획하되 실제 사용량은 설치 환경에 따라 달라진다. 데이터와 결과를 Hub로 올리는 코드는 없으며 report_to는 none이다.

## 16GB 메모리 대응

본체 선형층은 bitsandbytes NF4 + double quantization, 계산은 BF16이다. 언어 모델의 attention/MLP 선형층에만 rank16, alpha32, dropout0.05 LoRA를 건다. 비전·오디오·큰 임베딩·PLE 표·lm_head는 학습하지 않는다. 새 특수토큰을 추가하거나 임베딩을 확장하지 않는다.

E4B는 대형 PLE 임베딩을 가진다. 일반 `prepare_model_for_kbit_training()`의 비양자화 가중치 전체 FP32 변환을 그대로 적용하지 않고, 본체를 명시적으로 freeze하고 BF16 embedding을 유지한다. Gemma4 RMSNorm은 구현 내부에서 float32로 정규화한다. 비재진입 checkpointing을 켜고 실제 longest-row backward에서 LoRA gradient가 유한하고 0이 아닌지 확인한다. 이것은 임의의 전체 FP32 복사를 피하려는 별도 준비 방식이며, 모든 Gemma 학습에 범용으로 추천하는 설정은 아니다.

262K vocabulary에 대해 전체 prompt 위치의 logits를 만들면 메모리를 많이 사용한다. `logits_to_keep`를 이용해 **정답 토큰을 예측하는 위치만 vocabulary logits를 계산**한다. 모든 입력 토큰은 모델에 들어가며, attention 문맥을 자르지 않는다. 이 batch-size-1 계산의 loss와 gradient가 일반 masked causal cross-entropy와 같은지를 CPU tensor test로 확인했다.

## 정답 마스킹

학습과 추론 모두 공식 processor의 native chat template, `enable_thinking=False`를 사용한다. `system + user + model prefix`는 loss -100으로 가리고, assistant JSON과 실제 Gemma turn-end를 학습한다. template의 끝 구분 newline만 제거하며 자료는 자르지 않는다. prefix 문자열과 토큰 경계, 정답 decode, EOS를 먼저 검증한다. 불일치하면 임의로 보정하지 않고 멈춘다.

훈련 설정은 데이터 하나/학습률 하나/2 epoch이다. 기존 Qwen과 같은 업무 비교를 위해 greedy/no-thinking을 사용하며 Google의 일반 샘플링 성능 권장치 전체를 탐색하지 않는다. 정상적인 기본 성능을 넘어선 개선을 보장하지 않는다.

## 실행 단계와 산출물

|단계|내용|
|---|---|
|import|과거 데이터/메시지/정답/출처 스냅샷. 모델 로드 없음|
|preflight|CUDA NF4 작은 backward, revision/processor 고정, 모든 mask/길이 검사|
|baseline|Gemma 학습 전 24+40+20건 실제 생성|
|train|가장 긴 학습행의 backward 검사(optimizer step 0) 후 246행 2 epoch|
|finetuned|새 base + 저장된 Gemma adapter 재로딩 후 동일 84건 실제 생성|
|compare|기존 2B 참고값 / Gemma 전 / Gemma 후 비교|

학습 전후 총 168건을 생성한다. 새로운 독립 사례 168개로 계산하지 않는다. NS10은 이미 실패 결과를 개발에 사용한 회귀 세트이고, 근거40은 학습 유형이 포함돼 있다. 이 실험은 마감용 후보 비교이며 신규 독립 성능 인증이 아니다.

최종 위치:

```text
~/dorilab-gemma4-e4b/
  reports/RESULTS_KO.md
  reports/comparison.json
  reports/comparison_cases.jsonl
  reports/baseline/                 # 학습 전 실제 출력
  reports/finetuned/                # 학습 후 실제 출력
  reports/preflight.json
  reports/training_receipt.json
  runs/gemma4_e4b_repeat246_e2/       # 새 Gemma LoRA (full base가 아님)
  assets/processor/                 # Gemma processor/template 스냅샷
  data/train.jsonl
  data/eval_*.jsonl
  data/IMPORT_MANIFEST.json
  snapshot/                        # 출처 이력, Qwen weights 없음
  logs/
  state/                           # 완료 단계 확인 기록
```

```bash
explorer.exe reports
explorer.exe runs/gemma4_e4b_repeat246_e2
```

coverage arm을 선택한 경우에도 기본 실행 폴더명은 고정이다. **실제 학습 arm은 IMPORT_MANIFEST와 RUN_MANIFEST가 권위 있는 기록**이다. 기본 repeat 실행을 권한다.

## 실패·재시작

완료 단계는 output hash를 확인한 뒤 재실행하지 않는다. 미완료 단계의 이전 log는 timestamp 파일로 보존한다. 인증/일시적 다운로드 오류처럼 산출물이 아직 없으면 같은 start 명령으로 재시도할 수 있다.

중간까지 저장된 평가파일·학습 폴더가 있으면 덮어쓰지 않고 멈춘다. 자동 checkpoint resume·OOM batch 변경·CPU offload·문맥 자르기·패키지 업데이트는 하지 않는다. 이 경우 logs의 실패 단계 파일을 확인해야 한다. 데이터/평가의 고정 조건을 유지하기 위한 동작이다.

OOM이면 그것은 하드웨어·레시피 적합성 문제이지 학습 성능 판정이 아니다. CUDA kernel 오류면 bitsandbytes/torch/driver 호환성 문제부터 구분한다. 같은 GPU에서 다른 모델 학습/게임 등을 동시에 실행하지 않는 것이 좋다. 실제 메모리는 preflight/load_report/smoke에서 기록한다.

## 이전 Contract 메시지 추출의 특수사항

기존 runner가 Qwen 모델을 하드코딩한 경우 모델 이름만 Gemma로 바꾸지 않는다. 대신 코드/입력의 복사본을 새 snapshot에 만들고, **실제 모델이 아닌 inert double**로 reader를 실행해 정확한 system/user 메시지와 기존 expected만 추출한다. 그 임시 dummy 점수는 새 성능으로 보고하지 않는다. 이 추출 과정은 네트워크와 새 프로젝트 밖의 Python 파일 쓰기를 막는다.

과거 repeat Contract 출력 20건을 새 채점기에 넣었을 때 과거 pass와 일치하는지 먼저 확인한다. 일치하지 않거나 prompt capture가 정확히 20개가 아니면 본 학습 전에 중단한다. 데이터 구조를 추측해서 대충 변환하지 않는다.

## 검증 범위

제작 환경에서는 실제 Gemma 라이브러리와 GPU가 없었다. CPU에서 테스트한 것은 입력 보존, JSON/근거 검증, mock tokenizer의 mask/종료 토큰, 실제 PyTorch tensor로 loss/gradient 동등성, 복사한 가상 legacy reader에서 20개 메시지 추출, 가상 246행 프로젝트 전체 import이다.

Gemma 체크포인트의 실제 토큰 경계·로딩·NF4 연산·longest-row backward·adapter 저장과 재로딩은 사용자 실행에서 확인한다. 패키지가 그 검사들을 자동으로 포함하지만, 미리 성공했다고 주장하지 않는다.

## 출처

설계 확인일: 2026-09-20. 프로젝트 결과는 사용자가 제공한 v12 comparison.json 기반이다.

- 모델 카드: https://huggingface.co/google/gemma-4-E4B-it
- Gemma QLoRA 공식 안내: https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora
- Gemma4 Transformers API: https://huggingface.co/docs/transformers/model_doc/gemma4
- 선택한 구현: https://github.com/huggingface/transformers/blob/v5.10.1/src/transformers/models/gemma4/modeling_gemma4.py
- bitsandbytes 설치/지원표: https://huggingface.co/docs/bitsandbytes/main/en/installation
- PyTorch 배포 조합: https://pytorch.org/get-started/previous-versions/
- 독립 Python 설치: https://docs.astral.sh/uv/guides/install-python/

현재 문서의 일반 Gemma 예제를 그대로 복사한 것이 아니라, DoriLab의 고정 JSON 업무·16GB·기존 데이터 재사용에 맞춰 구현한 별도 recipe다.
