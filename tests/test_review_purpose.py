from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from dorilab.db import connection
from dorilab.worker import run_one

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
SEED_CLAIM = "00000000-0000-4000-8000-000000000101"


def claim_body(*, display_id: str, review_purpose: str | None = None) -> dict:
    body = {
        "display_id": display_id,
        "question": "현재 합성 자료가 지정된 검토 목적의 판단에 충분한가?",
        "review_target": "BM1",
        "scope": {
            "unit": "DORI-PURPOSE-01",
            "configuration": "PURPOSE-DEMO-A",
            "run": "RUN-PURPOSE-01",
        },
    }
    if review_purpose is not None:
        body["review_purpose"] = review_purpose
    return body


def create_claim(client, headers, *, purpose: str | None, prefix: str = "PURPOSE") -> dict:
    display_id = f"{prefix}-{uuid4().hex[:10].upper()}"
    response = client.post(
        f"/api/v1/projects/{PROJECT}/claims",
        headers=headers,
        json=claim_body(display_id=display_id, review_purpose=purpose),
    )
    assert response.status_code == 201, response.text
    return response.json()


def requirement_body(*, claim_id: str, review_purpose: str | None) -> dict:
    body = {
        "display_id": f"REQ-{uuid4().hex[:10].upper()}",
        "level": "EQUIPMENT",
        "parent_ref": "SYS-THERM-SYNTHETIC",
        "statement": "합성 검토 자료와 지정한 검토 목적을 현재 Claim에 연결한다.",
        "verification_method": "자료 검토",
        "owner": "열설계 담당",
        "claim_id": claim_id,
        "claim_label": "PURPOSE-CLAIM",
        "source_chapter": 19,
        "sort_order": 20,
    }
    if review_purpose is not None:
        body["review_purpose"] = review_purpose
    return body


def assert_coded_purpose_error(response, purpose: str, status: str) -> str:
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert purpose in detail
    assert status in detail
    assert re.search(r"\b[A-Z][A-Z0-9_]{3,}\b", detail), detail
    return detail


def create_review(client, headers, claim_id: str, key: str):
    return client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": key},
        json={"claim_id": claim_id, "evidence_ids": [], "mode": "SIMULATED"},
    )


def closure_request(client, headers, claim_id: str, claim_version: int = 1):
    return client.post(
        f"/api/v1/claims/{claim_id}/closures",
        headers=headers,
        json={
            "result": "SATISFIED",
            "closure_basis": "COMPLIANCE",
            "note": "검토 목적 경계가 종결 전에 적용되는지 확인한다.",
            "expected_claim_version": claim_version,
            "expected_project_version": 1,
        },
    )


def test_seed_and_legacy_records_expose_explicit_review_purpose_without_inference(client):
    headers = sign_in(client)

    seed = client.get(f"/api/v1/claims/{SEED_CLAIM}")
    assert seed.status_code == 200, seed.text
    assert seed.json()["claim"]["display_id"] == "THM-041"
    assert seed.json()["claim"]["review_purpose"] == "INPUT_READINESS"
    assert seed.json()["revisions"][0]["review_purpose"] == "INPUT_READINESS"

    requirements = client.get(f"/api/v1/projects/{PROJECT}/requirements")
    assert requirements.status_code == 200, requirements.text
    by_display_id = {item["display_id"]: item for item in requirements.json()}
    assert by_display_id["THM-041"]["review_purpose"] == "INPUT_READINESS"
    assert by_display_id["THM-041"]["claim_id"] == SEED_CLAIM
    assert by_display_id["THM-042"]["review_purpose"] == "PRODUCT_PERFORMANCE"
    assert by_display_id["THM-042"]["claim_id"] is None

    # Omission is preserved as an explicit legacy state.  A question that sounds
    # like input-readiness must not make the server infer that purpose.
    legacy = create_claim(client, headers, purpose=None, prefix="LEGACY")
    assert legacy["review_purpose"] == "UNSPECIFIED"
    legacy_detail = client.get(f"/api/v1/claims/{legacy['id']}").json()
    assert legacy_detail["claim"]["review_purpose"] == "UNSPECIFIED"
    assert legacy_detail["revisions"][0]["review_purpose"] == "UNSPECIFIED"

    missing_review = create_review(client, headers, legacy["id"], "purpose-unspecified-review")
    assert_coded_purpose_error(missing_review, "UNSPECIFIED", "PURPOSE_UNSPECIFIED")

    approver_headers = sign_in(client, "approver@demo")
    assert_coded_purpose_error(
        closure_request(client, approver_headers, legacy["id"]),
        "UNSPECIFIED",
        "PURPOSE_UNSPECIFIED",
    )

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS count FROM review_jobs WHERE claim_id=%s", (legacy["id"],))
        assert cur.fetchone()["count"] == 0
        cur.execute("SELECT count(*) AS count FROM verification_closures WHERE claim_id=%s", (legacy["id"],))
        assert cur.fetchone()["count"] == 0


