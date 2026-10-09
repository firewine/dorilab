# DoriLab 로컬 Docker MVP

DoriLab의 BM1 검토 한 흐름을 Mac Docker Compose에서 실행한다. 업무 DB·Artifact·사람 결정은 로컬에 보존하고, LIVE 추론만 기존 RunPod의 loopback API로 SSH forwarding한다.

화면의 모델 서비스 이름은 **Local LLM**, Baseline은 **기준점 / 형상 기준점**으로 표시한다. 현재 GPU 추론은 RunPod에서 실행된다. 용어의 의미와 추가 검토 후보는 [화면 용어 검토](Docs/UI_TERMINOLOGY_KO.md)에 정리했다.

## 빠른 시작

원격 없이 로컬 기능을 확인하려면 호스트 Python/Node 설치가 필요 없다.

```sh
cp .env.example .env          # .env가 아직 없을 때만
./scripts/dev.sh setup
./scripts/dev.sh up --demo
```

기본 브라우저 주소는 `http://localhost:8000`이다. 초기 확인 당시 이 개발 Mac의 8000을 다른 서비스가 사용하고 있어 setup 시 고급 override `DORILAB_APP_PORT=18000`을 적용했고, 그 파생 설정을 유지한 현재 주소는 `http://localhost:18000`이다. 충돌 process를 종료하거나 기존 Compose의 port를 바꾸지 않았다.

8개 화면 모두 `mockup/DoriLab_SE_Workbench.html`의 원본 CSS와 배치를 사용한다. 두 번째 화면에서 KASA/ECSS/NASA 체계를 미리보고, 승인권자가 프로젝트 프로파일을 적용하며, 기준 문서 등록과 테일러링 후보·승인 이력을 PostgreSQL에 저장할 수 있다. 세 번째 화면의 V 모델과 제품 요구사항 매트릭스는 서버 요구사항 레코드와 Claim revision을 읽고, 각 노드의 상위 요구·검증 방법·담당·Claim·기준점을 상세 모달로 연다. 네 번째 화면은 9개 회의의 준비·성공조건을 실제 서버 기록으로 평가하고, reviewer/approver의 기술검토 결정과 approver의 사업 단계 전환 결정을 분리해 저장한다. 다섯 번째 화면은 목업의 14단계 시험 rail, Evidence Board와 2열 BM1 검토 구조를 유지하면서 Claim scope, Artifact/Evidence, 문서 RAG, ContextSnapshot, Job/Validation, 사람 결정, 자료 요청과 서버 Blackboard를 연결한다. 업로드한 PDF text layer와 UTF-8 text/Markdown/JSON/CSV는 원본 hash를 유지한 채 page/section/line locator가 있는 청크로 저장되고, PostgreSQL FTS 결과의 rank·score·선택/제외 사유·parser/index receipt가 다음 Snapshot에 고정된다. Blackboard는 제안·이견, 공용 WorkItem, 객체 의존관계와 payload가 있는 BoardEvent를 PostgreSQL에 보존한다. 모델 결과는 확정 상태가 아니라 `PROPOSED` contribution이며 사람 결정과 별도로 처분된다. BM1 실행은 11개 노드의 고정 서버 graph로 진행되고 노드 attempt와 snapshot SHA256을 PostgreSQL에 남긴다. 유효 출력 뒤에는 `WAIT_HUMAN`에서 정지하고 사람 결정이 저장된 같은 transaction에서 `RESUME → COMPLETE`로 이어지며 모델을 다시 호출하지 않는다. 여섯 번째 화면은 제품·프로세스 검증 매트릭스와 종결 상태판을 제공하며, 데이터 품질 평가는 reviewer/approver, 공식 Claim 종결은 approver 권한으로 별도 저장한다. 종결 시 현재 Claim/project version, 근거, 출력 검증, 사람 수용, 판정, 자료 요청, 품질과 TRB 승인을 다시 검사한다. 일곱 번째 화면은 DRAFT 형상 변경과 승인권자의 CCB 결정을 분리하고, 적용 시 프로젝트 version 증가와 ReviewJob STALE 처리를 같은 transaction에서 수행한다. 이전 원출력·결정·종결 이력은 당시 기준점으로 보존하며 이전 version 명령은 409로 거부한다. 마지막 화면은 PostgreSQL의 Snapshot·ModelRun·담당자 결정 집계, 검색 가능한 AuditEvent, hash가 기록된 보고서와 읽기 전용 감사 JSON 다운로드를 제공한다. 복원 계약이 없는 JSON 가져오기와 파괴적 초기화는 비활성화했다. BM2와 NTR은 아직 결과 계약이 없어 `NOT_IMPLEMENTED`로 명시하며 가상 결과를 저장하지 않는다. “설계문서 n장”은 보존된 원문 Markdown의 해당 장을 읽고 원본 파일을 내려받는다. 역할을 바꾸면 서버 session과 membership이 다시 적용된다. SIMULATED/REPLAY 결과는 구조와 저장 흐름 확인용이며 LIVE나 모델 정확도 증거가 아니다. RAG v1은 lexical FTS 수직 경로이며 OCR·표/그림 구조화·embedding/reranker와 dependency 기반 부분 재검토는 후속 단계다.

