# DoriLab 구현 상태

2026-10-10 학습 세트 검토: **100Q 파일 하나 자동 분리 → 문항별 수정·승인·기각 → 서버 이력 보존**을 로컬 앱에 반영했다. 전달된 실제 파일은 학습용 87·평가용 13, 전체 100문항 모두 미검토로 등록했다. 전체 격리 회귀 252 passed, 최종 이미지 관련 회귀 50 passed와 실제 브라우저 등록/합성 결정/재열기/새로고침을 확인했다. 원 논문 검증·데이터 내보내기·GPU 학습과 문항 승인은 구분하며, 새 기능의 공개 Site·Render·Neon 배포는 아직 하지 않았다. 상세: [100문항 세트 검토](LEARNING_SET_REVIEW_20261010.md).

2026-10-09 실행환경 승인 후 최신 상태는 **LIVE / READY**다. `tokenizers 0.23.2 → 0.23.3` 차이를 공개 합성 LIVE 3건으로 검증한 뒤 사용자가 명시적으로 승인했다. 승인된 새 receipt `7e8f301c…4f0a`만 로컬 profile에 등록하고 API/worker를 재빌드했다. 실제 `/readyz`·인증 `/version` 200, exact receipt 일치와 브라우저의 LIVE 시연 버튼 활성화를 확인했다. 전체 격리 회귀 235 passed, 최종 승인 profile 관련 회귀 21 passed, 기존 첨부 28/28 hash 일치와 업무 건수 보존을 확인했다. 원격 설치·모델 변경·Site 배포는 없으며, 적용 후 전체 자동 시연을 다시 실행한 것은 아니다. 상세: [실행환경 승인·적용 결과](RUNPOD_RUNTIME_ALIGNMENT_RESULT_20261009.md).

2026-10-09 로컬 연결 수정: **저장 · LIVE 연결**은 검증된 설정을 Mac의 프로젝트 전용 관리 프로그램에 요청하고, 기존 키로 SSH 인증·기존 토큰의 로컬 동기화·Docker tunnel·LIVE 모드를 적용한다. API/worker에는 개인키나 Docker socket을 주지 않는다. 팝업 닫기·재열기·새로고침과 동일 설정 재저장을 확인했다. 최근 인증 연결이 정상인 동일 설정은 재시작하지 않으며, 같은 주소의 인증 실패·원격 단절 때는 명시적 복구를 허용한다. 진행 중인 검토가 있으면 교체를 막고 중단된 적용은 자동 재실행하지 않는다.

이날 앞선 연결 수정 단계에서는 `205.196.144.74:11284`의 strict SSH, Docker forwarding, `/healthz`·`/readyz`·인증된 `/version`이 실제로 성공했다. 당시 로컬 앱은 **LIVE**, 모델 생성 상태는 **MODEL_RELEASE_MISMATCH**였다. 승인 receipt와 복구 receipt의 모델·어댑터 및 나머지 항목은 같고 `runtime.tokenizers`만 `0.23.2 → 0.23.3`으로 달라 생성 차단을 유지했다. 그 단계의 격리 회귀는 **233 passed / 1 warning**, generation·원격 쓰기는 0건이었다. 그때의 보고서는 과거 실행 결과로 보존하며 runtime 승인·적용 결과는 위 최신 기록을 따른다. 상세: [연결 수정 결과](LOCAL_RUNPOD_CONNECTION_FIX_20261009.md).

2026-10-04 화면 용어 정리: Baseline은 **기준점 / 형상 기준점**, 모델 서비스 표시는 **Local LLM**, 실행 영수증은 **실행 증빙**으로 맞췄다. 실제 모델 식별값은 기술 상세에 보존하고 GPU 연결 대상은 RunPod로 명시했다. 기존 프로젝트의 시스템 점검 문구는 표시에서만 대응하고 원 DB·첨부·결정 이력은 유지했다. 격리 회귀 **158 passed**, 실제 반영 이미지 관련 검사 **12 passed**, JavaScript 4개 문법 검사와 실제 화면 조회를 확인했다. RunPod 호출·학습·새 시연 실행은 없다. 용어 검토와 결과: `Docs/UI_TERMINOLOGY_KO.md`, `Docs/UI_TERMINOLOGY_RESULT_20261004.md`. 개발·모델 관리 공개 범위는 아래 4단계 그대로다.

