from pathlib import Path


ROOT = Path("/app")


def test_autoplay_walks_all_mvp_pages_and_labels_its_boundary():
    html = (ROOT / "apps/web/index.html").read_text()
    script = (ROOT / "apps/web/app.js").read_text()

    assert 'id="autoDemoStart"' in html
    assert 'id="autoDemoPanel"' in html
    assert 'id="autoDemoModeDialog"' in html
    assert 'id="autoDemoReplayStart"' in html
    assert 'id="autoDemoLiveStart"' in html
    assert "DEMO REPLAY" in html
    assert "Local LLM LIVE" in html
    for page in (
        'page: "overview"',
        'page: "profile"',
        'page: "requirements"',
        'page: "gates"',
        'page: "workspace"',
        'page: "closure"',
        'page: "audit"',
    ):
        assert page in script


def test_autoplay_separates_replay_and_qwen_live_without_silent_fallback():
    script = (ROOT / "apps/web/app.js").read_text()
    start = script.index("async function ensureAutoDemoModelRun()")
    end = script.index("function scheduleAutoDemo()", start)
    model_run_boundary = script[start:end]

    assert 'state.autoDemo.mode === "LIVE"' in model_run_boundary
    assert 'throw new Error("QWEN_LIVE_AUTOPLAY_NOT_READY")' in model_run_boundary
    assert 'mode: "LIVE_MODEL_RUN"' in model_run_boundary
    assert 'mode: "REPLAY"' in model_run_boundary
    assert model_run_boundary.count('method: "POST"') == 2
    assert "/decisions" not in model_run_boundary
    assert "catch" not in model_run_boundary
    assert "자동 시연은 사람 결정을 만들지 않습니다" in script
    assert "사람 승인과 공식 종결은 자동 생성하지 않았습니다" in script


def test_qwen_live_autoplay_requires_ready_synthetic_demo_and_pauses_for_human():
    script = (ROOT / "apps/web/app.js").read_text()
    start = script.index("function qwenLiveAutoDemoReady()")
    end = script.index("async function openAutoDemoModeDialog()", start)
    guard = script[start:end]

    assert 'state.status?.remote?.state === "READY"' in guard
    assert 'state.project?.mode === "DEMO"' in guard
    assert 'state.project?.data_policy === "EXTERNAL_SYNTHETIC_ALLOWED"' in guard
    assert 'step.ensureModelRun && state.autoDemo.mode === "LIVE"' in script
    assert "state.autoDemo.playing = false" in script
    assert "자동 진행은 여기서 멈췄습니다" in script


def test_qwen_live_autoplay_shows_preserved_input_output_judgment_and_blackboard_projection():
    html = (ROOT / "apps/web/index.html").read_text()
    script = (ROOT / "apps/web/app.js").read_text()

    for marker in (
        'id="qwenTraceDialog"',
        'id="qwenTraceInput"',
        'id="qwenTraceOutput"',
        'id="qwenTraceDecision"',
        'id="qwenTraceReceipt"',
        'id="qwenTraceBlackboard"',
        'id="qwenTraceContinue"',
        "Local LLM에 보낸 합성 입력",
        "Local LLM 원출력",
        "Local LLM 판단",
        "Blackboard 반영",
    ):
        assert marker in html

    assert "await openQwenTraceDialog()" in script
    assert "await hydrateQwenTraceDialog(detail)" in script
    assert "/api/v1/artifacts/${artifactId}/download" in script
    assert "/api/v1/projects/${state.project.id}/blackboard" in script
    assert "item.source_job_id === jobId" in script
    assert "raw_artifact_id" in script
    assert "validation_status" in script
    assert '$("qwenTraceContinue").disabled = !terminal || !model || state.autoDemo.busy' in script
    assert 'if ($("qwenTraceDialog").open) renderQwenTraceDialog(state.jobDetail)' in script
    assert "if (state.autoDemo.active)" in script
    assert "await openBlackboardDialog()" in script
    assert "사람 결정, Gate 승인과 공식 검증 종결은 이 자동 시연이 만들지 않습니다" in html


def test_quick_demo_adds_one_simple_page_without_replacing_detailed_workbench():
    html = (ROOT / "apps/web/index.html").read_text()
    script = (ROOT / "apps/web/app.js").read_text()

    assert 'data-page="quickdemo"' in html
    assert 'id="quickDemoContent"' in html
    assert '["quickdemo", "빠른 시연", "play"]' in script
    for existing_page in ("overview", "profile", "requirements", "gates", "workspace", "closure", "changes", "audit"):
        assert f'data-page="{existing_page}"' in html

    for copy in (
        "문서를 읽고, 판단하고, 다음 일을 만듭니다",
        "Local LLM이 읽는 근거",
        "Local LLM은 무엇을 판단했나",
        "그래서 무슨 일이 생겼나",
        "마지막 판단은 사람이 합니다",
    ):
        assert copy in script
    assert "if (state.project && (modeChanged || remoteChanged)) renderQuickDemo();" in script
    assert "state.quickDemo.advancedOpen = !state.quickDemo.advancedOpen" in script


def test_quick_demo_uses_explicit_live_generation_without_replay_fallback():
    script = (ROOT / "apps/web/app.js").read_text()
    start = script.index("async function runQuickDemo()")
    end = script.index("function useQuickDemoDetail()", start)
    quick_run = script[start:end]

    assert 'mode: "LIVE_MODEL_RUN"' in quick_run
    assert 'qwenLiveAutoDemoReady()' in quick_run
    assert 'state.project?.data_policy === "EXTERNAL_SYNTHETIC_ALLOWED"' in script
    assert quick_run.count('method: "POST"') == 1
    assert "REPLAY" not in quick_run
    assert "자동 재실행하지 않았습니다" in quick_run