완료된 검토는 “저장된 검토”에서 다시 열고 Markdown 보고서를 만들 수 있다. `REQUEST_EVIDENCE` 결과는 기존 EvidenceRequest와 Blackboard `EVIDENCE_REQUEST` WorkItem으로 함께 생성된다. Evidence 제출은 WorkItem의 `WAITING_REVIEW`, reviewer의 수용은 `COMPLETED`와 원래 ReviewJob의 선택적 `STALE` 처리로 연결된다. 사람 결정에는 원출력을 바꾸지 않는 별도 수정 초안 JSON을 저장할 수 있다. 상세 endpoint는 [API_CONTRACT.md](Docs/API_CONTRACT.md)에 정리돼 있다.

문서 RAG는 **시험 워크스페이스 → 자료 등록**에서 원문을 선택해 `업로드 · 파싱 · 색인`을 누른 뒤 사용한다. 완료 receipt와 청크 수를 확인하고, 워크스페이스의 **문서 RAG** 카드에서 검색어를 입력한다. 선택된 청크의 원문 위치·hash·점수를 검토한 다음 `검토 실행`을 누르면 현재 retrieval run이 직접 선택 Evidence와 함께 새 ContextSnapshot에 들어간다. 검색 결과는 자동 수용되지 않으며, 질문이나 프로젝트 version이 바뀌면 기존 retrieval은 재사용하지 않는다.

## LIVE 연결

앱 상단의 **RunPod 연결**을 누르고 RunPod Connect의 `SSH over exposed TCP`에 표시된 두 값만 입력한다.

최초 실행은 `./scripts/dev.sh up` 또는 `./scripts/dev.sh up --demo`로 로컬 앱과 연결 관리 프로그램을 준비한다. 이후에는 주소 변경마다 셸 명령을 다시 실행하지 않아도 된다.

1. HostName 또는 IP 주소와 외부 SSH 포트를 입력하고 **저장 · LIVE 연결**을 누른다.
2. 처음 보는 호스트 키는 팝업의 SHA256 지문을 RunPod의 별도 인증된 콘솔 정보와 대조한 뒤 **지문 확인 후 신뢰 (yes)**를 한 번 누른다. 변경된 키는 자동 교체하지 않는다.
3. 팝업에서 **연결 설정 적용 / 현재 앱 모드 / SSH 터널 / 현재 추론 API·모델**을 구분해 확인한다. 창을 닫아도 연결 적용은 계속된다.
4. Pod 주소나 외부 SSH 포트가 바뀌면 같은 팝업에서 두 값만 바꾸고 저장한다. 같은 주소의 인증이 실패하면 저장으로 기존 서버 토큰을 다시 동기화할 수 있다. 최근 인증 연결이 정상인 같은 설정은 재시작하지 않는다.

