# Qwen 검색 제어기

현재 GPU에 상주하는 Qwen 한 벌로 검색 계획과 RC3 검토를 순차 수행한다. `/v1/generations`에 서비스 소유의 `memory_controller_qwen_v1` 계약을 추가했다. 해당 계약만 PEFT `disable_adapter()` 안에서 실행하고, 종료 시 RC3 adapter가 다시 활성화됐는지 확인한다. 다른 계약은 기존 RC3 경로다. 두 경로 모두 worker 1개/generation 1개, BF16/SDPA, greedy, thinking=false, native EOS, 전체4096/응답384 제한을 사용한다.

고정 prompt와 hash는 `planner_contract.py`에 있다. 임의 system/adapter/model 파라미터는 받지 않는다. 결과의 `execution_mode`와 `adapter_applied`로 경로를 구분한다. 요청 간 KV 공유는 추가하지 않았다.

## 제어 흐름

1. 신뢰된 프로젝트 권한과 정확한 unit/configuration/run scope로 baseline 근거 수집.
2. Qwen에 질문, 후보, 검색 이력과 원문 조회 결과 전달.
3. Qwen은 `search`, `inspect`, `finish` 중 하나의 JSON 계획 반환.
4. 코드가 schema를 검증하고 pool 검색 또는 이미 검색된 ID의 원문 조회만 수행.
5. 같은 snapshot/source hash의 근거를 기존 RC3 `observations`에 전달.

모델 출력으로 프로젝트/scope를 변경하지 않는다. shell, URL fetch, 임의 경로 지정, 기억 쓰기·삭제 도구는 제공하지 않는다. 문서의 action도 데이터로만 취급한다. 없는 ID나 잘못된 JSON은 자동 교정하지 않는다.

검색은 baseline 포함 최대3회, 판단은 기본6회, 시간은 기본90초다. timeout 이후에도 이미 접수된 Qwen job은 서버에서 실행 중일 수 있다. 이때 다음 생성은 기존429로 거부되며 자동 취소·재제출하지 않는다. trace의 accepted ID로 상태를 확인한다. 동기 파일 I/O까지 강제로 중단하는 hard realtime 보장은 아니다.

잘못된 계획, API 오류, 반복 질의·조회, 횟수·시간 한도는 baseline으로 복귀하며 `fallback=true`와 이유를 남긴다. 기억이 도중에 바뀌면 ConflictError로 거부한다. sufficient/insufficient/conflict는 제어기의 참고 판단이며 공학 승인이나 정확성 보증이 아니다. 원문 조회 없이 sufficient가 반환되면 별도 제어 상태를 insufficient로 낮춘다. 모델 원문은 trace에 그대로 보존한다.

근거 텍스트는 자르지 않는다. planner context에서 제외된 후보는 omitted_candidates에 표시한다. 최종 입력은 native token 검사를 통과해야 한다. 생성 답변을 기억에 자동 저장하지 않으며 제어기 응답 캐시도 없다. 기존 프로젝트/snapshot별 검색 캐시만 사용한다.

## 실행

query/prepare/generate의 기본 제어기는 `qwen`이다. 직접 검색은 `--controller off`, 네트워크 없는 규칙 제어기는 `--controller rules`로 선택한다. rules는 의미적 충분성을 판정하지 않는다.

```bash
cd /workspace/dorilab
/root/venvs/dorilab-tournament/bin/python -m project_memory \
  --store /workspace/dorilab/memory_data --project synthetic-lme-v2 \
  query project_memory/examples/packet.json --top-k 3 --max-bytes 6500 \
  --controller qwen --planner-trace-dir /workspace/dorilab/project_memory/artifacts/manual-plan-01
```

최종 RC3 검토까지:

```bash
/root/venvs/dorilab-tournament/bin/python -m project_memory \
  --store /workspace/dorilab/memory_data --project synthetic-lme-v2 \
  generate project_memory/examples/packet.json --top-k 3 --max-bytes 6500 \
  --controller qwen --planner-trace-dir /workspace/dorilab/project_memory/artifacts/manual-plan-02 \
  --native-check --token-file /root/.config/dorilab/inference.token \
  --output-dir /workspace/dorilab/project_memory/artifacts/manual-review-02
```

trace-dir/output-dir는 새 경로여야 한다. trace-dir 생략 시 `--store/_planner_traces/<UUID>`에 기록한다. 각 계획의 입력, service version, accepted ID, 종료 토큰 포함 결과를 보존한다. 키 값은 기록하지 않는다. trace는 프로젝트 근거를 포함하는 운영 데이터이므로 접근권한과 보존 정책을 관리해야 한다.

Mac에서는 기존 SSH 터널에 맞게 `--planner-url`, `--planner-token-file`을 지정하고 `--native-check`를 생략한다. 최종 검토용 `--base-url`, `--token-file`도 지정한다. 외부 LLM이나 별도 API 키는 필요하지 않다. Mac 실기 연결은 별도 검증 대상이다.

## 검증

`python -m unittest project_memory.test_memory project_memory.test_controller -v`는 합성 입력으로 재검색·원문 확인·권한 격리·오류 복귀·시간/반복 제한·동시 갱신 거부를 검사한다. 작은 실제 PEFT 모델을 CPU에서 사용해 base→RC3 전환과 예외 발생 후 adapter 복구도 확인한다. 실제 Qwen의 연결 증적은 `artifacts/controller_v1`에 남긴다. 공식 LongMemEval-V2 점수는 측정하지 않는다.