2026-10-04 개발·모델 관리 4단계: **저장된 사례의 사람 검토·기각 화면**을 현재 `http://localhost:18000`에 반영했다. 검토 책임자·승인권자는 원문·입력·응답을 확인하고 검토 기록을 남긴다. 검토 완료에는 현행 원문·등록 권리·판본·권리 확인 체크를 요구하며 기각에는 사유를 요구한다. 결정 계정·시각·사례 버전과 기존 입력·응답·출처를 보존한다. 원문 변경 시 검토 완료를 차단하고 과거 결정은 남긴다. 격리 전체 회귀 **157 passed**, 반영 이미지 관련 검사 **31 passed**, 격리 브라우저 정상/기각·역할·판본 변경·새로고침·연결 장애/복구를 확인했다. 기존 업무 테이블 **38개** 내용 digest와 첨부 **28개** bytes/hash, migration **14개**가 전후 동일하다. 새 migration·사용자 DB 시험 사례·Qwen 호출은 없다. 데이터 버전/manifest는 여전히 501, RunPod 학습은 미구현이다. 상세: `Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP4.md`. 다음 작업은 검토 완료 사례의 학습/평가 데이터 버전 고정 하나다.

이전 단계 기록: `Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP1.md`, `Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP2.md`, `Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP3.md`. 아래에는 당시 검증 결과와 후속 검증을 함께 보존한다.

- 갱신: 2026-10-10
- 현재 실행: **LOCAL_MVP_FUNCTIONAL / LIVE_READY / SYNTHETIC_CONFORMANCE_PASS**. 전체 개발 목표는 부분 달성이다.
- 과거 판정 보존: LOCAL_COMPLETE / UI_PAGE_8_COMPLETE / QUICK_DEMO_LIVE_VALID / DETAILED_SETUP_QWEN_LIVE_VALID / CURRENT_NATIVE_BLACKBOARD_E2E_VALID. 아래 기존 LIVE receipt는 과거 시험 결과이며 현재 READY를 뜻하지 않는다.
- 실행 환경: macOS 27.0.1 (arm64), Docker Engine 29.8.0 / Compose 5.5.1, Docker Desktop `desktop-linux`, Linux container aarch64, local API 1.0.0
- 로컬 주소: `http://localhost:18000` (기본값 8000, 초기 host 충돌 때 만든 고급 override 유지)

## 2026-10-03 최신 코드 로컬 반영

추가 반영: **개발·모델 관리 1단계의 개발 현황 화면**을 공개했다. 목표·M1~M6·통과 조건·남은 차이·날짜/hash가 있는 근거 보고서를 조회한다. 전체 목표는 PARTIAL이다. 논문·자료/학습 준비 탭은 비활성이고 준비 쓰기 API는 501이다. SQL 014는 초안으로 분리해 실제 개발 DB의 migration 13개와 기존 업무 데이터/첨부 hash를 유지했다. 격리 검사 124 passed에는 미공개 초안 검사도 포함되며 모델 정확도·학습 성공이 아니다. 다음 작업은 자료 등록 화면 하나다. 상세 범위와 실패·미검증은 `Docs/DEVELOPMENT_MODEL_MANAGEMENT_STEP1.md`에 기록했다.

- 설치된 Docker Desktop을 시작하고 DB·Artifact·Export를 백업한 뒤 `./scripts/dev.sh up --demo`로 최신 API/worker 이미지와 migration 012·013을 실제 개발 DB에 반영했다.
- 실행 API의 코드·웹 파일 26개와 worker 모듈 19개가 현재 저장소의 해시와 일치한다. API/DB health 정상, migrate exit 0이다.
- 검토 24건·ModelRun 24건·사람 결정 5건·ArtifactVersion 28건을 보존했다. 추가형 metadata를 제외한 기존 업무 테이블 내용 digest와 실제 첨부파일 hash가 적용 전후 동일하다. 기존 DB 암호·세션 키·추론 토큰·known_hosts도 그대로다.
- 기존 Claim 4건과 요구사항 8건은 UNSPECIFIED로 남는다. 내용으로 목적을 추측하거나 새 승인으로 승격하지 않았다. 수동 인용의 legacy 검증 정책도 유지했다.
- 브라우저에서 검토 목적 미지정·제품 성능 NOT_EVALUATED, 문서 등록 모달, REPLAY 시작 활성화와 Qwen LIVE 차단을 확인했다. 이번 반영에서는 새 generation·사람 결정·원격 접속/변경을 수행하지 않았다.
- 2026-10-02의 최신 소스 회귀 110 passed와 Chrome 26단계 REPLAY 검증은 변경되지 않은 소스의 기존 증거로 재사용했다. 이번에 전체 pytest나 전체 시연을 다시 실행했다는 뜻은 아니다. length 응답 완결성 수락 정책 등 재검증에서 남은 차이는 별도 보완 전까지 유지된다.
- 적용·백업 기록: `var/run-records/local-code-apply-20261003.ESW7ei`. PostgreSQL archive 목록 조회와 Artifact archive 목록 조회는 성공했으나 전체 복원 시험은 이번 범위가 아니다.
- 자세한 적용 결과는 `docs/LOCAL_DOCKER_APPLY_20261003.md`, 전체 목표 판정은 `docs/DEVELOPMENT_GOAL_REVERIFICATION_20261002.md`를 따른다.

