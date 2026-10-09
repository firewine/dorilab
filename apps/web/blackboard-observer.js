const CHANNEL_NAME = "dorilab-blackboard-observer-v1";
const SCHEMA = "dorilab.demo.observer.v1";
const POLL_MS = 1500;
const SIGNAL_TIMEOUT_MS = 6500;
const $ = id => document.getElementById(id);

const query = new URLSearchParams(window.location.search);
const state = {
  projectId: query.get("project_id"),
  projectDisplayId: null,
  runKey: query.get("run_key"),
  jobId: query.get("job_id"),
  mode: query.get("mode"),
  active: false,
  playing: false,
  stepIndex: 0,
  stepCount: 9,
  stepTitle: query.get("job_id") ? "저장된 실행 · 시연창 연결 대기" : "자동 시연 시작 전",
  executionStatus: "IDLE",
  error: null,
  board: null,
  job: null,
  apiError: null,
  lastApiAt: 0,
  lastSignalAt: 0,
  lastSentAt: 0,
  sourceInstanceId: query.get("source_id"),
  lastSequence: 0,
  signalError: null,
  signalPollBusy: false,
  seenMessages: new Set(),
  itemFingerprints: new Map(),
  highlightUntil: new Map(),
  pollBusy: false,
};

const channel = "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL_NAME) : null;

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function safeJson(value) {
  return JSON.stringify(value ?? null, null, 2);
}

function formatTime(value) {
  if (!value) return "시각 없음";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("ko-KR", {hour12: false});
}

function shortId(value) {
  if (!value) return "—";
  const text = String(value);
  return text.length > 16 ? `${text.slice(0, 8)}…${text.slice(-5)}` : text;
}

function resetRunView() {
  state.board = null;
  state.job = null;
  state.apiError = null;
  state.lastApiAt = 0;
  state.itemFingerprints.clear();
  state.highlightUntil.clear();
}

function persistIdentity() {
  const params = new URLSearchParams();
  if (state.projectId) params.set("project_id", state.projectId);
  if (state.sourceInstanceId) params.set("source_id", state.sourceInstanceId);
  if (state.runKey) params.set("run_key", state.runKey);
  if (state.jobId) params.set("job_id", state.jobId);
  if (state.mode) params.set("mode", state.mode);
  history.replaceState(null, "", `${window.location.pathname}${params.size ? `?${params}` : ""}`);
}

function acceptDemoState(message, fromOpener = false) {
  if (message?.schema !== SCHEMA || message?.type !== "DEMO_STATE") return;
  if (!state.sourceInstanceId && !fromOpener) return;
  if (state.sourceInstanceId && message.source_instance_id !== state.sourceInstanceId) return;
  if (!message.project_id) return;
  const sequence = Number(message.sequence);
  if (!Number.isSafeInteger(sequence) || sequence <= state.lastSequence) return;
  const sentAt = Date.parse(message.sent_at || "");
  if (!Number.isFinite(sentAt)) return;
  const messageId = `${message.source_instance_id}:${sequence}`;
  if (state.seenMessages.has(messageId)) return;
  state.seenMessages.add(messageId);
  if (state.seenMessages.size > 500) state.seenMessages = new Set([messageId]);

  const runChanged = state.runKey !== (message.run_key || null);
  const projectChanged = Boolean(state.projectId && message.project_id && state.projectId !== message.project_id);
  const jobChanged = state.jobId !== (message.job_id || null);
  if (runChanged || projectChanged || jobChanged) resetRunView();

  state.sourceInstanceId = message.source_instance_id || state.sourceInstanceId;
  state.lastSequence = sequence;
  state.lastSentAt = sentAt;
  state.lastSignalAt = Math.min(sentAt, Date.now());
  state.signalError = null;
  state.projectId = message.project_id || state.projectId;
  state.projectDisplayId = message.project_display_id || state.projectDisplayId;
  state.runKey = message.run_key || null;
  state.jobId = message.job_id || null;
  state.mode = message.mode || state.mode;
  state.active = Boolean(message.active);
  state.playing = Boolean(message.playing);
  state.stepIndex = Number(message.step_index || 0);
  state.stepCount = Number(message.step_count || 9);
  state.stepTitle = message.step_title || "자동 시연 시작 전";
  state.executionStatus = message.execution_status || "IDLE";
  state.error = message.error || null;
  persistIdentity();
  render();
  if (state.jobId) pollProjection();
}

