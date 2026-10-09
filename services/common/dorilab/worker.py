from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from .blackboard import create_contribution, create_work_item
from . import local_connection
from .config import APP_MODE, INFERENCE_URL, MODEL_PROFILE, inference_token
from .contracts import LIVE_CONTRACT, canonical
from .db import connection
from .orchestration import begin_source_review, complete_worker_path, fail_source_review, mark_stale, recover_source_review
from .storage import write_bytes
from .validation import validate_output


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
PROFILE_PATH = Path("/app/packages/contracts/model_profiles/rc3.json")


def recover_orphaned_jobs(stale_seconds: int = 30) -> dict[str, int]:
    recovered_demo = 0
    unknown_live = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id,mode FROM review_jobs
               WHERE status IN ('DISPATCHING','RUNNING','OUTPUT_RECEIVED','VALIDATING')
                 AND leased_at < now() - make_interval(secs => %s)
                 AND NOT EXISTS (SELECT 1 FROM model_runs mr WHERE mr.job_id=review_jobs.id)
               FOR UPDATE SKIP LOCKED""",
            (stale_seconds,),
        )
        for job in cur.fetchall():
            if job["mode"] == "LIVE_MODEL_RUN":
                cur.execute(
                    """UPDATE review_jobs SET status='UNKNOWN_OUTCOME',error_code='UNKNOWN_OUTCOME',
                              error_detail='worker lease expired after possible LIVE dispatch',version=version+1,
                              leased_by=NULL,leased_at=NULL,updated_at=now() WHERE id=%s""",
                    (job["id"],),
                )
                cur.execute(
                    """UPDATE review_attempts SET status='UNKNOWN_OUTCOME',finished_at=now()
                       WHERE job_id=%s AND finished_at IS NULL""",
                    (job["id"],),
                )
                recover_source_review(cur, job_id=job["id"], live=True)
                unknown_live += 1
            else:
                cur.execute(
                    """UPDATE review_jobs SET status='QUEUED',error_code='WORKER_RECOVERED',
                              error_detail='expired DEMO worker lease was safely requeued',version=version+1,
                              leased_by=NULL,leased_at=NULL,updated_at=now() WHERE id=%s""",
                    (job["id"],),
                )
                cur.execute(
                    """UPDATE review_attempts SET status='RECOVERED',finished_at=now()
                       WHERE job_id=%s AND finished_at IS NULL""",
                    (job["id"],),
                )
                recover_source_review(cur, job_id=job["id"], live=False)
                recovered_demo += 1
    return {"recovered_demo": recovered_demo, "unknown_live": unknown_live}


def set_remote_state(state: str, detail: str | None = None, receipt: dict | None = None) -> None:
    value = {
        "state": state,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if receipt:
        value["receipt"] = {
            k: receipt.get(k)
            for k in ("service", "model_receipt_id", "boot_id", "ready", "phase", "busy")
        }
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO system_state(key,value,updated_at) VALUES ('remote_status',%s::jsonb,now())
               ON CONFLICT (key) DO UPDATE SET value=excluded.value,updated_at=now()""",
            (json.dumps(value),),
        )


def claim_job() -> dict | None:
    with connection() as conn, conn.cursor() as cur:
        local_connection.lock(cur)
        if local_connection.pending():
            return None
        cur.execute(
            """SELECT j.*,s.contract_id,s.model_profile,s.messages,s.included_evidence_ids,
                      s.snapshot_sha256,s.claim_version,s.project_version,c.question,
                      c.display_id AS claim_display_id
               FROM review_jobs j JOIN context_snapshots s ON s.id=j.snapshot_id
               JOIN claims c ON c.id=j.claim_id
               WHERE j.status='QUEUED'
                 AND (j.error_code IS NULL OR j.updated_at < now() - interval '2 seconds')
               ORDER BY j.created_at
               FOR UPDATE OF j SKIP LOCKED LIMIT 1"""
        )
        job = cur.fetchone()
        if not job:
            return None
        attempt_id = uuid4()
        cur.execute(
            """UPDATE review_jobs SET status='DISPATCHING',leased_by=%s,leased_at=now(),
                      version=version+1,updated_at=now() WHERE id=%s""",
            (WORKER_ID, job["id"]),
        )
        cur.execute(
            """INSERT INTO review_attempts(id,job_id,attempt_no,status)
               VALUES (%s,%s,(SELECT count(*)+1 FROM review_attempts WHERE job_id=%s),'DISPATCHING')""",
            (attempt_id, job["id"], job["id"]),
        )
        job["attempt_id"] = attempt_id
        orchestration_attempt = begin_source_review(cur, job_id=job["id"], worker_id=WORKER_ID)
        if orchestration_attempt:
            job["orchestration_attempt_id"] = orchestration_attempt["id"]
            job["orchestration_attempt_no"] = orchestration_attempt["attempt_no"]
        return job