## 구현 완료

- 기본 자동 시연을 26장면 상세 설정 동선으로 추가. 새 공개 합성 DEMO 프로젝트, 참조 문서 메타데이터, Claim scope/revision, 요구사항 연결, 실제 Markdown bytes, parser·chunk·FTS retrieval를 한 단계씩 입력·저장·조회한 뒤 Qwen과 같은 Job의 Blackboard를 표시한다. 기존 9장면은 SUMMARY 선택으로 유지하며 장면당 8·12·20초와 일시정지/이전/다음을 제공한다.
- 같은 상세 실행의 저장 단계와 결과 재방문은 이미 받은 응답/Job을 재사용한다. 실패하거나 불명확한 저장은 자동 재전송하지 않는다. 사람 결정과 공식 승인은 자동으로 만들지 않으며 현재 RAG가 벡터 임베딩이 아닌 PostgreSQL FTS임을 표시한다.

- Compose의 api/worker/db/migrate와 LIVE 전용 llm-tunnel 분리
- PostgreSQL migration과 재실행 가능한 개발 seed
- Project/Membership, Claim/Scope, ArtifactVersion/SourceSpan/Evidence, ContextSnapshot, ReviewJob/Attempt, ModelRun/Validation, HumanReview/AuditEvent
- EvidenceRequest의 OPEN/RECEIVED/ACCEPTED/REJECTED 전이와 ReportExport Markdown snapshot
- 실제 bytes upload/download, SHA256, 프로젝트 권한, idempotency/409, STALE, 원출력·검증·사람 결정 분리 저장
- 최근 Job 재조회, 근거 원문 다운로드, 사람 수정 초안 JSON, hash 기반 Markdown 보고서 재다운로드
- worker lease 복구: DEMO만 안전 재대기하고 불명확한 LIVE는 UNKNOWN_OUTCOME 보존
- 명시적 SIMULATED/REPLAY BM1 흐름과 8개 화면/14단계 탐색 구조
- authenticated async inference wrapper, exact receipt 검사, single generation, boot_id 기반 UNKNOWN_OUTCOME
- strict SSH tunnel, host-key 확인, 단일 key/agent 격리, 비파괴 deploy-runpod plan
- 프로젝트 전용 Codex skill과 느슨한 고신뢰 destructive-command hook
- 원본 목업 CSS와 사업 개요 화면 구조를 재사용하고 수치·역할·동작을 서버 API에 연결
- 두 번째 적용 기준과 프로파일 화면을 원본 구조로 이식하고 KASA/ECSS/NASA 미리보기, 기준 문서 등록, 테일러링 결정과 원문 장 열기를 서버 API에 연결
- 세 번째 요구사항과 검증 경로 화면을 원본 구조로 이식하고 V 모델, 추적 경로, 제품 요구사항 매트릭스와 상세 모달을 PostgreSQL 요구사항·Claim revision에 연결
- 네 번째 기술검토회의 화면을 원본 3열 Gate 구조로 이식하고 프로파일별 회의명, 실제 준비·성공조건, 검토 권한과 별도 단계 전환 결정을 PostgreSQL에 연결
- 다섯 번째 시험 워크스페이스 화면을 원본 14단계 rail과 BM1 2열 작업 구조로 이식하고 Claim scope, Evidence Board, ContextSnapshot, 검토 결과, 사람 결정, Blackboard와 실행 trace를 서버 API에 연결
- 여섯 번째 검증 종결과 인계 화면을 원본 상태판·제품/프로세스 매트릭스 구조로 이식하고 별도 데이터 품질 평가, TRB 승인, 권한자 VerificationClosure와 version별 종결 이력을 PostgreSQL에 연결
- 일곱 번째 기준선과 변경 영향 화면을 원본 현재 기준선·전파 경로·CCB 처리·동시 변경 보호 구조로 이식하고 DRAFT ConfigurationChange, 영향 snapshot, approver 결정과 transaction 기반 version/STALE 전환을 PostgreSQL에 연결
- 여덟 번째 실행 이력과 작업 파일 화면을 원본 3개 집계·검색 toolbar·Audit Trail 구조로 이식하고 PostgreSQL projection, 보고서 bytes/hash 다운로드와 읽기 전용 JSON 감사 bundle을 서버 권한에 연결
- Audit `기록 상세`의 열린 event ID를 UI 상태로 보존해 비동기 재조회와 검색 재렌더 뒤에도 상세가 접히지 않도록 수정하고, 자동 시연 Audit 단계의 중복 조회 제거
- LIVE worker가 Job 유무와 무관하게 10초마다 인증된 `/readyz`와 `/version` receipt를 검사해 원격 상태를 저장
- 앱 상단 RunPod 연결 팝업에서 HostName/외부 SSH 포트 저장, SSH 설정 미리보기, SHA256 지문 조회와 한 번의 명시적 host-key 확인 지원
- 원격 `/root/.config/dorilab/inference.token`을 출력하지 않고 검증·원자 교체하는 `sync-runpod-token`과 승인 client/contract/receipt를 보존하는 `fetch-runpod-bundle` 지원
- 원본 RC3 `v15_rc1`을 보존하고 모든 Action에 `evidence_refs`를 요구하는 immutable `v15_rc1_cf1` SourceReview 계약, 네 필드 generation 요청, raw/native decode 분리 저장과 contract별 strict Validator 구현
- 9개 장면 자동 시연 제어판, REPLAY/Qwen LIVE 명시 선택, 일시정지/이전/다음/재생과 화면 강조, READY·합성 정책 guard, LIVE 실패 시 무대체, 모델 결과 후 사람 검토 경계 자동 정지 구현
- Qwen LIVE 관찰 팝업에서 실제 Snapshot 입력, Artifact Store 원출력, 모델 판단, token/boot/hash receipt, Validator 상태와 같은 Job의 Blackboard Contribution·WorkItem·dependency를 5단계로 표시하고 저장된 LIVE Job에서도 다시 열기 지원
- 기존 8개 상세 화면은 유지하고 별도 `빠른 시연` 탭에서 `문서 근거 → 실제 Qwen 판단 → Blackboard 다음 업무 → 사람 확인`을 한 화면에 표시. 버튼 한 번에 새 LIVE generation 한 건만 만들며 실패 시 REPLAY로 대체하지 않음
- 자동 시연 옆에 별도 `Blackboard 관찰 창`을 열어 같은 `run_key/job_id`의 Contribution, WorkItem, dependency, BoardEvent와 고정 graph checkpoint만 읽기 전용 카드로 표시. 새 실행에서는 이전 Job을 먼저 비우고, 프로젝트 전체 projection을 `source_job_id`와 연결 객체 ID로 격리하며, 팝업 열기 자체는 모델·시뮬레이션을 실행하지 않음
- 관찰 창은 부모 source ID와 sequence를 고정하고 BroadcastChannel/opener와 권한 검사가 있는 임시 관찰 세션 GET으로 현재 단계를 받는다. 본문은 기존 Blackboard/Job GET에서 1.5초마다 조회한다. 새 시연 준비·시작은 표시를 비우며 DB 이력을 지우지 않는다. 다른 탭 신호·중복·역순·이전 실행의 지연 GET을 버리고 부모 페이지 재로딩은 직접 opener 확인으로 연결을 갱신한다. localStorage는 사용하지 않는다.
- 노란 시연 커서, 클릭 링과 동작 이름을 표시한다. 현재 저장된 검토 질문의 입력 표시는 Claim revision을 새로 만들지 않으며, 결과 단계 재방문은 같은 Job을 재조회한다. HTML은 현재 JS/CSS 해시 URL과 no-store를 제공해 Docker 재빌드 뒤 캐시 혼합을 막는다.
- LIVE `up`은 검증된 SSH로 기존 서버 토큰을 로컬에 동기화하고 동일하면 그대로 보존한다. 실패해도 로컬 앱은 시작한다. 401/403은 `INFERENCE_AUTH_FAILED`로 표시하고 모델 receipt 불일치와 구분한다. 원격 토큰·서비스·가중치는 변경하지 않는다.
- 문서 RAG v1: PDF text layer와 UTF-8 text/Markdown/JSON/CSV 원본을 별도 보존하고 page/section/line locator가 있는 결정적 청크, PostgreSQL FTS, 검색 rank·score·선택/제외 사유와 parser/chunker/index receipt를 PostgreSQL에 저장
- 검색 시 프로젝트 membership, 운영자료 용도, rights·edition·adoption·applicability와 Claim/project version을 다시 검사하고 선택 청크와 receipt를 ContextSnapshot에 고정; 검색 결과는 Evidence 수용이나 공학 판정으로 자동 승격하지 않음
- BM1 고정 서버 graph: `SELECT_TASK → SCOPE_GATE → RETRIEVE_CONTEXT → BUILD_CONTEXT → SOURCE_REVIEW → VALIDATE → UPDATE_BLACKBOARD → ROUTE → WAIT_HUMAN → RESUME → COMPLETE`
- 각 노드 attempt와 상태 snapshot SHA256을 PostgreSQL에 저장하고, 사람 결정 전 `WAIT_HUMAN`에서 멈춘 뒤 같은 실행을 재개한다. DEMO lease 만료는 재대기하고 불명확한 LIVE는 `UNKNOWN_OUTCOME`으로 고정한다.
- 실행 graph는 결정적 서버 state machine으로 구현했다. LangGraph 패키지를 도입했다는 뜻은 아니며 공학 상태와 승인 권한은 기존 ReviewJob·Blackboard·HumanReview가 계속 소유한다.

