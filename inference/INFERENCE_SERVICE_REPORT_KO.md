# DoriLab RC3 추론 서비스 실제 기동 보고서

기록 시각: 2026-09-27T05:36:46Z. **RunPod 내부 구현·기동·검증 완료, 서비스 실행 유지. Mac 접속은 아직 시험하지 않았다.**

## 실행 상태

| 항목 | 실제 확인 결과 |
|---|---|
| 서비스 PID | `19386` |
| boot_id | `8a4e587f-75e2-446e-bc4c-1ba32964a7ea` |
| Listen | `127.0.0.1:8080`만 LISTEN |
| /healthz | 200 alive |
| /readyz, /health | 모두 200 ready; 로드 중에는 모두 503 확인 |
| 실행 Python | `/root/venvs/dorilab-tournament/bin/python` |
| 실제 base class | `Qwen3_5ForConditionalGeneration` |
| 실제 wrapper | `PeftModelForCausalLM` |
| 적용 adapter | active_adapters=`['default']`, LoRA parameter 수 116,727,808 |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| GPU 전체 사용량 / 용량 | 54,139 / 97,887 MiB |
| 이 서비스 GPU 사용량 | 54,130 MiB; GPU compute process는 PID 19386 1개 |
| 모델 receipt ID | `70a91c7182a24d6e6915e1bb6578777d7963d78182feadb112fb30d25a9af291` |

모델 1벌, web process 1개, generation 동시 1개, 대기열 0개이다. 모델은 GPU에 상주하며 요청마다 로드하지 않는다. warmup이 완료된 후에만 ready로 전환한다. `model.eval()`, 모든 parameter `requires_grad=False`, generation `torch.inference_mode()`를 적용했다.

## 원본 RC3 경로와 검증

성공했던 `results/v15_release_progress/experiment_rc3_resume_01/infer_once.py`, `run_common.py` 및 `cpu_rc3` 연결 모듈을 읽었다. serving bridge는 원래 `tokenization.processor`, `tokenization.inference`, `train_once.verify_checkpoint` 함수를 직접 재사용한다. inline loader는 성공 runner의 **Qwen3_5ForConditionalGeneration + PeftModel.from_pretrained** 클래스와 인자를 유지한다. 일반 AutoModel 예제로 교체하지 않았다. 학습 entrypoint, 평가 main, scorer는 실행하지 않았다. 원본 Python 16개 SHA256 보존 확인은 `artifacts/source_preservation.json`에 있다.

