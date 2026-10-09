const state = { project: null, profileProjectId: null, claims: [], requirements: [], evidence: [], jobs: [], requests: [], retrievalRuns: [], retrieval: null, ragQuery: "", profileData: {documents: [], tailoring: []}, gateData: {gates: [], transitions: []}, closureData: {claims: [], history: []}, changeData: {changes: [], impact: {}}, auditData: {summary: {}, events: [], reports: []}, auditFilter: "", auditOpenEventIds: [], closureMatrix: "product", profilePreview: "KASA", profilePhase: 4, workspaceMode: "BM1", workspaceEvidenceTab: "current", workspaceStep: 10, workspaceReviewMode: "SIMULATED", selectedEvidenceIds: [], selectedClaimId: null, job: null, jobDetail: null, timer: null, page: "overview", status: null, runpodScanSha256: null, quickDemo: {projectId: null, busy: false, error: null, stage: "IDLE", jobId: null, detail: null, board: null, advancedOpen: false}, autoDemo: {active: false, playing: false, step: 0, timer: null, busy: false, board: null, mode: "REPLAY", runKey: null, observedJobId: null, error: null, trace: {jobId: null, rawArtifactId: null, rawText: null, rawError: null, board: null, boardLoaded: false}} };
const $ = (id) => document.getElementById(id);
Object.assign(state.autoDemo, {walkthrough: "SETUP", paceMs: 12000, operation: "", setup: null});
const csrfHeaders = {"X-DoriLab-CSRF": "1"};
const DEMO_OBSERVER_CHANNEL = "dorilab-blackboard-observer-v1";
const DEMO_OBSERVER_SCHEMA = "dorilab.demo.observer.v1";
const demoObserverSourceId = crypto.randomUUID();
const demoObserverChannel = "BroadcastChannel" in window ? new BroadcastChannel(DEMO_OBSERVER_CHANNEL) : null;
let demoObserverWindow = null;
let demoObserverSequence = 0;
let demoObserverPending = null;
let demoObserverPublishing = false;
const navs = [
  ["quickdemo", "빠른 시연", "play"], ["overview", "사업 개요", "grid"], ["profile", "적용 기준과 프로파일", "layers"],
  ["requirements", "요구사항과 검증 경로", "tree"], ["gates", "기술검토회의", "gate"],
  ["workspace", "시험 워크스페이스", "flask"], ["closure", "검증 종결과 인계", "circle"],
  ["changes", "기준점과 변경 영향", "change"], ["audit", "실행 이력과 내보내기", "log"],
  ["development", "개발·모델 관리", "layers"]
];
const paths = {
  play: "M8 5v14l11-7L8 5Z",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  layers: "m12 2 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 17l9 5 9-5",
  tree: "M4 4h6v6H4zM14 14h6v6h-6zM7 10v4h10",
  gate: "M5 21V5l7-3 7 3v16M9 21v-5h6v5",
  flask: "M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M7 15h10",
  circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-13 0 3 3 5-6",
  change: "M4 7h11m0 0-3-3m3 3-3 3M20 17H9m0 0 3-3m-3 3 3 3",
  log: "M5 3h14v18H5zM8 8h8M8 12h8M8 16h5",
  down: "M12 3v13m0 0 5-5m-5 5-5-5M5 21h14",
  upload: "M12 21V8m0 0 5 5m-5-5-5 5M5 3h14"
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
const profiles = {
  KASA: {
    name: "KASA", label: "한국형 시스템엔지니어링", region: "대한민국",
    phases: ["임무 정의", "개념과 실현 가능성", "예비 설계", "상세 설계", "통합과 검증", "운용", "사업 종결"],
    codes: ["사업 단계 1", "사업 단계 2", "사업 단계 3", "사업 단계 4", "사업 단계 5", "사업 단계 6", "사업 단계 7"],
    note: "단계명과 회의는 사업계획의 예시 매핑이다. 실행 기준에는 KSER 원문과 프로젝트의 채택 기록을 연결한다.",
    launch: "사업계획에서 발사와 초기 운용의 단계 및 승인 관계를 지정한다.", output: "요구조건 만족표와 검증 종결 기록",
    gates: ["임무 개념 검토", "SRR", "PDR", "CDR", "S-IRR", "TRR", "TRB", "제품 인수 검토", "운용 준비검토"],
    gateNames: {mission: "임무 개념 검토", srr: "SRR", pdr: "PDR", cdr: "CDR", sir: "S-IRR", trr: "TRR", trb: "TRB", accept: "제품 인수 검토", orr: "운용 준비검토"},
    docs: [["KASA-SE-REQ", "한국형 시스템엔지니어링 프로세스 및 요구조건", "1.0 / 2025-06-30", "KSER 대응과 수행 근거"], ["KASA-SE-HB", "한국형 시스템엔지니어링 핸드북", "Rev.1.1 / 2025-06-02", "수행 지침과 산출물 예시"], ["ECSS-TEST", "ECSS-E-ST-10-03", "Rev.1 / 2022-05-31", "고객이 채택할 시험 기준"]]
  },
  ECSS: {
    name: "ECSS", label: "유럽 우주 표준 체계", region: "유럽",
    phases: ["임무 분석과 필요 식별", "실현 가능성 검토", "예비 정의", "상세 정의", "적격성 확인과 생산", "발사와 초기 운용 및 활용", "폐기"],
    codes: ["Phase 0", "Phase A", "Phase B", "Phase C", "Phase D", "Phase E", "Phase F"],
    note: "단계의 목적과 포함 활동은 ECSS 체계를 보존한다. 관리, 공학, 제품보증 기준을 프로젝트 채택 목록으로 묶는다.",
    launch: "발사는 Phase E에 연결한다. 제품 검증과 수용 근거는 제품 수준별로 관리한다.", output: "Verification Control Document (VCD)",
    gates: ["MDR", "SRR", "PDR", "CDR", "통합 준비검토", "TRR", "TRB", "AR", "ORR"],
    gateNames: {mission: "MDR", srr: "SRR", pdr: "PDR", cdr: "CDR", sir: "통합 준비검토", trr: "TRR", trb: "TRB", accept: "AR", orr: "ORR"},
    docs: [["ECSS-M10", "ECSS-M-ST-10", "Rev.1 / 2009-03-06", "사업계획과 단계 구성"], ["ECSS-REV", "ECSS-M-ST-10-01", "C / 2008-11-15", "검토회의 운영"], ["ECSS-SE", "ECSS-E-ST-10", "Rev.1 / 2017-02-15", "시스템엔지니어링 기술 기반"], ["ECSS-REQ", "ECSS-E-ST-10-06", "C / 2009-03-06", "기술 요구사항 명세"], ["ECSS-VER", "ECSS-E-ST-10-02", "Rev.1 / 2018-02-01", "검증 계획과 VCD"], ["ECSS-TEST", "ECSS-E-ST-10-03", "Rev.1 / 2022-05-31", "시험 계획과 수행"], ["ECSS-CM", "ECSS-M-ST-40", "Rev.1 / 2009-03-06", "형상과 정보 관리"]]
  },
  NASA: {
    name: "NASA", label: "미국 NASA 시스템엔지니어링", region: "미국",
    phases: ["개념 연구", "개념과 기술 개발", "예비 설계와 기술 완성", "최종 설계와 제작", "조립과 통합, 시험과 발사", "운용과 유지", "종결"],
    codes: ["Pre-Phase A", "Phase A", "Phase B", "Phase C", "Phase D", "Phase E", "Phase F"],
    note: "SE Engine의 시스템 설계 4개, 제품 실현 5개, 기술관리 8개 프로세스를 연결한다. 기술검토와 KDP는 각자의 결정 기록을 갖는다.",
    launch: "발사는 Phase D에 연결한다. KDP의 단계 전환은 의사결정권자의 별도 승인을 따른다.", output: "프로젝트 검증 매트릭스와 인계 자료",
    gates: ["MCR", "SRR", "PDR", "CDR", "SIR", "TRR", "시험 결과 검토", "SAR", "ORR"],
    gateNames: {mission: "MCR", srr: "SRR", pdr: "PDR", cdr: "CDR", sir: "SIR", trr: "TRR", trb: "시험 결과 검토", accept: "SAR", orr: "ORR"},
    docs: [["NASA-PROG", "NPR 7120.5 계열과 프로젝트 채택 지침", "채택 판본 지정", "사업 생애주기와 KDP"], ["NASA-SE", "NPR 7123.1", "D / 설계문서 참조", "17개 공통 기술 프로세스"], ["NASA-HB", "NASA Systems Engineering Handbook", "NASA/SP-2016-6105 Rev.2", "시스템엔지니어링 수행 지침"]]
  }
};
const phaseDetails = [
  ["임무 목적과 운용개념", "대안, 이해관계자 기대, 주요 위험", ["임무 개념 검토"]],
  ["실현 가능성과 기술 접근", "시스템 구조, 기술 성숙도, 검증 접근", ["SRR"]],
  ["요구사항과 예비 설계", "상하위 요구 추적, 인터페이스, 검증 계획", ["PDR"]],
  ["상세 설계와 기준점", "제작 정의, 분석 근거, 형상 통제", ["CDR"]],
  ["통합과 수준별 검증", "AIT, 시험, 결과 수용, 제품 인계", ["S-IRR", "TRR", "TRB", "제품 인수 검토"]],
  ["운용과 유지", "운용 절차, 이상 처리, 변경 이력", ["운용 준비검토"]],
  ["임무 종료와 자료 보존", "종료 처분, 최종 기록, 재사용 범위", ["운용 준비검토"]]
];
const workspaceSteps = ["시험 요청과 입력", "적용성과 테일러링", "시험 프로그램", "AIT Plan", "TSPE", "TPRO", "S-IRR", "TRR", "실행과 As-run", "PTR", "데이터 검증과 UQ", "TRPT", "TRB", "검증 종결"];
const workspaceStepInfo = [
  ["목적과 자료 권리", "시험 목적, 대상, 기한과 자료 목록을 해당 작업에 연결한다."],
  ["적용 조항", "채택 기준과 조정 사항을 프로젝트 프로파일에서 불러온다."],
  ["시험 블록", "검증 목표와 자원, 선행조건을 묶는다."],
  ["통합 순서", "조립, 인터페이스와 시험의 의존 순서를 확인한다."],
  ["사양과 기준", "수준, 기간, 측정량과 판정규칙을 고정한다."],
  ["실행 절차", "작업 순서와 채널, 자료 획득, 중단조건을 검토한다."],
  ["통합 준비", "준비 항목, 미종결 조치와 관련 위험을 검토한다."],
  ["시험 준비", "형상과 시설, 교정, 절차를 확인하고 실행 범위를 승인한다."],
  ["실제 수행", "run별 실제 조건과 변경, 이상과 원자료를 연결한다."],
  ["자료 수령", "시험 후 형상과 원자료를 접수하고 이상 처리를 배정한다."],
  ["품질과 결과", "계측 품질과 요구 충족, 불확실도를 각각 판단한다."],
  ["결과 문서", "시험 결과와 적용범위, 편차와 근거를 보고서에 연결한다."],
  ["결과 검토", "목표 달성과 부적합 영향, 남은 조치를 검토한다."],
  ["요구사항 종결", "근거 수용과 권한자 결정으로 해당 Claim을 종결한다."]
];
const summaryAutoDemoSteps = [
  {page: "overview", focus: ".hero", title: "프로젝트와 기준점", narration: "KASA 통합·검증 단계의 TVAC-03 BM1 검토 범위와 다음 의사결정을 확인합니다."},
  {page: "profile", focus: "#profileContent .grid3", title: "채택 기준과 프로파일", narration: "KASA·ECSS·NASA를 비교하되 실제 적용 판본과 테일러링은 프로젝트 서버 기록으로 구분합니다."},
  {page: "requirements", focus: "#requirementsContent .card", title: "요구사항 추적", narration: "요구사항 THM-041에서 Claim과 검증 경로로 이어지는 양방향 추적 구조를 확인합니다."},
  {page: "gates", focus: "#gatesContent .gatelist", title: "기술검토 Gate", narration: "TRB 준비조건과 회의 결정, 사업 단계 전환 결정을 서로 다른 권한 기록으로 유지합니다."},
  {page: "workspace", focus: "#workspaceContent .workcols", title: "BM1 입력과 Context", narration: "Scope Gate를 통과한 근거와 Claim revision으로 재현 가능한 ContextSnapshot을 구성합니다.", workspaceStep: 10},
  {page: "workspace", focus: "#workspaceContent .resultpanel", title: "Local LLM 입출력과 판단", narration: "Local LLM LIVE에서는 전송한 검토 입력, 모델 원문 응답, 출력 검증 결과와 Blackboard 반영을 팝업에서 단계별로 확인합니다.", workspaceStep: 10, ensureModelRun: true},
  {page: "workspace", focus: "#blackboardDialog", title: "공용 Blackboard", narration: "검증된 Contribution과 EvidenceRequest WorkItem을 공용 서버 상태로 조회합니다. 자동 시연은 사람 결정을 만들지 않습니다.", showBlackboard: true},
  {page: "closure", focus: "#closureContent .stategrid", title: "사람 승인과 공식 종결", narration: "모델 초안 수용, 데이터 품질, TRB 결정과 VerificationClosure가 서로 다른 상태 축으로 남습니다."},
  {page: "audit", focus: "#auditContent .timeline", title: "실행 증거와 내보내기", narration: "Snapshot, 원출력 hash, validation, 사람 기록과 보고서를 PostgreSQL 기반 Audit Trail에서 확인합니다."}
];

let autoDemoSteps = summaryAutoDemoSteps;

function autoDemoObserverMessage() {
  const completed = state.autoDemo.step >= autoDemoSteps.length;
  const stepIndex = completed ? autoDemoSteps.length - 1 : Math.max(0, state.autoDemo.step || 0);
  const step = autoDemoSteps[stepIndex];
  const executionStatus = state.autoDemo.error
    ? "FAILED"
    : !state.autoDemo.active
      ? state.autoDemo.runKey ? "STOPPED" : "IDLE"
      : completed
        ? "COMPLETED"
        : state.autoDemo.busy
          ? "UPDATING"
          : state.autoDemo.playing
            ? "PLAYING"
            : "PAUSED";
  return {
    type: "DEMO_STATE",
    schema: DEMO_OBSERVER_SCHEMA,
    sequence: ++demoObserverSequence,
    sent_at: new Date().toISOString(),
    source_instance_id: demoObserverSourceId,
    project_id: state.project?.id || null,
    project_display_id: state.project?.display_id || null,
    run_key: state.autoDemo.runKey || null,
    job_id: state.autoDemo.observedJobId || null,
    mode: state.autoDemo.mode || null,
    active: Boolean(state.autoDemo.active),
    playing: Boolean(state.autoDemo.playing),
    step_index: !state.autoDemo.runKey ? 0 : completed ? autoDemoSteps.length : stepIndex + 1,
    step_count: !state.autoDemo.runKey
      ? $("autoDemoWalkthrough")?.value === "SETUP" ? setupDemoSteps.length : summaryAutoDemoSteps.length
      : autoDemoSteps.length,
    step_title: !state.autoDemo.runKey ? "자동 시연 시작 전" : completed ? "최소 MVP 자동 시연 완료" : step?.title || "시연 시작 전",
    execution_status: executionStatus,
    error: state.autoDemo.error || null,
  };
}

async function flushDemoObserverSignal() {
  if (demoObserverPublishing) return;
  demoObserverPublishing = true;
  try {
    while (demoObserverPending) {
      const payload = demoObserverPending;
      demoObserverPending = null;
      try {
        await api(`/api/v1/projects/${payload.project_id}/demo-observer/sessions/${demoObserverSourceId}`, {
          method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"},
          body: JSON.stringify(payload), signal: AbortSignal.timeout(4000),
        });
      } catch (_) {
        // An observation signal never blocks or changes the actual demo.
        // The next heartbeat carries the latest state, without replaying a job.
      }
    }
  } finally {
    demoObserverPublishing = false;
  }
}

function publishAutoDemoObserverState(targetWindow = null) {
  const payload = autoDemoObserverMessage();
  demoObserverChannel?.postMessage(payload);
  const target = targetWindow || (demoObserverWindow && !demoObserverWindow.closed ? demoObserverWindow : null);
  if (target) target.postMessage(payload, window.location.origin);
  if (payload.project_id) {
    demoObserverPending = payload;
    void flushDemoObserverSignal();
  }
}

function handleAutoDemoObserverHello(message, targetWindow = null) {
  if (message?.schema !== DEMO_OBSERVER_SCHEMA || message?.type !== "OBSERVER_HELLO") return;
  if (targetWindow) {
    if (targetWindow.opener !== window) return;
    demoObserverWindow = targetWindow;
  }
  if (message.target_source_instance_id !== demoObserverSourceId) {
    if (!targetWindow) return;
    // Only the direct child can rebind after this parent document reloads.
    targetWindow.postMessage({type: "OBSERVER_SOURCE", schema: DEMO_OBSERVER_SCHEMA,
      previous_source_instance_id: message.target_source_instance_id,
      source_instance_id: demoObserverSourceId}, window.location.origin);
  }
  publishAutoDemoObserverState(targetWindow);
}

demoObserverChannel?.addEventListener("message", event => handleAutoDemoObserverHello(event.data));
window.addEventListener("message", event => {
  if (event.origin !== window.location.origin) return;
  handleAutoDemoObserverHello(event.data, event.source);
});

function openBlackboardObserver() {
  if (!state.project?.id) return message("Blackboard 관찰 창을 열 프로젝트가 없습니다.");
  const params = new URLSearchParams({project_id: state.project.id, source_id: demoObserverSourceId});
  if (state.autoDemo.runKey) params.set("run_key", state.autoDemo.runKey);
  const jobId = state.autoDemo.observedJobId;
  if (jobId) params.set("job_id", jobId);
  if (state.autoDemo.mode) params.set("mode", state.autoDemo.mode);
  demoObserverWindow = window.open(`/assets/blackboard-observer.html?${params}`, `dorilabBlackboardObserver-${demoObserverSourceId}`, "popup=yes,width=760,height=960,resizable=yes,scrollbars=yes");
  if (!demoObserverWindow) return message("브라우저에서 팝업을 허용한 뒤 다시 여십시오.");
  demoObserverWindow.focus();
  setTimeout(() => publishAutoDemoObserverState(demoObserverWindow), 250);
}
const gateDescriptions = {mission: "임무 목적과 개념, 대안과 위험", srr: "요구사항 기준점과 시스템 구조", pdr: "예비 설계와 인터페이스, 검증 접근", cdr: "상세 설계 기준점과 제작 준비", sir: "통합 형상과 주요 조치사항", trr: "시험 절차, 시설과 계측, 실행 범위", trb: "시험목표와 결과, 부적합 처분", accept: "납품 형상과 수준별 검증 기록", orr: "운용 준비와 시스템 시나리오"};

async function api(path, options = {}) {
  const response = await fetch(path, {credentials: "same-origin", ...options});
  const text = await response.text();
  let body;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `${response.status} ${response.statusText}`);
  return body;
}

function message(text, ok = false) {
  $("banner").textContent = text;
  $("banner").className = ok ? "notice banner" : "notice amber banner";
  $("banner").hidden = false;
  $("toast").textContent = text;
  $("toast").className = ok ? "feedback show" : "feedback show error";
  clearTimeout(message.timer);
  message.timer = setTimeout(() => $("toast").className = "feedback", 3500);
}

function updateRunpodSshPreview() {
  const form = $("runpodConnectionForm");
  const host = form.elements.host.value.trim() || "<HostName>";
  const port = form.elements.port.value || "<Port>";
  $("runpodSshPreview").textContent = `Host dorilab-runpod\n    HostName ${host}\n    User root\n    Port ${port}\n    IdentityFile ~/.ssh/id_ed25519\n    IdentitiesOnly yes\n    ServerAliveInterval 60\n    ServerAliveCountMax 5`;
}

function showRunpodState(text, kind = "blue") {
  $("runpodConnectionState").textContent = text;
  $("runpodConnectionState").className = kind === "amber" ? "notice amber" : "notice blue";
}

async function scanRunpodHostKey() {
  state.runpodScanSha256 = null;
  $("runpodTrustButton").hidden = true;
  $("runpodFingerprints").hidden = true;
  showRunpodState("SSH 서버의 공개 호스트 키와 지문을 확인하는 중입니다.");
  try {
    const scan = await api(`/api/v1/projects/${state.project.id}/runpod-connection/scan-host-key`, {
      method: "POST", headers: csrfHeaders
    });
    $("runpodFingerprints").textContent = scan.fingerprints.join("\n");
    $("runpodFingerprints").hidden = false;
    if (scan.host_key_state === "HOST_KEY_VERIFIED") {
      showRunpodState("호스트 키 확인 완료. SSH 로그인·추론 API 준비 상태는 아래에서 별도로 확인합니다.");
    } else if (scan.host_key_state === "HOST_KEY_CHANGED") {
      showRunpodState("HOST_KEY_CHANGED: 저장된 키와 현재 서버 키가 다릅니다. 기존 키를 자동 교체하지 않았습니다.", "amber");
    } else {
      state.runpodScanSha256 = scan.scan_sha256;
      $("runpodTrustButton").hidden = false;
      showRunpodState("RunPod의 별도 콘솔에서 아래 SHA256 지문을 대조한 뒤 ‘지문 확인 후 신뢰 (yes)’를 한 번 누르세요.", "amber");
    }
    return scan.host_key_state;
  } catch (error) {
    showRunpodState(error.message === "SSH_UNREACHABLE" ? "SSH_UNREACHABLE: 현재 HostName과 포트에 접속할 수 없습니다." : error.message, "amber");
  }
}

let runpodStatusTimer = null;

function renderRunpodRuntime(connection) {
  const controller = connection.controller || {};
  state.runpodApplying = Boolean(controller.pending);
  const runtime = connection.runtime || {};
  const sameTarget = controller.applied_host === connection.host
    && Number(controller.applied_port) === Number(connection.port);
  const remote = runtime.remote?.state || "LOCAL_ONLY";
  const remoteLabels = {
    READY: "READY / 승인된 모델 준비 완료",
    MODEL_RELEASE_MISMATCH: "MODEL_RELEASE_MISMATCH / 승인된 모델 실행환경과 다름",
    SERVICE_NOT_DEPLOYED: "SERVICE_NOT_DEPLOYED / 추론 API 미준비",
    WARMING_UP: "WARMING_UP / 모델 준비 중", SERVICE_BUSY: "SERVICE_BUSY / 모델 사용 중",
    INFERENCE_AUTH_FAILED: "INFERENCE_AUTH_FAILED / 추론 서비스 인증 실패",
    LOCAL_ONLY: "LOCAL_ONLY / 명시적 DEMO 모드"
  };
  const labels = {
    REQUESTED: "연결 적용 요청됨", CHECKING_SSH: "SSH 로그인 확인 중",
    SSH_CONNECTED: "SSH 로그인 완료", STARTING_TUNNEL: "Docker 터널 적용 중",
    ACTIVATING_LIVE: "LIVE 모드 적용 중", APPLIED: "연결 설정 적용 완료",
    SSH_AUTH_FAILED: "SSH 인증 실패 · 기존 키/agent 잠금 해제를 확인하세요",
    SSH_UNREACHABLE: "SSH 접속 불가 · IP와 외부 포트를 확인하세요",
    HOST_KEY_CONFIRMATION_REQUIRED: "호스트 키 지문 확인 필요",
    SERVICE_NOT_DEPLOYED: "SSH 연결 가능 · 추론 API가 준비되지 않았습니다",
    LOCAL_APPLY_FAILED: "로컬 연결 적용 실패 · 관리 로그를 확인하세요",
    UNKNOWN_LOCAL_APPLY_OUTCOME: "이전 연결 적용 결과 불명확 · 상태 확인 후 다시 연결하세요",
    CONNECTION_CHANGE_BUSY: "검토 실행 중 · 완료 후 다시 연결하세요",
    CONNECTION_SETTINGS_CHANGED: "저장 설정이 바뀌었습니다 · 다시 저장하세요",
    LOCAL_DOCKER_UNAVAILABLE: "로컬 Docker Desktop 확인 필요",
    CONNECTION_REQUEST_EXPIRED: "연결 적용 요청 만료 · 다시 연결하세요"
  };
  let progress = "저장한 주소를 아직 연결에 적용하지 않았습니다.";
  if (controller.pending) progress = labels[controller.code] || labels[controller.phase] || "연결 적용 중";
  else if (controller.phase === "FAILED") progress = labels[controller.code] || controller.code;
  else if (sameTarget && controller.phase === "APPLIED") progress = labels[controller.code] || labels.APPLIED;
  if (!controller.available && controller.pending) progress = "로컬 연결 관리 프로그램이 응답하지 않습니다. ./scripts/dev.sh up으로 다시 시작하세요.";
  $("runpodRuntimeState").className = `notice ${remote === "READY" && sameTarget ? "blue" : "amber"}`;
  $("runpodRuntimeState").innerHTML = `<b>${escapeHtml(progress)}</b><div class="space"></div>`
    + `<dl class="kv"><dt>저장한 접속 주소</dt><dd>${escapeHtml(connection.host || "미설정")}:${escapeHtml(connection.port ?? "—")}</dd>`
    + `<dt>현재 앱 모드</dt><dd>${escapeHtml(runtime.mode || state.status?.mode || "확인 중")}</dd>`
    + `<dt>SSH 터널 (적용 시 확인)</dt><dd>${escapeHtml(controller.ssh_state || "확인 전")}</dd>`
    + `<dt>현재 추론 API / 모델</dt><dd>${escapeHtml(remoteLabels[remote] || remote)}</dd>`
    + `<dt>연결 설정 적용</dt><dd>${sameTarget ? "저장한 주소 적용됨" : "적용 필요"}</dd></dl>`
    + `<p>SSH 호스트 키 확인과 모델 READY는 별도 검사입니다. 모델 응답은 생성 요청을 실행한 뒤에만 나옵니다.</p>`
    + (remote === "MODEL_RELEASE_MISMATCH" ? `<p>서버와 인증 연결은 가능하지만, 모델 실행 기록이 승인된 버전과 달라 생성을 보류합니다. 주소를 다시 저장해도 이 검증을 생략하지 않습니다.</p>` : "");
  const saveButton = $("runpodSaveButton");
  saveButton.disabled = Boolean(controller.pending || state.runpodSaving);
  saveButton.textContent = controller.pending ? "연결 적용 중…" : "저장 · LIVE 연결";
}

async function refreshRunpodRuntime() {
  if (!$("runpodDialog").open || !state.project) return;
  try {
    const connection = await api(`/api/v1/projects/${state.project.id}/runpod-connection`);
    renderRunpodRuntime(connection);
    await refreshStatus();
  } catch {
    $("runpodRuntimeState").className = "notice amber";
    $("runpodRuntimeState").textContent = "로컬 API 재연결 중입니다. 저장한 연결 적용은 계속 진행됩니다.";
  }
}