function sendHello() {
  const message = {type: "OBSERVER_HELLO", schema: SCHEMA, target_source_instance_id: state.sourceInstanceId, sent_at: new Date().toISOString()};
  channel?.postMessage(message);
  if (window.opener && !window.opener.closed) window.opener.postMessage(message, window.location.origin);
}

channel?.addEventListener("message", event => acceptDemoState(event.data));
window.addEventListener("message", event => {
  if (event.origin !== window.location.origin || event.source !== window.opener) return;
  const message = event.data;
  if (message?.type === "OBSERVER_SOURCE" && message.schema === SCHEMA
      && message.previous_source_instance_id === state.sourceInstanceId) {
    state.sourceInstanceId = message.source_instance_id;
    state.lastSequence = 0;
    state.lastSentAt = 0;
    state.seenMessages.clear();
    resetRunView();
    persistIdentity();
    return;
  }
  acceptDemoState(message, true);
});

async function getJson(path) {
  const response = await fetch(path, {credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(5000)});
  const text = await response.text();
  let body;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!response.ok) {
    const error = new Error(typeof body?.detail === "string" ? body.detail : `${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return body;
}

async function pollDemoSignal() {
  if (state.signalPollBusy || !state.projectId || !state.sourceInstanceId) return;
  state.signalPollBusy = true;
  const projectId = state.projectId;
  const sourceId = state.sourceInstanceId;
  try {
    const signal = await getJson(`/api/v1/projects/${encodeURIComponent(projectId)}/demo-observer/sessions/${encodeURIComponent(sourceId)}`);
    if (projectId !== state.projectId || sourceId !== state.sourceInstanceId) return;
    state.signalError = null;
    acceptDemoState(signal);
  } catch (error) {
    if (projectId !== state.projectId || sourceId !== state.sourceInstanceId) return;
    state.signalError = error.status === 404 ? null : error.message;
    render();
  } finally {
    state.signalPollBusy = false;
  }
}

function projectionIdentity() {
  return `${state.projectId}:${state.runKey}:${state.jobId}`;
}

async function pollProjection() {
  if (state.pollBusy || !state.projectId || !state.jobId) return;
  state.pollBusy = true;
  const requestIdentity = projectionIdentity();
  const projectId = state.projectId;
  const jobId = state.jobId;
  try {
    const [board, job] = await Promise.all([
      getJson(`/api/v1/projects/${encodeURIComponent(projectId)}/blackboard`),
      getJson(`/api/v1/jobs/${encodeURIComponent(jobId)}`),
    ]);
    if (requestIdentity !== projectionIdentity()) return;
    if (String(job?.job?.id || "") !== String(jobId)) throw new Error("JOB_ID_MISMATCH");
    state.board = board;
    state.job = job;
    state.apiError = null;
    state.lastApiAt = Date.now();
    render();
  } catch (error) {
    if (requestIdentity !== projectionIdentity()) return;
    state.apiError = error.message;
    render();
  } finally {
    state.pollBusy = false;
  }
}

function selectRunData() {
  const board = state.board || {};
  const jobId = String(state.jobId || "");
  const byCreatedAt = (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0);
  const contributions = (board.contributions || []).filter(item => jobId && String(item.source_job_id || "") === jobId).sort(byCreatedAt);
  const workItems = (board.work_items || []).filter(item => jobId && String(item.source_job_id || "") === jobId).sort(byCreatedAt);
  const dependencies = (board.dependencies || []).filter(item => jobId && String(item.source_job_id || "") === jobId).sort(byCreatedAt);
  const orchestrationRuns = (board.orchestration_runs || []).filter(item => String(item.job_id || "") === jobId);
  const relatedIds = new Set([
    ...contributions.map(item => String(item.id)),
    ...workItems.map(item => String(item.id)),
    ...orchestrationRuns.map(item => String(item.id)),
  ]);
  const events = (board.events || []).filter(event => relatedIds.has(String(event.object_id)));
  return {contributions, workItems, dependencies, orchestrationRuns, events};
}

function itemFingerprint(kind, item) {
  return safeJson({kind, id: item.id, version: item.version, status: item.status, updated_at: item.updated_at, content: item.content, purpose: item.purpose, current_node: item.current_node, checkpoint_seq: item.checkpoint_seq, event_type: item.event_type, result_version: item.result_version});
}

function updateHighlight(kind, item) {
  const key = `${kind}:${item.id}`;
  const next = itemFingerprint(kind, item);
  const previous = state.itemFingerprints.get(key);
  if (previous !== next) {
    state.itemFingerprints.set(key, next);
    state.highlightUntil.set(key, Date.now() + 2600);
    setTimeout(render, 2650);
  }
  return (state.highlightUntil.get(key) || 0) > Date.now() ? "is-updated" : "";
}

function badge(value, style = "info") {
  return `<span class="badge ${style}">${escapeHtml(value || "—")}</span>`;
}

function actorText(item) {
  return `${item.actor_type || item.created_by_type || "SYSTEM"} · ${item.actor_id || item.created_by || "unknown"}`;
}

function contentSummary(content) {
  if (!content || typeof content !== "object") return "저장된 내용 요약이 없습니다.";
  const action = content.action ? `${content.action}` : null;
  const reason = content.reason || content.reason_code || content.summary || content.note;
  return [action, reason].filter(Boolean).join(" · ") || "구조화된 제안이 저장되었습니다.";
}

function contributionCard(item) {
  const changed = updateHighlight("contribution", item);
  return `<article class="record-card ${changed}">
    <div class="record-top"><div>${badge(item.contribution_type, "info")} ${badge(item.status, item.status === "PROPOSED" ? "waiting" : "ok")}</div><small>${escapeHtml(item.claim_display_id || item.target_object_type || "대상")}</small></div>
    <h3>${escapeHtml(item.content?.action || item.contribution_type || "검토 제안")}</h3>
    <p>${escapeHtml(contentSummary(item.content))}</p>
    <div class="record-meta"><span>기록: ${escapeHtml(actorText(item))}</span><span>${escapeHtml(formatTime(item.updated_at || item.created_at))}</span></div>
    <details class="raw-details" data-observer-detail="contribution:${escapeHtml(item.id)}"><summary>긴 값과 원본 JSON</summary><pre>${escapeHtml(safeJson(item))}</pre></details>
  </article>`;
}

function workItemCard(item) {
  const changed = updateHighlight("work-item", item);
  return `<article class="record-card ${changed}">
    <div class="record-top"><div>${badge(item.work_type, "info")} ${badge(item.status, item.status === "COMPLETED" ? "ok" : "waiting")}</div><small>다음 담당: ${escapeHtml(item.assigned_role || "미지정")}</small></div>
    <h3>${escapeHtml(item.title || "공용 작업")}</h3>
    <p>${escapeHtml(item.purpose || "저장된 작업 목적이 없습니다.")}</p>
    <div class="record-meta"><span>생성: ${escapeHtml(actorText(item))}</span><span>${escapeHtml(formatTime(item.updated_at || item.created_at))}</span></div>
    <details class="raw-details" data-observer-detail="work-item:${escapeHtml(item.id)}"><summary>긴 값과 원본 JSON</summary><pre>${escapeHtml(safeJson(item))}</pre></details>
  </article>`;
}

function dependencyCard(item) {
  const changed = updateHighlight("dependency", item);
  return `<article class="link-card ${changed}">
    <div class="record-top">${badge(item.relationship, "info")}<small>${escapeHtml(formatTime(item.created_at))}</small></div>
    <div class="link-route"><span class="link-node">${escapeHtml(item.upstream_object_type)}<br>${escapeHtml(shortId(item.upstream_object_id))}</span><span class="link-arrow">→</span><span class="link-node">${escapeHtml(item.downstream_object_type)}<br>${escapeHtml(shortId(item.downstream_object_id))}</span></div>
    <p>연결 기록: ${escapeHtml(item.created_by_type || "SYSTEM")} · ${escapeHtml(item.created_by || "unknown")}</p>
  </article>`;
}

function orchestrationCards(data) {
  const projection = state.job?.orchestration;
  if (!projection?.nodes?.length) return '<div class="empty-card">현재 Job에 orchestration projection이 없습니다.</div>';
  return projection.nodes.map(node => {
    const status = node.status || "PENDING";
    const style = ["COMPLETED", "PROJECTED_COMPLETED"].includes(status) ? "done" : ["RUNNING", "READY", "WAITING"].includes(status) ? "active" : status === "FAILED" ? "failed" : "";
    const attempt = node.attempt || {};
    const changed = updateHighlight("node", {id: node.key, status, updated_at: attempt.finished_at || attempt.started_at});
    return `<article class="timeline-card ${style} ${changed}"><span class="timeline-dot"></span><div><b>${escapeHtml(node.label || node.key)} · ${escapeHtml(status)}</b><small>${escapeHtml(node.description || "")}</small>${attempt.worker_id ? `<small>worker ${escapeHtml(attempt.worker_id)} · ${escapeHtml(formatTime(attempt.finished_at || attempt.started_at))}</small>` : ""}</div></article>`;
  }).join("");
}

function eventCards(events) {
  if (!events.length) return '<div class="empty-card">현재 실행 객체와 연결된 BoardEvent가 없습니다.</div>';
  return [...events].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)).map(item => {
    const changed = updateHighlight("event", item);
    return `<article class="timeline-card done ${changed}"><span class="timeline-dot"></span><div><b>${escapeHtml(item.event_type)} · ${escapeHtml(item.object_type)}</b><small>${escapeHtml(actorText(item))} · ${escapeHtml(formatTime(item.created_at))}</small><details class="raw-details" data-observer-detail="event:${escapeHtml(item.id)}"><summary>이벤트 JSON</summary><pre>${escapeHtml(safeJson(item))}</pre></details></div></article>`;
  }).join("");
}

function renderBadges() {
  const mode = state.mode === "LIVE" ? "Local LLM LIVE" : state.mode === "REPLAY" ? "DEMO REPLAY" : "시작 전";
  $("modeBadge").textContent = mode;
  $("modeBadge").className = `badge ${state.mode === "LIVE" ? "live" : state.mode === "REPLAY" ? "replay" : "neutral"}`;
  const disconnected = !state.lastSignalAt || Date.now() - state.lastSignalAt > SIGNAL_TIMEOUT_MS;
  $("signalBadge").textContent = disconnected ? "DISCONNECTED · 시연창 신호 대기" : "시연창 연결됨";
  $("signalBadge").className = `badge ${disconnected ? "waiting" : "ok"}`;
  $("apiBadge").textContent = state.apiError || state.signalError ? "API ERROR" : state.board ? "Blackboard 동기화됨" : "API 대기";
  $("apiBadge").className = `badge ${state.apiError || state.signalError ? "error" : state.board ? "ok" : "neutral"}`;
}

function render() {
  const data = selectRunData();
  const openDetails = new Set([...document.querySelectorAll("details[data-observer-detail][open]")].map(node => node.dataset.observerDetail));
  renderBadges();
  $("stepTitle").textContent = state.stepTitle;
  $("stepCount").textContent = `${state.stepIndex} / ${state.stepCount}`;
  $("executionStatus").textContent = state.executionStatus;
  $("jobId").textContent = state.jobId || "아직 없음";
  $("jobId").title = state.jobId || "";
  $("lastSync").textContent = state.lastApiAt ? formatTime(state.lastApiAt) : "대기";
  $("stepProgress").style.width = `${Math.max(0, Math.min(100, state.stepCount ? state.stepIndex / state.stepCount * 100 : 0))}%`;
  $("sessionSummary").textContent = state.error
    ? `시연 오류: ${state.error}`
    : `${state.projectDisplayId || "프로젝트"} · ${state.mode === "LIVE" ? "실제 Local LLM 실행" : state.mode === "REPLAY" ? "저장 흐름 재현" : "실행 대기"} · run ${shortId(state.runKey)}`;

  const status = $("observerStatus");
  if (state.error) {
    status.textContent = `ERROR · 이번 시연이 멈췄습니다: ${state.error}. 마지막 저장 결과는 유지합니다.`;
    status.className = "status-line state-error";
  } else if (state.apiError || state.signalError) {
    status.textContent = `ERROR · 저장 상태 조회 실패: ${state.apiError || state.signalError}. 자동으로 다시 시도합니다.`;
    status.className = "status-line state-error";
  } else if (!state.jobId) {
    status.textContent = "EMPTY · 현재 실행의 Job을 기다리고 있습니다. 과거 실행 기록은 섞어 표시하지 않습니다.";
    status.className = "status-line state-empty";
  } else if (!state.board) {
    status.textContent = "Blackboard와 Job 상태를 읽는 중입니다.";
    status.className = "status-line state-disconnected";
  } else {
    status.textContent = `현재 Job과 일치: Contribution ${data.contributions.length} · WorkItem ${data.workItems.length} · Dependency ${data.dependencies.length} · Event ${data.events.length}`;
    status.className = "status-line state-ready";
  }

  $("contributionCount").textContent = data.contributions.length;
  $("workItemCount").textContent = data.workItems.length;
  $("dependencyCount").textContent = data.dependencies.length;
  $("eventCount").textContent = data.events.length;
  $("contributionList").innerHTML = data.contributions.length ? data.contributions.map(contributionCard).join("") : '<div class="empty-card">현재 실행에서 기록된 Contribution이 없습니다.</div>';
  $("workItemList").innerHTML = data.workItems.length ? data.workItems.map(workItemCard).join("") : '<div class="empty-card">현재 실행에서 생성된 WorkItem이 없습니다.</div>';
  $("dependencyList").innerHTML = data.dependencies.length ? data.dependencies.map(dependencyCard).join("") : '<div class="empty-card">현재 실행의 연결 기록을 기다리고 있습니다.</div>';
  $("orchestrationList").innerHTML = orchestrationCards(data);
  const run = state.job?.orchestration?.run || data.orchestrationRuns[0];
  $("orchestrationBadge").textContent = run ? `${run.current_node} · ${run.status}` : "대기";
  $("orchestrationBadge").className = `badge ${run?.status === "COMPLETED" ? "ok" : run ? "waiting" : "neutral"}`;
  $("eventList").innerHTML = eventCards(data.events);
  document.querySelectorAll("details[data-observer-detail]").forEach(node => { node.open = openDetails.has(node.dataset.observerDetail); });
  $("rawJson").textContent = safeJson({run_key: state.runKey, job_id: state.jobId, blackboard: data, job: state.job});
}

sendHello();
render();
if (state.jobId) pollProjection();
pollDemoSignal();
setInterval(pollDemoSignal, POLL_MS);
setInterval(() => {
  if (!state.lastSignalAt || Date.now() - state.lastSignalAt > SIGNAL_TIMEOUT_MS) sendHello();
}, 2000);
setInterval(pollProjection, POLL_MS);
setInterval(renderBadges, 1000);
