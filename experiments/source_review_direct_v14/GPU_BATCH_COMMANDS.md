이 문서는 다음 DEV8 출력 형식 진단의 실행 계획이다. 이번 CPU 작업에서는 아래 명령을 실행하지 않았다. RunPod 시작 명령은 포함하지 않는다.

고정 조건: `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Transformers `5.18.0.dev0` / commit `002e1edf5b5198488297f401dd853056b6521d02`, BF16, SDPA, greedy (`do_sample=False`), seed 42, native chat template, `enable_thinking=False`, 응답 384 / 총 2048 token. 기존 PyTorch 2.8.0+cu128, PEFT 0.21.0 환경과 동일 GPU 종류를 사용하고 실제 환경을 manifest에 남긴다. 다른 환경이면 생성 시간 차이를 프롬프트의 속도 효과로 단정하지 않는다. adapter, 학습, ledger, constrained decoding, 출력 보정은 사용하지 않는다.

현재 환경에는 과거 manifest의 snapshot 경로가 없다. 이후 준비된 동일 revision의 로컬 snapshot이 있어야 한다. 아래 경로는 과거 기록의 경로이며 현재 존재한다고 보증하지 않는다. 이동된 snapshot을 사용할 때는 `SR14_SNAPSHOT`만 실제 동일 revision 경로로 지정한다. runner는 revision 디렉터리명 및 tokenizer/template/config의 과거 hash를 검사하고 자동 다운로드하지 않는다. Python 경로는 당시 환경의 경로를 제시한 것이며, 실행 시 runner가 Transformers 버전·commit을 검사한다.

다음 명령은 별도 GPU 실행 지시를 받은 뒤 사용한다. `runs/token_preflight`와 `runs/direct_v14`는 새 폴더여야 한다. 기존 폴더가 있으면 덮어쓰지 말고 로그를 보존한 채 새 실행 이름을 지정한다.

```bash
cd /workspace/dorilab
export SR14_ROOT=/workspace/dorilab/experiments/source_review_direct_v14
export SR14_PYTHON=/workspace/dorilab/venvs/dorilab-tournament/bin/python
export SR14_SNAPSHOT=/root/hf-cache/hub/models--Qwen--Qwen3.8-27B/snapshots/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# CPU tokenizer 검사만 수행. 실제 prompt token 수와 렌더링 입력을 저장한다.
CUDA_VISIBLE_DEVICES='' "$SR14_PYTHON" "$SR14_ROOT/scripts/run_direct_v14.py" \
  --snapshot "$SR14_SNAPSHOT" --output "$SR14_ROOT/runs/token_preflight" --preflight-only
```

8건 모두 `prompt_tokens + 384 <= 2048`이고 조건·hash가 일치할 때만 다음 명령을 실행한다. 한 건이라도 초과하면 멈춘다. 입력 truncation, 응답 예산 축소, 문맥 한도 상향, 임의 프롬프트 편집으로 통과시키지 않는다. 필요하면 별도 명시적 수정본과 새 hash·검사·계획을 준비한다. 현재 token 수는 미측정이다.

```bash
# 미래 GPU 배치. runner 자체에서도 모델 로드 전에 tokenizer 검사를 다시 수행한다.
CUDA_VISIBLE_DEVICES=0 "$SR14_PYTHON" "$SR14_ROOT/scripts/run_direct_v14.py" \
  --snapshot "$SR14_SNAPSHOT" --output "$SR14_ROOT/runs/direct_v14" --generate
```

`OUTPUT_SEAL.json` 생성과 output hash 일치를 확인한 뒤, 별도 CPU 프로세스에서만 후보 gold를 결합한다.

```bash
CUDA_VISIBLE_DEVICES='' "$SR14_PYTHON" "$SR14_ROOT/scripts/compare_results.py" \
  --run "$SR14_ROOT/runs/direct_v14"
```

새 출력은 `runs/direct_v14/predictions.jsonl`, 실제 렌더링 텍스트·입력 token ID는 `actual_model_inputs.jsonl`, token 길이는 `TOKEN_PREFLIGHT.json`, 실행 조건은 `RUN_MANIFEST.json`, 생성·로딩 시간은 `OUTPUT_SEAL.json`에 저장한다. 비교 결과는 `runs/direct_v14/comparison/CASE_RESULTS.jsonl`, `CASE_COMPARISON.jsonl`, `SUMMARY.json`이다. 모든 파일 생성은 기존 경로 덮어쓰기를 거부한다.

비교 시 JSON 유효, 기존 scorer의 schema 유효, 필드 계약 위반(`reason_code`, 누락 필수 키, 불필요 키, 빈 요청, claim/reference 오류), 파싱된 Action 일치, schema 통과 후 Action 일치를 각각 집계한다. reference exact의 true/false/미평가를 나누고 strict, 각 사례의 개선·회귀, 생성 시간·token 수를 함께 기록한다. schema 실패 후 reference 미평가에서 평가 가능으로 바뀐 것은 일반적인 정오 개선과 구분한다. 기준은 보존된 과거 `RAW_OFFICIAL_CASE_RESULTS.jsonl`이며 기존 결과를 재채점하거나 고치지 않는다. 원래 `packtool.py`의 `normalize=False` 결과만 새 공식 채점으로 사용한다. 필드 계약 진단은 별도 메타데이터이고 scorer 대체물이 아니다.

후보 정답은 계속 **SOURCE_GROUNDED_AI_CANDIDATE / human_review_performed=false / training_eligible=false**이다. 동일 DEV8(한 출처, 두 관련 family)을 이미 관측한 뒤 설계한 출력 안내 진단이다. 독립 일반화 평가, 안전률 추정, 학습 데이터 또는 LoRA 필요성 판단의 근거로 승격하지 않는다.