```sh
./scripts/dev.sh up
```

기존 서비스가 준비된 경우에는 `up` 한 번으로 재개한다. LIVE `up`은 검증된 SSH로 서버의 기존 토큰을 동기화하며, 동일한 토큰이면 로컬 파일도 그대로 보존한다. 서버 토큰을 생성하거나 회전하지 않는다. 동기화에 실패해도 로컬 앱은 실행되며, API의 401/403은 `INFERENCE_AUTH_FAILED`로 표시한다. 모델 receipt 불일치와 구분하며 strict 릴리스 검사는 유지한다. 최초 배포나 릴리스 복구는 [RUNPOD_DEPLOYMENT.md](Docs/RUNPOD_DEPLOYMENT.md)의 명시적 배포 절차를 따른다.

`up`은 Mac의 현재 사용자 `launchd`에 이 프로젝트 전용 연결 관리 프로그램을 시작한다. API는 인증된 설정 적용 요청 파일만 만들고, Mac 관리 프로그램이 기존 키/agent로 SSH를 확인해 로컬 tunnel·worker·API를 적용한다. API/worker에 SSH 개인키나 Docker socket을 주지 않는다. 진행 중인 검토가 있으면 연결 교체를 막으며, 중단된 적용은 자동 재실행하지 않는다. `down`은 이 프로젝트의 관리 프로그램도 종료한다. 관리 프로그램이 없으면 팝업에 최초 한 번 `./scripts/dev.sh up`이 필요하다고 표시한다.

**저장 · LIVE 연결**은 DEMO에서 LIVE로 바꾸겠다는 명시적 동작이다. 원격 추론 서비스 설치, 모델 변경이나 generation은 실행하지 않는다. SSH 연결 및 `/readyz`가 성공해도 인증된 `/version`이 승인 receipt와 다르면 `MODEL_RELEASE_MISMATCH`로 생성을 보류한다. 2026-10-09 복구 서버의 `tokenizers 0.23.3`은 공개 합성 검사 3종과 실제 파일·runtime 대조 후 사용자 승인으로 별도 receipt에 등록했다. 로컬 API/worker에 반영한 현재 상태는 **LIVE / READY**이며, 이전·알 수 없는 receipt 차단은 유지한다. [연결 수정 결과](Docs/LOCAL_RUNPOD_CONNECTION_FIX_20261009.md), [실행환경 승인·적용 결과](Docs/RUNPOD_RUNTIME_ALIGNMENT_RESULT_20261009.md)를 참조한다.

`sync-runpod-token`은 검증된 SSH 경로로 원격 `/root/.config/dorilab/inference.token`을 권한 600 임시 파일에 직접 받고 형식을 검사한 뒤 로컬 Compose secret을 원자 교체한다. 값을 출력하거나 `.env`에 넣지 않는다. `fetch-runpod-bundle`은 원격의 Mac client, API 계약, contract, 인증된 `/version`과 현재 boot model receipt만 가져오며 원격 파일과 프로세스는 바꾸지 않는다. receipt가 승인 profile과 다르면 `reference/runpod/inference.pending-<boot_id>/`에 보존하고 승인된 `reference/runpod/inference/`를 교체하지 않는다.

현재 검증된 RC3 서비스는 원본 `v15_rc1`을 보존하면서 `evidence_refs`를 모든 Action에 필수로 만든 immutable overlay `v15_rc1_cf1`을 LIVE SourceReview contract로 사용한다. 로컬 worker는 원격 API에 `request_id`, `contract_id`, 단일 native JSON 문자열 `user`, `max_new_tokens`만 보낸다. 서버가 제공한 system prompt를 덮어쓰지 않고, `raw_text`와 일반 decode `text`, boot/model receipt와 token/hash metadata를 분리 보존한다.

팝업은 비밀이나 개인키를 저장하지 않는다. 연결값은 `var/connection/runpod.env`, 확인한 공개 호스트 키는 `.secrets/known_hosts`에 저장한다. `.env`의 `RUNPOD_HOST`와 `RUNPOD_SSH_PORT`는 기존 자동화 호환용 fallback으로만 남아 있다.

