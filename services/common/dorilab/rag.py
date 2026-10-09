from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import digest


PARSER_NAME = "dorilab-structural-text-parser"
PARSER_VERSION = "dorilab-parser-v1"
CHUNKER_VERSION = "paragraph-1600-v1"
INDEX_VERSION = "postgres-fts-simple-v1"
FILTER_POLICY = "dorilab-operational-reference-scope-v1"
MAX_EXTRACTED_CHARS = 4_000_000
MAX_CHUNK_CHARS = 1_600
MAX_BLOCK_CHARS = 1_200
OPERATIONAL_PURPOSE = "OPERATIONAL_EVIDENCE"
RESERVED_EVALUATION_KEYS = {
    "answer",
    "expected",
    "expected_answer",
    "gold",
    "gold_answer",
    "label",
    "rationale",
    "reference_answer",
}


class DocumentParseError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    text: str
    locator: str
    page_start: int | None
    page_end: int | None
    section_path: list[str]
    content_kind: str
    metadata: dict[str, Any]

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ParsedDocument:
    chunks: list[ChunkDraft]
    page_count: int
    issues: list[dict[str, Any]]
    extraction_sha256: str


@dataclass(frozen=True)
class _Block:
    text: str
    line_start: int
    line_end: int
    section_path: list[str]


def _reserved_keys(value: Any, found: set[str] | None = None) -> set[str]:
    found = found if found is not None else set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in RESERVED_EVALUATION_KEYS:
                found.add(normalized)
            _reserved_keys(child, found)
    elif isinstance(value, list):
        for child in value:
            _reserved_keys(child, found)
    return found


def _decode_text(data: bytes, content_type: str, usage_purpose: str) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("TEXT_ENCODING_UNSUPPORTED", "text documents must be UTF-8") from exc
    if "\x00" in text:
        raise DocumentParseError("BINARY_CONTENT_REJECTED", "NUL bytes are not valid document text")
    if len(text) > MAX_EXTRACTED_CHARS:
        raise DocumentParseError("EXTRACTED_TEXT_LIMIT", "extracted text exceeds 4,000,000 characters")
    if content_type == "application/json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DocumentParseError("INVALID_JSON_DOCUMENT", f"invalid JSON document at line {exc.lineno}") from exc
        if usage_purpose == OPERATIONAL_PURPOSE:
            blocked = sorted(_reserved_keys(parsed))
            if blocked:
                raise DocumentParseError(
                    "RESERVED_EVALUATION_METADATA",
                    "operational RAG JSON contains reserved evaluation fields: " + ",".join(blocked),
                )
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_long_block(block: _Block) -> list[_Block]:
    if len(block.text) <= MAX_BLOCK_CHARS:
        return [block]
    pieces: list[_Block] = []
    remaining = block.text
    while remaining:
        if len(remaining) <= MAX_BLOCK_CHARS:
            cut = len(remaining)
        else:
            cut = remaining.rfind(" ", 0, MAX_BLOCK_CHARS + 1)
            if cut < MAX_BLOCK_CHARS // 2:
                cut = MAX_BLOCK_CHARS
        text = remaining[:cut].strip()
        if text:
            pieces.append(_Block(text, block.line_start, block.line_end, block.section_path))
        remaining = remaining[cut:].lstrip()
    return pieces


def _blocks(text: str, *, markdown: bool) -> list[_Block]:
    lines = text.splitlines()
    section_stack: list[str] = []
    result: list[_Block] = []
    paragraph: list[str] = []
    paragraph_start = 1
    paragraph_section: list[str] = []

    def flush(line_end: int) -> None:
        nonlocal paragraph
        value = "\n".join(paragraph).strip()
        if value:
            result.extend(
                _split_long_block(_Block(value, paragraph_start, line_end, list(paragraph_section)))
            )
        paragraph = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line) if markdown else None
        if heading:
            flush(line_number - 1)
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_stack[:] = section_stack[: level - 1]
            section_stack.append(title)
            paragraph_start = line_number
            paragraph_section = list(section_stack)
            paragraph = [line]
            continue
        if not line.strip():
            flush(line_number - 1)
            paragraph_start = line_number + 1
            paragraph_section = list(section_stack)
            continue
        if not paragraph:
            paragraph_start = line_number
            paragraph_section = list(section_stack)
        paragraph.append(line)
    flush(len(lines))
    return result