def test_additive_migration_keeps_legacy_rows_unspecified_without_text_or_id_inference():
    schema = f"review_purpose_legacy_{uuid4().hex}"
    migration = Path("/app/migrations/012_review_purpose.sql").read_text(encoding="utf-8")
    tables = (
        "claims",
        "claim_revisions",
        "requirements",
        "context_snapshots",
        "verification_closures",
    )
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
        cur.execute(f'SET LOCAL search_path TO "{schema}"')
        for table in tables:
            cur.execute(f"CREATE TABLE {table} (id uuid PRIMARY KEY)")
            cur.execute(f"INSERT INTO {table}(id) VALUES (%s)", (uuid4(),))

        cur.execute(migration)
        for table in tables:
            cur.execute(f"SELECT review_purpose FROM {table}")
            assert cur.fetchone()["review_purpose"] == "UNSPECIFIED"
        cur.execute("SELECT source_snapshot_id FROM verification_closures")
        assert cur.fetchone()["source_snapshot_id"] is None

        cur.execute("SET LOCAL search_path TO public")
        cur.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_product_performance_is_stored_but_current_review_and_closure_reject_it(client):
    engineer_headers = sign_in(client)
    claim = create_claim(client, engineer_headers, purpose="PRODUCT_PERFORMANCE", prefix="PERF")
    assert claim["review_purpose"] == "PRODUCT_PERFORMANCE"

    review = create_review(client, engineer_headers, claim["id"], "purpose-product-review")
    assert_coded_purpose_error(review, "PRODUCT_PERFORMANCE", "PERFORMANCE_ASSESSMENT_UNSUPPORTED")

    approver_headers = sign_in(client, "approver@demo")
    assert_coded_purpose_error(
        closure_request(client, approver_headers, claim["id"]),
        "PRODUCT_PERFORMANCE",
        "PERFORMANCE_ASSESSMENT_UNSUPPORTED",
    )

    invalid_create = client.post(
        f"/api/v1/projects/{PROJECT}/claims",
        headers=engineer_headers,
        json=claim_body(display_id=f"BAD-{uuid4().hex[:10]}", review_purpose="GENERAL_REVIEW"),
    )
    assert invalid_create.status_code == 422

    invalid_update = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=engineer_headers,
        json={
            "question": claim["question"],
            "scope": claim["scope"],
            "review_purpose": "GENERAL_REVIEW",
            "expected_version": 1,
        },
    )
    assert invalid_update.status_code == 422


def test_requirement_purpose_mismatch_is_rejected_and_unspecified_remains_pending(client):
    headers = sign_in(client)
    claim = create_claim(client, headers, purpose="INPUT_READINESS", prefix="REQ-SCOPE")

    mismatched = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=headers,
        json=requirement_body(claim_id=claim["id"], review_purpose="PRODUCT_PERFORMANCE"),
    )
    assert mismatched.status_code == 422, mismatched.text
    mismatch_detail = mismatched.json()["detail"]
    assert isinstance(mismatch_detail, str)
    assert "PRODUCT_PERFORMANCE" in mismatch_detail

    invalid = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=headers,
        json=requirement_body(claim_id=claim["id"], review_purpose="GENERAL_REVIEW"),
    )
    assert invalid.status_code == 422

    pending = client.post(
        f"/api/v1/projects/{PROJECT}/requirements",
        headers=headers,
        json=requirement_body(claim_id=claim["id"], review_purpose=None),
    )
    assert pending.status_code == 201, pending.text
    assert pending.json()["review_purpose"] == "UNSPECIFIED"

    projection = client.get(f"/api/v1/projects/{PROJECT}/closure")
    assert projection.status_code == 200, projection.text
    claim_projection = next(item for item in projection.json()["claims"] if item["claim"]["id"] == claim["id"])
    checks = {item["code"]: item for item in claim_projection["checks"]}
    assert checks["REVIEW_PURPOSE"]["satisfied"] is True
    assert checks["REQUIREMENT_REVISION"]["satisfied"] is False
    assert "UNSPECIFIED" in str(checks["REQUIREMENT_REVISION"])
    assert claim_projection["ready_for_satisfied"] is False

    created = create_review(client, headers, claim["id"], "purpose-requirement-version")
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    updated_requirement = client.put(
        f"/api/v1/requirements/{pending.json()['id']}/purpose",
        headers=headers,
        json={"review_purpose": "INPUT_READINESS", "expected_version": 1},
    )
    assert updated_requirement.status_code == 200, updated_requirement.text
    updated_payload = updated_requirement.json()
    updated_row = updated_payload.get("requirement", updated_payload)
    assert updated_row["review_purpose"] == "INPUT_READINESS"
    assert updated_row["version"] == 2
    assert client.get(f"/api/v1/jobs/{job_id}").json()["job"]["freshness"] == "STALE"

    claim_detail = client.get(f"/api/v1/claims/{claim['id']}").json()
    assert claim_detail["claim"]["version"] == 2
    assert claim_detail["claim"]["review_purpose"] == "INPUT_READINESS"
    assert [(item["version"], item["review_purpose"]) for item in claim_detail["revisions"]] == [
        (2, "INPUT_READINESS"),
        (1, "INPUT_READINESS"),
    ]

    conflict = client.put(
        f"/api/v1/requirements/{pending.json()['id']}/purpose",
        headers=headers,
        json={"review_purpose": "INPUT_READINESS", "expected_version": 1},
    )
    assert conflict.status_code == 409