기본 계정은 `root`, 키는 `~/.ssh/id_ed25519`, 원격 inference port는 8080이다. 다른 값은 setup 시 환경변수로 한 번 재정의한다.

```sh
DORILAB_SSH_USER=root \
DORILAB_SSH_KEY_PATH="$HOME/.ssh/another_key" \
DORILAB_APP_PORT=18000 \
./scripts/dev.sh setup
```

암호가 있는 기존 키는 Mac agent에서 잠금 해제한 뒤 다음 지원 경로를 쓴다.

```sh
DORILAB_SSH_USE_AGENT=1 ./scripts/dev.sh setup
```

## 관리 명령

```sh
./scripts/dev.sh setup
./scripts/dev.sh sync-runpod-token
./scripts/dev.sh fetch-runpod-bundle
./scripts/dev.sh deploy-runpod
./scripts/dev.sh up
./scripts/dev.sh up --demo
./scripts/dev.sh status
./scripts/dev.sh logs
./scripts/dev.sh test
./scripts/dev.sh down
```

- `setup`: Docker 상태, 경로, 디렉터리, 비밀 파일, strict host-key와 SSH 인증을 비파괴적으로 준비한다.
- `sync-runpod-token`: 기존 원격 서비스 토큰을 노출 없이 로컬 Compose secret으로 동기화한다.
- `fetch-runpod-bundle`: 승인된 client/contract/allowlist/receipt 원본을 로컬 reference에 복사한다.
- `deploy-runpod`: 제한된 원격 조사 후 구체적 plan과 확인을 거쳐 wrapper만 설치한다.
- `up`: DB health → migration → API/tunnel → 기존 서비스 토큰 동기화 → worker 순서로 올린다. 원격 readiness는 로컬 앱 시작 조건이 아니다.
- `up --demo`: 원격 endpoint/키 없이 명시적인 DEMO만 올린다.
- `status`: Compose, DB, tunnel, remote API와 model receipt 상태를 분리한다. LIVE worker도 10초마다 인증된 readiness/version receipt를 갱신한다.
- `logs`: 이 프로젝트의 API/worker/tunnel 최근 로그를 본다.
- `test`: 격리된 PostgreSQL과 mock/SIMULATED inference로 자동검사를 실행하며 RunPod를 호출하지 않는다.
- `down`: 이 Compose stack만 내린다. volume, Artifact, 기록, secret과 원격 RunPod는 보존한다.

## 두 창으로 자동 시연 촬영하기

자동 시연은 기본으로 **상세 설정부터** 동선을 선택한다. 새 공개 합성 DEMO 프로젝트에서 이름·개발 체계·자료 정책, 기준 문서 참조, BM1 Claim과 시험 범위, 요구사항 연결을 실제로 저장한다. 이후 원문 미리보기 → bytes 업로드 → 파싱·청크 확인 → 프로젝트 문서 검색 → 실제 Local LLM 검토 → Blackboard → 실행 증거를 26장면으로 보여준다. 기존 9장면은 **기존 요약** 선택으로 사용할 수 있다.

장면 속도는 8초·12초·20초이고 입력 애니메이션과 서버 처리 대기는 별도다. 촬영 중 **일시정지 / 이전 / 다음 / 계속 재생**으로 설명 시간을 조정한다. Local LLM 결과에서는 사람 검토 경계에서 멈추며 **Blackboard 반영 보기**로 이어간다. 표준 속도의 예상 시간은 약 8분이며 모델 대기에 따라 달라진다.

상세 시연 시작은 실행별 새 프로젝트를 로컬 DB에 만들고 공개 합성 파일을 Artifact Store에 보존한다. 종료하거나 다시 시작해도 이미 저장된 자료를 삭제하지 않는다. 같은 실행의 저장 단계를 다시 방문하면 저장 응답을 재사용하고 Local LLM 결과 재방문도 같은 Job을 조회한다. 결과가 불명확한 저장 요청이나 실패한 LIVE를 자동 재전송하지 않는다. REPLAY는 `up --demo`에서 선택하고 LIVE 실패의 대체 경로로 사용하지 않는다.