async function applySavedRunpodConnection() {
  const connection = await api(`/api/v1/projects/${state.project.id}/runpod-connection`);
  if (!connection.controller?.available) {
    showRunpodState("주소는 저장됐지만 로컬 연결 관리 프로그램이 실행되지 않았습니다. 최초 한 번 ./scripts/dev.sh up으로 준비한 뒤 ‘저장 · LIVE 연결’을 누르세요.", "amber");
    renderRunpodRuntime(connection);
    return;
  }
  const applied = await api(`/api/v1/projects/${state.project.id}/runpod-connection/apply`, {
    method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"},
    body: JSON.stringify({host: connection.host, port: connection.port})
  });
  showRunpodState(applied.unchanged
    ? "같은 주소가 이미 적용되어 있습니다. 현재 연결을 유지합니다."
    : "저장한 주소로 SSH 터널과 LIVE 모드를 적용합니다. 이 창을 닫아도 진행됩니다. 추론 서비스는 새로 설치하지 않습니다.");
  await refreshRunpodRuntime();
}

async function openRunpodSettings() {
  if (!state.project) return message("프로젝트를 먼저 불러와야 합니다.");
  try {
    const connection = await api(`/api/v1/projects/${state.project.id}/runpod-connection`);
    const form = $("runpodConnectionForm");
    form.elements.host.value = connection.host || "";
    form.elements.port.value = connection.port || "";
    updateRunpodSshPreview();
    $("runpodDialog").showModal();
    renderRunpodRuntime(connection);
    clearInterval(runpodStatusTimer);
    runpodStatusTimer = setInterval(refreshRunpodRuntime, 1500);
    if (connection.configured) await scanRunpodHostKey();
    else showRunpodState("HostName과 포트를 저장하면 호스트 키 지문 확인 단계가 열립니다.");
  } catch (error) { message(error.message); }
}

async function openSourceChapter(chapter) {
  try {
    const reference = await api(`/api/v1/reference/final-goal/chapters/${chapter}`);
    $("sourceDialogTitle").textContent = `설계문서 / ${chapter}장`;
    $("sourceDialogMeta").textContent = `출처: ${reference.source}. 기관별 규칙과 사례를 구성하는 기준 문서다.`;
    $("sourceDialogContent").textContent = reference.content;
    $("sourceDialog").showModal();
  } catch (error) {
    message(error.message);
  }
}

function renderShell() {
  $("nav").innerHTML = navs.map(([key, label, ico]) => `<button class="navbutton ${state.page === key ? "active" : ""}" data-page="${key}">${icon(ico)}<span>${label}</span>${key === "workspace" && state.requests.some(r => r.status === "OPEN") ? `<span class="count">${state.requests.filter(r => r.status === "OPEN").length}</span>` : ""}</button>`).join("");
  const label = navs.find(item => item[0] === state.page)?.[1] || "사업 개요";
  $("crumb").innerHTML = `<span>프로젝트</span><span>/</span><b>${escapeHtml(state.project?.display_id || "DORI-01")}</b><span>/</span><span>${label}</span>`;
}

function showPage(page, {loadData = true} = {}) {
  state.page = page;
  document.querySelectorAll(".page").forEach(node => node.hidden = node.dataset.page !== page);
  renderShell();
  $("sidebar").classList.remove("open");
  $("menuOverlay").classList.remove("active");
  if (page === "quickdemo") {
    renderQuickDemo();
    if (loadData) loadQuickDemo();
  }
  if (page === "audit" && loadData) loadAudit();
  if (page === "development" && loadData) window.dorilabDevelopment?.load();
  window.scrollTo({top: 0, behavior: "instant"});
}

const autoDemoWait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function closeOpenDialogs() {
  document.querySelectorAll("dialog[open]").forEach(dialog => dialog.close());
}

function clearAutoDemoFocus() {
  document.querySelectorAll(".autodemo-focus").forEach(node => node.classList.remove("autodemo-focus"));
}

function autoDemoRunIsCurrent(runKey) {
  return state.autoDemo.active && state.autoDemo.runKey === runKey;
}

function showDemoOverlay(node) {
  if (!node) return;
  node.hidden = false;
  if (node.showPopover) {
    if (node.matches(":popover-open")) node.hidePopover();
    node.showPopover();
  }
}

function hideAutoDemoCursor() {
  for (const id of ["autoDemoCursor", "autoDemoAction"]) {
    const node = $(id);
    if (node?.hidePopover && node.matches(":popover-open")) node.hidePopover();
    if (node) node.hidden = true;
  }
}

async function pointAutoDemoCursor(target, label, runKey, {click = false, scroll = true} = {}) {
  if (!target || !autoDemoRunIsCurrent(runKey)) return false;
  if (scroll) {
    target.scrollIntoView({behavior: "smooth", block: "center"});
    await autoDemoWait(350);
  }
  if (!autoDemoRunIsCurrent(runKey)) return false;
  const rect = target.getBoundingClientRect();
  const cursor = $("autoDemoCursor");
  cursor.classList.remove("clicking");
  const x = Math.max(10, Math.min(innerWidth - 40, rect.left + Math.min(rect.width / 2, 70)));
  cursor.classList.toggle("label-left", x > innerWidth - 285);
  cursor.style.left = `${x}px`;
  cursor.style.top = `${Math.max(10, Math.min(innerHeight - 65, rect.top + Math.min(rect.height / 2, 32)))}px`;
  $("autoDemoCursorLabel").textContent = label;
  $("autoDemoAction").textContent = `시연 커서 · ${label}`;
  showDemoOverlay($("autoDemoAction"));
  showDemoOverlay(cursor);
  await autoDemoWait(500);
  if (!autoDemoRunIsCurrent(runKey)) return false;
  if (click) {
    cursor.classList.add("clicking");
    await autoDemoWait(300);
  }
  return autoDemoRunIsCurrent(runKey);
}

async function showAutoDemoQuestion(runKey) {
  const input = $("workspaceQuestion");
  const question = selectedWorkspaceClaim()?.question;
  if (!input || !question) return;
  if (!await pointAutoDemoCursor(input, "입력 표시 · 현재 저장된 검토 질문", runKey, {click: true})) return;
  input.focus({preventScroll: true});
  const originalValue = input.value;
  const characters = Array.from(question);
  const chunk = Math.max(1, Math.ceil(characters.length / 32));
  input.value = "";
  try {
    for (let count = chunk; count < characters.length; count += chunk) {
      if (!autoDemoRunIsCurrent(runKey) || !input.isConnected) return;
      input.value = characters.slice(0, count).join("");
      await autoDemoWait(45);
    }
  } finally {
    // Display the saved input; do not manufacture a revision or save partial text.
    if (input.isConnected) input.value = originalValue;
  }
}

function autoDemoEvidence(stepIndex) {
  const step = autoDemoSteps[stepIndex];
  if (!step) return "자동 시연이 완료됐습니다.";
  if (step.action) return `${state.project?.display_id || "프로젝트 준비"} · 공개 합성 설정 자료 · 실제 로컬 저장`;
  if (step.page === "overview") return `${state.project?.display_id || "프로젝트"} · ${state.project?.baseline_display_id || "기준점 미지정"} · project v${state.project?.version || 0}`;
  if (step.page === "profile") return `채택 문서 ${state.profileData.documents?.length || 0}건 · 테일러링 ${state.profileData.tailoring?.length || 0}건 · 현재 ${state.project?.framework || "—"}`;
  if (step.page === "requirements") return `요구사항 ${state.requirements.length}건 · Claim ${state.claims.length}건 · 현재 Claim ${selectedWorkspaceClaim()?.display_id || "—"}`;
  if (step.page === "gates") return `Gate ${state.gateData.gates?.length || 0}개 · 단계 전환 기록 ${state.gateData.transitions?.length || 0}건`;
  if (step.ensureModelRun) return state.jobDetail?.model_run
    ? `${state.job?.mode || "—"} · ${state.job?.status || "—"} · validation ${state.jobDetail.model_run.validation_status || "—"}`
    : state.autoDemo.mode === "LIVE"
      ? "인증된 RunPod의 Local LLM에 새 합성 BM1 generation을 요청하는 중입니다."
      : "저장된 검토가 없으면 DEMO REPLAY Job 한 건을 멱등적으로 준비합니다.";
  if (step.showBlackboard) {
    if (!state.autoDemo.board) return "이번 실행의 Blackboard를 조회하는 중입니다.";
    const summary = state.autoDemo.board?.summary || {};
    return `Contribution ${summary.contributions || 0}건 · WorkItem ${summary.work_items || 0}건 · Dependency ${summary.dependencies || 0}건`;
  }
  if (step.page === "workspace") return `Evidence ${state.evidence.length}건 · 직접 선택 ${state.selectedEvidenceIds.length}건 · RAG ${activeRetrieval()?.run.selected_count || 0}건 · 입력 Claim v${selectedWorkspaceClaim()?.version || 0}`;
  if (step.page === "closure") return `종결 대상 ${state.closureData.claims?.length || 0}건 · 종결 이력 ${state.closureData.history?.length || 0}건`;
  if (step.page === "audit") return `Snapshot ${state.auditData.summary?.execution_snapshots || 0}건 · ModelRun ${state.auditData.summary?.model_runs || 0}건 · 사람 기록 ${state.auditData.summary?.human_records || 0}건`;
  return "서버 상태를 읽어 현재 화면에 투영했습니다.";
}

function resetQwenTrace(jobId = null) {
  state.autoDemo.trace = {
    jobId,
    rawArtifactId: null,
    rawText: null,
    rawError: null,
    board: null,
    boardLoaded: false,
  };
}

function prettyNativeJson(value) {
  if (value === null || value === undefined || value === "") return "아직 수신되지 않았습니다.";
  if (typeof value !== "string") return JSON.stringify(value, null, 2);
  try { return JSON.stringify(JSON.parse(value), null, 2); }
  catch { return value; }
}

function qwenInputText(snapshot) {
  const messages = snapshot?.messages || [];
  if (!messages.length) return "ContextSnapshot을 준비하는 중입니다.";
  return messages.map(message => `[${String(message.role || "user").toUpperCase()}]\n${prettyNativeJson(message.content)}`).join("\n\n");
}

function qwenTraceAction(detail) {
  const parsed = detail?.model_run?.parsed_output || {};
  return parsed.actions?.[0] || parsed;
}

function qwenJobBlackboard(board, jobId) {
  if (!board || !jobId) return {contributions: [], workItems: [], dependencies: []};
  return {
    contributions: (board.contributions || []).filter(item => item.source_job_id === jobId),
    workItems: (board.work_items || []).filter(item => item.source_job_id === jobId),
    dependencies: (board.dependencies || []).filter(item => item.source_job_id === jobId),
  };
}

const quickReasonDescriptions = {
  AS_RUN_MISSING: "실제 시험 실행 정보나 결과가 빠져 있습니다.",
  BOUNDARY_CONDITION_UNRESOLVED: "검토에 필요한 경계조건이 확인되지 않았습니다.",
  CONFIGURATION_SCOPE_UNRESOLVED: "현재 형상에 해당하는 자료인지 확인되지 않았습니다.",
  EVIDENCE_INTERPRETATION_ERROR: "제공된 근거와 현재 설명이 서로 맞지 않습니다.",
  MEASUREMENT_MAPPING_MISMATCH: "측정 위치나 물리량의 연결 관계가 맞지 않습니다.",
  METHOD_INTERPRETATION_ERROR: "제안한 방법이 제공된 절차나 계산 규칙과 맞지 않습니다.",
  MODAL_INPUTS_MISSING: "판단에 필요한 모달 입력 자료가 빠져 있습니다.",
  MODEL_SCOPE_EXCEEDED: "주장이 모델이나 시험으로 확인된 범위를 벗어납니다.",
  MODE_SELECTION_MISMATCH: "모드 선택이나 대응 관계를 다시 확인해야 합니다.",
  MONITORING_COVERAGE_INSUFFICIENT: "기록된 측정 범위만으로는 판단하기 어렵습니다.",
  SUPPORTING_EVIDENCE_MISSING: "판단을 뒷받침할 자료가 더 필요합니다.",
  TEST_ARTIFACT_UNMODELED: "시험 장치의 영향이 현재 모델에 반영되지 않았습니다.",
  EVIDENCE_SUFFICIENT: "제공된 근거 범위에서 추가 이견을 찾지 못했습니다.",
  EVIDENCE_MISSING: "판단에 필요한 자료가 더 필요합니다."
};

function quickDemoActionCopy(action) {
  if (action === "REQUEST_EVIDENCE") return {title: "자료가 더 필요합니다", body: "Local LLM이 현재 자료만으로 결론을 내리기 어렵다고 판단했습니다.", style: "wait"};
  if (["CHALLENGE", "CONTRADICT"].includes(action)) return {title: "현재 판단을 다시 확인해야 합니다", body: "Local LLM이 제공된 근거와 현재 주장 사이의 문제를 찾았습니다.", style: "bad"};
  if (action === "NO_ACTION_REQUIRED") return {title: "추가 이견이 없습니다", body: "Local LLM은 제공된 자료 범위에서 검토를 계속할 수 있다고 제안했습니다.", style: "ok"};
  return {title: "Local LLM 판단을 기다리는 중입니다", body: "입력 고정, 원격 생성과 출력 검증이 끝나면 여기에 쉬운 말로 표시합니다.", style: "info"};
}

function quickDemoCurrentDetail() {
  if (state.quickDemo.detail?.job?.mode === "LIVE_MODEL_RUN") return state.quickDemo.detail;
  if (state.quickDemo.busy || ["SUBMITTING", "FAILED"].includes(state.quickDemo.stage)) return null;
  if (state.jobDetail?.job?.mode === "LIVE_MODEL_RUN") return state.jobDetail;
  return null;
}

function quickDemoInputs() {
  const retrieval = activeRetrieval();
  const chunks = (retrieval?.results || []).filter(item => item.selected);
  const selected = new Set(state.selectedEvidenceIds);
  const evidence = state.evidence.filter(item => selected.has(item.id) && evidenceEligibility(item)[0]);
  return {retrieval, chunks, evidence};
}

function quickDemoHumanState(detail) {
  const decision = detail?.decisions?.at(-1);
  if (!decision) return {title: "사람 검토 대기", body: "Local LLM의 결과는 제안입니다. 검토 책임자가 수용하거나 수정 의견을 남겨야 합니다.", style: "wait"};
  if (decision.disposition === "ACCEPTED") return {title: "사람이 초안을 수용했습니다", body: "이 기록은 AI 초안 수용이며 공식 시험 승인이나 요구사항 종결과는 별도입니다.", style: "ok"};
  return {title: "사람이 수정을 요청했습니다", body: "원출력은 그대로 보존되고 사람 의견이 별도 기록으로 남았습니다.", style: "bad"};
}

function quickDemoStep(number, title, detail, stateClass) {
  return `<div class="quick-step ${stateClass}"><span>${number}</span><div><b>${escapeHtml(title)}</b><small>${escapeHtml(detail)}</small></div></div>`;
}

