from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from psycopg.errors import UniqueViolation

from .auth import COOKIE_NAME, actor, csrf, issue_session
from .blackboard import append_event, board_projection, create_contribution, create_work_item, link_dependency
from .config import APP_MODE, CONNECTION_CONFIG_PATH, KNOWN_HOSTS_PATH, MODEL_PROFILE
from .citations import receipt_is_current, unresolved_legacy, verify_citation
from .contracts import (DEMO_CONTRACT, LIVE_CONTRACT, ReviewPurpose,
                        assessment_scope, canonical, digest, render_demo, render_live, scope_decision)
from .db import all_rows, connection, one
from .demo_observer import sessions as demo_observer_sessions
from .gates import project_gate_projection, seed_project_gates
from .learning import create_router as create_learning_router
from . import local_connection
from .orchestration import create_native_run, mark_stale, orchestration_projection, resume_after_human
from .rag import (
    CHUNKER_VERSION,
    FILTER_POLICY,
    INDEX_VERSION,
    OPERATIONAL_PURPOSE,
    PARSER_NAME,
    PARSER_VERSION,
    DocumentParseError,
    parse_document,
    parser_receipt,
    retrieval_receipt,
)
from .reports import render_review_markdown
from .storage import resolved_export_path, resolved_path, write_export, write_stream
from .web_assets import LocalWebAssets, html_response


app = FastAPI(title="DoriLab Local MVP", version="1.0.0")
WEB_ROOT = Path("/app/apps/web")
MOCKUP_ROOT = Path("/app/mockup")
FINAL_GOAL_PATH = MOCKUP_ROOT / "DoriLab_Final_Goal_KASA_ECSS_NASA.md"
DEMO_SETUP_FIXTURE_ROOT = Path("/app/fixtures/demo")
DEMO_SETUP_FIXTURE_PATH = DEMO_SETUP_FIXTURE_ROOT / "setup_walkthrough.json"
DEMO_SETUP_DOCUMENT_PATH = DEMO_SETUP_FIXTURE_ROOT / "setup_walkthrough.md"
app.mount("/assets", LocalWebAssets(directory=WEB_ROOT), name="assets")


class SessionRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=160)


class DemoObserverSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["dorilab.demo.observer.v1"] = Field(alias="schema")
    type: Literal["DEMO_STATE"]
    source_instance_id: UUID
    sequence: int = Field(ge=1)
    sent_at: datetime
    project_id: UUID
    project_display_id: str | None = Field(default=None, max_length=80)
    run_key: UUID | None = None
    job_id: UUID | None = None
    mode: Literal["LIVE", "REPLAY"] | None = None
    active: bool
    playing: bool
    step_index: int = Field(ge=0, le=50)
    step_count: int = Field(ge=1, le=50)
    step_title: str = Field(max_length=240)
    execution_status: Literal["IDLE", "UPDATING", "PLAYING", "PAUSED", "COMPLETED", "STOPPED", "FAILED"]
    error: str | None = Field(default=None, max_length=600)


class RunPodConnectionUpdate(BaseModel):
    host: str = Field(pattern=r"^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])$", max_length=253)
    port: int = Field(ge=1, le=65535)


class RunPodHostKeyConfirmation(BaseModel):
    scan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProjectCreate(BaseModel):
    display_id: str = Field(pattern=r"^[A-Za-z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=200)
    framework: str = Field(pattern=r"^(KASA|ECSS|NASA)$")
    framework_edition: str | None = Field(default=None, max_length=100)
    data_policy: str = Field(default="LOCAL_ONLY", pattern=r"^(LOCAL_ONLY|EXTERNAL_SYNTHETIC_ALLOWED|EXTERNAL_ALLOWED)$")
    mode: str = Field(default="DEMO", pattern=r"^(DEMO|LIVE)$")


class ProjectProfileUpdate(BaseModel):
    framework: str = Field(pattern=r"^(KASA|ECSS|NASA)$")
    framework_edition: str | None = Field(default=None, max_length=100)
    expected_version: int = Field(ge=1)


class ProjectDocumentUpsert(BaseModel):
    profile: str = Field(pattern=r"^(KASA|ECSS|NASA)$")
    title: str = Field(min_length=2, max_length=300)
    revision: str = Field(min_length=1, max_length=160)
    product_level: str = Field(min_length=1, max_length=160)
    clause_locator: str = Field(min_length=1, max_length=500)
    adoption_note: str = Field(min_length=1, max_length=4000)


class TailoringCreate(BaseModel):
    profile: str = Field(pattern=r"^(KASA|ECSS|NASA)$")
    title: str = Field(min_length=2, max_length=300)
    clause_locator: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=2, max_length=4000)
    owner: str = Field(min_length=2, max_length=200)


class TailoringDisposition(BaseModel):
    disposition: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    expected_version: int = Field(ge=1)


class GateDecisionCreate(BaseModel):
    disposition: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    note: str = Field(min_length=2, max_length=4000)
    expected_gate_version: int = Field(ge=1)
    expected_project_version: int = Field(ge=1)


class PhaseTransitionCreate(BaseModel):
    disposition: str = Field(pattern=r"^(HOLD|GO)$")
    note: str = Field(min_length=2, max_length=4000)
    expected_project_version: int = Field(ge=1)


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_id: str = Field(min_length=2, max_length=80)
    question: str = Field(min_length=5, max_length=4000)
    review_target: str = Field(default="BM1", pattern=r"^BM1$")
    scope: dict
    review_purpose: ReviewPurpose = "UNSPECIFIED"


class ClaimUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=5, max_length=4000)
    scope: dict
    expected_version: int = Field(ge=1)
    review_purpose: ReviewPurpose | None = None


class RequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_id: str = Field(min_length=2, max_length=80)
    level: Literal["MISSION", "SYSTEM", "SUBSYSTEM", "EQUIPMENT"]
    parent_ref: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=5, max_length=4000)
    verification_method: str = Field(min_length=2, max_length=200)
    owner: str = Field(min_length=2, max_length=200)
    claim_id: UUID | None = None
    claim_label: str = Field(min_length=1, max_length=160)
    source_chapter: int = Field(ge=1, le=20)
    sort_order: int = Field(default=0, ge=0, le=100000)
    review_purpose: ReviewPurpose = "UNSPECIFIED"


class RequirementPurposeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_purpose: ReviewPurpose
    expected_version: int = Field(ge=1)


class CitationPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class ManualCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_chunk_id: UUID | None = None
    cited_edition: str | None = Field(default=None, max_length=160)
    source_position: CitationPosition | None = None


class EvidenceCreate(BaseModel):
    artifact_id: UUID
    display_id: str = Field(min_length=2, max_length=80)
    kind: str = Field(pattern=r"^(REFERENCE|OBSERVATION)$")
    basis: str = Field(default="USER_PROVIDED", max_length=80)
    scope: dict = Field(default_factory=dict)
    locator: str | None = Field(default=None, max_length=500)
    quote: str | None = Field(default=None, max_length=12000)
    provenance: dict = Field(default_factory=dict)
    citation: ManualCitation | None = None


class ReviewCreate(BaseModel):
    claim_id: UUID
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    retrieval_run_id: UUID | None = None
    mode: str = Field(pattern=r"^(SIMULATED|REPLAY|LIVE_MODEL_RUN)$")


class RetrievalCreate(BaseModel):
    claim_id: UUID
    query: str = Field(min_length=2, max_length=1000)
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=4, ge=1, le=20)


class DecisionCreate(BaseModel):
    disposition: str = Field(pattern=r"^(ACCEPTED|REVISION_REQUESTED|REJECTED)$")
    expected_job_version: int = Field(ge=1)
    edited_draft: dict | None = None
    note: str | None = Field(default=None, max_length=4000)


class EvidenceSubmission(BaseModel):
    evidence_id: UUID
    expected_version: int = Field(ge=1)


class EvidenceRequestDecision(BaseModel):
    disposition: str = Field(pattern=r"^(ACCEPTED|REJECTED)$")
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=4000)


class DataQualityAssessmentCreate(BaseModel):
    quality_status: str = Field(pattern=r"^(VALID|LIMITED|INVALID|UNRESOLVED)$")
    note: str = Field(min_length=2, max_length=4000)
    expected_claim_version: int = Field(ge=1)
    expected_project_version: int = Field(ge=1)


class VerificationClosureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: str = Field(pattern=r"^(SATISFIED|NOT_SATISFIED|INCONCLUSIVE)$")
    closure_basis: str = Field(pattern=r"^(COMPLIANCE|NON_COMPLIANCE|INCONCLUSIVE)$")
    note: str = Field(min_length=2, max_length=4000)
    expected_claim_version: int = Field(ge=1)
    expected_project_version: int = Field(ge=1)


class ConfigurationChangeCreate(BaseModel):
    to_baseline: str = Field(min_length=1, max_length=80)
    to_configuration: str = Field(min_length=1, max_length=160)
    to_test_run: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=2, max_length=4000)
    expected_project_version: int = Field(ge=1)


class ConfigurationChangeDecision(BaseModel):
    disposition: str = Field(pattern=r"^(APPLIED|REJECTED)$")
    note: str = Field(min_length=2, max_length=4000)
    expected_change_version: int = Field(ge=1)
    expected_project_version: int = Field(ge=1)


class ContributionCreate(BaseModel):
    claim_id: UUID
    contribution_type: str = Field(pattern=r"^(FACT_PROPOSAL|FINDING|HYPOTHESIS|CHALLENGE)$")
    content: dict
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    expected_project_version: int = Field(ge=1)
    expected_claim_version: int = Field(ge=1)


class ContributionDecision(BaseModel):
    disposition: str = Field(pattern=r"^(ACCEPTED|REVISION_REQUESTED|REJECTED|SUPERSEDED)$")
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=4000)


class WorkItemCreate(BaseModel):
    claim_id: UUID
    work_type: str = Field(pattern=r"^(TASK|TOOL_REQUEST)$")
    title: str = Field(min_length=2, max_length=300)
    purpose: str = Field(min_length=2, max_length=4000)
    input_refs: list[dict] = Field(default_factory=list, max_length=100)
    assigned_role: str = Field(pattern=r"^(EVIDENCE|ANALYSIS|CRITIC|ROUTER|HUMAN|TOOL)$")
    budget: dict = Field(default_factory=dict)
    expected_project_version: int = Field(ge=1)
    expected_claim_version: int = Field(ge=1)


class WorkItemTransition(BaseModel):
    status: str = Field(
        pattern=r"^(OPEN|READY|RUNNING|WAITING_INPUT|WAITING_REVIEW|COMPLETED|CANCELLED|REJECTED)$"
    )
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=4000)


