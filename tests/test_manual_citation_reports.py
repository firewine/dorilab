from __future__ import annotations

from dorilab.db import connection
from dorilab.worker import run_one

from conftest import sign_in
from test_manual_citations import CLAIM, PROJECT, create_evidence, evidence_body, upload_parsed_pdf


def test_report_keeps_snapshot_citation_receipt_and_marks_changed_source_stale(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    evidence = create_evidence(client, headers, evidence_body(artifact, parsed["chunks"][2], "CITE-REPORT")).json()
    created = client.post(f"/api/v1/projects/{PROJECT}/reviews",
                          headers={**headers, "Idempotency-Key": "citation-report"},
                          json={"claim_id": CLAIM, "evidence_ids": [evidence["id"]], "mode": "SIMULATED"})
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    assert run_one()
    detail = client.get(f"/api/v1/jobs/{job_id}").json()
    frozen = detail["snapshot"]["source_verifications"][evidence["id"]]
    assert frozen["evidence_version"] == 1
    assert frozen["semantic_support"] == "UNASSESSED"
    reviewer = sign_in(client, "reviewer@demo")
    decision = client.post(f"/api/v1/reviews/{job_id}/decisions", headers=reviewer,
                           json={"disposition": "ACCEPTED", "expected_job_version": detail["job"]["version"]})
    assert decision.status_code == 201, decision.text
    exported = client.post(f"/api/v1/jobs/{job_id}/reports", headers=reviewer)
    assert exported.status_code == 201, exported.text
    report = client.get(f"/api/v1/reports/{exported.json()['id']}/download")
    assert report.status_code == 200, report.text
    assert "VALID / CURRENT / CITATION_MATCHED" in report.text
    assert frozen["parser_receipt_sha256"] in report.text
    assert "의미적 지지·적용성·제품 적합성" in report.text
    assert "공식 시험 승인" in report.text

    # Source metadata corruption is simulated only in the isolated test database.
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE artifact_versions SET edition='REV-B' WHERE id=%s", (artifact["id"],))
    later_export = client.post(f"/api/v1/jobs/{job_id}/reports", headers=reviewer)
    assert later_export.status_code == 201, later_export.text
    later_report = client.get(f"/api/v1/reports/{later_export.json()['id']}/download")
    assert "현행성: STALE" in later_report.text
    assert "Snapshot의 원문 위치 검증: VALID / CURRENT / CITATION_MATCHED" in later_report.text
    later_detail = client.get(f"/api/v1/jobs/{job_id}").json()
    assert later_detail["snapshot"]["source_verifications"][evidence["id"]] == frozen
    assert len(later_detail["decisions"]) == 1
    # The original export is immutable, and its historical CURRENT label is not rewritten.
    assert client.get(f"/api/v1/reports/{exported.json()['id']}/download").content == report.content