def _chunk_blocks(
    blocks: list[_Block],
    *,
    ordinal_start: int,
    page_number: int,
    locator_prefix: str,
    source_kind: str,
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    current: list[_Block] = []
    current_size = 0

    def flush() -> None:
        nonlocal current, current_size
        if not current:
            return
        text = "\n\n".join(block.text for block in current)
        line_start = min(block.line_start for block in current)
        line_end = max(block.line_end for block in current)
        common_section = current[0].section_path if all(
            block.section_path == current[0].section_path for block in current
        ) else []
        section_text = " / ".join(common_section)
        locator = f"{locator_prefix}, lines {line_start}-{line_end}"
        if section_text:
            locator = f"{locator}, section {section_text}"
        chunks.append(
            ChunkDraft(
                ordinal=ordinal_start + len(chunks),
                text=text,
                locator=locator,
                page_start=page_number,
                page_end=page_number,
                section_path=list(common_section),
                content_kind="BODY_TEXT",
                metadata={
                    "source_kind": source_kind,
                    "line_start": line_start,
                    "line_end": line_end,
                    "normalization": "UTF8_NEWLINES_PARAGRAPHS_V1",
                },
            )
        )
        current = []
        current_size = 0

    for block in blocks:
        separator = 2 if current else 0
        section_changed = current and block.section_path != current[-1].section_path
        if current and (current_size + separator + len(block.text) > MAX_CHUNK_CHARS or section_changed):
            flush()
        current.append(block)
        current_size += (2 if len(current) > 1 else 0) + len(block.text)
    flush()
    return chunks


def parse_document(path: Path, content_type: str, usage_purpose: str) -> ParsedDocument:
    data = path.read_bytes()
    issues: list[dict[str, Any]] = []
    chunks: list[ChunkDraft] = []

    if content_type == "application/pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - image build guarantees this dependency
            raise DocumentParseError("PDF_PARSER_UNAVAILABLE", "pypdf is not installed") from exc
        try:
            reader = PdfReader(path)
        except Exception as exc:
            raise DocumentParseError("PDF_PARSE_FAILED", "PDF structure could not be read") from exc
        if reader.is_encrypted:
            raise DocumentParseError("PDF_ENCRYPTED", "encrypted PDF documents are not parsed")
        if len(reader.pages) > 2_000:
            raise DocumentParseError("PDF_PAGE_LIMIT", "PDF exceeds the 2,000 page limit")
        total_chars = 0
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n")
            except Exception as exc:
                issues.append({"code": "PAGE_EXTRACTION_FAILED", "page": page_number, "detail": type(exc).__name__})
                continue
            total_chars += len(text)
            if total_chars > MAX_EXTRACTED_CHARS:
                raise DocumentParseError("EXTRACTED_TEXT_LIMIT", "extracted text exceeds 4,000,000 characters")
            if not text.strip():
                issues.append({"code": "PAGE_TEXT_EMPTY", "page": page_number})
                continue
            page_chunks = _chunk_blocks(
                _blocks(text, markdown=False),
                ordinal_start=len(chunks),
                page_number=page_number,
                locator_prefix=f"PDF page {page_number}",
                source_kind="PDF_TEXT_LAYER",
            )
            chunks.extend(page_chunks)
        page_count = len(reader.pages)
        issues.append({"code": "TABLE_FIGURE_STRUCTURE_NOT_EXTRACTED", "detail": "v1 indexes the PDF text layer only"})
    elif content_type in {"text/plain", "text/markdown", "application/json", "text/csv"}:
        text = _decode_text(data, content_type, usage_purpose)
        chunks = _chunk_blocks(
            _blocks(text, markdown=content_type == "text/markdown"),
            ordinal_start=0,
            page_number=1,
            locator_prefix="text document",
            source_kind="UTF8_TEXT",
        )
        page_count = 1
    else:
        raise DocumentParseError("UNSUPPORTED_DOCUMENT_TYPE", f"unsupported parser content type: {content_type}")

    if not chunks:
        raise DocumentParseError("NO_EXTRACTABLE_TEXT", "document contains no extractable text")
    extraction_hash = digest(
        [
            {
                "ordinal": chunk.ordinal,
                "text_sha256": chunk.text_sha256,
                "locator": chunk.locator,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section_path": chunk.section_path,
            }
            for chunk in chunks
        ]
    )
    return ParsedDocument(chunks, page_count, issues, extraction_hash)


def parser_receipt(artifact: dict, parsed: ParsedDocument) -> dict[str, Any]:
    return {
        "schema": "dorilab.document-parser-receipt.v1",
        "artifact_id": str(artifact["id"]),
        "artifact_sha256": artifact["sha256"],
        "content_type": artifact["content_type"],
        "usage_purpose": artifact["usage_purpose"],
        "parser": {"name": PARSER_NAME, "version": PARSER_VERSION},
        "chunker_version": CHUNKER_VERSION,
        "index_version": INDEX_VERSION,
        "page_count": parsed.page_count,
        "chunk_count": len(parsed.chunks),
        "extraction_sha256": parsed.extraction_sha256,
        "issues": parsed.issues,
        "position_contract": "PAGE_LINE_SECTION",
        "ocr_performed": False,
        "table_figure_structuring": False,
    }


def retrieval_receipt(
    *,
    run_id: str,
    project_id: str,
    claim: dict,
    query: str,
    artifact_ids: list[str],
    top_k: int,
    results: list[dict],
) -> dict[str, Any]:
    return {
        "schema": "dorilab.retrieval-receipt.v1",
        "retrieval_run_id": run_id,
        "project_id": project_id,
        "claim_id": str(claim["id"]),
        "claim_version": claim["version"],
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "query": query,
        "artifact_filter": artifact_ids,
        "top_k": top_k,
        "filter_policy": FILTER_POLICY,
        "usage_purpose": OPERATIONAL_PURPOSE,
        "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "index_version": INDEX_VERSION,
        "ranking": "ts_rank_cd(simple) DESC, artifact_sha256 ASC, chunk_ordinal ASC",
        "results": [
            {
                "chunk_id": str(row["id"]),
                "artifact_id": str(row["artifact_id"]),
                "artifact_sha256": row["artifact_sha256"],
                "text_sha256": row["text_sha256"],
                "candidate_rank": row["candidate_rank"],
                "score": float(row["score"]),
                "selected": row["selected"],
                "reason": row["reason"],
                "locator": row["locator"],
                "parser_receipt_sha256": row["parser_receipt_sha256"],
            }
            for row in results
        ],
        "candidate_count": len(results),
        "selected_count": sum(1 for row in results if row["selected"]),
        "truncated_source_text": False,
    }