def membership(cur, project_id: UUID, user_id: str, roles: set[str] | None = None) -> dict:
    cur.execute(
        "SELECT role FROM memberships WHERE project_id=%s AND user_id=%s",
        (project_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    if roles and row["role"] not in roles:
        raise HTTPException(status_code=403, detail="project role does not allow this action")
    return row


def audit(cur, project_id, user_id: str, action: str, object_type: str, object_id: str, payload, before_version=None):
    cur.execute(
        """INSERT INTO audit_events(project_id,actor,action,object_type,object_id,before_version,payload_hash)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (project_id, user_id, action, object_type, object_id, before_version, digest(payload)),
    )


app.include_router(create_learning_router(membership, audit))


def stale_current_jobs(
    cur,
    *,
    actor_id: str,
    reason: str,
    project_id: UUID | None = None,
    claim_id: UUID | None = None,
    job_id: UUID | None = None,
) -> int:
    conditions = ["freshness='CURRENT'"]
    params: list = []
    if project_id is not None:
        conditions.append("project_id=%s")
        params.append(project_id)
    if claim_id is not None:
        conditions.append("claim_id=%s")
        params.append(claim_id)
    if job_id is not None:
        conditions.append("id=%s")
        params.append(job_id)
    cur.execute(
        f"SELECT id FROM review_jobs WHERE {' AND '.join(conditions)} FOR UPDATE",
        tuple(params),
    )
    job_ids = [row["id"] for row in cur.fetchall()]
    if not job_ids:
        return 0
    cur.execute(
        """UPDATE review_jobs SET freshness='STALE',version=version+1,updated_at=now()
           WHERE id=ANY(%s)""",
        (job_ids,),
    )
    for stale_job_id in job_ids:
        mark_stale(cur, job_id=stale_job_id, actor_id=actor_id, reason=reason)
    return len(job_ids)


def refresh_source_verifications(cur, project_id, actor_id: str = "system:source-integrity") -> None:
    """Invalidate receipts and only jobs that used those receipts. Never reclassify legacy rows."""
    cur.execute("""SELECT e.id AS evidence_id,e.version AS evidence_version,e.source_verification,
                          s.quote AS submitted_quote,s.locator AS submitted_locator,s.sha256 AS submitted_sha256,a.* FROM evidence e
                   JOIN artifact_versions a ON a.id=e.artifact_id
                   LEFT JOIN source_spans s ON s.id=e.source_span_id
                   WHERE e.project_id=%s AND e.source_verification->>'status'='VALID'
                     AND e.source_verification->>'freshness'='CURRENT' ORDER BY e.id FOR UPDATE OF e""", (project_id,))
    rows = cur.fetchall()
    hash_cache = {}
    for row in rows:
        receipt = row["source_verification"]
        quote_hash = hashlib.sha256((row["submitted_quote"] or "").encode()).hexdigest()
        if (quote_hash == receipt.get("submitted_quote_sha256") == row["submitted_sha256"]
                and row["submitted_locator"] == receipt.get("submitted_locator")
                and receipt_is_current(cur, row, receipt, hash_cache)):
            continue
        updated = {**receipt, "freshness": "STALE", "reason_code": "SOURCE_CHANGED",
                   "original_reason_code": receipt["reason_code"],
                   "invalidated_at": datetime.now(timezone.utc).isoformat()}
        cur.execute("UPDATE evidence SET source_verification=%s::jsonb,version=version+1 WHERE id=%s",
                    (json.dumps(updated), row["evidence_id"]))
        cur.execute("""SELECT j.id FROM review_jobs j JOIN context_snapshots cs ON cs.id=j.snapshot_id
                       WHERE j.project_id=%s AND j.freshness='CURRENT'
                         AND cs.included_evidence_ids @> %s::jsonb""",
                    (project_id, json.dumps([str(row["evidence_id"])])))
        jobs = cur.fetchall()
        for job in jobs:
            stale_current_jobs(cur, job_id=job["id"], actor_id=actor_id, reason="CITATION_SOURCE_CHANGED")
        audit(cur, project_id, actor_id, "INVALIDATE_SOURCE_VERIFICATION", "evidence",
              str(row["evidence_id"]), updated, row["evidence_version"])


def citation_record(row: dict) -> dict:
    return {**row, "source_verification": row.get("source_verification") or unresolved_legacy()}


def _valid_runpod_host(value: str) -> bool:
    if not value or value.startswith("-") or len(value) > 253:
        return False
    return all(character.isalnum() or character in ".-" for character in value) and value[-1].isalnum()


def _read_runpod_connection() -> dict:
    values: dict[str, str] = {}
    try:
        lines = CONNECTION_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {"host": "", "port": None, "configured": False}
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"connection settings are unavailable: {exc.strerror}")
    for line in lines:
        if line.startswith("RUNPOD_HOST="):
            values["host"] = line.removeprefix("RUNPOD_HOST=")
        elif line.startswith("RUNPOD_SSH_PORT="):
            values["port"] = line.removeprefix("RUNPOD_SSH_PORT=")
    host = values.get("host", "")
    port_text = values.get("port", "")
    if not _valid_runpod_host(host) or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        return {"host": host, "port": int(port_text) if port_text.isdigit() else None, "configured": False}
    return {"host": host, "port": int(port_text), "configured": True}


def _write_runpod_connection(host: str, port: int) -> None:
    CONNECTION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = f"RUNPOD_HOST={host}\nRUNPOD_SSH_PORT={port}\n"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CONNECTION_CONFIG_PATH.parent, prefix=".runpod-", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, CONNECTION_CONFIG_PATH)
    except OSError as exc:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=f"connection settings could not be saved: {exc.strerror}")


def _stored_host_key_lines(host: str, port: int) -> list[str]:
    if not KNOWN_HOSTS_PATH.is_file():
        return []
    lookup = f"[{host}]:{port}"
    result = subprocess.run(
        ["ssh-keygen", "-F", lookup, "-f", str(KNOWN_HOSTS_PATH)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip() and not line.startswith("#")]


def _key_material(lines: list[str]) -> set[tuple[str, str]]:
    material: set[tuple[str, str]] = set()
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            material.add((parts[1], parts[2]))
    return material


def _scan_runpod_host_key(host: str, port: int) -> dict:
    try:
        result = subprocess.run(
            ["ssh-keyscan", "-T", "10", "-p", str(port), host],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=503, detail="SSH_UNREACHABLE")
    lines = sorted({line.strip() for line in result.stdout.splitlines() if line.strip() and not line.startswith("#")})
    if not lines:
        raise HTTPException(status_code=503, detail="SSH_UNREACHABLE")
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix="dorilab-host-key-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
        fingerprints_result = subprocess.run(
            ["ssh-keygen", "-lf", str(temporary_path), "-E", "sha256"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
    fingerprints = sorted({line.strip() for line in fingerprints_result.stdout.splitlines() if line.strip()})
    if not fingerprints:
        raise HTTPException(status_code=503, detail="HOST_KEY_SCAN_INVALID")
    return {"lines": lines, "fingerprints": fingerprints, "scan_sha256": hashlib.sha256(payload).hexdigest()}


def _host_key_state(host: str, port: int, scanned_lines: list[str] | None = None) -> str:
    stored = _stored_host_key_lines(host, port)
    if not stored:
        return "HOST_KEY_CONFIRMATION_REQUIRED"
    if scanned_lines is not None and not (_key_material(stored) & _key_material(scanned_lines)):
        return "HOST_KEY_CHANGED"
    return "HOST_KEY_VERIFIED"


def _connection_response(connection_values: dict) -> dict:
    state = "NOT_CONFIGURED"
    if connection_values["configured"]:
        state = _host_key_state(connection_values["host"], connection_values["port"])
    return {
        **connection_values,
        "ssh_user": "root",
        "identity_file": "~/.ssh/id_ed25519",
        "host_key_state": state,
        "controller": local_connection.projection(),
        "runtime": {
            "mode": APP_MODE,
            "remote": (one("SELECT value FROM system_state WHERE key='remote_status'") or {}).get(
                "value", {"state": "LOCAL_ONLY" if APP_MODE == "DEMO" else "SERVICE_NOT_DEPLOYED"}
            ),
        },
    }


def configuration_change_impact(cur, project_id: UUID, project_version: int) -> dict:
    """Count current records that a new project baseline would make non-current."""
    cur.execute(
        """SELECT
             (SELECT count(*) FROM claims WHERE project_id=%s) AS affected_claims,
             (SELECT count(*) FROM review_jobs WHERE project_id=%s AND freshness='CURRENT') AS current_review_jobs,
             (SELECT count(*) FROM gate_decisions WHERE project_id=%s AND source_project_version=%s) AS current_gate_decisions,
             (SELECT count(*) FROM data_quality_assessments WHERE project_id=%s AND source_project_version=%s) AS current_quality_assessments,
             (SELECT count(*) FROM verification_closures WHERE project_id=%s AND source_project_version=%s) AS current_closures,
             (SELECT count(*) FROM evidence_requests WHERE project_id=%s AND status IN ('OPEN','RECEIVED')) AS open_evidence_requests""",
        (
            project_id,
            project_id,
            project_id,
            project_version,
            project_id,
            project_version,
            project_id,
            project_version,
            project_id,
        ),
    )
    return dict(cur.fetchone())


def project_audit_view(cur, project: dict) -> dict:
    project_id = project["id"]
    cur.execute(
        """SELECT
             (SELECT count(*) FROM context_snapshots WHERE project_id=%s) AS execution_snapshots,
             (SELECT count(*) FROM model_runs WHERE project_id=%s) AS model_runs,
             ((SELECT count(*) FROM human_reviews WHERE project_id=%s) +
              (SELECT count(*) FROM gate_decisions WHERE project_id=%s) +
              (SELECT count(*) FROM phase_transition_decisions WHERE project_id=%s) +
              (SELECT count(*) FROM data_quality_assessments WHERE project_id=%s) +
              (SELECT count(*) FROM verification_closures WHERE project_id=%s) +
              (SELECT count(*) FROM configuration_changes WHERE project_id=%s AND status<>'DRAFT')) AS human_records,
             (SELECT count(*) FROM report_exports WHERE project_id=%s) AS report_exports,
             (SELECT count(*) FROM audit_events WHERE project_id=%s) AS audit_events,
             (SELECT count(*) FROM document_parser_runs WHERE project_id=%s AND status='COMPLETED') AS parsed_documents,
             (SELECT count(*) FROM retrieval_runs WHERE project_id=%s AND status='COMPLETED') AS retrieval_runs,
             (SELECT count(*) FROM orchestration_runs WHERE project_id=%s) AS orchestration_runs,
             (SELECT count(*) FROM orchestration_checkpoints oc JOIN orchestration_runs r ON r.id=oc.run_id
                WHERE r.project_id=%s) AS orchestration_checkpoints""",
        (project_id,) * 14,
    )
    summary = dict(cur.fetchone())
    cur.execute(
        """SELECT id,actor,action,object_type,object_id,before_version,payload_hash,created_at
           FROM audit_events WHERE project_id=%s ORDER BY id DESC LIMIT 500""",
        (project_id,),
    )
    events = cur.fetchall()
    cur.execute(
        """SELECT re.id,re.job_id,re.filename,re.content_type,re.byte_size,re.sha256,
                  re.created_by,re.created_at,c.display_id AS claim_display_id,
                  j.status AS job_status,j.freshness AS job_freshness
           FROM report_exports re JOIN review_jobs j ON j.id=re.job_id
           JOIN claims c ON c.id=j.claim_id
           WHERE re.project_id=%s ORDER BY re.created_at DESC""",
        (project_id,),
    )
    reports = cur.fetchall()
    return {"project": project, "summary": summary, "events": events, "reports": reports}


def project_audit_bundle(cur, project: dict) -> dict:
    project_id = project["id"]
    view = project_audit_view(cur, project)
    cur.execute(
        """SELECT j.id,j.claim_id,c.display_id AS claim_display_id,j.mode,j.status,j.freshness,j.version,
                  j.error_code,j.created_by,j.created_at,j.updated_at,
                  cs.id AS snapshot_id,cs.claim_version,cs.project_version,cs.contract_id,
                  cs.model_profile,cs.included_evidence_ids,cs.excluded_evidence,cs.snapshot_sha256,
                  cs.retrieval_run_id,cs.retrieved_chunk_ids,cs.retrieval_receipt,cs.context_budget,
                  mr.id AS model_run_id,mr.raw_artifact_id,mr.raw_sha256,mr.finish_reason,
                  mr.token_usage,mr.receipt,mr.request_id,mr.boot_id,
                  v.status AS validation_status,v.errors AS validation_errors
           FROM review_jobs j JOIN claims c ON c.id=j.claim_id
           JOIN context_snapshots cs ON cs.id=j.snapshot_id
           LEFT JOIN model_runs mr ON mr.job_id=j.id
           LEFT JOIN validations v ON v.model_run_id=mr.id
           WHERE j.project_id=%s ORDER BY j.created_at""",
        (project_id,),
    )
    jobs = cur.fetchall()
    records = {}
    for name, query in {
        "human_reviews": "SELECT * FROM human_reviews WHERE project_id=%s ORDER BY created_at",
        "evidence_requests": "SELECT * FROM evidence_requests WHERE project_id=%s ORDER BY created_at",
        "gate_decisions": "SELECT * FROM gate_decisions WHERE project_id=%s ORDER BY created_at",
        "phase_transitions": "SELECT * FROM phase_transition_decisions WHERE project_id=%s ORDER BY created_at",
        "quality_assessments": "SELECT * FROM data_quality_assessments WHERE project_id=%s ORDER BY created_at",
        "verification_closures": "SELECT * FROM verification_closures WHERE project_id=%s ORDER BY created_at",
        "configuration_changes": "SELECT * FROM configuration_changes WHERE project_id=%s ORDER BY created_at",
        "document_parser_runs": "SELECT * FROM document_parser_runs WHERE project_id=%s ORDER BY started_at",
        "retrieval_runs": "SELECT * FROM retrieval_runs WHERE project_id=%s ORDER BY created_at",
        "orchestration_runs": "SELECT * FROM orchestration_runs WHERE project_id=%s ORDER BY created_at",
        "orchestration_node_attempts": """SELECT a.* FROM orchestration_node_attempts a
            JOIN orchestration_runs r ON r.id=a.run_id WHERE r.project_id=%s ORDER BY a.started_at""",
        "orchestration_checkpoints": """SELECT oc.* FROM orchestration_checkpoints oc
            JOIN orchestration_runs r ON r.id=oc.run_id WHERE r.project_id=%s ORDER BY oc.created_at""",
    }.items():
        cur.execute(query, (project_id,))
        records[name] = cur.fetchall()
    return {
        "schema_id": "dorilab.audit-bundle.v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "authority": "READ_ONLY_PROJECT_PROJECTION",
        "project": project,
        "summary": view["summary"],
        "jobs": jobs,
        "decision_records": records,
        "report_exports": view["reports"],
        "audit_events": view["events"],
    }


REQUIREMENT_SELECT = """
    SELECT r.*, COALESCE(r.claim_label,c.display_id) AS display_claim,
           c.version AS linked_claim_version,
           CASE
             WHEN r.review_purpose='PRODUCT_PERFORMANCE' THEN 'PERFORMANCE_ASSESSMENT_UNSUPPORTED'
             WHEN r.review_purpose='UNSPECIFIED' THEN 'PURPOSE_UNSPECIFIED'
             WHEN r.review_purpose='INPUT_READINESS' AND EXISTS(
               SELECT 1 FROM evidence e WHERE e.project_id=r.project_id
             ) THEN 'EVIDENCE_REGISTERED'
             WHEN r.review_purpose='INPUT_READINESS' THEN 'NEEDS_EVIDENCE'
             ELSE 'PLANNED'
           END AS ui_status
    FROM requirements r LEFT JOIN claims c ON c.id=r.claim_id
"""


def scoped_record(row: dict) -> dict:
    return {**row, "assessment_scope": assessment_scope(row.get("review_purpose"))}


def check_supported_purpose(claim: dict) -> dict:
    scope = assessment_scope(claim.get("review_purpose"))
    if not scope["supported"]:
        raise HTTPException(409, f"{scope['status']}: {scope['review_purpose']}")
    return scope


def verification_projection(cur, project: dict, claim: dict) -> dict:
    """Build a version-scoped closure view from authoritative business records."""
    refresh_source_verifications(cur, project["id"])
    cur.execute(
        """SELECT j.id AS job_id,v.parsed_output,hr.id AS review_id,
                  cs.id AS snapshot_id,cs.review_purpose AS snapshot_review_purpose,
                  jsonb_array_length(cs.included_evidence_ids) AS included_evidence_count
           FROM review_jobs j JOIN context_snapshots cs ON cs.id=j.snapshot_id
           JOIN model_runs mr ON mr.job_id=j.id JOIN validations v ON v.model_run_id=mr.id
           LEFT JOIN human_reviews hr ON hr.job_id=j.id AND hr.disposition='ACCEPTED'
           WHERE j.claim_id=%s AND j.freshness='CURRENT' AND cs.claim_version=%s
             AND cs.project_version=%s AND v.status='VALID'
           ORDER BY (hr.id IS NOT NULL) DESC,mr.created_at DESC LIMIT 1""",
        (claim["id"], claim["version"], project["version"]),
    )
    review = cur.fetchone()
    action = None
    if review and review.get("parsed_output"):
        actions = review["parsed_output"].get("actions") or []
        action = actions[0].get("action") if actions else review["parsed_output"].get("action")

    cur.execute(
        """SELECT * FROM data_quality_assessments
           WHERE claim_id=%s AND source_claim_version=%s AND source_project_version=%s
           ORDER BY created_at DESC LIMIT 1""",
        (claim["id"], claim["version"], project["version"]),
    )
    quality = cur.fetchone()
    cur.execute(
        """SELECT count(*)>0 AND bool_and(review_purpose=%s AND review_purpose<>'UNSPECIFIED') AS ok
           FROM requirements WHERE claim_id=%s""",
        (claim["review_purpose"], claim["id"]),
    )
    has_requirement = bool(cur.fetchone()["ok"])
    cur.execute(
        """SELECT EXISTS(SELECT 1 FROM evidence_requests
               WHERE claim_id=%s AND status IN ('OPEN','RECEIVED')) AS ok""",
        (claim["id"],),
    )
    has_open_request = cur.fetchone()["ok"]
    cur.execute(
        """SELECT EXISTS(
               SELECT 1 FROM gate_decisions gd JOIN review_gates rg ON rg.id=gd.gate_id
               WHERE gd.project_id=%s AND rg.framework=%s AND rg.gate_key='trb'
                 AND gd.disposition='APPROVED' AND gd.source_project_version=%s
           ) AS ok""",
        (project["id"], project["framework"], project["version"]),
    )
    trb_approved = cur.fetchone()["ok"]
    cur.execute(
        """SELECT * FROM verification_closures
           WHERE claim_id=%s AND source_claim_version=%s AND source_project_version=%s
             AND NOT EXISTS(SELECT 1 FROM review_jobs j WHERE j.snapshot_id=verification_closures.source_snapshot_id AND j.freshness='STALE')
           ORDER BY created_at DESC LIMIT 1""",
        (claim["id"], claim["version"], project["version"]),
    )
    current_closure = cur.fetchone()
    scope = assessment_scope(claim["review_purpose"])
    matching_review = bool(review and review["snapshot_review_purpose"] == claim["review_purpose"]
                           and scope["supported"])

    checks = [
        {"code": "REVIEW_PURPOSE", "label": scope["label"], "satisfied": scope["supported"],
         "basis": scope["result_scope"]},
        {"code": "REQUIREMENT_REVISION", "label": "모든 연결 요구사항의 검토 목적 일치", "satisfied": has_requirement,
         "basis": "연결 요구사항의 명시된 목적 일치" if has_requirement else "연결 요구사항 없음 또는 UNSPECIFIED/목적 불일치"},
        {"code": "CURRENT_EVIDENCE", "label": "현재 Snapshot에 검토 근거 포함", "satisfied": bool(review and review["included_evidence_count"]),
         "basis": f"포함 근거 {review['included_evidence_count']}건" if review and review["included_evidence_count"] else "현재 범위에 포함된 근거 없음"},
        {"code": "VALID_RESULT", "label": "현재 version과 목적의 출력 계약 검증", "satisfied": matching_review,
         "basis": f"Job {review['job_id']}" if matching_review else "현재 목적과 일치하는 VALID ModelRun 없음"},
        {"code": "HUMAN_REVIEW_ACCEPTED", "label": "검토 책임자의 초안 수용", "satisfied": bool(review and review["review_id"]),
         "basis": "별도 HumanReview 수용 기록" if review and review["review_id"] else "수용된 사람 검토 없음"},
        {"code": "RULE_JUDGEMENT", "label": "입력준비 검토의 추가 자료 조치 없음", "satisfied": matching_review and action == "NO_ACTION_REQUIRED",
         "basis": scope["no_action_required_meaning"] if matching_review and action == "NO_ACTION_REQUIRED" else (action or "판정 결과 없음")},
        {"code": "NO_OPEN_EVIDENCE_REQUESTS", "label": "미해결 자료 요청 없음", "satisfied": not has_open_request,
         "basis": "모든 요청 처리" if not has_open_request else "OPEN/RECEIVED 자료 요청 존재"},
        {"code": "DATA_QUALITY_VALID", "label": "현재 범위의 데이터 품질 수용", "satisfied": bool(quality and quality["quality_status"] == "VALID"),
         "basis": quality["quality_status"] if quality else "품질 검토 기록 없음"},
        {"code": "TRB_APPROVED", "label": "현재 기준점의 TRB 승인", "satisfied": trb_approved,
         "basis": "TRB 승인 기록" if trb_approved else "현재 project version의 TRB 승인 없음"},
    ]
    return {
        "claim": scoped_record(claim),
        "assessment_scope": scope,
        "checks": checks,
        "ready_for_satisfied": all(item["satisfied"] for item in checks),
        "latest_quality_assessment": quality,
        "current_closure": scoped_record(current_closure) if current_closure else None,
        "latest_job_id": review["job_id"] if review else None,
        "source_snapshot_id": review["snapshot_id"] if matching_review else None,
    }


@app.get("/")
def root():
    return html_response(WEB_ROOT / "index.html", WEB_ROOT)


@app.put("/api/v1/projects/{project_id}/demo-observer/sessions/{source_instance_id}", dependencies=[Depends(csrf)])
def publish_demo_observer(project_id: UUID, source_instance_id: UUID, body: DemoObserverSignal, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
    if body.project_id != project_id or body.source_instance_id != source_instance_id:
        raise HTTPException(422, "Observer signal identity differs from its URL")
    return demo_observer_sessions.publish(str(project_id), str(source_instance_id), body.model_dump(mode="json", by_alias=True))


@app.get("/api/v1/projects/{project_id}/demo-observer/sessions/{source_instance_id}")
def read_demo_observer(project_id: UUID, source_instance_id: UUID, response: Response, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
    signal = demo_observer_sessions.read(str(project_id), str(source_instance_id))
    if signal is None:
        raise HTTPException(404, "Observer session is not available")
    response.headers["Cache-Control"] = "no-store"
    return signal


@app.get("/mockup.css", include_in_schema=False)
def mockup_css():
    """Serve the reference workbench stylesheet without maintaining a divergent copy."""
    source = (MOCKUP_ROOT / "DoriLab_SE_Workbench.html").read_text(encoding="utf-8")
    start = source.index("<style>") + len("<style>")
    end = source.index("</style>", start)
    return Response(content=source[start:end], media_type="text/css")


@app.get("/api/v1/reference/final-goal/download")
def download_final_goal(user_id: str = Depends(actor)):
    return FileResponse(
        FINAL_GOAL_PATH,
        media_type="text/markdown; charset=utf-8",
        filename=FINAL_GOAL_PATH.name,
    )


@app.get("/api/v1/reference/final-goal/chapters/{chapter}")
def get_final_goal_chapter(chapter: int, user_id: str = Depends(actor)):
    if chapter < 1 or chapter > 20:
        raise HTTPException(status_code=404, detail="reference chapter not found")
    source = FINAL_GOAL_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    prefix = f"## {chapter}. "
    start = next((index for index, line in enumerate(lines) if line.startswith(prefix)), None)
    if start is None:
        raise HTTPException(status_code=404, detail="reference chapter not found")
    end = next(
        (index for index, line in enumerate(lines[start + 1 :], start + 1) if line.startswith("## ")),
        len(lines),
    )
    content = "\n".join(lines[start:end]).strip()
    return {
        "chapter": chapter,
        "title": lines[start].removeprefix("## "),
        "content": content,
        "source": FINAL_GOAL_PATH.name,
        "sha256": hashlib.sha256(FINAL_GOAL_PATH.read_bytes()).hexdigest(),
    }


@app.get("/api/v1/demo/setup-fixture")
def get_demo_setup_fixture(response: Response, user_id: str = Depends(actor)):
    """Return the immutable setup walkthrough inputs without creating business state."""
    fixture = json.loads(DEMO_SETUP_FIXTURE_PATH.read_text(encoding="utf-8"))
    document_text = DEMO_SETUP_DOCUMENT_PATH.read_text(encoding="utf-8")
    response.headers["Cache-Control"] = "no-store"
    return {"fixture": fixture, "document_text": document_text}


@app.get("/healthz")
def healthz():
    row = one("SELECT 1 AS ok")
    return {"status": "ok" if row and row["ok"] == 1 else "error", "database": "READY"}


@app.post("/api/v1/session")
def create_session(body: SessionRequest, response: Response):
    user = one("SELECT id,display_name FROM users WHERE id=%s", (body.user_id,))
    if not user:
        raise HTTPException(status_code=401, detail="unknown internal user")
    response.set_cookie(COOKIE_NAME, issue_session(body.user_id), httponly=True, samesite="strict", secure=False, max_age=12 * 3600)
    return {"user": user, "auth_mode": "LOCAL_INTERNAL_SESSION"}


@app.delete("/api/v1/session", dependencies=[Depends(csrf)])
def delete_session(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "signed_out"}


@app.get("/api/v1/status")
def system_status(user_id: str = Depends(actor)):
    remote = one("SELECT value,updated_at FROM system_state WHERE key='remote_status'")
    return {
        "backend": "READY",
        "database": "READY",
        "mode": APP_MODE,
        "remote": remote["value"] if remote else {"state": "LOCAL_ONLY" if APP_MODE == "DEMO" else "SERVICE_NOT_DEPLOYED"},
        "model_profile": MODEL_PROFILE,
        "user": user_id,
    }


@app.get("/api/v1/projects/{project_id}/runpod-connection")
def get_runpod_connection(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
    return _connection_response(_read_runpod_connection())


@app.put("/api/v1/projects/{project_id}/runpod-connection", dependencies=[Depends(csrf)])
def update_runpod_connection(project_id: UUID, body: RunPodConnectionUpdate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        local_connection.lock(cur)
        if local_connection.pending():
            raise HTTPException(status_code=409, detail="CONNECTION_APPLY_IN_PROGRESS")
        before = _read_runpod_connection()
        _write_runpod_connection(body.host, body.port)
        audit(
            cur,
            project_id,
            user_id,
            "UPDATE_RUNPOD_CONNECTION",
            "runpod_connection",
            f"{body.host}:{body.port}",
            {"host": body.host, "port": body.port, "previously_configured": before["configured"]},
        )
    return _connection_response(_read_runpod_connection())


@app.post("/api/v1/projects/{project_id}/runpod-connection/apply", status_code=202, dependencies=[Depends(csrf)])
def apply_runpod_connection(project_id: UUID, body: RunPodConnectionUpdate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        local_connection.lock(cur)
        values = _read_runpod_connection()
        if not values["configured"] or values["host"] != body.host or values["port"] != body.port:
            raise HTTPException(status_code=409, detail="CONNECTION_SETTINGS_CHANGED")
        if _host_key_state(body.host, body.port) != "HOST_KEY_VERIFIED":
            raise HTTPException(status_code=409, detail="HOST_KEY_CONFIRMATION_REQUIRED")
        if not local_connection.controller_available():
            raise HTTPException(status_code=409, detail="LOCAL_CONNECTOR_NOT_RUNNING: ./scripts/dev.sh up")
        if local_connection.pending():
            return {"request_id": local_connection.projection()["request_id"], "status": "IN_PROGRESS"}
        applied = local_connection.projection()
        if (APP_MODE == "LIVE" and applied["phase"] == "APPLIED" and applied["code"] == "APPLIED"
                and applied["applied_host"] == body.host and applied["applied_port"] == str(body.port)):
            cur.execute("SELECT value,updated_at FROM system_state WHERE key='remote_status'")
            remote = cur.fetchone()
            # A restored Pod may have a new token at the same address. Only a
            # recent authenticated receipt permits skipping connection recovery.
            if (remote and remote["value"].get("receipt")
                    and remote["value"].get("state") in {"READY", "MODEL_RELEASE_MISMATCH"}
                    and 0 <= (datetime.now(timezone.utc) - remote["updated_at"]).total_seconds() <= 30):
                return {"request_id": applied["request_id"], "status": "APPLIED", "unchanged": True}
        # Do not replace transport or restart a worker with an admitted job in flight.
        cur.execute("SELECT count(*) AS count FROM review_jobs WHERE status IN "
                    "('QUEUED','DISPATCHING','RUNNING','OUTPUT_RECEIVED','VALIDATING')")
        if cur.fetchone()["count"]:
            raise HTTPException(status_code=409, detail="CONNECTION_CHANGE_BUSY: wait for current reviews")
        try:
            request_id = local_connection.request_apply(body.host, body.port)
        except OSError:
            raise HTTPException(status_code=503, detail="LOCAL_CONNECTOR_REQUEST_FAILED")
        audit(cur, project_id, user_id, "APPLY_RUNPOD_CONNECTION", "runpod_connection", request_id,
              {"host": body.host, "port": body.port, "requested_mode": "LIVE"})
    return {"request_id": request_id, "status": "REQUESTED"}


@app.post("/api/v1/projects/{project_id}/runpod-connection/scan-host-key", dependencies=[Depends(csrf)])
def scan_runpod_host_key(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
    values = _read_runpod_connection()
    if not values["configured"]:
        raise HTTPException(status_code=409, detail="RunPod connection is not configured")
    scan = _scan_runpod_host_key(values["host"], values["port"])
    return {
        "host": values["host"],
        "port": values["port"],
        "host_key_state": _host_key_state(values["host"], values["port"], scan["lines"]),
        "fingerprints": scan["fingerprints"],
        "scan_sha256": scan["scan_sha256"],
    }


@app.post("/api/v1/projects/{project_id}/runpod-connection/confirm-host-key", dependencies=[Depends(csrf)])
def confirm_runpod_host_key(
    project_id: UUID, body: RunPodHostKeyConfirmation, user_id: str = Depends(actor)
):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        values = _read_runpod_connection()
        if not values["configured"]:
            raise HTTPException(status_code=409, detail="RunPod connection is not configured")
        scan = _scan_runpod_host_key(values["host"], values["port"])
        state = _host_key_state(values["host"], values["port"], scan["lines"])
        if state == "HOST_KEY_CHANGED":
            raise HTTPException(status_code=409, detail="HOST_KEY_CHANGED: the stored key was not replaced")
        if scan["scan_sha256"] != body.scan_sha256:
            raise HTTPException(status_code=409, detail="host key changed after fingerprint review; scan again")
        if state == "HOST_KEY_CONFIRMATION_REQUIRED":
            KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            try:
                with KNOWN_HOSTS_PATH.open("a", encoding="utf-8") as known_hosts:
                    known_hosts.write("\n".join(scan["lines"]) + "\n")
                    known_hosts.flush()
                    os.fsync(known_hosts.fileno())
                KNOWN_HOSTS_PATH.chmod(0o600)
            except OSError as exc:
                raise HTTPException(status_code=503, detail=f"known_hosts could not be updated: {exc.strerror}")
            audit(
                cur,
                project_id,
                user_id,
                "CONFIRM_RUNPOD_HOST_KEY",
                "runpod_host_key",
                f"{values['host']}:{values['port']}",
                {"scan_sha256": scan["scan_sha256"], "fingerprints": scan["fingerprints"]},
            )
    return {
        "host": values["host"],
        "port": values["port"],
        "host_key_state": "HOST_KEY_VERIFIED",
        "fingerprints": scan["fingerprints"],
    }


@app.get("/api/v1/projects")
def list_projects(user_id: str = Depends(actor)):
    return all_rows(
        """SELECT p.*,m.role FROM projects p JOIN memberships m ON m.project_id=p.id
           WHERE m.user_id=%s ORDER BY p.created_at""",
        (user_id,),
    )


@app.post("/api/v1/projects", status_code=201, dependencies=[Depends(csrf)])
def create_project(body: ProjectCreate, user_id: str = Depends(actor)):
    project_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """INSERT INTO projects(id,display_id,name,framework,framework_edition,data_policy,mode)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (project_id, body.display_id, body.name, body.framework, body.framework_edition, body.data_policy, body.mode),
            )
            project = cur.fetchone()
            cur.execute("INSERT INTO memberships(project_id,user_id,role) VALUES (%s,%s,'approver')", (project_id, user_id))
            seed_project_gates(cur, project_id, body.framework, user_id)
            audit(cur, project_id, user_id, "CREATE", "project", str(project_id), body.model_dump())
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="project display_id already exists")
    return project


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        return cur.fetchone()


@app.get("/api/v1/projects/{project_id}/blackboard")
def get_blackboard(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        return board_projection(cur, project_id)


@app.post("/api/v1/projects/{project_id}/blackboard/contributions", status_code=201, dependencies=[Depends(csrf)])
def propose_contribution(
    project_id: UUID,
    body: ContributionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    user_id: str = Depends(actor),
):
    evidence_refs = [str(value) for value in body.evidence_ids]
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        cur.execute(
            "SELECT * FROM agent_contributions WHERE project_id=%s AND idempotency_key=%s",
            (project_id, idempotency_key),
        )
        existing = cur.fetchone()
        if not existing:
            cur.execute("SELECT version FROM projects WHERE id=%s FOR SHARE", (project_id,))
            project = cur.fetchone()
            cur.execute(
                "SELECT version FROM claims WHERE id=%s AND project_id=%s FOR SHARE",
                (body.claim_id, project_id),
            )
            claim = cur.fetchone()
            if not claim:
                raise HTTPException(status_code=404, detail="claim not found in project")
            if project["version"] != body.expected_project_version or claim["version"] != body.expected_claim_version:
                raise HTTPException(status_code=409, detail="project or claim version conflict")
            if evidence_refs:
                cur.execute(
                    "SELECT id FROM evidence WHERE project_id=%s AND id=ANY(%s)",
                    (project_id, body.evidence_ids),
                )
                if len(cur.fetchall()) != len(set(body.evidence_ids)):
                    raise HTTPException(status_code=422, detail="unprovided or cross-project evidence id")
        try:
            contribution, replay = create_contribution(
                cur,
                project_id=project_id,
                claim_id=body.claim_id,
                contribution_type=body.contribution_type,
                target_object_type="CLAIM",
                target_object_id=body.claim_id,
                content=body.content,
                evidence_refs=evidence_refs,
                actor_type="HUMAN",
                actor_id=user_id,
                read_project_version=body.expected_project_version,
                read_claim_version=body.expected_claim_version,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            if str(exc) == "IDEMPOTENCY_CONFLICT":
                raise HTTPException(status_code=409, detail="idempotency key reused with different contribution")
            raise
        if not replay:
            audit(
                cur,
                project_id,
                user_id,
                "PROPOSE",
                "agent_contribution",
                str(contribution["id"]),
                body.model_dump(mode="json"),
            )
        return {"contribution": contribution, "idempotent_replay": replay}


@app.post("/api/v1/blackboard/contributions/{contribution_id}/decisions", dependencies=[Depends(csrf)])
def decide_contribution(contribution_id: UUID, body: ContributionDecision, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM agent_contributions WHERE id=%s FOR UPDATE", (contribution_id,))
        contribution = cur.fetchone()
        if not contribution:
            raise HTTPException(status_code=404, detail="contribution not found")
        membership(cur, contribution["project_id"], user_id, {"reviewer", "approver"})
        if contribution["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="contribution version conflict")
        if contribution["status"] not in {"PROPOSED", "REVISION_REQUESTED"}:
            raise HTTPException(status_code=409, detail="contribution already decided")
        if body.disposition == "ACCEPTED":
            cur.execute("SELECT version FROM projects WHERE id=%s", (contribution["project_id"],))
            project = cur.fetchone()
            current_claim_version = None
            if contribution["claim_id"]:
                cur.execute("SELECT version FROM claims WHERE id=%s", (contribution["claim_id"],))
                claim = cur.fetchone()
                current_claim_version = claim["version"] if claim else None
            if (
                project["version"] != contribution["read_project_version"]
                or current_claim_version != contribution["read_claim_version"]
            ):
                raise HTTPException(status_code=409, detail="contribution is stale")
        cur.execute(
            """UPDATE agent_contributions SET status=%s,reviewed_by=%s,review_note=%s,
                      decided_at=now(),version=version+1,updated_at=now() WHERE id=%s RETURNING *""",
            (body.disposition, user_id, body.note, contribution_id),
        )
        row = cur.fetchone()
        append_event(
            cur,
            project_id=contribution["project_id"],
            event_type="CONTRIBUTION_DECIDED",
            object_type="CONTRIBUTION",
            object_id=str(contribution_id),
            actor_type="HUMAN",
            actor_id=user_id,
            payload={"disposition": body.disposition, "note": body.note},
            source_version=contribution["version"],
            result_version=row["version"],
            idempotency_key=f"contribution:{contribution_id}:decision:{row['version']}",
        )
        audit(
            cur,
            contribution["project_id"],
            user_id,
            "DECIDE",
            "agent_contribution",
            str(contribution_id),
            body.model_dump(),
            contribution["version"],
        )
        return row


@app.post("/api/v1/projects/{project_id}/blackboard/work-items", status_code=201, dependencies=[Depends(csrf)])
def add_work_item(
    project_id: UUID,
    body: WorkItemCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    user_id: str = Depends(actor),
):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        cur.execute("SELECT * FROM work_items WHERE project_id=%s AND idempotency_key=%s", (project_id, idempotency_key))
        existing = cur.fetchone()
        if not existing:
            cur.execute("SELECT version FROM projects WHERE id=%s FOR SHARE", (project_id,))
            project = cur.fetchone()
            cur.execute("SELECT version FROM claims WHERE id=%s AND project_id=%s FOR SHARE", (body.claim_id, project_id))
            claim = cur.fetchone()
            if not claim:
                raise HTTPException(status_code=404, detail="claim not found in project")
            if project["version"] != body.expected_project_version or claim["version"] != body.expected_claim_version:
                raise HTTPException(status_code=409, detail="project or claim version conflict")
        try:
            work_item, replay = create_work_item(
                cur,
                project_id=project_id,
                claim_id=body.claim_id,
                work_type=body.work_type,
                title=body.title,
                purpose=body.purpose,
                input_refs=body.input_refs,
                assigned_role=body.assigned_role,
                budget=body.budget,
                status="OPEN",
                idempotency_key=idempotency_key,
                actor_type="HUMAN",
                actor_id=user_id,
                source_project_version=body.expected_project_version,
                source_claim_version=body.expected_claim_version,
            )
        except ValueError as exc:
            if str(exc) == "IDEMPOTENCY_CONFLICT":
                raise HTTPException(status_code=409, detail="idempotency key reused with different work item")
            raise
        if not replay:
            audit(cur, project_id, user_id, "CREATE", "work_item", str(work_item["id"]), body.model_dump(mode="json"))
        return {"work_item": work_item, "idempotent_replay": replay}


@app.post("/api/v1/blackboard/work-items/{work_item_id}/transitions", dependencies=[Depends(csrf)])
def transition_work_item(work_item_id: UUID, body: WorkItemTransition, user_id: str = Depends(actor)):
    allowed = {
        "OPEN": {"READY", "WAITING_INPUT", "CANCELLED"},
        "READY": {"RUNNING", "CANCELLED"},
        "RUNNING": {"WAITING_INPUT", "WAITING_REVIEW", "COMPLETED", "CANCELLED"},
        "WAITING_INPUT": {"READY", "CANCELLED"},
        "WAITING_REVIEW": {"COMPLETED", "REJECTED"},
    }
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM work_items WHERE id=%s FOR UPDATE", (work_item_id,))
        item = cur.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="work item not found")
        roles = {"reviewer", "approver"} if body.status in {"COMPLETED", "REJECTED"} else {"engineer", "reviewer", "approver"}
        membership(cur, item["project_id"], user_id, roles)
        if item["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="work item version conflict")
        if body.status not in allowed.get(item["status"], set()):
            raise HTTPException(status_code=409, detail="invalid work item transition")
        cur.execute(
            "UPDATE work_items SET status=%s,version=version+1,updated_at=now() WHERE id=%s RETURNING *",
            (body.status, work_item_id),
        )
        row = cur.fetchone()
        append_event(
            cur,
            project_id=item["project_id"],
            event_type="WORK_ITEM_TRANSITIONED",
            object_type="WORK_ITEM",
            object_id=str(work_item_id),
            actor_type="HUMAN",
            actor_id=user_id,
            payload={"from": item["status"], "to": body.status, "note": body.note},
            source_version=item["version"],
            result_version=row["version"],
            idempotency_key=f"work-item:{work_item_id}:transition:{row['version']}",
        )
        audit(cur, item["project_id"], user_id, "TRANSITION", "work_item", str(work_item_id), body.model_dump(), item["version"])
        return row


@app.get("/api/v1/projects/{project_id}/profile")
def get_project_profile(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        cur.execute("SELECT * FROM project_documents WHERE project_id=%s ORDER BY profile,document_code", (project_id,))
        documents = cur.fetchall()
        cur.execute("SELECT * FROM tailoring_decisions WHERE project_id=%s ORDER BY created_at", (project_id,))
        tailoring = cur.fetchall()
        return {"project": project, "documents": documents, "tailoring": tailoring}


@app.put("/api/v1/projects/{project_id}/profile", dependencies=[Depends(csrf)])
def update_project_profile(project_id: UUID, body: ProjectProfileUpdate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        if project["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        if project["framework"] == body.framework and project["framework_edition"] == body.framework_edition:
            return project
        cur.execute(
            """UPDATE projects SET framework=%s,framework_edition=%s,adoption_status='UNCONFIRMED',
                      version=version+1,updated_at=now() WHERE id=%s RETURNING *""",
            (body.framework, body.framework_edition, project_id),
        )
        updated = cur.fetchone()
        seed_project_gates(cur, project_id, body.framework, user_id)
        stale_current_jobs(cur, project_id=project_id, actor_id=user_id, reason="PROJECT_PROFILE_CHANGED")
        cur.execute("UPDATE claims SET status='OPEN',updated_at=now() WHERE project_id=%s AND status<>'OPEN'", (project_id,))
        audit(cur, project_id, user_id, "UPDATE_PROFILE", "project", str(project_id), body.model_dump(), project["version"])
        return updated


@app.put("/api/v1/projects/{project_id}/documents/{document_code}", dependencies=[Depends(csrf)])
def upsert_project_document(project_id: UUID, document_code: str, body: ProjectDocumentUpsert, user_id: str = Depends(actor)):
    if not document_code or len(document_code) > 100 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-" for ch in document_code):
        raise HTTPException(status_code=422, detail="invalid document code")
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        document_id = uuid4()
        cur.execute(
            """INSERT INTO project_documents(id,project_id,profile,document_code,title,revision,
                       product_level,clause_locator,adoption_note,created_by,updated_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (project_id,profile,document_code) DO UPDATE SET
                 title=excluded.title,revision=excluded.revision,product_level=excluded.product_level,
                 clause_locator=excluded.clause_locator,adoption_note=excluded.adoption_note,
                 updated_by=excluded.updated_by,version=project_documents.version+1,updated_at=now()
               RETURNING *""",
            (document_id, project_id, body.profile, document_code, body.title, body.revision,
             body.product_level, body.clause_locator, body.adoption_note, user_id, user_id),
        )
        row = cur.fetchone()
        audit(cur, project_id, user_id, "UPSERT", "project_document", str(row["id"]), {"document_code": document_code, **body.model_dump()})
        return row


@app.post("/api/v1/projects/{project_id}/tailoring", status_code=201, dependencies=[Depends(csrf)])
def create_tailoring(project_id: UUID, body: TailoringCreate, user_id: str = Depends(actor)):
    tailoring_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        cur.execute(
            """INSERT INTO tailoring_decisions(id,project_id,profile,title,clause_locator,reason,owner,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (tailoring_id, project_id, body.profile, body.title, body.clause_locator, body.reason, body.owner, user_id),
        )
        row = cur.fetchone()
        audit(cur, project_id, user_id, "CREATE", "tailoring_decision", str(tailoring_id), body.model_dump())
        return row


@app.post("/api/v1/tailoring/{tailoring_id}/decision", dependencies=[Depends(csrf)])
def decide_tailoring(tailoring_id: UUID, body: TailoringDisposition, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM tailoring_decisions WHERE id=%s FOR UPDATE", (tailoring_id,))
        tailoring = cur.fetchone()
        if not tailoring:
            raise HTTPException(status_code=404, detail="tailoring decision not found")
        membership(cur, tailoring["project_id"], user_id, {"approver"})
        if tailoring["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="tailoring version conflict")
        if tailoring["status"] != "DRAFT":
            raise HTTPException(status_code=409, detail="tailoring decision already decided")
        cur.execute(
            """UPDATE tailoring_decisions SET status=%s,decided_by=%s,decided_at=now(),
                      version=version+1,updated_at=now() WHERE id=%s RETURNING *""",
            (body.disposition, user_id, tailoring_id),
        )
        row = cur.fetchone()
        audit(cur, tailoring["project_id"], user_id, "DECIDE", "tailoring_decision", str(tailoring_id), body.model_dump(), tailoring["version"])
        return row


@app.get("/api/v1/projects/{project_id}/claims")
def list_claims(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM claims WHERE project_id=%s ORDER BY created_at", (project_id,))
        return [scoped_record(row) for row in cur.fetchall()]


@app.get("/api/v1/claims/{claim_id}")
def get_claim(claim_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM claims WHERE id=%s", (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found")
        membership(cur, claim["project_id"], user_id)
        cur.execute("SELECT * FROM claim_revisions WHERE claim_id=%s ORDER BY version DESC", (claim_id,))
        revisions = cur.fetchall()
        cur.execute("SELECT id,display_id,level,parent_ref,review_purpose FROM requirements WHERE claim_id=%s ORDER BY sort_order", (claim_id,))
        requirements = cur.fetchall()
        return {"claim": scoped_record(claim), "revisions": [scoped_record(row) for row in revisions],
                "requirements": [scoped_record(row) for row in requirements]}


@app.get("/api/v1/projects/{project_id}/closure")
def get_verification_closure(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        cur.execute("SELECT * FROM claims WHERE project_id=%s ORDER BY created_at", (project_id,))
        claims = cur.fetchall()
        projections = [verification_projection(cur, project, claim) for claim in claims]
        cur.execute(
            """SELECT vc.*,c.display_id AS claim_display_id
               FROM verification_closures vc JOIN claims c ON c.id=vc.claim_id
               WHERE vc.project_id=%s ORDER BY vc.created_at DESC""",
            (project_id,),
        )
        history = [scoped_record(row) for row in cur.fetchall()]
        return {"project": project, "claims": projections, "history": history}


@app.post("/api/v1/claims/{claim_id}/quality-assessments", status_code=201, dependencies=[Depends(csrf)])
def create_data_quality_assessment(claim_id: UUID, body: DataQualityAssessmentCreate, user_id: str = Depends(actor)):
    assessment_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM claims WHERE id=%s FOR SHARE", (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found")
        membership(cur, claim["project_id"], user_id, {"reviewer", "approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR SHARE", (claim["project_id"],))
        project = cur.fetchone()
        if claim["version"] != body.expected_claim_version:
            raise HTTPException(status_code=409, detail="claim version conflict")
        if project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        projection = verification_projection(cur, project, claim)
        valid_result = next(item for item in projection["checks"] if item["code"] == "VALID_RESULT")
        if not valid_result["satisfied"]:
            raise HTTPException(status_code=409, detail="current validated review result is required before quality assessment")
        cur.execute(
            """INSERT INTO data_quality_assessments(id,project_id,claim_id,quality_status,note,actor,
                      source_claim_version,source_project_version,baseline_display_id,product_configuration,test_run)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (assessment_id, project["id"], claim["id"], body.quality_status, body.note, user_id,
             claim["version"], project["version"], project["baseline_display_id"],
             project["product_configuration"], project["test_run"]),
        )
        row = cur.fetchone()
        audit(cur, project["id"], user_id, "ASSESS_DATA_QUALITY", "data_quality_assessment",
              str(assessment_id), body.model_dump(), claim["version"])
        return row


@app.post("/api/v1/claims/{claim_id}/closures", status_code=201, dependencies=[Depends(csrf)])
def create_verification_closure(claim_id: UUID, body: VerificationClosureCreate, user_id: str = Depends(actor)):
    closure_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM claims WHERE id=%s FOR UPDATE", (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found")
        membership(cur, claim["project_id"], user_id, {"approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR SHARE", (claim["project_id"],))
        project = cur.fetchone()
        if claim["version"] != body.expected_claim_version:
            raise HTTPException(status_code=409, detail="claim version conflict")
        if project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        projection = verification_projection(cur, project, claim)
        if projection["current_closure"]:
            raise HTTPException(status_code=409, detail="claim is already closed for this version")
        check_supported_purpose(claim)
        if body.result != "SATISFIED" or body.closure_basis != "COMPLIANCE":
            raise HTTPException(status_code=409, detail="this MVP records only evidence-based SATISFIED closure")
        if not projection["ready_for_satisfied"]:
            missing = [item["code"] for item in projection["checks"] if not item["satisfied"]]
            raise HTTPException(status_code=409, detail=f"closure prerequisites unresolved: {','.join(missing)}")
        quality = projection["latest_quality_assessment"]
        try:
            cur.execute(
                """INSERT INTO verification_closures(id,project_id,claim_id,result,closure_basis,note,actor,
                          source_claim_version,source_project_version,source_quality_assessment_id,scope,
                          baseline_display_id,product_configuration,test_run,review_purpose,source_snapshot_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *""",
                (closure_id, project["id"], claim["id"], body.result, body.closure_basis, body.note, user_id,
                 claim["version"], project["version"], quality["id"], json.dumps(claim["scope"]),
                 project["baseline_display_id"], project["product_configuration"], project["test_run"],
                 claim["review_purpose"], projection["source_snapshot_id"]),
            )
            row = cur.fetchone()
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="claim is already closed for this version")
        cur.execute("UPDATE claims SET status=%s,updated_at=now() WHERE id=%s", (body.result, claim_id))
        audit(cur, project["id"], user_id, "CLOSE_VERIFICATION", "verification_closure",
              str(closure_id), body.model_dump(), claim["version"])
        return scoped_record(row)


@app.get("/api/v1/projects/{project_id}/changes")
def list_configuration_changes(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        cur.execute(
            """SELECT * FROM configuration_changes
               WHERE project_id=%s ORDER BY created_at DESC""",
            (project_id,),
        )
        changes = cur.fetchall()
        return {
            "project": project,
            "impact": configuration_change_impact(cur, project_id, project["version"]),
            "changes": changes,
        }


@app.post("/api/v1/projects/{project_id}/changes", status_code=201, dependencies=[Depends(csrf)])
def create_configuration_change(project_id: UUID, body: ConfigurationChangeCreate, user_id: str = Depends(actor)):
    target = {
        "baseline": body.to_baseline.strip(),
        "configuration": body.to_configuration.strip(),
        "test_run": body.to_test_run.strip(),
    }
    if not all(target.values()) or not body.reason.strip():
        raise HTTPException(status_code=422, detail="baseline, configuration, test run and reason are required")
    change_id = uuid4()
    change_code = f"CHG-{change_id.hex[:8].upper()}"
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR SHARE", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        if project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        current = (
            project["baseline_display_id"],
            project["product_configuration"],
            project["test_run"],
        )
        proposed = (target["baseline"], target["configuration"], target["test_run"])
        if current == proposed:
            raise HTTPException(status_code=409, detail="change target matches the current baseline")
        impact = configuration_change_impact(cur, project_id, project["version"])
        cur.execute(
            """INSERT INTO configuration_changes(
                     id,project_id,change_code,from_baseline,to_baseline,
                     from_configuration,to_configuration,from_test_run,to_test_run,
                     reason,impact_assessment,requested_by,source_project_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               RETURNING *""",
            (
                change_id,
                project_id,
                change_code,
                project["baseline_display_id"],
                target["baseline"],
                project["product_configuration"],
                target["configuration"],
                project["test_run"],
                target["test_run"],
                body.reason.strip(),
                json.dumps(impact),
                user_id,
                project["version"],
            ),
        )
        row = cur.fetchone()
        audit(
            cur,
            project_id,
            user_id,
            "CREATE_CONFIGURATION_CHANGE",
            "configuration_change",
            str(change_id),
            body.model_dump(),
            project["version"],
        )
        return row


@app.post("/api/v1/changes/{change_id}/decision", dependencies=[Depends(csrf)])
def decide_configuration_change(change_id: UUID, body: ConfigurationChangeDecision, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM configuration_changes WHERE id=%s FOR UPDATE", (change_id,))
        change = cur.fetchone()
        if not change:
            raise HTTPException(status_code=404, detail="configuration change not found")
        membership(cur, change["project_id"], user_id, {"approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (change["project_id"],))
        project = cur.fetchone()
        if change["version"] != body.expected_change_version:
            raise HTTPException(status_code=409, detail="configuration change version conflict")
        if project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        if change["status"] != "DRAFT":
            raise HTTPException(status_code=409, detail="configuration change already decided")

        invalidated_jobs = 0
        reopened_claims = 0
        if body.disposition == "APPLIED":
            current = (
                project["baseline_display_id"],
                project["product_configuration"],
                project["test_run"],
            )
            source = (change["from_baseline"], change["from_configuration"], change["from_test_run"])
            if change["source_project_version"] != project["version"] or source != current:
                raise HTTPException(status_code=409, detail="configuration change source is no longer current")
            cur.execute(
                """UPDATE projects SET baseline_display_id=%s,product_configuration=%s,test_run=%s,
                          version=version+1,updated_at=now() WHERE id=%s RETURNING *""",
                (
                    change["to_baseline"],
                    change["to_configuration"],
                    change["to_test_run"],
                    project["id"],
                ),
            )
            project = cur.fetchone()
            invalidated_jobs = stale_current_jobs(
                cur,
                project_id=project["id"],
                actor_id=user_id,
                reason="CONFIGURATION_BASELINE_CHANGED",
            )
            cur.execute(
                """UPDATE claims SET status='OPEN',updated_at=now()
                   WHERE project_id=%s AND status<>'OPEN'""",
                (project["id"],),
            )
            reopened_claims = cur.rowcount

        cur.execute(
            """UPDATE configuration_changes SET status=%s,decided_by=%s,decision_note=%s,
                      decided_at=now(),version=version+1,updated_at=now()
               WHERE id=%s RETURNING *""",
            (body.disposition, user_id, body.note.strip(), change_id),
        )
        decided = cur.fetchone()
        audit(
            cur,
            change["project_id"],
            user_id,
            "APPLY_CONFIGURATION_CHANGE" if body.disposition == "APPLIED" else "REJECT_CONFIGURATION_CHANGE",
            "configuration_change",
            str(change_id),
            body.model_dump(),
            change["version"],
        )
        return {
            "change": decided,
            "project": project,
            "invalidated_review_jobs": invalidated_jobs,
            "reopened_claims": reopened_claims,
        }


@app.get("/api/v1/projects/{project_id}/requirements")
def list_requirements(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute(REQUIREMENT_SELECT + " WHERE r.project_id=%s ORDER BY r.sort_order,r.display_id", (project_id,))
        return [scoped_record(row) for row in cur.fetchall()]


@app.post("/api/v1/projects/{project_id}/requirements", status_code=201, dependencies=[Depends(csrf)])
def create_requirement(project_id: UUID, body: RequirementCreate, user_id: str = Depends(actor)):
    requirement_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        if body.claim_id is not None:
            cur.execute(
                "SELECT * FROM claims WHERE id=%s AND project_id=%s FOR SHARE",
                (body.claim_id, project_id),
            )
            linked_claim = cur.fetchone()
            if not linked_claim:
                raise HTTPException(status_code=422, detail="linked claim must belong to the project")
            if (body.review_purpose != "UNSPECIFIED" and linked_claim["review_purpose"] != "UNSPECIFIED"
                    and body.review_purpose != linked_claim["review_purpose"]):
                raise HTTPException(422, f"requirement {body.review_purpose} must match linked claim {linked_claim['review_purpose']}")
        try:
            cur.execute(
                """INSERT INTO requirements(id,project_id,display_id,level,parent_ref,statement,
                           verification_method,owner,claim_id,claim_label,source_chapter,sort_order,created_by,review_purpose)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    requirement_id,
                    project_id,
                    body.display_id,
                    body.level,
                    body.parent_ref,
                    body.statement,
                    body.verification_method,
                    body.owner,
                    body.claim_id,
                    body.claim_label,
                    body.source_chapter,
                    body.sort_order,
                    user_id,
                    body.review_purpose,
                ),
            )
            audit(
                cur,
                project_id,
                user_id,
                "CREATE",
                "requirement",
                str(requirement_id),
                body.model_dump(mode="json"),
            )
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="requirement display_id already exists")
        cur.execute(REQUIREMENT_SELECT + " WHERE r.id=%s", (requirement_id,))
        return scoped_record(cur.fetchone())


@app.get("/api/v1/requirements/{requirement_id}")
def get_requirement(requirement_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(REQUIREMENT_SELECT + " WHERE r.id=%s", (requirement_id,))
        requirement = cur.fetchone()
        if not requirement:
            raise HTTPException(status_code=404, detail="requirement not found")
        membership(cur, requirement["project_id"], user_id)
        return scoped_record(requirement)


@app.put("/api/v1/requirements/{requirement_id}/purpose", dependencies=[Depends(csrf)])
def update_requirement_purpose(requirement_id: UUID, body: RequirementPurposeUpdate, user_id: str = Depends(actor)):
    # Lock a linked Claim first, matching closure's lock order. No historical record is rewritten.
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM requirements WHERE id=%s", (requirement_id,))
        requirement = cur.fetchone()
        if not requirement:
            raise HTTPException(404, "requirement not found")
        membership(cur, requirement["project_id"], user_id, {"engineer", "reviewer", "approver"})
        claim = None
        if requirement["claim_id"]:
            cur.execute("SELECT * FROM claims WHERE id=%s FOR UPDATE", (requirement["claim_id"],))
            claim = cur.fetchone()
        cur.execute("SELECT * FROM requirements WHERE id=%s FOR UPDATE", (requirement_id,))
        requirement = cur.fetchone()
        if requirement["version"] != body.expected_version:
            raise HTTPException(409, "requirement version conflict")
        if (claim and claim["review_purpose"] != "UNSPECIFIED" and body.review_purpose != "UNSPECIFIED"
                and claim["review_purpose"] != body.review_purpose):
            raise HTTPException(422, f"requirement {body.review_purpose} must match linked claim {claim['review_purpose']}")
        if body.review_purpose == requirement["review_purpose"]:
            return scoped_record(requirement)
        cur.execute("UPDATE requirements SET review_purpose=%s,version=version+1,updated_at=now() WHERE id=%s RETURNING *",
                    (body.review_purpose, requirement_id))
        updated = cur.fetchone()
        if claim:
            cur.execute("UPDATE claims SET version=version+1,status='OPEN',updated_at=now() WHERE id=%s RETURNING *",
                        (claim["id"],))
            revised = cur.fetchone()
            cur.execute(
                """INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,review_purpose)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (revised["id"], revised["project_id"], revised["version"], revised["question"],
                 json.dumps(revised["scope"]), revised["status"], user_id, revised["review_purpose"]),
            )
            stale_current_jobs(cur, claim_id=claim["id"], actor_id=user_id, reason="REQUIREMENT_PURPOSE_CHANGED")
        audit(cur, requirement["project_id"], user_id, "DECLARE_REVIEW_PURPOSE", "requirement",
              str(requirement_id), {"before": requirement["review_purpose"], **body.model_dump()}, requirement["version"])
        return scoped_record(updated)


@app.get("/api/v1/projects/{project_id}/gates")
def list_review_gates(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        cur.execute(
            """SELECT * FROM review_gates WHERE project_id=%s AND framework=%s
               ORDER BY sort_order""",
            (project_id, project["framework"]),
        )
        gates = [project_gate_projection(cur, project, row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM phase_transition_decisions WHERE project_id=%s ORDER BY created_at", (project_id,))
        transitions = cur.fetchall()
        return {"project": project, "gates": gates, "transitions": transitions}


@app.get("/api/v1/gates/{gate_id}")
def get_review_gate(gate_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM review_gates WHERE id=%s", (gate_id,))
        gate = cur.fetchone()
        if not gate:
            raise HTTPException(status_code=404, detail="review gate not found")
        membership(cur, gate["project_id"], user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (gate["project_id"],))
        project = cur.fetchone()
        return project_gate_projection(cur, project, gate)


@app.post("/api/v1/gates/{gate_id}/decisions", status_code=201, dependencies=[Depends(csrf)])
def create_gate_decision(gate_id: UUID, body: GateDecisionCreate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM review_gates WHERE id=%s FOR UPDATE", (gate_id,))
        gate = cur.fetchone()
        if not gate:
            raise HTTPException(status_code=404, detail="review gate not found")
        roles = {"approver"} if gate["authority"] == "APPROVER" else {"reviewer", "approver"}
        membership(cur, gate["project_id"], user_id, roles)
        cur.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (gate["project_id"],))
        project = cur.fetchone()
        if gate["version"] != body.expected_gate_version or project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="gate or project version conflict")
        if gate["framework"] != project["framework"]:
            raise HTTPException(status_code=409, detail="gate profile is no longer current")
        projection = project_gate_projection(cur, project, gate)
        if projection["latest_decision"] and projection["latest_decision"]["disposition"] == "APPROVED":
            raise HTTPException(status_code=409, detail="review gate already approved for this project version")
        if body.disposition == "APPROVED" and not projection["ready_for_decision"]:
            raise HTTPException(status_code=409, detail="review gate criteria are unresolved")
        decision_id = uuid4()
        cur.execute(
            """INSERT INTO gate_decisions(id,project_id,gate_id,disposition,note,actor,
                       source_gate_version,source_project_version,baseline_display_id,product_configuration,test_run)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (decision_id, project["id"], gate_id, body.disposition, body.note, user_id,
             gate["version"], project["version"], project["baseline_display_id"],
             project["product_configuration"], project["test_run"]),
        )
        decision = cur.fetchone()
        audit(cur, project["id"], user_id, "GATE_DECISION", "review_gate", str(gate_id), body.model_dump(), gate["version"])
        return decision


@app.post("/api/v1/projects/{project_id}/transitions", status_code=201, dependencies=[Depends(csrf)])
def create_phase_transition(project_id: UUID, body: PhaseTransitionCreate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"approver"})
        cur.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        if project["version"] != body.expected_project_version:
            raise HTTPException(status_code=409, detail="project version conflict")
        next_phase = min(project["current_phase"] + 1, 6)
        if body.disposition == "GO":
            if project["current_phase"] >= 6:
                raise HTTPException(status_code=409, detail="project is already in the final phase")
            cur.execute(
                """SELECT rg.gate_key FROM gate_decisions gd JOIN review_gates rg ON rg.id=gd.gate_id
                   WHERE gd.project_id=%s AND rg.framework=%s AND rg.gate_key IN ('accept','orr')
                     AND gd.disposition='APPROVED' AND gd.source_project_version=%s""",
                (project_id, project["framework"], project["version"]),
            )
            approved = {row["gate_key"] for row in cur.fetchall()}
            if approved != {"accept", "orr"}:
                raise HTTPException(status_code=409, detail="acceptance and operations readiness approvals are required")
        transition_id = uuid4()
        cur.execute(
            """INSERT INTO phase_transition_decisions(id,project_id,framework,from_phase,to_phase,
                       disposition,note,actor,source_project_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (transition_id, project_id, project["framework"], project["current_phase"], next_phase,
             body.disposition, body.note, user_id, project["version"]),
        )
        transition = cur.fetchone()
        if body.disposition == "GO":
            cur.execute(
                """UPDATE projects SET current_phase=%s,version=version+1,updated_at=now()
                   WHERE id=%s RETURNING *""",
                (next_phase, project_id),
            )
            project = cur.fetchone()
            stale_current_jobs(cur, project_id=project_id, actor_id=user_id, reason="PROJECT_PHASE_CHANGED")
            cur.execute("UPDATE claims SET status='OPEN',updated_at=now() WHERE project_id=%s AND status<>'OPEN'", (project_id,))
        audit(cur, project_id, user_id, "PHASE_TRANSITION", "project", str(project_id), body.model_dump(), body.expected_project_version)
        return {"transition": transition, "project": project}


@app.post("/api/v1/projects/{project_id}/claims", status_code=201, dependencies=[Depends(csrf)])
def create_claim(project_id: UUID, body: ClaimCreate, user_id: str = Depends(actor)):
    claim_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        try:
            cur.execute(
                """INSERT INTO claims(id,project_id,display_id,question,review_target,scope,created_by,review_purpose)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING *""",
                (claim_id, project_id, body.display_id, body.question, body.review_target, json.dumps(body.scope), user_id, body.review_purpose),
            )
            row = cur.fetchone()
            cur.execute(
                """INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,review_purpose)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (row["id"], row["project_id"], row["version"], row["question"], json.dumps(row["scope"]),
                 row["status"], user_id, row["review_purpose"]),
            )
            audit(cur, project_id, user_id, "CREATE", "claim", str(claim_id), body.model_dump(mode="json"))
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="claim display_id already exists")
    return scoped_record(row)


@app.put("/api/v1/claims/{claim_id}", dependencies=[Depends(csrf)])
def update_claim(claim_id: UUID, body: ClaimUpdate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM claims WHERE id=%s FOR UPDATE", (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found")
        membership(cur, claim["project_id"], user_id, {"engineer", "reviewer", "approver"})
        if claim["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="claim version conflict")
        cur.execute(
            """UPDATE claims SET question=%s,scope=%s::jsonb,review_purpose=%s,status='OPEN',version=version+1,updated_at=now()
               WHERE id=%s RETURNING *""",
            (body.question, json.dumps(body.scope), body.review_purpose or claim["review_purpose"], claim_id),
        )
        updated = cur.fetchone()
        cur.execute(
            """INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,review_purpose)
               VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (updated["id"], updated["project_id"], updated["version"], updated["question"],
             json.dumps(updated["scope"]), updated["status"], user_id, updated["review_purpose"]),
        )
        stale_current_jobs(cur, claim_id=claim_id, actor_id=user_id, reason="CLAIM_REVISION_CHANGED")
        audit(cur, claim["project_id"], user_id, "UPDATE", "claim", str(claim_id), body.model_dump(), claim["version"])
        return scoped_record(updated)


@app.post("/api/v1/projects/{project_id}/artifacts", status_code=201, dependencies=[Depends(csrf)])
def upload_artifact(
    project_id: UUID,
    file: UploadFile = File(...),
    rights_status: str = Form("UNCONFIRMED"),
    edition: str | None = Form(None),
    adopted: bool = Form(False),
    applicability_status: str = Form("UNCONFIRMED"),
    usage_purpose: str = Form(OPERATIONAL_PURPOSE),
    user_id: str = Depends(actor),
):
    allowed_content = {"application/pdf", "text/plain", "text/markdown", "application/json", "text/csv"}
    if file.content_type not in allowed_content:
        raise HTTPException(status_code=415, detail="unsupported content type")
    if rights_status not in {"UNCONFIRMED", "PUBLIC", "GRANTED", "RESTRICTED"}:
        raise HTTPException(status_code=422, detail="invalid rights_status")
    if applicability_status not in {"UNCONFIRMED", "APPLICABLE", "NOT_APPLICABLE"}:
        raise HTTPException(status_code=422, detail="invalid applicability_status")
    if usage_purpose not in {"OPERATIONAL_EVIDENCE", "TRAINING", "EVALUATION_GOLD"}:
        raise HTTPException(status_code=422, detail="invalid usage_purpose")
    artifact_id = uuid4()
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
    try:
        object_key, size, sha256 = write_stream(project_id, artifact_id, file.file)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    try:
        with connection() as conn, conn.cursor() as cur:
            membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
            cur.execute(
                """INSERT INTO artifact_versions(id,project_id,kind,filename,content_type,byte_size,sha256,
                   object_key,rights_status,edition,adopted,applicability_status,usage_purpose,created_by)
                   VALUES (%s,%s,'SOURCE',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (artifact_id, project_id, file.filename or "upload", file.content_type, size, sha256, object_key,
                 rights_status, edition, adopted, applicability_status, usage_purpose, user_id),
            )
            row = cur.fetchone()
            audit(cur, project_id, user_id, "UPLOAD", "artifact", str(artifact_id), {"sha256": sha256, "size": size})
        return row
    except Exception:
        resolved_path(object_key).unlink(missing_ok=True)
        raise


@app.get("/api/v1/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM artifact_versions WHERE id=%s", (artifact_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="artifact not found")
        membership(cur, row["project_id"], user_id)
    return FileResponse(resolved_path(row["object_key"]), media_type=row["content_type"], filename=row["filename"])


def _parser_projection(cur, parser_run_id: UUID) -> dict:
    cur.execute("SELECT * FROM document_parser_runs WHERE id=%s", (parser_run_id,))
    parser_run = cur.fetchone()
    cur.execute(
        """SELECT id,artifact_id,ordinal,content_kind,page_start,page_end,section_path,locator,
                  chunk_text,char_count,text_sha256,metadata,version
           FROM document_chunks WHERE parser_run_id=%s ORDER BY ordinal""",
        (parser_run_id,),
    )
    return {"parser_run": parser_run, "chunks": cur.fetchall()}


@app.post("/api/v1/artifacts/{artifact_id}/parse", status_code=201, dependencies=[Depends(csrf)])
def parse_artifact(artifact_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM artifact_versions WHERE id=%s", (artifact_id,))
        artifact = cur.fetchone()
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found")
        membership(cur, artifact["project_id"], user_id, {"engineer", "reviewer", "approver"})
        if artifact["kind"] != "SOURCE":
            raise HTTPException(status_code=422, detail="only SOURCE artifacts can be parsed")
        cur.execute(
            """SELECT id FROM document_parser_runs
               WHERE artifact_id=%s AND parser_version=%s AND chunker_version=%s AND status='COMPLETED'""",
            (artifact_id, PARSER_VERSION, CHUNKER_VERSION),
        )
        existing = cur.fetchone()
        if existing:
            return _parser_projection(cur, existing["id"])
        parser_run_id = uuid4()
        cur.execute(
            """INSERT INTO document_parser_runs(id,project_id,artifact_id,parser_name,parser_version,
                      chunker_version,source_sha256,status,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'PROCESSING',%s)""",
            (
                parser_run_id,
                artifact["project_id"],
                artifact_id,
                PARSER_NAME,
                PARSER_VERSION,
                CHUNKER_VERSION,
                artifact["sha256"],
                user_id,
            ),
        )

    path = resolved_path(artifact["object_key"])
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha256 != artifact["sha256"]:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE document_parser_runs SET status='FAILED',error_code='ARTIFACT_HASH_MISMATCH',
                          error_detail='stored bytes do not match artifact metadata',finished_at=now()
                   WHERE id=%s""",
                (parser_run_id,),
            )
        raise HTTPException(status_code=409, detail="ARTIFACT_HASH_MISMATCH")
    try:
        parsed = parse_document(path, artifact["content_type"], artifact["usage_purpose"])
    except DocumentParseError as exc:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE document_parser_runs SET status='FAILED',error_code=%s,error_detail=%s,
                          finished_at=now() WHERE id=%s""",
                (exc.code, exc.detail[:1000], parser_run_id),
            )
            audit(
                cur,
                artifact["project_id"],
                user_id,
                "PARSE_FAILED",
                "artifact",
                str(artifact_id),
                {"parser_run_id": str(parser_run_id), "error_code": exc.code},
            )
        raise HTTPException(status_code=422, detail=f"{exc.code}:{exc.detail}") from exc

    with connection() as conn, conn.cursor() as cur:
        membership(cur, artifact["project_id"], user_id, {"engineer", "reviewer", "approver"})
        for chunk in parsed.chunks:
            source_span_id, chunk_id = uuid4(), uuid4()
            cur.execute(
                """INSERT INTO source_spans(id,project_id,artifact_id,locator,quote,sha256)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    source_span_id,
                    artifact["project_id"],
                    artifact_id,
                    chunk.locator,
                    chunk.text,
                    chunk.text_sha256,
                ),
            )
            metadata = {
                **chunk.metadata,
                "artifact_sha256": artifact["sha256"],
                "rights_status": artifact["rights_status"],
                "edition": artifact["edition"],
                "adopted": artifact["adopted"],
                "applicability_status": artifact["applicability_status"],
                "usage_purpose": artifact["usage_purpose"],
                "parser_version": PARSER_VERSION,
                "chunker_version": CHUNKER_VERSION,
            }
            cur.execute(
                """INSERT INTO document_chunks(id,project_id,artifact_id,parser_run_id,source_span_id,
                          ordinal,content_kind,page_start,page_end,section_path,locator,chunk_text,
                          char_count,text_sha256,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb)""",
                (
                    chunk_id,
                    artifact["project_id"],
                    artifact_id,
                    parser_run_id,
                    source_span_id,
                    chunk.ordinal,
                    chunk.content_kind,
                    chunk.page_start,
                    chunk.page_end,
                    json.dumps(chunk.section_path, ensure_ascii=False),
                    chunk.locator,
                    chunk.text,
                    len(chunk.text),
                    chunk.text_sha256,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
        receipt = {
            **parser_receipt(artifact, parsed),
            "parser_run_id": str(parser_run_id),
        }
        receipt_sha256 = digest(receipt)
        cur.execute(
            """UPDATE document_parser_runs SET status='COMPLETED',page_count=%s,chunk_count=%s,
                      issues=%s::jsonb,receipt=%s::jsonb,receipt_sha256=%s,finished_at=now()
               WHERE id=%s""",
            (
                parsed.page_count,
                len(parsed.chunks),
                json.dumps(parsed.issues, ensure_ascii=False),
                json.dumps(receipt, ensure_ascii=False),
                receipt_sha256,
                parser_run_id,
            ),
        )
        audit(
            cur,
            artifact["project_id"],
            user_id,
            "PARSE",
            "artifact",
            str(artifact_id),
            {
                "parser_run_id": str(parser_run_id),
                "parser_version": PARSER_VERSION,
                "chunker_version": CHUNKER_VERSION,
                "chunk_count": len(parsed.chunks),
                "receipt_sha256": receipt_sha256,
            },
        )
        return _parser_projection(cur, parser_run_id)


@app.get("/api/v1/artifacts/{artifact_id}/chunks")
def get_artifact_chunks(artifact_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM artifact_versions WHERE id=%s", (artifact_id,))
        artifact = cur.fetchone()
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found")
        membership(cur, artifact["project_id"], user_id)
        cur.execute(
            """SELECT * FROM document_parser_runs WHERE artifact_id=%s
               ORDER BY started_at DESC LIMIT 1""",
            (artifact_id,),
        )
        parser_run = cur.fetchone()
        if not parser_run:
            return {"artifact": artifact, "parser_run": None, "chunks": []}
        projection = _parser_projection(cur, parser_run["id"])
        projection["artifact"] = artifact
        return projection


def _retrieval_projection(cur, retrieval_run_id: UUID) -> dict:
    cur.execute("SELECT * FROM retrieval_runs WHERE id=%s", (retrieval_run_id,))
    run = cur.fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="retrieval run not found")
    cur.execute(
        """SELECT rr.candidate_rank,rr.score,rr.selected,rr.reason,
                  dc.id AS chunk_id,dc.artifact_id,dc.ordinal,dc.page_start,dc.page_end,
                  dc.section_path,dc.locator,dc.char_count,dc.text_sha256,
                  CASE WHEN rr.selected THEN dc.chunk_text ELSE NULL END AS chunk_text,
                  a.filename,a.sha256 AS artifact_sha256,dpr.receipt_sha256 AS parser_receipt_sha256
           FROM retrieval_results rr JOIN document_chunks dc ON dc.id=rr.chunk_id
           JOIN artifact_versions a ON a.id=dc.artifact_id
           JOIN document_parser_runs dpr ON dpr.id=dc.parser_run_id
           WHERE rr.retrieval_run_id=%s ORDER BY rr.candidate_rank""",
        (retrieval_run_id,),
    )
    return {"run": run, "results": cur.fetchall()}


@app.post("/api/v1/projects/{project_id}/retrievals", status_code=201, dependencies=[Depends(csrf)])
def create_retrieval(
    project_id: UUID,
    body: RetrievalCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    user_id: str = Depends(actor),
):
    if len(body.artifact_ids) != len(set(body.artifact_ids)):
        raise HTTPException(status_code=422, detail="duplicate artifact id")
    query = " ".join(body.query.split())
    artifact_ids = sorted(body.artifact_ids, key=str)
    request_value = {
        "project_id": str(project_id),
        "claim_id": str(body.claim_id),
        "query": query,
        "artifact_ids": [str(value) for value in artifact_ids],
        "top_k": body.top_k,
        "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "index_version": INDEX_VERSION,
        "filter_policy": FILTER_POLICY,
    }
    request_hash = digest(request_value)
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute(
            "SELECT * FROM retrieval_runs WHERE project_id=%s AND idempotency_key=%s",
            (project_id, idempotency_key),
        )
        existing = cur.fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise HTTPException(status_code=409, detail="idempotency key reused with different content")
            projection = _retrieval_projection(cur, existing["id"])
            projection["idempotent_replay"] = True
            return projection
        cur.execute("SELECT * FROM projects WHERE id=%s FOR SHARE", (project_id,))
        project = cur.fetchone()
        cur.execute("SELECT * FROM claims WHERE id=%s AND project_id=%s FOR SHARE", (body.claim_id, project_id))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found in project")
        cur.execute("SELECT numnode(websearch_to_tsquery('simple',%s)) AS terms", (query,))
        if cur.fetchone()["terms"] == 0:
            raise HTTPException(status_code=422, detail="query has no searchable terms")
        if artifact_ids:
            cur.execute(
                "SELECT count(*) AS value FROM artifact_versions WHERE project_id=%s AND id=ANY(%s)",
                (project_id, artifact_ids),
            )
            if cur.fetchone()["value"] != len(artifact_ids):
                raise HTTPException(status_code=422, detail="unprovided or cross-project artifact id")

        params: list[Any] = [query, query, project_id, PARSER_VERSION, CHUNKER_VERSION]
        artifact_clause = ""
        if artifact_ids:
            artifact_clause = " AND dc.artifact_id=ANY(%s)"
            params.append(artifact_ids)
        params.append(min(200, max(50, body.top_k * 10)))
        cur.execute(
            f"""WITH q AS (SELECT websearch_to_tsquery('simple',%s) AS value)
                SELECT dc.id,dc.artifact_id,dc.ordinal,dc.locator,dc.chunk_text,dc.text_sha256,
                       a.filename,a.sha256 AS artifact_sha256,a.rights_status,a.edition,a.adopted,
                       a.applicability_status,a.usage_purpose,dpr.receipt_sha256 AS parser_receipt_sha256,
                       (ts_rank_cd(dc.search_vector,q.value) +
                        CASE WHEN lower(a.filename)=lower(%s) THEN 2.0 ELSE 0.0 END)::double precision AS score
                FROM document_chunks dc JOIN artifact_versions a ON a.id=dc.artifact_id
                JOIN document_parser_runs dpr ON dpr.id=dc.parser_run_id CROSS JOIN q
                WHERE dc.project_id=%s AND a.usage_purpose='OPERATIONAL_EVIDENCE'
                  AND dpr.status='COMPLETED' AND dpr.parser_version=%s AND dpr.chunker_version=%s
                  AND (dc.search_vector @@ q.value OR lower(a.filename)=lower(%s)){artifact_clause}
                ORDER BY score DESC,a.sha256,dc.ordinal
                LIMIT %s""",
            [params[0], params[1], params[2], params[3], params[4], params[1], *params[5:]],
        )
        candidates = cur.fetchall()
        results = []
        selected_count = 0
        for candidate_rank, row in enumerate(candidates, start=1):
            allowed, reason = scope_decision(
                claim["scope"],
                {
                    "kind": "REFERENCE",
                    "rights_status": row["rights_status"],
                    "edition": row["edition"],
                    "adopted": row["adopted"],
                    "applicability_status": row["applicability_status"],
                    "quote": row["chunk_text"],
                },
            )
            selected = allowed and selected_count < body.top_k
            if selected:
                selected_count += 1
                decision = "SELECTED_FTS"
            elif allowed:
                decision = "NOT_SELECTED_TOP_K"
            else:
                decision = reason or "SCOPE_GATE_EXCLUDED"
            results.append(
                {
                    **row,
                    "candidate_rank": candidate_rank,
                    "score": max(0.0, float(row["score"])),
                    "selected": selected,
                    "reason": decision,
                }
            )

        retrieval_run_id = uuid4()
        receipt = retrieval_receipt(
            run_id=str(retrieval_run_id),
            project_id=str(project_id),
            claim=claim,
            query=query,
            artifact_ids=[str(value) for value in artifact_ids],
            top_k=body.top_k,
            results=results,
        )
        receipt_sha256 = digest(receipt)
        cur.execute(
            """INSERT INTO retrieval_runs(id,project_id,claim_id,claim_version,project_version,query,
                      artifact_filter,filter_policy,parser_version,index_version,top_k,status,request_hash,
                      idempotency_key,candidate_count,selected_count,receipt,receipt_sha256,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,'COMPLETED',%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                retrieval_run_id,
                project_id,
                claim["id"],
                claim["version"],
                project["version"],
                query,
                json.dumps([str(value) for value in artifact_ids]),
                FILTER_POLICY,
                PARSER_VERSION,
                INDEX_VERSION,
                body.top_k,
                request_hash,
                idempotency_key,
                len(results),
                selected_count,
                json.dumps(receipt, ensure_ascii=False),
                receipt_sha256,
                user_id,
            ),
        )
        for result in results:
            cur.execute(
                """INSERT INTO retrieval_results(retrieval_run_id,project_id,chunk_id,candidate_rank,
                          score,selected,reason) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    retrieval_run_id,
                    project_id,
                    result["id"],
                    result["candidate_rank"],
                    result["score"],
                    result["selected"],
                    result["reason"],
                ),
            )
        audit(
            cur,
            project_id,
            user_id,
            "RETRIEVE",
            "retrieval_run",
            str(retrieval_run_id),
            {
                "request_hash": request_hash,
                "receipt_sha256": receipt_sha256,
                "candidate_count": len(results),
                "selected_count": selected_count,
            },
        )
        projection = _retrieval_projection(cur, retrieval_run_id)
        projection["idempotent_replay"] = False
        return projection


@app.get("/api/v1/projects/{project_id}/retrievals")
def list_retrievals(project_id: UUID, claim_id: UUID | None = None, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        if claim_id:
            cur.execute(
                """SELECT * FROM retrieval_runs WHERE project_id=%s AND claim_id=%s
                   ORDER BY created_at DESC LIMIT 50""",
                (project_id, claim_id),
            )
        else:
            cur.execute(
                "SELECT * FROM retrieval_runs WHERE project_id=%s ORDER BY created_at DESC LIMIT 50",
                (project_id,),
            )
        return cur.fetchall()


@app.get("/api/v1/retrievals/{retrieval_run_id}")
def get_retrieval(retrieval_run_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        projection = _retrieval_projection(cur, retrieval_run_id)
        membership(cur, projection["run"]["project_id"], user_id)
        return projection


@app.post("/api/v1/projects/{project_id}/evidence", status_code=201, dependencies=[Depends(csrf)])
def create_evidence(project_id: UUID, body: EvidenceCreate, user_id: str = Depends(actor)):
    evidence_id, span_id = uuid4(), uuid4() if body.locator or body.quote else None
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        cur.execute("SELECT * FROM artifact_versions WHERE id=%s AND project_id=%s FOR SHARE", (body.artifact_id, project_id))
        artifact = cur.fetchone()
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found in project")
        verification = verify_citation(cur, artifact, body.citation.model_dump(mode="json") if body.citation else None,
                                       body.quote, body.locator)
        if span_id:
            quote_hash = hashlib.sha256((body.quote or "").encode()).hexdigest() if body.quote is not None else None
            cur.execute(
                """INSERT INTO source_spans(id,project_id,artifact_id,locator,quote,sha256)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (span_id, project_id, body.artifact_id, body.locator or "UNCONFIRMED", body.quote, quote_hash),
            )
        try:
            cur.execute(
                """INSERT INTO evidence(id,project_id,artifact_id,source_span_id,display_id,kind,basis,scope,provenance,created_by,source_verification)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb) RETURNING *""",
                (evidence_id, project_id, body.artifact_id, span_id, body.display_id, body.kind, body.basis,
                 json.dumps(body.scope), json.dumps(body.provenance), user_id, json.dumps(verification)),
            )
            row = cur.fetchone()
            audit(cur, project_id, user_id, "CREATE", "evidence", str(evidence_id),
                  {**body.model_dump(mode="json"), "source_verification": verification})
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="evidence display_id already exists")
        return row


@app.get("/api/v1/projects/{project_id}/evidence")
def list_evidence(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        refresh_source_verifications(cur, project_id, user_id)
        cur.execute(
            """SELECT e.*,a.filename,a.content_type,a.byte_size,a.sha256 AS artifact_sha256,
                      a.rights_status,a.edition,a.adopted,a.applicability_status,s.locator,s.quote
               FROM evidence e JOIN artifact_versions a ON a.id=e.artifact_id
               LEFT JOIN source_spans s ON s.id=e.source_span_id
               WHERE e.project_id=%s ORDER BY e.created_at""",
            (project_id,),
        )
        return [citation_record(row) for row in cur.fetchall()]


@app.get("/api/v1/evidence/{evidence_id}")
def get_evidence(evidence_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT e.*,a.filename,a.content_type,a.byte_size,a.sha256 AS artifact_sha256,
                      a.id AS download_artifact_id,a.rights_status,a.edition,a.adopted,
                      a.applicability_status,s.locator,s.quote
               FROM evidence e JOIN artifact_versions a ON a.id=e.artifact_id
               LEFT JOIN source_spans s ON s.id=e.source_span_id WHERE e.id=%s""",
            (evidence_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="evidence not found")
        membership(cur, row["project_id"], user_id)
        refresh_source_verifications(cur, row["project_id"], user_id)
        cur.execute("SELECT source_verification,version FROM evidence WHERE id=%s", (evidence_id,))
        row.update(cur.fetchone())
        return citation_record(row)


@app.post("/api/v1/projects/{project_id}/reviews", status_code=202, dependencies=[Depends(csrf)])
def create_review(
    project_id: UUID,
    body: ReviewCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    user_id: str = Depends(actor),
):
    if len(body.evidence_ids) != len(set(body.evidence_ids)):
        raise HTTPException(status_code=422, detail="duplicate evidence id")
    if body.mode == "LIVE_MODEL_RUN" and APP_MODE == "DEMO":
        raise HTTPException(status_code=409, detail="LIVE request is disabled in explicit DEMO mode")
    if body.mode != "LIVE_MODEL_RUN" and APP_MODE != "DEMO":
        raise HTTPException(status_code=409, detail="SIMULATED/REPLAY require explicit DEMO mode")
    request_value = {"project_id": str(project_id), **body.model_dump(mode="json")}
    request_hash = digest(request_value)
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id, {"engineer", "reviewer", "approver"})
        local_connection.lock(cur)
        if local_connection.pending():
            raise HTTPException(status_code=409, detail="CONNECTION_APPLY_IN_PROGRESS")
        refresh_source_verifications(cur, project_id, user_id)
        cur.execute("SELECT * FROM review_jobs WHERE project_id=%s AND idempotency_key=%s", (project_id, idempotency_key))
        existing = cur.fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise HTTPException(status_code=409, detail="idempotency key reused with different content")
            cur.execute("SELECT id,status,current_node FROM orchestration_runs WHERE job_id=%s", (existing["id"],))
            orchestration = cur.fetchone()
            cur.execute("SELECT review_purpose FROM context_snapshots WHERE id=%s", (existing["snapshot_id"],))
            existing_scope = assessment_scope(cur.fetchone()["review_purpose"])
            return {
                "job_id": existing["id"],
                "status": existing["status"],
                "idempotent_replay": True,
                "orchestration": orchestration,
                "assessment_scope": existing_scope,
            }
        cur.execute("SELECT * FROM projects WHERE id=%s FOR SHARE", (project_id,))
        project = cur.fetchone()
        cur.execute("SELECT * FROM claims WHERE id=%s AND project_id=%s FOR SHARE", (body.claim_id, project_id))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="claim not found in project")
        scope_contract = check_supported_purpose(claim)
        if body.mode == "LIVE_MODEL_RUN" and project["data_policy"] == "LOCAL_ONLY":
            raise HTTPException(status_code=409, detail="project data policy forbids external inference")

        retrieval_run = None
        retrieved = []
        if body.retrieval_run_id:
            cur.execute(
                "SELECT * FROM retrieval_runs WHERE id=%s AND project_id=%s",
                (body.retrieval_run_id, project_id),
            )
            retrieval_run = cur.fetchone()
            if not retrieval_run or retrieval_run["claim_id"] != claim["id"]:
                raise HTTPException(status_code=422, detail="retrieval run is not provided for this project and claim")
            if retrieval_run["status"] != "COMPLETED":
                raise HTTPException(status_code=409, detail="retrieval run is not complete")
            if (
                retrieval_run["claim_version"] != claim["version"]
                or retrieval_run["project_version"] != project["version"]
            ):
                raise HTTPException(status_code=409, detail="STALE_RETRIEVAL: claim or project version changed")
            cur.execute(
                """SELECT dc.*,a.filename,a.rights_status,a.edition,a.adopted,a.applicability_status,
                          a.sha256 AS artifact_sha256,rr.candidate_rank,rr.score,rr.reason
                   FROM retrieval_results rr JOIN document_chunks dc ON dc.id=rr.chunk_id
                   JOIN artifact_versions a ON a.id=dc.artifact_id
                   WHERE rr.retrieval_run_id=%s AND rr.selected=true
                   ORDER BY rr.candidate_rank""",
                (body.retrieval_run_id,),
            )
            retrieved = cur.fetchall()
            if len(retrieved) != retrieval_run["selected_count"]:
                raise HTTPException(status_code=409, detail="retrieval receipt/result count mismatch")

        selected = []
        if body.evidence_ids:
            cur.execute(
                """SELECT e.*,a.rights_status,a.edition,a.adopted,a.applicability_status,s.locator,s.quote
                   FROM evidence e JOIN artifact_versions a ON a.id=e.artifact_id
                   LEFT JOIN source_spans s ON s.id=e.source_span_id
                   WHERE e.project_id=%s AND e.id=ANY(%s) FOR SHARE OF e,a""",
                (project_id, body.evidence_ids),
            )
            selected = cur.fetchall()
            if len(selected) != len(body.evidence_ids):
                raise HTTPException(status_code=422, detail="unprovided or cross-project evidence id")
        included, excluded = [], []
        for item in selected:
            allowed, reason = scope_decision(claim["scope"], item)
            if allowed:
                included.append(item)
            else:
                excluded.append({"evidence_id": str(item["id"]), "reason": reason})

        retrieved_included = []
        for item in retrieved:
            retrieved_item = {
                "id": item["id"],
                "display_id": f"RAG-{item['filename']}-{item['ordinal'] + 1}",
                "kind": "REFERENCE",
                "basis": "RAG_RETRIEVED",
                "scope": {},
                "quote": item["chunk_text"],
                "locator": item["locator"],
                "rights_status": item["rights_status"],
                "edition": item["edition"],
                "adopted": item["adopted"],
                "applicability_status": item["applicability_status"],
                "artifact_id": item["artifact_id"],
                "artifact_sha256": item["artifact_sha256"],
                "retrieval_rank": item["candidate_rank"],
                "retrieval_score": item["score"],
            }
            allowed, reason = scope_decision(claim["scope"], retrieved_item)
            if allowed:
                included.append(retrieved_item)
                retrieved_included.append(retrieved_item)
            else:
                excluded.append(
                    {"document_chunk_id": str(item["id"]), "reason": reason or "SCOPE_GATE_EXCLUDED"}
                )
        if retrieval_run:
            excluded.extend(
                {
                    "document_chunk_id": result["chunk_id"],
                    "reason": result["reason"],
                }
                for result in retrieval_run["receipt"].get("results", [])
                if not result.get("selected")
            )

        source_characters = sum(len(item.get("quote") or "") for item in included)
        if source_characters > 9_000:
            raise HTTPException(
                status_code=422,
                detail="CONTEXT_BUDGET_EXCEEDED: reduce direct evidence or retrieval top_k; source text was not truncated",
            )

        if body.mode == "LIVE_MODEL_RUN":
            contract_id = LIVE_CONTRACT
            messages = render_live(claim, included)
        else:
            contract_id = DEMO_CONTRACT
            messages = render_demo(claim, included)
        snapshot_value = {
            "project_id": str(project_id),
            "claim_id": str(claim["id"]),
            "claim_version": claim["version"],
            "review_purpose": claim["review_purpose"],
            "project_version": project["version"],
            "contract_id": contract_id,
            "model_profile": MODEL_PROFILE if body.mode == "LIVE_MODEL_RUN" else "dorilab-bm1-demo-v1",
            "included_evidence_ids": [str(v["id"]) for v in included],
            "source_verifications": {str(v["id"]): {**(v.get("source_verification") or unresolved_legacy()),
                                                       "evidence_version": v["version"]} for v in included if v in selected},
            "excluded_evidence": excluded,
            "retrieval_run_id": str(retrieval_run["id"]) if retrieval_run else None,
            "retrieved_chunk_ids": [str(v["id"]) for v in retrieved_included],
            "retrieval_receipt": (
                {**retrieval_run["receipt"], "receipt_sha256": retrieval_run["receipt_sha256"]}
                if retrieval_run else None
            ),
            "context_budget": {
                "source_character_limit": 9000,
                "source_characters": source_characters,
                "remote_total_token_limit": 4096,
                "remote_response_token_reservation": 384,
                "token_preflight_owner": "INFERENCE_SERVICE",
                "source_text_truncated": False,
            },
            "messages": messages,
        }
        snapshot_id, job_id = uuid4(), uuid4()
        snapshot_sha256 = digest(snapshot_value)
        cur.execute(
            """INSERT INTO context_snapshots(id,project_id,claim_id,claim_version,project_version,contract_id,
               model_profile,included_evidence_ids,excluded_evidence,messages,snapshot_sha256,retrieval_run_id,
               retrieved_chunk_ids,retrieval_receipt,context_budget,review_purpose,source_verifications)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb)""",
            (snapshot_id, project_id, claim["id"], claim["version"], project["version"], contract_id,
             snapshot_value["model_profile"], json.dumps(snapshot_value["included_evidence_ids"]),
             json.dumps(excluded), json.dumps(messages, ensure_ascii=False), snapshot_sha256,
             retrieval_run["id"] if retrieval_run else None,
             json.dumps(snapshot_value["retrieved_chunk_ids"]),
             json.dumps(snapshot_value["retrieval_receipt"], ensure_ascii=False) if retrieval_run else None,
             json.dumps(snapshot_value["context_budget"]), claim["review_purpose"],
             json.dumps(snapshot_value["source_verifications"])),
        )
        cur.execute(
            """INSERT INTO review_jobs(id,project_id,claim_id,snapshot_id,idempotency_key,request_hash,mode,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (job_id, project_id, claim["id"], snapshot_id, idempotency_key, request_hash, body.mode, user_id),
        )
        orchestration = create_native_run(
            cur,
            project=project,
            claim=claim,
            job_id=job_id,
            snapshot_id=snapshot_id,
            snapshot_sha256=snapshot_sha256,
            mode=body.mode,
            actor_id=user_id,
            included_evidence_ids=snapshot_value["included_evidence_ids"],
            excluded_evidence=excluded,
            retrieval_run_id=retrieval_run["id"] if retrieval_run else None,
            retrieved_chunk_ids=snapshot_value["retrieved_chunk_ids"],
            retrieval_receipt_sha256=retrieval_run["receipt_sha256"] if retrieval_run else None,
        )
        audit(cur, project_id, user_id, "CREATE", "review_job", str(job_id), request_value)
        return {
            "job_id": job_id,
            "status": "QUEUED",
            "assessment_scope": scope_contract,
            "idempotent_replay": False,
            "excluded_evidence": excluded,
            "orchestration": {
                "id": orchestration["id"],
                "status": orchestration["status"],
                "current_node": orchestration["current_node"],
            },
        }


@app.get("/api/v1/projects/{project_id}/jobs")
def list_jobs(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        refresh_source_verifications(cur, project_id, user_id)
        cur.execute(
            """SELECT j.*,c.display_id AS claim_display_id,cr.question,cs.review_purpose,
                      v.status AS validation_status,
                      (SELECT hr.disposition FROM human_reviews hr WHERE hr.job_id=j.id
                       ORDER BY hr.created_at DESC LIMIT 1) AS latest_disposition,
                      (SELECT count(*) FROM evidence_requests er WHERE er.job_id=j.id) AS evidence_request_count,
                      (SELECT count(*) FROM report_exports re WHERE re.job_id=j.id) AS report_count,
                      o.id AS orchestration_run_id,o.status AS orchestration_status,
                      o.current_node AS orchestration_current_node,o.checkpoint_seq AS orchestration_checkpoint_count
               FROM review_jobs j JOIN claims c ON c.id=j.claim_id
               JOIN context_snapshots cs ON cs.id=j.snapshot_id
               LEFT JOIN claim_revisions cr ON cr.claim_id=cs.claim_id AND cr.version=cs.claim_version
               LEFT JOIN model_runs mr ON mr.job_id=j.id
               LEFT JOIN validations v ON v.model_run_id=mr.id
               LEFT JOIN orchestration_runs o ON o.job_id=j.id
               WHERE j.project_id=%s ORDER BY j.created_at DESC LIMIT 100""",
            (project_id,),
        )
        return [scoped_record(row) for row in cur.fetchall()]


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM review_jobs WHERE id=%s", (job_id,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        membership(cur, job["project_id"], user_id)
        refresh_source_verifications(cur, job["project_id"], user_id)
        cur.execute("SELECT * FROM review_jobs WHERE id=%s", (job_id,))
        job = cur.fetchone()
        cur.execute("SELECT * FROM context_snapshots WHERE id=%s", (job["snapshot_id"],))
        snapshot = cur.fetchone()
        cur.execute(
            """SELECT mr.*,v.status AS validation_status,v.errors,v.parsed_output
               FROM model_runs mr LEFT JOIN validations v ON v.model_run_id=mr.id WHERE mr.job_id=%s""",
            (job_id,),
        )
        model_run = cur.fetchone()
        cur.execute("SELECT * FROM human_reviews WHERE job_id=%s ORDER BY created_at", (job_id,))
        decisions = cur.fetchall()
        cur.execute(
            """SELECT er.*,e.display_id AS submitted_evidence_display_id
               FROM evidence_requests er LEFT JOIN evidence e ON e.id=er.submitted_evidence_id
               WHERE er.job_id=%s ORDER BY er.created_at""",
            (job_id,),
        )
        evidence_requests = cur.fetchall()
        cur.execute("SELECT * FROM report_exports WHERE job_id=%s ORDER BY created_at", (job_id,))
        reports = cur.fetchall()
        orchestration = orchestration_projection(cur, job_id)
        return {
            "job": job,
            "snapshot": scoped_record(snapshot),
            "assessment_scope": assessment_scope(snapshot["review_purpose"]),
            "model_run": model_run,
            "decisions": decisions,
            "evidence_requests": evidence_requests,
            "reports": reports,
            "orchestration": orchestration,
        }


@app.get("/api/v1/jobs/{job_id}/orchestration")
def get_job_orchestration(job_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT project_id FROM review_jobs WHERE id=%s", (job_id,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        membership(cur, job["project_id"], user_id)
        projection = orchestration_projection(cur, job_id)
        if not projection:
            raise HTTPException(status_code=404, detail="orchestration run not found")
        return projection


@app.get("/api/v1/projects/{project_id}/evidence-requests")
def list_evidence_requests(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute(
            """SELECT er.*,c.display_id AS claim_display_id,e.display_id AS submitted_evidence_display_id
               FROM evidence_requests er JOIN claims c ON c.id=er.claim_id
               LEFT JOIN evidence e ON e.id=er.submitted_evidence_id
               WHERE er.project_id=%s ORDER BY er.created_at DESC""",
            (project_id,),
        )
        return cur.fetchall()


@app.post("/api/v1/evidence-requests/{request_id}/submission", dependencies=[Depends(csrf)])
def submit_evidence_request(request_id: UUID, body: EvidenceSubmission, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM evidence_requests WHERE id=%s FOR UPDATE", (request_id,))
        request = cur.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="evidence request not found")
        membership(cur, request["project_id"], user_id, {"engineer", "reviewer", "approver"})
        if request["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="evidence request version conflict")
        if request["status"] not in {"OPEN", "RECEIVED"}:
            raise HTTPException(status_code=409, detail="decided evidence request cannot be resubmitted")
        cur.execute("SELECT id FROM evidence WHERE id=%s AND project_id=%s", (body.evidence_id, request["project_id"]))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="evidence not found in project")
        cur.execute(
            """UPDATE evidence_requests SET submitted_evidence_id=%s,status='RECEIVED',received_by=%s,
                      received_at=now(),decided_by=NULL,decided_at=NULL,decision_note=NULL,version=version+1
               WHERE id=%s RETURNING *""",
            (body.evidence_id, user_id, request_id),
        )
        row = cur.fetchone()
        cur.execute("SELECT * FROM work_items WHERE evidence_request_id=%s FOR UPDATE", (request_id,))
        work_item = cur.fetchone()
        if work_item:
            cur.execute(
                """UPDATE work_items SET status='WAITING_REVIEW',
                          input_refs=input_refs || %s::jsonb,version=version+1,updated_at=now()
                   WHERE id=%s RETURNING *""",
                (json.dumps([{"object_type": "EVIDENCE", "object_id": str(body.evidence_id)}]), work_item["id"]),
            )
            updated_work_item = cur.fetchone()
            link_dependency(
                cur,
                project_id=request["project_id"],
                upstream_type="EVIDENCE",
                upstream_id=body.evidence_id,
                upstream_version=1,
                downstream_type="WORK_ITEM",
                downstream_id=work_item["id"],
                downstream_version=updated_work_item["version"],
                relationship="RESPONDS_TO",
                actor_type="HUMAN",
                actor_id=user_id,
                source_job_id=request["job_id"],
            )
            append_event(
                cur,
                project_id=request["project_id"],
                event_type="WORK_ITEM_INPUT_RECEIVED",
                object_type="WORK_ITEM",
                object_id=str(work_item["id"]),
                actor_type="HUMAN",
                actor_id=user_id,
                payload={"evidence_id": str(body.evidence_id), "evidence_request_id": str(request_id)},
                source_version=work_item["version"],
                result_version=updated_work_item["version"],
                idempotency_key=f"evidence-request:{request_id}:received:{updated_work_item['version']}",
            )
        audit(
            cur,
            request["project_id"],
            user_id,
            "SUBMIT",
            "evidence_request",
            str(request_id),
            body.model_dump(mode="json"),
            request["version"],
        )
        return row


@app.post("/api/v1/evidence-requests/{request_id}/decision", dependencies=[Depends(csrf)])
def decide_evidence_request(request_id: UUID, body: EvidenceRequestDecision, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM evidence_requests WHERE id=%s FOR UPDATE", (request_id,))
        request = cur.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="evidence request not found")
        membership(cur, request["project_id"], user_id, {"reviewer", "approver"})
        if request["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="evidence request version conflict")
        if request["status"] != "RECEIVED" or not request["submitted_evidence_id"]:
            raise HTTPException(status_code=409, detail="received evidence is required before disposition")
        cur.execute(
            """UPDATE evidence_requests SET status=%s,decided_by=%s,decided_at=now(),decision_note=%s,
                      version=version+1 WHERE id=%s RETURNING *""",
            (body.disposition, user_id, body.note, request_id),
        )
        row = cur.fetchone()
        cur.execute("SELECT * FROM work_items WHERE evidence_request_id=%s FOR UPDATE", (request_id,))
        work_item = cur.fetchone()
        if work_item:
            work_status = "COMPLETED" if body.disposition == "ACCEPTED" else "REJECTED"
            cur.execute(
                "UPDATE work_items SET status=%s,version=version+1,updated_at=now() WHERE id=%s RETURNING *",
                (work_status, work_item["id"]),
            )
            updated_work_item = cur.fetchone()
            append_event(
                cur,
                project_id=request["project_id"],
                event_type="WORK_ITEM_COMPLETED" if work_status == "COMPLETED" else "WORK_ITEM_REJECTED",
                object_type="WORK_ITEM",
                object_id=str(work_item["id"]),
                actor_type="HUMAN",
                actor_id=user_id,
                payload={"evidence_request_id": str(request_id), "disposition": body.disposition, "note": body.note},
                source_version=work_item["version"],
                result_version=updated_work_item["version"],
                idempotency_key=f"evidence-request:{request_id}:decision:{updated_work_item['version']}",
            )
        if body.disposition == "ACCEPTED":
            stale_current_jobs(
                cur,
                job_id=request["job_id"],
                actor_id=user_id,
                reason="EVIDENCE_REQUEST_ACCEPTED",
            )
        audit(
            cur,
            request["project_id"],
            user_id,
            "DECIDE",
            "evidence_request",
            str(request_id),
            body.model_dump(),
            request["version"],
        )
        return row


@app.post("/api/v1/reviews/{job_id}/decisions", status_code=201, dependencies=[Depends(csrf)])
def create_decision(job_id: UUID, body: DecisionCreate, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT j.*,s.claim_version,s.project_version,s.review_purpose,c.version AS current_claim_version,
                      p.version AS current_project_version
               FROM review_jobs j JOIN context_snapshots s ON s.id=j.snapshot_id
               JOIN claims c ON c.id=j.claim_id JOIN projects p ON p.id=j.project_id
               WHERE j.id=%s""",
            (job_id,),
        )
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        membership(cur, job["project_id"], user_id, {"reviewer", "approver"})
        refresh_source_verifications(cur, job["project_id"], user_id)
        # Persist integrity invalidations even if the attempted human decision is rejected below.
        conn.commit()
        cur.execute(
            """SELECT j.*,s.claim_version,s.project_version,s.review_purpose,c.version AS current_claim_version,
                      p.version AS current_project_version
               FROM review_jobs j JOIN context_snapshots s ON s.id=j.snapshot_id
               JOIN claims c ON c.id=j.claim_id JOIN projects p ON p.id=j.project_id
               WHERE j.id=%s FOR UPDATE OF j""", (job_id,))
        job = cur.fetchone()
        if job["version"] != body.expected_job_version:
            raise HTTPException(status_code=409, detail="job version conflict")
        if job["freshness"] != "CURRENT" or job["claim_version"] != job["current_claim_version"] or job["project_version"] != job["current_project_version"]:
            stale_current_jobs(cur, job_id=job_id, actor_id=user_id, reason="DECISION_INPUT_NOT_CURRENT")
            raise HTTPException(status_code=409, detail="review is stale")
        if job["status"] != "AWAITING_REVIEW":
            raise HTTPException(status_code=409, detail="job is not awaiting human review")
        if body.disposition == "ACCEPTED":
            check_supported_purpose(job)
        cur.execute(
            """SELECT mr.id,v.status FROM model_runs mr JOIN validations v ON v.model_run_id=mr.id
               WHERE mr.job_id=%s""",
            (job_id,),
        )
        run = cur.fetchone()
        if not run or run["status"] != "VALID":
            raise HTTPException(status_code=409, detail="validated model output required")
        review_id = uuid4()
        cur.execute(
            """INSERT INTO human_reviews(id,project_id,job_id,model_run_id,disposition,edited_draft,note,actor,source_job_version)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING *""",
            (review_id, job["project_id"], job_id, run["id"], body.disposition,
             json.dumps(body.edited_draft) if body.edited_draft is not None else None,
             body.note, user_id, job["version"]),
        )
        row = cur.fetchone()
        cur.execute("UPDATE review_jobs SET status='COMPLETED',version=version+1,updated_at=now() WHERE id=%s", (job_id,))
        resume_after_human(cur, job_id=job_id, review=row, actor_id=user_id)
        contribution_status = {
            "ACCEPTED": "ACCEPTED",
            "REVISION_REQUESTED": "REVISION_REQUESTED",
            "REJECTED": "REJECTED",
        }[body.disposition]
        cur.execute(
            """UPDATE agent_contributions SET status=%s,reviewed_by=%s,review_note=%s,
                      decided_at=now(),version=version+1,updated_at=now()
               WHERE source_job_id=%s AND status='PROPOSED' RETURNING id,version""",
            (contribution_status, user_id, body.note, job_id),
        )
        for contribution in cur.fetchall():
            append_event(
                cur,
                project_id=job["project_id"],
                event_type="CONTRIBUTION_DECIDED",
                object_type="CONTRIBUTION",
                object_id=str(contribution["id"]),
                actor_type="HUMAN",
                actor_id=user_id,
                payload={"source": "HUMAN_REVIEW", "disposition": contribution_status, "job_id": str(job_id)},
                source_version=contribution["version"] - 1,
                result_version=contribution["version"],
                idempotency_key=f"review:{job_id}:contribution:{contribution['id']}:decision:{contribution['version']}",
            )
        audit(cur, job["project_id"], user_id, "DECIDE", "review_job", str(job_id), body.model_dump(), job["version"])
        return row


@app.post("/api/v1/jobs/{job_id}/reports", status_code=201, dependencies=[Depends(csrf)])
def create_review_report(job_id: UUID, user_id: str = Depends(actor)):
    object_key = None
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT j.*,s.contract_id,s.model_profile,s.snapshot_sha256,s.included_evidence_ids,
                          s.retrieval_run_id,s.retrieved_chunk_ids,s.retrieval_receipt,s.context_budget,s.review_purpose,s.source_verifications,
                          s.claim_version AS source_claim_version,s.project_version AS source_project_version,
                          c.display_id AS claim_display_id,cr.question,cr.scope AS claim_scope,c.review_target
                   FROM review_jobs j JOIN context_snapshots s ON s.id=j.snapshot_id
                   JOIN claims c ON c.id=j.claim_id
                   LEFT JOIN claim_revisions cr ON cr.claim_id=s.claim_id AND cr.version=s.claim_version
                   WHERE j.id=%s""",
                (job_id,),
            )
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="job not found")
            membership(cur, job["project_id"], user_id, {"engineer", "reviewer", "approver"})
            refresh_source_verifications(cur, job["project_id"], user_id)
            cur.execute("SELECT freshness,version FROM review_jobs WHERE id=%s", (job_id,))
            job.update(cur.fetchone())
            if job["status"] != "COMPLETED":
                raise HTTPException(status_code=409, detail="completed review is required for report export")
            cur.execute("SELECT * FROM projects WHERE id=%s", (job["project_id"],))
            project = cur.fetchone()
            cur.execute(
                """SELECT mr.*,v.status AS validation_status,v.errors,v.parsed_output
                   FROM model_runs mr JOIN validations v ON v.model_run_id=mr.id WHERE mr.job_id=%s""",
                (job_id,),
            )
            model_run = cur.fetchone()
            if not model_run:
                raise HTTPException(status_code=409, detail="model run is required for report export")
            cur.execute("SELECT * FROM human_reviews WHERE job_id=%s ORDER BY created_at", (job_id,))
            decisions = cur.fetchall()
            cur.execute("SELECT * FROM evidence_requests WHERE job_id=%s ORDER BY created_at", (job_id,))
            evidence_requests = cur.fetchall()
            included_ids = job["included_evidence_ids"]
            evidence = []
            if included_ids:
                cur.execute(
                    """SELECT e.*,a.sha256 AS artifact_sha256,s.locator
                       FROM evidence e JOIN artifact_versions a ON a.id=e.artifact_id
                       LEFT JOIN source_spans s ON s.id=e.source_span_id
                       WHERE e.project_id=%s AND e.id=ANY(%s::uuid[]) ORDER BY e.created_at""",
                    (job["project_id"], included_ids),
                )
                evidence = cur.fetchall()
            retrieved_chunks = []
            if job["retrieved_chunk_ids"]:
                cur.execute(
                    """SELECT dc.id,dc.locator,dc.text_sha256,a.sha256 AS artifact_sha256
                       FROM document_chunks dc JOIN artifact_versions a ON a.id=dc.artifact_id
                       WHERE dc.project_id=%s AND dc.id=ANY(%s::uuid[]) ORDER BY dc.ordinal""",
                    (job["project_id"], job["retrieved_chunk_ids"]),
                )
                retrieved_chunks = cur.fetchall()
            orchestration = orchestration_projection(cur, job_id)
            report_bytes = render_review_markdown(
                project=project,
                claim={
                    "display_id": job["claim_display_id"],
                    "question": job["question"] or "Snapshot 당시 질문 revision 미보존 (현재 질문으로 대체하지 않음)",
                    "scope": job["claim_scope"],
                    "review_target": job["review_target"],
                },
                job=job,
                snapshot={
                    "review_purpose": job["review_purpose"],
                    "claim_version": job["source_claim_version"],
                    "project_version": job["source_project_version"],
                    "snapshot_sha256": job["snapshot_sha256"],
                    "contract_id": job["contract_id"],
                    "model_profile": job["model_profile"],
                    "retrieval_run_id": job["retrieval_run_id"],
                    "retrieval_receipt": job["retrieval_receipt"],
                    "context_budget": job["context_budget"],
                    "source_verifications": job["source_verifications"],
                },
                model_run=model_run,
                decisions=decisions,
                evidence=evidence,
                retrieved_chunks=retrieved_chunks,
                evidence_requests=evidence_requests,
                orchestration=orchestration,
            )
            report_sha256 = hashlib.sha256(report_bytes).hexdigest()
            cur.execute("SELECT * FROM report_exports WHERE job_id=%s AND sha256=%s", (job_id, report_sha256))
            existing = cur.fetchone()
            if existing:
                return existing
            report_id = uuid4()
            object_key, size, stored_sha256 = write_export(job["project_id"], report_id, report_bytes)
            cur.execute(
                """INSERT INTO report_exports(id,project_id,job_id,filename,content_type,byte_size,sha256,object_key,created_by)
                   VALUES (%s,%s,%s,%s,'text/markdown; charset=utf-8',%s,%s,%s,%s) RETURNING *""",
                (
                    report_id,
                    job["project_id"],
                    job_id,
                    f"dorilab-bm1-{job_id}.md",
                    size,
                    stored_sha256,
                    object_key,
                    user_id,
                ),
            )
            row = cur.fetchone()
            audit(cur, job["project_id"], user_id, "EXPORT", "review_report", str(report_id), {"sha256": stored_sha256})
            return row
    except Exception:
        if object_key:
            resolved_export_path(object_key).unlink(missing_ok=True)
        raise


@app.get("/api/v1/reports/{report_id}/download")
def download_review_report(report_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM report_exports WHERE id=%s", (report_id,))
        report = cur.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="report not found")
        membership(cur, report["project_id"], user_id)
    return FileResponse(
        resolved_export_path(report["object_key"]),
        media_type=report["content_type"],
        filename=report["filename"],
    )


@app.get("/api/v1/projects/{project_id}/audit")
def list_audit(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM audit_events WHERE project_id=%s ORDER BY id DESC LIMIT 200", (project_id,))
        return cur.fetchall()


@app.get("/api/v1/projects/{project_id}/audit-view")
def get_project_audit_view(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        return project_audit_view(cur, project)


@app.get("/api/v1/projects/{project_id}/audit-export")
def download_project_audit_bundle(project_id: UUID, user_id: str = Depends(actor)):
    with connection() as conn, conn.cursor() as cur:
        membership(cur, project_id, user_id)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        bundle = project_audit_bundle(cur, project)
    content = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n").encode("utf-8")
    content_sha256 = hashlib.sha256(content).hexdigest()
    filename = f"dorilab-{project['display_id']}-audit-v{project['version']}.json"
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-SHA256": content_sha256,
        },
    )