function renderQuickDemo() {
  const root = $("quickDemoContent");
  if (!root) return;
  const detail = quickDemoCurrentDetail();
  const job = detail?.job;
  const model = detail?.model_run;
  const action = qwenTraceAction(detail);
  const actionName = action?.action;
  const actionCopy = quickDemoActionCopy(actionName);
  const reasonCode = action?.reason || action?.reason_code;
  const reason = quickReasonDescriptions[reasonCode] || reasonCode || actionCopy.body;
  const requested = action?.requested_items || action?.requested_evidence || [];
  const inputs = quickDemoInputs();
  const inputCount = inputs.chunks.length + inputs.evidence.length;
  const firstChunk = inputs.chunks[0];
  const firstEvidence = inputs.evidence[0];
  const boardForJob = qwenJobBlackboard(state.quickDemo.board, job?.id);
  const projected = boardForJob.contributions.length + boardForJob.workItems.length > 0;
  const workItem = boardForJob.workItems[0];
  const decision = detail?.decisions?.at(-1);
  const humanState = quickDemoHumanState(detail);
  const role = $("role")?.value?.split("@")[0] || "engineer";
  const canDecide = ["reviewer", "approver"].includes(role)
    && job?.status === "AWAITING_REVIEW"
    && model?.validation_status === "VALID";
  const liveReady = qwenLiveAutoDemoReady();
  const remoteState = state.status?.remote?.state || "LOCAL_ONLY";
  const jobActive = job && ["QUEUED", "DISPATCHING", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING"].includes(job.status);
  const stageText = state.quickDemo.busy
    ? job?.status === "RUNNING" ? "RunPod의 Local LLM이 답을 만드는 중" : "입력과 결과를 확인하는 중"
    : liveReady ? "실제 RunPod의 Local LLM 연결 준비됨" : `RunPod 연결 상태: ${remoteState}`;
  const evidencePreview = firstChunk
    ? `<div class="quick-source"><span class="pill ok">RAG 문서 청크</span><h3>${escapeHtml(firstChunk.filename)}</h3><p>${escapeHtml((firstChunk.chunk_text || "").slice(0, 360))}${(firstChunk.chunk_text || "").length > 360 ? "…" : ""}</p><small>${escapeHtml(firstChunk.locator || "원문 위치 기록됨")}</small></div>`
    : firstEvidence
      ? `<div class="quick-source"><span class="pill ok">등록 근거</span><h3>${escapeHtml(firstEvidence.filename)}</h3><p>${escapeHtml(firstEvidence.quote || "서버에 등록된 근거입니다.")}</p><small>${escapeHtml(firstEvidence.display_id)}</small></div>`
      : `<div class="quick-empty"><b>아직 선택된 문서 근거가 없습니다.</b><p>상세 화면에서 문서를 검색해도 되고, 지금 실행해 Local LLM이 어떤 자료를 요청하는지 볼 수도 있습니다.</p></div>`;
  const requestedHtml = requested.length
    ? `<div class="quick-request"><b>Local LLM이 요청한 자료</b><ul>${requested.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`
    : "";
  const resultHtml = model
    ? `<div class="quick-judgment ${actionCopy.style}"><span class="quick-judgment-icon">${actionCopy.style === "ok" ? "✓" : actionCopy.style === "bad" ? "!" : "?"}</span><div><span class="eyebrow">Local LLM 판단</span><h2>${escapeHtml(actionCopy.title)}</h2><p>${escapeHtml(reason)}</p></div></div>${requestedHtml}`
    : `<div class="quick-empty"><b>${escapeHtml(actionCopy.title)}</b><p>${escapeHtml(state.quickDemo.error || (jobActive ? `현재 상태: ${job.status}` : actionCopy.body))}</p></div>`;
  const boardHtml = projected
    ? `<div class="quick-board-result"><span class="pill info">BLACKBOARD 기록됨</span><h3>${escapeHtml(workItem?.title || actionCopy.title)}</h3><p>${escapeHtml(workItem?.purpose || boardForJob.contributions[0]?.content?.reason || "Local LLM 판단과 근거가 검토 제안으로 저장됐습니다.")}</p><small>제안 ${boardForJob.contributions.length}건 · 다음 작업 ${boardForJob.workItems.length}건</small></div>`
    : model?.validation_status === "VALID"
      ? `<div class="quick-empty"><b>검증된 판단을 저장했습니다.</b><p>${actionName === "NO_ACTION_REQUIRED" ? "새 자료 요청 없이 검토 제안만 기록했습니다." : "Blackboard 투영 상태를 확인하고 있습니다."}</p></div>`
      : `<div class="quick-empty"><b>다음 업무는 아직 없습니다.</b><p>Local LLM 출력이 계약 검증을 통과한 뒤에만 공용 작업으로 연결됩니다.</p></div>`;
  const receipt = model?.receipt || {};
  root.innerHTML = `<div class="pagehead quick-pagehead"><div><div class="eyebrow">ONE PAGE DEMO</div><h1>문서를 읽고, 판단하고, 다음 일을 만듭니다</h1><p class="subtitle">복잡한 화면은 그대로 두었습니다. 이 탭에서는 DoriLab의 핵심 흐름 한 번만 확인합니다.</p></div><div class="buttons"><span class="pill ${liveReady ? "ok" : "wait"}">${escapeHtml(stageText)}</span><button class="btn" data-quick-refresh type="button">상태 새로고침</button></div></div>
    <section class="quick-hero">
      <div><span class="eyebrow">현재 시연 질문</span><h2>${escapeHtml(selectedWorkspaceClaim()?.question || "현재 자료로 열모델 검토를 계속할 수 있는가?")}</h2><p>버튼을 누르면 현재 선택된 합성 BM1 자료를 실제 RunPod에서 실행되는 Local LLM에 보냅니다. Local LLM은 팀이 관리하는 모델 서비스의 표시 이름입니다. 응답은 검증 후 Blackboard의 제안과 다음 작업으로 저장되며, 사람이 확인하기 전에는 확정되지 않습니다.</p></div>
      <button class="btn primary quick-run" data-run-quick-demo type="button" ${!liveReady || state.quickDemo.busy ? "disabled" : ""}>${state.quickDemo.busy ? "Local LLM 응답 기다리는 중…" : "Local LLM으로 검토하기"}</button>
    </section>
    ${state.quickDemo.error ? `<div class="notice amber quick-error">${escapeHtml(state.quickDemo.error)} · REPLAY로 자동 대체하지 않았습니다.</div>` : ""}
    <div class="quick-flow" aria-label="빠른 시연 처리 흐름">
      ${quickDemoStep(1, "문서 근거", inputCount ? `${inputCount}개 입력 준비` : "입력 없이 부족 자료 확인", inputCount ? "done" : "ready")}
      ${quickDemoStep(2, "Local LLM 검토", model ? "실제 응답 수신" : state.quickDemo.busy ? "응답 대기" : "실행 대기", model ? "done" : state.quickDemo.busy ? "active" : "ready")}
      ${quickDemoStep(3, "다음 업무", projected ? "Blackboard에 기록" : model ? "검증 결과 저장" : "판단 뒤 생성", projected || model ? "done" : "ready")}
      ${quickDemoStep(4, "사람 확인", decision ? "결정 기록됨" : "사람 결정 대기", decision ? "done" : model ? "active" : "ready")}
    </div>
    <div class="quick-main-grid">
      <section class="card quick-card"><div class="cardhead"><div><span class="quick-number">1</span><h3>Local LLM이 읽는 근거</h3><p>RAG 검색과 Scope Gate를 통과한 현재 입력</p></div><span class="pill info">${inputCount}개</span></div><div class="cardbody">${evidencePreview}<div class="quick-card-actions"><button class="btn link" data-page="workspace">문서와 검색 결과 자세히 보기 →</button></div></div></section>
      <section class="card quick-card quick-result-card"><div class="cardhead"><div><span class="quick-number">2</span><h3>Local LLM은 무엇을 판단했나</h3><p>원출력을 고치지 않고 계약 검증한 결과</p></div>${model ? `<span class="pill ${model.validation_status === "VALID" ? "ok" : "bad"}">${escapeHtml(model.validation_status)}</span>` : ""}</div><div class="cardbody">${resultHtml}${model ? `<div class="quick-card-actions"><button class="btn" data-quick-trace>실제 입출력 전체 보기</button></div>` : ""}</div></section>
      <section class="card quick-card"><div class="cardhead"><div><span class="quick-number">3</span><h3>그래서 무슨 일이 생겼나</h3><p>검증된 판단만 공용 상태와 다음 작업에 연결</p></div></div><div class="cardbody">${boardHtml}<div class="quick-card-actions"><button class="btn" data-open-blackboard>Blackboard 전체 보기</button></div></div></section>
      <section class="card quick-card"><div class="cardhead"><div><span class="quick-number">4</span><h3>마지막 판단은 사람이 합니다</h3><p>AI 제안과 사람 결정, 공식 승인을 분리</p></div><span class="pill ${humanState.style}">${escapeHtml(humanState.title)}</span></div><div class="cardbody"><div class="quick-human ${humanState.style}"><h3>${escapeHtml(humanState.title)}</h3><p>${escapeHtml(humanState.body)}</p></div>${job ? `<div class="quick-card-actions"><button class="btn primary" data-quick-decision="ACCEPTED" ${canDecide ? "" : "disabled"}>초안 수용</button><button class="btn" data-quick-decision="REVISION_REQUESTED" ${canDecide ? "" : "disabled"}>수정 요청</button><button class="btn link" data-open-quick-workspace>상세 검토 화면</button></div>${!canDecide && !decision ? '<p class="tiny muted">상단 역할을 ‘검토 책임자’로 바꾸면 사람 결정을 기록할 수 있습니다.</p>' : ""}` : '<p class="tiny muted">Local LLM 검토 결과가 생기면 사람 결정 버튼이 열립니다.</p>'}</div></section>
    </div>
    <details class="quick-advanced" ${state.quickDemo.advancedOpen ? "open" : ""}><summary data-quick-advanced-summary>기술 기록 보기</summary><dl class="kv"><dt>Review Job</dt><dd>${escapeHtml(job?.id || "실행 전")}</dd><dt>상태</dt><dd>${escapeHtml(job?.status || state.quickDemo.stage)}</dd><dt>원출력 SHA256</dt><dd>${escapeHtml(model?.raw_sha256 || "실행 전")}</dd><dt>RunPod boot</dt><dd>${escapeHtml(receipt.boot_id || "실행 전")}</dd><dt>입력 / 출력 token</dt><dd>${escapeHtml(model ? `${receipt.input_tokens ?? model.input_tokens ?? "—"} / ${receipt.generated_tokens ?? model.generated_tokens ?? "—"}` : "실행 전")}</dd></dl></details>
    <div class="notice amber quick-boundary"><b>여기까지가 AI의 역할입니다.</b> Local LLM은 자료를 읽고 제안과 다음 작업을 만들지만, 시험 승인·Gate 결정·공식 검증 종결은 만들지 않습니다.</div>`;
}

async function loadQuickDemo() {
  if (!state.project || state.quickDemo.busy) return;
  if (state.quickDemo.projectId !== state.project.id) {
    state.quickDemo = {projectId: state.project.id, busy: false, error: null, stage: "IDLE", jobId: null, detail: null, board: null, advancedOpen: false};
  }
  try {
    const target = state.jobs.find(item => item.id === state.quickDemo.jobId && item.mode === "LIVE_MODEL_RUN")
      || state.jobs.find(item => item.mode === "LIVE_MODEL_RUN");
    const [detail, board] = await Promise.all([
      target ? api(`/api/v1/jobs/${target.id}`) : Promise.resolve(null),
      api(`/api/v1/projects/${state.project.id}/blackboard`)
    ]);
    state.quickDemo.jobId = detail?.job?.id || null;
    state.quickDemo.detail = detail;
    state.quickDemo.board = board;
    state.quickDemo.error = null;
    state.quickDemo.stage = detail ? "LOADED" : "IDLE";
  } catch (error) {
    state.quickDemo.error = `저장된 시연 결과 조회 실패: ${error.message}`;
  }
  renderQuickDemo();
}

async function runQuickDemo() {
  if (state.quickDemo.busy || !state.project) return;
  const claim = selectedWorkspaceClaim();
  if (!claim) return message("빠른 시연에 사용할 BM1 Claim이 없습니다.");
  state.quickDemo.busy = true;
  state.quickDemo.error = null;
  state.quickDemo.stage = "SUBMITTING";
  state.quickDemo.detail = null;
  renderQuickDemo();
  try {
    await refreshStatus();
    if (!qwenLiveAutoDemoReady()) throw new Error(`Local LLM LIVE 준비가 필요합니다. 현재 원격 상태는 ${state.status?.remote?.state || "LOCAL_ONLY"}입니다.`);
    const selected = new Set(state.selectedEvidenceIds);
    const evidenceIds = state.evidence.filter(item => selected.has(item.id) && evidenceEligibility(item)[0]).map(item => item.id);
    const result = await api(`/api/v1/projects/${state.project.id}/reviews`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": `quick-live:${crypto.randomUUID()}`},
      body: JSON.stringify({claim_id: claim.id, evidence_ids: evidenceIds, retrieval_run_id: activeRetrieval()?.run.id || null, mode: "LIVE_MODEL_RUN"})
    });
    state.quickDemo.jobId = result.job_id;
    state.quickDemo.stage = "QUEUED";
    state.job = {id: result.job_id};
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const detail = await api(`/api/v1/jobs/${result.job_id}`);
      state.quickDemo.detail = detail;
      state.quickDemo.stage = detail.job.status;
      state.job = detail.job;
      state.jobDetail = detail;
      renderQuickDemo();
      if (!["QUEUED", "DISPATCHING", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING"].includes(detail.job.status)) break;
      await autoDemoWait(500);
    }
    if (["QUEUED", "DISPATCHING", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING"].includes(state.quickDemo.detail?.job?.status)) throw new Error("Local LLM 응답 대기 시간이 초과됐습니다. Job은 자동 재실행하지 않았습니다.");
    await loadJobsAndRequests();
    state.quickDemo.detail = state.jobDetail?.job?.id === result.job_id
      ? state.jobDetail
      : await api(`/api/v1/jobs/${result.job_id}`);
    state.quickDemo.board = await api(`/api/v1/projects/${state.project.id}/blackboard`);
    state.quickDemo.stage = "COMPLETE";
    if (!state.quickDemo.detail?.model_run) throw new Error(`Local LLM 검토가 ${state.quickDemo.detail?.job?.status || "UNKNOWN"} 상태로 끝났습니다.`);
    message("실제 Local LLM 응답, Validator 결과와 Blackboard 반영을 한 화면에 불러왔습니다.", true);
  } catch (error) {
    state.quickDemo.error = error.message;
    state.quickDemo.stage = "FAILED";
    message(error.message);
  } finally {
    state.quickDemo.busy = false;
    renderQuickDemo();
  }
}

function useQuickDemoDetail() {
  const detail = quickDemoCurrentDetail();
  if (!detail) return null;
  state.job = detail.job;
  state.jobDetail = detail;
  return detail;
}

function setQwenTraceStage(name, status, note) {
  const node = document.querySelector(`[data-qwen-stage="${name}"]`);
  if (!node) return;
  node.className = `qwen-stage ${status}`;
  const noteNode = node.querySelector("small");
  if (noteNode) noteNode.textContent = note;
}

function renderQwenTraceDialog(detail = state.jobDetail) {
  const trace = state.autoDemo.trace;
  const job = detail?.job;
  const snapshot = detail?.snapshot;
  const model = detail?.model_run;
  const action = qwenTraceAction(detail);
  const validation = model?.validation_status;
  const terminal = job && !["QUEUED", "DISPATCHING", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING"].includes(job.status);
  const remoteReady = state.status?.remote?.state === "READY";
  const boardForJob = qwenJobBlackboard(trace.board, job?.id);
  const projected = boardForJob.contributions.length + boardForJob.workItems.length > 0;

  $("qwenTraceStatus").textContent = !job
    ? "새 LIVE Job을 만들고 ContextSnapshot을 준비하는 중입니다."
    : model
      ? `Job ${job.id} · ${job.status} · 원출력 저장과 계약 검증 완료`
      : `Job ${job.id} · ${job.status} · RunPod의 Local LLM 응답을 기다리는 중입니다.`;
  $("qwenTraceStatus").className = `notice ${job?.status === "FAILED" || job?.status === "UNKNOWN_OUTCOME" ? "amber" : "blue"}`;

  setQwenTraceStage("input", snapshot ? "done" : "active", snapshot ? "Snapshot 고정" : "구성 중");
  setQwenTraceStage("transport", remoteReady ? "done" : "fail", remoteReady ? "SSH tunnel READY" : state.status?.remote?.state || "확인 중");
  setQwenTraceStage("model", model ? "done" : terminal ? "fail" : job ? "active" : "pending", model ? "원출력 수신" : job?.status || "대기");
  setQwenTraceStage("validator", validation === "VALID" ? "done" : validation === "REJECTED" ? "fail" : model ? "active" : "pending", validation || "대기");
  setQwenTraceStage("blackboard", projected ? "done" : trace.boardLoaded && model ? "done" : validation === "VALID" ? "active" : "pending", projected ? `제안 ${boardForJob.contributions.length} · 작업 ${boardForJob.workItems.length}` : trace.boardLoaded && model ? "변경 없음" : "대기");

  $("qwenTraceInput").textContent = qwenInputText(snapshot);
  $("qwenTraceOutput").textContent = trace.rawText || (trace.rawError ? `원출력 조회 실패: ${trace.rawError}` : model ? "보존된 원출력을 불러오는 중입니다." : "Local LLM이 생성 중입니다. 출력이 끝나면 원문 그대로 표시됩니다.");

  const requested = action.requested_evidence || action.requested_items || [];
  const evidenceRefs = action.evidence_refs || [];
  const decision = action.action || (model ? "출력 계약 불일치" : "판단 대기");
  $("qwenTraceDecisionBadge").textContent = decision;
  $("qwenTraceDecisionBadge").className = `pill ${validation === "VALID" ? (decision === "REQUEST_EVIDENCE" ? "wait" : "ok") : model ? "bad" : "info"}`;
  $("qwenTraceDecision").innerHTML = `<dt>판단</dt><dd>${escapeHtml(decision)}</dd><dt>판단 사유</dt><dd>${escapeHtml(action.reason || action.reason_code || "아직 없음")}</dd><dt>참조 근거</dt><dd>${escapeHtml(evidenceRefs.join(", ") || "없음")}</dd><dt>요청 자료</dt><dd>${escapeHtml(requested.join(", ") || "없음")}</dd>`;

  const receipt = model?.receipt || {};
  const tokens = model?.token_usage || receipt.token_usage || {};
  $("qwenTraceReceipt").innerHTML = `<dt>Contract</dt><dd><code>${escapeHtml(snapshot?.contract_id || "준비 중")}</code></dd><dt>Request</dt><dd><code>${escapeHtml(model?.request_id || job?.id || "준비 중")}</code></dd><dt>Boot</dt><dd><code>${escapeHtml(model?.boot_id || "응답 대기")}</code></dd><dt>Tokens</dt><dd>${escapeHtml(`${tokens.input_tokens ?? "—"} 입력 / ${tokens.generated_tokens ?? "—"} 출력 / ${tokens.reserved_new_tokens ?? "—"} 예약`)}</dd><dt>Finish</dt><dd>${escapeHtml(model?.finish_reason || "대기")}</dd><dt>Raw SHA256</dt><dd><code>${escapeHtml(model?.raw_sha256 || "대기")}</code></dd>`;

  const contribution = boardForJob.contributions[0];
  const workItem = boardForJob.workItems[0];
  $("qwenTraceBlackboard").innerHTML = projected
    ? `<b>공용 Blackboard에 반영됨</b><br>Contribution ${boardForJob.contributions.length}건 · ${escapeHtml(contribution?.status || "—")}<br>WorkItem ${boardForJob.workItems.length}건 · ${escapeHtml(workItem?.status || "해당 없음")}<br>Dependency ${boardForJob.dependencies.length}건 · Router는 사람 검토 경계에서 정지`
    : trace.boardLoaded && model
      ? "검증 결과에 따라 새 Blackboard 객체가 생성되지 않았습니다. 원출력과 Validation 기록은 보존됐습니다."
      : "Validator 통과 뒤 모델 제안과 다음 작업을 서버 공용 상태에 기록합니다.";
  $("qwenTraceContinue").disabled = !terminal || !model || state.autoDemo.busy;
}

async function hydrateQwenTraceDialog(detail = state.jobDetail) {
  if (!detail) return;
  const trace = state.autoDemo.trace;
  if (trace.jobId !== detail.job.id) resetQwenTrace(detail.job.id);
  renderQwenTraceDialog(detail);
  const artifactId = detail.model_run?.raw_artifact_id;
  if (artifactId && state.autoDemo.trace.rawArtifactId !== artifactId) {
    state.autoDemo.trace.rawArtifactId = artifactId;
    try {
      const response = await fetch(`/api/v1/artifacts/${artifactId}/download`, {credentials: "same-origin"});
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      state.autoDemo.trace.rawText = await response.text();
    } catch (error) {
      state.autoDemo.trace.rawError = error.message;
    }
  }
  if (detail.model_run && !state.autoDemo.trace.boardLoaded) {
    try {
      state.autoDemo.trace.board = await api(`/api/v1/projects/${state.project.id}/blackboard`);
    } catch (error) {
      state.autoDemo.trace.rawError = state.autoDemo.trace.rawError || `Blackboard: ${error.message}`;
    } finally {
      state.autoDemo.trace.boardLoaded = true;
    }
  }
  renderQwenTraceDialog(detail);
}

async function openQwenTraceDialog(detail = state.jobDetail) {
  if (detail?.job && state.autoDemo.trace.jobId !== detail.job.id) resetQwenTrace(detail.job.id);
  renderQwenTraceDialog(detail);
  if (!$("qwenTraceDialog").open) $("qwenTraceDialog").showModal();
  if (detail) await hydrateQwenTraceDialog(detail);
}

function renderAutoDemoPanel(stepIndex) {
  const step = autoDemoSteps[stepIndex];
  const panel = $("autoDemoPanel");
  panel.hidden = false;
  $("autoDemoBoundary").textContent = state.autoDemo.mode === "LIVE" ? "Local LLM LIVE" : "DEMO REPLAY";
  $("autoDemoBoundary").className = state.autoDemo.mode === "LIVE" ? "pill ok" : "pill wait";
  $("autoDemoCount").textContent = `${stepIndex + 1} / ${autoDemoSteps.length}`;
  $("autoDemoProgress").style.width = `${(stepIndex + 1) / autoDemoSteps.length * 100}%`;
  $("autoDemoTitle").textContent = step.title;
  $("autoDemoChapter").textContent = step.chapter || "기존 요약 시연";
  $("autoDemoOperation").textContent = state.autoDemo.operation || "";
  $("autoDemoOperation").hidden = !state.autoDemo.operation;
  const atLiveHumanBoundary = state.autoDemo.mode === "LIVE"
    && step.ensureModelRun
    && !state.autoDemo.busy
    && Boolean(state.jobDetail?.model_run);
  $("autoDemoNarration").textContent = state.autoDemo.error
    ? `자동 시연을 계속하려면 다음 상태를 확인하십시오: ${state.autoDemo.error}`
    : atLiveHumanBoundary
      ? `${step.narration} 새 Local LLM 결과를 저장했습니다. 자동 진행은 여기서 멈췄습니다. 사람이 검토하거나 ‘다음’을 눌러 Blackboard 투영을 확인하십시오.`
      : step.narration;
  $("autoDemoEvidence").textContent = autoDemoEvidence(stepIndex);
  $("autoDemoPrev").disabled = stepIndex === 0 || state.autoDemo.busy;
  $("autoDemoNext").disabled = state.autoDemo.busy || Boolean(state.autoDemo.error);
  $("autoDemoToggle").disabled = state.autoDemo.busy || Boolean(state.autoDemo.error);
  $("autoDemoToggle").textContent = state.autoDemo.busy ? "준비 중" : state.autoDemo.playing ? "일시정지" : "계속 재생";
  publishAutoDemoObserverState();
}

async function waitForAutoDemoJob(jobId, runKey = state.autoDemo.runKey) {
  clearTimeout(state.timer);
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const detail = await api(`/api/v1/jobs/${jobId}`);
    if (!autoDemoRunIsCurrent(runKey)) return;
    state.job = detail.job;
    state.jobDetail = detail;
    renderWorkspace();
    publishAutoDemoObserverState();
    if (state.autoDemo.mode === "LIVE") await hydrateQwenTraceDialog(detail);
    if (!["QUEUED", "DISPATCHING", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING"].includes(detail.job.status)) {
      await loadJobsAndRequests();
      if (["FAILED", "UNKNOWN_OUTCOME"].includes(detail.job.status)) throw new Error(detail.job.error_code || detail.job.status);
      return;
    }
    await autoDemoWait(500);
  }
  throw new Error("AUTOPLAY_JOB_TIMEOUT");
}

function qwenLiveAutoDemoReady() {
  return state.status?.mode !== "DEMO"
    && state.status?.remote?.state === "READY"
    && state.project?.mode === "DEMO"
    && state.project?.data_policy === "EXTERNAL_SYNTHETIC_ALLOWED";
}

function reusableAutoDemoReplayJob() {
  if (activeRetrieval()) return null;
  const claim = selectedWorkspaceClaim();
  return state.jobs.find(job => job.claim_id === claim?.id && job.mode === "REPLAY" && job.freshness === "CURRENT"
    && ["AWAITING_REVIEW", "OUTPUT_REJECTED", "COMPLETED"].includes(job.status)) || null;
}

function renderAutoDemoModeDialog() {
  const detailed = $("autoDemoWalkthrough").value === "SETUP";
  const replayAvailable = state.status?.mode === "DEMO" || (!detailed && Boolean(reusableAutoDemoReplayJob()));
  const liveReady = detailed
    ? state.status?.mode !== "DEMO" && state.status?.remote?.state === "READY"
    : qwenLiveAutoDemoReady();
  $("autoDemoReplayStart").disabled = !replayAvailable;
  $("autoDemoLiveStart").disabled = !liveReady;
  const mode = state.status?.mode || "UNKNOWN";
  const remote = state.status?.remote?.state || "LOCAL_ONLY";
  const policy = state.project?.data_policy || "정책 미확인";
  $("autoDemoModeState").textContent = `App ${mode} · Remote ${remote} · ${state.project?.display_id || "프로젝트 미선택"} · ${policy}`;
  $("autoDemoModeState").className = liveReady ? "notice blue" : "notice amber";
  const remoteHints = {
    INFERENCE_AUTH_FAILED: "RunPod 서비스 인증 정보가 맞지 않습니다. ./scripts/dev.sh up을 실행하면 검증된 SSH로 현재 서비스 토큰을 동기화합니다.",
    MODEL_RELEASE_MISMATCH: "접속은 됐지만 모델 릴리스 또는 출력 계약이 로컬 설정과 다릅니다. 승인된 모델과 계약 확인이 필요합니다.",
    WARMING_UP: "RunPod에서 모델을 준비하는 중입니다. READY가 되면 시작 버튼이 자동으로 활성화됩니다.",
    SERVICE_BUSY: "RunPod가 다른 생성을 처리하고 있습니다. 준비 상태가 바뀌면 이 창에도 반영됩니다.",
    SERVICE_NOT_DEPLOYED: "원격 추론 API에 연결할 수 없습니다. RunPod 연결의 주소·SSH 포트와 서비스 실행 상태를 확인하세요.",
    LOCAL_ONLY: "현재 앱은 DEMO 모드입니다. Local LLM LIVE를 사용하려면 RunPod 연결 후 ./scripts/dev.sh up을 실행하세요.",
  };
  $("autoDemoLiveHint").textContent = liveReady
    ? detailed ? "Local LLM이 READY입니다. 새 합성 프로젝트의 설정·문서 검색을 마친 뒤 실제 입력 한 건을 실행합니다." : "Local LLM 연결과 모델 릴리스 확인이 끝났습니다. 아래 버튼으로 실제 합성 입력 한 건을 실행합니다."
    : remoteHints[remote] || "Local LLM LIVE는 READY인 RunPod와 외부 합성 입력을 허용한 DEMO 프로젝트에서 실행할 수 있습니다.";
  $("autoDemoLiveHint").className = liveReady ? "notice blue smalltext" : "notice amber smalltext";
  $("autoDemoReplayHint").textContent = replayAvailable
    ? "REPLAY 시연을 사용할 수 있습니다. 실제 Local LLM 호출은 발생하지 않습니다."
    : "현재 입력에 맞는 REPLAY 기록이 없습니다. 리허설은 ./scripts/dev.sh up --demo로 앱을 시작하세요.";
  $("autoDemoReplayHint").className = replayAvailable ? "notice blue smalltext" : "notice amber smalltext";
}

async function openAutoDemoModeDialog() {
  if (state.autoDemo.busy) return message("현재 시연 단계가 진행 중입니다. 완료 후 새 시연을 시작할 수 있습니다.");
  stopAutoDemo();
  state.autoDemo.runKey = null;
  state.autoDemo.observedJobId = null;
  state.autoDemo.board = null;
  state.autoDemo.step = 0;
  state.autoDemo.error = null;
  state.autoDemo.operation = "";
  publishAutoDemoObserverState();
  await refreshStatus();
  renderAutoDemoModeDialog();
  if (!$("autoDemoModeDialog").open) $("autoDemoModeDialog").showModal();
}

async function ensureAutoDemoModelRun() {
  const runKey = state.autoDemo.runKey;
  // Revisiting the result step observes the same Job; it never issues generation #2.
  if (state.autoDemo.observedJobId) {
    if (state.autoDemo.mode === "LIVE") await openQwenTraceDialog(state.jobDetail);
    return waitForAutoDemoJob(state.autoDemo.observedJobId, runKey);
  }
  const claim = selectedWorkspaceClaim();
  if (!claim) throw new Error("BM1 검토 Claim이 없습니다.");
  if (state.autoDemo.mode === "LIVE") {
    await refreshStatus();
    if (!autoDemoRunIsCurrent(runKey)) return;
    if (!qwenLiveAutoDemoReady()) throw new Error("QWEN_LIVE_AUTOPLAY_NOT_READY");
    const selected = new Set(state.selectedEvidenceIds);
    const evidenceIds = state.evidence.filter(item => selected.has(item.id) && evidenceEligibility(item)[0]).map(item => item.id);
    state.workspaceReviewMode = "LIVE_MODEL_RUN";
    state.job = null;
    state.jobDetail = null;
    const result = await api(`/api/v1/projects/${state.project.id}/reviews`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": `autoplay-live:${state.autoDemo.runKey}`},
      body: JSON.stringify({claim_id: claim.id, evidence_ids: evidenceIds, retrieval_run_id: activeRetrieval()?.run.id || null, mode: "LIVE_MODEL_RUN"})
    });
    if (!autoDemoRunIsCurrent(runKey)) return;
    state.job = {id: result.job_id};
    state.autoDemo.observedJobId = result.job_id;
    resetQwenTrace(result.job_id);
    publishAutoDemoObserverState();
    await openQwenTraceDialog();
    await waitForAutoDemoJob(result.job_id);
    return;
  }
  const retrieval = activeRetrieval();
  const reusable = reusableAutoDemoReplayJob();
  if (reusable) {
    state.job = {id: reusable.id};
    state.autoDemo.observedJobId = reusable.id;
    state.jobDetail = await api(`/api/v1/jobs/${reusable.id}`);
    renderWorkspace();
    publishAutoDemoObserverState();
    return;
  }
  if (state.status?.mode !== "DEMO") throw new Error("REPLAY_AUTOPLAY_REQUIRES_DEMO_MODE");
  const evidenceIds = state.evidence.filter(item => evidenceEligibility(item)[0]).map(item => item.id);
  const requestIdentity = [state.project.id, claim.id, state.project.version, claim.version, retrieval?.run.id || "NO_RAG", ...evidenceIds].join(":");
  let requestHash = 2166136261;
  for (let index = 0; index < requestIdentity.length; index += 1) requestHash = Math.imul(requestHash ^ requestIdentity.charCodeAt(index), 16777619);
  const key = `autoplay-replay-v1:${state.project.id}:${claim.version}:${(requestHash >>> 0).toString(16)}`;
  const result = await api(`/api/v1/projects/${state.project.id}/reviews`, {
    method: "POST",
    headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": key},
    body: JSON.stringify({claim_id: claim.id, evidence_ids: evidenceIds, retrieval_run_id: retrieval?.run.id || null, mode: "REPLAY"})
  });
  state.job = {id: result.job_id};
  state.autoDemo.observedJobId = result.job_id;
  publishAutoDemoObserverState();
  await waitForAutoDemoJob(result.job_id);
}

function scheduleAutoDemo() {
  clearTimeout(state.autoDemo.timer);
  if (!state.autoDemo.playing || !state.autoDemo.active) return;
  state.autoDemo.timer = setTimeout(() => activateAutoDemoStep(state.autoDemo.step + 1), state.autoDemo.paceMs);
}

function completeAutoDemo() {
  clearTimeout(state.autoDemo.timer);
  closeOpenDialogs();
  clearAutoDemoFocus();
  hideAutoDemoCursor();
  document.querySelectorAll(".setup-recording-dialog").forEach(dialog => dialog.classList.remove("setup-recording-dialog"));
  state.autoDemo.playing = false;
  state.autoDemo.step = autoDemoSteps.length;
  $("autoDemoCount").textContent = `${autoDemoSteps.length} / ${autoDemoSteps.length} · 완료`;
  $("autoDemoProgress").style.width = "100%";
  $("autoDemoTitle").textContent = "최소 MVP 자동 시연 완료";
  $("autoDemoChapter").textContent = state.autoDemo.walkthrough === "SETUP" ? "처음 설정부터 실행 증거까지 완료" : "기존 요약 시연 완료";
  $("autoDemoNarration").textContent = state.autoDemo.mode === "LIVE"
    ? state.jobDetail?.model_run?.validation_status === "VALID"
      ? "RunPod의 Local LLM의 새 응답이 출력 계약 검증을 통과했습니다. 실제 판단에 따른 Blackboard 기록을 저장했고 사람 승인과 공식 종결은 자동 생성하지 않았습니다."
      : "RunPod의 Local LLM 원출력과 검증 결과를 보존했습니다. 출력 계약을 통과하지 못한 결과는 검토 제안으로 승격하지 않았으며 사람 승인과 공식 종결은 자동 생성하지 않았습니다."
    : "자동 시연은 검증된 DEMO REPLAY를 사용했습니다. Local LLM 호출, 사람 승인과 공식 종결은 자동 생성하지 않았습니다.";
  $("autoDemoEvidence").textContent = state.autoDemo.mode === "LIVE"
    ? `${state.job?.id || "Job"} · ${state.job?.status || "상태 미확인"} · boot ${state.jobDetail?.model_run?.receipt?.boot_id || "—"}`
    : "문서 RAG v1과 durable checkpoint 기반 고정 조율 graph가 연결됐습니다. 다음 아키텍처 단계는 dependency 기반 부분 재검토입니다.";
  $("autoDemoPrev").disabled = false;
  $("autoDemoNext").disabled = true;
  $("autoDemoToggle").disabled = false;
  $("autoDemoToggle").textContent = "다시 재생";
  publishAutoDemoObserverState();
}

async function activateAutoDemoStep(stepIndex) {
  if (!state.autoDemo.active || state.autoDemo.busy) return;
  if (stepIndex >= autoDemoSteps.length) return completeAutoDemo();
  stepIndex = Math.max(0, stepIndex);
  clearTimeout(state.autoDemo.timer);
  clearAutoDemoFocus();
  closeOpenDialogs();
  state.autoDemo.step = stepIndex;
  state.autoDemo.busy = true;
  state.autoDemo.error = null;
  state.autoDemo.operation = "";
  renderAutoDemoPanel(stepIndex);
  const step = autoDemoSteps[stepIndex];
  const runKey = state.autoDemo.runKey;
  try {
    if (step.page === "workspace") {
      state.workspaceMode = "BM1";
      state.workspaceEvidenceTab = "current";
      state.workspaceStep = step.workspaceStep ?? 10;
      renderWorkspace();
    }
    const navigation = document.querySelector(`#nav [data-page="${step.page}"]`);
    const pageLabel = navs.find(item => item[0] === step.page)?.[1] || step.title;
    if (!await pointAutoDemoCursor(navigation, `클릭 · ${pageLabel}`, runKey, {click: true, scroll: false})) return;
    showPage(step.page, {loadData: step.page !== "audit"});
    if (!autoDemoRunIsCurrent(runKey)) return;
    if (step.page === "audit") await loadAudit();
    if (state.autoDemo.walkthrough === "SUMMARY" && stepIndex === 4) await showAutoDemoQuestion(runKey);
    if (step.action) await runSetupDemoAction(step.action, runKey);
    if (!autoDemoRunIsCurrent(runKey)) return;
    if (step.ensureModelRun) {
      const button = document.querySelector("#workspaceContent [data-run-review]");
      if (!await pointAutoDemoCursor(button, "클릭 · BM1 검토 실행", runKey, {click: true})) return;
      // Use the existing autoplay admission once; button.click() would also run
      // the manual review handler and create an unrelated second request.
      await ensureAutoDemoModelRun();
      if (!autoDemoRunIsCurrent(runKey)) return;
      const result = state.autoDemo.mode === "LIVE" ? $("qwenTraceDecision") : document.querySelector(step.focus);
      await pointAutoDemoCursor(result, "결과 확인 · 원출력과 Validator", runKey);
    }
    if (step.showBlackboard) {
      const button = document.querySelector("#workspaceContent [data-open-blackboard]");
      if (!await pointAutoDemoCursor(button, "클릭 · 이번 실행의 Blackboard", runKey, {click: true})) return;
      state.autoDemo.board = await openBlackboardDialog({jobId: state.autoDemo.observedJobId});
      if (state.autoDemo.walkthrough === "SETUP" && $("blackboardDialog").open) {
        $("blackboardDialog").close();
        $("blackboardDialog").classList.add("setup-recording-dialog");
        $("blackboardDialog").show();
      }
      await pointAutoDemoCursor($("blackboardSummary"), "이번 실행에서 저장된 제안·작업", runKey, {scroll: false});
    }
    if (!autoDemoRunIsCurrent(runKey)) return;
    await new Promise(resolve => requestAnimationFrame(resolve));
    clearAutoDemoFocus();
    const target = document.querySelector(step.focus) || document.querySelector(`.page[data-page="${step.page}"] .pagehead`);
    if (target) {
      target.classList.add("autodemo-focus");
      if (!step.showBlackboard) target.scrollIntoView({behavior: "smooth", block: "center"});
    }
  } catch (error) {
    if (!autoDemoRunIsCurrent(runKey)) return;
    state.autoDemo.playing = false;
    state.autoDemo.error = error.message;
  } finally {
    if (!autoDemoRunIsCurrent(runKey)) {
      state.autoDemo.busy = false;
      return;
    }
    if (step.ensureModelRun && state.autoDemo.mode === "LIVE" && state.jobDetail?.model_run) {
      state.autoDemo.playing = false;
    }
    state.autoDemo.busy = false;
    renderAutoDemoPanel(stepIndex);
    if ($("qwenTraceDialog").open) renderQwenTraceDialog(state.jobDetail);
    scheduleAutoDemo();
  }
}

async function startAutoDemo(mode = "REPLAY") {
  if (state.autoDemo.busy) return;
  if (!state.project) await loadAll();
  const walkthrough = $("autoDemoWalkthrough").value;
  const detailed = walkthrough === "SETUP";
  const liveReady = detailed ? state.status?.mode !== "DEMO" && state.status?.remote?.state === "READY" : qwenLiveAutoDemoReady();
  if (mode === "LIVE" && !liveReady) return message("Local LLM LIVE 자동 시연의 READY·합성 데이터 정책 조건을 확인하십시오.");
  if (mode === "REPLAY" && state.status?.mode !== "DEMO" && (detailed || !reusableAutoDemoReplayJob())) return message("REPLAY 자동 시연은 ./scripts/dev.sh up --demo에서 준비하십시오.");
  let fixturePacket = null;
  if (detailed) {
    state.autoDemo.busy = true;
    try {
      fixturePacket = await api("/api/v1/demo/setup-fixture");
      if (fixturePacket.fixture?.schema_id !== "dorilab.setup-walkthrough.v1" || fixturePacket.fixture?.basis !== "PUBLIC_SYNTHETIC") throw new Error("승인된 공개 합성 설정 fixture가 아닙니다.");
    } catch (error) {
      message(`상세 시연 준비 실패: ${error.message}`);
      return;
    } finally { state.autoDemo.busy = false; }
  }
  if ($("autoDemoModeDialog").open) $("autoDemoModeDialog").close();
  state.autoDemo.active = true;
  state.autoDemo.playing = true;
  state.autoDemo.step = 0;
  state.autoDemo.board = null;
  state.autoDemo.mode = mode;
  state.autoDemo.runKey = crypto.randomUUID();
  state.autoDemo.walkthrough = walkthrough;
  state.autoDemo.paceMs = Number($("autoDemoPace").value) || 12000;
  state.autoDemo.operation = "";
  autoDemoSteps = detailed ? setupDemoSteps : summaryAutoDemoSteps;
  if (detailed) {
    const f = fixturePacket.fixture;
    state.autoDemo.setup = {
      fixture: {project: f.project.body, profile_document: {document_code: "KASA-SE-REQ", ...f.profile_document.body}, claim: f.claim.body, requirement: f.requirement.body, document: {filename: f.document.filename, edition: f.document.form.edition}, retrieval: f.retrieval.body},
      documentText: fixturePacket.document_text,
      projectDisplayId: `DEMO-SETUP-${state.autoDemo.runKey.slice(0, 8).toUpperCase()}`,
      saved: Object.create(null), attempted: new Set(),
    };
  } else state.autoDemo.setup = null;
  state.autoDemo.observedJobId = null;
  state.autoDemo.error = null;
  state.job = null;
  state.jobDetail = null;
  resetQwenTrace();
  renderWorkspace();
  publishAutoDemoObserverState();
  await activateAutoDemoStep(0);
}

function stopAutoDemo() {
  clearTimeout(state.autoDemo.timer);
  closeOpenDialogs();
  clearAutoDemoFocus();
  hideAutoDemoCursor();
  document.querySelectorAll(".setup-recording-dialog").forEach(dialog => dialog.classList.remove("setup-recording-dialog"));
  state.autoDemo.active = false;
  state.autoDemo.playing = false;
  $("autoDemoPanel").hidden = true;
  publishAutoDemoObserverState();
}

document.addEventListener("click", event => {
  const quickAdvancedSummary = event.target.closest("[data-quick-advanced-summary]");
  if (quickAdvancedSummary) {
    event.preventDefault();
    state.quickDemo.advancedOpen = !state.quickDemo.advancedOpen;
    renderQuickDemo();
  }
  const auditSummary = event.target.closest("summary[data-audit-event-summary]");
  if (auditSummary) {
    event.preventDefault();
    const details = auditSummary.parentElement;
    const eventId = details.dataset.auditEventId;
    const openEventIds = new Set(state.auditOpenEventIds);
    details.open = !details.open;
    if (details.open) openEventIds.add(eventId);
    else openEventIds.delete(eventId);
    state.auditOpenEventIds = [...openEventIds];
  }
  const pageLink = event.target.closest("button[data-page], a[data-page]");
  if (pageLink) {
    showPage(pageLink.dataset.page);
    const parentDialog = pageLink.closest("dialog");
    if (parentDialog?.open) parentDialog.close();
  }
  if (event.target.closest('[data-action="mobileMenu"]')) {
    $("sidebar").classList.toggle("open");
    $("menuOverlay").classList.toggle("active");
  }
  const preview = event.target.closest("[data-profile-preview]");
  if (preview) {
    state.profilePreview = preview.dataset.profilePreview;
    state.profilePhase = 4;
    renderProfile();
  }
  const profilePhase = event.target.closest("[data-profile-phase]");
  if (profilePhase) {
    state.profilePhase = Number(profilePhase.dataset.profilePhase);
    renderProfile();
  }
  const apply = event.target.closest("[data-apply-profile]");
  if (apply && !apply.disabled) applySelectedProfile(apply.dataset.applyProfile);
  const documentButton = event.target.closest("[data-document-code]");
  if (documentButton) openDocumentDialog(documentButton.dataset.documentCode);
  if (event.target.closest("[data-open-tailoring]")) openTailoringDialog();
  const tailoringDecision = event.target.closest("[data-tailoring-decision]");
  if (tailoringDecision) approveTailoring(tailoringDecision.dataset.tailoringDecision, Number(tailoringDecision.dataset.version));
  const requirementButton = event.target.closest("[data-requirement-id]");
  if (requirementButton) openRequirementDialog(requirementButton.dataset.requirementId);
  const purposeButton = event.target.closest("[data-save-requirement-purpose]");
  if (purposeButton) saveRequirementPurpose(purposeButton);
  if (event.target.closest("[data-save-claim-purpose]")) saveWorkspaceClaimPurpose();
  const gateButton = event.target.closest("[data-gate-id]");
  if (gateButton) openGateDialog(gateButton.dataset.gateId);
  const gateRecordButton = event.target.closest("[data-record-gate-id]");
  if (gateRecordButton && !gateRecordButton.disabled) openGateDecisionDialog(gateRecordButton.dataset.recordGateId);
  if (event.target.closest("[data-open-transition]")) openTransitionDialog();
  const closureMatrix = event.target.closest("[data-closure-matrix]");
  if (closureMatrix) { state.closureMatrix = closureMatrix.dataset.closureMatrix; renderClosure(); }
  if (event.target.closest("[data-open-quality]")) openQualityAssessmentDialog();
  if (event.target.closest("[data-open-closure]")) openClosureDecisionDialog();
  if (event.target.closest("[data-closure-report]")) exportClosureReport();
  if (event.target.closest("[data-open-change]")) openChangeRequestDialog();
  const changeDecision = event.target.closest("[data-change-decision]");
  if (changeDecision && !changeDecision.disabled) openChangeDecisionDialog(changeDecision.dataset.changeDecision);
  if (event.target.closest("[data-stale-change-demo]")) demonstrateStaleChange();
  const workspaceMode = event.target.closest("[data-workspace-mode]");
  if (workspaceMode) { state.workspaceMode = workspaceMode.dataset.workspaceMode; renderWorkspace(); }
  const workspaceStep = event.target.closest("[data-workspace-step]");
  if (workspaceStep) { state.workspaceStep = Number(workspaceStep.dataset.workspaceStep); renderWorkspace(); }
  const evidenceTab = event.target.closest("[data-evidence-tab]");
  if (evidenceTab) { state.workspaceEvidenceTab = evidenceTab.dataset.evidenceTab; renderWorkspace(); }
  const evidenceCheck = event.target.closest(".workspaceEvidenceCheck");
  if (evidenceCheck) {
    const selected = new Set(state.selectedEvidenceIds);
    evidenceCheck.checked ? selected.add(evidenceCheck.value) : selected.delete(evidenceCheck.value);
    state.selectedEvidenceIds = [...selected];
  }
  if (event.target.closest("[data-run-review]")) runWorkspaceReview();
  if (event.target.closest("[data-run-quick-demo]")) runQuickDemo();
  if (event.target.closest("[data-quick-refresh]")) {
    refreshStatus().then(loadQuickDemo);
  }
  if (event.target.closest("[data-quick-trace]")) {
    const detail = useQuickDemoDetail();
    if (detail) openQwenTraceDialog(detail);
  }
  if (event.target.closest("[data-open-quick-workspace]")) {
    useQuickDemoDetail();
    state.workspaceMode = "BM1";
    state.workspaceStep = 10;
    renderWorkspace();
    showPage("workspace");
  }
  const quickDecision = event.target.closest("[data-quick-decision]");
  if (quickDecision && !quickDecision.disabled) {
    useQuickDemoDetail();
    openReviewDecisionDialog(quickDecision.dataset.quickDecision);
  }
  if (event.target.closest("[data-run-retrieval]")) runDocumentRetrieval();
  if (event.target.closest("[data-clear-retrieval]")) { state.retrieval = null; renderWorkspace(); }
  if (event.target.closest("[data-open-artifact]")) openArtifactDialog();
  const evidenceButton = event.target.closest("[data-evidence-id]");
  if (evidenceButton) openEvidenceDialog(evidenceButton.dataset.evidenceId);
  const ragChunkButton = event.target.closest("[data-rag-chunk-id]");
  if (ragChunkButton) openRagChunkDialog(ragChunkButton.dataset.ragChunkId);
  const reviewDecision = event.target.closest("[data-review-decision]");
  if (reviewDecision && !reviewDecision.disabled) openReviewDecisionDialog(reviewDecision.dataset.reviewDecision);
  if (event.target.closest("[data-open-qwen-trace]")) openQwenTraceDialog();
  if (event.target.closest("[data-open-blackboard]")) openBlackboardDialog();
  if (event.target.closest("[data-open-router]")) openRouterDialog();
  const openJobButton = event.target.closest("[data-open-job]");
  if (openJobButton) openStoredJob(openJobButton.dataset.openJob);
  const exportJobButton = event.target.closest("[data-export-job]");
  if (exportJobButton && !exportJobButton.disabled) exportJobReport(exportJobButton.dataset.exportJob);
  const requestAction = event.target.closest("[data-request-action]");
  if (requestAction && !requestAction.disabled) handleEvidenceRequest(requestAction);
  const closeDialogButton = event.target.closest("[data-close-dialog]");
  if (closeDialogButton) $(closeDialogButton.dataset.closeDialog).close();
  const sourceButton = event.target.closest("[data-source-chapter]");
  if (sourceButton) openSourceChapter(Number(sourceButton.dataset.sourceChapter));
  if (event.target.closest("[data-profile-gate]")) message("미리보기 회의 정의입니다. 실제 조건과 결정 권한은 채택 문서 등록 후 확정합니다.", true);
});

document.addEventListener("change", async event => {
  if (event.target.id === "autoDemoWalkthrough") renderAutoDemoModeDialog();
  if (event.target.id === "workspaceClaimSelect") {
    state.selectedClaimId = event.target.value;
    const claim = selectedWorkspaceClaim();
    const latest = state.retrievalRuns.find(item => item.claim_id === claim?.id && item.claim_version === claim?.version && item.project_version === state.project.version);
    state.retrieval = latest ? await api(`/api/v1/retrievals/${latest.id}`) : null;
    renderWorkspace();
  }
  if (event.target.id === "workspaceReviewMode") state.workspaceReviewMode = event.target.value;
});

document.addEventListener("input", event => {
  if (event.target.id === "auditSearch") {
    state.auditFilter = event.target.value;
    renderAuditTimeline();
  }
  if (event.target.id === "ragQuery") state.ragQuery = event.target.value;
});

async function startSession(showMessage = true) {
  try {
    await api("/api/v1/session", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({user_id: $("role").value})});
    await loadAll();
    if (showMessage) message(`역할을 전환했습니다. 권한은 서버 membership에서 검사합니다.`, true);
  } catch (error) { message(error.message); }
}

$("role").addEventListener("change", () => startSession());
$("runpodSettingsBtn").addEventListener("click", openRunpodSettings);
$("runpodConnectionForm").addEventListener("input", updateRunpodSshPreview);
$("runpodDialog").addEventListener("close", () => {
  clearInterval(runpodStatusTimer);
  runpodStatusTimer = null;
  refreshStatus();
});
$("runpodTrustButton").addEventListener("click", async () => {
  if (!state.runpodScanSha256) return;
  try {
    await api(`/api/v1/projects/${state.project.id}/runpod-connection/confirm-host-key`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({scan_sha256: state.runpodScanSha256})
    });
    state.runpodScanSha256 = null;
    $("runpodTrustButton").hidden = true;
    showRunpodState("호스트 키를 확인해 저장했습니다.");
    message("RunPod 호스트 키를 한 번 확인해 저장했습니다.", true);
    await applySavedRunpodConnection();
  } catch (error) { showRunpodState(error.message, "amber"); }
});

async function loadAll() {
  const [status, projects] = await Promise.all([api("/api/v1/status"), api("/api/v1/projects")]);
  state.status = status;
  const addressProjectId = new URLSearchParams(location.search).get("project_id");
  state.project = projects.find(project => project.id === (state.project?.id || addressProjectId)) || projects[0];
  if (state.project) {
    const address = new URL(location.href);
    address.searchParams.set("project_id", state.project.id);
    history.replaceState(null, "", address);
  }
  if (state.project && state.profileProjectId !== state.project.id) {
    state.profilePreview = state.project.framework;
    state.profileProjectId = state.project.id;
  }
  $("modeLabel").textContent = status.mode;
  $("remoteChip").textContent = status.remote.state;
  state.workspaceReviewMode = status.mode === "DEMO"
    ? (state.workspaceReviewMode === "LIVE_MODEL_RUN" ? "SIMULATED" : state.workspaceReviewMode)
    : "LIVE_MODEL_RUN";
  if (!state.project) return;
  [state.claims, state.requirements, state.evidence, state.jobs, state.requests, state.retrievalRuns, state.profileData, state.gateData, state.closureData, state.changeData] = await Promise.all([
    api(`/api/v1/projects/${state.project.id}/claims`),
    api(`/api/v1/projects/${state.project.id}/requirements`),
    api(`/api/v1/projects/${state.project.id}/evidence`),
    api(`/api/v1/projects/${state.project.id}/jobs`),
    api(`/api/v1/projects/${state.project.id}/evidence-requests`),
    api(`/api/v1/projects/${state.project.id}/retrievals`),
    api(`/api/v1/projects/${state.project.id}/profile`),
    api(`/api/v1/projects/${state.project.id}/gates`),
    api(`/api/v1/projects/${state.project.id}/closure`),
    api(`/api/v1/projects/${state.project.id}/changes`)
  ]);
  state.selectedClaimId = state.claims.some(item => item.id === state.selectedClaimId) ? state.selectedClaimId : state.claims[0]?.id || null;
  const selectedClaim = selectedWorkspaceClaim();
  const latestRetrieval = state.retrievalRuns.find(item => item.claim_id === selectedClaim?.id && item.claim_version === selectedClaim?.version && item.project_version === state.project.version);
  state.retrieval = latestRetrieval ? await api(`/api/v1/retrievals/${latestRetrieval.id}`) : null;
  const availableEvidence = new Set(state.evidence.map(item => item.id));
  state.selectedEvidenceIds = state.selectedEvidenceIds.filter(id => availableEvidence.has(id));
  const preferredJobId = state.jobs.some(item => item.id === state.job?.id) ? state.job.id : state.jobs[0]?.id;
  if (preferredJobId) {
    state.jobDetail = await api(`/api/v1/jobs/${preferredJobId}`);
    state.job = state.jobDetail.job;
  } else {
    state.job = null;
    state.jobDetail = null;
  }
  if (!profiles[state.profilePreview]) state.profilePreview = state.project.framework;
  renderClaims(); renderRequirements(); renderGates(); renderEvidence(); renderJobs(); renderRequests(); renderWorkspace(); renderClosure(); renderChanges(); renderOverview(); renderProfile(); renderQuickDemo(); renderShell();
  if (state.page === "development") window.dorilabDevelopment?.load();
}

async function refreshStatus() {
  try {
    const status = await api("/api/v1/status");
    const modeChanged = state.status?.mode !== status.mode;
    const remoteChanged = state.status?.remote?.state !== status.remote?.state;
    state.status = status;
    $("modeLabel").textContent = status.mode;
    $("remoteChip").textContent = status.remote.state;
    if (modeChanged) {
      state.workspaceReviewMode = status.mode === "DEMO" ? "SIMULATED" : "LIVE_MODEL_RUN";
      if (state.project) renderWorkspace();
    }
    if (state.project && (modeChanged || remoteChanged)) renderQuickDemo();
    if ($("autoDemoModeDialog").open) renderAutoDemoModeDialog();
  } catch {
    $("remoteChip").textContent = "LOCAL API UNAVAILABLE";
  }
}

function renderOverview() {
  const openRequests = state.requests.filter(item => ["OPEN", "RECEIVED"].includes(item.status)).length;
  const completedClaims = new Set(state.jobs.filter(item => item.latest_disposition === "ACCEPTED").map(item => item.claim_id)).size;
  $("projectName").textContent = state.project?.name || "DORI-01 관측위성";
  $("profileBadge").textContent = state.project?.framework || "KASA";
  $("baselineBtn").textContent = `${state.project?.baseline_display_id || "BL-003"} / ${state.project?.product_configuration || "Rev.C"}`;
  $("heroProfile").textContent = state.project?.framework || "KASA";
  $("connectedRequirements").textContent = state.claims.length;
  $("reviewGaps").textContent = openRequests;
  $("evidenceScope").textContent = `${state.evidence.length}/${state.evidence.length}`;
  $("closedClaims").textContent = `${completedClaims}/${state.claims.length}`;
  const ready = state.evidence.length > 0;
  $("primaryTask").textContent = ready ? "보완자료 등록 완료" : "열모델 입력 완전성 검토";
  $("primaryTaskDetail").textContent = ready ? "새 입력의 검토 결과와 담당자 의견을 확인하세요." : "부품별 소산전력과 열원 위치 자료를 확인하세요.";
}

function profileGateLabels(profile, phase) {
  if (phase === 0) return [profile.gates[0]];
  if (phase === 1) return [profile.gates[1]];
  if (phase === 2) return [profile.gates[2]];
  if (phase === 3) return [profile.gates[3]];
  if (phase === 4) return profile.gates.slice(4, 8);
  return [profile.gates[8]];
}

function renderProfile() {
  const selectedKey = state.profilePreview;
  const selected = profiles[selectedKey];
  const current = state.project?.framework || "KASA";
  const active = selectedKey === current;
  const savedDocuments = new Map((state.profileData.documents || []).filter(item => item.profile === selectedKey).map(item => [item.document_code, item]));
  const tailoring = (state.profileData.tailoring || []).filter(item => item.profile === selectedKey);
  const phase = state.profilePhase;
  const phaseRail = `<div class="phase-rail">${selected.phases.map((name, index) => `<button class="phase ${index === phase ? "active" : ""} ${index < 4 ? "done" : ""}" data-profile-phase="${index}"><div class="phase-code">${escapeHtml(selected.codes[index])}</div><h4>${escapeHtml(name)}</h4><small>${index === 4 ? "현재 프로젝트" : escapeHtml(phaseDetails[index][0])}</small></button>`).join("")}</div><div class="phase-detail"><div>${icon("layers")}</div><div><b>${escapeHtml(phaseDetails[phase][0])}</b><br>${escapeHtml(phaseDetails[phase][1])}<div class="phase-gates">${profileGateLabels(selected, phase).map(label => `<button class="btn small" data-profile-gate="${escapeHtml(label)}">${escapeHtml(label)}</button>`).join("")}</div></div></div>`;
  const documentRows = selected.docs.map(([code, title, revision, purpose]) => {
    const saved = savedDocuments.get(code);
    return `<tr><td><b>${escapeHtml(title)}</b><span class="subline mono">${escapeHtml(code)}</span></td><td>${escapeHtml(saved?.revision || revision)}</td><td>${escapeHtml(purpose)}<span class="subline">${escapeHtml(saved?.adoption_note || "프로젝트 예시 채택")}</span></td><td><button class="btn small" data-document-code="${escapeHtml(code)}">등록 정보</button></td></tr>`;
  }).join("");
  const tailoringBody = tailoring.length ? tailoring.map(item => `<div class="task"><div class="grow"><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.reason)}</p><small class="muted">${escapeHtml(item.profile)} / ${escapeHtml(item.owner)}</small></div><span class="pill ${item.status === "APPROVED" ? "ok" : item.status === "REJECTED" ? "bad" : "wait"}">${item.status === "APPROVED" ? "승인 기록" : item.status === "REJECTED" ? "기각 기록" : "검토 대기"}</span>${item.status === "DRAFT" ? `<button class="btn small" data-tailoring-decision="${item.id}" data-version="${item.version}">검토</button>` : ""}</div>`).join("") : '<div class="empty">등록된 테일러링 결정이 없습니다.<br>사업에 필요한 조정 사항을 새 기록으로 추가하세요.</div>';

  $("profileContent").innerHTML = `
    <div class="pagehead"><div><div class="eyebrow">SYSTEMS ENGINEERING PROFILE</div><h1>프로젝트에 적용할 개발 체계</h1><p class="subtitle">기관별 원문 용어와 단계 경계를 보존하고, 사업에서 채택한 기준과 승인 관계를 연결합니다.</p></div><div class="buttons"><button class="btn link small" data-source-chapter="1">${icon("log")}설계문서 1장</button></div></div>
    <div class="grid3">${Object.entries(profiles).map(([key, profile]) => `<button class="profilecard ${selectedKey === key ? "active" : ""}" data-profile-preview="${key}"><div class="eyebrow">${profile.region}</div><div class="profile-monogram">${profile.name}</div><h4>${profile.label}</h4><p>${key === "KASA" ? "KSER 대응, 산출물 성숙도와 사업 검토" : key === "ECSS" ? "제품 수준별 검증, 고객과 공급자, VCD" : "SE Engine, 기술검토 기준과 KDP"}</p><div class="bottom"><span class="pill ${key === current ? "ok" : ""}">${key === current ? "현재 적용" : "미리보기"}</span><span>체계 보기 →</span></div></button>`).join("")}</div><div class="space"></div>
    <div class="notice blue">${escapeHtml(selected.note)} ${active ? `프로파일 버전 ${state.project.version}.` : ""}</div><div class="space"></div>
    <section class="card"><div class="cardhead"><div><h3>${selected.name} 단계와 검토 관계</h3><p>같은 알파벳 단계의 포함 활동과 결정 권한을 함께 확인합니다.</p></div><button class="btn primary" data-apply-profile="${selectedKey}" ${active ? "disabled" : ""}>${active ? "현재 적용 중" : "이 프로파일 적용"}</button></div>${phaseRail}<div class="cardbody" style="padding-top:0"><p class="smalltext muted">${escapeHtml(selected.launch)}</p></div></section><div class="space"></div>
    <section class="card"><div class="cardhead"><div><h3>기준 문서 등록부</h3><p>판본과 역할은 제공된 설계문서의 참조 범위를 따른다. 세부 조항은 프로젝트 원문 연결 대상으로 보존한다.</p></div></div><div class="tablewrap"><table><thead><tr><th>문서</th><th>판본</th><th>적용 목적</th><th>원문 연결</th></tr></thead><tbody>${documentRows}</tbody></table></div></section>
    <div class="space"></div><div class="equal2">
      <section class="card"><div class="cardhead"><div><h3>원문 용어와 화면 표시명</h3><p>기관과 문서 판본을 함께 식별</p></div></div><div class="cardbody"><table><tbody><tr><th>예</th><th>보존할 정의</th></tr><tr><td>ECSS PRR</td><td>Preliminary Requirements Review</td></tr><tr><td>NASA PRR</td><td>Production Readiness Review</td></tr><tr><td>KASA S-IRR</td><td>사업이 채택한 원문 정의와 제품 수준</td></tr></tbody></table><div class="space"></div><button class="btn link small" data-source-chapter="4">${icon("log")}회의 정의 확인</button></div></section>
      <section class="card"><div class="cardhead"><div><h3>테일러링 결정</h3><p>조정의 사유와 담당자, 승인 범위를 등록</p></div><button class="btn small" data-open-tailoring>+ 결정 등록</button></div><div class="cardbody">${tailoringBody}</div></section>
    </div><div class="space"></div>
    <section class="card"><div class="cardhead"><div><h3>프로세스 요구조건과 제품 요구사항</h3><p>각 매트릭스가 확인하는 범위를 구분</p></div><button class="btn link small" data-source-chapter="4">${icon("log")}문서 근거</button></div><div class="cardbody"><div class="equal2"><div><h4>프로세스 매트릭스</h4><p class="smalltext muted">수행 책임, 제출 문서와 성숙도, 검토회의 이력, 채택한 KSER 등의 요구조건을 연결합니다.</p></div><div><h4>제품 검증 매트릭스</h4><p class="smalltext muted">제품 성능, 적용 조건, 검증 방법, 실제 결과와 종결 근거를 연결합니다.</p></div></div><div class="space"></div><button class="btn link" data-page="closure">검증 매트릭스 열기 →</button></div></section>`;
}

async function applySelectedProfile(framework) {
  try {
    const updated = await api(`/api/v1/projects/${state.project.id}/profile`, {
      method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({framework, framework_edition: null, expected_version: state.project.version})
    });
    state.project = updated;
    state.profilePreview = framework;
    await loadAll();
    message(`${framework} 프로파일을 적용했습니다. 기존 검토 결과는 STALE로 보존됩니다.`, true);
  } catch (error) { message(error.message); }
}

function openDocumentDialog(documentCode) {
  const definition = profiles[state.profilePreview].docs.find(item => item[0] === documentCode);
  if (!definition) return;
  const saved = (state.profileData.documents || []).find(item => item.profile === state.profilePreview && item.document_code === documentCode);
  const form = $("documentForm");
  form.elements.document_code.value = documentCode;
  form.elements.profile.value = state.profilePreview;
  form.elements.title.value = definition[1];
  form.elements.revision.value = saved?.revision || definition[2];
  form.elements.product_level.value = saved?.product_level || "열제어 장비";
  form.elements.clause_locator.value = saved?.clause_locator || "원문 연결 대기";
  form.elements.adoption_note.value = saved?.adoption_note || `${definition[3]} / 시연용 적용 기록`;
  $("documentDialog").showModal();
}

function openTailoringDialog() {
  $("tailoringForm").elements.profile.value = state.profilePreview;
  $("tailoringDialog").showModal();
}

async function approveTailoring(tailoringId, expectedVersion) {
  try {
    await api(`/api/v1/tailoring/${tailoringId}/decision`, {
      method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({disposition: "APPROVED", expected_version: expectedVersion})
    });
    state.profileData = await api(`/api/v1/projects/${state.project.id}/profile`);
    renderProfile();
    message("테일러링 승인 기록을 저장했습니다.", true);
  } catch (error) { message(error.message); }
}

function requirementStatus(status) {
  const values = {
    NEEDS_EVIDENCE: ["자료 보완", "wait"],
    EVIDENCE_REGISTERED: ["근거 등록 / 판단 전", "info"],
    PURPOSE_UNSPECIFIED: ["목적 미지정 / 판단 보류", "wait"],
    PERFORMANCE_ASSESSMENT_UNSUPPORTED: ["성능 판정 미지원 / 미평가", "wait"],
    EVIDENCE_READY: ["근거 확보", "info"],
    ANALYSIS_PENDING: ["분석 대기", "wait"],
    RESULT_REVIEW: ["결과 검토", "info"],
    CLOSED: ["종결", "ok"],
    PLANNED: ["계획 등록", ""]
  };
  return values[status] || values.PLANNED;
}

function requirementPill(status) {
  const [label, style] = requirementStatus(status);
  return `<span class="pill ${style}">${label}</span>`;
}

function assessmentScopeNotice(scope) {
  if (!scope) return '<div class="notice amber">검토 목적 미지정 · 목적을 명시하기 전에는 판단 보류</div>';
  return `<div class="notice ${scope.supported ? "blue" : "amber"}" data-assessment-scope="${escapeHtml(scope.review_purpose)}"><b>${escapeHtml(scope.label)}</b><br>${escapeHtml(scope.result_scope)}<div class="tiny">${escapeHtml(scope.no_action_required_meaning)}<br>제품 성능 요구: ${escapeHtml(scope.product_performance_status)}</div></div>`;
}

function reviewPurposeOptions(purpose) {
  return [["UNSPECIFIED", "검토 목적 미지정"], ["INPUT_READINESS", "입력 근거 준비 여부"], ["PRODUCT_PERFORMANCE", "제품 성능 요구 충족 여부 (판정 미지원)"]]
    .map(([value, label]) => `<option value="${value}" ${purpose === value ? "selected" : ""}>${label}</option>`).join("");
}

function requirementLevel(level) {
  return {MISSION: "임무", SYSTEM: "시스템", SUBSYSTEM: "하위 시스템", EQUIPMENT: "장비"}[level] || level;
}

function requirementByDisplay(displayId) {
  return state.requirements.find(item => item.display_id === displayId);
}

function renderRequirements() {
  const root = $("requirementsContent");
  if (!root || !state.project) return;
  const baseline = state.project.baseline_display_id || "BL-003";
  const run = state.project.test_run || "TVAC-03";
  const vRows = [
    ["임무 목적과 운용개념", "ConOps-01", "MIS-001", "임무 운용 적합성", "Validation"],
    ["시스템 요구사항", "SYS-THERM", "THM-041", "시스템 통합 결과", "Verification"],
    ["하위 시스템과 인터페이스", "ICD-TH-008", "THM-042", "하위 시스템 검증", "Verification"],
    ["장비 요구와 상세 설계", "THM-041 / THM-042", "THM-041", "장비 검사, 분석과 시험", run]
  ];
  const vModel = vRows.map((row, index) => {
    const requirement = requirementByDisplay(row[2]);
    const target = requirement ? `data-requirement-id="${requirement.id}"` : "disabled";
    return `<button class="vnode" ${target} style="margin-left:${index * 11}px"><b>${escapeHtml(row[0])}</b><small>${escapeHtml(row[1])}</small></button><div class="vlink"></div><button class="vnode" ${target} style="margin-right:${index * 11}px"><b>${escapeHtml(row[3])}</b><small>${escapeHtml(row[4])}</small></button>`;
  }).join("");
  const rows = state.requirements.map(item => `<tr class="clickrow" data-requirement-id="${item.id}"><td class="nowrap"><b>${escapeHtml(item.display_id)}</b><span class="subline">${escapeHtml(requirementLevel(item.level))}</span></td><td>${escapeHtml(item.statement)}<span class="subline">${escapeHtml(item.owner)}</span></td><td><code>${escapeHtml(item.parent_ref)}</code></td><td>${escapeHtml(item.verification_method)}</td><td>${requirementPill(item.ui_status)}</td></tr>`).join("");
  root.innerHTML = `
    <div class="pagehead"><div><div class="eyebrow">REQUIREMENTS &amp; V MODEL</div><h1>요구사항과 검증 경로</h1><p class="subtitle">임무의 목적을 제품 요구로 전개하고, 같은 수준의 실제 근거를 상위 판단에 연결합니다.</p></div><div class="buttons"><button class="btn link small" data-source-chapter="3">${icon("log")}설계문서 3장</button></div></div>
    <div class="grid2">
      <section class="card"><div class="cardhead"><div><h3>요구사항 전개와 제품 실현</h3><p>요소를 클릭하면 관련 문서와 검증 범위를 확인할 수 있습니다.</p></div><span class="pill info">양방향 추적</span></div><div class="cardbody"><div class="vgrid">${vModel}<div class="diagramcap">설계, 제작과 소프트웨어 구현</div></div></div></section>
      <section class="card"><div class="cardhead"><div><h3>현재 추적 경로</h3><p>열모델 검토의 적용 범위</p></div></div><div class="cardbody"><div class="chain"><div class="chain-node"><b>ConOps-01 → MIS-001</b><small>운용 환경과 이해관계자 목적</small></div><div class="chain-node"><b>SYS-THERM → THM-041 / 042</b><small>입력 완전성과 온도 상관 검토</small></div><div class="chain-node"><b>ICD-TH-008 / ${escapeHtml(baseline)}</b><small>열원 위치와 온도 채널 대응</small></div><div class="chain-node"><b>${escapeHtml(run)} → TRB</b><small>관측, 분석 결과와 검토 기록</small></div></div><div class="space"></div><div class="notice">THM-041은 입력 근거 준비 여부 검토다. THM-042는 별도 제품 성능 요구이며 현재 판정 미지원이다. 입력준비 검토를 성능 충족이나 제품 인수 승인으로 전용하지 않는다.</div></div></section>
    </div><div class="space"></div>
    <section class="card"><div class="cardhead"><div><h3>제품 요구사항 매트릭스</h3><p>모든 요구사항과 수치는 제품 흐름을 위한 예시 데이터입니다.</p></div></div><div class="tablewrap"><table><thead><tr><th>식별자 / 수준</th><th>요구사항</th><th>상위 연결</th><th>방법</th><th>상태</th></tr></thead><tbody>${rows}</tbody></table></div></section>
    <div class="space"></div><div class="equal2">
      <section class="card"><div class="cardhead"><div><h3>Verification</h3><p>명세된 요구사항과 설계 정의의 충족 확인</p></div></div><div class="cardbody"><p class="smalltext muted">제품 수준과 검증 방법, 적용 조건을 고정하고 검사, 분석과 시험 결과를 수용한다.</p></div></section>
      <section class="card"><div class="cardhead"><div><h3>Validation</h3><p>의도한 환경과 운용에서의 목적 충족 확인</p></div></div><div class="cardbody"><p class="smalltext muted">운용 시나리오와 이해관계자 기대에 연결한다. ECSS 납품 문서는 프로젝트가 채택한 요구사항과 검증 구조로 출력한다.</p></div></section>
    </div>`;
}

async function openRequirementDialog(requirementId) {
  try {
    const item = await api(`/api/v1/requirements/${requirementId}`);
    const baseline = state.project.baseline_display_id || "BL-003";
    const run = state.project.test_run || "TVAC-03";
    const configuration = state.project.product_configuration || "Rev.C";
    const isThermal = item.display_id.startsWith("THM");
    $("requirementDialogTitle").textContent = `${item.display_id} / 요구사항 추적`;
    $("requirementDialogBody").innerHTML = `<div class="buttons"><span class="pill info">프로젝트 예시 요구</span>${requirementPill(item.ui_status)}</div><div class="space"></div><h3>${escapeHtml(item.statement)}</h3><dl class="kv"><dt>상위 요구</dt><dd>${escapeHtml(item.parent_ref)}</dd><dt>검증 방법</dt><dd>${escapeHtml(item.verification_method)}</dd><dt>담당</dt><dd>${escapeHtml(item.owner)}</dd><dt>Claim</dt><dd>${escapeHtml(item.display_claim)}</dd><dt>기준점</dt><dd>${escapeHtml(baseline)}</dd></dl><div class="space"></div>${isThermal ? `<div class="relation-list"><div class="relation-row">${icon("log")}<span>ICD-TH-008 / 열원과 센서 위치</span><span class="pill">인터페이스</span></div><div class="relation-row">${icon("flask")}<span>${escapeHtml(run)} / ${escapeHtml(configuration)}</span><span class="pill">시험 실행</span></div><div class="relation-row">${icon("gate")}<span>TRB → 제품 인수 검토</span><span class="pill">결과와 인수</span></div></div><div class="space"></div>${item.display_id === "THM-042" ? '<div class="notice amber">RMS + 보수 여유 ≤ 3.0 K는 이 목업의 가상 프로젝트 기준이다. 적용 표준의 수치로 사용할 때는 원문과 채택 기록을 연결한다.</div>' : ""}` : '<div class="notice blue">이 항목은 상하위 추적 관계를 보여주는 계획 데이터입니다. 실제 검증 근거는 별도 작업으로 연결합니다.</div>'}<div class="space"></div><button class="btn link small" data-source-chapter="${item.source_chapter}">${icon("log")}관련 설계문서</button>`;
    $("requirementDialogBody").insertAdjacentHTML("afterbegin", assessmentScopeNotice(item.assessment_scope) + '<div class="space"></div>');
    $("requirementDialogBody").insertAdjacentHTML("beforeend", `<div class="space"></div><div class="field"><label>요구사항 검토 목적을 명시적으로 선언</label><select id="requirementPurpose">${reviewPurposeOptions(item.review_purpose || "UNSPECIFIED")}</select></div><p class="tiny muted">변경 시 연결 Claim의 새 revision을 만들고 기존 검토를 STALE로 처리합니다. 과거 기록은 보존합니다.</p><button class="btn" data-save-requirement-purpose="${item.id}" data-version="${item.version}">목적 저장</button>`);
    $("requirementDialog").showModal();
  } catch (error) {
    message(error.message);
  }
}

function gateStateDisplay(value) {
  return {
    UNRESOLVED: ["자료 대기", "wait"],
    READY: ["검토 가능", "info"],
    REVIEW_COMPLETE: ["검토 완료", "ok"],
    REJECTED: ["재검토", "bad"]
  }[value] || [value || "확인 대기", "wait"];
}

function gateStatePill(value) {
  const [label, style] = gateStateDisplay(value);
  return `<span class="pill ${style}">${escapeHtml(label)}</span>`;
}

function gateByKey(key) {
  return (state.gateData.gates || []).find(item => item.gate_key === key);
}

function gateChecklist(items, showBasis = false) {
  return `<div class="checklist">${items.map(item => `<div class="checkline ${item.satisfied ? "" : "missing"}">${icon("circle")}<span>${escapeHtml(item.label)}${showBasis ? `<small class="muted" style="display:block">${escapeHtml(item.basis)}</small>` : ""}</span></div>`).join("")}</div>`;
}

function phaseLabel(profile, phase) {
  const index = Math.max(0, Math.min(Number(phase) || 0, profile.phases.length - 1));
  return `${profile.codes[index]} / ${profile.phases[index]}`;
}

function renderGates() {
  const root = $("gatesContent");
  if (!root || !state.project) return;
  const gates = state.gateData.gates || [];
  const profile = profiles[state.project.framework] || profiles.KASA;
  const project = state.gateData.project || state.project;
  const currentPhase = project.current_phase ?? 4;
  const accept = gateByKey("accept");
  const orr = gateByKey("orr");
  const cards = gates.map((gate, index) => {
    const progress = gate.criteria_count ? Math.round(gate.ready_count / gate.criteria_count * 100) : 0;
    return `<section class="card gatecard"><div class="buttons" style="justify-content:space-between"><span class="eyebrow">REVIEW ${String(index + 1).padStart(2, "0")}</span>${gateStatePill(gate.state)}</div><h2>${escapeHtml(gate.display_name)}</h2><p>${escapeHtml(gate.description || gateDescriptions[gate.gate_key])}</p><div class="smalltext muted">${gate.ready_count} / ${gate.criteria_count} 준비 항목</div><div class="progress"><div style="width:${progress}%"></div></div><div class="bottom"><span class="tiny muted">${escapeHtml(project.baseline_display_id || "기준점 미등록")}</span><button class="btn small" data-gate-id="${gate.id}">자료와 조건 확인</button></div></section>`;
  }).join("");
  const transitionCount = (state.gateData.transitions || []).length;
  root.innerHTML = `
    <div class="pagehead"><div><div class="eyebrow">REVIEWS &amp; DECISIONS</div><h1>기술검토회의와 단계 전환</h1><p class="subtitle">검토자료의 성숙도, 성공조건과 다음 활동의 승인 범위를 각각 관리합니다.</p></div><div class="buttons"><button class="btn link small" data-source-chapter="4">${icon("log")}설계문서 4장</button></div></div>
    <div class="notice blue">적용 프로파일 ${escapeHtml(state.project.framework)}. 아래 체크리스트는 설계문서에 따른 프로젝트 시연 항목이다. 회의별 상세 기준은 사업의 채택 문서에 연결한다.</div><div class="space"></div>
    <div class="gatelist">${cards}</div><div class="space"></div>
    <section class="card"><div class="cardhead"><div><h3>${state.project.framework === "NASA" ? "KDP / 사업 단계 전환" : "사업 단계 진입 결정"}</h3><p>기술검토 결과와 별도의 의사결정 기록</p></div>${transitionCount ? `<span class="pill info">결정 ${transitionCount}건</span>` : ""}</div><div class="cardbody"><div class="equal2"><div><p class="smalltext">현재 단계: <b>${escapeHtml(phaseLabel(profile, currentPhase))}</b></p><p class="smalltext muted">다음 단계의 포함 활동과 권한자의 승인 조건을 확인한다. 열모델 두 Claim의 종결 결과는 인계 자료에 포함한다.</p></div><div>${gateChecklist([{label: "제품 인수 검토 승인", satisfied: accept?.state === "REVIEW_COMPLETE"}, {label: "운용 준비의 잔여 조건 확인", satisfied: orr?.state === "REVIEW_COMPLETE"}])}<div class="space"></div><button class="btn dark" data-open-transition>단계 진입 검토</button></div></div></div></section>`;
}

async function refreshGateData() {
  [state.gateData, state.closureData] = await Promise.all([
    api(`/api/v1/projects/${state.project.id}/gates`),
    api(`/api/v1/projects/${state.project.id}/closure`)
  ]);
  state.project = state.gateData.project;
  renderGates();
  renderClosure();
  renderOverview();
  renderShell();
}

async function openGateDialog(gateId) {
  try {
    const gate = await api(`/api/v1/gates/${gateId}`);
    const project = state.gateData.project || state.project;
    const criteria = [...gate.evaluated_entry_criteria, ...gate.evaluated_success_criteria];
    const scope = gate.gate_key === "trb" ? `THM-041, THM-042와 ${project.test_run}` : "프로젝트가 채택한 회의 범위";
    const authority = gate.authority === "APPROVER" ? "승인권자" : "검토 책임자 또는 승인권자";
    const decision = gate.latest_decision;
    $("gateDialogTitle").textContent = `${gate.display_name} / 기술검토회의`;
    $("gateDialogBody").innerHTML = `<div class="buttons"><span class="pill info">${escapeHtml(gate.framework)}</span>${gateStatePill(gate.state)}<span class="pill">시연용 조건</span></div><div class="space"></div><p>${escapeHtml(gate.description)}</p><dl class="kv"><dt>대상 수준</dt><dd>${escapeHtml(gate.product_level)} / ${escapeHtml(project.product_configuration)}</dd><dt>검토 범위</dt><dd>${escapeHtml(scope)}</dd><dt>판단 권한</dt><dd>${escapeHtml(authority)}</dd><dt>근거 구조</dt><dd>진입조건, 성공조건, 문서 성숙도와 조치 이력</dd></dl><div class="separator"></div><h4>준비와 성공조건</h4><div class="space" style="height:11px"></div>${gateChecklist(criteria, true)}<div class="space"></div>${decision ? `<div class="notice">현재 프로젝트 version ${decision.source_project_version}의 ${escapeHtml(decision.disposition)} 기록 · ${escapeHtml(decision.actor)}<br><span class="tiny">${escapeHtml(decision.note)}</span></div><div class="space"></div>` : ""}${!gate.ready_for_decision ? '<div class="notice amber">미충족 조건을 보완한 뒤 승인 결과를 기록할 수 있습니다. 기각 기록은 API 감사 경계에서 별도로 보존됩니다.</div><div class="space"></div>' : ""}<button class="btn link small" data-source-chapter="${gate.source_chapter}">${icon("log")}회의와 단계 전환의 정의</button>`;
    const button = $("recordGateButton");
    button.dataset.recordGateId = gate.id;
    button.disabled = !gate.ready_for_decision || gate.state === "REVIEW_COMPLETE";
    $("gateDialog").showModal();
  } catch (error) { message(error.message); }
}

async function openGateDecisionDialog(gateId) {
  const role = $("role").value.split("@")[0];
  if (!new Set(["reviewer", "approver"]).has(role)) {
    message("검토 결과 기록은 검토 책임자 또는 승인권자 역할에서 수행할 수 있습니다.");
    return;
  }
  try {
    const gate = await api(`/api/v1/gates/${gateId}`);
    const form = $("gateDecisionForm");
    form.elements.gate_id.value = gate.id;
    form.elements.expected_gate_version.value = gate.version;
    form.elements.expected_project_version.value = (state.gateData.project || state.project).version;
    $("gateDecisionActor").value = $("role").selectedOptions[0].textContent;
    $("gateDecisionDialogTitle").textContent = `${gate.display_name} / 기술검토 결과 기록`;
    if ($("gateDialog").open) $("gateDialog").close();
    $("gateDecisionDialog").showModal();
  } catch (error) { message(error.message); }
}

function openTransitionDialog() {
  const project = state.gateData.project || state.project;
  const profile = profiles[project.framework] || profiles.KASA;
  const current = project.current_phase ?? 4;
  const next = Math.min(current + 1, 6);
  const accept = gateByKey("accept");
  const orr = gateByKey("orr");
  $("transitionDialogTitle").textContent = project.framework === "NASA" ? "KDP 단계 진입 결정" : "사업 단계 진입 검토";
  $("transitionNotice").textContent = `현재 ${profile.codes[current]} → 다음 ${profile.codes[next]}. 검토회의와 단계 전환의 결정을 각각 저장한다.`;
  $("transitionChecklist").innerHTML = gateChecklist([{label: "제품 인수 검토", satisfied: accept?.state === "REVIEW_COMPLETE"}, {label: "운용 준비검토의 잔여 조건", satisfied: orr?.state === "REVIEW_COMPLETE"}]);
  $("transitionActor").value = $("role").selectedOptions[0].textContent;
  $("transitionForm").elements.expected_project_version.value = project.version;
  $("transitionDialog").showModal();
}

function workspaceCard(title, description, body, action = "") {
  return `<section class="card"><div class="cardhead"><div><h3>${title}</h3>${description ? `<p>${description}</p>` : ""}</div>${action}</div><div class="cardbody">${body}</div></section>`;
}

function selectedWorkspaceClaim() {
  return state.claims.find(item => item.id === state.selectedClaimId) || state.claims[0] || null;
}

function workspaceScope() {
  const claim = selectedWorkspaceClaim();
  return claim?.scope || {unit: state.project?.display_id, configuration: state.project?.product_configuration, run: state.project?.test_run};
}

function evidenceEligibility(item) {
  const citation = item.source_verification;
  if (citation?.enforced && (citation.status !== "VALID" || citation.freshness !== "CURRENT")) return [false, `원문 대조 대기/실패 · ${citation.reason_code}`];
  if (item.kind === "REFERENCE") {
    if (!["PUBLIC", "GRANTED"].includes(item.rights_status)) return [false, "권리 확인 필요"];
    if (!item.edition) return [false, "판본 확인 필요"];
    if (!item.adopted) return [false, "프로젝트 채택 필요"];
    if (item.applicability_status !== "APPLICABLE") return [false, "적용성 확인 필요"];
    return [true, "권리·채택·적용성 등록 확인"];
  }
  const scope = workspaceScope();
  const mismatch = ["unit", "configuration", "run"].filter(key => !scope[key] || item.scope?.[key] !== scope[key]);
  return mismatch.length ? [false, `${mismatch.join("/")} 범위 불일치`] : [true, "현재 범위"];
}

function citationNotice(item) {
  const check = item.source_verification || {status: "UNRESOLVED", reason_code: "LEGACY_NOT_VERIFIED", freshness: "CURRENT"};
  const matched = check.status === "VALID" && check.freshness === "CURRENT";
  const title = check.freshness === "STALE" ? "원문 변경 · 이전 대조는 STALE" : matched ? "원문 텍스트·위치 일치" : "원문 대조 미완료";
  const reasons = {CITATION_MATCHED: "선택한 문서·판본·청크·위치와 전체 인용문 일치", SOURCE_CHANGED: "원문·판본 또는 파싱 기록 변경: 새 자료 등록과 재검토 필요", CITATION_DOCUMENT_MISMATCH: "청크가 선택한 문서에 속하지 않거나 확인할 수 없음", CITATION_LOCATION_MISMATCH: "제출 페이지·줄 범위 또는 위치 표기가 원문 청크와 불일치", CITATION_QUOTE_MISMATCH: "인용문이 전체 원문 청크와 불일치 (부분·유사 인용 포함)", CITATION_EDITION_MISMATCH: "인용 판본과 문서 판본 불일치", CITATION_EDITION_REQUIRED: "인용 판본 확인 필요", CITATION_POSITION_REQUIRED: "원문 청크와 페이지·줄 범위 선택 필요", CITATION_LOCATION_AMBIGUOUS: "같은 문구의 위치를 특정할 수 없어 확인 대기", SOURCE_NOT_PARSED: "원문 파싱 완료 필요", SOURCE_PARSE_FAILED: "파싱 실패: 텍스트 원문 확인 대기", SOURCE_UNAVAILABLE: "보존된 원문 파일을 읽을 수 없음", SOURCE_FORMAT_UNSUPPORTED: "이번 대조는 PDF 텍스트층만 지원", LEGACY_NOT_VERIFIED: "이전 등록 자료: 원문과 자동 대조하지 않음"};
  return `<div class="notice ${matched ? "blue" : "amber"}"><b>${escapeHtml(title)}</b> · ${escapeHtml(check.status)} / ${escapeHtml(check.freshness)}<br>${escapeHtml(reasons[check.reason_code] || "원문 확인 대기")}<br><code>${escapeHtml(check.reason_code || "LEGACY_NOT_VERIFIED")}</code><br><span class="tiny">원문 일치가 확인되어도 Claim의 의미적 지지·적용성·제품 적합성은 별도 검토이며 자동 승인되지 않습니다.${!check.enforced ? " 이전 등록/미지원 형식은 자동 검증되지 않았고 기존 범위 검사를 유지합니다." : ""}</span></div><details><summary>원문 대조 receipt</summary><pre>${escapeHtml(JSON.stringify(check, null, 2))}</pre></details>`;
}

function workspaceStepState(index) {
  const detail = state.jobDetail;
  const currentEvidence = state.evidence.some(item => item.kind === "OBSERVATION" && evidenceEligibility(item)[0]);
  const valid = detail?.model_run?.validation_status === "VALID" && detail.job.freshness === "CURRENT";
  const accepted = detail?.decisions?.at(-1)?.disposition === "ACCEPTED" && detail.job.freshness === "CURRENT";
  if (index === 0) return state.claims.length ? "입력 등록" : "입력 대기";
  if (index === 1) return (state.profileData.documents || []).some(item => item.status === "ADOPTED") ? "채택 기록" : "채택 확인";
  if (index >= 2 && index <= 5) return "계획 대기";
  if (index === 6) return gateStateDisplay(gateByKey("sir")?.state)[0];
  if (index === 7) return gateStateDisplay(gateByKey("trr")?.state)[0];
  if (index === 8 || index === 9) return currentEvidence ? "자료 접수" : "자료 대기";
  if (index === 10) return accepted ? "완료" : valid ? "검토 대기" : "분석 대기";
  if (index === 11) return detail?.model_run ? "작성 가능" : "근거 대기";
  if (index === 12) return gateStateDisplay(gateByKey("trb")?.state)[0];
  return "검토 대기";
}

function workspaceEvidenceList(tab) {
  if (tab === "unresolved") return renderRequestCards();
  let items;
  if (tab === "current") items = state.evidence.filter(item => item.kind === "OBSERVATION" && evidenceEligibility(item)[0]);
  else if (tab === "reference") items = state.evidence.filter(item => item.kind === "REFERENCE");
  else items = state.evidence.filter(item => !evidenceEligibility(item)[0]);
  if (!items.length) return '<div class="empty">이 범위에 등록된 기록이 없습니다.</div>';
  return items.map(item => {
    const [included, reason] = evidenceEligibility(item);
    const checked = state.selectedEvidenceIds.includes(item.id);
    const scopeText = item.kind === "REFERENCE" ? `${item.rights_status || "UNCONFIRMED"} / ${item.edition || "판본 미확인"}` : `${item.scope?.unit || "—"} / ${item.scope?.configuration || "—"} / ${item.scope?.run || "—"}`;
    return `<article class="evitem ${included ? "" : "excluded"}"><div class="evitem-head"><label class="checkline"><input class="workspaceEvidenceCheck" type="checkbox" value="${item.id}" ${checked ? "checked" : ""}><span><b>${escapeHtml(item.display_id)}</b><br>${escapeHtml(item.filename)}</span></label><span class="pill ${included ? "ok" : "wait"}">${escapeHtml(reason)}</span></div><p>${escapeHtml(item.quote || "확인된 발췌 없음")}</p><div class="meta"><span>${escapeHtml(scopeText)}</span><span>${escapeHtml(item.basis)}</span><span>SHA256 ${escapeHtml(item.artifact_sha256.slice(0, 12))}</span><span>원문 대조 ${escapeHtml(item.source_verification?.status || "UNRESOLVED")} / ${escapeHtml(item.source_verification?.freshness || "CURRENT")}</span></div><div class="space" style="height:7px"></div><button class="btn link small" data-evidence-id="${item.id}">근거 상세</button></article>`;
  }).join("");
}

function activeRetrieval() {
  const claim = selectedWorkspaceClaim();
  const run = state.retrieval?.run;
  if (!claim || !run) return null;
  if (run.project_id !== state.project.id || run.claim_id !== claim.id) return null;
  if (run.project_version !== state.project.version || run.claim_version !== claim.version) return null;
  return state.retrieval;
}

function renderRagRetrieval() {
  const retrieval = activeRetrieval();
  const run = retrieval?.run;
  const results = retrieval?.results || [];
  const resultRows = results.length ? results.map(item => {
    const selected = item.selected;
    const preview = selected && item.chunk_text
      ? `<p>${escapeHtml(item.chunk_text.length > 360 ? `${item.chunk_text.slice(0, 360)}…` : item.chunk_text)}</p>`
      : "";
    return `<article class="evitem ${selected ? "" : "excluded"}"><div class="evitem-head"><div><b>#${item.candidate_rank} ${escapeHtml(item.filename)}</b><br><span class="tiny muted">${escapeHtml(item.locator)}</span></div><span class="pill ${selected ? "ok" : "wait"}">${escapeHtml(item.reason)}</span></div>${preview}<div class="meta"><span>score ${Number(item.score).toFixed(4)}</span><span>chunk ${escapeHtml(item.text_sha256.slice(0, 12))}</span></div>${selected ? `<div class="space" style="height:7px"></div><button class="btn link small" data-rag-chunk-id="${item.chunk_id}">청크와 원문 위치</button>` : ""}</article>`;
  }).join("") : '<div class="empty">검색어와 일치하면서 Scope Gate를 통과한 문서 청크가 없습니다.</div>';
  const summary = run
    ? `<div class="notice blue">선택 ${run.selected_count} / 후보 ${run.candidate_count} · parser ${escapeHtml(run.parser_version)} · index ${escapeHtml(run.index_version)}<br><span class="tiny">retrieval receipt ${escapeHtml(run.receipt_sha256)}</span></div><div class="space" style="height:10px"></div>${resultRows}`
    : '<div class="empty">업로드·파싱된 운영 문서를 현재 Claim 질문으로 검색합니다. 검색 결과는 자동 수용되지 않으며 receipt와 함께 다음 ContextSnapshot에 고정됩니다.</div>';
  return `<div class="formgrid"><div class="field full"><label>문서 검색어</label><input id="ragQuery" value="${escapeHtml(state.ragQuery)}" placeholder="예: 소산전력 열원 위치"></div><div class="field"><label>최대 선택 청크</label><select id="ragTopK"><option value="3">3</option><option value="4" selected>4</option><option value="6">6</option></select></div><div class="field"><label>검색 경계</label><input value="Project + Rights + Edition + Adoption + Applicability" readonly></div></div><div class="space" style="height:10px"></div><div class="buttons"><button class="btn primary" data-run-retrieval>문서 검색</button>${run ? '<button class="btn" data-clear-retrieval>이번 Snapshot에서 제외</button>' : ""}</div><div class="space"></div>${summary}`;
}

function jobTraceProgress() {
  const detail = state.jobDetail;
  if (!detail) return 0;
  if (detail.orchestration?.nodes?.length) {
    return detail.orchestration.nodes.filter(node => ["COMPLETED", "PROJECTED_COMPLETED"].includes(node.status)).length;
  }
  if (detail.job.status === "QUEUED") return 2;
  if (["DISPATCHING", "RUNNING"].includes(detail.job.status)) return 3;
  if (["OUTPUT_RECEIVED", "VALIDATING"].includes(detail.job.status)) return 4;
  if (detail.model_run) return 5;
  return 1;
}

function renderWorkspaceTrace() {
  const orchestration = state.jobDetail?.orchestration;
  if (orchestration?.nodes?.length) {
    const completed = orchestration.nodes.filter(node => ["COMPLETED", "PROJECTED_COMPLETED"].includes(node.status)).length;
    const statusClass = status => {
      if (["COMPLETED", "PROJECTED_COMPLETED"].includes(status)) return "done";
      if (["RUNNING", "READY"].includes(status)) return "running";
      if (status === "WAITING") return "waiting";
      if (["FAILED", "UNKNOWN_OUTCOME", "STALE"].includes(status)) return "fail";
      return "";
    };
    const run = orchestration.run;
    const stateText = `${run.status} / ${run.current_node} · checkpoint ${orchestration.integrity.checkpoint_count} · ${run.origin}`;
    return `<div class="trace graph-trace">${orchestration.nodes.map((node, index) => `<div class="trace-step ${statusClass(node.status)}" title="${escapeHtml(node.description)}"><b>${index + 1}. ${escapeHtml(node.label)}</b><span>${escapeHtml(node.key)}</span><small>${escapeHtml(node.status)}</small></div>`).join("")}</div><div class="progress"><div style="width:${completed / orchestration.nodes.length * 100}%"></div></div><p class="tiny muted" style="margin-top:9px">${escapeHtml(stateText)} · SHA256 ${escapeHtml(orchestration.integrity.latest_sha256?.slice(0, 12) || "없음")}</p>`;
  }
  const progress = jobTraceProgress();
  const labels = [["Scope Gate", "범위와 자료 권리"], ["RAG + Context", "직접 근거·검색 receipt"], ["Model / Tool", "지정된 실행 모드"], ["Validator", "구조와 참조"], ["Human Review", "검토 후보 등록"]];
  const stateText = state.jobDetail ? `${state.jobDetail.job.status} / ${state.jobDetail.job.freshness}` : "실행 준비";
  return `<div class="trace">${labels.map((item, index) => `<div class="trace-step ${progress > index ? "done" : progress === index && progress < 5 ? "running" : ""}"><b>${index + 1}. ${item[0]}</b>${item[1]}</div>`).join("")}</div><div class="progress"><div style="width:${progress / 5 * 100}%"></div></div><p class="tiny muted" style="margin-top:9px">${escapeHtml(stateText)}</p>`;
}

function renderWorkspaceResult() {
  const detail = state.jobDetail;
  if (!detail) return `<div class="empty">${icon("flask")}<br>검토를 실행하면 입력 상태에 맞는<br>구조화된 결과가 표시됩니다.</div>`;
  const job = detail.job;
  if (!detail.model_run) return `<div class="resultpanel wait"><div class="tiny muted">${escapeHtml(job.id)}</div><div class="resultcode">${escapeHtml(job.status)}</div><p class="smalltext">worker가 명시된 실행 모드로 처리 중입니다.</p></div>`;
  const model = detail.model_run;
  const parsed = model.parsed_output || {};
  const action = parsed.actions?.[0] || parsed;
  const valid = model.validation_status === "VALID";
  const current = job.freshness === "CURRENT";
  const decision = detail.decisions?.at(-1);
  const refs = (action.evidence_refs || []).map(ref => {
    const evidence = state.evidence.find(item => item.id === ref);
    const chunk = state.retrieval?.results?.find(item => item.chunk_id === ref && item.selected);
    if (evidence) return `<button class="refbutton" data-evidence-id="${evidence.id}">${escapeHtml(evidence.display_id)}</button>`;
    if (chunk) return `<button class="refbutton" data-rag-chunk-id="${chunk.chunk_id}">RAG #${chunk.candidate_rank}</button>`;
    return `<code>${escapeHtml(ref)}</code>`;
  }).join(" ") || "제공 근거 없음";
  const requested = action.requested_items || action.requested_evidence || [];
  const canDecide = current && valid && detail.assessment_scope?.supported && job.status === "AWAITING_REVIEW";
  return `${assessmentScopeNotice(detail.assessment_scope)}<div class="space"></div>${!current ? '<div class="notice amber">입력이나 프로젝트 version이 변경됐습니다. 새 Snapshot으로 다시 검토하세요.</div><div class="space"></div>' : ""}<div class="resultpanel ${!valid ? "bad" : action.action === "REQUEST_EVIDENCE" ? "wait" : ""}"><div class="tiny muted">${escapeHtml(job.id)} / ${escapeHtml(detail.snapshot.id)}</div><div class="resultcode">${escapeHtml(action.action || job.status)}</div><dl class="kv"><dt>Reason</dt><dd>${escapeHtml(action.reason || action.reason_code || "해당 없음")}</dd><dt>Claim</dt><dd>${escapeHtml(selectedWorkspaceClaim()?.display_id || job.claim_id)}</dd><dt>근거</dt><dd>${refs}</dd><dt>요청 자료</dt><dd>${escapeHtml(requested.join(", ") || "추가 요청 없음")}</dd></dl></div><div class="space" style="height:12px"></div><div class="buttons"><span class="pill ${valid ? "ok" : "bad"}">${valid ? "OUTPUT_VALIDATED" : "OUTPUT_REJECTED"}</span><span class="pill ${decision ? (decision.disposition === "ACCEPTED" ? "ok" : "wait") : "wait"}">${escapeHtml(decision?.disposition || "검토 의견 대기")}</span></div>${model.errors?.length ? `<p class="tiny" style="color:var(--red);margin-top:9px">${escapeHtml(model.errors.join(" / "))}</p>` : ""}<div class="review-actions"><button class="btn primary" data-review-decision="ACCEPTED" ${canDecide ? "" : "disabled"}>초안 수용</button><button class="btn" data-review-decision="REVISION_REQUESTED" ${canDecide ? "" : "disabled"}>수정 의견</button>${job.mode === "LIVE_MODEL_RUN" ? '<button class="btn" data-open-qwen-trace>Local LLM 입출력 보기</button>' : ""}<button class="btn" data-evidence-tab="unresolved" ${state.requests.length ? "" : "disabled"}>근거 요청 확인</button><button class="btn" disabled>상위 검토 요청</button></div><details><summary>모델 응답 JSON과 실행 증빙</summary><pre>${escapeHtml(JSON.stringify({parsed_output: parsed, validation: model.validation_status, raw_sha256: model.raw_sha256, receipt: model.receipt}, null, 2))}</pre></details>`;
}

function renderBM1Workspace() {
  const claim = selectedWorkspaceClaim();
  if (!claim) return '<div class="notice amber">BM1 검토에 사용할 Claim을 먼저 등록하십시오.</div>';
  const scope = workspaceScope();
  const requirement = state.requirements.find(item => item.claim_id === claim.id || item.display_claim === claim.display_id);
  const decision = state.jobDetail?.decisions?.at(-1);
  const currentEvidence = state.evidence.filter(item => evidenceEligibility(item)[0]);
  const inputReady = currentEvidence.length > 0;
  const accepted = decision?.disposition === "ACCEPTED" && state.jobDetail?.job.freshness === "CURRENT";
  const modeOptions = state.status?.mode === "DEMO"
    ? `<option value="SIMULATED" ${state.workspaceReviewMode === "SIMULATED" ? "selected" : ""}>SIMULATED</option><option value="REPLAY" ${state.workspaceReviewMode === "REPLAY" ? "selected" : ""}>REPLAY</option><option value="LIVE_MODEL_RUN" disabled>LIVE_MODEL_RUN</option>`
    : '<option value="LIVE_MODEL_RUN" selected>LIVE_MODEL_RUN</option>';
  const scopeCard = workspaceCard("검토 범위와 Claim", claim.assessment_scope?.label || "검토 목적 미지정", `<div class="scope-tags" style="margin-top:0"><span>unit: ${escapeHtml(scope.unit || "—")}</span><span>configuration: ${escapeHtml(scope.configuration || "—")}</span><span>run: ${escapeHtml(scope.run || "—")}</span></div><div class="claimbox"><b>${escapeHtml(claim.display_id)} / ${escapeHtml(requirement?.display_id || "연결 요구사항")}</b>${escapeHtml(requirement?.statement || claim.question)}</div>`);
  const evidenceBoard = workspaceCard("Evidence Board", "검토 근거와 적용범위", `<div class="evtabs">${[["current", "현재 범위"], ["reference", "Reference"], ["unresolved", "미해결"], ["excluded", "제외 기록"]].map(([key, label]) => `<button class="${state.workspaceEvidenceTab === key ? "active" : ""}" data-evidence-tab="${key}">${label}</button>`).join("")}</div>${workspaceEvidenceList(state.workspaceEvidenceTab)}`, '<button class="btn small" data-open-artifact>+ 자료 등록</button>');
  const ragCard = workspaceCard("문서 RAG", "원문 위치를 보존한 PostgreSQL FTS 검색", renderRagRetrieval(), '<span class="pill info">FTS v1</span>');
  const retrievalCount = activeRetrieval()?.run?.selected_count || 0;
  const requestCard = workspaceCard("검토 요청", "질문과 구조화 자료를 입력 Snapshot에 보존", `<div class="formgrid"><div class="field"><label>Claim</label><select id="workspaceClaimSelect">${state.claims.map(item => `<option value="${item.id}" ${item.id === claim.id ? "selected" : ""}>${escapeHtml(item.display_id)}</option>`).join("")}</select></div><div class="field"><label>실행 모드</label><select id="workspaceReviewMode">${modeOptions}</select></div><div class="field full"><label>Claim 검토 목적 (변경 시 새 revision)</label><select id="workspacePurpose">${reviewPurposeOptions(claim.review_purpose || "UNSPECIFIED")}</select><button class="btn small" data-save-claim-purpose>목적과 질문 저장</button></div><div class="field full"><label>검토 질문</label><textarea id="workspaceQuestion">${escapeHtml(claim.question)}</textarea></div></div><div class="space" style="height:10px"></div><div class="buttons" style="justify-content:space-between"><span class="tiny muted">직접 근거 ${state.selectedEvidenceIds.length}건 + RAG 청크 ${retrievalCount}건 / 질문 변경 시 Claim revision 생성</span><button class="btn primary" data-run-review>검토 실행</button></div><details><summary>실행과 검증 경계</summary><p class="tiny muted">DEMO는 구조와 저장 흐름을 확인한다. LIVE와 자동 fallback하지 않으며 미제공 참조와 JSON 오류는 Validator가 거부한다. 검색 결과는 Evidence 수용이나 공식 판정을 뜻하지 않는다.</p></details>`);
  const resultMode = state.jobDetail?.job?.mode || state.workspaceReviewMode;
  const resultCard = workspaceCard(
    "AI 검토 초안",
    "모델 원출력과 담당자 검토",
    renderWorkspaceResult(),
    `<span class="pill info">${escapeHtml(resultMode)}</span>`,
  );
  const nextCard = workspaceCard("다음 업무와 실행 조건", "판단 범위별로 연결", `<div class="checksummary"><span>등록된 입력 근거</span><span class="pill ${inputReady ? "ok" : "wait"}">${inputReady ? "등록됨 / 판단 전" : "자료 보완"}</span></div><div class="checksummary"><span>검토 의견</span><span class="pill ${accepted ? "ok" : "wait"}">${accepted ? "수용" : "대기"}</span></div><div class="checksummary"><span>상관 계산</span><span class="pill wait">ToolRun 미구현</span></div><div class="space"></div><button class="btn link" data-workspace-mode="BM2">BM2 물리 분석으로 이동 →</button>`);
  const boundaryCard = workspaceCard("출력과 권한의 구분", "상태 축을 각각 저장", '<p class="smalltext muted">출력 검증은 JSON과 참조를 확인한다. 검토 의견 수용, 시험 실행 허가, 결과 수용과 검증 종결에는 각 범위의 담당자 결정을 기록한다.</p>', `<button class="btn link small" data-source-chapter="14">${icon("log")}문서 근거</button>`);
  const traceCard = workspaceCard("오케스트레이션 실행 이력", "CP1 입력 / CP2 실행 / CP3 산출물 검사", renderWorkspaceTrace(), '<button class="btn link" data-page="audit">실행 로그</button>');
  return `<div class="workcols"><div class="stack">${assessmentScopeNotice(claim.assessment_scope)}${scopeCard}${evidenceBoard}${ragCard}${requestCard}</div><div class="stack">${resultCard}${nextCard}${boundaryCard}</div></div>${traceCard}`;
}

function renderWorkspacePreview(mode) {
  const bm2 = mode === "BM2";
  const title = bm2 ? "상관 계산 작업" : "다음 시험 조건 후보";
  const detail = bm2 ? "ToolRun, 계산 receipt와 계측 품질 승인 객체가 아직 구현되지 않았습니다." : "후속 시험 후보, 일정 계획과 실행 승인 객체가 아직 구현되지 않았습니다.";
  return `<div class="notice amber">${escapeHtml(detail)} 이 탭은 목업의 업무 경계를 보존하며 브라우저 계산이나 가상 계획을 서버 결과로 저장하지 않습니다. <button class="btn link small" data-workspace-mode="BM1">자료 검토로 이동</button></div><div class="space"></div><div class="workcols"><div class="stack">${workspaceCard(title, bm2 ? "입력과 실행 receipt가 준비된 뒤 연결" : "Scientific Selector와 Operational Scheduler 경계", `<div class="empty">${bm2 ? "BM1 검토 수용과 ToolRun 계약 대기" : "후속 시험 계획 API 대기"}</div>`)}</div><div class="stack">${workspaceCard(bm2 ? "Tool Result" : "후속 시험계획", "공학 승인과 분리", '<div class="resultpanel wait"><div class="resultcode">NOT_IMPLEMENTED</div><p class="smalltext">기능이 준비되기 전까지 결과를 생성하거나 완료로 표시하지 않습니다.</p></div>')}</div></div>`;
}

function renderWorkspace() {
  const root = $("workspaceContent");
  if (!root || !state.project) return;
  const profile = profiles[state.project.framework] || profiles.KASA;
  const phase = state.project.current_phase ?? 4;
  const step = Math.max(0, Math.min(state.workspaceStep, workspaceSteps.length - 1));
  const completeStates = new Set(["입력 등록", "채택 기록", "검토 완료", "자료 접수", "완료"]);
  root.innerHTML = `<div class="pagehead"><div><div class="eyebrow">TEST WORKSPACE</div><h1>${escapeHtml(state.project.test_run)} / 열모델 상관 검토</h1><p class="subtitle">상위 단계 ${escapeHtml(profile.codes[phase])} → ${escapeHtml(gateByKey("trb")?.display_name || "TRB")} → 개별 시험 업무</p></div><div class="buttons"><button class="btn" data-open-blackboard>${icon("layers")}Blackboard</button><button class="btn" data-open-router>${icon("flask")}모델 경로</button>${state.workspaceMode === "BM1" ? '<button class="btn primary" data-run-review>검토 실행</button>' : ""}</div></div><div class="workhead"><div class="segments">${[["BM1", "자료 검토"], ["NTR", "다음 시험"], ["BM2", "물리 분석"]].map(([key, label]) => `<button class="segment ${state.workspaceMode === key ? "active" : ""}" data-workspace-mode="${key}">${key} / ${label}</button>`).join("")}</div><div class="buttons"><span class="pill info">${escapeHtml(state.project.framework)} / ${escapeHtml(state.project.baseline_display_id)}</span><span class="pill">입력 v${selectedWorkspaceClaim()?.version || 0}</span></div></div><div class="workgrid"><aside class="card testrail"><div class="header-label">TEST LIFECYCLE</div>${workspaceSteps.map((label, index) => { const status = workspaceStepState(index); return `<button class="${step === index ? "active" : ""} ${completeStates.has(status) ? "complete" : ""}" data-workspace-step="${index}" title="${escapeHtml(status)}"><span class="step-num">${index + 1}</span><span>${escapeHtml(label)}</span></button>`; }).join("")}</aside><div class="stack"><div class="inset"><div class="buttons" style="justify-content:space-between"><h4>${step + 1}. ${escapeHtml(workspaceSteps[step])} / ${escapeHtml(workspaceStepInfo[step][0])}</h4><span class="pill info">${escapeHtml(workspaceStepState(step))}</span></div><p class="tiny muted" style="margin-top:4px">${escapeHtml(workspaceStepInfo[step][1])}</p></div>${state.workspaceMode === "BM1" ? renderBM1Workspace() : renderWorkspacePreview(state.workspaceMode)}</div></div>`;
}

function closureClaimView() {
  return state.closureData.claims?.find(item => item.claim.id === state.selectedClaimId) || state.closureData.claims?.[0] || null;
}

function closureStatusPill(label, style = "wait") {
  return `<span class="pill ${style}">${escapeHtml(label)}</span>`;
}

function renderClosureProductMatrix(view) {
  const rows = state.requirements.map(requirement => {
    const linked = state.closureData.claims?.find(item => item.claim.id === requirement.claim_id);
    let status = requirement.ui_status || "PLANNED";
    let style = "wait";
    let basis = "관련 자료 연결 대기";
    const scope = requirement.assessment_scope;
    const matches = scope?.supported && requirement.review_purpose === linked?.assessment_scope?.review_purpose;
    if (!scope?.supported) {
      status = scope?.status || "PURPOSE_UNSPECIFIED";
      basis = `${scope?.label || "검토 목적 미지정"} / NOT_EVALUATED`;
    } else if (matches && linked?.current_closure?.review_purpose === requirement.review_purpose) {
      status = `${scope.label} / ${linked.current_closure.result}`;
      style = linked.current_closure.result === "SATISFIED" ? "ok" : "bad";
      basis = `${linked.current_closure.baseline_display_id} / ${linked.current_closure.test_run}`;
    } else if (matches && linked?.ready_for_satisfied) {
      status = "READY_FOR_CLOSURE";
      style = "info";
      basis = `${scope.label} / 근거·품질·TRB 조건 충족`;
    } else if (linked) {
      const satisfied = linked.checks.filter(item => item.satisfied).length;
      basis = `종결 조건 ${satisfied}/${linked.checks.length}`;
    }
    return `<tr><td><button class="refbutton" data-requirement-id="${requirement.id}">${escapeHtml(requirement.display_id)}</button><span class="subline">${escapeHtml(requirement.display_claim)}</span></td><td>${escapeHtml(requirement.verification_method)}</td><td>${escapeHtml(basis)}</td><td>${closureStatusPill(status, style)}</td></tr>`;
  }).join("");
  return `<section class="card"><div class="cardhead"><div><h3>Verification Record</h3><p>원자료에서 Claim과 승인까지 연결</p></div></div><div class="tablewrap"><table><thead><tr><th>요구사항</th><th>검증 방법</th><th>결과와 근거</th><th>처분 상태</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function renderClosureProcessMatrix(view) {
  const trb = gateByKey("trb");
  const quality = view?.latest_quality_assessment;
  const rows = [
    ["PROC-01", "요구사항과 기준점 관리", state.project.baseline_display_id, Boolean(state.project.baseline_display_id)],
    ["PROC-02", "단계별 기술검토", trb?.display_name || "TRB", trb?.state === "REVIEW_COMPLETE"],
    ["PROC-03", "자료 품질과 추적성", quality?.quality_status || "품질 검토 대기", quality?.quality_status === "VALID"],
    ["PROC-04", "검토 종결과 승인", view?.current_closure?.assessment_scope?.supported ? `${view.claim.display_id} / ${view.current_closure.assessment_scope.closure_label}` : "목적별 종결 확인 대기", Boolean(view?.current_closure?.assessment_scope?.supported)],
  ];
  return `<section class="card"><div class="cardhead"><div><h3>프로세스 요구조건 대응</h3><p>항목 ID는 시연용이며 공식 조항은 채택 원문과 연결</p></div></div><div class="tablewrap"><table><thead><tr><th>프로젝트 항목</th><th>요구하는 기록</th><th>현재 대응</th><th>상태</th></tr></thead><tbody>${rows.map(row => `<tr><td><code>${row[0]}</code></td><td>${escapeHtml(row[1])}</td><td>${escapeHtml(row[2])}</td><td>${closureStatusPill(row[3] ? "기록 확보" : "확인 대기", row[3] ? "ok" : "wait")}</td></tr>`).join("")}</tbody></table></div></section>`;
}

function renderClosure() {
  const root = $("closureContent");
  if (!root || !state.project) return;
  const view = closureClaimView();
  if (!view) {
    root.innerHTML = `<div class="pagehead"><div><div class="eyebrow">VERIFICATION &amp; HANDOVER</div><h1>검증 종결과 인계</h1><p class="subtitle">결과의 품질, 적용범위와 담당자 결정을 확인합니다.</p></div></div><div class="empty">종결 대상 Claim이 없습니다.</div>`;
    return;
  }
  const closed = Boolean(view.current_closure && view.current_closure.assessment_scope?.supported && view.assessment_scope?.supported);
  const quality = view.latest_quality_assessment;
  const rule = view.checks.find(item => item.code === "RULE_JUDGEMENT")?.satisfied;
  const evidence = view.checks.find(item => item.code === "CURRENT_EVIDENCE")?.satisfied;
  const valid = view.checks.find(item => item.code === "VALID_RESULT")?.satisfied;
  const completedJob = state.jobs.find(item => item.status === "COMPLETED");
  const profile = profiles[state.project.framework] || profiles.KASA;
  const history = state.closureData.history || [];
  const stateBoxes = [
    [view.assessment_scope?.label || "검토 목적 미지정", rule ? "추가 자료 조치 없음" : !view.assessment_scope?.supported ? "판단 보류" : valid ? "결과 보완" : "확인 대기", rule ? "ok" : "wait"],
    ["근거 상태", evidence ? "입력 확보" : "자료 보완", evidence ? "ok" : "wait"],
    ["데이터 품질", quality?.quality_status || "검토 대기", quality?.quality_status === "VALID" ? "ok" : quality?.quality_status === "INVALID" ? "bad" : "wait"],
    ["업무 상태", closed ? "해당 검토 종결" : "진행 중", closed ? "ok" : "info"],
    ["승인", closed ? "권한자 결정 기록" : "승인 대기", closed ? "ok" : "wait"],
    ["Claim 결과", closed ? view.current_closure.result : history.length ? "REOPENED" : "INCONCLUSIVE", closed ? "ok" : "wait"],
  ];
  const historyHtml = history.length ? history.map(item => `<div class="task"><span class="task-index">${icon("circle")}</span><div class="grow"><h4>${escapeHtml(item.claim_display_id)} / ${escapeHtml(item.assessment_scope?.label || "검토 목적 미지정")} / ${escapeHtml(item.product_configuration)} / ${escapeHtml(item.test_run)}</h4><p>${escapeHtml(item.note)}<br>승인자: ${escapeHtml(item.actor)} / Claim v${item.source_claim_version}, project v${item.source_project_version}</p></div>${closureStatusPill(item.assessment_scope?.supported ? (item.id === view.current_closure?.id ? "현재 입력준비 종결" : "재검토 또는 이전 기록") : "목적 미확인 보존 기록", item.id === view.current_closure?.id ? "ok" : "wait")}</div>`).join("") : '<div class="empty">권한자의 종결 결정이 여기에 연결됩니다.</div>';
  root.innerHTML = `<div class="pagehead"><div><div class="eyebrow">VERIFICATION &amp; HANDOVER</div><h1>검증 종결과 인계</h1><p class="subtitle">결과의 품질, 적용범위와 담당자 결정을 확인하고 요구사항별 종결 기록을 구성합니다.</p></div><div class="buttons"><button class="btn" data-closure-report ${completedJob ? "" : "disabled"}>${icon("log")}보고서 저장</button><button class="btn primary" data-open-closure ${view.ready_for_satisfied && !closed ? "" : "disabled"}>${escapeHtml(view.assessment_scope?.closure_label || "종결 판단 보류")}</button></div></div>
  ${assessmentScopeNotice(view.assessment_scope)}<div class="space"></div><div class="stategrid">${stateBoxes.map(([key, value, style]) => `<div class="statebox"><div class="key">${key}</div>${closureStatusPill(value, style)}</div>`).join("")}</div><div class="space"></div>
  <div class="grid2"><section class="card"><div class="cardhead"><div><h3>종결 전 확인사항</h3><p>${escapeHtml(view.claim.display_id)}와 현재 scope에 한정한 검증 범위</p></div></div><div class="cardbody">${gateChecklist(view.checks, true)}<div class="space"></div><div class="buttons"><button class="btn" data-open-quality ${valid ? "" : "disabled"}>데이터 품질 검토</button><button class="btn" data-gate-id="${gateByKey("trb")?.id || ""}">${escapeHtml(gateByKey("trb")?.display_name || "TRB")} 결과 검토</button><button class="btn primary" data-open-closure ${view.ready_for_satisfied && !closed ? "" : "disabled"}>권한자 종결 결정</button></div></div></section>
  <section class="card"><div class="cardhead"><div><h3>납품 기록 형식</h3><p>${escapeHtml(profile.name)} 프로젝트 프로파일</p></div><button class="btn link small" data-source-chapter="14">${icon("log")}문서 근거</button></div><div class="cardbody"><h3>${escapeHtml(profile.output)}</h3><p class="smalltext muted" style="margin-top:9px">판정 근거와 실제 범위, 자료 수용과 승인 기록을 포함합니다. 상위 임무 적합성은 별도 검증 관계로 보존합니다.</p><div class="space"></div>${closureStatusPill(closed ? "인수 검토자료 준비" : "자료 구성 중", closed ? "ok" : "wait")}<div class="space"></div><button class="btn link" data-gate-id="${gateByKey("accept")?.id || ""}">제품 인수 검토</button></div></section></div><div class="space"></div>
  <div class="toolbar"><div class="segments"><button class="segment ${state.closureMatrix === "product" ? "active" : ""}" data-closure-matrix="product">제품 검증 매트릭스</button><button class="segment ${state.closureMatrix === "process" ? "active" : ""}" data-closure-matrix="process">프로세스 만족 매트릭스</button></div><span class="tiny muted">기준점 ${escapeHtml(state.project.baseline_display_id)} / ${escapeHtml(state.project.product_configuration)}</span></div>
  ${state.closureMatrix === "product" ? renderClosureProductMatrix(view) : renderClosureProcessMatrix(view)}<div class="space"></div>
  <section class="card"><div class="cardhead"><div><h3>검토 목적별 종결 결정 이력</h3><p>이전 기준점의 결정은 그때의 범위로 보존</p></div></div><div class="cardbody">${historyHtml}</div></section>`;
}

function renderChanges() {
  const root = $("changesContent");
  if (!root || !state.project) return;
  const project = state.project;
  const impact = state.changeData.impact || {};
  const requirements = state.requirements.filter(item => item.display_id.startsWith("THM-")).map(item => item.display_id).join(" / ") || "연결 요구사항 없음";
  const changes = state.changeData.changes || [];
  const changeRows = changes.length ? changes.map(change => {
    const style = change.status === "APPLIED" ? "ok" : change.status === "REJECTED" ? "bad" : "wait";
    const savedImpact = change.impact_assessment || {};
    return `<article class="task"><span class="task-index">${icon("change")}</span><div class="grow"><h4>${escapeHtml(change.change_code)} / ${escapeHtml(change.from_baseline)} → ${escapeHtml(change.to_baseline)}</h4><p>${escapeHtml(change.reason)}<br>제품 형상 ${escapeHtml(change.from_configuration)} → ${escapeHtml(change.to_configuration)} · 후속 실행 ${escapeHtml(change.to_test_run)}<br><span class="tiny muted">영향: Claim ${savedImpact.affected_claims || 0}, ReviewJob ${savedImpact.current_review_jobs || 0}, 종결 ${savedImpact.current_closures || 0} · 요청자 ${escapeHtml(change.requested_by)}</span></p></div><div class="change-actions">${closureStatusPill(change.status, style)}${change.status === "DRAFT" ? `<button class="btn small" data-change-decision="${change.id}">영향 검토와 적용</button>` : `<small class="muted">${change.decided_by ? escapeHtml(change.decided_by) : "결정 완료"}</small>`}</div></article>`;
  }).join("") : '<div class="empty">형상 변경을 요청하면 관련 근거와 종결 기록의 영향 범위를 확인할 수 있습니다.</div>';
  root.innerHTML = `<div class="pagehead"><div><div class="eyebrow">CONFIGURATION &amp; IMPACT</div><h1>기준점과 변경 영향</h1><p class="subtitle">형상 변경은 새 버전으로 적용하고, 종속된 검토와 승인에 재검토 상태를 부여합니다.</p></div><div class="buttons"><button class="btn primary" data-open-change>${icon("change")}형상 변경 요청</button></div></div>
  <div class="equal2"><section class="card"><div class="cardhead"><div><h3>현재 형상 기준점</h3><p>제품 형상과 관련 자료를 고정해 변경의 비교 기준으로 관리합니다.</p></div>${closureStatusPill(`project v${project.version}`, "info")}</div><div class="cardbody"><dl class="kv"><dt>형상 기준점</dt><dd><b>${escapeHtml(project.baseline_display_id)}</b></dd><dt>제품 형상</dt><dd>${escapeHtml(project.product_configuration)}</dd><dt>시험 run</dt><dd>${escapeHtml(project.test_run)}</dd><dt>요구사항</dt><dd>${escapeHtml(requirements)}</dd><dt>인터페이스</dt><dd>ICD-TH-008</dd><dt>프로파일</dt><dd>${escapeHtml(project.framework)} / project v${project.version}</dd><dt>입력 버전</dt><dd>Claim ${state.claims.map(item => `v${item.version}`).join(", ") || "없음"}</dd></dl></div></section>
  <section class="card"><div class="cardhead"><div><h3>변경 전파 경로</h3><p>이전 기록은 당시 기준점의 이력으로 보존</p></div></div><div class="cardbody"><div class="chain"><div class="chain-node"><b>1. 제품 형상 또는 계측 조건 변경</b><small>변경 사유와 CCB 결정</small></div><div class="chain-node"><b>2. 적용 가능한 관측 재구성</b><small>기존 run은 당시 형상으로 보존</small></div><div class="chain-node"><b>3. 검토와 계산 결과의 현행성 확인</b><small>새 입력 스냅샷과 후속 분석</small></div><div class="chain-node"><b>4. Claim과 검토회의 재검토</b><small>TRR, TRB와 인수 자료의 적용범위</small></div></div></div></section></div><div class="space"></div>
  <section class="card"><div class="cardhead"><div><h3>변경 요청과 CCB 처리</h3><p>권한자가 영향을 확인한 뒤 적용</p></div><div class="buttons"><span class="pill">현재 영향 Claim ${impact.affected_claims || 0}</span><span class="pill">ReviewJob ${impact.current_review_jobs || 0}</span></div></div><div class="cardbody stack">${changeRows}</div></section><div class="space"></div>
  <section class="card"><div class="cardhead"><div><h3>동시 변경 보호</h3><p>같은 객체에 대한 이전 버전의 명령을 검사</p></div><button class="btn" data-stale-change-demo>이전 버전 명령 시연</button></div><div class="cardbody"><p>변경 요청은 대상 버전과 권한을 포함한다. 이전 버전의 요청은 충돌 기록을 남기고 새 기준점을 확인하도록 안내한다.</p><div class="space"></div><div class="notice blue">현재 project version ${project.version}. 적용 시 서버가 한 트랜잭션에서 version을 증가시키고 ReviewJob을 STALE로 전환합니다.</div></div></section>`;
}

function nextBaseline(value) {
  const match = String(value || "").match(/^(.*?)(\d+)$/);
  if (!match) return `${value || "BL"}-NEXT`;
  return `${match[1]}${String(Number(match[2]) + 1).padStart(match[2].length, "0")}`;
}

function nextConfiguration(value) {
  const match = String(value || "").match(/^(.*?)([A-Z])$/);
  return match ? `${match[1]}${String.fromCharCode(match[2].charCodeAt(0) + 1)}` : `${value || "CONFIG"}-NEXT`;
}

function openChangeRequestDialog() {
  const form = $("changeRequestForm");
  form.elements.expected_project_version.value = state.project.version;
  form.elements.to_baseline.value = nextBaseline(state.project.baseline_display_id);
  form.elements.to_configuration.value = nextConfiguration(state.project.product_configuration);
  form.elements.to_test_run.value = nextBaseline(state.project.test_run);
  $("changeRequestCurrent").textContent = `현재 ${state.project.baseline_display_id} / ${state.project.product_configuration} / ${state.project.test_run} · project v${state.project.version}`;
  $("changeRequestDialog").showModal();
}

function openChangeDecisionDialog(changeId) {
  const role = $("role").value.split("@")[0];
  if (role !== "approver") return message("CCB 적용과 기각은 승인권자 역할에서만 수행할 수 있습니다.");
  const change = (state.changeData.changes || []).find(item => item.id === changeId);
  if (!change || change.status !== "DRAFT") return message("현재 결정할 수 있는 DRAFT 변경 요청이 없습니다.");
  const form = $("changeDecisionForm");
  form.elements.change_id.value = change.id;
  form.elements.expected_change_version.value = change.version;
  form.elements.expected_project_version.value = state.project.version;
  form.elements.disposition.value = "APPLIED";
  $("changeDecisionActor").value = $("role").selectedOptions[0].textContent;
  const impact = change.impact_assessment || {};
  $("changeDecisionImpact").innerHTML = `<dl class="kv"><dt>변경</dt><dd>${escapeHtml(change.from_baseline)} / ${escapeHtml(change.from_configuration)} / ${escapeHtml(change.from_test_run)}<br>→ ${escapeHtml(change.to_baseline)} / ${escapeHtml(change.to_configuration)} / ${escapeHtml(change.to_test_run)}</dd><dt>영향 Claim</dt><dd>${impact.affected_claims || 0}</dd><dt>STALE 전환 검토</dt><dd>${impact.current_review_jobs || 0}</dd><dt>이전 승인 기록</dt><dd>Gate ${impact.current_gate_decisions || 0} · 종결 ${impact.current_closures || 0}</dd><dt>미해결 자료 요청</dt><dd>${impact.open_evidence_requests || 0}</dd></dl>`;
  $("changeDecisionDialog").showModal();
}

async function demonstrateStaleChange() {
  try {
    await api(`/api/v1/projects/${state.project.id}/changes`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        to_baseline: `${state.project.baseline_display_id}-STALE-DEMO`,
        to_configuration: state.project.product_configuration,
        to_test_run: state.project.test_run,
        reason: "이전 project version 명령 충돌 시연",
        expected_project_version: state.project.version + 1
      })
    });
    message("예상하지 못한 결과입니다. 서버가 이전 version 명령을 수용했습니다.");
  } catch (error) {
    message(`서버가 이전 project version 명령을 거부했습니다: ${error.message}`, true);
  }
}

function openQualityAssessmentDialog() {
  const role = $("role").value.split("@")[0];
  if (!new Set(["reviewer", "approver"]).has(role)) return message("데이터 품질 검토는 검토 책임자 또는 승인권자 역할에서 수행할 수 있습니다.");
  const view = closureClaimView();
  if (!view?.checks.find(item => item.code === "VALID_RESULT")?.satisfied) return message("현재 version의 검증된 검토 결과가 필요합니다.");
  const form = $("qualityAssessmentForm");
  form.elements.claim_id.value = view.claim.id;
  form.elements.expected_claim_version.value = view.claim.version;
  form.elements.expected_project_version.value = state.project.version;
  form.elements.quality_status.value = view.latest_quality_assessment?.quality_status || "VALID";
  $("qualityAssessmentActor").value = $("role").selectedOptions[0].textContent;
  $("qualityAssessmentDialog").showModal();
}

function openClosureDecisionDialog() {
  const role = $("role").value.split("@")[0];
  if (role !== "approver") return message("공식 Claim 종결은 승인권자 역할에서만 수행할 수 있습니다.");
  const view = closureClaimView();
  if (!view?.ready_for_satisfied || view.current_closure) return message("현재 version의 종결 선행조건이 모두 충족되지 않았습니다.");
  const form = $("closureDecisionForm");
  form.elements.claim_id.value = view.claim.id;
  form.elements.expected_claim_version.value = view.claim.version;
  form.elements.expected_project_version.value = state.project.version;
  $("closureDecisionActor").value = $("role").selectedOptions[0].textContent;
  $("closureDecisionChecks").innerHTML = assessmentScopeNotice(view.assessment_scope) + gateChecklist(view.checks, true);
  $("closureDecisionDialog").showModal();
}

function exportClosureReport() {
  const job = state.jobs.find(item => item.status === "COMPLETED");
  if (!job) return message("완료된 BM1 검토가 있어야 현재 snapshot 보고서를 저장할 수 있습니다.");
  exportJobReport(job.id);
}

function openArtifactDialog() {
  const scope = workspaceScope();
  const form = $("evidenceForm");
  form.elements.scope_unit.value = scope.unit || "";
  form.elements.scope_configuration.value = scope.configuration || "";
  form.elements.scope_run.value = scope.run || "";
  $("ragParseState").hidden = true;
  $("artifactDialog").showModal();
}

async function openEvidenceDialog(evidenceId) {
  try {
    const item = await api(`/api/v1/evidence/${evidenceId}`);
    const [included, reason] = evidenceEligibility(item);
    $("evidenceDialogTitle").textContent = `${item.display_id} / 근거 상세`;
    $("evidenceDialogBody").innerHTML = `<div class="buttons"><span class="pill info">${escapeHtml(item.kind)}</span><span class="pill ${included ? "ok" : "wait"}">${escapeHtml(reason)}</span></div><dl class="kv"><dt>파일</dt><dd>${escapeHtml(item.filename)}</dd><dt>SHA256</dt><dd><code>${escapeHtml(item.artifact_sha256)}</code></dd><dt>문서 판본</dt><dd>${escapeHtml(item.edition || "미확인")}</dd><dt>인용 판본</dt><dd>${escapeHtml(item.source_verification?.cited_edition || "미확인")}</dd><dt>Basis</dt><dd>${escapeHtml(item.basis)}</dd><dt>Scope</dt><dd><code>${escapeHtml(JSON.stringify(item.scope))}</code></dd><dt>Locator</dt><dd>${escapeHtml(item.locator || "없음")}</dd></dl><div class="space"></div><div class="notice blue">${escapeHtml(item.quote || "확인된 발췌 없음")}</div>`;
    $("evidenceDownload").href = `/api/v1/artifacts/${item.download_artifact_id}/download`;
    $("evidenceDialogBody").insertAdjacentHTML("beforeend", `<div class="space"></div>${citationNotice(item)}`);
    $("evidenceDialog").showModal();
  } catch (error) { message(error.message); }
}

async function runDocumentRetrieval() {
  const claim = selectedWorkspaceClaim();
  const input = $("ragQuery");
  const query = input?.value.trim() || "";
  if (!claim) return message("문서 검색에 사용할 Claim이 없습니다.");
  if (query.length < 2) return message("두 글자 이상의 문서 검색어를 입력하십시오.");
  state.ragQuery = query;
  try {
    const retrieval = await api(`/api/v1/projects/${state.project.id}/retrievals`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID()},
      body: JSON.stringify({
        claim_id: claim.id,
        query,
        artifact_ids: [],
        top_k: Number($("ragTopK")?.value || 4)
      })
    });
    state.retrieval = retrieval;
    state.retrievalRuns = [retrieval.run, ...state.retrievalRuns.filter(item => item.id !== retrieval.run.id)];
    renderWorkspace();
    message(`문서 검색 완료: 후보 ${retrieval.run.candidate_count}건 중 ${retrieval.run.selected_count}건을 Context 후보로 고정했습니다.`, true);
  } catch (error) { message(error.message); }
}

function openRagChunkDialog(chunkId) {
  const item = state.retrieval?.results?.find(result => result.chunk_id === chunkId);
  if (!item || !item.selected) return message("현재 retrieval receipt에 선택된 문서 청크가 아닙니다.");
  $("evidenceDialogTitle").textContent = `${item.filename} / 검색 청크 #${item.candidate_rank}`;
  $("evidenceDialogBody").innerHTML = `<div class="buttons"><span class="pill info">RAG_RETRIEVED</span><span class="pill ok">${escapeHtml(item.reason)}</span></div><dl class="kv"><dt>원문 Artifact</dt><dd>${escapeHtml(item.artifact_id)}</dd><dt>Artifact SHA256</dt><dd><code>${escapeHtml(item.artifact_sha256)}</code></dd><dt>Chunk SHA256</dt><dd><code>${escapeHtml(item.text_sha256)}</code></dd><dt>Locator</dt><dd>${escapeHtml(item.locator)}</dd><dt>검색 점수</dt><dd>${Number(item.score).toFixed(6)}</dd></dl><div class="space"></div><div class="notice blue">${escapeHtml(item.chunk_text || "청크 원문 비공개")}</div><div class="space"></div><p class="tiny muted">검색 선택은 근거 수용이나 공식 판정이 아닙니다. 이 ID와 해시는 ContextSnapshot receipt에 보존됩니다.</p>`;
  $("evidenceDownload").href = `/api/v1/artifacts/${item.artifact_id}/download`;
  $("evidenceDialog").showModal();
}

function openReviewDecisionDialog(disposition) {
  const role = $("role").value.split("@")[0];
  if (!new Set(["reviewer", "approver"]).has(role)) return message("AI 초안 결정은 검토 책임자 또는 승인권자 역할에서 수행할 수 있습니다.");
  const detail = state.jobDetail;
  if (!detail || detail.job.status !== "AWAITING_REVIEW" || detail.model_run?.validation_status !== "VALID") return message("현재 결정할 수 있는 검증 완료 초안이 없습니다.");
  const form = $("reviewDecisionForm");
  form.elements.job_id.value = detail.job.id;
  form.elements.expected_job_version.value = detail.job.version;
  form.elements.disposition.value = disposition;
  form.elements.edited_draft.value = "";
  $("reviewDecisionActor").value = $("role").selectedOptions[0].textContent;
  $("reviewDecisionDialog").showModal();
}

function blackboardForJob(board, jobId) {
  const contributions = (board.contributions || []).filter(item => jobId && item.source_job_id === jobId);
  const workItems = (board.work_items || []).filter(item => jobId && item.source_job_id === jobId);
  const dependencies = (board.dependencies || []).filter(item => jobId && item.source_job_id === jobId);
  const orchestrationRuns = (board.orchestration_runs || []).filter(item => jobId && item.job_id === jobId);
  const ids = new Set([...contributions, ...workItems, ...orchestrationRuns].map(item => item.id));
  const events = (board.events || []).filter(item => ids.has(item.object_id));
  return {...board, contributions, work_items: workItems, dependencies, orchestration_runs: orchestrationRuns, events,
    summary: {contributions: contributions.length, work_items: workItems.length, dependencies: dependencies.length, events: events.length}};
}

function renderBlackboardProjection(board, jobId) {
  const summary = board.summary || {};
  const project = board.project || {};
  $("blackboardSummary").innerHTML = `<b>${escapeHtml(project.display_id || "프로젝트")}</b> · 기준점 ${escapeHtml(project.baseline_display_id || "—")} · project v${project.version || 0}${jobId !== undefined ? '<br><b>이번 시연에서 저장된 기록</b>' : ""}<br><span class="tiny">제안 ${summary.contributions || 0}건 · 작업 ${summary.work_items || 0}건 · 의존관계 ${summary.dependencies || 0}건 · Event ${summary.events || 0}건</span>`;
  $("contributionList").innerHTML = (board.contributions || []).map(item => {
    const content = item.content || {};
    const title = content.action || item.contribution_type;
    const detail = content.reason || content.reason_code || "대상 상태에 대한 검토 제안";
    const style = item.status === "ACCEPTED" ? "ok" : ["REJECTED", "SUPERSEDED"].includes(item.status) ? "bad" : "wait";
    return `<article class="task"><div class="grow"><h4>${escapeHtml(item.claim_display_id || item.target_object_id)} · ${escapeHtml(title)}</h4><p>${escapeHtml(detail)}<br><span class="tiny muted">${escapeHtml(item.actor_type)} / ${escapeHtml(item.actor_id)} · 읽은 project v${item.read_project_version}</span></p></div><span class="pill ${style}">${escapeHtml(item.status)}</span></article>`;
  }).join("") || '<div class="empty">아직 저장된 제안이나 이견이 없습니다.</div>';
  $("workItemList").innerHTML = (board.work_items || []).map(item => {
    const style = item.status === "COMPLETED" ? "ok" : ["REJECTED", "CANCELLED"].includes(item.status) ? "bad" : "wait";
    return `<article class="task"><div class="grow"><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.purpose)}<br><span class="tiny muted">${escapeHtml(item.claim_display_id || "공통 작업")} · 담당 ${escapeHtml(item.assigned_role)} · v${item.version}</span></p></div><span class="pill ${style}">${escapeHtml(item.status)}</span></article>`;
  }).join("") || '<div class="empty">현재 공용 작업 큐가 비어 있습니다.</div>';
  $("blackboardJson").textContent = JSON.stringify(board, null, 2);
}

async function openBlackboardDialog({jobId = state.autoDemo.active ? state.autoDemo.observedJobId : undefined} = {}) {
  if (!state.project) return message("프로젝트를 먼저 불러와야 합니다.");
  $("blackboardSummary").textContent = "서버 Blackboard를 불러오는 중입니다.";
  $("contributionList").innerHTML = '<div class="empty">불러오는 중</div>';
  $("workItemList").innerHTML = '<div class="empty">불러오는 중</div>';
  $("blackboardJson").textContent = "";
  renderJobs();
  renderRequests();
  // History remains available outside autoplay; the recording view only shows
  // this run's newly observed records, without deleting the stored history.
  const historySection = $("jobList").closest(".equal2");
  historySection.hidden = jobId !== undefined;
  if (!$("blackboardDialog").open) $("blackboardDialog").showModal();
  try {
    const fullBoard = await api(`/api/v1/projects/${state.project.id}/blackboard`);
    const board = jobId === undefined ? fullBoard : blackboardForJob(fullBoard, jobId);
    renderBlackboardProjection(board, jobId);
    return board;
  } catch (error) {
    $("blackboardSummary").textContent = `Blackboard 조회 실패: ${error.message}`;
    message(error.message);
    return null;
  }
}

function openRouterDialog() {
  const detail = state.jobDetail;
  const remote = state.status?.remote || {state: "LOCAL_ONLY"};
  $("routerDialogBody").innerHTML = `<div class="notice ${state.status?.mode === "DEMO" ? "blue" : ""}">${state.status?.mode === "DEMO" ? "명시적 DEMO 모드이며 LIVE로 자동 전환하지 않습니다." : "LIVE_MODEL_RUN은 인증된 tunnel과 exact receipt가 준비된 경우에만 실행합니다."}</div><div class="space"></div><dl class="kv"><dt>App mode</dt><dd>${escapeHtml(state.status?.mode || "—")}</dd><dt>선택 mode</dt><dd>${escapeHtml(state.workspaceReviewMode)}</dd><dt>Remote</dt><dd>${escapeHtml(remote.state)}</dd><dt>Contract</dt><dd>${escapeHtml(detail?.snapshot?.contract_id || "실행 전")}</dd><dt>Model profile</dt><dd>${escapeHtml(detail?.snapshot?.model_profile || "실행 전")}</dd><dt>Fallback</dt><dd>비활성</dd></dl>`;
  $("routerDialog").showModal();
}

function renderClaims() {
  const claimList = $("claimList");
  if (claimList) claimList.innerHTML = state.claims.map(c => `<article class="item"><strong>${escapeHtml(c.display_id)}</strong><span>${escapeHtml(c.question)}</span><small>version ${c.version} · ${escapeHtml(c.assessment_scope?.label || "검토 목적 미지정")} · ${escapeHtml(c.review_target)} · ${escapeHtml(c.status)}</small></article>`).join("") || '<p class="muted">Claim 없음</p>';
}

function renderEvidence() {
  renderWorkspace();
}

function renderJobs() {
  const root = $("jobList");
  if (!root) return;
  root.innerHTML = state.jobs.map(job => `<article class="item"><strong>${escapeHtml(job.claim_display_id)} · ${escapeHtml(job.status)}</strong><span>${escapeHtml(job.mode)} · ${escapeHtml(job.freshness)}</span><small>${new Date(job.created_at).toLocaleString()} · 자료요청 ${job.evidence_request_count} · 보고서 ${job.report_count}${job.latest_disposition ? ` · ${escapeHtml(job.latest_disposition)}` : ""}</small><div class="item-actions"><button class="btn small" data-open-job="${job.id}">다시 열기</button><button class="btn small" data-export-job="${job.id}" ${job.status === "COMPLETED" ? "" : "disabled"}>Markdown 보고서</button></div></article>`).join("") || '<p class="muted">저장된 검토 없음</p>';
}

function evidenceOptions(selected = null) {
  return state.evidence.map(item => `<option value="${item.id}"${item.id === selected ? " selected" : ""}>${escapeHtml(item.display_id)} · ${escapeHtml(item.filename)}</option>`).join("");
}

function renderRequestCards() {
  return state.requests.map(request => {
    const canSubmit = ["OPEN", "RECEIVED"].includes(request.status) && state.evidence.length;
    const canDecide = request.status === "RECEIVED";
    return `<article class="evitem"><div class="evitem-head"><h4>${escapeHtml(request.claim_display_id)} / ${escapeHtml(request.requested_item)}</h4><span class="pill ${request.status === "ACCEPTED" ? "ok" : request.status === "REJECTED" ? "bad" : "wait"}">${escapeHtml(request.status)}</span></div><p>source ${escapeHtml(request.source)} · version ${request.version}${request.submitted_evidence_display_id ? ` · 제출 ${escapeHtml(request.submitted_evidence_display_id)}` : ""}</p><div class="item-actions"><select class="requestEvidence" data-request-id="${request.id}" ${canSubmit ? "" : "disabled"}>${evidenceOptions(request.submitted_evidence_id)}</select><button class="btn small" data-request-action="submit" data-request-id="${request.id}" data-version="${request.version}" ${canSubmit ? "" : "disabled"}>근거 제출</button><button class="btn small" data-request-action="ACCEPTED" data-request-id="${request.id}" data-version="${request.version}" ${canDecide ? "" : "disabled"}>수용</button><button class="btn small" data-request-action="REJECTED" data-request-id="${request.id}" data-version="${request.version}" ${canDecide ? "" : "disabled"}>기각</button></div></article>`;
  }).join("") || '<div class="empty">현재 범위의 자료 요청이 없습니다.</div>';
}

function renderRequests() {
  const root = $("requestList");
  if (root) root.innerHTML = renderRequestCards();
}

async function loadJobsAndRequests() {
  if (!state.project) return;
  [state.jobs, state.requests, state.closureData] = await Promise.all([
    api(`/api/v1/projects/${state.project.id}/jobs`),
    api(`/api/v1/projects/${state.project.id}/evidence-requests`),
    api(`/api/v1/projects/${state.project.id}/closure`)
  ]);
  const currentId = state.jobs.some(item => item.id === state.job?.id) ? state.job.id : state.jobs[0]?.id;
  if (currentId) {
    state.jobDetail = await api(`/api/v1/jobs/${currentId}`);
    state.job = state.jobDetail.job;
  } else {
    state.job = null;
    state.jobDetail = null;
  }
  if (state.quickDemo.jobId && state.jobDetail?.job?.id === state.quickDemo.jobId) state.quickDemo.detail = state.jobDetail;
  renderJobs(); renderRequests(); renderWorkspace(); renderClosure(); renderOverview(); renderGates(); renderQuickDemo(); renderShell();
}

let citationChunks = [];

$("citationChunk").addEventListener("change", event => {
  const chunk = citationChunks.find(item => item.id === event.target.value);
  const form = $("evidenceForm");
  for (const field of ["page_start", "page_end", "line_start", "line_end"]) form.elements[field].value = chunk ? (chunk[field] ?? chunk.metadata[field] ?? "") : "";
  form.elements.locator.value = chunk?.locator || "";
  form.elements.quote.value = chunk?.chunk_text || "";
});

$("uploadForm").addEventListener("submit", async event => {
  event.preventDefault();
  if (!state.project) return message("먼저 세션을 시작하십시오.");
  const form = new FormData(event.currentTarget);
  form.set("adopted", form.get("adopted") ? "true" : "false");
  form.set("applicability_status", "APPLICABLE");
  const parseState = $("ragParseState");
  parseState.hidden = false;
  parseState.className = "notice blue";
  parseState.textContent = "원본을 저장하고 문서 텍스트를 파싱하는 중입니다.";
  try {
    const artifact = await api(`/api/v1/projects/${state.project.id}/artifacts`, {method: "POST", headers: csrfHeaders, body: form});
    $("evidenceForm").hidden = false;
    $("evidenceForm").elements.artifact_id.value = artifact.id;
    $("evidenceForm").elements.cited_edition.value = artifact.edition || "";
    citationChunks = [];
    $("citationChunk").innerHTML = '<option value="">청크 선택 전 / 원문 대조 대기</option>';
    $("citationChunk").dispatchEvent(new Event("change"));
    try {
      const parsed = await api(`/api/v1/artifacts/${artifact.id}/parse`, {method: "POST", headers: csrfHeaders});
      const run = parsed.parser_run;
      citationChunks = (parsed.chunks || []).filter(chunk => chunk.metadata.source_kind === "PDF_TEXT_LAYER");
      $("citationChunk").innerHTML += citationChunks.map(chunk => `<option value="${escapeHtml(chunk.id)}">${escapeHtml(chunk.locator)}</option>`).join("");
      parseState.textContent = `RAG 색인 완료 · ${run.page_count} page · ${run.chunk_count} chunk · receipt ${run.receipt_sha256.slice(0, 16)}…`;
      message(`원문 SHA256 ${artifact.sha256.slice(0, 16)}…와 ${run.chunk_count}개 RAG 청크를 저장했습니다.`, true);
    } catch (parseError) {
      parseState.className = "notice amber";
      parseState.textContent = `원본은 보존됐지만 자동 파싱은 완료되지 않았습니다: ${parseError.message}`;
      message(parseError.message);
    }
  } catch (error) {
    parseState.className = "notice amber";
    parseState.textContent = error.message;
    message(error.message);
  }
});

$("evidenceForm").addEventListener("submit", async event => {
  event.preventDefault();
  const submittedForm = event.currentTarget;
  const form = new FormData(submittedForm);
  const body = Object.fromEntries(form.entries());
  body.scope = body.kind === "OBSERVATION" ? {unit: body.scope_unit, configuration: body.scope_configuration, run: body.scope_run} : {};
  delete body.scope_unit;
  delete body.scope_configuration;
  delete body.scope_run;
  const chunkId = $("citationChunk").value;
  const coordinates = ["page_start", "page_end", "line_start", "line_end"];
  body.citation = {document_chunk_id: chunkId || null, cited_edition: body.cited_edition || null,
    source_position: coordinates.every(key => body[key]) ? Object.fromEntries(coordinates.map(key => [key, Number(body[key])])) : null};
  for (const field of ["cited_edition", ...coordinates]) delete body[field];
  body.provenance = {created_in: "LOCAL_INTERNAL_UI", basis: "USER_CONFIRMED_EXCERPT"};
  try {
    const created = await api(`/api/v1/projects/${state.project.id}/evidence`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(body)});
    state.evidence = await api(`/api/v1/projects/${state.project.id}/evidence`);
    state.selectedEvidenceIds = [...new Set([...state.selectedEvidenceIds, created.id])];
    renderEvidence(); renderOverview(); renderGates(); submittedForm.hidden = true;
    $("uploadForm").reset();
    $("artifactDialog").close();
    const verified = created.source_verification?.status === "VALID" && created.source_verification?.freshness === "CURRENT";
    message(`Evidence 저장 · ${verified ? "원문 텍스트·위치 일치 (의미·적용성 별도 검토)" : `원문 대조 미완료: ${created.source_verification?.reason_code || "UNRESOLVED"}`}`, verified);
    await openEvidenceDialog(created.id);
  } catch (error) { message(error.message); }
});