## 실행 증거

- container test: 87 passed
- 상세 시연 새 프로젝트 `DEMO-SETUP-085A9390`에서 Claim 1·요구사항 1·참조 등록 1·문서 1·청크 5·선택 청크 1을 실제 저장했다. Qwen Job `3137d0d5-65fa-4862-99b9-b6df12dc4130`은 `VALID / AWAITING_REVIEW / NO_ACTION_REQUIRED`, token 1154/55/384와 eos를 보존했다. 실제 결과에 맞춰 Contribution 1·WorkItem 0·Dependency 2·Event 11을 관찰했고 HumanReview는 0건이다. 모델 의미 정확도나 공식 승인 검증을 뜻하지 않는다.
- 별도 관찰 창 정적 계약 7건과 기존 전체 회귀검사 통과. 브라우저에서 빈 상태, 저장된 LIVE Job `f275ae0d-922d-40ad-9712-7e2e6a338543`의 Contribution 1·WorkItem 1·dependency 3·관련 BoardEvent 12 표시, JSON 펼침 유지, 새로고침, 닫기·재열기, 새 run의 0건 격리와 404 오류 상태를 확인
- 관찰 UI 검증 전후 ReviewJob/ModelRun은 각각 13건으로 유지됐고 최신 생성시각도 2026-09-27에서 바뀌지 않아 팝업이 generation을 중복 실행하지 않았음을 확인
- 앞선 관찰 창 검사 당시 원격 표시는 `SERVICE_NOT_DEPLOYED`였으므로 저장된 실제 LIVE Job만 조회했다. 이후 기존 서버 토큰을 안전하게 동기화해 READY를 복구했으며, 촬영용 수정 검증에서 새 Qwen LIVE Job `0ae5b55c-1b33-4f21-9f94-afcf0622c6bf`의 원출력·Validator·같은 Job의 Blackboard와 빈 화면 재시작을 확인했다. 부모/팝업 새로고침 후 연결도 확인했다.
- 공개 합성 packet 기반 REPLAY fixture 3종(`normal`, `request_evidence`, `contradiction`)의 기대 판정·receipt·원출력 hash·자료 요청 수 검증 통과
- hook test: 4 passed
- Compose build, DB health, migration, API/worker health 통과
- 브라우저 8개 화면 탐색과 BM1 REQUEST_EVIDENCE → reviewer 결정 저장 확인
- 최신 `down` 후 `up --demo`에서 Job 2건, ModelRun 2건, 사람 결정 1건, 보고서 1건, AuditEvent 5건과 관련 파일 SHA256이 동일하게 유지됨
- mock SSH argument/injection과 mock remote API 단절을 포함해 LIVE의 조용한 DEMO fallback 부재 확인
- 자료 요청 제출과 수용 분리, report idempotency/bytes hash, 저장 Job 재조회, DEMO/LIVE lease 복구 경계 확인
- 실제 개발 DB에 migration 001부터 011까지 적용; migration 009는 응답 token 예약량을 복원하고 migration 010은 문서 RAG receipt를 추가하며, migration 011은 기존 Job/Artifact를 보존한 채 orchestration run/node attempt/checkpoint를 추가한다.
- 격리 시험에서 새 Job의 준비 노드 4개, worker 실행, validator, Blackboard 반영, 규칙 Router, 사람 대기와 결정 후 재개를 하나의 run ID로 확인했다. 같은 idempotency key는 checkpoint나 ModelRun을 중복 생성하지 않았고, 완료 trace의 11개 노드가 모두 `COMPLETED`가 됐다.
- 실제 report DB/file SHA256 `8b7b076e5d7a794eb393d2cda7fa269c6159a7d06920b9c0b87dd5985aa04d09` 일치
- DB와 tunnel host publish 없음; API는 `127.0.0.1:18000`만 publish
- 실행 중 api/worker/db에 Docker socket과 SSH home mount가 없고, 각 서비스 secret이 필요한 파일로만 제한됨을 확인
- 브라우저에서 목업형 사업 개요, 시연 길잡이, 워크스페이스 이동과 기존 BM1 폼 보존을 확인
- 브라우저에서 KASA와 ECSS 프로파일 카드, 단계 rail, 기준 문서 등록부, 테일러링 영역과 원문 장 모달을 확인
- 브라우저에서 V 모델 양방향 노드, 추적 chain, 5개 요구사항 행과 THM-041 상세 관계 모달을 확인
- 브라우저에서 9개 기술검토 카드, 서버 계산 준비도, 조건 상세 모달과 별도 단계 진입 결정 폼을 확인
- 브라우저에서 시험 워크스페이스의 14단계 rail, 실제 Job·Snapshot Blackboard, 모델 경로, 자료 요청 탭, 역할별 사람 결정 폼을 확인
- BM2/NTR은 서버 계약이 없는 상태를 `NOT_IMPLEMENTED`로 표시하고 브라우저 계산이나 가상 결과를 저장하지 않음을 확인
- Evidence 목록과 상세 조회에서 bytes/content type, rights, edition, adoption, applicability와 원문 다운로드 locator 보존을 자동검사로 확인
- 브라우저에서 종결 상태판, 8개 서버 선행조건, 제품·프로세스 매트릭스, 데이터 품질 역할 경계와 종결 이력 영역을 확인
- Claim 종결은 현재 Claim/project version, 포함 근거, VALID 출력, 사람 수용, 판정, 미해결 요청, 데이터 품질과 TRB 승인을 서버에서 재검사하며 승인권자만 기록할 수 있음을 자동검사로 확인
- 기준선 변경은 DRAFT 요청과 CCB 결정을 분리하고, approver 적용 시 project version 증가·CURRENT Job STALE 전환·종결 Claim 재개방이 원자적으로 수행되며 model raw artifact와 이전 결정은 보존됨을 자동검사로 확인
- 브라우저에서 현재 기준선, 4단계 변경 전파 경로, CCB 요청 영역과 입력 dialog를 확인하고 이전 project version 명령이 409로 거부되는 시연을 확인; 앱 자체 console 오류 없음
- 브라우저에서 실행 Snapshot 2건, ModelRun 2건, 담당자 기록 1건과 5개 AuditEvent, hash가 표시된 Markdown 작업 파일을 확인하고 `EXPORT` 검색이 1개 이벤트로 축소되는 동작을 확인
- JSON 감사 bundle의 attachment, SHA256 header, project membership 격리, Snapshot/raw hash와 결정 기록 포함, secret 이름 부재를 자동검사로 확인; 가져오기와 파괴적 초기화는 명시적으로 비활성
- 브라우저에서 Audit event 21의 상세를 열어 1.5초 뒤에도 유지되고, `CREATE` 검색으로 timeline을 다시 그린 뒤에도 같은 event의 상세 JSON이 열린 상태로 유지됨을 확인
- 연결값 옵션 주입 거부, 프로젝트 membership, one-time host-key 확인, 변경된 host key 보존·거부를 자동검사로 확인
- Mac SSH 인증, Compose `llm-tunnel`, 원격 loopback `/readyz`, 인증된 `/version`을 실제 연결로 확인
- 현재 remote boot `6ded0350-ad57-4b92-932b-78d1668029ba`, 승인 model release receipt `b96e7289…a847`, `v15_rc1_cf1` contract `7240db…0114`, 4096/384 token limits가 로컬 profile과 일치
- RunPod에서 새 계약의 공개·합성 적합성 3종을 실제 Qwen으로 실행해 `REQUEST_EVIDENCE`, `NO_ACTION_REQUIRED`, `CHALLENGE`와 exact schema를 모두 통과; 영수증 SHA256 `45a5b973…56568`
- 로컬 API/DB worker → Compose tunnel → RunPod Qwen → strict Validator 종단 LIVE Job `b8d3bbbe-f120-4aae-a12b-782a33db3376` 통과; `CURRENT / AWAITING_REVIEW`, validation error 0건, EvidenceRequest 1건
- 브라우저 시험 워크스페이스에서 `OUTPUT_VALIDATED / 검토 의견 대기`를 확인하고 Blackboard에서 모델 제안 `PROPOSED`, 공용 근거 작업 `WAITING_INPUT`, 저장 Job `AWAITING_REVIEW / CURRENT` 투영 확인
- 브라우저 새 세션에서 `LIVE / READY`와 `LIVE_MODEL_RUN` 선택이 표시되는 것을 확인; 기존 SIMULATED Job은 실행 mode를 그대로 표시
- 브라우저에서 자동 시연의 9개 장면 이동·일시정지·재개와 REPLAY/Qwen LIVE 선택 팝업을 확인하고, LIVE는 `App LIVE / Remote READY / EXTERNAL_SYNTHETIC_ALLOWED` 조건에서만 활성화됨을 확인
- DEMO 자동 시연이 멱등 REPLAY Job `81ead82f-e77b-4759-b0ef-38616f755596`을 `VALID / AWAITING_REVIEW`로 준비하고 Blackboard의 Contribution 5건, WorkItem 4건, Dependency 9건을 표시함을 확인; 사람 결정·공식 종결·LIVE 호출은 자동 생성하지 않음
- Qwen LIVE 자동 시연이 새 Job `dba5de2a-6a2f-4972-a4ad-a1ed3f48e648`을 생성해 `VALID / AWAITING_REVIEW / REQUEST_EVIDENCE`에 도달함을 확인; 입력/출력/예약 token 963/46/384, boot `55aae728-…`, raw SHA256 `bc0c3e34…669ca`; 같은 Job의 Contribution 1건과 WorkItem 1건, 사람 결정 0건을 확인하고 결과 저장 직후 자동 정지함
- 현재 release의 관찰형 Qwen LIVE 자동 시연 Job `40f50ade-de7a-4f8a-a90d-d6e67c73ed83`을 실제 브라우저에서 확인; 팝업이 Snapshot 입력, 원출력 bytes, `REQUEST_EVIDENCE / SUPPORTING_EVIDENCE_MISSING`, token 1128/76/384, boot `6ded0350-…`, raw SHA256 `a2e30ade…8900`, strict Validator `VALID`, 같은 Job의 Contribution 1건·WorkItem 1건·dependency 3건을 연결해 표시함. Orchestration은 `WAIT_HUMAN`, HumanReview는 0건이며 자동 승인·종결은 생성하지 않음
- `빠른 시연` 탭에서 새 LIVE Job `c7552cd5-f285-435a-bdbe-777f87124d89`을 실제 실행해 `VALID / AWAITING_REVIEW / REQUEST_EVIDENCE`를 확인. remote request `6caf0b28-1060-4ba7-b73c-95c24b2b6c4f`, token 1128/76/384, boot `6ded0350-…`, raw SHA256 `a2e30ade…8900`, Contribution 1건·WorkItem 1건·HumanReview 0건이며 화면은 사람 확인 단계에서 멈춤
- 현재 release를 대상으로 합성 적합성 3종을 다시 실행해 `REQUEST_EVIDENCE`, `NO_ACTION_REQUIRED`, `CHALLENGE`를 모두 통과했고 receipt `ae135569…47ba9`를 `reference/runpod/inference/receipts/release-b96e7289/`에 보존함
- RAG 청크를 포함한 새 Native LIVE Job `64f445f3-656b-46b8-9a98-5353eff987e1`이 현재 Qwen → Validator → Blackboard → 규칙 Router → `WAIT_HUMAN`을 통과함. 입력/출력/예약 token 1128/76/384, raw SHA256 `a2e30ade…8900`, Contribution 1건, WorkItem 1건, dependency 3건을 확인함
- reviewer의 합성 `REVISION_REQUESTED` 결정 후 같은 run이 `RESUME → COMPLETE`로 이어져 11개 노드가 모두 완료됨. checkpoint 13개, ModelRun/원격 request/ReviewAttempt/HumanReview 각 1건, `duplicate_model_call=false`, 공식 검증 승인 생성 없음을 확인함
- `down → up` 뒤에도 위 Job, 원출력 receipt, 13개 checkpoint와 사람 결정이 유지됐고 원격 generation이 재실행되지 않음을 확인함
- 이후 원격 transport가 reset되어도 주기 status probe가 worker를 종료하지 않도록 모든 `httpx.RequestError`를 연결 상태로 흡수하고, 생성 제출·조회 중 단절은 `UNKNOWN_OUTCOME`으로 보존하도록 보강함; 원격 불가 상태에서 worker가 재시작 없이 계속 실행됨을 확인
- 문서 RAG 자동검사에서 Markdown과 생성 PDF text layer의 upload→parse→chunk→FTS→receipt→ContextSnapshot→SIMULATED worker→Validator→Blackboard dependency 경로, parser/retrieval idempotency·409, 프로젝트 격리, rights 제외, EVALUATION_GOLD 격리, 금지된 gold/rationale JSON 거부와 stale retrieval 거부를 확인
- 실제 브라우저에서 합성 `rag_browser_smoke.md`를 업로드해 `1 page / 4 chunk`, parser receipt `c5cf29f85a4d01de…`를 확인하고 `소산전력 열원 위치` 검색에서 1개 청크가 `SELECTED_FTS`로 선택됨을 확인; retrieval receipt `68a3eb928f3594e0…`, section/line locator, Artifact/Chunk SHA256과 `직접 근거 0건 + RAG 청크 1건` 표시를 대조함

