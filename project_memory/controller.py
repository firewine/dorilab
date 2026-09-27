"""Bounded retrieval controller. Plans are untrusted; scope and tools are code-owned."""
from copy import deepcopy
from pathlib import Path
import re
import time
import uuid

from .store import (MemoryError, ConflictError, POOLS, canonical, digest, strict_loads,
                    atomic_json, validate_scope, text_field)
from .planner_contract import CONTRACT_ID


class PlanError(ValueError):
    pass


def validate_plan(raw, known):
    if not isinstance(raw, str) or len(raw.encode()) > 12000:
        raise PlanError("oversized or nontext plan")
    try:
        plan = strict_loads(raw)
    except (ValueError, TypeError, RecursionError) as error:
        raise PlanError("invalid plan JSON") from error
    if not isinstance(plan, dict):
        raise PlanError("plan must be object")
    action = plan.get("action")
    if not isinstance(action, str):
        raise PlanError("action must be string")
    if action == "search":
        if set(plan) != {"action", "queries"} or not isinstance(plan["queries"], dict):
            raise PlanError("invalid search fields")
        if not 1 <= len(plan["queries"]) <= 3 or set(plan["queries"]) - set(POOLS):
            raise PlanError("invalid pools")
        for query in plan["queries"].values():
            if not isinstance(query, str) or not query.strip() or len(query) > 600:
                raise PlanError("invalid query")
    elif action in {"inspect", "finish"}:
        fields = {"action", "evidence_ids"} | ({"assessment", "missing"} if action == "finish" else set())
        if set(plan) != fields:
            raise PlanError("invalid selection fields")
        ids = plan["evidence_ids"]
        cap = 3 if action == "inspect" else 6
        if not isinstance(ids, list) or len(ids) > cap or any(not isinstance(i, str) or i not in known for i in ids):
            raise PlanError("unknown evidence ID")
        if len(ids) != len(set(ids)) or (action == "inspect" and not ids):
            raise PlanError("invalid evidence selection")
        if action == "finish":
            if not isinstance(plan["assessment"], str) or plan["assessment"] not in {"sufficient", "insufficient", "conflict"}:
                raise PlanError("invalid assessment")
            missing = plan["missing"]
            if not isinstance(missing, list) or len(missing) > 3 or any(not isinstance(x, str) or not x.strip() or len(x) > 300 for x in missing):
                raise PlanError("invalid missing information")
            if plan["assessment"] == "sufficient" and (not ids or missing):
                raise PlanError("sufficient needs evidence and no missing information")
    else:
        raise PlanError("unknown action")
    return plan


class RulePlanner:
    """Deterministic offline planner; never labels evidence semantically sufficient."""
    name = "rules-v1"

    def __call__(self, context, timeout):
        ids = [r["evidence_id"] for r in context["candidates"]][:3]
        unseen = [i for i in ids if i not in context["inspected"]]
        if unseen:
            return canonical(dict(action="inspect", evidence_ids=unseen))
        return canonical(dict(action="finish", evidence_ids=ids, assessment="insufficient",
                              missing=["Rule planner retrieves evidence but cannot establish semantic sufficiency."]))


