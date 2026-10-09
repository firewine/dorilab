from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from dorilab.api import app
from dorilab.db import connection
from dorilab.worker import run_one

from conftest import sign_in


SEED_PROJECT = "00000000-0000-4000-8000-000000000001"
ROOT = Path("/app")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[1]


def _seed_project_footprint() -> dict:
    """Capture rows whose history must not be changed by a new walkthrough."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT display_id,framework,adoption_status,current_phase,version
               FROM projects WHERE id=%s""",
            (SEED_PROJECT,),
        )
        project = cur.fetchone()
        counts = {}
        for name, table in (
            ("audit", "audit_events"),
            ("jobs", "review_jobs"),
            ("requirements", "requirements"),
            ("human_reviews", "human_reviews"),
            ("gate_decisions", "gate_decisions"),
            ("closures", "verification_closures"),
        ):
            cur.execute(f"SELECT count(*) AS count FROM {table} WHERE project_id=%s", (SEED_PROJECT,))
            counts[name] = cur.fetchone()["count"]
    return {"project": project, "counts": counts}


def _walkthrough_counts(project_id: str) -> dict:
    with connection() as conn, conn.cursor() as cur:
        result = {}
        for name, table in (
            ("model_runs", "model_runs"),
            ("human_reviews", "human_reviews"),
            ("gate_decisions", "gate_decisions"),
            ("closures", "verification_closures"),
        ):
            cur.execute(f"SELECT count(*) AS count FROM {table} WHERE project_id=%s", (project_id,))
            result[name] = cur.fetchone()["count"]
    return result


