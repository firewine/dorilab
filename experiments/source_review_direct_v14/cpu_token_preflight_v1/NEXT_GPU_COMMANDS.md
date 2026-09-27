이 실행 준비는 CPU 사전검사 PASS 후 기존 로컬 가중치 경로가 없어 중단된 상태이다. 가중치는 다운로드하지 않는다. 기존 `GPU_BATCH_COMMANDS.md`의 생성 조건은 유지하며, 아래 새 runner는 CPU/GPU 입력 일치 검사와 실패 보존을 추가한 실행 경로이다. 기존 runner는 보존했다. 생성 코드 부분은 byte 단위로 같다.

가중치 경로 확인, 기존 Pod 상태 확인, 정확한 Transformers commit과 기존 GPU runtime 확인 후에만 실행한다. 이번 작업에서는 아래 GPU 명령을 실행하지 않았다. SR14_SNAPSHOT과 SR14_GPU_PYTHON은 확인된 실제 경로를 넣어야 하며 현재 경로 존재를 추정하지 않는다.

```bash
export SR14_STAGE=/workspace/dorilab/experiments/source_review_direct_v14/cpu_token_preflight_v1
export SR14_CPU_REFERENCE="$SR14_STAGE/runs/linux_cpu_01"
export SR14_GPU_OUTPUT=/workspace/dorilab/experiments/source_review_direct_v14/runs/direct_v14_checked_01
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# 기존 로컬 snapshot과 고정 GPU Python 경로가 확인된 뒤 지정한다.
# export SR14_SNAPSHOT=...
# export SR14_GPU_PYTHON=...
CUDA_VISIBLE_DEVICES=0 "$SR14_GPU_PYTHON" "$SR14_STAGE/scripts/execute_once.py" \
  --snapshot "$SR14_SNAPSHOT" --cpu-preflight "$SR14_CPU_REFERENCE" \
  --output "$SR14_GPU_OUTPUT" --gpu-python "$SR14_GPU_PYTHON"
```

wrapper는 `*_control/run.log`, `COMPLETION.json`, `SHA256.json`과 생성한 원본 출력·입력·manifest를 보존한다. 8개 ID의 정확한 일회 저장과 OUTPUT_SEAL 일치를 확인해야 COMPLETE이다. 실패 시 재시도나 덮어쓰기를 하지 않는다. 기존 STOP script의 legacy 절차 `runpodctl stop pod "$RUNPOD_POD_ID"`가 현재 CLI에서 확인된 명령이다. STOP 전 다른 승인 작업 부재를 재확인한다. DELETE/TERMINATE는 사용하지 않는다.

생성이 완료되고 원본 output hash 봉인·회수·GPU 종료가 끝난 뒤, 별도 CPU 환경에서 실행할 비교 명령:

```bash
CUDA_VISIBLE_DEVICES='' "$SR14_CPU_PYTHON" "$SR14_STAGE/scripts/compare_results_extended.py" \
  --run "$SR14_GPU_OUTPUT"
```

SR14_CPU_PYTHON은 실제 확인한 CPU Python 경로를 사용한다. macOS 연결이 없으면 회수 여부와 실제 Linux 실행 환경을 명시한다. 기존 v13 점수는 읽기만 하며 재채점하지 않는다. JSON/check_answer/field error/두 Action 지표/reason 평가 상태/reference 3상태/strict/시간/token 수를 분리한다. 새 모델 출력이 없는 현재는 비교를 실행하지 않는다.