## LIVE 상태

연결 팝업의 최신 SSH over exposed TCP 값 `205.196.144.18:11874`에 대해 사용자가 대조한 host key를 재사용했고 Mac SSH 인증이 성공했다. 원격은 NVIDIA RTX PRO 6000 Blackwell에서 단일 Python 모델 프로세스를 실행하며 `127.0.0.1:8080`에만 bind한다.

Qwen LIVE 자동 시연 시점의 검증 release는 boot `55aae728-3b58-4e0a-bbbb-21f8d5d38e93`, model release receipt `bfcd7d5e…c851`, active SourceReview contract `v15_rc1_cf1`/`7240db11…0114`였다. 서비스 토큰은 원격 root-only 파일에서 로컬 Compose secret으로 노출 없이 동기화했다. 이 이전 기준선과 배포·적합성 영수증은 `reference/runpod/inference/receipts/contractfix1/`에 보존했다.

자동 시연 완료 뒤 서버 측 작업으로 inference가 boot `6ded0350-ad57-4b92-932b-78d1668029ba`, receipt `b96e7289…a847`로 다시 시작됐다. 새 `/version`에는 `memory_controller_qwen_v1` 계약이 추가됐고 model receipt에는 `serving_modes.memory_planner=adapter_disabled`, `serving_modes.rc3=adapter_enabled`가 추가됐다. exact guard가 먼저 이를 차단했다. 이후 base revision, 전체 shard, adapter, runtime, generation policy와 active RC3 계약이 동일함을 비교하고, 현재 Qwen에서 공개 합성 적합성 3종을 다시 통과시킨 뒤 사용자 승인에 따라 새 receipt를 로컬 기준선으로 승격했다. 승인 증거는 `reference/runpod/inference/receipts/release-b96e7289/`에 보존했으며 원격 파일이나 모델 프로세스는 변경하지 않았다.