async function saveRequirementPurpose(button) {
  try {
    await api(`/api/v1/requirements/${button.dataset.saveRequirementPurpose}/purpose`, {
      method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({review_purpose: $("requirementPurpose").value, expected_version: Number(button.dataset.version)})
    });
    $("requirementDialog").close();
    await loadAll();
    message("명시된 목적을 저장했습니다. 변경된 연결 Claim은 새 revision에서 다시 검토하세요.", true);
  } catch (error) { message(error.message); }
}

async function saveWorkspaceClaimPurpose() {
  const claim = selectedWorkspaceClaim();
  if (!claim) return;
  const question = $("workspaceQuestion")?.value.trim() || claim.question;
  const review_purpose = $("workspacePurpose")?.value || claim.review_purpose || "UNSPECIFIED";
  if (question === claim.question && review_purpose === claim.review_purpose) return message("질문과 목적에 변경이 없습니다.", true);
  try {
    await api(`/api/v1/claims/${claim.id}`, {
      method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({question, scope: claim.scope, review_purpose, expected_version: claim.version})
    });
    await loadAll();
    message("질문과 목적을 새 Claim revision으로 저장했습니다. 이전 검토는 STALE로 보존합니다.", true);
  } catch (error) { message(error.message); }
}

async function runWorkspaceReview() {
  let claim = selectedWorkspaceClaim();
  if (!claim) return message("BM1 검토에 사용할 Claim이 없습니다.");
  const question = $("workspaceQuestion")?.value.trim() || claim.question;
  try {
    const reviewPurpose = $("workspacePurpose")?.value || claim.review_purpose || "UNSPECIFIED";
    if (question !== claim.question || reviewPurpose !== claim.review_purpose) {
      claim = await api(`/api/v1/claims/${claim.id}`, {
        method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"},
        body: JSON.stringify({question, scope: claim.scope, review_purpose: reviewPurpose, expected_version: claim.version})
      });
      state.claims = state.claims.map(item => item.id === claim.id ? claim : item);
    }
    const retrieval = activeRetrieval();
    const body = {claim_id: claim.id, evidence_ids: state.selectedEvidenceIds, retrieval_run_id: retrieval?.run.id || null, mode: state.workspaceReviewMode};
    const result = await api(`/api/v1/projects/${state.project.id}/reviews`, {
      method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID()}, body: JSON.stringify(body)
    });
    state.job = {id: result.job_id};
    message(`ReviewJob ${result.job_id}을 ${body.mode}로 요청했습니다.`, true);
    await loadJobsAndRequests();
    pollJob();
  } catch (error) { message(error.message); }
}

