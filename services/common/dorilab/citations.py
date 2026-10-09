"""Physical source matching only; never a judgement of meaning or applicability."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from .contracts import digest
from .rag import DocumentParseError, parse_document
from .storage import resolved_path

SCHEMA = "dorilab.manual-citation.v1"
NORMALIZATION = "ASCII_WHITESPACE_V1"


def normalize_quote(text: str) -> str:
    # No case folding, fuzzy matching, Unicode folding, or punctuation removal.
    return re.sub(r"[ \t\r\n\f\v]+", " ", text).strip(" \t\r\n\f\v")


def unresolved_legacy() -> dict:
    return {"schema": SCHEMA, "status": "UNRESOLVED", "freshness": "CURRENT",
            "reason_code": "LEGACY_NOT_VERIFIED", "enforced": False,
            "semantic_support": "UNASSESSED", "normalization": NORMALIZATION}


def position(chunk: dict) -> dict:
    return {"page_start": chunk["page_start"], "page_end": chunk["page_end"],
            "line_start": chunk["metadata"].get("line_start"),
            "line_end": chunk["metadata"].get("line_end")}


def _bytes_hash(artifact: dict) -> str | None:
    try:
        with resolved_path(artifact["object_key"]).open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()
    except (OSError, ValueError):
        return None


def verify_citation(cur, artifact: dict, citation: dict | None, quote: str | None, locator: str | None) -> dict:
    result = {"schema": SCHEMA, "status": "UNRESOLVED", "freshness": "CURRENT",
              "enforced": artifact["content_type"].split(";", 1)[0].lower() == "application/pdf",
              "semantic_support": "UNASSESSED", "normalization": NORMALIZATION,
              "checked_at": datetime.now(timezone.utc).isoformat(),
              "submitted_citation": citation or {},
              "artifact_id": str(artifact["id"]), "artifact_sha256": artifact["sha256"],
              "edition": artifact["edition"],
              "submitted_quote_sha256": hashlib.sha256((quote or "").encode()).hexdigest(),
              "normalized_quote_sha256": hashlib.sha256(normalize_quote(quote or "").encode()).hexdigest(),
              "position_contract": "PDF_PHYSICAL_PAGE_PAGE_LOCAL_EXTRACTED_LINES_WHOLE_CHUNK",
              "format": "PDF_TEXT_LAYER"}

    def finish(status: str, reason: str) -> dict:
        return {**result, "status": status, "reason_code": reason}

    if not result["enforced"]:
        return finish("UNRESOLVED", "SOURCE_FORMAT_UNSUPPORTED")
    actual_hash = _bytes_hash(artifact)
    if actual_hash is None:
        return finish("UNRESOLVED", "SOURCE_UNAVAILABLE")
    if actual_hash != artifact["sha256"]:
        return finish("REJECTED", "SOURCE_CHANGED")
    cur.execute("SELECT * FROM document_parser_runs WHERE artifact_id=%s AND project_id=%s ORDER BY started_at DESC,id DESC LIMIT 1",
                (artifact["id"], artifact["project_id"]))
    run = cur.fetchone()
    if not run or run["status"] == "PROCESSING":
        return finish("UNRESOLVED", "SOURCE_NOT_PARSED")
    if run["status"] != "COMPLETED":
        return finish("UNRESOLVED", "SOURCE_PARSE_FAILED")
    if any(issue.get("code") == "PAGE_EXTRACTION_FAILED" for issue in run["issues"]):
        return finish("UNRESOLVED", "SOURCE_PARSE_FAILED")
    result.update(parser_run_id=str(run["id"]), parser_receipt_sha256=run["receipt_sha256"])
    if run["source_sha256"] != actual_hash or run["receipt"].get("artifact_sha256") != actual_hash or digest(run["receipt"]) != run["receipt_sha256"]:
        return finish("REJECTED", "SOURCE_CHANGED")
    cur.execute("SELECT * FROM document_chunks WHERE parser_run_id=%s AND project_id=%s ORDER BY ordinal",
                (run["id"], artifact["project_id"]))
    chunks = cur.fetchall()
    citation = citation or {}
    chunk = next((item for item in chunks if str(item["id"]) == str(citation.get("document_chunk_id"))), None)
    if citation.get("document_chunk_id") and chunk is None:
        # Same generic result for an unknown ID or any other document/project.
        return finish("REJECTED", "CITATION_DOCUMENT_MISMATCH")
    if not chunk:
        matches = [item for item in chunks if normalize_quote(item["chunk_text"]) == normalize_quote(quote or "")]
        return finish("UNRESOLVED", "CITATION_LOCATION_AMBIGUOUS" if len(matches) > 1 else "CITATION_POSITION_REQUIRED")
    result.update(document_chunk_id=str(chunk["id"]), parsed_source_span_id=str(chunk["source_span_id"]),
                  source_position=position(chunk), canonical_locator=chunk["locator"],
                  chunk_sha256=chunk["text_sha256"], cited_edition=citation.get("cited_edition"),
                  submitted_position=citation.get("source_position"), submitted_locator=locator)
    if chunk["metadata"].get("source_kind") != "PDF_TEXT_LAYER":
        return finish("UNRESOLVED", "SOURCE_FORMAT_UNSUPPORTED")
    if not citation.get("cited_edition") or not artifact["edition"]:
        return finish("UNRESOLVED", "CITATION_EDITION_REQUIRED")
    if citation["cited_edition"] != artifact["edition"]:
        return finish("REJECTED", "CITATION_EDITION_MISMATCH")
    if not citation.get("source_position"):
        return finish("UNRESOLVED", "CITATION_POSITION_REQUIRED")
    identical_positions = [item for item in chunks if position(item) == position(chunk)
                           and normalize_quote(item["chunk_text"]) == normalize_quote(chunk["chunk_text"])]
    if len(identical_positions) > 1:
        return finish("UNRESOLVED", "CITATION_LOCATION_AMBIGUOUS")
    if citation["source_position"] != position(chunk) or locator != chunk["locator"]:
        return finish("REJECTED", "CITATION_LOCATION_MISMATCH")
    if not quote or normalize_quote(quote) != normalize_quote(chunk["chunk_text"]):
        return finish("REJECTED", "CITATION_QUOTE_MISMATCH")
    # Reuse the same parser against actual stored bytes: a chunk cache alone is not source proof.
    try:
        parsed = parse_document(resolved_path(artifact["object_key"]), artifact["content_type"], artifact["usage_purpose"])
    except DocumentParseError:
        return finish("UNRESOLVED", "SOURCE_PARSE_FAILED")
    except (OSError, ValueError):
        return finish("UNRESOLVED", "SOURCE_UNAVAILABLE")
    actual = next((draft for draft in parsed.chunks if draft.ordinal == chunk["ordinal"]), None)
    if (not actual or parsed.extraction_sha256 != run["receipt"].get("extraction_sha256")
            or actual.text != chunk["chunk_text"] or actual.text_sha256 != chunk["text_sha256"]
            or actual.locator != chunk["locator"]):
        return finish("REJECTED", "SOURCE_CHANGED")
    if position(chunk) != {"page_start": actual.page_start, "page_end": actual.page_end,
                           "line_start": actual.metadata.get("line_start"), "line_end": actual.metadata.get("line_end")}:
        return finish("REJECTED", "SOURCE_CHANGED")
    if _bytes_hash(artifact) != actual_hash:
        return finish("REJECTED", "SOURCE_CHANGED")
    return finish("VALID", "CITATION_MATCHED")


def receipt_is_current(cur, artifact: dict, receipt: dict, hash_cache: dict) -> bool:
    key = str(artifact["id"])
    if key not in hash_cache:
        hash_cache[key] = _bytes_hash(artifact)
    if hash_cache[key] != receipt.get("artifact_sha256") or artifact["sha256"] != receipt.get("artifact_sha256") or artifact["edition"] != receipt.get("edition"):
        return False
    cur.execute("SELECT dc.*,pr.status AS parser_status,pr.receipt,pr.receipt_sha256,pr.source_sha256 FROM document_chunks dc JOIN document_parser_runs pr ON pr.id=dc.parser_run_id WHERE dc.id=%s AND dc.artifact_id=%s AND dc.project_id=%s",
                (receipt.get("document_chunk_id"), artifact["id"], artifact["project_id"]))
    chunk = cur.fetchone()
    return bool(chunk and str(chunk["parser_run_id"]) == receipt.get("parser_run_id")
                and str(chunk["source_span_id"]) == receipt.get("parsed_source_span_id")
                and chunk["metadata"].get("source_kind") == "PDF_TEXT_LAYER"
                and chunk["parser_status"] == "COMPLETED"
                and chunk["source_sha256"] == receipt["artifact_sha256"]
                and digest(chunk["receipt"]) == chunk["receipt_sha256"] == receipt.get("parser_receipt_sha256")
                and chunk["text_sha256"] == receipt.get("chunk_sha256")
                and hashlib.sha256(chunk["chunk_text"].encode()).hexdigest() == receipt.get("chunk_sha256")
                and chunk["locator"] == receipt.get("canonical_locator")
                and position(chunk) == receipt.get("source_position"))