def simulated_output(job: dict) -> tuple[str, dict]:
    evidence_ids = [str(v) for v in job["included_evidence_ids"]]
    question = job["question"].lower()
    if "반박" in question or "충돌" in question or "contradict" in question:
        action = {
            "action": "CONTRADICT",
            "reason_code": "EVIDENCE_CONFLICT",
            "reason": "DEMO fixture에서 상충하는 진술이 지정되었습니다. 공학 판단이 아닙니다.",
            "evidence_refs": evidence_ids[:2],
            "requested_items": [],
        }
    elif not evidence_ids or "자료 요청" in question or "missing" in question:
        action = {
            "action": "REQUEST_EVIDENCE",
            "reason_code": "EVIDENCE_MISSING",
            "reason": "현재 DEMO snapshot에 범위가 확인된 근거가 없습니다.",
            "evidence_refs": [],
            "requested_items": ["현재 형상과 run에 대응하는 검토 근거"],
        }
    else:
        action = {
            "action": "NO_ACTION_REQUIRED",
            "reason_code": "EVIDENCE_SUFFICIENT",
            "reason": "DEMO contract의 구조 검증용 결과이며 공식 승인이나 의미 정확도 판정이 아닙니다.",
            "evidence_refs": evidence_ids,
            "requested_items": [],
        }
    raw = json.dumps({"actions": [action]}, ensure_ascii=False, separators=(",", ":"))
    receipt = {
        "profile_id": "dorilab-bm1-demo-v1",
        "contract_id": job["contract_id"],
        "basis": "SYNTHETIC",
        "execution_mode": job["mode"],
        "request_id": f"demo-{job['id']}",
        "attempt_id": str(job["attempt_id"]),
        "boot_id": "local-demo-worker",
        "finish_reason": "stop",
        "token_usage": {"prompt_tokens": None, "generated_tokens": None, "measurement": "NOT_MEASURED"},
    }
    return raw, receipt


def _verify_receipt(receipt: dict) -> list[str]:
    expected = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    errors = []
    if receipt.get("model_receipt_id") != expected.get("model_receipt_id"):
        errors.append("model_receipt_id_MISMATCH")
    if receipt.get("ready") is not True:
        errors.append("ready_MISMATCH")
    contracts = receipt.get("contracts")
    if not isinstance(contracts, list):
        errors.append("contracts_UNRESOLVED")
    else:
        contract = next((item for item in contracts if item.get("id") == expected.get("contract_id")), None)
        if contract is None:
            errors.append("contract_id_MISMATCH")
        else:
            if contract.get("route") != expected.get("contract_route"):
                errors.append("contract_route_MISMATCH")
            if contract.get("system_sha256") != expected.get("contract_id"):
                errors.append("system_sha256_MISMATCH")
    limits = receipt.get("limits") or {}
    generation = expected.get("generation") or {}
    if limits.get("max_total_tokens") != generation.get("max_total_tokens"):
        errors.append("max_total_tokens_MISMATCH")
    if limits.get("max_new_tokens") != generation.get("max_new_tokens"):
        errors.append("max_new_tokens_MISMATCH")
    return errors


def _remote_token_usage(result: dict) -> dict:
    """Normalize the authenticated inference receipt without dropping its response reservation."""
    return {
        "input_tokens": result.get("input_tokens", result.get("input_token_count")),
        "generated_tokens": result.get("generated_tokens", result.get("generated_token_count")),
        "reserved_new_tokens": result.get(
            "reserved_output_tokens",
            result.get("max_new_tokens", result.get("response_reservation")),
        ),
    }