async function pollJob() {
  clearTimeout(state.timer);
  try {
    const result = await api(`/api/v1/jobs/${state.job.id}`); state.job = result.job; state.jobDetail = result;
    if (state.quickDemo.jobId === result.job.id) state.quickDemo.detail = result;
    renderWorkspace(); renderJobs(); renderRequests(); renderGates(); renderClosure(); renderQuickDemo();
    if (["QUEUED","DISPATCHING","RUNNING","OUTPUT_RECEIVED","VALIDATING"].includes(result.job.status)) {
      state.timer = setTimeout(pollJob, 1000);
    } else {
      await loadJobsAndRequests();
    }
  } catch (error) { message(error.message); }
}

$("reviewDecisionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    let edited_draft = null;
    if (values.edited_draft.trim()) edited_draft = JSON.parse(values.edited_draft);
    const body = {disposition: values.disposition, expected_job_version: Number(values.expected_job_version), note: values.note || null, edited_draft};
    await api(`/api/v1/reviews/${values.job_id}/decisions`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(body)});
    $("reviewDecisionDialog").close();
    state.job = {id: values.job_id};
    message("사람 결정이 모델 원출력과 별도 레코드로 저장되었습니다.", true); await pollJob();
  } catch (error) { message(error instanceof SyntaxError ? "수정 초안은 올바른 JSON이어야 합니다." : error.message); }
});