기존 `v15_rc1`로 수행한 end-to-end LIVE Job `c901d3de-95fb-4541-88d1-d70f2f050d35`는 Qwen 응답까지 도달했지만 빈 `evidence_refs` 누락으로 strict Validator가 거부했다. 이 실패 원출력과 receipt는 역사적 증거로 그대로 보존했다.

이를 수정하기 위해 원본 계약을 바꾸지 않고 `v15_rc1_cf1` overlay를 추가했다. 현재 최종 boot에서 공개·합성 입력 3종을 원격 API로 생성한 결과 자료 부족은 `REQUEST_EVIDENCE`, 충분한 자료는 `NO_ACTION_REQUIRED`, 모순 자료는 `CHALLENGE`를 반환했고 세 결과 모두 필수 필드와 참조 규칙을 통과했다. 출력 교정이나 validator 완화는 없었다.

검증 계약을 사용하는 로컬 종단 LIVE Job `b8d3bbbe-f120-4aae-a12b-782a33db3376`과 자동 시연 Job `dba5de2a-6a2f-4972-a4ad-a1ed3f48e648`은 release 변경 전에 모두 통과했다. Qwen은 입력 963 token, 출력 46 token으로 `REQUEST_EVIDENCE / SUPPORTING_EVIDENCE_MISSING`을 반환했고 필수 `evidence_refs: []`와 허용된 요청 ID를 포함했다. backend는 원출력 SHA256 `bc0c3e34…669ca`, boot와 model release receipt를 보존하고 validation error 없이 `CURRENT / AWAITING_REVIEW`로 전환했으며 각 Job에 EvidenceRequest 한 건을 생성했다. 같은 결과는 Blackboard에 모델 `PROPOSED` contribution과 `WAITING_INPUT` WorkItem으로 투영됐다.