def refresh_remote_state() -> dict:
    """Probe the forwarded API independently of generation dispatch."""
    headers = {"Authorization": f"Bearer {inference_token()}"}
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0), follow_redirects=False, trust_env=False) as client:
            ready = client.get(f"{INFERENCE_URL}/readyz", headers=headers)
            if ready.status_code == 503:
                body = ready.json()
                remote_state = body.get("state", "WARMING_UP")
                if remote_state not in {"SERVICE_NOT_DEPLOYED", "WARMING_UP", "SERVICE_BUSY", "MODEL_RELEASE_MISMATCH"}:
                    remote_state = "WARMING_UP"
                set_remote_state(remote_state, body.get("detail"))
                return {"state": remote_state, "detail": body.get("detail")}
            ready.raise_for_status()
            version = client.get(f"{INFERENCE_URL}/version", headers=headers)
            version.raise_for_status()
            receipt = version.json()
            mismatches = _verify_receipt(receipt)
            remote_state = "MODEL_RELEASE_MISMATCH" if mismatches else "READY"
            set_remote_state(remote_state, ",".join(mismatches) if mismatches else None, receipt)
            return {"state": remote_state, "mismatches": mismatches, "receipt": receipt}
    except httpx.RequestError as exc:
        set_remote_state("SERVICE_NOT_DEPLOYED", str(exc))
        return {"state": "SERVICE_NOT_DEPLOYED", "detail": str(exc)}
    except httpx.HTTPStatusError as exc:
        remote_state = "INFERENCE_AUTH_FAILED" if exc.response.status_code in {401, 403} else "SERVICE_NOT_DEPLOYED"
        set_remote_state(remote_state, f"HTTP {exc.response.status_code}")
        return {"state": remote_state, "http_status": exc.response.status_code}
    except (ValueError, json.JSONDecodeError) as exc:
        set_remote_state("MODEL_RELEASE_MISMATCH", str(exc))
        return {"state": "MODEL_RELEASE_MISMATCH", "detail": str(exc)}