async function openStoredJob(jobId) {
  state.job = {id: jobId};
  await pollJob();
  if ($("blackboardDialog").open) $("blackboardDialog").close();
}

async function handleEvidenceRequest(button) {
  const requestId = button.dataset.requestId;
  const expected_version = Number(button.dataset.version);
  try {
    if (button.dataset.requestAction === "submit") {
      const select = document.querySelector(`.requestEvidence[data-request-id="${requestId}"]`);
      await api(`/api/v1/evidence-requests/${requestId}/submission`, {
        method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"},
        body: JSON.stringify({evidence_id: select.value, expected_version})
      });
      message("자료를 RECEIVED로 기록했습니다. 검토자 수용은 아직 별도입니다.", true);
    } else {
      await api(`/api/v1/evidence-requests/${requestId}/decision`, {
        method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"},
        body: JSON.stringify({disposition: button.dataset.requestAction, expected_version, note: "로컬 MVP 화면 결정"})
      });
      message(`자료 요청을 ${button.dataset.requestAction}로 기록했습니다.`, true);
    }
    await loadJobsAndRequests();
    if (state.job) await pollJob();
  } catch (error) { message(error.message); }
}

async function exportJobReport(jobId) {
  try {
    const report = await api(`/api/v1/jobs/${jobId}/reports`, {method: "POST", headers: csrfHeaders});
    message(`보고서 ${report.sha256}를 저장했습니다.`, true);
    state.job = {id: jobId};
    await pollJob();
  } catch (error) { message(error.message); }
}

