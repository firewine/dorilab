# 로컬 RunPod 연결 저장·적용 수정 결과

작성일: 2026-10-09. 범위: Mac Docker 로컬 연결 도구·설정 팝업. Site/Render/Neon 배포, 학습, 원격 패키지·모델·Pod 변경은 수행하지 않았다.

후속 결과: 이 문서 아래의 runtime 대기 상태와 generation 0건은 **연결 수정 당시**의 기록이다. 이후 별도 공개 합성 3건 검증과 사용자 승인으로 복구 runtime을 등록하고 로컬 API/worker에 적용해 **LIVE / READY**를 확인했다. 이전 원출력·receipt와 이 보고서는 보존한다. 최신 결과는 [실행환경 승인·적용 결과](RUNPOD_RUNTIME_ALIGNMENT_RESULT_20261009.md)를 따른다.

## 결과와 원인

기존 팝업은 HostName/포트를 파일에 저장하고 호스트 키만 확인했다. 실행 중인 API/worker는 DEMO였고 llm-tunnel이 없어서, 설정을 저장해도 앱은 LOCAL_ONLY에 남았다. SSH 자체의 인증 실패와는 다른 문제였다.

현재는 **저장 · LIVE 연결**로 로컬 터널과 LIVE 실행 모드를 적용한다. 실제 `205.196.144.74:11284`에서 기존 `~/.ssh/id_ed25519`, root, 이미 확인된 host key로 strict SSH 인증을 통과했다. Docker 내부 `http://llm-tunnel:18080`을 통해 원격 loopback `127.0.0.1:8080`의 `/healthz`·`/readyz`·Bearer `/version`이 모두 200이었다. 연결 정보를 저장한 뒤 팝업을 닫아도 LIVE가 유지된다.

앱은 **LIVE_CONNECTED / GENERATION_PENDING_RUNTIME_RECEIPT**다. 승인 model receipt `b96e7289…a847`과 복구 서버 receipt `7e8f301c…4f0a`의 차이를 실제 파일에서 비교했다. boot_id를 제외한 모델 실행 계약의 유일한 차이는 `runtime.tokenizers: 0.23.2 → 0.23.3`이다. 모델·어댑터와 나머지 receipt는 동일하지만 기존 exact receipt 기준은 보존해 **MODEL_RELEASE_MISMATCH**로 생성 요청을 보류한다. `/readyz` 200만으로 승인된 릴리스라고 처리하지 않았다.

이번 새 generation은 **0건**이다. 모델 답변·현재 runtime의 공학 적합성·LIVE 자동 시연 완료를 검증했다고 주장하지 않는다.

## 데이터 흐름

1. 팝업 PUT은 두 연결값을 `var/connection/runpod.env`에 저장한다. 처음 보는 host key만 별도 지문 확인 후 신뢰한다.
2. 인증·CSRF·프로젝트 권한·saved target·known_hosts를 검사한 POST `runpod-connection/apply`가 UUID/host/port/시각으로 제한된 원자적 요청 파일을 만든다.
3. `scripts/dev.sh up`이 시작한 Mac 관리 프로그램은 요청을 한 번만 처리한다. 기존 key/agent로 SSH 인증, 기존 서버 token의 로컬 파일 동기화, Docker tunnel·worker·API의 LIVE 적용을 수행한다. DB·migration은 재실행하지 않는다.
4. heartbeat·적용 결과를 파일로 읽고, 기존 worker가 DB에 보존하는 remote 상태를 GET으로 표시한다. key 확인, 적용 당시 SSH 연결, 앱 모드, 현재 모델 readiness를 구분한다. 창 열기·닫기·재조회는 모델 실행이 아니다.

Mac 프로세스는 현재 사용자 `launchd`의 프로젝트별 label에 등록한다. 터미널/Codex 명령 종료로 watcher가 사라지던 문제도 실제 브라우저 검증 중 발견해 수정했다. 시스템 LaunchAgent 설치·sudo·Docker socket API·앱의 private key 접근은 없다. `down`은 해당 프로젝트 label만 제거한다.

검토 admission과 연결 적용은 DB advisory lock으로 직렬화한다. 진행 중이거나 QUEUED인 검토는 연결 교체를 막는다. 중복 apply ID를 재실행하지 않고, 최근 인증 receipt가 있는 같은 LIVE 설정은 worker를 재시작하지 않는다. 인증 실패·원격 불가·probe 만료 뒤에는 같은 주소에서도 사용자가 저장해 복구할 수 있다. 중단된 APPLYING은 `UNKNOWN_LOCAL_APPLY_OUTCOME`으로 보존하며 자동 재생하지 않는다.

## 변경 파일