def live_output(job: dict) -> tuple[str, dict]:
    messages = job.get("messages") or []
    if job.get("contract_id") != LIVE_CONTRACT or len(messages) != 1 or messages[0].get("role") != "user":
        raise RuntimeError("MODEL_RELEASE_MISMATCH: registered RC3 contract/user renderer is not selected")
    user_content = messages[0].get("content")
    if not isinstance(user_content, str):
        raise RuntimeError("MODEL_RELEASE_MISMATCH: rendered user packet is missing")
    try:
        user_packet = json.loads(user_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("MODEL_RELEASE_MISMATCH: rendered user packet is invalid JSON") from exc
    if canonical(user_packet).decode("utf-8") != user_content:
        raise RuntimeError("MODEL_RELEASE_MISMATCH: rendered user packet is not canonical JSON")
    token = inference_token()
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(30.0, connect=5.0)
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        try:
            version = client.get(f"{INFERENCE_URL}/version", headers=headers)
        except httpx.RequestError as exc:
            set_remote_state("SERVICE_NOT_DEPLOYED", str(exc))
            raise RuntimeError("SERVICE_NOT_DEPLOYED") from exc
        if version.status_code == 503:
            set_remote_state("WARMING_UP", version.text[:300])
            raise RuntimeError("WARMING_UP")
        if version.status_code in {401, 403}:
            set_remote_state("INFERENCE_AUTH_FAILED", f"HTTP {version.status_code}")
            raise RuntimeError("INFERENCE_AUTH_FAILED")
        version.raise_for_status()
        receipt = version.json()
        mismatches = _verify_receipt(receipt)
        if mismatches:
            set_remote_state("MODEL_RELEASE_MISMATCH", ",".join(mismatches), receipt)
            raise RuntimeError("MODEL_RELEASE_MISMATCH:" + ",".join(mismatches))
        set_remote_state("READY", receipt=receipt)
        payload = {
            "request_id": str(job["id"]),
            "contract_id": job["contract_id"],
            "user": user_content,
            "max_new_tokens": 384,
        }
        try:
            response = client.post(f"{INFERENCE_URL}/v1/generations", headers=headers, json=payload)
        except httpx.RequestError as exc:
            set_remote_state("SERVICE_NOT_DEPLOYED", str(exc))
            raise RuntimeError("UNKNOWN_OUTCOME:generation submit transport failed") from exc
        if response.status_code == 429:
            set_remote_state("SERVICE_BUSY", response.text[:300])
            raise RuntimeError("SERVICE_BUSY")
        if response.status_code == 503:
            set_remote_state("WARMING_UP", response.text[:300])
            raise RuntimeError("WARMING_UP")
        if response.status_code in {401, 403}:
            set_remote_state("INFERENCE_AUTH_FAILED", f"HTTP {response.status_code}")
            raise RuntimeError("INFERENCE_AUTH_FAILED")
        response.raise_for_status()
        accepted = response.json()
        request_id, boot_id = accepted["id"], accepted["boot_id"]
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE review_attempts SET request_id=%s,boot_id=%s,status='RUNNING'
                   WHERE id=%s""",
                (request_id, boot_id, job["attempt_id"]),
            )
            cur.execute("UPDATE review_jobs SET status='RUNNING',updated_at=now() WHERE id=%s", (job["id"],))
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                status_response = client.get(f"{INFERENCE_URL}/v1/generations/{request_id}", headers=headers)
            except httpx.RequestError as exc:
                set_remote_state("SERVICE_NOT_DEPLOYED", str(exc))
                raise RuntimeError("UNKNOWN_OUTCOME:generation poll transport failed") from exc
            if status_response.status_code == 404:
                raise RuntimeError("UNKNOWN_OUTCOME:generation state disappeared")
            if status_response.status_code in {429, 503}:
                time.sleep(1)
                continue
            status_response.raise_for_status()
            result = status_response.json()
            if result.get("boot_id") != boot_id:
                raise RuntimeError("UNKNOWN_OUTCOME:boot_id changed")
            status = str(result.get("status", "")).lower()
            if status == "completed":
                if not isinstance(result.get("raw_text"), str) or not isinstance(result.get("text"), str):
                    raise RuntimeError("REMOTE_GENERATION_FAILED:completed response lacks preserved output text")
                result["request_id"] = request_id
                result["token_usage"] = _remote_token_usage(result)
                return result["raw_text"], result
            if status == "failed":
                raise RuntimeError("REMOTE_GENERATION_FAILED:" + str(result.get("error", "unknown")))
            time.sleep(1)
        raise RuntimeError("UNKNOWN_OUTCOME:poll deadline exceeded")


def store_result(job: dict, raw: str, receipt: dict) -> None:
    artifact_id, run_id, validation_id = uuid4(), uuid4(), uuid4()
    object_key, size, raw_hash = write_bytes(job["project_id"], artifact_id, raw.encode("utf-8"))
    allowed = {str(v) for v in job["included_evidence_ids"]}
    validation_text = receipt.get("text", raw)
    request_catalog = {}
    if job["contract_id"] == LIVE_CONTRACT and job.get("messages"):
        packet = json.loads(job["messages"][0]["content"])
        request_catalog = {
            item["request_id"]: item["description"]
            for item in packet.get("request_catalog", [])
            if isinstance(item, dict) and isinstance(item.get("request_id"), str)
        }
    parsed, errors = validate_output(
        validation_text,
        allowed,
        contract_id=job["contract_id"],
        expected_claim_id=job.get("claim_display_id"),
        allowed_request_ids=set(request_catalog),
    )
    validation_status = "REJECTED" if errors else "VALID"
    job_status = "OUTPUT_REJECTED" if errors else "AWAITING_REVIEW"
    token_usage = receipt.get("token_usage", {})
    contribution_count = 0
    work_item_count = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO artifact_versions(id,project_id,kind,filename,content_type,byte_size,sha256,
               object_key,rights_status,applicability_status,created_by)
               VALUES (%s,%s,'MODEL_RAW',%s,%s,%s,%s,%s,'RESTRICTED','APPLICABLE',%s)""",
            (artifact_id, job["project_id"], f"{job['id']}-raw-output.txt",
             "text/plain; charset=utf-8", size, raw_hash, object_key, job["created_by"]),
        )
        cur.execute(
            """INSERT INTO model_runs(id,project_id,job_id,attempt_id,raw_artifact_id,raw_sha256,finish_reason,
               token_usage,receipt,request_id,boot_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)""",
            (run_id, job["project_id"], job["id"], job["attempt_id"], artifact_id, raw_hash,
             receipt.get("finish_reason"), json.dumps(token_usage), json.dumps(receipt),
             receipt.get("request_id"), receipt.get("boot_id")),
        )
        cur.execute(
            """INSERT INTO validations(id,model_run_id,status,errors,parsed_output)
               VALUES (%s,%s,%s,%s::jsonb,%s::jsonb)""",
            (validation_id, run_id, validation_status, json.dumps(errors), json.dumps(parsed, ensure_ascii=False) if parsed is not None else None),
        )
        if validation_status == "VALID" and parsed:
            actions = parsed.get("actions") or [parsed]
            for action_index, action in enumerate(actions):
                action_name = action["action"]
                contribution_type = "CHALLENGE" if action_name in {"CHALLENGE", "CONTRADICT"} else "FINDING"
                evidence_refs = [str(value) for value in action.get("evidence_refs", [])]
                contribution, contribution_replayed = create_contribution(
                    cur,
                    project_id=job["project_id"],
                    claim_id=job["claim_id"],
                    contribution_type=contribution_type,
                    target_object_type="CLAIM",
                    target_object_id=job["claim_id"],
                    content=action,
                    evidence_refs=evidence_refs,
                    actor_type="MODEL",
                    actor_id=job["model_profile"],
                    read_project_version=job["project_version"],
                    read_claim_version=job["claim_version"],
                    idempotency_key=f"review-job:{job['id']}:action:{action_index}",
                    source_snapshot_id=job["snapshot_id"],
                    source_job_id=job["id"],
                    action_index=action_index,
                )
                if not contribution_replayed:
                    contribution_count += 1
                if action_name != "REQUEST_EVIDENCE":
                    continue
                requested_items = action.get("requested_items") or action.get("requested_evidence") or []
                for requested_index, requested_item in enumerate(requested_items):
                    description = request_catalog.get(requested_item, requested_item)
                    evidence_request_id = uuid4()
                    cur.execute(
                        """INSERT INTO evidence_requests(id,project_id,job_id,claim_id,requested_item,source,created_by)
                           VALUES (%s,%s,%s,%s,%s,'MODEL',%s)
                           ON CONFLICT (job_id,requested_item) DO UPDATE SET requested_item=excluded.requested_item
                           RETURNING id""",
                        (evidence_request_id, job["project_id"], job["id"], job["claim_id"], description, job["created_by"]),
                    )
                    evidence_request_id = cur.fetchone()["id"]
                    input_refs = [
                        {"object_type": "CLAIM", "object_id": str(job["claim_id"]), "version": job["claim_version"]},
                    ]
                    for evidence_id in evidence_refs:
                        cur.execute(
                            "SELECT 1 FROM evidence WHERE id=%s AND project_id=%s",
                            (evidence_id, job["project_id"]),
                        )
                        object_type = "EVIDENCE" if cur.fetchone() else "DOCUMENT_CHUNK"
                        input_refs.append({"object_type": object_type, "object_id": evidence_id})
                    _, work_item_replayed = create_work_item(
                        cur,
                        project_id=job["project_id"],
                        claim_id=job["claim_id"],
                        work_type="EVIDENCE_REQUEST",
                        title=f"근거 요청 · {description[:240]}",
                        purpose=description,
                        input_refs=input_refs,
                        assigned_role="EVIDENCE",
                        budget={"model_calls": 0, "requires_human_submission": True},
                        status="WAITING_INPUT",
                        idempotency_key=f"review-job:{job['id']}:action:{action_index}:request:{requested_index}",
                        actor_type="MODEL",
                        actor_id=job["model_profile"],
                        source_project_version=job["project_version"],
                        source_claim_version=job["claim_version"],
                        source_contribution_id=contribution["id"],
                        source_job_id=job["id"],
                        evidence_request_id=evidence_request_id,
                    )
                    if not work_item_replayed:
                        work_item_count += 1
        cur.execute(
            """SELECT c.version AS claim_version,p.version AS project_version
               FROM claims c JOIN projects p ON p.id=c.project_id WHERE c.id=%s""",
            (job["claim_id"],),
        )
        current = cur.fetchone()
        freshness = "CURRENT" if current["claim_version"] == job["claim_version"] and current["project_version"] == job["project_version"] else "STALE"
        cur.execute(
            """UPDATE review_jobs SET status=%s,freshness=%s,error_code=%s,version=version+1,updated_at=now()
               WHERE id=%s""",
            (job_status, freshness, "OUTPUT_VALIDATION_FAILED" if errors else None, job["id"]),
        )
        cur.execute(
            "UPDATE review_attempts SET status=%s,finished_at=now() WHERE id=%s",
            ("OUTPUT_REJECTED" if errors else "COMPLETED", job["attempt_id"]),
        )
        complete_worker_path(
            cur,
            job=job,
            model_run_id=run_id,
            raw_sha256=raw_hash,
            receipt=receipt,
            validation_id=validation_id,
            validation_status=validation_status,
            validation_errors=errors,
            contribution_count=contribution_count,
            work_item_count=work_item_count,
        )
        if freshness == "STALE":
            mark_stale(cur, job_id=job["id"], actor_id="worker", reason="INPUT_CHANGED_DURING_GENERATION")