class QwenPlanner:
    """Use the existing single-worker service and the pinned BASE-Qwen contract.

    Every plan is an ordinary bounded generation job. No second model, arbitrary
    prompt, tool execution, response repair, or retry after ambiguous submission.
    """
    name = "qwen-base-v1"

    def __init__(self, client, trace_dir):
        self.client = client
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=False)
        self.sequence = 0

    def __call__(self, context, timeout):
        self.sequence += 1
        directory = self.trace_dir / str(self.sequence)
        directory.mkdir()
        deadline = time.monotonic() + timeout
        def call(path, body=None):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("planner deadline")
            return self.client.call(path, body, timeout=min(30, remaining))
        status, version = call("/version")
        if status != 200 or not version.get("ready") or CONTRACT_ID not in {c["id"] for c in version.get("contracts", [])}:
            raise PlanError("base-Qwen planner contract unavailable")
        request = dict(request_id="plan-" + uuid.uuid4().hex, contract_id=CONTRACT_ID,
                       user=canonical(context), max_new_tokens=384)
        atomic_json(directory / "request.json", request)
        atomic_json(directory / "service_version.json", version)
        status, accepted = call("/v1/generations", request)
        if status != 202:
            raise PlanError("planner not accepted")
        atomic_json(directory / "accepted.json", accepted)
        if accepted["boot_id"] != version["boot_id"]:
            raise PlanError("planner boot changed")
        while True:
            status, result = call("/v1/generations/" + accepted["id"])
            if status != 200:
                raise PlanError("planner poll failed")
            if result["status"] in {"completed", "failed"}:
                atomic_json(directory / "result.json", result)
                if (result["status"] != "completed" or result.get("execution_mode") != "memory_planner"
                        or result.get("adapter_applied") is not False
                        or result.get("boot_id") != accepted["boot_id"]
                        or result.get("model_receipt_id") != version["model_receipt_id"]):
                    raise PlanError("planner execution identity mismatch")
                return result["text"]
            time.sleep(min(0.2, max(0, deadline-time.monotonic())))