- `compose.yaml`, 신규 `compose.live.yaml`: 로컬 파일 채널의 권한 범위와 명시적 LIVE override.
- `scripts/dev.sh`, 신규 `scripts/local-connection.sh`: 프로젝트별 Mac 프로세스 관리, strict SSH·로컬 token 동기화·Compose 적용.
- 신규 `services/common/dorilab/local_connection.py`: 제한된 요청·heartbeat·결과 계약과 직렬화.
- `services/common/dorilab/api.py`, `worker.py`: 인증된 적용 API와 실행 중 변경 방어, worker admission 정지.
- `apps/web/app.js`, `index.html`: 저장·실제 적용 연동, 별도 상태 카드, 닫기·재열기·중복 클릭 처리.
- 신규 `tests/test_local_connection_apply.py`, `test_local_connection_controller.py`, `local_connection_ui.cjs`: DB/API·호스트 도구·실제 UI handler의 실패/복구 회귀.
- `README_LOCAL_DOCKER.md`, `docs/ADR_DOCKER_SSH_LOCAL.md`, `STATUS.md`, `STATUS.json`, 이 보고서: 실제 동작과 남은 릴리스 차이 기록.

## 이번 실행 검증

| 검사 | 결과 |
|---|---|
| Bash 문법 / LIVE Compose config / 이미지 build | 통과 |
| `./scripts/dev.sh test`, 격리 PostgreSQL/mock inference | **233 passed / 1 warning / 45.67초** |
| 실제 app.js 설정 handler, network 없는 Node Docker | 통과: 저장·적용·중복·오프라인 관리 프로그램·host key 확인·실패·다른 target·동일 연결 유지 |
| 권한/CSRF, 검토 실행 중 교체 금지, 오래된 probe·동일 주소 인증 실패 복구 | 격리 회귀 통과 |
| Mac launchd 등록/자신의 label만 제거, command 인자·경로 공백 | 격리 회귀 통과; 실제 watcher 지속 실행 확인 |
| 실제 브라우저 저장 → LIVE, 닫기/재열기/페이지 reload, 같은 설정 재저장 | 통과; 같은 worker container ID 유지 |
| strict SSH / Docker forwarding / readiness / authenticated version | 통과; generation은 실행하지 않음 |
| 실제 DB / tunnel host publication | 없음; API만 127.0.0.1:18000 |
| API/worker/DB private key, Docker socket, privileged/host network | 없음; tunnel의 DB/Artifact 접근 없음 |
| 기존 업무 DB | 프로젝트 5, 첨부 28, 검토·ModelRun 각 24, 사람 결정 5 그대로 |
| 실제 등록 Artifact bytes/size/SHA256 | **28/28 일치** |

warning은 Starlette testclient의 anyio alias deprecation이다. 테스트 DB의 두 duplicate key 로그는 기존 중복 등록 거부 검사에서 발생했으며 최종 테스트 실패가 아니다. 생성 수·보존 건수는 실제 로컬 DB에서 읽었다. 전체 업무 테이블 digest의 이번 전후 비교나 down/up 전체 복원 시험을 새로 수행한 것은 아니다.

실행 OS는 macOS 27.0.1 arm64, Docker context는 `desktop-linux`, Engine 29.8.0, Compose 5.5.1, 컨테이너는 Linux aarch64다. context는 변경하지 않았다.

## 사용 순서와 남은 한 단계

현재 `http://localhost:18000`을 새로고침하고 **RunPod 연결**을 열면 적용 상태를 볼 수 있다. 다음 Pod 주소/외부 SSH 포트 변경은 두 값을 입력한 뒤 **저장 · LIVE 연결**만 누른다. 최초 관리 프로그램이 없을 때만 `./scripts/dev.sh up`으로 시작한다. 원격 서비스가 없으면 설치로 자동 진행하지 않으며 `deploy-runpod`의 기존 절차를 따른다.

남은 한 단계는 복구 runtime의 버전 정합이다. 기존 승인 baseline을 보존하면서 현재 0.23.3 runtime을 별도 후보로 검증·승인하거나, 서버에서 승인된 0.23.2를 복원해야 한다. 이를 이번 연결 수정에 끼워 넣어 receipt 검사를 완화하거나 원격 패키지를 바꾸지 않았다.

실행 기록: `var/run-records/local-runpod-20261009/`. `final-tests.log`, `final-build.log`, `local_verification.json`, `boundary_verification.json`, `receipt_diff.json`, `current_model_receipt.json`을 보존한다. token·private key·DB password를 기록에 포함하지 않는다. 원문/결정은 기존 `var/artifacts`, PostgreSQL named volume에 남는다. API·컨테이너 경계 검증 화면은 `connection-status.jpg`다.