def test_setup_walkthrough_persists_one_replay_rag_run_and_blackboard_lineage(client):
    fixture_path = "/api/v1/demo/setup-fixture"
    assert client.get(fixture_path).status_code == 401
    headers = sign_in(client)

    seed_before = _seed_project_footprint()
    fixture_response = client.get(fixture_path)
    assert fixture_response.status_code == 200, fixture_response.text
    assert fixture_response.headers["cache-control"] == "no-store"
    setup = fixture_response.json()
    fixture = setup["fixture"]
    document_text = setup["document_text"]

    project_body = deepcopy(fixture["project"]["body"])
    project_body["display_id"] = f"DORI-SETUP-{uuid4().hex[:8].upper()}"
    created_project = client.post(fixture["project"]["path"], headers=headers, json=project_body)
    assert created_project.status_code == 201, created_project.text
    project = created_project.json()
    project_id = project["id"]
    assert project["mode"] == "DEMO"
    assert project["data_policy"] == "EXTERNAL_SYNTHETIC_ALLOWED"

    document_profile = client.put(
        fixture["profile_document"]["path_template"].format(project_id=project_id),
        headers=headers,
        json=fixture["profile_document"]["body"],
    )
    assert document_profile.status_code == 200, document_profile.text
    assert document_profile.json()["status"] == fixture["profile_document"]["expected_status"]

    claim_response = client.post(
        fixture["claim"]["path_template"].format(project_id=project_id),
        headers=headers,
        json=fixture["claim"]["body"],
    )
    assert claim_response.status_code == 201, claim_response.text
    claim = claim_response.json()

    requirement_body = deepcopy(fixture["requirement"]["body"])
    requirement_body["claim_id"] = claim["id"]
    requirement_response = client.post(
        fixture["requirement"]["path_template"].format(project_id=project_id),
        headers=headers,
        json=requirement_body,
    )
    assert requirement_response.status_code == 201, requirement_response.text
    requirement = requirement_response.json()
    assert requirement["claim_id"] == claim["id"]
    assert requirement["linked_claim_version"] == claim["version"]

    upload_form = deepcopy(fixture["document"]["form"])
    upload_form["adopted"] = str(upload_form["adopted"]).lower()
    source_response = client.post(
        fixture["document"]["path_template"].format(project_id=project_id),
        headers=headers,
        data=upload_form,
        files={
            "file": (
                fixture["document"]["filename"],
                document_text.encode("utf-8"),
                fixture["document"]["content_type"],
            )
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    assert source["sha256"] == hashlib.sha256(document_text.encode("utf-8")).hexdigest()

    parse_path = fixture["parse"]["path_template"].format(artifact_id=source["id"])
    parsed_response = client.post(parse_path, headers=headers)
    assert parsed_response.status_code == 201, parsed_response.text
    parsed = parsed_response.json()
    assert parsed["parser_run"]["status"] == "COMPLETED"
    assert parsed["chunks"]

    chunk_detail = client.get(
        fixture["parse"]["chunk_detail_path_template"].format(artifact_id=source["id"])
    )
    assert chunk_detail.status_code == 200, chunk_detail.text
    assert chunk_detail.json()["artifact"]["id"] == source["id"]
    assert chunk_detail.json()["parser_run"]["id"] == parsed["parser_run"]["id"]
    assert chunk_detail.json()["chunks"] == parsed["chunks"]

    repeated_parse = client.post(parse_path, headers=headers)
    assert repeated_parse.status_code == 201, repeated_parse.text
    assert repeated_parse.json()["parser_run"]["id"] == parsed["parser_run"]["id"]
    assert repeated_parse.json()["chunks"] == parsed["chunks"]

    run_suffix = uuid4().hex
    retrieval_body = deepcopy(fixture["retrieval"]["body"])
    retrieval_body["claim_id"] = claim["id"]
    retrieval_body["artifact_ids"] = [source["id"]]
    retrieval_key = f"{fixture['retrieval']['idempotency_key_prefix']}:{run_suffix}"
    retrieval_path = fixture["retrieval"]["path_template"].format(project_id=project_id)
    retrieval_response = client.post(
        retrieval_path,
        headers={**headers, "Idempotency-Key": retrieval_key},
        json=retrieval_body,
    )
    assert retrieval_response.status_code == 201, retrieval_response.text
    retrieval = retrieval_response.json()
    retrieval_run = retrieval["run"]
    selected = [item for item in retrieval["results"] if item["selected"]]
    assert retrieval_run["status"] == "COMPLETED"
    assert retrieval_run["receipt"]["artifact_filter"] == [source["id"]]
    assert selected
    assert {item["artifact_id"] for item in retrieval["results"]} == {source["id"]}
    assert all(item["reason"] == "SELECTED_FTS" for item in selected)

    repeated_retrieval = client.post(
        retrieval_path,
        headers={**headers, "Idempotency-Key": retrieval_key},
        json=retrieval_body,
    )
    assert repeated_retrieval.status_code == 201, repeated_retrieval.text
    assert repeated_retrieval.json()["idempotent_replay"] is True
    assert repeated_retrieval.json()["run"]["id"] == retrieval_run["id"]

    review_body = deepcopy(fixture["live_review"]["body"])
    review_body.update(
        {
            "claim_id": claim["id"],
            "retrieval_run_id": retrieval_run["id"],
            "mode": "REPLAY",
        }
    )
    review_key = f"setup-walkthrough-replay:{run_suffix}"
    review_path = fixture["live_review"]["path_template"].format(project_id=project_id)
    review_response = client.post(
        review_path,
        headers={**headers, "Idempotency-Key": review_key},
        json=review_body,
    )
    assert review_response.status_code == 202, review_response.text
    job_id = review_response.json()["job_id"]

    repeated_review = client.post(
        review_path,
        headers={**headers, "Idempotency-Key": review_key},
        json=review_body,
    )
    assert repeated_review.status_code == 202, repeated_review.text
    assert repeated_review.json()["idempotent_replay"] is True
    assert repeated_review.json()["job_id"] == job_id

    queued = client.get(f"/api/v1/jobs/{job_id}").json()
    assert queued["snapshot"]["retrieval_run_id"] == retrieval_run["id"]
    assert queued["snapshot"]["retrieved_chunk_ids"] == [item["chunk_id"] for item in selected]
    assert queued["snapshot"]["retrieval_receipt"]["artifact_filter"] == [source["id"]]

    assert run_one() is True
    completed = client.get(f"/api/v1/jobs/{job_id}").json()
    assert completed["job"]["status"] == "AWAITING_REVIEW"
    assert completed["model_run"]["validation_status"] == "VALID"
    assert completed["decisions"] == []

    board = client.get(f"/api/v1/projects/{project_id}/blackboard")
    assert board.status_code == 200, board.text
    projection = board.json()
    contribution = next(item for item in projection["contributions"] if item["source_job_id"] == job_id)
    assert contribution["actor_type"] == "MODEL"
    chunk_dependencies = [
        item
        for item in projection["dependencies"]
        if item["source_job_id"] == job_id and item["upstream_object_type"] == "DOCUMENT_CHUNK"
    ]
    assert {item["upstream_object_id"] for item in chunk_dependencies} == {
        item["chunk_id"] for item in selected
    }
    assert all(item["downstream_object_id"] == contribution["id"] for item in chunk_dependencies)

    completed_replay = client.post(
        review_path,
        headers={**headers, "Idempotency-Key": review_key},
        json=review_body,
    )
    assert completed_replay.status_code == 202, completed_replay.text
    assert completed_replay.json()["idempotent_replay"] is True
    assert completed_replay.json()["job_id"] == job_id
    assert run_one() is False

    counts = _walkthrough_counts(project_id)
    assert counts == {
        "model_runs": 1,
        "human_reviews": 0,
        "gate_decisions": 0,
        "closures": 0,
    }
    assert _seed_project_footprint() == seed_before

    # A fresh browser/API client can reconstruct the run exclusively from the
    # persisted PostgreSQL and artifact-store records.
    with TestClient(app) as reloaded_client:
        sign_in(reloaded_client)
        assert reloaded_client.get(f"/api/v1/projects/{project_id}").json()["display_id"] == project_body["display_id"]
        assert reloaded_client.get(f"/api/v1/requirements/{requirement['id']}").json()["claim_id"] == claim["id"]
        assert reloaded_client.get(f"/api/v1/artifacts/{source['id']}/chunks").json()["parser_run"]["id"] == parsed["parser_run"]["id"]
        assert reloaded_client.get(f"/api/v1/retrievals/{retrieval_run['id']}").json()["run"]["id"] == retrieval_run["id"]
        assert reloaded_client.get(f"/api/v1/jobs/{job_id}").json()["model_run"]["validation_status"] == "VALID"
        reloaded_board = reloaded_client.get(f"/api/v1/projects/{project_id}/blackboard").json()
        assert any(item["source_job_id"] == job_id for item in reloaded_board["contributions"])


def test_detailed_autoplay_uses_setup_or_summary_and_never_posts_a_decision():
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")
    setup_script = (ROOT / "apps/web/setup-demo.js").read_text(encoding="utf-8")

    assert 'id="autoDemoWalkthrough"' in html
    assert 'value="SETUP"' in html
    assert 'value="SUMMARY"' in html
    assert 'id="setupDemoDialog"' in html
    assert 'id="setupDemoSave"' in html
    assert '/assets/setup-demo.js' in html

    # The detailed route must load immutable fixture inputs and execute the
    # actual business endpoints once per stage rather than synthesizing rows in
    # browser state. The human boundary remains outside autoplay.
    for endpoint in (
        "/api/v1/projects",
        "/documents/",
        "/claims",
        "/requirements",
        "/artifacts",
        "/parse",
        "/chunks",
        "/retrievals",
    ):
        assert endpoint in setup_script
    assert "/api/v1/demo/setup-fixture" in script
    assert "/reviews" in script
    assert 'mode: "LIVE_MODEL_RUN"' in script
    assert 'mode: "REPLAY"' in script
    assert 'walkthrough === "SETUP"' in script
    assert 'state.autoDemo.walkthrough === "SUMMARY"' in script
    assert "autoDemoSteps = detailed ? setupDemoSteps : summaryAutoDemoSteps" in script

    steps_source = setup_script[
        setup_script.index("const setupDemoSteps = [") : setup_script.index("];", setup_script.index("const setupDemoSteps = ["))
    ]
    assert steps_source.count("{chapter:") == 26
    for action in (
        "project-save",
        "document-save",
        "claim-save",
        "requirement-save",
        "upload-save",
        "parse",
        "search",
        "input-check",
    ):
        assert f'action: "{action}"' in steps_source

    write_once = setup_script[
        setup_script.index("async function setupWriteOnce(") : setup_script.index("function setupPost(")
    ]
    assert "Object.hasOwn(ctx.saved, key)" in write_once
    assert write_once.index("ctx.attempted.add(key)") < write_once.index("const result = await write()")
    assert write_once.index("const result = await write()") < write_once.index("ctx.saved[key] = result")
    write_keys = set(re.findall(r'setupWriteOnce\("([^"]+)"', setup_script))
    assert write_keys == {
        "project",
        "profile-document",
        "claim",
        "requirement",
        "artifact",
        "parser",
        "retrieval",
    }
    assert '"Idempotency-Key": `setup-rag:${runKey}`' in setup_script

    assert "/decisions" not in setup_script
    assert "/quality-assessments" not in setup_script
    assert "/closures" not in setup_script
