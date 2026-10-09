from __future__ import annotations

import json
from pathlib import Path

import pytest

from dorilab.worker import run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"
FIXTURE_ROOT = Path("/app/fixtures/demo")


@pytest.mark.parametrize("scenario", ["normal", "request_evidence", "contradiction"])
def test_replay_fixture_keeps_explicit_mode_basis_and_expected_action(client, scenario):
    fixture = json.loads((FIXTURE_ROOT / f"{scenario}.json").read_text(encoding="utf-8"))
    headers = sign_in(client)

    artifact = client.post(
        f"/api/v1/projects/{PROJECT}/artifacts",
        headers=headers,
        data={
            "rights_status": "PUBLIC",
            "edition": "DEMO-REPLAY-1",
            "adopted": "true",
            "applicability_status": "APPLICABLE",
        },
        files={"file": (f"{scenario}.txt", b"synthetic replay evidence\n", "text/plain")},
    )
    assert artifact.status_code == 201
    evidence = client.post(
        f"/api/v1/projects/{PROJECT}/evidence",
        headers=headers,
        json={
            "artifact_id": artifact.json()["id"],
            "display_id": f"REPLAY-{scenario.upper()}",
            "kind": "REFERENCE",
            "basis": fixture["basis"],
            "scope": {},
            "locator": f"fixture/{scenario}",
            "quote": "synthetic replay evidence",
            "provenance": {"fixture": scenario},
        },
    )
    assert evidence.status_code == 201

    updated = client.put(
        f"/api/v1/claims/{CLAIM}",
        headers=headers,
        json={
            "question": fixture["claim_question"],
            "scope": {"unit": "DORI-01", "configuration": "TVAC-03", "run": "RUN-DEMO-01"},
            "expected_version": 1,
        },
    )
    assert updated.status_code == 200
    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": f"replay-{scenario}-0001"},
        json={
            "claim_id": CLAIM,
            "evidence_ids": [evidence.json()["id"]],
            "mode": fixture["mode"],
        },
    )
    assert review.status_code == 202
    assert run_one() is True

    result = client.get(f"/api/v1/jobs/{review.json()['job_id']}").json()
    assert result["job"]["mode"] == "REPLAY"
    assert result["job"]["freshness"] == "CURRENT"
    assert result["model_run"]["validation_status"] == "VALID"
    assert result["model_run"]["receipt"]["execution_mode"] == "REPLAY"
    assert result["model_run"]["receipt"]["basis"] == "SYNTHETIC"
    assert result["model_run"]["receipt"]["profile_id"] == "dorilab-bm1-demo-v1"
    assert result["model_run"]["parsed_output"]["actions"][0]["action"] == fixture["expected_action"]
    assert result["model_run"]["raw_sha256"]
    expected_requests = 1 if fixture["expected_action"] == "REQUEST_EVIDENCE" else 0
    assert len(result["evidence_requests"]) == expected_requests