def test_purpose_change_versions_claim_stales_job_and_freezes_snapshot_metadata(client):
    headers = sign_in(client)
    claim = create_claim(client, headers, purpose="INPUT_READINESS", prefix="VERSION")
    created = create_review(client, headers, claim["id"], "purpose-version-review")
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    before = client.get(f"/api/v1/jobs/{job_id}").json()
    assert before["snapshot"]["review_purpose"] == "INPUT_READINESS"
    assert before["assessment_scope"] == before["snapshot"]["assessment_scope"]
    frozen_label = before["assessment_scope"]["label"]

    changed = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=headers,
        json={
            "question": "현재 합성 산출물의 제품 성능을 평가할 준비가 되었는가?",
            "scope": {**claim["scope"], "run": "RUN-PURPOSE-02"},
            "review_purpose": "PRODUCT_PERFORMANCE",
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    assert changed.json()["review_purpose"] == "PRODUCT_PERFORMANCE"

    stale = client.get(f"/api/v1/jobs/{job_id}").json()
    assert stale["job"]["freshness"] == "STALE"
    assert stale["snapshot"]["review_purpose"] == "INPUT_READINESS"
    assert stale["assessment_scope"]["review_purpose"] == "INPUT_READINESS"
    assert stale["assessment_scope"]["label"] == frozen_label

    replayed = create_review(client, headers, claim["id"], "purpose-version-review")
    assert replayed.status_code == 202, replayed.text
    assert replayed.json()["job_id"] == job_id
    assert replayed.json()["idempotent_replay"] is True
    assert replayed.json()["assessment_scope"] == before["assessment_scope"]
    fresh_attempt = create_review(client, headers, claim["id"], "purpose-version-review-new")
    assert_coded_purpose_error(
        fresh_attempt,
        "PRODUCT_PERFORMANCE",
        "PERFORMANCE_ASSESSMENT_UNSUPPORTED",
    )
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS count FROM review_jobs WHERE claim_id=%s", (claim["id"],))
        assert cur.fetchone()["count"] == 1

    # Omitting the optional purpose on a later update preserves the current
    # value rather than falling back to UNSPECIFIED.
    preserved = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=headers,
        json={
            "question": "변경된 형상에서도 제품 성능 검토 목적을 유지하는가?",
            "scope": {**claim["scope"], "run": "RUN-PURPOSE-03"},
            "expected_version": 2,
        },
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["version"] == 3
    assert preserved.json()["review_purpose"] == "PRODUCT_PERFORMANCE"

    detail = client.get(f"/api/v1/claims/{claim['id']}").json()
    assert [(item["version"], item["review_purpose"]) for item in detail["revisions"]] == [
        (3, "PRODUCT_PERFORMANCE"),
        (2, "PRODUCT_PERFORMANCE"),
        (1, "INPUT_READINESS"),
    ]


def test_legacy_unspecified_snapshot_is_readable_but_cannot_be_newly_accepted(client):
    engineer_headers = sign_in(client)
    created = create_review(client, engineer_headers, SEED_CLAIM, "legacy-purpose-acceptance")
    assert created.status_code == 202, created.text
    assert run_one() is True
    job_id = created.json()["job_id"]
    current = client.get(f"/api/v1/jobs/{job_id}").json()
    assert current["job"]["status"] == "AWAITING_REVIEW"

    # Model an additive migration of a historical Snapshot.  It remains
    # inspectable, but its missing purpose cannot authorize a new acceptance.
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE context_snapshots SET review_purpose='UNSPECIFIED' WHERE id=%s",
            (current["snapshot"]["id"],),
        )

    legacy = client.get(f"/api/v1/jobs/{job_id}")
    assert legacy.status_code == 200, legacy.text
    legacy_body = legacy.json()
    assert legacy_body["snapshot"]["review_purpose"] == "UNSPECIFIED"
    assert legacy_body["assessment_scope"]["status"] == "PURPOSE_UNSPECIFIED"

    reviewer_headers = sign_in(client, "reviewer@demo")
    accepted = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "ACCEPTED",
            "expected_job_version": legacy_body["job"]["version"],
            "note": "목적이 없는 과거 Snapshot을 새로 수용해서는 안 됨",
        },
    )
    assert_coded_purpose_error(accepted, "UNSPECIFIED", "PURPOSE_UNSPECIFIED")
    after_rejection = client.get(f"/api/v1/jobs/{job_id}").json()
    assert after_rejection["job"]["status"] == "AWAITING_REVIEW"
    assert after_rejection["decisions"] == []


def test_web_uses_server_assessment_scope_label_instead_of_claiming_performance(client):
    sign_in(client)
    script = Path("/app/apps/web/app.js").read_text(encoding="utf-8")
    assert "function assessmentScopeNotice(scope)" in script
    assert "scope.label" in script
    assert "scope.result_scope" in script
    assert "scope.product_performance_status" in script
    assert re.search(r"assessmentScopeNotice\([^)]*assessment_scope", script)