class SearchController:
    def __init__(self, planner=None, *, max_searches=3, max_steps=6, timeout=90, context_bytes=10500):
        if type(max_searches) is not int or not 1 <= max_searches <= 3:
            raise MemoryError("search bound is 1..3")
        if type(max_steps) is not int or not 1 <= max_steps <= 8:
            raise MemoryError("controller step bound is 1..8")
        if isinstance(timeout, bool) or not 1 <= timeout <= 180 or not 2000 <= context_bytes <= 14000:
            raise MemoryError("invalid controller time/context bounds")
        self.planner = planner or RulePlanner()
        self.max_searches, self.max_steps = max_searches, max_steps
        self.timeout, self.context_bytes = timeout, context_bytes

    def gather(self, store, project, question, scope, *, queries=None, top_k=6, max_bytes=12000):
        store.access.check(project)
        validate_scope(scope)
        text_field(question, 4000)
        # Bound controller candidate growth to <= 3 * 6 records. Legacy direct
        # retrieval may use 30, but controller plans can select at most six.
        if not 1 <= top_k <= 6:
            raise MemoryError("controller top_k must be 1..6")
        started = time.monotonic()
        deadline = started + self.timeout
        baseline = store.query(project, question, scope, queries=queries, top_k=top_k, max_bytes=max_bytes)
        version = baseline["version"]
        known = {r["evidence_id"]: r for r in baseline["evidence"]}
        inspected, trace = {}, []
        history = [queries or {pool: question for pool in POOLS}]
        searches = 1

        def stable():
            if store.manifest(project)["version"] != version:
                raise ConflictError("memory changed during planning; gather again")

        def inspect(eid):
            row = known[eid]
            span = store.inspect(project, row["trajectory_id"], min(row["step_indices"]), max(row["step_indices"])+1)
            if span["version"] != version or span["source_hash"] != row["source_hash"] or span["scope"] != scope:
                raise ConflictError("source span no longer matches retrieved evidence")
            return span

        def finish(ids, reason, assessment, missing, *, fallback=False):
            stable()
            selected, excluded, used = [], [], 2
            for eid in ids:
                row = known[eid]
                cost = len(canonical(row).encode()) + (1 if selected else 0)
                why = "top_k" if len(selected) >= top_k else "byte_budget" if used+cost > max_bytes else None
                if why:
                    excluded.append(dict(evidence_id=eid, reason=why))
                else:
                    # Always verify origin even if a model skipped inspect.
                    inspected[eid] = inspected.get(eid) or inspect(eid)
                    selected.append(deepcopy(row)); used += cost
            stable()
            if excluded or (assessment == "sufficient" and not selected):
                assessment = "insufficient"
                missing = [*missing, "Selected evidence exceeded the delivery budget."][:3]
            result = deepcopy(baseline)
            result.update(evidence=selected, evidence_bytes=used, excluded=excluded,
                          status="evidence_found" if selected else "no_evidence", cache_hit=False,
                          selection_policy="controller-whole-records; source spans verified")
            result["controller"] = dict(schema="dorilab.search-controller.v1", planner=self.planner.name,
                stop_reason=reason, fallback=fallback, assessment=assessment, assessment_is_advisory=True,
                missing=missing, searches=searches, steps=len(trace), trace=trace,
                inspected={eid: {"source_hash": span["source_hash"], "span_sha256": digest(span),
                                 "start":span["start"], "stop":span["stop"]} for eid, span in inspected.items()},
                elapsed_seconds=time.monotonic()-started)
            result.pop("bundle_hash", None)
            result["bundle_hash"] = digest({k:v for k,v in result.items() if k != "cache_hit"})
            return result

        def fallback(reason):
            return finish([r["evidence_id"] for r in baseline["evidence"]], reason, "insufficient",
                          ["Controller stopped; baseline retrieval requires reviewer assessment."], fallback=True)

        for step in range(self.max_steps):
            stable()
            if time.monotonic() >= deadline:
                return fallback("deadline")
            # Whole records/spans only; omissions are explicit and selectable IDs
            # are restricted to those actually shown to this planner call.
            context = dict(question=question, scope=deepcopy(scope), candidates=[], inspected={},
                           searches=deepcopy(history), remaining_searches=self.max_searches-searches,
                           remaining_steps=self.max_steps-step, omitted_candidates=[])
            for eid, row in known.items():
                context["candidates"].append(row)
                if len(canonical(context).encode()) > self.context_bytes:
                    context["candidates"].pop()
                    context["omitted_candidates"].append(eid)
            visible = {r["evidence_id"] for r in context["candidates"]}
            for eid, span in inspected.items():
                if eid in visible:
                    context["inspected"][eid] = span
                    if len(canonical(context).encode()) > self.context_bytes:
                        del context["inspected"][eid]
            if len(canonical(context).encode()) > self.context_bytes:
                return fallback("context_budget")
            try:
                raw = self.planner(deepcopy(context), max(0.01, deadline-time.monotonic()))
                if time.monotonic() >= deadline:
                    return fallback("deadline")
                plan = validate_plan(raw, visible)
            except (ValueError, TypeError, KeyError, TimeoutError, OSError, RuntimeError) as error:
                trace.append(dict(step=step, error_type=type(error).__name__))
                return fallback("planner_error")
            trace.append(dict(step=step, plan=plan, plan_sha256=digest(plan)))
            if plan["action"] == "finish":
                assessment = plan["assessment"]
                missing = plan["missing"]
                if assessment == "sufficient" and any(i not in context["inspected"] for i in plan["evidence_ids"]):
                    assessment = "insufficient"
                    missing = ["Planner did not review the selected source spans."]
                return finish(plan["evidence_ids"], "finished", assessment, missing)
            if plan["action"] == "inspect":
                if all(eid in inspected for eid in plan["evidence_ids"]):
                    return fallback("repeated_inspection")
                for eid in plan["evidence_ids"]:
                    inspected[eid] = inspect(eid)
            else:
                if plan["queries"] in history:
                    return fallback("repeated_query")
                if searches >= self.max_searches:
                    return fallback("search_limit")
                searches += 1
                history.append(plan["queries"])
                result = store.query(project, question, scope, queries=plan["queries"], top_k=top_k, max_bytes=max_bytes)
                if result["version"] != version:
                    raise ConflictError("memory changed during retrieval")
                for row in result["evidence"]:
                    known[row["evidence_id"]] = row
        return fallback("step_limit")