def fail_job(job: dict, exc: Exception) -> None:
    detail = str(exc)[:1000]
    if detail.startswith("UNKNOWN_OUTCOME"):
        status, code = "UNKNOWN_OUTCOME", "UNKNOWN_OUTCOME"
    elif detail.startswith("WARMING_UP") or detail.startswith("SERVICE_BUSY"):
        status, code = "QUEUED", detail.split(":", 1)[0]
    else:
        status, code = "FAILED", detail.split(":", 1)[0]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE review_jobs SET status=%s,error_code=%s,error_detail=%s,version=version+1,
                      leased_by=NULL,leased_at=NULL,updated_at=now() WHERE id=%s""",
            (status, code, detail, job["id"]),
        )
        cur.execute("UPDATE review_attempts SET status=%s,finished_at=now() WHERE id=%s", (status, job["attempt_id"]))
        fail_source_review(cur, job=job, status=status, error_code=code, detail=detail)


def run_one() -> bool:
    job = claim_job()
    if not job:
        return False
    try:
        if job["mode"] in {"SIMULATED", "REPLAY"}:
            if APP_MODE != "DEMO":
                raise RuntimeError("DEMO_MODE_DISABLED")
            raw, receipt = simulated_output(job)
        else:
            if APP_MODE == "DEMO":
                raise RuntimeError("LIVE_MODE_DISABLED")
            raw, receipt = live_output(job)
        store_result(job, raw, receipt)
    except Exception as exc:
        fail_job(job, exc)
    return True


def main() -> None:
    if APP_MODE == "DEMO":
        set_remote_state("LOCAL_ONLY", "explicit DEMO mode")
    poll = float(os.getenv("DORILAB_WORKER_POLL_SECONDS", "1"))
    recovery_interval = float(os.getenv("DORILAB_WORKER_RECOVERY_SECONDS", "15"))
    remote_check_interval = float(os.getenv("DORILAB_REMOTE_CHECK_SECONDS", "10"))
    last_recovery = 0.0
    last_remote_check = 0.0
    while True:
        if time.monotonic() - last_recovery >= recovery_interval:
            recover_orphaned_jobs()
            last_recovery = time.monotonic()
        if APP_MODE != "DEMO" and time.monotonic() - last_remote_check >= remote_check_interval:
            refresh_remote_state()
            last_remote_check = time.monotonic()
        if not run_one():
            time.sleep(poll)


if __name__ == "__main__":
    main()
