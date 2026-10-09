from __future__ import annotations

import re
from pathlib import Path


ROOT = Path("/app")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[1]

WEB = ROOT / "apps" / "web"


def source(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_blackboard_observer_is_a_standalone_recording_view_with_two_launch_points():
    index = source("index.html")
    observer_html = source("blackboard-observer.html")

    assert (WEB / "blackboard-observer.js").is_file()
    assert (WEB / "blackboard-observer.css").is_file()
    assert 'id="blackboardObserverOpen"' in index
    assert 'id="autoDemoObserverOpen"' in index
    assert "blackboard-observer.css" in observer_html
    assert "blackboard-observer.js" in observer_html
    assert "Blackboard" in observer_html
    assert re.search(r'aria-live=["\'](?:polite|assertive)["\']', observer_html)


def test_main_window_publishes_one_run_and_answers_late_observer_hello():
    script = source("app.js")

    assert "dorilab-blackboard-observer-v1" in script
    assert "dorilab.demo.observer.v1" in script
    assert "new BroadcastChannel(" in script
    assert "window.open(" in script
    assert "/assets/blackboard-observer.html" in script
    assert "/demo-observer/sessions/" in script
    assert re.search(r"method\s*:\s*['\"]PUT['\"]", script)
    assert "csrfHeaders" in script
    assert "OBSERVER_HELLO" in script
    assert "DEMO_STATE" in script
    assert "publishAutoDemoObserverState" in script
    assert ".postMessage(payload" in script
    for field in (
        "source_instance_id",
        "sequence",
        "project_id",
        "run_key",
        "job_id",
        "mode",
        "step_index",
        "step_title",
        "execution_status",
        "sent_at",
    ):
        assert field in script
    assert re.search(r"sequence\s*:\s*[^,\n]+", script)

    # Opening or refreshing the observer is observational: it may publish current
    # state, but it must never start the autoplay or create another model request.
    start = script.index("function openBlackboardObserver()")
    end = script.index("const gateDescriptions", start)
    launcher = script[start:end]
    assert "fetch(" not in launcher
    assert 'method: "POST"' not in launcher
    assert "startAutoDemo(" not in launcher
    assert "ensureAutoDemoModelRun(" not in launcher

    start_run = script.index("async function startAutoDemo(")
    end_run = script.index("function stopAutoDemo()", start_run)
    run_setup = script[start_run:end_run]
    assert "state.autoDemo.runKey = crypto.randomUUID()" in run_setup
    assert "state.autoDemo.observedJobId = null" in run_setup
    assert 'mode === "LIVE" ? crypto.randomUUID()' not in run_setup


def test_observer_is_read_only_and_fetches_only_current_blackboard_and_job():
    script = source("blackboard-observer.js")

    assert "fetch(" in script
    assert "/api/v1/projects/" in script
    assert "/blackboard" in script
    assert "/api/v1/jobs/" in script
    assert "/demo-observer/sessions/" in script
    assert not re.search(r"method\s*:\s*['\"]POST['\"]", script, re.IGNORECASE)
    assert not re.search(r"method\s*:\s*['\"](?:PUT|PATCH|DELETE)['\"]", script, re.IGNORECASE)
    for forbidden in (
        "/reviews",
        "/v1/generations",
        "/decisions",
        "/blackboard/contributions",
        "/blackboard/work-items",
        "/reports",
        "Idempotency-Key",
        "X-DoriLab-CSRF",
    ):
        assert forbidden not in script


def test_observer_persists_run_identity_in_url_and_filters_projection_to_that_job():
    main = source("app.js")
    observer = source("blackboard-observer.js")

    assert "new URLSearchParams(" in main
    assert "window.location.search" in observer
    assert "URLSearchParams" in observer
    for query_key in ("project_id", "source_id", "run_key", "job_id", "mode"):
        assert query_key in main
        assert query_key in observer

    # The project Blackboard endpoint is a projection of many runs. The observer
    # must select records linked to the one Job shown by the autoplay.
    assert "source_job_id" in observer
    assert "job_id" in observer
    assert ".filter(" in observer
    assert re.search(r"source_job_id[^\n]{0,180}job", observer, re.IGNORECASE)
    assert re.search(r"job_id[^\n]{0,180}job", observer, re.IGNORECASE)

    # board_events do not carry source_job_id. They are safe to show only when
    # their object_id belongs to a contribution/work item/orchestration run that
    # was already selected for this Job.
    assert "object_id" in observer
    assert re.search(r"events[^;]{0,1400}\.filter\(", observer, re.IGNORECASE | re.DOTALL)
    assert re.search(
        r"(?:related|relevant|visible|linked|run)[A-Za-z_]*(?:Ids|_ids)",
        observer,
        re.IGNORECASE,
    )


def test_observer_resets_on_new_run_and_rejects_duplicate_or_out_of_order_messages():
    script = source("blackboard-observer.js")

    # Run changes clear the view before applying the new run. A message identity
    # set and sent_at watermark prevent duplicate/stale delivery from regressing it.
    assert re.search(r"run(?:Key|_key)", script)
    assert re.search(r"reset", script, re.IGNORECASE)
    assert re.search(r"(?:\.clear\(\)|new\s+(?:Set|Map)\s*\(\))", script)
    assert "source_instance_id" in script
    assert "sequence" in script
    assert "sent_at" in script
    assert re.search(r"(?:stale|out.?of.?order|lastSequence|last_sequence|watermark)", script, re.IGNORECASE)
    assert re.search(r"new\s+Set\s*\(", script)
    assert re.search(r"(?:\.has\(|duplicate|dedup)", script, re.IGNORECASE)

    # A popup is pinned to the parent source_id. Messages and delayed GETs from
    # another source/run must not overwrite the cards currently being recorded.
    assert re.search(
        r"source_instance_id[^\n]{0,220}(?:!==|!=)[^\n]{0,120}(?:sourceInstanceId|source_id|sourceId)",
        script,
        re.IGNORECASE,
    )
    assert re.search(r"(?:request|poll|generation|epoch|token)", script, re.IGNORECASE)


def test_observer_has_recording_safe_states_cards_metadata_and_expandable_raw_json():
    html = source("blackboard-observer.html")
    script = source("blackboard-observer.js")
    styles = source("blackboard-observer.css")
    combined = "\n".join((html, script, styles))

    for state_name in ("EMPTY", "DISCONNECTED", "ERROR"):
        assert state_name in combined.upper()
    for field in ("actor_type", "actor_id", "created_at", "updated_at", "assigned_role"):
        assert field in script

    assert "<details" in html or "<details" in script
    assert "<summary" in html or "<summary" in script
    assert "JSON.stringify" in script
    assert re.search(r"(?:card|tree)", combined, re.IGNORECASE)
    assert re.search(r"(?:highlight|updated|flash)", script, re.IGNORECASE)
    assert re.search(r"(?:highlight|updated|flash)", styles, re.IGNORECASE)
    assert "@keyframes" in styles


def test_observer_labels_replay_live_and_does_not_claim_unobserved_agent_reads():
    script = source("blackboard-observer.js")
    html = source("blackboard-observer.html")
    combined = f"{html}\n{script}"

    assert "REPLAY" in combined
    assert "LIVE" in combined
    assert "actor" in combined.lower()
    assert "assigned_role" in script
    # There is no server-side read-event contract. The view may show a stored
    # dependency/assignment, but must not manufacture an agent-read assertion.
    for invented_claim in ("AGENT_READ", "READ_BY_AGENT", "에이전트가 읽음"):
        assert invented_claim not in combined