- Base: `Qwen/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, 실제 경로 `/root/models/qwen38-27b`.
- 실제 index와 shard 파일 이름 집합이 일치하는지 확인하고, **18개 shard 전체 bytes·SHA256을 기존 개별 receipt 및 성공 실행 CHECKPOINT_HASHES.json과 대조해 통과**했다. ready marker만으로 hash 검증을 주장하지 않는다. 재다운로드는 없었다.
- Adapter symlink의 실제 경로: `/workspace/dorilab/models/qwen38-27b/rc3-source-review-v15/adapter`.
- Adapter weights SHA256: `d90dee59f00f7c987c1b61ae334f928464bfb412ddb26110d692b92b9a46a689`.
- Adapter config SHA256: `d037e965c05ec56ed6069581635ada7f704a6c6331b56831075f127f52f61628`.
- Transformers commit: `002e1edf5b5198488297f401dd853056b6521d02`.
- BF16, SDPA, greedy, `enable_thinking=false`, 검증된 native processor/template, pad 248044, EOS `<|im_end|>` 248046 유지.
- 전체 4096 / 응답 최대 384. 실제 native 입력 token 수 + 요청 응답 예약이 4096을 넘으면 생성 전 422, 자동 truncation 없음.
- 실제 RC3의 system hash 6개를 allowlist로 고정했다. 서버가 system을 선택하며 임의 system, messages/history, model/adapter 경로 override는 거부한다. 요청마다 입력 tensor 및 KV cache를 새로 사용한다.

## HTTP smoke 실제 결과

공개 데이터나 학습 행을 재사용하지 않고 새 합성 입력 `CHECK_AXIS_DURATION`, required_s=17, synthetic_x=19, synthetic_y=13 한 건을 보냈다. gold, rationale, reference 정답 집합을 전송하지 않았다. 별도의 기술 warmup 1회(최대 8 tokens) 후 **인증된 HTTP generation은 1회** 실행했다.

| 항목 | 결과 |
|---|---|
| 접수 | HTTP 202 |
| 상태 조회 | running → completed |
| 작업 ID | `7385506b-d72c-4a7b-9503-b86575175c1a` |
| 입력 / 생성 token 수 | 629 / 40 |
| 응답 예약 | 384 |
| finish_reason | `eos` |
| 종료 token | `<|im_end|>` 원문에 보존 |
| 모델 generation 지연 | 3.525901초 |
| 접수~완료 HTTP 흐름 | 3.643275초 |
| 입력 SHA256 | `d9fd10a37333211241cdedf62a179d8f022c2e2842a1814c24fff552b1bb231b` |
| 원문 출력 SHA256 | `2fffd2382b288d4111c70c41c2fce760f19ea33d8ff6ee31cc2244e5f68339d1` |

모델 원문:

```text
{"action":"CALL_TOOL","tool":"compare_axis_durations","arguments":{"required_s":17,"actual_by_axis":{"synthetic_x":19,"synthetic_y":13}}}<|im_end|>
```

출력 JSON이나 필드값을 자동 교정하지 않았다. tool call은 실행하지 않았다. **이 smoke는 서비스 전송·생성·보존 검사이며 공학 정확도 평가, 안전성 승인 또는 새 일반화 점수가 아니다.** 전체 DEV/legacy benchmark는 재실행하지 않았다.

## CPU/mock 및 운영 확인

`test_service.py` 4개 test가 통과했다: 무인증 401·잘못된 토큰 403, 준비 전 503 및 실패한 load의 readiness 유지, 준비 후 200, 입력 schema/예산 초과 거부, 최대 body 413, 중복 동일 요청 재사용·변경 payload 409·busy 429, 요청 간 message 분리, 실제 generate bridge의 request-local tensor 및 past_key_values 미전달, gradient 비활성. 실제 native processor로 4096 경계와 예약 token 초과, gold metadata, 중복 JSON key, NaN/무한수, native delimiter 거부도 확인했다. mock 실패 시험의 의도된 traceback은 `cpu_tests.log`에 있으며 실제 서버 load 실패가 아니다.

시작 script 재실행은 기존 PID 19386를 반환했다. 서버는 독립 session(setsid)에 있으며 stdin/stdout이 SSH와 분리됐다. bootstrap FD9는 시작 script에서 닫고 launcher는 필요한 서비스 lock FD만 전달한다. 실제 `/proc/19386/fd` 검사에서 `.bootstrap.lock` 상속 없음, 별도 `/root/.config/dorilab/inference.lock` 상속을 확인했다. FD9 번호 자체는 Python이 pipe로 재사용하므로 번호 존재만으로 상속을 판단하지 않았다. 타 프로세스가 8080을 점유하면 launcher는 충돌 오류로 반환하며 종료하지 않는다.

기존 bootstrap의 `inference/start_inference.sh` 발견 및 `/health` polling 지점을 그대로 이용한다. `/start.sh`, `/pre_start.sh`, Start Command 및 bootstrap 본문은 변경하지 않았다. bootstrap 전체를 다시 실행하지 않았다.

## API 의존성과 인증

추가된 패키지는 fastapi 0.141.1, starlette 1.7.0, uvicorn 0.54.0뿐이다. 기존 torch/Transformers/PEFT 및 나머지 설치 패키지의 버전을 변경하거나 venv를 재생성하지 않았다. `pip check`는 전후 모두 통과했다. API dependency closure는 `requirements-api.lock`에 고정했고 시작 시 `restore_api.py`가 빠진 패키지만 `--no-deps`로 복구한다. 기존 버전과 lock이 다르면 GPU 환경을 변경하지 않고 실패한다.

`/version`, 생성, 결과 조회에 Bearer 인증을 적용했다. 토큰은 `/root/.config/dorilab/inference.token`(600), 디렉터리 700에 생성했다. 응답·로그·보고서에 토큰 값을 출력하지 않았고 workspace에 secret을 백업하지 않았다. Mac SSH 교환은 `mac/fetch_token.sh`와 `MAC_CONNECTION_HANDOFF.md` 참조.

결과 및 idempotency key 조회는 live boot 내 24시간, admission은 boot당 256개로 제한된다. 용량이 끝나면 429이며 운영자 관리가 필요하다. 디스크 증거는 자동 삭제하지 않는다. 재기동하면 API lookup은 새 boot로 바뀐다. 현재 런타임의 일부 Qwen 커널은 기존 PyTorch fallback을 사용한다는 로그가 있으며 최적화 패키지를 추가하거나 런타임을 변경하지 않았다.

## 파일 및 명령

- 서버 로그: `/workspace/dorilab/inference/run/server-20260927T053108Z.log`
- PID 정보: `/workspace/dorilab/inference/run/service.json`
- 모델 receipt / warmup: `/workspace/dorilab/inference/run/8a4e587f-75e2-446e-bc4c-1ba32964a7ea`
- HTTP smoke 원문 및 응답·poll 기록: `/workspace/dorilab/inference/artifacts/http-smoke-20260927T053310Z`
- 종료 token 포함 원문: `/workspace/dorilab/inference/artifacts/http-smoke-20260927T053310Z/raw_output.txt`
- 서버가 저장한 입력/결과: `/workspace/dorilab/inference/run/8a4e587f-75e2-446e-bc4c-1ba32964a7ea/7385506b-d72c-4a7b-9503-b86575175c1a.input.json`, `/workspace/dorilab/inference/run/8a4e587f-75e2-446e-bc4c-1ba32964a7ea/7385506b-d72c-4a7b-9503-b86575175c1a.json`
- 최종 확인: `artifacts/final_verification.json`
- 검사: `artifacts/cpu_tests.log`, `artifacts/duplicate_start.json`
- 의존성 기록: `artifacts/packages.before.json`, `packages.after.json`, `package_diff.json`, `pip.freeze.before.txt`, `pip.freeze.after.txt`, `pip.check.before.txt`, `pip.check.after.txt`, `api_install.log`, `restore-*`
- 상세 HTTP 계약: `API_CONTRACT.md`
- Mac Docker/SSH 연결: `MAC_CONNECTION_HANDOFF.md`, `mac/compose.yaml`, `mac/client.py`, `mac/fetch_token.sh`

시작(이미 떠 있으면 동일 서비스 반환):

```bash
bash /workspace/dorilab/inference/start_inference.sh
```

상태:

```bash
bash /workspace/dorilab/inference/start_inference.sh --status
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/readyz
nvidia-smi
```

Mac Docker는 제공한 SSH tunnel container와 앱의 network namespace를 공유하고 파일 기반 secret을 읽는다. 외부 SSH host/port/key는 Mac에서 실제 연결값을 넣어야 한다. **RunPod 내부 검증만 완료했고 Mac end-to-end 접속은 미검증이다.** 서비스는 켜 두었다. Pod lock 조작, STOP, DELETE, 새 학습, 양자화, adapter merge는 실행하지 않았다.


## 후속 수정: 컨테이너 재생성 시 자동 시작 hook

영구 wrapper `/workspace/dorilab/runpod_start.sh`를 추가했다. 이 wrapper는 매 부팅마다 `/pre_start.sh`를 `/workspace/dorilab/runpod_post_start.sh`에 연결한 뒤 이미지의 `/start.sh`를 실행한다. 기존 SSH/Jupyter/nginx 초기화와 bootstrap → inference → health 확인 경로를 유지한다. 기존 `/post_start.sh`만 연결하는 Start Command의 불일치를 해결하기 위한 변경이다.

RunPod 콘솔에서 해당 Pod의 Start Command를 아래 값으로 변경해야 한다.

```text
/bin/bash /workspace/dorilab/runpod_start.sh
```

**현재 적용 범위: wrapper 작성 및 검증 완료, 콘솔 Start Command 변경은 미완료.** 관리 API 읽기 요청이 HTTP 403으로 거부되어 control-plane 설정을 직접 수정하지 못했다. 현재 컨테이너의 기존 `/pre_start.sh` 연결은 정상이며 서비스 PID 19386, `/health`·`/readyz` 200을 유지했다. 실제 Pod 재시작은 실행하지 않았다.

`test_startup_hook.py`로 hook이 없는 새 파일시스템, 반복 실행, 무관한 기존 hook 보호를 CPU/mock 검사했고 통과했다. 실제 환경에서는 `bash /workspace/dorilab/runpod_start.sh --check`로 읽기 전용 검증을 통과했다. 상세 증거: `artifacts/startup_hook_fix/receipt.json`, `cpu_test.log`, `START_COMMAND.txt`.
