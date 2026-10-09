/* Operator-facing local preparation; this page never starts inference or remote training. */
(() => {
  const view = {catalog: null, data: null, projectId: null, user: null, ready: false, tab: "goals", generation: 0, sourceGeneration: 0, source: null, chunks: [], keys: new Map(), previews: new Map()};
  const labels = {VERIFIED: "검증 확인", IMPLEMENTED: "구현 확인", PARTIAL: "부분 달성", BLOCKED: "준비 대기", PLANNED: "계획", DRAFT: "미검토 초안", APPROVED: "사례 검토 완료", REJECTED: "기각", TRAIN: "학습용", EVALUATION: "평가용"};
  const pendingReviews = new Set();
  const blockers = {TRAINING_RECIPE_UNVERIFIED: "승인된 학습 코드·환경·설정 확인 필요", REMOTE_TRAINING_RUNNER_NOT_IMPLEMENTED: "RunPod 학습 작업 실행기 연결 필요", TRAIN_DATASET_NOT_READY: "검토 완료된 학습 데이터 버전 필요", EVALUATION_DATASET_NOT_READY: "학습 자료와 분리된 평가 데이터 버전 필요"};
  const html = value => escapeHtml(value);
  const badge = (value, good = ["VERIFIED", "APPROVED"].includes(value)) => `<span class="pill ${good ? "ok" : "wait"}">${html(labels[value] || value)}</span>`;
  const date = value => value ? new Date(value).toLocaleString("ko-KR") : "—";
  const isEditor = () => ["engineer", "reviewer", "approver"].includes(view.data?.role);
  const isReviewer = () => ["reviewer", "approver"].includes(view.data?.role);
  const current = (projectId, user) => state.project?.id === projectId && state.status?.user === user;
  const reviewKey = id => `${view.projectId}:${view.user}:${id}`;
  const formAllowed = form => {
    if (!view.ready || !isEditor() || !current(view.projectId, view.user)) return false;
    if (form.id === "developmentUploadForm") return view.catalog?.released_sections.includes("documents");
    if (form.id === "learningExampleForm") return view.data?.example_authoring_enabled && view.chunks.some(c => c.id === $("learningSourceChunk").value);
    if (form.dataset.learningDecision) return view.data?.example_review_enabled && isReviewer() && !pendingReviews.has(reviewKey(form.dataset.learningDecision)) && view.data.examples.some(e => e.id === form.dataset.learningDecision && e.status === "DRAFT");
    return view.data?.preparation_enabled;
  };
  const reviewBlocker = item => item.freshness !== "CURRENT" ? "원문이 변경되거나 확인되지 않아 검토 완료로 처리할 수 없습니다. 기각 기록은 남길 수 있습니다." : !["PUBLIC", "GRANTED"].includes(item.source_snapshot.rights_status) || !item.source_snapshot.edition?.trim() ? "등록된 사용 권리·판본이 미확인입니다. 검토 완료로 처리할 수 없으며 기각 기록은 남길 수 있습니다." : "";
  function decisionAllowed(form, decision) {
    if (!formAllowed(form) || !form.elements.note.value.trim()) return false;
    const item = view.data.examples.find(e => e.id === form.dataset.learningDecision);
    return decision === "REJECTED" || decision === "APPROVED" && !reviewBlocker(item) && form.elements.data_use_confirmed.checked;
  }
  function updateFormButtons(form) {
    form.querySelectorAll('button[type="submit"]').forEach(button => {
      button.disabled = form.dataset.busy === "true" || !(form.dataset.learningDecision ? decisionAllowed(form, button.value) : formAllowed(form));
    });
  }
  const updateReviewButtons = () => document.querySelectorAll('[data-learning-decision]').forEach(updateFormButtons);
  const updateAuthoringButton = () => $("learningExampleForm").querySelector('button[type="submit"]').disabled = !formAllowed($("learningExampleForm")) || $("learningExampleForm").dataset.busy === "true";
  const error = text => {$("developmentError").textContent = text; $("developmentError").hidden = !text;};
  const keyFor = (form, payload) => {
    const text = JSON.stringify(payload);
    if (view.keys.get(form)?.payload !== text) view.keys.set(form, {payload: text, key: crypto.randomUUID()});
    return view.keys.get(form).key;
  };
  function activateTab(tab) {
    if (view.catalog && !view.catalog.released_sections.includes(tab)) tab = 'goals';
    view.tab = tab;
    for (const name of ["goals", "documents", "learning"]) {
      const button = document.querySelector(`[data-development-tab="${name}"]`);
      button.classList.toggle("active", name === tab);
      button.setAttribute("aria-selected", String(name === tab));
      $("development" + name[0].toUpperCase() + name.slice(1)).hidden = name !== tab;
    }
  }
  function clearSource() {
    ++view.sourceGeneration; view.source = null; view.chunks = [];
    $("learningSourceChunk").innerHTML = '<option value="">문서를 선택하십시오.</option>';
    $("learningSourceChunk").disabled = true;
    $("learningSourcePreview").textContent = "원문 위치를 선택하십시오.";
    $("learningSourceState").textContent = "파싱이 완료된 자료만 선택할 수 있습니다.";
    updateAuthoringButton();
  }
  async function load() {
    const projectId = state.project?.id;
    if (!projectId) return;
    const generation = ++view.generation;
    view.ready = false;
    const user = state.status?.user;
    const changed = view.projectId !== projectId || view.user !== user;
    if (changed) {
      view.catalog = view.data = null;
      view.projectId = projectId;
      view.user = user;
      view.keys.clear();
      view.previews.clear();
      $("developmentUploadForm").reset();
      $("learningExampleForm").reset();
      $("developmentUploadState").hidden = true;
      clearSource();
      for (const id of ["developmentGoals", "developmentDocumentList", "learningExamples", "learningDatasets", "learningDatasetChoices"]) $(id).innerHTML = "";
      $("learningSourceDocument").innerHTML = '<option value="">자료를 불러오는 중입니다.</option>';
    }
    for (const id of ["developmentUploadForm", "learningExampleForm", "learningDatasetForm"]) $(id).querySelector('button[type="submit"]').disabled = true;
    updateReviewButtons();
    error("");
    $("developmentLoadState").hidden = false;
    $("developmentLoadState").textContent = "로컬 저장 상태를 확인하는 중입니다. RunPod 모델을 호출하지 않습니다.";
    try {
      const [catalog, data] = await Promise.all([api(`/api/v1/projects/${projectId}/development`), api(`/api/v1/projects/${projectId}/learning`)]);
      if (generation !== view.generation || state.project?.id !== projectId || state.status?.user !== user) return;
      view.catalog = catalog; view.data = data; view.ready = true;
      render();
      $("developmentLoadState").textContent = `${state.project.display_id} · 로컬 준비 자료 · 조회 ${date(new Date())}`;
    } catch (e) {
      if (generation !== view.generation) return;
      error(`조회 실패: ${e.message}. 마지막으로 표시한 기록은 새 상태가 아닐 수 있습니다.`);
      $("developmentLoadState").textContent = "로컬 API 연결을 확인한 뒤 새로고침하십시오.";
    }
  }
  function renderGoals() {
    const catalog = view.catalog;
    const training = view.data.training;
    const model = catalog.model_baseline;
    $("developmentGoals").innerHTML = `
      <section class="hero development-hero"><div><div class="eyebrow">DORILAB DEVELOPMENT GOAL</div><h2>${html(catalog.goal)}</h2><p>${html(catalog.scope_note)}</p></div><div class="hero-side">${badge(catalog.overall_status)}<p>개발 기준일 ${html(catalog.assessed_at)}<br>프로젝트 공식 승인과 별도</p></div></section>
      <div class="notice blue">현재 원문 등록·사례 작성과 사람의 검토·기각 기록을 제공합니다. 검토는 로컬 자료 준비에 한정되며 데이터 버전 고정과 RunPod 학습 연결은 후속 단계입니다.</div><div class="space"></div>
      <div class="development-summary"><div class="card cardbody"><span>기존 등록 원문</span><strong>${view.data.documents.length}건</strong></div><div class="card cardbody"><span>작성한 사례</span><strong>${view.data.example_authoring_enabled ? `${view.data.examples.length}건` : "다음 단계"}</strong></div><div class="card cardbody"><span>데이터 버전 관리</span><strong>${view.data.preparation_enabled ? `${view.data.datasets.length}건` : "이후 단계"}</strong></div><div class="card cardbody"><span>RunPod 학습 작업</span><strong>미연결</strong></div></div>
      <section class="card"><div class="cardhead"><div><h3>전체 개발 마일스톤</h3><p>원 설계의 남은 목표와 모델 관리 작업을 함께 추적합니다. 완료율이나 모델 정확도를 추정하지 않습니다.</p></div></div><div class="cardbody development-milestones">${catalog.milestones.map(m => `<article class="development-milestone"><div class="development-milestone-title"><span class="mono">${html(m.id)}</span><h3>${html(m.title)}</h3>${badge(m.status)}</div><p>${html(m.current)}</p><p><b>통과 조건</b> ${html(m.acceptance)}</p><details><summary>판정 근거·남은 범위</summary><p>${html(m.limit)}</p>${m.evidence_ids.map(id => {const source = catalog.evidence.find(e => e.id === id); return source ? `<p><a href="${html(source.download_url)}">${html(source.title)} ↗</a> · ${source.source_verified ? "원본 hash 일치" : "근거 파일 확인 필요"}<span class="subline">${html(source.source)} · ${html(source.kind)} · ${html(source.date)}</span></p>` : "";}).join("")}</details></article>`).join("")}</div></section><div class="space"></div>
      <div class="grid2"><section class="card"><div class="cardhead"><div><h3>RunPod 연결과 학습 준비</h3><p>추론 연결과 학습 실행 준비는 별도 상태입니다.</p></div><button class="btn small" data-development-connection type="button">주소·SSH 포트 설정</button></div><div class="cardbody"><p>현재 추론 연결: <b>${html(state.status?.remote?.state || "확인 대기")}</b> · 앱 ${html(state.status?.mode || "—")}</p><p>학습 실행: ${badge(training.state)} · 원격 GPU 조회 미실행</p><ul>${training.blockers.map(code => `<li>${html(blockers[code] || code)}</li>`).join("")}</ul><button class="btn primary" type="button" disabled title="학습 실행기는 아직 연결되지 않았습니다.">RunPod 학습 실행 · 준비 대기</button><p class="smalltext muted">여기서 데이터를 준비·검토해도 외부 전송이나 학습이 시작되지 않습니다. 실제 실행은 대상·설정·GPU 사용 범위를 확인하는 다음 단계입니다.</p></div></section>
      <section class="card"><div class="cardhead"><div><h3>비교 기준 모델</h3><p>기존 모델을 유지하고 새 후보는 별도로 비교합니다.</p></div></div><div class="cardbody"><h3>Local LLM</h3><p>연결 대상: RunPod · ${html(model.profile_id)}</p><details><summary>고정 릴리스 정보</summary><p>모델 식별자: <span class="mono">${html(model.base_model)}</span></p><p class="mono">base ${html(model.base_revision)}</p><p class="mono">adapter ${html(model.adapter_model_sha256)}</p></details><p class="smalltext muted">등록된 profile의 기준값입니다. 현재 GPU 준비 상태나 이번 학습 성능을 뜻하지 않습니다. 후보 모델·학습 손실·개선 수치는 아직 없습니다.</p></div></section></div>`;
  }
  function renderDocuments() {
    const documents = view.data.documents;
    const statuses = {COMPLETED: "텍스트 파싱 완료", FAILED: "파싱 실패", PROCESSING: "파싱 진행 중"};
    const rights = {PUBLIC: "공개", GRANTED: "권리 확보", RESTRICTED: "제한", UNCONFIRMED: "미확인"};
    const applicability = {APPLICABLE: "적용 가능", NOT_APPLICABLE: "적용 불가", UNCONFIRMED: "미확인"};
    $("developmentDocumentList").innerHTML = `<section class="card"><div class="cardhead"><div><h3>프로젝트 원문 등록부 · ${documents.length}건</h3><p>기존 워크스페이스의 자료도 조회합니다. 추출 텍스트와 원본 파일은 구분해 보존합니다.</p></div><button class="btn small" data-page="workspace">RAG 검색 열기</button></div><div class="cardbody development-documents">${documents.length ? documents.map(d => `<article class="item" data-development-document="${html(d.id)}"><div class="development-milestone-title"><h3>${html(d.filename)}</h3><span class="pill ${d.parser_status === "COMPLETED" ? "ok" : "wait"}">${html(statuses[d.parser_status] || "파싱 대기")}</span></div><p>판본 ${html(d.edition || "미지정")} · 권리 ${html(rights[d.rights_status] || d.rights_status)} · ${html(d.usage_purpose === "OPERATIONAL_EVIDENCE" ? "RAG용 (검색 시 범위 검사)" : d.usage_purpose === "TRAINING" ? "학습 준비 전용 · RAG 제외" : "평가 전용 · RAG·학습 제외")}</p><p>${d.page_count ?? 0}페이지 · ${d.chunk_count ?? 0}개 청크 · ${d.byte_size.toLocaleString()} bytes · ${date(d.created_at)}</p><details><summary>원문 hash·파싱 정보 보기</summary><p class="mono">SHA256 ${html(d.sha256)}</p><p>채택 ${d.adopted ? "확인" : "미확인"} · 적용성 ${html(applicability[d.applicability_status] || d.applicability_status)}</p><p>파서 ${html(d.parser_version || "미실행")} · 청킹 ${html(d.chunker_version || "미실행")} · 완료 ${date(d.finished_at)}</p>${d.receipt_sha256 ? `<p class="mono">파싱 기록 SHA256 ${html(d.receipt_sha256)}</p>` : ""}<ul>${(d.issues || []).map(issue => `<li>${html(issue.code)}${issue.page ? ` · 페이지 ${issue.page}` : ""}${issue.detail ? ` · ${html(issue.detail)}` : ""}</li>`).join("")}</ul></details>${d.parser_status === "COMPLETED" ? `<details data-development-preview="${html(d.id)}"><summary>원문 위치·텍스트 보기</summary><div class="development-source-preview" role="status">펼치면 저장된 추출 텍스트를 조회합니다.</div></details>` : ""}<div class="buttons"><a class="btn small" href="/api/v1/artifacts/${html(d.id)}/download">원본 다운로드</a>${d.parser_status !== "COMPLETED" ? `<button class="btn small" type="button" data-development-parse="${html(d.id)}" ${isEditor() && d.parser_status !== "PROCESSING" ? "" : "disabled"}>${d.parser_status === "FAILED" ? "파싱 다시시도" : "파싱 시도"}</button>` : ""}</div>${d.error_code ? `<p class="notice amber">${html(parseFailure(d.error_code))}<span class="subline">${html(d.error_code)} · ${html(d.error_detail || "")}</span>원본은 보존되어 있습니다.</p>` : ""}</article>`).join("") : '<div class="notice empty">등록한 원문이 없습니다. 위에서 논문이나 텍스트 파일을 등록하십시오.</div>'}</div></section>`;
    const selected = $("learningSourceDocument").value;
    const parsed = documents.filter(d => d.parser_status === "COMPLETED");
    $("learningSourceDocument").innerHTML = '<option value="">파싱된 원문 선택</option>' + parsed.map(d => `<option value="${html(d.id)}">${html(d.filename)} · ${html(d.edition || "판본 미지정")}</option>`).join("");
    if (parsed.some(d => d.id === selected)) {
      const document = parsed.find(d => d.id === selected);
      if (view.source && (view.source.artifact.sha256 !== document.sha256 || view.source.artifact.edition !== document.edition || view.source.parser_run.id !== document.parser_run_id)) clearSource();
      $("learningSourceDocument").value = selected;
    }
    else clearSource();
  }
  function parseFailure(code) {
    return {NO_EXTRACTABLE_TEXT: "추출할 텍스트가 없습니다. 이미지·스캔 자료는 OCR 확인이 필요합니다.", PDF_PARSE_FAILED: "PDF 구조를 읽을 수 없습니다.", PDF_ENCRYPTED: "암호화된 PDF는 파싱을 지원하지 않습니다.", TEXT_ENCODING_UNSUPPORTED: "지원하지 않는 텍스트 인코딩입니다.", ARTIFACT_HASH_MISMATCH: "보존 파일과 등록 hash가 일치하지 않습니다."}[code] || "텍스트 파싱을 완료하지 못했습니다.";
  }
  function renderPreview(details, result) {
    const target = details.querySelector('.development-source-preview');
    const start = result.offset, end = Math.min(start + 10, result.chunks.length);
    target.innerHTML = `<p class="smalltext muted">파싱된 텍스트의 위치입니다. 문서 내용의 타당성·적용성 승인을 뜻하지 않습니다.</p><p>${start + 1}–${end} / ${result.chunks.length}개 청크</p>${result.chunks.slice(start, end).map(c => `<section><h4>${html(c.locator)}</h4>${c.section_path.length ? `<p>${html(c.section_path.join(" / "))}</p>` : ""}<pre>${html(c.chunk_text)}</pre><p class="mono smalltext">텍스트 SHA256 ${html(c.text_sha256)}</p></section>`).join("")}<div class="buttons"><button class="btn small" type="button" data-development-chunks="-10" ${start === 0 ? "disabled" : ""}>이전 청크</button><button class="btn small" type="button" data-development-chunks="10" ${end === result.chunks.length ? "disabled" : ""}>다음 청크</button></div><details><summary>파싱 기록 JSON</summary><pre>${html(JSON.stringify(result.parser_run.receipt, null, 2))}</pre></details>`;
  }
  $("developmentDocumentList").addEventListener("toggle", async event => {
    const details = event.target;
    const id = details.dataset.developmentPreview;
    if (!id || !details.open || details.dataset.loading === "true") return;
    const projectId = view.projectId, user = view.user;
    const document = view.data.documents.find(d => d.id === id);
    const cached = view.previews.get(id);
    if (cached?.parser_run.id === document?.parser_run_id) return renderPreview(details, cached);
    const target = details.querySelector('.development-source-preview');
    details.dataset.loading = "true"; target.textContent = "저장된 원문 텍스트를 불러오는 중입니다.";
    try {
      const result = await api(`/api/v1/artifacts/${id}/chunks`);
      if (!details.isConnected || !current(projectId, user)) return;
      if (result.parser_run?.status !== "COMPLETED" || !result.chunks.length) {
        target.textContent = "현재 파싱 결과가 완료 상태가 아닙니다. 등록부를 새로고침하십시오."; return;
      }
      result.offset = 0; view.previews.set(id, result); renderPreview(details, result);
    } catch (e) {if (details.isConnected && current(projectId, user)) target.textContent = `원문 조회 실패: ${e.message}. 닫았다가 다시 펼치면 재조회합니다.`;}
    finally {details.dataset.loading = "false";}
  }, true);
  function renderExampleReview(item) {
    if (item.reviewed_by) return `<div class="notice ${item.status === "APPROVED" && item.freshness === "CURRENT" ? "blue" : "amber"}"><b>${html(labels[item.status])}</b> · 사례 버전 ${item.version}<p>검토 계정 ${html(item.reviewed_by)} · ${date(item.reviewed_at)}</p><p>로컬 자료 사용 권리 확인: ${item.data_use_confirmed ? "체크함" : "체크하지 않음"}</p><details><summary>사람이 작성한 검토 기록</summary><pre>${html(item.review_note)}</pre></details><p>로컬 학습·평가 자료 준비에 대한 결정입니다. 공학 승인·외부 전송 승인·자동 정답 검증은 아닙니다.${item.freshness === "STALE" ? " 원문이 변경되어 현재 사용은 보류합니다. 당시 결정과 입력·응답은 보존합니다." : ""}</p></div>`;
    if (!view.data.example_review_enabled) return '<p>내용·사용 권리는 미확인입니다. 검토 기능은 아직 공개하지 않았습니다.</p>';
    if (!isReviewer()) return '<p class="smalltext muted">미검토 초안입니다. 검토 책임자·승인권자가 검토 또는 기각 기록을 남길 수 있습니다.</p>';
    const blocked = reviewBlocker(item);
    return `<details class="learning-review"><summary>사례 검토·기각</summary><p>입력·응답·출처를 펼치고 원본을 확인한 뒤 검토한 범위와 남은 제약을 기록하십시오.</p><a class="btn small" href="/api/v1/artifacts/${html(item.source_snapshot.artifact_id)}/download">연결된 원본 다운로드</a>${blocked ? `<p class="notice amber">${html(blocked)}</p>` : ""}<form data-learning-decision="${html(item.id)}"><div class="field"><label for="learningReviewNote-${html(item.id)}">검토 기록</label><textarea id="learningReviewNote-${html(item.id)}" name="note" required maxlength="2000" placeholder="원문과 응답을 비교해 확인한 범위 또는 기각 사유"></textarea></div><label class="checkline"><input name="data_use_confirmed" type="checkbox"><span>이 자료를 로컬 학습·평가 자료 준비에 사용할 권리를 확인했습니다. 외부 전송 승인은 별도입니다.</span></label><p class="smalltext muted">검토 완료에는 원문 현행성·등록 권리·판본·권리 확인 체크와 검토 기록이 필요합니다. 기각은 검토 기록만 필요합니다.</p><div class="buttons"><button class="btn primary small" type="submit" value="APPROVED" disabled>사례 검토 완료</button><button class="btn small" type="submit" value="REJECTED" disabled>기각</button></div></form></details>`;
  }
  function renderExamples() {
    $("learningExamples").innerHTML = `<section class="card"><div class="cardhead"><div><h3>저장된 사례 · ${view.data.examples.length}건</h3><p>입력·응답은 작성자가 제공한 초안입니다. 원문 현행성과 사람의 검토 기록을 구분해 확인하십시오.</p></div></div><div class="cardbody development-documents">${view.data.examples.length ? view.data.examples.map(e => `<article class="item" data-learning-example="${html(e.id)}"><div class="development-milestone-title"><h3>${html(e.title)}</h3>${badge(e.status)} ${badge(e.split, false)} ${e.freshness === "STALE" ? '<span class="pill bad">원문 변경 · 재준비 필요</span>' : ""}</div><p>${html(e.source_snapshot.filename)} · ${html(e.source_snapshot.edition || "판본 미지정")} · ${html(e.source_snapshot.locator)}</p><p>문서 묶음 ${html(e.family_key)} · ${html(e.origin === "HUMAN_AUTHORED" ? "직접 작성" : "합성 사례")} · 작성 계정 ${html(e.created_by)} / ${date(e.created_at)}</p><details><summary>입력·응답·출처 펼치기</summary><h4>작성된 입력</h4><pre>${html(e.prompt)}</pre><h4>작성된 응답 / 기대 결과</h4><pre>${html(e.completion)}</pre><p class="mono">입력·응답 SHA256 ${html(e.content_sha256)}</p><p class="mono">원본 SHA256 ${html(e.source_snapshot.sha256)}</p><p class="mono">원문 청크 SHA256 ${html(e.source_snapshot.text_sha256)}</p><p>원문 상태 ${html(e.freshness)} ${html(e.source_issues.join(", "))}</p><p>내용 검증: ${e.semantic_correctness === "NOT_VERIFIED" ? "미검증" : "사람 검토 기록만 있음"}</p></details>${renderExampleReview(e)}</article>`).join("") : '<div class="notice empty">저장된 사례가 없습니다. 파싱된 원문 위치를 선택하고 입력과 응답을 직접 작성하십시오.</div>'}</div></section>`;
    renderDatasetChoices();
    $("learningDatasets").innerHTML = `<section class="card"><div class="cardhead"><div><h3>보존된 데이터 버전</h3><p>버전·출처·검토 기록·JSONL hash를 함께 보존합니다. 이전 버전을 덮어쓰지 않습니다.</p></div></div><div class="cardbody development-documents">${view.data.datasets.length ? view.data.datasets.map(d => `<article class="item"><div class="development-milestone-title"><h3>${html(d.name)} v${d.version}</h3>${badge(d.split, false)}<span class="pill ${d.freshness === "STALE" ? "bad" : "info"}">${d.freshness === "STALE" ? "원문 변경 · 사용 보류" : "로컬 준비 버전"}</span></div><p>${d.manifest.example_count}개 사례 · ${date(d.created_at)} · ${html(d.created_by)}</p><p class="mono">JSONL ${html(d.manifest.jsonl_sha256)}</p><div class="buttons"><a class="btn small" href="${html(d.download_url)}">JSONL 다운로드</a><a class="btn small" href="${html(d.manifest_url)}" target="_blank" rel="noopener">출처·검토 manifest</a></div><p class="smalltext muted">학습 레시피 매핑·token 예산·실제 GPU 실행은 미검증입니다. 다운로드는 기존 버전의 보존 자료이며 재학습 실행이 아닙니다.</p></article>`).join("") : '<div class="notice empty">고정한 데이터 버전이 없습니다. 검토 완료된 사례를 선택해 학습용·평가용을 따로 저장하십시오.</div>'}</div></section>`;
  }
  function renderDatasetChoices() {
    const split = $("learningDatasetSplit").value;
    const eligible = view.data?.examples.filter(e => e.status === "APPROVED" && e.freshness === "CURRENT" && e.split === split) || [];
    $("learningDatasetChoices").innerHTML = eligible.length ? eligible.map(e => `<label class="checkline"><input type="checkbox" name="example_ids" value="${html(e.id)}"><span>${html(e.title)} · ${html(e.family_key)}</span></label>`).join("") : '<p class="smalltext muted">이 용도로 검토 완료된 현행 사례가 없습니다.</p>';
  }
  function render() {
    for (const name of ['documents', 'learning']) document.querySelector(`[data-development-tab="${name}"]`).disabled = !view.catalog.released_sections.includes(name);
    renderGoals(); renderDocuments(); renderExamples(); activateTab(view.tab);
    for (const id of ["developmentUploadForm", "learningExampleForm", "learningDatasetForm"]) $(id).querySelector('button[type="submit"]').disabled = !formAllowed($(id)) || $(id).dataset.busy === "true";
    $("developmentUploadPermission").textContent = isEditor() ? "" : "조회 권한입니다. 파일 등록·파싱은 엔지니어·검토 책임자·승인권자가 할 수 있습니다.";
    $("learningAuthoringPermission").textContent = isEditor() ? "" : "조회 권한입니다. 사례 작성은 엔지니어·검토 책임자·승인권자가 할 수 있습니다.";
    $("learningDatasetSection").hidden = !view.data.preparation_enabled;
    $("learningNextStep").hidden = view.data.preparation_enabled;
    updateReviewButtons();
  }
  async function selectDocument(id) {
    clearSource();
    $("learningSourceDocument").value = id;
    const projectId = state.project?.id;
    const user = state.status?.user, generation = view.sourceGeneration;
    $("learningSourceState").textContent = "원문과 위치 목록을 불러오는 중입니다.";
    try {
      const result = await api(`/api/v1/artifacts/${id}/chunks`);
      if (!current(projectId, user) || generation !== view.sourceGeneration || $("learningSourceDocument").value !== id) return;
      if (result.parser_run?.status !== "COMPLETED" || !result.chunks.length) throw new Error("파싱이 완료된 원문 위치가 없습니다.");
      view.source = result;
      view.chunks = result.chunks;
      $("learningSourceChunk").innerHTML = '<option value="">원문 위치 선택</option>' + view.chunks.map(c => `<option value="${html(c.id)}">${html(c.locator)}</option>`).join("");
      $("learningSourceChunk").disabled = false;
      $("learningSourceState").textContent = `판본 ${result.artifact.edition || "미지정"} · ${result.chunks.length}개 원문 위치 · 원하는 위치를 선택하십시오.`;
    } catch (e) { if (current(projectId, user) && generation === view.sourceGeneration) {error(e.message); $("learningSourceState").textContent = "원문 조회 실패 · 문서를 다시 선택하십시오.";} }
    finally {updateAuthoringButton();}
  }
  async function submit(form, action) {
    if (form.dataset.busy === "true") return;
    if (!formAllowed(form)) return error("현재 프로젝트와 역할에서 이 작업을 할 수 없습니다.");
    const projectId = view.projectId, user = view.user;
    const pendingKey = form.dataset.learningDecision ? reviewKey(form.dataset.learningDecision) : null;
    if (pendingKey) pendingReviews.add(pendingKey);
    form.dataset.busy = "true";
    const buttons = [...form.querySelectorAll('button[type="submit"]')];
    buttons.forEach(b => b.disabled = true);
    error("");
    try { await action(); } catch (e) {if (current(projectId, user)) error(e.message);}
    finally { if (pendingKey) pendingReviews.delete(pendingKey); form.dataset.busy = "false"; updateFormButtons(form); updateReviewButtons(); }
  }
  $("developmentRefresh").addEventListener("click", load);
  document.querySelectorAll("[data-development-tab]").forEach(button => button.addEventListener("click", () => activateTab(button.dataset.developmentTab)));
  $("developmentGoals").addEventListener("click", event => {if (event.target.closest("[data-development-connection]")) openRunpodSettings();});
  $("developmentDocumentList").addEventListener("click", async event => {
    const paginate = event.target.closest("[data-development-chunks]");
    if (paginate) {
      const details = paginate.closest('[data-development-preview]');
      const result = view.previews.get(details.dataset.developmentPreview);
      result.offset += Number(paginate.dataset.developmentChunks); renderPreview(details, result);
    }
    const parse = event.target.closest("[data-development-parse]");
    if (parse) {
      const projectId = view.projectId, user = view.user;
      parse.disabled = true;
      try {await api(`/api/v1/artifacts/${parse.dataset.developmentParse}/parse`, {method: "POST", headers: csrfHeaders}); if (current(projectId, user)) await load();}
      catch (e) {if (current(projectId, user)) {await load(); error(`원본은 보존됐지만 파싱은 완료되지 않았습니다: ${e.message}`);}}
    }
  });
  $("learningSourceDocument").addEventListener("change", event => {if (event.target.value) selectDocument(event.target.value); else clearSource();});
  $("learningSourceChunk").addEventListener("change", event => {$("learningSourcePreview").textContent = view.chunks.find(c => c.id === event.target.value)?.chunk_text || "원문 위치를 선택하십시오."; updateAuthoringButton();});
  $("learningDatasetSplit").addEventListener("change", renderDatasetChoices);
  $("developmentUploadForm").addEventListener("submit", event => {
    event.preventDefault(); const form = event.currentTarget; const projectId = state.project?.id; const user = state.status?.user;
    const data = new FormData(form);
    data.set("adopted", data.has("adopted") ? "true" : "false");
    const file = data.get("file");
    const types = {pdf: "application/pdf", txt: "text/plain", md: "text/markdown", json: "application/json", csv: "text/csv"};
    const contentType = types[file?.name?.split(".").pop().toLowerCase()];
    if (!file?.name || !contentType) return error("PDF·TXT·MD·JSON·CSV 파일을 선택하십시오.");
    if (file.size > 20 * 1024 * 1024) return error("파일이 20 MiB를 초과했습니다. 전송하지 않았습니다.");
    data.set("file", new File([file], file.name, {type: contentType}));
    void submit(form, async () => {
      const status = $("developmentUploadState"); status.hidden = false; status.textContent = "원문을 로컬에 저장하는 중입니다.";
      let saved;
      try {
        saved = await api(`/api/v1/projects/${projectId}/artifacts`, {method: "POST", headers: csrfHeaders, body: data});
        if (current(projectId, user)) {status.textContent = "원문 저장 완료 · 텍스트를 파싱하는 중입니다."; form.reset();}
        const parsed = await api(`/api/v1/artifacts/${saved.id}/parse`, {method: "POST", headers: csrfHeaders});
        if (current(projectId, user)) status.textContent = `저장·파싱 완료 · ${parsed.parser_run.chunk_count}개 청크 · 아래 등록부에서 원문 위치를 확인하십시오.`;
      } catch (e) {if (current(projectId, user)) status.textContent = saved ? `원문은 보존됐지만 파싱은 완료되지 않았습니다: ${e.message}. 파일을 다시 등록할 필요 없이 아래 등록부에서 확인하십시오.` : `원문 저장 확인 실패: ${e.message}. 등록 목록을 확인하십시오. 자동 재전송은 하지 않습니다.`;}
      if (current(projectId, user)) await load();
    });
  });
  $("learningExampleForm").addEventListener("submit", event => {
    event.preventDefault(); const form = event.currentTarget; const projectId = state.project?.id; const user = state.status?.user;
    const payload = Object.fromEntries(new FormData(form));
    const key = keyFor(form, payload);
    void submit(form, async () => {
      await api(`/api/v1/projects/${projectId}/learning/examples`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": key}, body: JSON.stringify(payload)});
      if (!current(projectId, user)) return;
      view.keys.delete(form); form.reset(); clearSource(); await load(); message("미검토 초안을 로컬에 저장했습니다. 학습과 모델 호출은 실행하지 않았습니다.", true);
    });
  });
  $("learningExamples").addEventListener("submit", event => {
    const form = event.target.closest("[data-learning-decision]"); if (!form) return;
    event.preventDefault(); const item = view.data.examples.find(e => e.id === form.dataset.learningDecision);
    const data = new FormData(form); const decision = event.submitter?.value;
    if (!decisionAllowed(form, decision)) return error("검토 기록과 권리 확인을 확인하십시오. 현재 역할과 원문 상태에서 허용되는 결정만 저장할 수 있습니다.");
    const payload = {expected_version: item.version, decision, note: data.get("note"), data_use_confirmed: data.has("data_use_confirmed")};
    const projectId = view.projectId, user = view.user;
    void submit(form, async () => {
      try {await api(`/api/v1/learning/examples/${item.id}/decisions`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(payload)});}
      catch (e) {
        const reason = e.message.includes("SOURCE_NOT_CURRENT") ? "원문이 변경되거나 확인되지 않습니다. 현재 상태를 새로고침하고 새 사례로 재검토하십시오." : e.message.includes("DATA_USE_OR_EDITION_UNCONFIRMED") ? "사용 권리·판본과 권리 확인 체크가 필요합니다. 미확인 자료는 검토 완료로 처리할 수 없습니다." : e.message.includes("EXAMPLE_VERSION_OR_STATUS_CONFLICT") ? "이미 결정됐거나 사례 버전이 바뀌었습니다. 현재 상태를 새로고침하십시오. 결정은 중복 저장하지 않습니다." : `결정 저장 여부를 확인하지 못했습니다: ${e.message}. 자동 재전송하지 않습니다. 현재 상태를 새로고침해 반영 여부를 확인하십시오.`;
        throw new Error(reason);
      }
      if (!current(projectId, user)) return;
      await load();
      if (!current(projectId, user)) return;
      message(`사례 ${decision === "APPROVED" ? "검토 완료" : "기각"} 기록을 저장했습니다. 공학 승인·외부 전송·학습 실행은 아닙니다.${view.ready ? "" : " 목록 재조회는 실패했습니다. 현재 상태를 새로고침하십시오."}`, true);
    });
  });
  $("learningExamples").addEventListener("input", updateReviewButtons);
  $("learningExamples").addEventListener("change", updateReviewButtons);
  $("learningDatasetForm").addEventListener("submit", event => {
    event.preventDefault(); const form = event.currentTarget; const projectId = state.project?.id;
    const data = new FormData(form); const payload = {name: data.get("name"), split: data.get("split"), example_ids: data.getAll("example_ids")};
    if (!payload.example_ids.length) return error("검토 완료된 현행 사례를 하나 이상 선택하십시오.");
    const key = keyFor(form, payload);
    void submit(form, async () => {const result = await api(`/api/v1/projects/${projectId}/learning/datasets`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": key}, body: JSON.stringify(payload)}); view.keys.delete(form); await load(); message(`${result.name} v${result.version}를 로컬에 보존했습니다. RunPod 전송·학습은 실행하지 않았습니다.`, true);});
  });
  window.dorilabDevelopment = {load};
})();