async function loadAudit() {
  if (!state.project) return;
  try {
    state.auditData = await api(`/api/v1/projects/${state.project.id}/audit-view`);
    renderAudit();
  } catch (error) { message(error.message); }
}

function auditEventText(row) {
  const labels = {
    CREATE_CONFIGURATION_CHANGE: "형상 변경 요청을 등록했습니다.",
    APPLY_CONFIGURATION_CHANGE: "CCB 결정으로 새 기준점을 적용했습니다.",
    REJECT_CONFIGURATION_CHANGE: "CCB에서 형상 변경 요청을 기각했습니다.",
    ASSESS_DATA_QUALITY: "현재 범위의 데이터 품질 판단을 기록했습니다.",
    CLOSE_VERIFICATION: "권한자가 검증 종결을 기록했습니다.",
    GATE_DECISION: "기술검토회의 결과를 기록했습니다.",
    PHASE_TRANSITION: "사업 단계 진입 결정을 기록했습니다.",
    UPDATE_PROFILE: "프로젝트 개발 프로파일을 변경했습니다.",
    UPLOAD: "원문 Artifact bytes와 hash를 저장했습니다.",
    EXPORT: "검토 snapshot 보고서를 생성했습니다.",
    DECIDE: "담당자 결정을 별도 레코드로 저장했습니다.",
    SUBMIT: "자료 요청에 Evidence를 제출했습니다.",
    UPDATE: "version 기반 업무 객체 변경을 저장했습니다.",
    UPSERT: "프로젝트 채택 문서 정보를 저장했습니다.",
    CREATE: "새 업무 객체를 생성했습니다.",
    SEED: "재실행 가능한 개발 seed를 확인했습니다."
  };
  return labels[row.action] || `${row.object_type}에 ${row.action} 이벤트를 기록했습니다.`;
}

