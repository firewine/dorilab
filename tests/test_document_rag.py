from __future__ import annotations

import json
from io import BytesIO
from uuid import UUID

from dorilab.db import connection
from dorilab.worker import run_one
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def upload_document(
    client,
    headers,
    *,
    name="thermal-source.md",
    content=None,
    content_type="text/markdown",
    rights="PUBLIC",
    edition="REV-A",
    adopted="true",
    applicability="APPLICABLE",
    purpose="OPERATIONAL_EVIDENCE",
    project=PROJECT,
):
    content = content or (
        "# Thermal correlation input\n\n"
        "The current thermal correlation requires a component dissipation power map and "
        "a traceable heat-source location for every modeled component.\n\n"
        "# Configuration limits\n\n"
        "The evidence applies to the TVAC-03 configuration. Boundary conditions and the "
        "as-run identity must be checked separately before engineering acceptance.\n"
    ).encode()
    response = client.post(
        f"/api/v1/projects/{project}/artifacts",
        headers=headers,
        files={"file": (name, content, content_type)},
        data={
            "rights_status": rights,
            "edition": edition,
            "adopted": adopted,
            "applicability_status": applicability,
            "usage_purpose": purpose,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def parse_document(client, headers, artifact_id):
    response = client.post(f"/api/v1/artifacts/{artifact_id}/parse", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def retrieve(client, headers, query, *, key, artifact_ids=None, project=PROJECT, claim=CLAIM, top_k=4):
    response = client.post(
        f"/api/v1/projects/{project}/retrievals",
        headers={**headers, "Idempotency-Key": key},
        json={
            "claim_id": claim,
            "query": query,
            "artifact_ids": artifact_ids or [],
            "top_k": top_k,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def text_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Thermal dissipation power map TVAC-03) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def test_markdown_parse_fts_receipt_and_context_snapshot(client):
    headers = sign_in(client)
    source = upload_document(client, headers)
    parsed = parse_document(client, headers, source["id"])

    run = parsed["parser_run"]
    assert run["status"] == "COMPLETED"
    assert run["parser_version"] == "dorilab-parser-v1"
    assert run["chunker_version"] == "paragraph-1600-v1"
    assert run["chunk_count"] == 2
    assert len(run["receipt_sha256"]) == 64
    assert parsed["chunks"][0]["locator"].startswith("text document, lines")
    assert parsed["chunks"][0]["section_path"] == ["Thermal correlation input"]

    repeated = parse_document(client, headers, source["id"])
    assert repeated["parser_run"]["id"] == run["id"]
    assert repeated["chunks"] == parsed["chunks"]

    retrieval = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-0001",
        artifact_ids=[source["id"]],
        top_k=2,
    )
    retrieval_run = retrieval["run"]
    selected = [item for item in retrieval["results"] if item["selected"]]
    assert retrieval_run["status"] == "COMPLETED"
    assert retrieval_run["index_version"] == "postgres-fts-simple-v1"
    assert retrieval_run["selected_count"] == 1
    assert retrieval_run["receipt"]["query"] == "component dissipation power map"
    assert retrieval_run["receipt"]["results"][0]["reason"] == "SELECTED_FTS"
    assert len(retrieval_run["receipt_sha256"]) == 64
    assert "dissipation power map" in selected[0]["chunk_text"]

    replay = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-0001",
        artifact_ids=[source["id"]],
        top_k=2,
    )
    assert replay["idempotent_replay"] is True
    assert replay["run"]["id"] == retrieval_run["id"]

    conflict = client.post(
        f"/api/v1/projects/{PROJECT}/retrievals",
        headers={**headers, "Idempotency-Key": "rag-retrieve-0001"},
        json={"claim_id": CLAIM, "query": "different query", "artifact_ids": [], "top_k": 2},
    )
    assert conflict.status_code == 409

    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "rag-review-0001"},
        json={
            "claim_id": CLAIM,
            "evidence_ids": [],
            "retrieval_run_id": retrieval_run["id"],
            "mode": "SIMULATED",
        },
    )
    assert review.status_code == 202, review.text
    detail = client.get(f"/api/v1/jobs/{review.json()['job_id']}")
    assert detail.status_code == 200
    snapshot = detail.json()["snapshot"]
    assert snapshot["retrieval_run_id"] == retrieval_run["id"]
    assert snapshot["retrieved_chunk_ids"] == [selected[0]["chunk_id"]]
    assert snapshot["included_evidence_ids"] == [selected[0]["chunk_id"]]
    assert snapshot["retrieval_receipt"]["query_sha256"] == retrieval_run["receipt"]["query_sha256"]
    assert snapshot["context_budget"]["source_text_truncated"] is False
    packet = json.loads(snapshot["messages"][1]["content"])
    assert packet["evidence"][0]["id"] == selected[0]["chunk_id"]
    assert "gold" not in snapshot["messages"][1]["content"].lower()

    assert run_one() is True
    completed = client.get(f"/api/v1/jobs/{review.json()['job_id']}").json()
    assert completed["job"]["status"] == "AWAITING_REVIEW"
    assert completed["model_run"]["validation_status"] == "VALID"
    assert completed["model_run"]["parsed_output"]["actions"][0]["evidence_refs"] == [selected[0]["chunk_id"]]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT upstream_object_type,upstream_object_id,relationship
               FROM object_dependencies WHERE source_job_id=%s AND upstream_object_type='DOCUMENT_CHUNK'""",
            (review.json()["job_id"],),
        )
        dependency = cur.fetchone()
    assert dependency == {
        "upstream_object_type": "DOCUMENT_CHUNK",
        "upstream_object_id": selected[0]["chunk_id"],
        "relationship": "DERIVED_FROM",
    }


def test_scope_gate_exclusion_is_saved_in_retrieval_receipt(client):
    headers = sign_in(client)
    source = upload_document(client, headers, rights="RESTRICTED")
    parse_document(client, headers, source["id"])
    retrieval = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-scope",
        artifact_ids=[source["id"]],
    )
    assert retrieval["run"]["candidate_count"] == 1
    assert retrieval["run"]["selected_count"] == 0
    assert retrieval["results"][0]["reason"] == "REFERENCE_RIGHTS_UNCONFIRMED"
    assert retrieval["results"][0]["chunk_text"] is None
    assert retrieval["run"]["receipt"]["results"][0]["selected"] is False


def test_pdf_text_layer_preserves_page_locator_and_is_searchable(client):
    headers = sign_in(client)
    source = upload_document(
        client,
        headers,
        name="thermal-source.pdf",
        content=text_pdf(),
        content_type="application/pdf",
    )
    parsed = parse_document(client, headers, source["id"])
    assert parsed["parser_run"]["page_count"] == 1
    assert parsed["parser_run"]["chunk_count"] == 1
    assert parsed["chunks"][0]["locator"].startswith("PDF page 1")
    assert parsed["parser_run"]["receipt"]["ocr_performed"] is False
    assert any(
        issue["code"] == "TABLE_FIGURE_STRUCTURE_NOT_EXTRACTED"
        for issue in parsed["parser_run"]["issues"]
    )
    retrieval = retrieve(
        client,
        headers,
        "thermal dissipation power map",
        key="rag-retrieve-pdf",
        artifact_ids=[source["id"]],
    )
    assert retrieval["run"]["selected_count"] == 1
    assert retrieval["results"][0]["page_start"] == 1


def test_evaluation_corpus_is_not_in_operational_search_and_reserved_json_is_rejected(client):
    headers = sign_in(client)
    payload = json.dumps(
        {"task": "thermal", "gold": "component dissipation power map", "rationale": "hidden evaluation"}
    ).encode()
    gold = upload_document(
        client,
        headers,
        name="sealed-evaluation.json",
        content=payload,
        content_type="application/json",
        purpose="EVALUATION_GOLD",
    )
    parse_document(client, headers, gold["id"])
    retrieval = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-gold",
    )
    assert retrieval["run"]["candidate_count"] == 0
    assert retrieval["run"]["selected_count"] == 0

    operational = upload_document(
        client,
        headers,
        name="bad-operational.json",
        content=payload,
        content_type="application/json",
    )
    rejected = client.post(f"/api/v1/artifacts/{operational['id']}/parse", headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["detail"].startswith("RESERVED_EVALUATION_METADATA:")


def test_retrieval_is_project_isolated_and_stale_run_is_rejected(client):
    headers = sign_in(client)
    project = client.post(
        "/api/v1/projects",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "display_id": "DORI-RAG-2",
            "name": "RAG isolation project",
            "framework": "KASA",
            "mode": "DEMO",
            "data_policy": "LOCAL_ONLY",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    source = upload_document(client, headers, project=project_id)
    parse_document(client, headers, source["id"])

    retrieval = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-isolation",
    )
    assert retrieval["run"]["candidate_count"] == 0

    own_source = upload_document(client, headers)
    parse_document(client, headers, own_source["id"])
    own = retrieve(
        client,
        headers,
        "component dissipation power map",
        key="rag-retrieve-stale",
    )
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE claims SET version=version+1 WHERE id=%s",
            (UUID(CLAIM),),
        )
    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "rag-review-stale"},
        json={
            "claim_id": CLAIM,
            "evidence_ids": [],
            "retrieval_run_id": own["run"]["id"],
            "mode": "SIMULATED",
        },
    )
    assert review.status_code == 409
    assert review.json()["detail"].startswith("STALE_RETRIEVAL:")
