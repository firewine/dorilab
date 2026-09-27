"""Evidence gathering -> unchanged SourceReview native request contract.

Only retrieved evidence enters observations. The bundle, cache metadata, memory
instructions and provenance receipt remain outside the model's system prompt.
"""
from copy import deepcopy
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .store import MemoryError, ConflictError, atomic_json, canonical, digest, validate_content, validate_scope

CONTRACT_ID = "7240db117d7c66d5bb162ce72290fee4b87bfaefa97771246d392be07c0b0114"
PARENT_CONTRACT_ID = "4fe243c2300a5084f54833e7b6fd8aa45f55592c9dfcf6aaa53cc07692e0282f"
PACKET_FIELDS = {"claim_id", "review_question", "review_target", "scope", "source_refs",
                 "observations", "request_catalog", "scope_of_result"}


def prepare(store, project, packet, *, contract_id=CONTRACT_ID, max_new_tokens=384,
            top_k=6, max_bytes=12000, queries=None, token_counter=None, controller=None):
    store.access.check(project)
    if contract_id not in {CONTRACT_ID, PARENT_CONTRACT_ID}:
        raise MemoryError("memory bridge supports pinned SourceReview contracts only")
    if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= 384:
        raise MemoryError("response reservation must be 1..384")
    validate_content(packet)
    if not isinstance(packet, dict) or set(packet) != PACKET_FIELDS:
        raise MemoryError("SourceReview packet fields must match existing contract")
    validate_scope(packet["scope"])
    for field in ("observations", "source_refs", "request_catalog"):
        if not isinstance(packet[field], list):
            raise MemoryError("packet list field required")
    used = []
    for rows, key in ((packet["observations"], "evidence_id"), (packet["source_refs"], "reference_id")):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get(key), str):
                raise MemoryError("invalid native evidence reference")
            used.append(row[key])
    if len(used) != len(set(used)):
        raise MemoryError("duplicate native evidence reference")
    gather = controller.gather if controller is not None else lambda s, *a, **kw: s.query(*a, **kw)
    bundle = gather(store, project, packet["review_question"], packet["scope"], queries=queries,
                    top_k=top_k, max_bytes=max_bytes)
    enriched = deepcopy(packet)
    for row in bundle["evidence"]:
        if row["evidence_id"] in used:
            raise MemoryError("memory evidence ID collides with supplied evidence")
        metadata = {k: row[k] for k in ("pool", "source", "source_hash", "trajectory_id", "step_indices")}
        if "observed_at" in row:
            metadata["observed_at"] = row["observed_at"]
        enriched["observations"].append(dict(
            evidence_id=row["evidence_id"], display_id=row["evidence_id"], scope=deepcopy(row["scope"]),
            text="Memory provenance: " + canonical(metadata) + "\n" + row["text"],
            origin="PROJECT_MEMORY_" + row["pool"].upper()))
    user = canonical(enriched)
    request = dict(request_id="mem-" + uuid.uuid4().hex, contract_id=contract_id,
                   user=user, max_new_tokens=max_new_tokens)
    if len(user) > 60000 or len(canonical(request).encode()) > 65536:
        raise MemoryError("native HTTP input limit exceeded; select fewer whole records")
    tokens = token_counter(contract_id, user, max_new_tokens) if token_counter else None
    if tokens is not None and (type(tokens) is not int or tokens < 1 or tokens + max_new_tokens > 4096):
        raise MemoryError("native input plus response reservation exceeds 4096; no truncation")
    receipt = dict(schema="dorilab.memory-preparation.v1", project_id=project,
                   memory_version=bundle["version"], bundle_hash=bundle["bundle_hash"],
                   evidence_ids=[r["evidence_id"] for r in bundle["evidence"]],
                   user_sha256=hashlib.sha256(user.encode()).hexdigest(),
                   native_input_tokens=tokens,
                   token_budget_validation="local-native" if tokens is not None else "server-before-202",
                   original_packet_sha256=digest(packet), output_used_as_memory=False)
    return dict(request=request, memory=bundle, receipt=receipt)


class APIError(RuntimeError):
    pass


class HTTPClient:
    """Loopback SSH tunnel or HTTPS only. Redirects never forward credentials."""
    def __init__(self, base_url, token):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise MemoryError("invalid API URL")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise MemoryError("use a loopback SSH tunnel or HTTPS")
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        if len(self.token) < 32:
            raise MemoryError("invalid token file")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, path, body=None, *, timeout=30):
        data = canonical(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"Authorization": "Bearer " + self.token,
                                              "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            # No automatic resubmit on 429/503/422 or ambiguous network failure.
            raise APIError(f"HTTP {error.code}; see saved request; not automatically retried") from error


def generate(store, project, preparation, client, output_dir, *, timeout=300, poll_interval=0.5):
    """One submission. Save input before sending and accepted ID before polling.

    Submission uses an explicit memory snapshot; later updates do not retroactively
    change a running request. No answer is automatically promoted to memory.
    """
    from pathlib import Path
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=False)
    request = preparation["request"]
    receipt = preparation["receipt"]
    if receipt["project_id"] != project:
        raise MemoryError("preparation project mismatch")
    if store.manifest(project)["version"] != receipt["memory_version"]:
        raise ConflictError("memory changed since preparation; gather again")
    if hashlib.sha256(request["user"].encode()).hexdigest() != receipt["user_sha256"]:
        raise MemoryError("prepared input changed")
    status, version = client.call("/version")
    if status != 200 or not version.get("ready"):
        raise APIError("inference service not ready")
    if request["contract_id"] not in {c["id"] for c in version["contracts"]}:
        raise APIError("pinned memory bridge contract not served")
    atomic_json(directory / "preparation.json", preparation)
    atomic_json(directory / "service_version.json", version)
    try:
        status, accepted = client.call("/v1/generations", request)
        if status != 202:
            raise APIError("expected HTTP 202")
        atomic_json(directory / "accepted.json", accepted)
        if accepted["boot_id"] != version["boot_id"]:
            raise APIError("server boot changed; retain accepted ID and inspect, do not replay")
        deadline = time.monotonic() + timeout
        while True:
            status, result = client.call("/v1/generations/" + accepted["id"])
            if status != 200:
                raise APIError("unexpected poll status")
            if result["status"] in {"completed", "failed"}:
                atomic_json(directory / "result.json", result)
                if result["status"] != "completed":
                    raise APIError("generation failed; result preserved")
                if result.get("boot_id") != accepted["boot_id"] or result.get("model_receipt_id") != version["model_receipt_id"]:
                    raise APIError("result identity changed")
                summary = dict(receipt, boot_id=result["boot_id"], model_receipt_id=result["model_receipt_id"],
                               job_id=accepted["id"], output_sha256=result["output_sha256"],
                               purpose="memory integration smoke; not engineering accuracy or LongMemEval score")
                atomic_json(directory / "memory_generation_receipt.json", summary)
                return summary
            if time.monotonic() >= deadline:
                raise APIError("poll timeout; resume GET using accepted.json; never blindly resubmit")
            time.sleep(poll_interval)
    except Exception as error:
        atomic_json(directory / "failure.json", {"error_type": type(error).__name__,
                    "message": "Submission may have been accepted. Inspect accepted.json or saved request ID before any retry."})
        raise