이 검사에서 원격 `reserved_output_tokens` 384가 로컬 `reserved_new_tokens`에 저장되지 않는 필드 매핑 결함을 발견해 수정했다. migration 009로 기존 Job도 receipt에서 복원했고 회귀 검사를 추가했다. 새 Native LIVE Job의 token usage는 입력 1128, 출력 76, 예약 384로 재조회된다. 사람 결정은 별도 API에서 `REVISION_REQUESTED`로 기록했으며 공식 승인이나 VerificationClosure를 자동 생성하지 않았다.

Blackboard 서버 코어 1단계를 구현했다. 모델·사람의 `FINDING/HYPOTHESIS/CHALLENGE/FACT_PROPOSAL`, 공용 `TASK/TOOL_REQUEST/EVIDENCE_REQUEST`, 객체 dependency와 payload BoardEvent를 PostgreSQL에 저장하고 membership·version·idempotency를 검사한다. 모델 Action은 `PROPOSED`로 남고 HumanReview와 별도 처분되며, 수용된 보완 근거는 원래 Job만 선택적으로 `STALE`로 만든다. 기존 VALID ModelRun·HumanReview·EvidenceRequest는 모델을 재실행하지 않고 `LEGACY_PROJECTION`으로 graph에 투영한다. 화면의 Blackboard는 서버 projection과 고정 graph trace를 조회한다. 문서 RAG v1은 선택 청크를 `DOCUMENT_CHUNK → CONTRIBUTION` dependency로 연결한다. 남은 핵심은 embedding/reranker와 dependency graph 전체를 이용한 영향 기반 부분 재평가다.

## 목업 기준선

원본 Workbench HTML, Final Goal, README, QA_RESULTS와 sample JSON을 `mockup/`에서 확인했고 기록된 SHA256과 모두 일치했다. 8개 상세 페이지 모두 원본 CSS와 레이아웃을 재사용해 서버 상태에 연결했고 별도 빠른 시연 탭을 추가했다. 원본이 보고한 56개 QA 전체를 현재 서버 구현에서 재실행했다고 표시하지 않으며, 현재 구현에 대응하는 container 검사 87건을 별도로 통과했다.
