// Recording walkthrough: ordinary local APIs, one explicit model admission.
// All setup material comes from the named public synthetic fixture.
const setupDemoSteps = [
  {chapter: "1 · 실행 환경", action: "environment", page: "overview", focus: "#setupDemoDialog", title: "로컬 앱과 Local LLM 연결 확인", narration: "로컬 API와 DB, 현재 실행 모드와 인증된 모델 준비 상태를 먼저 확인합니다. 서버 설치나 연결값 변경은 수행하지 않습니다."},
  {chapter: "2 · 새 프로젝트", action: "project-form", page: "overview", focus: "#projectDialog", title: "빈 프로젝트의 이름과 ID 입력", narration: "이번 촬영만의 새 프로젝트를 만듭니다. 기존 프로젝트와 검토 기록은 그대로 남습니다."},
  {chapter: "2 · 새 프로젝트", action: "project-policy", page: "overview", focus: "#projectDialog", title: "개발 체계와 데이터 정책 설정", narration: "KASA 체계를 선택하고 공개 합성 자료만 Local LLM에 보낼 수 있도록 설정합니다. 프로젝트의 자료 성격은 DEMO로 유지합니다."},
  {chapter: "2 · 새 프로젝트", action: "project-save", page: "overview", focus: "#projectDialog", title: "프로젝트를 서버에 저장", narration: "실제 프로젝트 API로 PostgreSQL에 저장하고 서버가 돌려준 프로젝트 ID를 확인합니다."},
  {chapter: "2 · 새 프로젝트", action: "empty-project", page: "overview", focus: "#setupDemoDialog", title: "아직 아무 자료도 없는 상태 확인", narration: "Claim·요구사항·근거·검색·검토가 0건인 새 프로젝트입니다. 이제 한 항목씩 등록합니다."},
  {chapter: "3 · 기준과 검토 대상", action: "profile-preview", page: "profile", focus: "#profileContent .grid3", title: "KASA·ECSS·NASA 체계 비교", narration: "비교 화면을 살펴보고 프로젝트에 지정한 KASA로 돌아옵니다. 미리보기는 공식 채택이나 승인 기록을 만들지 않습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "document-form", page: "profile", focus: "#documentDialog", title: "참조 문서의 판본과 적용 메모 입력", narration: "참조 문서명, 판본, 제품 수준과 적용 메모를 입력합니다. 원문 확인과 기관 기준의 실제 채택은 미확인으로 남깁니다."},
  {chapter: "3 · 기준과 검토 대상", action: "document-save", page: "profile", focus: "#documentDialog", title: "기준 문서 등록 정보 저장", narration: "문서 참조 메타데이터를 실제 서버 기록으로 저장합니다. 이 등록을 공학 승인으로 사용하지 않습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "claim-form", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "BM1이 검토할 질문 작성", narration: "무엇을 검토할지 한 문장으로 지정합니다. 모델은 이 질문과 이후 선택된 근거만 받습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "claim-scope", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "장비·형상·시험 Run 범위 지정", narration: "관측 자료의 unit, configuration, run을 구분해 입력합니다. 범위가 다른 근거를 같은 시험 자료로 사용하지 않습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "claim-save", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "Claim 첫 revision 저장", narration: "질문과 범위를 실제 Claim revision 1로 저장합니다. 아직 검토 결과나 사람 결정은 없습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "requirement-form", page: "requirements", focus: "#setupDemoDialog", title: "요구사항과 검증 방법 연결", narration: "공개 합성 요구사항을 작성하고 방금 만든 Claim과 연결합니다. 공식 표준의 수치나 승인을 생성하지 않습니다."},
  {chapter: "3 · 기준과 검토 대상", action: "requirement-save", page: "requirements", focus: "#setupDemoDialog", title: "요구사항 추적 관계 저장", narration: "새 프로젝트의 요구사항 API로 저장하고 요구사항 → Claim 연결을 확인합니다."},
  {chapter: "4 · 문서와 RAG", action: "source-preview", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "업로드할 문서 원문 읽기", narration: "전력 지도와 열원 위치에 관한 공개 합성 문서의 원문을 먼저 보여줍니다. 정답이나 평가 gold는 포함하지 않습니다."},
  {chapter: "4 · 문서와 RAG", action: "upload-form", page: "workspace", workspaceStep: 0, focus: "#artifactDialog", title: "원문 파일과 사용 범위 설정", narration: "합성 Markdown 파일, 권리 PUBLIC, 판본, 프로젝트 사용과 적용성 정보를 지정합니다. 이 파일의 실제 bytes를 보관합니다."},
  {chapter: "4 · 문서와 RAG", action: "upload-save", page: "workspace", workspaceStep: 0, focus: "#artifactDialog", title: "원문 bytes 업로드와 SHA256 확인", narration: "아직 파싱하지 않고 먼저 원문을 Artifact Store에 저장합니다. 파일 크기와 SHA256은 서버 응답을 표시합니다."},
  {chapter: "4 · 문서와 RAG", action: "parse", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "문서 파싱·청킹·검색 색인 생성", narration: "기존 parser가 실제 문서를 파싱하고 위치와 hash를 가진 청크를 저장합니다. 현재 검색은 PostgreSQL FTS이며 임베딩 벡터 생성은 아닙니다."},
  {chapter: "4 · 문서와 RAG", action: "chunks", page: "workspace", workspaceStep: 0, focus: "#setupDemoDialog", title: "청크와 원문 위치 확인", narration: "실제로 저장된 청크의 본문, section·line 위치와 hash를 확인합니다. 임의의 청크 수나 검색 점수를 만들지 않습니다."},
  {chapter: "4 · 문서와 RAG", action: "search-form", page: "workspace", workspaceStep: 10, focus: "#ragQuery", title: "검토 질문에 맞는 검색어 입력", narration: "문서에서 찾을 소산전력과 열원 위치를 입력하고 최대 선택 청크 수를 지정합니다."},
  {chapter: "4 · 문서와 RAG", action: "search", page: "workspace", workspaceStep: 10, focus: "#workspaceContent .workcols", title: "프로젝트 범위에서 문서 검색", narration: "이 프로젝트의 업로드 문서만 검색합니다. Rights·Edition·Adoption·Applicability를 검사하고 선택과 제외 사유를 보존합니다."},
  {chapter: "4 · 문서와 RAG", action: "selected-chunk", page: "workspace", workspaceStep: 10, focus: "#evidenceDialog", title: "모델에 제공할 근거와 검색 계보", narration: "선택된 실제 문서 청크와 원문 hash, retrieval receipt를 확인합니다. 검색 결과는 사람의 Evidence 수용과 별개입니다."},
  {chapter: "5 · Local LLM과 Blackboard", action: "input-check", page: "workspace", workspaceStep: 10, focus: "#setupDemoDialog", title: "검토 실행 전 입력 경계 확인", narration: "현재 Claim revision과 Scope, 선택된 청크 ID, 자료 성격을 확인합니다. 실행 후 만들어지는 실제 Snapshot은 Local LLM 팝업에서 확인합니다."},
  {chapter: "5 · Local LLM과 Blackboard", page: "workspace", workspaceStep: 10, focus: "#workspaceContent .resultpanel", title: "실제 Local LLM 검토 요청과 원출력", narration: "한 건의 검토를 요청하고 동일 Job을 조회합니다. 실제 입력·출력과 Validator 결과를 보고 사람 검토 지점에서 멈춥니다.", ensureModelRun: true},
  {chapter: "5 · Local LLM과 Blackboard", page: "workspace", focus: "#blackboardDialog", title: "Local LLM 제안과 다음 업무의 저장", narration: "같은 Job에서 저장된 Contribution, WorkItem과 Dependency를 관찰 창과 대조합니다. 다음 업무는 실제 모델 결과에 따라 달라집니다.", showBlackboard: true},
  {chapter: "6 · 사람 검토와 실행 증거", page: "closure", focus: "#closureContent .stategrid", title: "사람 판단과 공식 종결의 경계", narration: "검토 초안과 공식 시험 승인은 별도입니다. 이 시연은 사람 수락·기각·Gate 승인·종결을 자동으로 만들지 않습니다."},
  {chapter: "6 · 사람 검토와 실행 증거", page: "audit", focus: "#auditContent .timeline", title: "처음 등록부터 실행 결과까지 감사 이력", narration: "이번 프로젝트의 등록 기록, Snapshot, 원출력 hash와 validation을 확인합니다. 빈 프로젝트에서 실제로 생긴 기록입니다."},
];

// Recording uses the same local API operations as the forms, exactly once.
// A manual submit while the pointer is demonstrating must not create job #2.
document.addEventListener("submit", event => {
  if (!state.autoDemo?.active || state.autoDemo.step >= autoDemoSteps.length || state.autoDemo.walkthrough !== "SETUP") return;
  if (!["projectForm", "documentForm", "uploadForm", "setupDemoForm"].includes(event.target.id)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

function setupContext() {
  if (!state.autoDemo.setup) throw new Error("상세 시연의 준비 상태가 없습니다.");
  return state.autoDemo.setup;
}

function setupFields(fields) {
  return `<form id="setupDemoForm"><div class="formgrid">${fields.map(([name, label, multiline = false]) => `<div class="field ${multiline ? "full" : ""}"><label for="setup-field-${name}">${escapeHtml(label)}</label>${multiline ? `<textarea id="setup-field-${name}" name="${name}" rows="3"></textarea>` : `<input id="setup-field-${name}" name="${name}">`}</div>`).join("")}</div></form>`;
}

function showSetupDialog(title, explanation, body, receipt = "", saving = false) {
  $("setupDemoTitle").textContent = title;
  $("setupDemoExplanation").textContent = explanation;
  $("setupDemoBody").innerHTML = body;
  $("setupDemoReceipt").textContent = receipt;
  $("setupDemoReceipt").hidden = !receipt;
  $("setupDemoSave").hidden = !saving;
  $("setupDemoSave").disabled = true;
  if (!$("setupDemoDialog").open) $("setupDemoDialog").show();
}

function setupKv(values) {
  return `<dl class="kv">${Object.entries(values).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value ?? "미확인"))}</dd>`).join("")}</dl>`;
}

function setupReceipt(label, value) {
  state.autoDemo.operation = `${label} · ${value}`;
  $("autoDemoOperation").textContent = state.autoDemo.operation;
  $("autoDemoOperation").hidden = false;
}

async function fillSetupField(target, value, runKey, label) {
  if (!target) throw new Error(`시연 입력 필드 없음: ${label}`);
  if (!await pointAutoDemoCursor(target, `입력 · ${label}`, runKey, {click: true})) return;
  target.focus({preventScroll: true});
  if (target.tagName === "SELECT") {
    target.value = String(value);
    await autoDemoWait(500);
  } else {
    const characters = Array.from(String(value));
    const startedAt = performance.now();
    target.value = "";
    while (performance.now() - startedAt < 1300) {
      if (!autoDemoRunIsCurrent(runKey)) return;
      const count = Math.max(1, Math.ceil((performance.now() - startedAt) / 1300 * characters.length));
      target.value = characters.slice(0, count).join("");
      await autoDemoWait(55);
    }
    target.value = String(value);
  }
  if (!autoDemoRunIsCurrent(runKey)) return;
  target.dispatchEvent(new Event("input", {bubbles: true}));
  target.dispatchEvent(new Event("change", {bubbles: true}));
  await autoDemoWait(250);
}

async function fillSetupForm(form, values, runKey) {
  for (const [name, value] of Object.entries(values)) {
    if (!autoDemoRunIsCurrent(runKey)) return;
    await fillSetupField(form.elements.namedItem(name), value, runKey, name);
  }
}

async function setupWriteOnce(key, button, label, runKey, write) {
  const ctx = setupContext();
  if (Object.hasOwn(ctx.saved, key)) {
    setupReceipt("같은 실행의 저장 기록 재표시", label);
    return ctx.saved[key];
  }
  if (ctx.attempted.has(key)) throw new Error("이 저장 요청의 결과가 불명확하거나 실패했습니다. 자동 재전송하지 않습니다. 실행 이력을 확인하고 새 시연을 시작하세요.");
  const originallyDisabled = button?.disabled;
  try {
    if (button) button.disabled = false;
    if (!await pointAutoDemoCursor(button, `클릭 · ${label}`, runKey, {click: true})) return;
    if (button) button.disabled = true;
    ctx.attempted.add(key);
    const result = await write();
    ctx.saved[key] = result;
    if (!autoDemoRunIsCurrent(runKey)) return;
    return result;
  } finally {
    if (button) button.disabled = originallyDisabled;
  }
}

function setupPost(path, body, headers = {}) {
  return api(path, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json", ...headers}, body: JSON.stringify(body)});
}

async function runSetupDemoAction(action, runKey) {
  const ctx = setupContext();
  const f = ctx.fixture;
  const step = autoDemoSteps[state.autoDemo.step];
  const caption = step.narration;
  if (action === "environment") {
    const health = await api("/healthz");
    await refreshStatus();
    if (!autoDemoRunIsCurrent(runKey)) return;
    showSetupDialog(step.title, caption, setupKv({"로컬 API": health.status || "응답 확인", "앱 모드": state.status.mode, "원격 모델": state.status.remote.state, "전송": "SSH tunnel → 원격 loopback", "이번 자료": "공개 합성 DEMO"}));
    setupReceipt("조회", "기존 서버 준비 상태 · 설치/설정 변경 없음");
  }
  if (action.startsWith("project-")) {
    const form = $("projectForm");
    $("projectDialog").classList.add("setup-recording-dialog");
    $("projectDialog").show();
    if (action === "project-form") {
      await fillSetupForm(form, {display_id: ctx.projectDisplayId, name: f.project.name}, runKey);
      setupReceipt("입력 중", "이 시점에는 아직 프로젝트가 저장되지 않았습니다");
    }
    if (action === "project-policy" || action === "project-save") {
      form.elements.display_id.value = ctx.projectDisplayId;
      form.elements.name.value = f.project.name;
      if (action === "project-policy") await fillSetupForm(form, {framework: f.project.framework, data_policy: "EXTERNAL_SYNTHETIC_ALLOWED"}, runKey);
      else {
        form.elements.framework.value = f.project.framework;
        form.elements.data_policy.value = "EXTERNAL_SYNTHETIC_ALLOWED";
      }
    }
    if (action === "project-save") {
      const body = {display_id: ctx.projectDisplayId, name: form.elements.name.value, framework: form.elements.framework.value, framework_edition: f.project.framework_edition || null, data_policy: "EXTERNAL_SYNTHETIC_ALLOWED", mode: "DEMO"};
      const result = await setupWriteOnce("project", document.querySelector('[form="projectForm"]'), "프로젝트 생성", runKey, () => setupPost("/api/v1/projects", body));
      if (!autoDemoRunIsCurrent(runKey) || !result) return;
      ctx.project = result;
      state.project = result;
      state.selectedClaimId = null;
      state.selectedEvidenceIds = [];
      state.retrieval = null;
      state.ragQuery = "";
      await loadAll();
      setupReceipt("POST /projects · 저장됨", `${result.display_id} · ${result.id}`);
    }
  }
  if (action === "empty-project") {
    await loadAll();
    showSetupDialog(step.title, caption, setupKv({"프로젝트": state.project.display_id, "Claim": state.claims.length, "요구사항": state.requirements.length, "직접 근거": state.evidence.length, "검색 기록": state.retrievalRuns.length, "검토 Job": state.jobs.length}));
    setupReceipt("서버 조회", "이번 촬영 프로젝트의 실제 저장 건수");
  }
  if (action === "profile-preview") {
    for (const name of ["ECSS", "NASA", "KASA"]) {
      const target = document.querySelector(`[data-profile-preview="${name}"]`);
      if (!await pointAutoDemoCursor(target, `클릭 · ${name} 미리보기`, runKey, {click: true})) return;
      state.profilePreview = name;
      renderProfile();
      await autoDemoWait(1500);
    }
    setupReceipt("미리보기", "저장된 개발 체계는 KASA · 다른 체계 채택 변경 없음");
  }
  if (action.startsWith("document-")) {
    openDocumentDialog(f.profile_document.document_code);
    $("documentDialog").close();
    $("documentDialog").classList.add("setup-recording-dialog");
    $("documentDialog").show();
    const form = $("documentForm");
    const values = f.profile_document;
    for (const name of ["document_code", "profile", "title"]) form.elements[name].value = values[name];
    const documentFields = {revision: values.revision, product_level: values.product_level, clause_locator: values.clause_locator, adoption_note: values.adoption_note};
    if (action === "document-form") await fillSetupForm(form, documentFields, runKey);
    else for (const [name, value] of Object.entries(documentFields)) form.elements[name].value = value;
    if (action === "document-save") {
      const {document_code, ...body} = values;
      const saved = await setupWriteOnce("profile-document", document.querySelector('[form="documentForm"]'), "등록 정보 저장", runKey, () => api(`/api/v1/projects/${ctx.project.id}/documents/${document_code}`, {method: "PUT", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(body)}));
      if (!autoDemoRunIsCurrent(runKey) || !saved) return;
      await loadAll();
      setupReceipt("PUT /documents · 저장됨", `${saved.title} · 상태 ${saved.status || "등록"} · 공식 채택 미확인`);
    }
  }
  if (action.startsWith("claim-")) {
    showSetupDialog(step.title, caption, setupFields([["display_id", "Claim ID"], ["question", "BM1 검토 질문", true], ["unit", "장비 / Unit"], ["configuration", "형상 / Configuration"], ["run", "시험 / Run"]]), "", action === "claim-save");
    const form = $("setupDemoForm");
    const values = {display_id: f.claim.display_id, question: f.claim.question, ...f.claim.scope};
    if (action === "claim-form") await fillSetupForm(form, {display_id: values.display_id, question: values.question}, runKey);
    else {
      form.elements.display_id.value = values.display_id;
      form.elements.question.value = values.question;
      if (action === "claim-scope") await fillSetupForm(form, f.claim.scope, runKey);
      else for (const [name, value] of Object.entries(f.claim.scope)) form.elements[name].value = value;
    }
    if (action === "claim-save") {
      const result = await setupWriteOnce("claim", $("setupDemoSave"), "Claim revision 저장", runKey, () => setupPost(`/api/v1/projects/${ctx.project.id}/claims`, {display_id: form.elements.display_id.value, question: form.elements.question.value, review_target: "BM1", review_purpose: f.claim.review_purpose, scope: Object.fromEntries(["unit", "configuration", "run"].map(name => [name, form.elements[name].value]))}));
      if (!autoDemoRunIsCurrent(runKey) || !result) return;
      ctx.claim = result;
      state.selectedClaimId = result.id;
      await loadAll();
      $("setupDemoReceipt").textContent = `서버 저장 · ${result.id} · revision ${result.version}`;
      $("setupDemoReceipt").hidden = false;
      setupReceipt("POST /claims · 저장됨", `${result.display_id} · revision ${result.version}`);
    }
  }
  if (action.startsWith("requirement-")) {
    const fields = [["display_id", "요구사항 ID"], ["statement", "합성 요구사항", true], ["level", "제품 수준"], ["parent_ref", "상위 요구"], ["verification_method", "검증 방법"], ["owner", "담당 역할"], ["claim_label", "연결 Claim"]];
    showSetupDialog(step.title, caption, setupFields(fields), "", action === "requirement-save");
    const form = $("setupDemoForm");
    const requirementFields = Object.fromEntries(fields.map(([name]) => [name, f.requirement[name]]));
    if (action === "requirement-form") await fillSetupForm(form, requirementFields, runKey);
    else for (const [name, value] of Object.entries(requirementFields)) form.elements[name].value = value;
    if (action === "requirement-save") {
      const body = {...f.requirement, claim_id: ctx.claim.id};
      for (const [name] of fields) body[name] = form.elements[name].value;
      const saved = await setupWriteOnce("requirement", $("setupDemoSave"), "요구사항 연결 저장", runKey, () => setupPost(`/api/v1/projects/${ctx.project.id}/requirements`, body));
      if (!autoDemoRunIsCurrent(runKey) || !saved) return;
      ctx.requirement = saved;
      await loadAll();
      setupReceipt("POST /requirements · 저장됨", `${saved.display_id} → ${ctx.claim.display_id}`);
      $("setupDemoReceipt").textContent = state.autoDemo.operation;
      $("setupDemoReceipt").hidden = false;
    }
  }
  if (action === "source-preview") {
    showSetupDialog(step.title, caption, `<pre class="setup-source">${escapeHtml(ctx.documentText)}</pre>`, `출처: fixtures/demo/setup_walkthrough.md · 공개 합성 문서`);
    setupReceipt("원문 미리보기", "아직 업로드/파싱하지 않은 촬영용 파일");
  }
  if (action.startsWith("upload-")) {
    openArtifactDialog();
    $("artifactDialog").close();
    $("artifactDialog").classList.add("setup-recording-dialog");
    $("artifactDialog").show();
    $("evidenceForm").hidden = true;
    const form = $("uploadForm");
    const transfer = new DataTransfer();
    transfer.items.add(new File([ctx.documentText], f.document.filename, {type: "text/markdown"}));
    form.elements.file.files = transfer.files;
    if (action === "upload-form") {
      await pointAutoDemoCursor(form.elements.file, `파일 선택 · ${f.document.filename}`, runKey, {click: true});
      await fillSetupForm(form, {rights_status: "PUBLIC", edition: f.document.edition}, runKey);
    } else {
      form.elements.rights_status.value = "PUBLIC";
      form.elements.edition.value = f.document.edition;
    }
    form.elements.adopted.checked = true;
    if (action === "upload-save") {
      const upload = new FormData(form);
      upload.set("adopted", "true");
      upload.set("applicability_status", "APPLICABLE");
      upload.set("usage_purpose", "OPERATIONAL_EVIDENCE");
      const artifact = await setupWriteOnce("artifact", form.querySelector('[type="submit"]'), "원문 bytes 업로드", runKey, () => api(`/api/v1/projects/${ctx.project.id}/artifacts`, {method: "POST", headers: csrfHeaders, body: upload}));
      if (!autoDemoRunIsCurrent(runKey) || !artifact) return;
      ctx.artifact = artifact;
      $("ragParseState").hidden = false;
      $("ragParseState").textContent = `원문 저장 · ${artifact.byte_size} bytes · SHA256 ${artifact.sha256} · 아직 파싱 전`;
      setupReceipt("POST /artifacts · 실제 원문 저장", `${artifact.byte_size} bytes · ${artifact.sha256.slice(0, 16)}`);
    }
  }
  if (action === "parse") {
    showSetupDialog(step.title, caption, setupKv({"원문 파일": ctx.artifact.filename, "Artifact": ctx.artifact.id, "SHA256": ctx.artifact.sha256}), "", true);
    const parsed = await setupWriteOnce("parser", $("setupDemoSave"), "파싱·청킹·색인", runKey, () => setupPost(`/api/v1/artifacts/${ctx.artifact.id}/parse`, {}));
    if (!autoDemoRunIsCurrent(runKey) || !parsed) return;
    ctx.parser = parsed;
    $("setupDemoBody").innerHTML = setupKv({"파싱 상태": parsed.parser_run.status, "페이지": parsed.parser_run.page_count, "청크": parsed.chunks.length, "Parser": parsed.parser_run.parser_version, "Chunker": parsed.parser_run.chunker_version, "Receipt": parsed.parser_run.receipt_sha256});
    setupReceipt("POST /parse · 실제 색인 완료", `${parsed.chunks.length} 청크 · ${parsed.parser_run.receipt_sha256?.slice(0, 16)}`);
    $("setupDemoReceipt").textContent = state.autoDemo.operation;
    $("setupDemoReceipt").hidden = false;
  }
  if (action === "chunks") {
    if (!ctx.parser?.chunks.length) throw new Error("문서에서 검색 가능한 청크를 만들지 못했습니다.");
    const projection = await api(`/api/v1/artifacts/${ctx.artifact.id}/chunks`);
    const chunks = projection.chunks;
    if (!autoDemoRunIsCurrent(runKey)) return;
    showSetupDialog(step.title, caption, `<div class="setup-chunks">${chunks.map(chunk => `<article class="card"><div class="cardhead"><h3>청크 ${chunk.ordinal}</h3><span class="pill info">${escapeHtml(chunk.locator)}</span></div><div class="cardbody"><p>${escapeHtml(chunk.chunk_text)}</p><p class="tiny mono">SHA256 ${escapeHtml(chunk.text_sha256)}</p></div></article>`).join("")}</div>`);
    setupReceipt("GET /artifacts/.../chunks", `${chunks.length}개 저장 원문·위치 조회`);
  }
  if (action === "search-form" || action === "search") {
    if (action === "search-form") {
      await fillSetupField($("ragQuery"), f.retrieval.query, runKey, "문서 검색어");
      await fillSetupField($("ragTopK"), f.retrieval.top_k, runKey, "최대 선택 청크");
    } else {
      $("ragQuery").value = f.retrieval.query;
      $("ragTopK").value = f.retrieval.top_k;
    }
    if (action === "search") {
      const result = await setupWriteOnce("retrieval", document.querySelector("[data-run-retrieval]"), "문서 검색", runKey, () => setupPost(`/api/v1/projects/${ctx.project.id}/retrievals`, {claim_id: ctx.claim.id, query: $("ragQuery").value.trim(), artifact_ids: [ctx.artifact.id], top_k: Number($("ragTopK").value)}, {"Idempotency-Key": `setup-rag:${runKey}`}));
      if (!autoDemoRunIsCurrent(runKey) || !result) return;
      if (!result.run.selected_count) throw new Error("Scope Gate를 통과한 검색 청크가 없습니다. LIVE 요청은 진행하지 않습니다.");
      ctx.retrieval = result;
      state.retrieval = result;
      state.retrievalRuns = [result.run];
      state.ragQuery = result.run.query;
      renderWorkspace();
      setupReceipt("POST /retrievals · 검색 저장", `후보 ${result.run.candidate_count} · 선택 ${result.run.selected_count} · ${result.run.receipt_sha256.slice(0, 16)}`);
    }
  }
  if (action === "selected-chunk") {
    const item = ctx.retrieval?.results.find(result => result.selected);
    if (!item) throw new Error("이번 시연의 선택 청크가 없습니다.");
    openRagChunkDialog(item.chunk_id);
    $("evidenceDialog").close();
    $("evidenceDialog").classList.add("setup-recording-dialog");
    $("evidenceDialog").show();
    await pointAutoDemoCursor($("evidenceDialogBody"), "근거 확인 · 실제 청크와 원문 위치", runKey);
    setupReceipt("선택된 청크", `${item.locator} · ${item.reason}`);
  }
  if (action === "input-check") {
    const retrieval = activeRetrieval();
    if (!retrieval || retrieval.run.id !== ctx.retrieval?.run.id) throw new Error("검색의 Claim 또는 프로젝트 version이 현행 입력과 다릅니다.");
    showSetupDialog(step.title, caption, setupKv({"프로젝트": state.project.display_id, "정책": state.project.data_policy, "Claim": `${ctx.claim.display_id} · v${ctx.claim.version}`, "범위": JSON.stringify(ctx.claim.scope), "직접 Evidence": state.selectedEvidenceIds.length, "선택 RAG 청크": retrieval.run.selected_count, "검색 Receipt": retrieval.run.receipt_sha256, "다음 실행": state.autoDemo.mode === "LIVE" ? "새 Local LLM 응답 생성 1건" : "명시적 REPLAY 1건"}));
    setupReceipt("입력 현행성 확인", "등록된 Claim + 이번 검색 receipt · 자동 승인 없음");
  }
}