기준 문서 등록은 UNCONFIRMED 참조 메타데이터이고, 문서의 RAG 사용 설정은 공개 합성 fixture의 사용 범위다. 공식 표준 채택·사람 결정·Gate 승인·검증 종결을 자동으로 만들지 않는다. 현재 RAG는 PostgreSQL FTS이며 임베딩 벡터 검색은 아니다.

1. `./scripts/dev.sh up` 후 `http://localhost:18000`을 새로고침한다.
2. **사업 개요 → 자동 시연 → Blackboard 관찰 창 열기**를 누르고 두 창을 나란히 배치한다.
3. **Local LLM LIVE 자동 시연 시작**을 누른다. 노란 시연 커서, 클릭 표시와 현재 저장된 질문의 입력 표시가 실제 시연 단계에 맞춰 보인다.
4. Local LLM 결과에서 정지하면 **Blackboard 반영 보기**로 같은 Job의 기록을 확인하고 **계속 재생** 또는 **다음**으로 남은 조회 장면을 진행한다. 사람 결정은 자동 저장하지 않는다.

새 시연 준비·시작 시 관찰 표시를 비우고 이번 실행의 Job만 표시한다. PostgreSQL의 이전 검토·원출력·사람 결정은 보존한다. 입력 표시는 저장된 질문을 화면에서 보여주는 동작이며 새 Claim revision이나 업로드를 만들지 않는다. REPLAY는 저장 흐름 재현으로 표시하며 실제 Local LLM 호출과 구분한다.

관찰 창은 부모 탭의 source ID와 순서 번호를 고정한다. BroadcastChannel/opener 메시지와 멤버십 검사를 거친 임시 관찰 세션 GET으로 현재 단계를 복구하며 본문은 기존 Blackboard/Job GET에서 읽는다. 관찰 세션은 최대 128개·30분 TTL의 API 메모리 신호로 업무 DB와 모델을 변경하지 않는다. 팝업 닫기·재열기·새로고침은 생성 요청을 만들지 않고, 부모 창 재로딩은 직접 opener 확인으로 연결을 갱신한다. 페이지의 JS/CSS 해시를 URL에 붙여 Docker 재빌드 뒤 예전 파일이 섞이지 않게 한다.

## 데이터와 비밀

**개발·모델 관리 → 논문·자료**에서 맥의 파일을 선택하고 용도·권리·판본을 입력한 뒤 **문서 저장 · 텍스트 파싱**을 누른다. 최대 20 MiB의 PDF 텍스트층·UTF-8 TXT/Markdown/JSON/CSV를 지원한다. 아래 원문 등록부에서 저장된 원본 다운로드, SHA256, 파싱 상태·실패 사유, 페이지/줄 위치와 추출 텍스트를 확인한다. 긴 문서는 10개 청크씩 조회한다.

미확인 권리·판본·채택·적용성은 자동 승인하지 않는다. RAG 검색 자료의 채택·적용성은 **RAG 검토 범위 설정**에서 지정하며 기존 서버 Scope Gate가 검색 때 다시 검사한다. 학습 준비·평가 전용 자료는 운영 RAG에서 제외된다. 업로드·파싱은 모델 학습이나 근거 수용이 아니며 OCR·표·그림의 의미 판정은 지원하지 않는다.

