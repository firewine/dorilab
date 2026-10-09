from __future__ import annotations

import json
import re
from io import BytesIO
from uuid import uuid4

import pytest
from dorilab.db import connection
from dorilab.storage import resolved_path
from dorilab.validation import validate_output
from dorilab.worker import run_one
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"
SCOPE = {"unit": "DORI-01", "configuration": "TVAC-03", "run": "RUN-DEMO-01"}
REPEATED = "Thermal  dissipation power map TVAC-03."
NEGATIVE = "Product performance is NOT evaluated; limit 3.0 K is unapproved."


def _pdf_literal(value: str) -> bytes:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("ascii")


def text_layer_pdf(*pages: str) -> bytes:
    """Build a local, deterministic, multi-page PDF with one text-layer line per page."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 72 720 Td (" + _pdf_literal(text) + b") Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def upload(
    client,
    headers,
    *,
    content: bytes,
    filename: str = "manual-citation.pdf",
    content_type: str = "application/pdf",
    project: str = PROJECT,
    edition: str = "REV-A",
    rights: str = "PUBLIC",
    adopted: str = "true",
    applicability: str = "APPLICABLE",
):
    response = client.post(
        f"/api/v1/projects/{project}/artifacts",
        headers=headers,
        files={"file": (filename, content, content_type)},
        data={
            "rights_status": rights,
            "edition": edition,
            "adopted": adopted,
            "applicability_status": applicability,
            "usage_purpose": "OPERATIONAL_EVIDENCE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def parse(client, headers, artifact_id: str):
    response = client.post(f"/api/v1/artifacts/{artifact_id}/parse", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def upload_parsed_pdf(client, headers, *, filename="manual-citation.pdf"):
    artifact = upload(
        client,
        headers,
        filename=filename,
        content=text_layer_pdf(REPEATED, REPEATED, NEGATIVE),
    )
    parsed = parse(client, headers, artifact["id"])
    assert parsed["parser_run"]["status"] == "COMPLETED"
    assert parsed["parser_run"]["page_count"] == 3
    assert len(parsed["chunks"]) == 3
    return artifact, parsed


def source_position(chunk: dict) -> dict:
    return {
        "page_start": chunk["page_start"],
        "page_end": chunk["page_end"],
        "line_start": chunk["metadata"]["line_start"],
        "line_end": chunk["metadata"]["line_end"],
    }


def evidence_body(
    artifact: dict,
    chunk: dict | None,
    display_id: str,
    *,
    quote: str | None = None,
    locator: str | None = None,
    cited_edition: str | None = "REV-A",
    position: dict | None = None,
    kind: str = "REFERENCE",
    scope: dict | None = None,
    citation: bool = True,
) -> dict:
    body = {
        "artifact_id": artifact["id"],
        "display_id": display_id,
        "kind": kind,
        "basis": "USER_PROVIDED",
        "scope": scope or {},
        "locator": locator if locator is not None else (chunk["locator"] if chunk else "unconfirmed"),
        "quote": quote if quote is not None else (chunk["chunk_text"] if chunk else "unconfirmed"),
        "provenance": {"fixture": "manual-citation"},
    }
    if citation:
        body["citation"] = {
            "document_chunk_id": chunk["id"] if chunk else None,
            "cited_edition": cited_edition,
            "source_position": position if position is not None else (source_position(chunk) if chunk else None),
        }
    return body


def create_evidence(client, headers, body: dict, *, project: str = PROJECT, expected=201):
    response = client.post(f"/api/v1/projects/{project}/evidence", headers=headers, json=body)
    assert response.status_code == expected, response.text
    return response


def assert_verification(record: dict, status: str, reason: str, *, enforced: bool = True):
    receipt = record["source_verification"]
    assert receipt["schema"] == "dorilab.manual-citation.v1"
    assert receipt["status"] == status
    assert receipt["reason_code"] == reason
    assert receipt["freshness"] == "CURRENT"
    assert receipt["enforced"] is enforced
    assert receipt["semantic_support"] == "UNASSESSED"
    return receipt


def test_valid_pdf_citation_has_independent_user_span_and_stable_receipt(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    chunk = parsed["chunks"][2]
    request = evidence_body(artifact, chunk, "CITE-VALID")

    created = create_evidence(client, headers, request).json()
    receipt = assert_verification(created, "VALID", "CITATION_MATCHED")
    assert receipt["artifact_id"] == artifact["id"]
    assert receipt["artifact_sha256"] == artifact["sha256"]
    assert receipt["edition"] == "REV-A"
    assert receipt["parser_run_id"] == parsed["parser_run"]["id"]
    assert receipt["parser_receipt_sha256"] == parsed["parser_run"]["receipt_sha256"]
    assert receipt["document_chunk_id"] == chunk["id"]
    assert receipt["source_position"] == source_position(chunk)
    assert receipt["format"] == "PDF_TEXT_LAYER"

    detail = client.get(f"/api/v1/evidence/{created['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["locator"] == request["locator"]
    assert detail.json()["quote"] == request["quote"]
    assert detail.json()["source_verification"] == receipt
    listed = client.get(f"/api/v1/projects/{PROJECT}/evidence")
    assert listed.status_code == 200, listed.text
    assert next(item for item in listed.json() if item["id"] == created["id"])["source_verification"] == receipt

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_span_id FROM evidence WHERE id=%s", (created["id"],))
        user_span_id = str(cur.fetchone()["source_span_id"])
        cur.execute("SELECT source_span_id FROM document_chunks WHERE id=%s", (chunk["id"],))
        parser_span_id = str(cur.fetchone()["source_span_id"])
        cur.execute("SELECT locator,quote FROM source_spans WHERE id=%s", (user_span_id,))
        user_span = cur.fetchone()
    assert user_span_id != parser_span_id
    assert receipt["parsed_source_span_id"] == parser_span_id
    assert user_span == {"locator": request["locator"], "quote": request["quote"]}


def test_only_ascii_whitespace_is_normalized_and_whole_chunk_is_required(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    chunk = parsed["chunks"][0]
    canonical = chunk["chunk_text"]
    collapsed = re.sub(r"[ \t\r\n\f\v]+", " ", canonical).strip(" \t\r\n\f\v")
    assert collapsed != canonical

    accepted = create_evidence(
        client,
        headers,
        evidence_body(artifact, chunk, "CITE-WS", quote=f" \t{collapsed}\r\n"),
    ).json()
    assert_verification(accepted, "VALID", "CITATION_MATCHED")
    stored = client.get(f"/api/v1/evidence/{accepted['id']}").json()
    assert stored["quote"] == f" \t{collapsed}\r\n"

    counterexamples = {
        "CITE-CASE": collapsed.replace("Thermal", "thermal"),
        "CITE-PUNCT": collapsed.removesuffix("."),
        "CITE-NUMBER": collapsed.replace("03", "04"),
        "CITE-PART": "dissipation power map",
        # NFKC would turn these full-width characters into ASCII.  The
        # citation contract deliberately performs no such Unicode folding.
        "CITE-NFKC": collapsed.replace("TVAC", "ＴＶＡＣ"),
        "CITE-EMPTY": " \t\r\n\f\v ",
    }
    for display_id, quote in counterexamples.items():
        rejected = create_evidence(
            client, headers, evidence_body(artifact, chunk, display_id, quote=quote)
        ).json()
        assert_verification(rejected, "REJECTED", "CITATION_QUOTE_MISMATCH")

    # Physical matching is deliberately not a claim that the sentence supports a
    # performance conclusion; even an exact negative sentence stays UNASSESSED.
    negative = create_evidence(
        client, headers, evidence_body(artifact, parsed["chunks"][2], "CITE-SEMANTIC")
    ).json()
    assert_verification(negative, "VALID", "CITATION_MATCHED")


def test_document_position_edition_and_unknown_chunk_failures_are_persisted(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers, filename="source-a.pdf")
    other, other_parsed = upload_parsed_pdf(client, headers, filename="source-b.pdf")
    chunk = parsed["chunks"][2]

    wrong_document = evidence_body(artifact, other_parsed["chunks"][2], "CITE-DOCUMENT")
    wrong_document["locator"] = chunk["locator"]
    wrong_document["quote"] = chunk["chunk_text"]
    unknown_chunk = evidence_body(artifact, chunk, "CITE-UNKNOWN")
    unknown_chunk["citation"]["document_chunk_id"] = str(uuid4())
    wrong_location = evidence_body(
        artifact,
        chunk,
        "CITE-LOCATION",
        position={**source_position(chunk), "page_start": 2, "page_end": 2},
    )
    wrong_lines = evidence_body(
        artifact,
        chunk,
        "CITE-LINES",
        position={
            **source_position(chunk),
            "line_start": source_position(chunk)["line_start"] + 1,
            "line_end": source_position(chunk)["line_end"] + 1,
        },
    )
    free_form_locator = evidence_body(
        artifact, chunk, "CITE-FREE-LOCATOR", locator="§4.6 / p.142"
    )
    quote_from_other_page = evidence_body(
        artifact,
        chunk,
        "CITE-OTHER-PAGE-QUOTE",
        quote=parsed["chunks"][0]["chunk_text"],
    )
    multi_page_position = evidence_body(
        artifact,
        chunk,
        "CITE-MULTI-PAGE-POS",
        position={**source_position(chunk), "page_start": 1, "page_end": 3},
    )
    noncontiguous_quote = evidence_body(
        artifact,
        chunk,
        "CITE-NONCONTIGUOUS",
        quote=f"{parsed['chunks'][0]['chunk_text']}\n{chunk['chunk_text']}",
    )
    wrong_edition = evidence_body(artifact, chunk, "CITE-EDITION", cited_edition="REV-B")
    cases = [
        (wrong_document, "CITATION_DOCUMENT_MISMATCH"),
        (unknown_chunk, "CITATION_DOCUMENT_MISMATCH"),
        (wrong_location, "CITATION_LOCATION_MISMATCH"),
        (wrong_lines, "CITATION_LOCATION_MISMATCH"),
        (free_form_locator, "CITATION_LOCATION_MISMATCH"),
        (quote_from_other_page, "CITATION_QUOTE_MISMATCH"),
        (multi_page_position, "CITATION_LOCATION_MISMATCH"),
        (noncontiguous_quote, "CITATION_QUOTE_MISMATCH"),
        (wrong_edition, "CITATION_EDITION_MISMATCH"),
    ]
    for request, reason in cases:
        created = create_evidence(client, headers, request).json()
        assert_verification(created, "REJECTED", reason)
        persisted = client.get(f"/api/v1/evidence/{created['id']}").json()
        assert_verification(persisted, "REJECTED", reason)
        assert persisted["locator"] == request["locator"]
        assert persisted["quote"] == request["quote"]

    assert other["id"] != artifact["id"]


def test_missing_location_and_source_readiness_are_unresolved_records(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)

    ambiguous = evidence_body(artifact, None, "CITE-AMBIGUOUS", quote=parsed["chunks"][0]["chunk_text"])
    ambiguous["citation"] = {"document_chunk_id": None, "cited_edition": "REV-A", "source_position": None}
    position_required = evidence_body(artifact, None, "CITE-POSITION", quote=parsed["chunks"][2]["chunk_text"])
    position_required["citation"] = {
        "document_chunk_id": None,
        "cited_edition": "REV-A",
        "source_position": None,
    }
    omitted = evidence_body(artifact, None, "CITE-OMITTED", citation=False)
    for request, reason in (
        (ambiguous, "CITATION_LOCATION_AMBIGUOUS"),
        (position_required, "CITATION_POSITION_REQUIRED"),
        (omitted, "CITATION_POSITION_REQUIRED"),
    ):
        created = create_evidence(client, headers, request).json()
        assert_verification(created, "UNRESOLVED", reason)

    unparsed = upload(client, headers, filename="unparsed.pdf", content=text_layer_pdf(NEGATIVE))
    unparsed_request = evidence_body(unparsed, None, "CITE-NOT-PARSED")
    unparsed_request["citation"]["document_chunk_id"] = str(uuid4())
    not_parsed = create_evidence(client, headers, unparsed_request).json()
    assert_verification(not_parsed, "UNRESOLVED", "SOURCE_NOT_PARSED")

    failed = upload(client, headers, filename="failed.pdf", content=b"%PDF-1.4 broken")
    failed_parse = client.post(f"/api/v1/artifacts/{failed['id']}/parse", headers=headers)
    assert failed_parse.status_code == 422, failed_parse.text
    failed_request = evidence_body(failed, None, "CITE-PARSE-FAILED")
    failed_request["citation"]["document_chunk_id"] = str(uuid4())
    parse_failed = create_evidence(client, headers, failed_request).json()
    assert_verification(parse_failed, "UNRESOLVED", "SOURCE_PARSE_FAILED")

    unavailable = upload(client, headers, filename="missing.pdf", content=text_layer_pdf(NEGATIVE))
    resolved_path(unavailable["object_key"]).unlink()
    unavailable_request = evidence_body(unavailable, None, "CITE-UNAVAILABLE")
    unavailable_request["citation"]["document_chunk_id"] = str(uuid4())
    source_missing = create_evidence(client, headers, unavailable_request).json()
    assert_verification(source_missing, "UNRESOLVED", "SOURCE_UNAVAILABLE")

    for record in (not_parsed, parse_failed, source_missing):
        persisted = client.get(f"/api/v1/evidence/{record['id']}")
        assert persisted.status_code == 200, persisted.text
        assert persisted.json()["source_verification"] == record["source_verification"]
        assert persisted.json()["locator"] == "unconfirmed"
        assert persisted.json()["quote"] == "unconfirmed"


def test_repeated_long_line_chunks_remain_location_ambiguous_even_with_chunk_id(client):
    headers = sign_in(client)
    repeated_piece = "A" * 1_200
    artifact = upload(
        client,
        headers,
        filename="same-position-long-line.pdf",
        content=text_layer_pdf(repeated_piece * 3),
    )
    parsed = parse(client, headers, artifact["id"])
    assert len(parsed["chunks"]) == 3
    assert {chunk["chunk_text"] for chunk in parsed["chunks"]} == {repeated_piece}
    assert {tuple(source_position(chunk).items()) for chunk in parsed["chunks"]} == {
        tuple(source_position(parsed["chunks"][0]).items())
    }
    assert {chunk["locator"] for chunk in parsed["chunks"]} == {
        parsed["chunks"][0]["locator"]
    }

    selected = parsed["chunks"][1]
    request = evidence_body(artifact, selected, "CITE-SAME-POSITION")
    created = create_evidence(client, headers, request).json()
    receipt = assert_verification(
        created, "UNRESOLVED", "CITATION_LOCATION_AMBIGUOUS"
    )
    assert receipt["document_chunk_id"] == selected["id"]
    assert receipt["source_position"] == source_position(selected)
    assert client.get(f"/api/v1/evidence/{created['id']}").json()[
        "source_verification"
    ] == receipt


def test_pdf_gate_is_enforced_for_reference_and_observation_but_legacy_text_remains_compatible(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    incomplete = evidence_body(
        artifact,
        None,
        "CITE-OBS-INCOMPLETE",
        quote=parsed["chunks"][2]["chunk_text"],
        kind="OBSERVATION",
        scope=SCOPE,
        citation=False,
    )
    pdf_evidence = create_evidence(client, headers, incomplete).json()
    pdf_receipt = assert_verification(pdf_evidence, "UNRESOLVED", "CITATION_POSITION_REQUIRED")
    assert pdf_receipt["enforced"] is True

    legacy_artifact = upload(
        client,
        headers,
        filename="legacy.md",
        content_type="text/markdown",
        content=b"Synthetic current-scope supporting evidence.\n",
    )
    legacy_request = evidence_body(
        legacy_artifact,
        None,
        "CITE-LEGACY",
        locator="line 1",
        quote="Synthetic current-scope supporting evidence.",
        citation=False,
    )
    legacy = create_evidence(client, headers, legacy_request).json()
    assert_verification(legacy, "UNRESOLVED", "SOURCE_FORMAT_UNSUPPORTED", enforced=False)

    # An additive migration leaves old rows at the JSON default.  Reading that
    # row must expose the explicit legacy state without retroactive inference.
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE evidence SET source_verification='{}'::jsonb WHERE id=%s", (legacy["id"],))
    legacy_detail = client.get(f"/api/v1/evidence/{legacy['id']}")
    assert legacy_detail.status_code == 200, legacy_detail.text
    assert_verification(
        legacy_detail.json(), "UNRESOLVED", "LEGACY_NOT_VERIFIED", enforced=False
    )

    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "manual-citation-gate"},
        json={
            "claim_id": CLAIM,
            "evidence_ids": [pdf_evidence["id"], legacy["id"]],
            "mode": "SIMULATED",
        },
    )
    assert review.status_code == 202, review.text
    assert review.json()["excluded_evidence"] == [
        {"evidence_id": pdf_evidence["id"], "reason": "CITATION_POSITION_REQUIRED"}
    ]
    job = client.get(f"/api/v1/jobs/{review.json()['job_id']}").json()
    assert job["snapshot"]["included_evidence_ids"] == [legacy["id"]]
    assert job["snapshot"]["source_verifications"][legacy["id"]]["enforced"] is False


def test_valid_physical_citation_does_not_bypass_rights_adoption_or_applicability(client):
    headers = sign_in(client)
    controls = [
        ("RIGHTS", {"rights": "RESTRICTED"}, "REFERENCE_RIGHTS_UNCONFIRMED"),
        ("ADOPTED", {"adopted": "false"}, "REFERENCE_NOT_ADOPTED"),
        (
            "APPLICABILITY",
            {"applicability": "UNCONFIRMED"},
            "REFERENCE_APPLICABILITY_UNCONFIRMED",
        ),
    ]
    evidence_ids = []
    expected_exclusions = {}
    for label, upload_override, reason in controls:
        artifact = upload(
            client,
            headers,
            filename=f"scope-{label.lower()}.pdf",
            content=text_layer_pdf(NEGATIVE),
            **upload_override,
        )
        parsed = parse(client, headers, artifact["id"])
        evidence = create_evidence(
            client,
            headers,
            evidence_body(artifact, parsed["chunks"][0], f"CITE-SCOPE-{label}"),
        ).json()
        assert_verification(evidence, "VALID", "CITATION_MATCHED")
        evidence_ids.append(evidence["id"])
        expected_exclusions[evidence["id"]] = reason

    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "manual-citation-scope-controls"},
        json={"claim_id": CLAIM, "evidence_ids": evidence_ids, "mode": "SIMULATED"},
    )
    assert review.status_code == 202, review.text
    assert {
        item["evidence_id"]: item["reason"] for item in review.json()["excluded_evidence"]
    } == expected_exclusions
    job = client.get(f"/api/v1/jobs/{review.json()['job_id']}").json()
    assert job["snapshot"]["included_evidence_ids"] == []


def test_output_validator_checks_schema_and_provided_ids_without_claiming_semantic_support(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    evidence = create_evidence(
        client,
        headers,
        evidence_body(artifact, parsed["chunks"][2], "CITE-VALIDATION-BOUNDARY"),
    ).json()
    receipt = assert_verification(evidence, "VALID", "CITATION_MATCHED")
    assert receipt["semantic_support"] == "UNASSESSED"

    raw = json.dumps(
        {
            "actions": [
                {
                    "action": "NO_ACTION_REQUIRED",
                    "reason_code": "EVIDENCE_SUFFICIENT",
                    "reason": "This synthetic sentence deliberately overclaims product performance.",
                    "evidence_refs": [evidence["id"]],
                    "requested_items": [],
                }
            ]
        }
    )
    validated, errors = validate_output(raw, {evidence["id"]})
    assert errors == []
    assert validated["actions"][0]["reason"].endswith("product performance.")

    _, unprovided_errors = validate_output(raw, {"different-provided-id"})
    assert unprovided_errors == ["actions[0]:UNPROVIDED_EVIDENCE_REF"]
    # Structural validation neither changes nor upgrades the source receipt.
    persisted = client.get(f"/api/v1/evidence/{evidence['id']}").json()
    assert persisted["source_verification"]["semantic_support"] == "UNASSESSED"


@pytest.mark.parametrize(
    "mutation", ["bytes", "edition", "parser_receipt", "chunk_text", "user_span_quote"]
)
def test_changed_source_stales_receipt_job_and_every_downstream_boundary(client, mutation):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    evidence = create_evidence(
        client, headers, evidence_body(artifact, parsed["chunks"][2], "CITE-CHANGE")
    ).json()
    original = evidence["source_verification"]
    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "manual-citation-before-change"},
        json={"claim_id": CLAIM, "evidence_ids": [evidence["id"]], "mode": "SIMULATED"},
    )
    assert review.status_code == 202, review.text
    assert review.json()["excluded_evidence"] == []
    assert run_one() is True
    job_id = review.json()["job_id"]
    before = client.get(f"/api/v1/jobs/{job_id}").json()
    assert before["job"]["status"] == "AWAITING_REVIEW"
    assert before["job"]["freshness"] == "CURRENT"

    if mutation == "bytes":
        resolved_path(artifact["object_key"]).write_bytes(text_layer_pdf("changed bytes"))
    else:
        with connection() as conn, conn.cursor() as cur:
            if mutation == "edition":
                cur.execute(
                    "UPDATE artifact_versions SET edition='REV-B' WHERE id=%s",
                    (artifact["id"],),
                )
            elif mutation == "parser_receipt":
                cur.execute(
                    """UPDATE document_parser_runs
                       SET receipt=jsonb_set(receipt,'{test_tampered}','true'::jsonb,true)
                       WHERE id=%s""",
                    (parsed["parser_run"]["id"],),
                )
            elif mutation == "chunk_text":
                cur.execute(
                    "UPDATE document_chunks SET chunk_text=chunk_text || ' tampered' WHERE id=%s",
                    (parsed["chunks"][2]["id"],),
                )
            elif mutation == "user_span_quote":
                cur.execute(
                    """UPDATE source_spans SET quote=quote || ' tampered'
                       WHERE id=(SELECT source_span_id FROM evidence WHERE id=%s)""",
                    (evidence["id"],),
                )
            else:  # pragma: no cover - the parametrization is closed above
                raise AssertionError(mutation)
    detail = client.get(f"/api/v1/evidence/{evidence['id']}")
    assert detail.status_code == 200, detail.text
    stale = detail.json()["source_verification"]
    assert stale["status"] == "VALID"
    assert stale["freshness"] == "STALE"
    assert stale["reason_code"] == "SOURCE_CHANGED"
    for field in (
        "artifact_sha256",
        "parser_run_id",
        "parser_receipt_sha256",
        "document_chunk_id",
        "parsed_source_span_id",
        "source_position",
        "chunk_sha256",
        "canonical_locator",
    ):
        assert stale[field] == original[field]
    listed = client.get(f"/api/v1/projects/{PROJECT}/evidence").json()
    assert next(item for item in listed if item["id"] == evidence["id"])["source_verification"] == stale

    stale_job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert stale_job["job"]["freshness"] == "STALE"
    closure = client.get(f"/api/v1/projects/{PROJECT}/closure").json()
    checks = {item["code"]: item for item in closure["claims"][0]["checks"]}
    assert checks["CURRENT_EVIDENCE"]["satisfied"] is False

    reviewer_headers = sign_in(client, "reviewer@demo")
    decision = client.post(
        f"/api/v1/reviews/{job_id}/decisions",
        headers=reviewer_headers,
        json={
            "disposition": "ACCEPTED",
            "expected_job_version": stale_job["job"]["version"],
            "note": "changed source must prevent acceptance",
        },
    )
    assert decision.status_code == 409, decision.text
    assert "stale" in decision.json()["detail"].lower()

    engineer_headers = sign_in(client)
    later = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**engineer_headers, "Idempotency-Key": "manual-citation-after-change"},
        json={"claim_id": CLAIM, "evidence_ids": [evidence["id"]], "mode": "SIMULATED"},
    )
    assert later.status_code == 202, later.text
    assert later.json()["excluded_evidence"] == [
        {"evidence_id": evidence["id"], "reason": "SOURCE_CHANGED"}
    ]
    later_job = client.get(f"/api/v1/jobs/{later.json()['job_id']}").json()
    assert later_job["snapshot"]["included_evidence_ids"] == []


def test_manual_citation_authorization_project_isolation_and_duplicate_display_id(client):
    headers = sign_in(client)
    artifact, parsed = upload_parsed_pdf(client, headers)
    request = evidence_body(artifact, parsed["chunks"][2], "CITE-AUTH")

    viewer_headers = sign_in(client, "viewer@demo")
    denied = create_evidence(client, viewer_headers, request, expected=403)
    assert denied.json()["detail"] == "project role does not allow this action"

    engineer_headers = sign_in(client)
    created = create_evidence(client, engineer_headers, request)
    assert created.status_code == 201
    duplicate = create_evidence(client, engineer_headers, request, expected=409)
    assert duplicate.json()["detail"] == "evidence display_id already exists"

    other_project = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={"display_id": "CITE-OTHER", "name": "Citation isolation", "framework": "KASA"},
    )
    assert other_project.status_code == 201, other_project.text
    other_artifact = upload(
        client,
        engineer_headers,
        project=other_project.json()["id"],
        filename="other.pdf",
        content=text_layer_pdf(NEGATIVE),
    )
    cross_project = evidence_body(other_artifact, None, "CITE-CROSS-PROJECT")
    rejected = create_evidence(client, engineer_headers, cross_project, expected=404)
    assert rejected.json()["detail"] == "artifact not found in project"