function auditFilteredEvents() {
  const query = state.auditFilter.trim().toLowerCase();
  const events = state.auditData.events || [];
  if (!query) return events;
  return events.filter(row => [row.action, row.object_type, row.object_id, row.actor, auditEventText(row)].join(" ").toLowerCase().includes(query));
}

function renderAuditTimeline() {
  const root = $("auditTimeline");
  if (!root) return;
  const rows = auditFilteredEvents();
  const openEventIds = new Set(state.auditOpenEventIds);
  root.innerHTML = rows.map(row => {
    const eventId = String(row.id);
    const detail = {
      event_id: row.id,
      action: row.action,
      actor: row.actor,
      object_type: row.object_type,
      object_id: row.object_id,
      created_at: row.created_at,
      before_version: row.before_version,
      payload_sha256: row.payload_hash,
    };
    return `<div class="timeline-item"><div class="time">${new Date(row.created_at).toLocaleString("ko-KR", {hour12: false})}</div><div class="event"><div class="buttons"><span class="pill info">${escapeHtml(row.action)}</span><span class="tiny muted">event ${escapeHtml(eventId)}</span></div><p style="margin-top:5px">${escapeHtml(auditEventText(row))}</p><small>${escapeHtml(row.actor)} / ${escapeHtml(row.object_type)} / ${escapeHtml(row.object_id)}</small><details data-audit-event-id="${escapeHtml(eventId)}"${openEventIds.has(eventId) ? " open" : ""}><summary data-audit-event-summary>기록 상세</summary><pre>${escapeHtml(JSON.stringify(detail, null, 2))}</pre></details></div></div>`;
  }).join("") || '<div class="empty">해당하는 이력이 없습니다.</div>';
  const count = $("auditVisibleCount");
  if (count) count.textContent = `${rows.length} / ${(state.auditData.events || []).length}개 이벤트`;
}

function renderAudit() {
  const root = $("auditContent");
  if (!root || !state.project) return;
  const summary = state.auditData.summary || {};
  const reports = state.auditData.reports || [];
  const reportRows = reports.length ? reports.map(report => `<article class="task"><span class="task-index">${icon("log")}</span><div class="grow"><h4>${escapeHtml(report.claim_display_id)} / ${escapeHtml(report.filename)}</h4><p>${escapeHtml(report.content_type)} · ${report.byte_size} bytes<br><code>${escapeHtml(report.sha256)}</code></p><small class="muted">${escapeHtml(report.created_by)} · ${new Date(report.created_at).toLocaleString()} · ${escapeHtml(report.job_status)} / ${escapeHtml(report.job_freshness)}</small></div><a class="btn small" href="/api/v1/reports/${report.id}/download" download>파일 저장</a></article>`).join("") : '<div class="empty">완료된 BM1 Job에서 보고서를 만들면 작업 파일이 여기에 표시됩니다.</div>';
  root.innerHTML = `<div class="pagehead"><div><div class="eyebrow">AUDIT &amp; EXPORT</div><h1>실행 이력과 작업 파일</h1><p class="subtitle">입력 스냅샷, 모델 결과와 담당자 결정을 같은 실행 기록으로 조회합니다.</p></div><div class="buttons"><button class="btn" data-open-blackboard>${icon("layers")}Blackboard</button><a class="btn primary" href="/api/v1/projects/${state.project.id}/audit-export" download>${icon("down")}작업 JSON 저장</a></div></div>
  <div class="grid3"><section class="card"><div class="cardhead"><div><h3>실행 스냅샷</h3><p>프로파일과 근거 버전</p></div></div><div class="cardbody"><h1>${summary.execution_snapshots || 0}</h1><p class="tiny muted">질문, 범위, 포함 근거와 입력 hash</p></div></section><section class="card"><div class="cardhead"><div><h3>계산 작업</h3><p>조건과 산출물</p></div></div><div class="cardbody"><h1>${summary.model_runs || 0}</h1><p class="tiny muted">ModelRun 원출력과 계약 검증 결과</p></div></section><section class="card"><div class="cardhead"><div><h3>담당자 기록</h3><p>검토와 승인</p></div></div><div class="cardbody"><h1>${summary.human_records || 0}</h1><p class="tiny muted">역할, 적용범위, 의견과 결정</p></div></section></div><div class="space"></div>
  <div class="toolbar"><input id="auditSearch" aria-label="이력 검색" placeholder="이벤트 또는 내용 검색" value="${escapeHtml(state.auditFilter)}"><div class="buttons"><button class="btn" disabled title="DEMO 격리 import 계약은 아직 구현되지 않았습니다.">${icon("upload")}작업 JSON 불러오기</button><button class="btn danger" disabled title="서버 데이터의 파괴적 초기화는 제품 UI에서 제공하지 않습니다.">시연 초기화</button></div></div>
  <section class="card"><div class="cardhead"><div><h3>Audit Trail</h3><p id="auditVisibleCount">${(state.auditData.events || []).length}개 이벤트 / PostgreSQL 추가 기록</p></div><span class="pill info">project v${state.project.version}</span></div><div id="auditTimeline" class="cardbody timeline"></div></section><div class="space"></div>
  <section class="card"><div class="cardhead"><div><h3>작업 파일</h3><p>서버가 생성하고 SHA256을 기록한 보고서</p></div><span class="pill">${summary.report_exports || 0} files</span></div><div class="cardbody stack">${reportRows}</div></section><div class="space"></div>
  <div class="notice blue">역할과 접근 권한은 서버 session과 project membership에서 검사합니다. JSON은 현재 PostgreSQL 기록의 읽기 전용 감사 projection이며, 업무 상태를 덮어쓰는 import 파일이나 LIVE 완료 증거가 아닙니다.</div>`;
  renderAuditTimeline();
}

function escapeHtml(value) { const node = document.createElement("span"); node.textContent = value ?? ""; return node.innerHTML; }

$("phaseRail").addEventListener("click", event => {
  const phase = event.target.closest(".phase");
  if (!phase) return;
  const index = Number(phase.dataset.phase);
  document.querySelectorAll("#phaseRail .phase").forEach(node => node.classList.toggle("active", node === phase));
  $("phaseTitle").textContent = phaseDetails[index][0];
  $("phaseDescription").textContent = phaseDetails[index][1];
  $("phaseGates").innerHTML = phaseDetails[index][2].map(label => `<button class="btn small">${label}</button>`).join("");
});

$("phaseGates").addEventListener("click", event => {
  if (event.target.closest("button")) message("회의별 공식 조건은 기술검토회의 화면에서 현재 채택 문서와 연결합니다.", true);
});

$("openTour").addEventListener("click", () => $("tour").hidden = false);
$("closeTour").addEventListener("click", () => $("tour").hidden = true);
$("autoDemoStart").addEventListener("click", openAutoDemoModeDialog);
$("autoDemoReplayStart").addEventListener("click", () => startAutoDemo("REPLAY"));
$("autoDemoLiveStart").addEventListener("click", () => startAutoDemo("LIVE"));
$("autoDemoStatusRefresh").addEventListener("click", openAutoDemoModeDialog);
$("setupDemoSave").addEventListener("click", () => message("상세 시연이 이 단계의 저장을 한 번만 실행합니다. 진행 상태는 오른쪽 패널에서 확인하세요.", true));
$("blackboardObserverOpen").addEventListener("click", openBlackboardObserver);
$("autoDemoObserverOpen").addEventListener("click", openBlackboardObserver);
$("autoDemoStop").addEventListener("click", stopAutoDemo);
$("qwenTraceContinue").addEventListener("click", async () => {
  if ($("qwenTraceDialog").open) $("qwenTraceDialog").close();
  if (state.autoDemo.active) {
    await activateAutoDemoStep(state.autoDemo.step + 1);
    return;
  }
  await openBlackboardDialog();
});
$("autoDemoPrev").addEventListener("click", () => activateAutoDemoStep(Math.max(0, state.autoDemo.step - 1)));
$("autoDemoNext").addEventListener("click", () => activateAutoDemoStep(state.autoDemo.step + 1));
$("autoDemoToggle").addEventListener("click", () => {
  if (state.autoDemo.step >= autoDemoSteps.length) return startAutoDemo(state.autoDemo.mode);
  state.autoDemo.playing = !state.autoDemo.playing;
  renderAutoDemoPanel(state.autoDemo.step);
  scheduleAutoDemo();
});
$("newProject").addEventListener("click", () => $("projectDialog").showModal());
$("closeProjectDialog").addEventListener("click", () => $("projectDialog").close());
$("cancelProject").addEventListener("click", () => $("projectDialog").close());

$("projectForm").addEventListener("submit", async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.currentTarget).entries());
  body.mode = state.status?.mode === "DEMO" ? "DEMO" : "LIVE";
  try {
    state.project = await api("/api/v1/projects", {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(body)});
    $("projectDialog").close();
    await loadAll();
    message(`${state.project.display_id} 프로젝트를 서버에 생성했습니다.`, true);
  } catch (error) { message(error.message); }
});

$("runpodConnectionForm").addEventListener("submit", async event => {
  event.preventDefault();
  if (state.runpodSaving || state.runpodApplying) return;
  state.runpodSaving = true;
  $("runpodSaveButton").disabled = true;
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/projects/${state.project.id}/runpod-connection`, {
      method: "PUT",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({host: values.host.trim(), port: Number(values.port)})
    });
    message("RunPod HostName과 외부 SSH 포트를 로컬 설정에 저장했습니다.", true);
    const hostKeyState = await scanRunpodHostKey();
    if (hostKeyState === "HOST_KEY_VERIFIED") await applySavedRunpodConnection();
  } catch (error) { showRunpodState(error.message, "amber"); }
  finally {
    state.runpodSaving = false;
    $("runpodSaveButton").disabled = false;
    await refreshRunpodRuntime();
  }
});

$("documentForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  const documentCode = values.document_code;
  delete values.document_code;
  try {
    await api(`/api/v1/projects/${state.project.id}/documents/${encodeURIComponent(documentCode)}`, {
      method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(values)
    });
    $("documentDialog").close();
    state.profileData = await api(`/api/v1/projects/${state.project.id}/profile`);
    renderProfile();
    message(`${documentCode} 등록 정보를 서버에 저장했습니다.`, true);
  } catch (error) { message(error.message); }
});

$("tailoringForm").addEventListener("submit", async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/projects/${state.project.id}/tailoring`, {
      method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(body)
    });
    $("tailoringDialog").close();
    state.profileData = await api(`/api/v1/projects/${state.project.id}/profile`);
    renderProfile();
    event.currentTarget.reset();
    event.currentTarget.elements.profile.value = state.profilePreview;
    message("테일러링 검토 후보를 서버에 저장했습니다.", true);
  } catch (error) { message(error.message); }
});

$("gateDecisionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/gates/${values.gate_id}/decisions`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        disposition: "APPROVED",
        note: values.note,
        expected_gate_version: Number(values.expected_gate_version),
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("gateDecisionDialog").close();
    await refreshGateData();
    message("기술검토 결과를 단계 전환과 분리된 승인 기록으로 저장했습니다.", true);
  } catch (error) { message(error.message); }
});

$("transitionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const result = await api(`/api/v1/projects/${state.project.id}/transitions`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        disposition: values.disposition,
        note: values.note,
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("transitionDialog").close();
    state.project = result.project;
    await loadAll();
    message(values.disposition === "GO" ? "다음 사업 단계 진입 결정을 저장했습니다." : "단계 진입 HOLD와 남은 조건을 저장했습니다.", true);
  } catch (error) { message(error.message); }
});

$("qualityAssessmentForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/claims/${values.claim_id}/quality-assessments`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        quality_status: values.quality_status,
        note: values.note,
        expected_claim_version: Number(values.expected_claim_version),
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("qualityAssessmentDialog").close();
    await loadAll();
    message("데이터 품질 판단을 출력 검증과 별도 기록으로 저장했습니다.", true);
  } catch (error) { message(error.message); }
});

$("closureDecisionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/claims/${values.claim_id}/closures`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        result: values.result,
        closure_basis: values.closure_basis,
        note: values.note,
        expected_claim_version: Number(values.expected_claim_version),
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("closureDecisionDialog").close();
    await loadAll();
    message("권한자의 검증 종결을 현재 Claim revision과 scope에 기록했습니다.", true);
  } catch (error) { message(error.message); }
});

$("changeRequestForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api(`/api/v1/projects/${state.project.id}/changes`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        to_baseline: values.to_baseline,
        to_configuration: values.to_configuration,
        to_test_run: values.to_test_run,
        reason: values.reason,
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("changeRequestDialog").close();
    await loadAll();
    message("형상 변경 요청을 DRAFT로 저장했습니다. 기준점은 CCB 결정 전까지 바뀌지 않습니다.", true);
  } catch (error) { message(error.message); }
});

$("changeDecisionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const result = await api(`/api/v1/changes/${values.change_id}/decision`, {
      method: "POST",
      headers: {...csrfHeaders, "Content-Type": "application/json"},
      body: JSON.stringify({
        disposition: values.disposition,
        note: values.note,
        expected_change_version: Number(values.expected_change_version),
        expected_project_version: Number(values.expected_project_version)
      })
    });
    $("changeDecisionDialog").close();
    await loadAll();
    const detail = values.disposition === "APPLIED"
      ? `새 기준점을 적용하고 ReviewJob ${result.invalidated_review_jobs}건을 STALE로 전환했습니다.`
      : "변경 요청을 기각하고 현재 기준점을 유지했습니다.";
    message(detail, true);
  } catch (error) { message(error.message); }
});

renderShell();
startSession(false);
setInterval(refreshStatus, 10000);
setInterval(publishAutoDemoObserverState, 2000);