**개발·모델 관리 → 학습 사례 작성·검토**에서 `DoriLab_100Q_통합검토_핸드오프_v1.0.md` 파일 하나를 선택하고 **자동 분리 · 검토 목록에 저장**을 누른다. 문항 번호·유형·출처 묶음·학습/평가 용도와 질문·입력·정답 초안·오답을 분리해 서버에 저장한다. 검토 책임자 또는 승인권자 역할에서 문항을 하나씩 확인하고, 입력·정답을 수정하거나 검토 사유와 확인 체크를 입력해 **승인하고 다음 문항** 또는 **기각하고 다음 문항**을 누른다. 원본과 수정본·검토 계정·시각·버전은 따로 보존된다. 상태·유형·학습/평가 용도로 목록을 걸러 볼 수 있으며, 새로고침 또는 같은 파일 재등록으로 기존 결정이 초기화되지 않는다. 이번 형식은 100Q 핸드오프 전용이며 일반 논문 PDF를 질문 세트로 자동 생성하지 않는다. 문항 승인과 원 논문 검증·학습 파일 생성·RunPod LoRA 실행은 구분한다. 상세: [100문항 세트 검토](docs/LEARNING_SET_REVIEW_20261010.md).

개별 사례를 직접 작성하려면 같은 탭의 기존 작성 양식에서 파싱된 문서와 원문 위치를 고르고, 문서 묶음 ID·용도·입력·응답을 입력해 **미검토 초안으로 저장**한다. 같은 논문·개정판에는 같은 문서 묶음 ID를 사용한다. 원문 hash·판본·위치·작성 계정·시각을 함께 보존하며, 저장한 입력·응답은 펼쳐서 다시 조회할 수 있다. 원문이 변경되면 이전 사례는 `STALE`로 표시된다. 저장 자체는 정답·사용 권리·공학 승인이 아니며 Local LLM 호출이나 학습을 실행하지 않는다. 상세: [3단계 기록](Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP3.md).

검토 책임자·승인권자는 저장 카드의 **사례 검토·기각**을 펼쳐 입력·응답·원본을 확인하고 **검토 기록**을 작성한다. 현행 원문·공개/확보된 사용 권리·판본과 권리 확인 체크가 있으면 **사례 검토 완료**, 문제가 있으면 사유만 작성해 **기각**할 수 있다. 엔지니어는 결정을 저장할 수 없다. 결정 후 계정·시각·사례 버전과 작성한 검토 기록을 조회하며 기존 입력·응답·출처를 덮어쓰지 않는다. 원문이 바뀌면 과거 결정은 보존하고 현재 사용은 보류한다. 이 결정은 로컬 자료 준비에 한정되며 공학·외부 전송 승인이 아니다. 데이터 버전 고정·내보내기와 RunPod 학습은 후속 단계다. 상세: [4단계 기록](Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP4.md).

- PostgreSQL: named volume `dorilab-postgres`
- 원문과 model raw output: `var/artifacts/`
- 실행 기록: `var/run-records/`
- export: `var/exports/`
- 로컬 비밀과 known_hosts: `.secrets/`
- setup 파생 설정: `.env.derived`
- RunPod HostName/외부 SSH 포트: `var/connection/runpod.env`

setup은 기존 비밀 파일을 덮어쓰거나 회전하지 않는다. Compose secrets는 필요한 container에 파일로 제한해 제공하지만 암호화된 외부 secret manager는 아니다. 개인키는 프로젝트에 복사되지 않으며 key 방식에서는 tunnel에 한 파일만 read-only mount된다. API/worker/DB에는 개인키가 없다.

상세 RunPod 준비 절차는 [RUNPOD_DEPLOYMENT.md](Docs/RUNPOD_DEPLOYMENT.md), 배치 결정은 [ADR_DOCKER_SSH_LOCAL.md](Docs/ADR_DOCKER_SSH_LOCAL.md)를 따른다.

## Codex 프로젝트 가이드

`.codex/skills/dorilab-local-docker-runpod/SKILL.md`는 PABCD의 Plan/Audit/Build/Check/Done 관점을 이 프로젝트 경계에 맞춘 짧은 작업 지침이다. `.codex/hooks.json`의 PreToolUse 후크는 명백한 파괴 명령, Docker 전역 정리, strict SSH 우회와 RunPod stop/delete만 차단한다. 일반 build/test/edit/Compose down과 제한된 임시 파일 정리는 허용하며, 입력 JSON을 읽지 못할 때도 개발을 막지 않는다.
