# Mac / Docker 연결 인계

RunPod 내부 검증만 완료했다. 실제 Mac, Docker Desktop, 외부 SSH 경로는 아직 시험하지 않았다. 서버는 RunPod의 `127.0.0.1:8080`에만 열려 있다. RunPod HTTP proxy나 공인 8080 포트 공개는 필요 없다.

## 연결값

RunPod 콘솔에서 현재 Pod의 **직접 SSH host/IP와 외부 매핑 SSH port**를 확인한다. 이 작업에서는 그 값을 추측하거나 Pod 설정을 바꾸지 않았다. Mac에서 기존에 검증한 SSH host key를 `known_hosts`에 등록하고 아래 변수에 실제 값을 넣는다. 새 host key는 신뢰할 수 있는 콘솔 경로에서 fingerprint를 대조한다. `StrictHostKeyChecking=no`를 사용하지 않는다.

```bash
export DORILAB_SSH_HOST='ACTUAL_RUNPOD_SSH_HOST'
export DORILAB_SSH_PORT='ACTUAL_RUNPOD_SSH_PORT'
export DORILAB_SSH_KEY="$HOME/.ssh/your_runpod_key"
export DORILAB_KNOWN_HOSTS="$HOME/.ssh/known_hosts"
export DORILAB_TOKEN_FILE="$HOME/.config/dorilab/inference.token"
```

`inference/mac/` 폴더를 Mac으로 복사한다. 토큰은 파일에 포함되어 있지 않다. `mac/fetch_token.sh`를 Mac에서 실행하면 검증된 SSH 연결의 stdout을 권한 600 임시 파일로 직접 받아 검증 후 원자적으로 교체한다. 토큰을 터미널, shell history, 명령 인자, `.env`, Docker image, Git, `/workspace`에 넣지 않는다. `set -x`는 사용하지 않는다.

```bash
bash mac/fetch_token.sh
```

서버 토큰 위치는 `/root/.config/dorilab/inference.token`이며 디렉터리는 700, 파일은 600이다. 기존 토큰은 재사용한다. `/root`가 소멸하는 Pod 재생성 시 토큰은 새로 생성되므로 SSH로 다시 받아야 한다. workspace에 secret 백업은 없다.

## Mac 프로세스에서 직접 연결

다음 SSH 명령은 Mac terminal에서 계속 실행한다. Mac의 loopback 18080이 Pod의 loopback 8080으로 전달된다.

```bash
ssh -NT -p "$DORILAB_SSH_PORT" -i "$DORILAB_SSH_KEY" \
  -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -L 127.0.0.1:18080:127.0.0.1:8080 "root@$DORILAB_SSH_HOST"
```

별도 terminal에서 추가 generation 없이 readiness와 인증을 확인한다.

```bash
curl --fail http://127.0.0.1:18080/health
python3 mac/client.py --base-url http://127.0.0.1:18080 \
  --token-file "$DORILAB_TOKEN_FILE"
```

## Mac Docker에서 연결

제공한 Compose 예시는 SSH tunnel container와 client가 동일한 network namespace를 공유한다. client의 주소는 `http://127.0.0.1:8080`이다. host의 loopback과 container loopback을 혼동하지 않도록 Docker 안에서 SSH tunnel을 연다. Mac 및 Pod의 외부 인터페이스에 포트를 publish하지 않는다.

```bash
cd mac
docker compose build tunnel
docker compose up -d tunnel
docker compose run --rm client
```

SSH private key와 검증된 known_hosts는 read-only mount한다. 이 예시는 SSH가 비대화식으로 인증할 수 있어야 한다. 암호화된 key라면 Docker Desktop의 SSH-agent forwarding 구성을 별도로 적용하거나 위 Mac native SSH 경로를 사용한다. key passphrase를 환경변수나 image에 넣지 않는다. 현재 예제 Docker image는 Mac에서 빌드하며 RunPod GPU Python을 변경하지 않는다.

사용자 앱을 연결할 때 Compose 서비스에 `network_mode: service:tunnel`을 적용하고 API URL을 `http://127.0.0.1:8080`으로 설정한다. 서비스 토큰은 Compose secret으로 필요한 앱에만 전달하고 `/run/secrets/dorilab_token` 파일을 읽어 `Authorization: Bearer …` header를 구성한다. 토큰 값은 인자나 로그에 출력하지 않는다. 파일 기반 Compose secret은 host 파일 mount이므로 Mac 원본 파일의 권한 600도 유지한다. 근거: [Docker Compose network_mode](https://docs.docker.com/reference/compose-file/services/#network_mode), [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).

연결 확인의 기본 동작은 `/version` 조회뿐이다. 별도 승인된 공개/합성 입력을 실행하려면 `client.py --request-file <request.json>`을 사용한다. 모든 요청은 새로운 `request_id`, allowlist의 `contract_id`, 단일 native JSON 문자열 `user`, 최대 384의 `max_new_tokens`를 사용한다. 202의 ID와 boot_id를 기록하고 GET으로 완료를 조회한다. 429에는 대기 후 같은 request_id로 재시도하며, 503은 readiness부터 확인한다. boot_id가 바뀌면 이전 작업을 무조건 재실행하지 않는다. 모델 JSON 오류를 자동 교정하거나 tool call을 자동 실행하지 않는다.

전체 API와 보존 범위는 `API_CONTRACT.md`를 참조한다. 서버는 boot당 최대 256개 작업을 받으며, 조회/중복 방지 기간은 24시간이다. 오류나 용량 소진 시 운영자 확인을 거친다. 이 문서는 Mac 접속 성공이나 공학 정확도 검증을 주장하지 않는다.


## 후속 수정: 컨테이너 재생성 시 자동 시작 hook

영구 wrapper `/workspace/dorilab/runpod_start.sh`를 추가했다. 이 wrapper는 매 부팅마다 `/pre_start.sh`를 `/workspace/dorilab/runpod_post_start.sh`에 연결한 뒤 이미지의 `/start.sh`를 실행한다. 기존 SSH/Jupyter/nginx 초기화와 bootstrap → inference → health 확인 경로를 유지한다. 기존 `/post_start.sh`만 연결하는 Start Command의 불일치를 해결하기 위한 변경이다.

RunPod 콘솔에서 해당 Pod의 Start Command를 아래 값으로 변경해야 한다.

```text
/bin/bash /workspace/dorilab/runpod_start.sh
```

**현재 적용 범위: wrapper 작성 및 검증 완료, 콘솔 Start Command 변경은 미완료.** 관리 API 읽기 요청이 HTTP 403으로 거부되어 control-plane 설정을 직접 수정하지 못했다. 현재 컨테이너의 기존 `/pre_start.sh` 연결은 정상이며 서비스 PID 19386, `/health`·`/readyz` 200을 유지했다. 실제 Pod 재시작은 실행하지 않았다.

`test_startup_hook.py`로 hook이 없는 새 파일시스템, 반복 실행, 무관한 기존 hook 보호를 CPU/mock 검사했고 통과했다. 실제 환경에서는 `bash /workspace/dorilab/runpod_start.sh --check`로 읽기 전용 검증을 통과했다. 상세 증거: `artifacts/startup_hook_fix/receipt.json`, `cpu_test.log`, `START_COMMAND.txt`.
