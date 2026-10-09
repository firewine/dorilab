/* File declarations -> persistent question-set rows -> individual human label reviews. */
(() => {
  const ui = {projectId: null, user: null, ready: false, overview: null, reload: null, openTab: null,
    batchId: null, itemId: null, detail: null, signature: null, readSequence: 0, reading: null,
    importBusy: false, decisionBusy: false, keys: new Map(), savedUpload: null};
  const h = value => escapeHtml(value);
  const when = value => value ? new Date(value).toLocaleString("ko-KR") : "—";
  const statusLabel = value => ({DRAFT: "미검토", APPROVED: "문항 승인", REJECTED: "기각"}[value] || value);
  const current = (projectId = ui.projectId, user = ui.user) => projectId === state.project?.id && user === state.status?.user;
  const canEdit = () => ui.ready && current() && ["engineer", "reviewer", "approver"].includes(ui.overview?.role);
  const canReview = () => ui.ready && current() && ui.overview?.import_review_enabled && ["reviewer", "approver"].includes(ui.overview.role);
  const selectedItem = () => ui.detail?.items.find(i => i.id === ui.itemId);
  const tell = (text, failure = false) => {
    const target = $("learningSetMessage"); target.textContent = text; target.hidden = !text;
    target.className = `notice ${failure ? "amber" : "blue"}`;
  };
  function updateButtons() {
    $("learningSetUploadForm").querySelector('button[type="submit"]').disabled = !canEdit() || ui.importBusy;
    const form = $("learningSetDetail").querySelector('[data-learning-set-decision]');
    if (!form) return;
    const item = selectedItem(), note = form.elements.note?.value.trim() || "";
    form.querySelectorAll('button[type="submit"]').forEach(button => {
      const basic = canReview() && !ui.decisionBusy && item?.status === "DRAFT" && !!note;
      button.disabled = !basic || button.value === "APPROVED" && (item.freshness !== "CURRENT" || !form.elements.review_confirmed.checked || !form.elements.prompt.value.trim() || !form.elements.completion.value.trim());
    });
  }
  function context({projectId, user, ready, reload, openTab}) {
    if (ui.projectId !== projectId || ui.user !== user) {
      ++ui.readSequence; ui.overview = ui.detail = ui.signature = ui.batchId = ui.itemId = null;
      ui.keys.clear(); ui.savedUpload = null;
      $("learningSetUploadForm").reset(); $("learningSetStatus").value = "DRAFT";
      $("learningSetSplit").value = "ALL"; $("learningSetSearch").value = "";
      $("learningSetSummary").textContent = ""; $("learningSetList").textContent = "";
      $("learningSetDetail").innerHTML = '<div class="notice empty">등록한 문항 세트를 불러오는 중입니다.</div>';
      $("learningSetFilters").hidden = true; tell("");
    }
    Object.assign(ui, {projectId, user, ready, reload, openTab}); updateButtons();
  }
  function render(overview) {
    ui.overview = overview;
    $("learningSetPermission").textContent = canEdit() ? "" : "파일 등록은 엔지니어·검토 책임자·승인권자만 할 수 있습니다.";
    const sets = overview.imports || [];
    $("learningSetSelect").innerHTML = sets.length ? sets.map(s => `<option value="${h(s.id)}">${h(s.source_snapshot.filename)} · 승인 ${s.counts.APPROVED}/${s.example_count} · ${when(s.created_at)}</option>`).join("") : '<option value="">등록한 문항 세트가 없습니다.</option>';
    $("learningSetSelect").disabled = !sets.length;
    if (!sets.length) {
      ui.detail = ui.batchId = null; $("learningSetSummary").textContent = "";
      $("learningSetFilters").hidden = true; $("learningSetList").textContent = "";
      $("learningSetDetail").innerHTML = '<div class="notice empty">위에서 파일 하나를 선택하고 ‘자동 분리 · 검토 목록에 저장’을 누르십시오.</div>';
    } else {
      if (!sets.some(s => s.id === ui.batchId)) ui.batchId = sets[0].id;
      $("learningSetSelect").value = ui.batchId;
      const batch = sets.find(s => s.id === ui.batchId);
      const signature = JSON.stringify([batch.id, batch.counts, batch.freshness, batch.source_issues]);
      if (!ui.detail || signature !== ui.signature) {
        ui.signature = signature; ui.reading = selectBatch(ui.batchId);
      } else updateButtons();
    }
    updateButtons();
  }
  async function selectBatch(id) {
    const projectId = ui.projectId, user = ui.user, sequence = ++ui.readSequence;
    ui.batchId = id; ui.detail = null;
    $("learningSetSummary").textContent = "원본 분리 결과와 문항별 결정 이력을 불러오는 중입니다.";
    $("learningSetList").textContent = ""; $("learningSetFilters").hidden = true;
    $("learningSetDetail").textContent = "문항을 불러오는 중입니다.";
    try {
      const detail = await api(`/api/v1/learning/imports/${id}`);
      if (sequence !== ui.readSequence || !current(projectId, user)) return;
      ui.detail = detail;
      const category = $("learningSetCategory").value;
      $("learningSetCategory").innerHTML = '<option value="ALL">모든 유형</option>' + detail.categories.map(c => `<option value="${h(c)}">${h(c)}</option>`).join("");
      if (detail.categories.includes(category)) $("learningSetCategory").value = category;
      $("learningSetFilters").hidden = false; renderSummary(); renderList();
    } catch (e) {
      if (sequence !== ui.readSequence || !current(projectId, user)) return;
      $("learningSetSummary").textContent = "검토 목록 조회 실패 · 연결을 확인한 뒤 현재 상태를 새로고침하십시오.";
      $("learningSetDetail").textContent = e.message; tell(`검토 목록을 가져오지 못했습니다: ${e.message}`, true);
    }
  }
  function renderSummary() {
    const d = ui.detail;
    $("learningSetSummary").innerHTML = `<div class="learning-set-counts"><b>전체 ${d.example_count}</b><span>미검토 ${d.counts.DRAFT}</span><span>승인 ${d.counts.APPROVED}</span><span>기각 ${d.counts.REJECTED}</span><span>학습용 ${d.train_count} · 평가 전용 ${d.evaluation_count}</span></div><p class="smalltext muted">파일 분리 결과 · 원본과 결정은 서버에 보존됩니다. 새로고침해도 검토 기록이 유지됩니다.</p>${d.freshness === "STALE" ? `<div class="notice amber">원본 또는 등록 정보 변경 · 기존 결정은 보존되지만 새 승인은 차단됩니다. 변경된 파일을 새 세트로 등록해 재검토하십시오.<p>${h(d.source_issues.join(" · "))}</p></div>` : ""}`;
  }
  function filtered() {
    const status = $("learningSetStatus").value, split = $("learningSetSplit").value, category = $("learningSetCategory").value;
    const search = $("learningSetSearch").value.trim().toLocaleLowerCase();
    return (ui.detail?.items || []).filter(i => (status === "ALL" || i.status === status) && (split === "ALL" || i.split === split) && (category === "ALL" || i.category === category) && (!search || [i.question_id, i.question, i.source?.id, i.source?.title, i.family_key].join(" ").toLocaleLowerCase().includes(search)));
  }
  function renderList() {
    const rows = filtered();
    if (!rows.some(i => i.id === ui.itemId)) ui.itemId = rows[0]?.id || null;
    $("learningSetList").innerHTML = rows.length ? `<p class="smalltext muted">현재 조건 ${rows.length}문항</p>` + rows.map(i => `<button type="button" class="learning-set-row ${i.id === ui.itemId ? "selected" : ""}" data-learning-set-item="${h(i.id)}" aria-pressed="${i.id === ui.itemId}"><span class="learning-set-row-title">${h(i.question_id)} · ${h(i.category)} <small>${statusLabel(i.status)}</small></span><span>${h(i.question)}</span><small>${i.split === "TRAIN" ? "학습용" : "평가 전용"} · ${h(i.source?.id || "출처 미지정")} · ${h(i.family_key || "묶음 미지정")}</small></button>`).join("") : '<div class="notice empty">현재 분류 조건에 해당하는 문항이 없습니다.</div>';
    renderDetail();
  }
  function renderDetail() {
    const item = selectedItem();
    if (!item) {$("learningSetDetail").innerHTML = '<div class="notice empty">문항을 선택하거나 분류 조건을 바꾸십시오.</div>'; return;}
    const source = item.source || {}, draft = item.original_payload, history = item.decision_history[0];
    const approved = item.status === "APPROVED", reviewable = canReview() && item.status === "DRAFT";
    const text = (title, value) => value ? `<p><b>${h(title)}</b></p><pre>${h(value)}</pre>` : "";
    const form = item.status === "DRAFT" ? `<form data-learning-set-decision="${h(item.id)}"><div class="field"><label for="learningSetPrompt">검토할 모델 입력</label><textarea id="learningSetPrompt" name="prompt" maxlength="32768" required ${reviewable ? "" : "readonly"}>${h(draft.prompt)}</textarea></div><div class="field"><label for="learningSetCompletion">검토할 정답 초안</label><textarea id="learningSetCompletion" name="completion" maxlength="32768" required ${reviewable ? "" : "readonly"}>${h(draft.completion_draft)}</textarea></div><p class="smalltext muted">수정해서 승인하면 원 초안과 승인한 입력·답안을 따로 저장합니다. 오답은 정답으로 내보내지 않습니다.</p>${reviewable ? `<div class="field"><label for="learningSetNote">승인 또는 기각 근거</label><textarea id="learningSetNote" name="note" maxlength="2000" required placeholder="확인한 근거·수정 사항 또는 기각 이유"></textarea></div><label class="checkline"><input name="review_confirmed" type="checkbox"><span>이 문항의 질문·정답과 제시된 확인 범위를 검토했습니다. 원 논문 검증·학습 실행 승인은 별도입니다.</span></label><div class="buttons"><button class="btn primary" type="submit" value="APPROVED" disabled>승인하고 다음 문항</button><button class="btn" type="submit" value="REJECTED" disabled>기각하고 다음 문항</button></div>` : '<div class="notice blue">내용 검토와 결정 저장은 검토 책임자·승인권자 역할에서 할 수 있습니다.</div>'}</form>` : text("승인한 모델 입력", item.reviewed_prompt) + text("승인한 정답", item.reviewed_completion);
    $("learningSetDetail").innerHTML = `<article><div class="development-milestone-title"><h3>${h(item.question_id)} · ${h(item.category)}</h3><span class="pill ${approved ? "ok" : "wait"}">${statusLabel(item.status)}</span></div><p class="learning-set-question">${h(item.question)}</p><p><b>${item.split === "TRAIN" ? "학습 후보 문항" : "평가 전용 · 학습 제외"}</b> · ${h(source.id || "출처 미지정")} · ${h(source.title || "제목 미지정")}</p><p class="smalltext muted">출처 묶음 ${h(item.family_key || "미지정")} · 작성 구분 ${h(item.origin || "미지정")} · 검토 분류 ${h(item.review_classification || "미지정")}</p><details><summary>파일에 기재된 출처·판본·위치</summary><p>판본 ${h(source.edition || "미지정")}<br>위치 ${h(source.locator || "미지정")}<br>DOI ${h(source.doi || "미지정")}</p>${text("원문 확인 범위 (파일의 기록)", source.confirmation_scope)}<p class="smalltext muted">${h(source.access_status || "접근 상태 미지정")}<br>${h(source.url || "주소 미지정")}</p><p>서버가 원 논문을 대조한 결과가 아닙니다.</p></details>${item.freshness !== "CURRENT" ? `<div class="notice amber">원본 또는 항목 변경으로 새 승인을 할 수 없습니다. ${h(item.source_issues.join(" · "))}</div>` : ""}${item.classification_issues?.length ? `<div class="notice amber">출처·학습/평가 분류 확인 필요: ${h(item.classification_issues.join(" · "))}. 자동 분류를 재배정하거나 학습 대상으로 승인하지 않습니다.</div>` : ""}<div class="learning-set-wrong">${text("오답 초안 · 정답 학습에서 제외", draft.rejected_draft)}${text("파일의 오답 이유", draft.rejected_reason_draft)}</div><details><summary>원 초안·채점항목·이전 검토 메모</summary>${text("원 모델 입력", draft.prompt)}${text("원 정답 초안", draft.completion_draft)}${text("최소 채점항목", item.rubric)}${text("관찰", item.review_observations)}${text("수정 제안 (미승인)", item.revision_suggestion)}<p>${h(item.expression_diagnostic || "")}</p><p class="mono smalltext">원 항목 SHA256 ${h(item.original_sha256)}</p></details>${form}${history ? `<section class="learning-set-history"><h4>결정 이력</h4><p>${statusLabel(history.decision)} · ${h(history.reviewed_by)} · ${when(history.reviewed_at)} · v${history.from_version} → v${history.to_version}</p><pre>${h(history.note)}</pre><p class="smalltext muted">이 결정은 문항 내용 검토에만 적용됩니다. 학습 파일 생성·GPU 실행·제품 적합성 승인은 아닙니다.</p></section>` : ""}<div class="buttons"><button class="btn small" type="button" data-learning-set-next>다음 문항 보기</button><a class="btn small" href="/api/v1/artifacts/${h(ui.detail.artifact_id)}/download">원본 세트 다운로드</a></div></article>`;
    updateButtons();
  }
  async function refresh(batchId, itemId = null) {
    ui.batchId = batchId; ui.itemId = itemId; ui.detail = null;
    await ui.reload(); await ui.reading;
  }
  async function importArtifact(artifactId) {
    if (!canEdit() || ui.importBusy) return;
    const projectId = ui.projectId, user = ui.user;
    ui.importBusy = true; updateButtons(); tell("파일 형식·원본 hash를 확인하고 미검토 문항을 저장하는 중입니다.");
    if (!ui.keys.has(artifactId)) ui.keys.set(artifactId, crypto.randomUUID());
    try {
      const batch = await api(`/api/v1/projects/${projectId}/learning/imports`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json", "Idempotency-Key": ui.keys.get(artifactId)}, body: JSON.stringify({artifact_id: artifactId})});
      if (!current(projectId, user)) return;
      $("learningSetStatus").value = "DRAFT"; $("learningSetSplit").value = "ALL"; $("learningSetSearch").value = "";
      await refresh(batch.id);
      if (!current(projectId, user)) return;
      ui.openTab("learning");
      tell(`${batch.duplicate ? "기존 검토 세트를 다시 열었습니다. 기록을 초기화하지 않았습니다." : "문항 세트를 자동 분리해 저장했습니다."} 전체 ${batch.example_count} · 학습용 ${batch.train_count} · 평가용 ${batch.evaluation_count}. GPU 학습은 시작하지 않았습니다.`);
      return batch;
    } catch (e) {
      if (current(projectId, user)) tell(`문항 등록 확인 실패: ${e.message}. 원본은 보존됩니다. 등록한 세트와 원문 등록부를 확인한 뒤 다시 시도하십시오. 자동 재전송하지 않습니다.`, true);
    } finally {ui.importBusy = false; updateButtons();}
  }
  $("learningSetUploadForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (!canEdit() || ui.importBusy) return;
    const form = event.currentTarget, file = $("learningSetFile").files[0];
    if (!file || !file.name.toLowerCase().endsWith(".md")) return tell("100Q 통합검토 Markdown(.md) 파일을 선택하십시오.", true);
    if (file.size > 20 * 1024 * 1024) return tell("20 MiB를 초과했습니다. 파일을 전송하지 않았습니다.", true);
    const projectId = ui.projectId, user = ui.user, metadata = JSON.stringify([form.elements.edition.value, form.elements.rights_status.value]);
    ui.importBusy = true; updateButtons(); tell("원본 세트 파일을 서버에 저장하는 중입니다.");
    try {
      let saved = ui.savedUpload?.file === file && ui.savedUpload.metadata === metadata ? ui.savedUpload.artifact : null;
      if (!saved) {
        const data = new FormData(form); data.set("usage_purpose", "TRAINING");
        data.set("file", new File([file], file.name, {type: "text/markdown"}));
        saved = await api(`/api/v1/projects/${projectId}/artifacts`, {method: "POST", headers: csrfHeaders, body: data});
      }
      if (!current(projectId, user)) return;
      ui.savedUpload = {file, metadata, artifact: saved}; ui.importBusy = false;
      const batch = await importArtifact(saved.id);
      if (batch && current(projectId, user)) {form.reset(); ui.savedUpload = null;}
    } catch (e) {if (current(projectId, user)) tell(`원본 저장 확인 실패: ${e.message}. 원문 등록부를 확인하십시오. 자동 재전송하지 않습니다.`, true);}
    finally {ui.importBusy = false; updateButtons();}
  });
  $("learningSetSelect").addEventListener("change", event => {
    ui.itemId = null; ui.signature = null; ui.reading = selectBatch(event.target.value);
  });
  for (const id of ["learningSetStatus", "learningSetSplit", "learningSetCategory", "learningSetSearch"]) $(id).addEventListener(id === "learningSetSearch" ? "input" : "change", () => {if (ui.detail) renderList();});
  $("learningSetList").addEventListener("click", event => {
    const button = event.target.closest('[data-learning-set-item]');
    if (!button || ui.decisionBusy) return;
    ui.itemId = button.dataset.learningSetItem; renderList();
  });
  $("learningSetDetail").addEventListener("input", updateButtons);
  $("learningSetDetail").addEventListener("change", updateButtons);
  $("learningSetDetail").addEventListener("click", event => {
    if (!event.target.closest('[data-learning-set-next]') || ui.decisionBusy) return;
    const rows = filtered(), index = rows.findIndex(i => i.id === ui.itemId);
    ui.itemId = rows[(index + 1) % rows.length]?.id || null; renderList();
  });
  $("learningSetDetail").addEventListener("submit", async event => {
    const form = event.target.closest('[data-learning-set-decision]'); if (!form) return;
    event.preventDefault(); const item = selectedItem(), decision = event.submitter?.value;
    if (!canReview() || ui.decisionBusy || !item || item.status !== "DRAFT" || !form.elements.note.value.trim() || !["APPROVED", "REJECTED"].includes(decision)) return;
    if (decision === "APPROVED" && (!form.elements.review_confirmed.checked || item.freshness !== "CURRENT")) return;
    const projectId = ui.projectId, user = ui.user, batchId = ui.batchId;
    const rows = filtered(), index = rows.findIndex(i => i.id === item.id), nextId = rows[index + 1]?.id || rows[index - 1]?.id || null;
    const payload = {expected_version: item.version, decision, note: form.elements.note.value, review_confirmed: form.elements.review_confirmed.checked};
    if (decision === "APPROVED") {payload.prompt = form.elements.prompt.value; payload.completion = form.elements.completion.value;}
    ui.decisionBusy = true; updateButtons(); tell(`${item.question_id} 문항의 결정 기록을 저장하는 중입니다.`);
    try {
      await api(`/api/v1/learning/import-items/${item.id}/decisions`, {method: "POST", headers: {...csrfHeaders, "Content-Type": "application/json"}, body: JSON.stringify(payload)});
      if (!current(projectId, user)) return;
      await refresh(batchId, nextId);
      if (current(projectId, user)) tell(`${item.question_id} ${statusLabel(decision)} 기록을 저장했습니다. 원 초안·오답과 결정 이력은 보존됩니다. 학습은 실행하지 않았습니다.`);
    } catch (e) {
      if (current(projectId, user)) {
        await refresh(batchId, item.id);
        if (current(projectId, user)) tell(`결정 저장 확인 실패: ${e.message}. 최신 상태와 결정 이력을 확인하십시오. 중복 승인을 자동 재전송하지 않습니다.`, true);
      }
    } finally {ui.decisionBusy = false; updateButtons();}
  });
  window.dorilabLearningSets = {context, render, importArtifact};
})();
