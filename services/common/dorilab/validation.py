from __future__ import annotations

import json


ACTIONS = {
    "NO_ACTION_REQUIRED": "EVIDENCE_SUFFICIENT",
    "REQUEST_EVIDENCE": "EVIDENCE_MISSING",
    "CONTRADICT": "EVIDENCE_CONFLICT",
}

LIVE_REASONS = {
    "AS_RUN_MISSING",
    "BOUNDARY_CONDITION_UNRESOLVED",
    "CONFIGURATION_SCOPE_UNRESOLVED",
    "EVIDENCE_INTERPRETATION_ERROR",
    "MEASUREMENT_MAPPING_MISMATCH",
    "METHOD_INTERPRETATION_ERROR",
    "MODAL_INPUTS_MISSING",
    "MODEL_SCOPE_EXCEEDED",
    "MODE_SELECTION_MISMATCH",
    "MONITORING_COVERAGE_INSUFFICIENT",
    "SUPPORTING_EVIDENCE_MISSING",
    "TEST_ARTIFACT_UNMODELED",
}


def _validate_live(
    parsed: dict,
    allowed_evidence_ids: set[str],
    expected_claim_id: str | None,
    allowed_request_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    action = parsed.get("action")
    fields = {
        "NO_ACTION_REQUIRED": {"action", "claim_id", "evidence_refs"},
        "CHALLENGE": {"action", "claim_id", "reason", "evidence_refs"},
        "REQUEST_EVIDENCE": {"action", "claim_id", "reason", "evidence_refs", "requested_evidence"},
    }
    if action not in fields:
        return ["ACTION_INVALID"]
    if set(parsed) != fields[action]:
        errors.append("ROOT_FIELDS_INVALID")
    if expected_claim_id is not None and parsed.get("claim_id") != expected_claim_id:
        errors.append("CLAIM_ID_MISMATCH")
    refs = parsed.get("evidence_refs")
    if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(not isinstance(v, str) for v in refs):
        errors.append("EVIDENCE_REFS_INVALID")
    elif any(ref not in allowed_evidence_ids for ref in refs):
        errors.append("UNPROVIDED_EVIDENCE_REF")
    if action != "NO_ACTION_REQUIRED" and parsed.get("reason") not in LIVE_REASONS:
        errors.append("REASON_INVALID")
    if action == "REQUEST_EVIDENCE":
        requested = parsed.get("requested_evidence")
        if (
            not isinstance(requested, list)
            or not requested
            or len(requested) != len(set(requested))
            or any(not isinstance(v, str) or v not in allowed_request_ids for v in requested)
        ):
            errors.append("REQUESTED_EVIDENCE_INVALID")
    return errors


def validate_output(
    raw: str,
    allowed_evidence_ids: set[str],
    *,
    contract_id: str | None = None,
    expected_claim_id: str | None = None,
    allowed_request_ids: set[str] | None = None,
) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"INVALID_JSON:{exc.msg}"]
    if not isinstance(parsed, dict):
        return None, ["ROOT_FIELDS_INVALID"]
    if contract_id and len(contract_id) == 64:
        return parsed, _validate_live(parsed, allowed_evidence_ids, expected_claim_id, allowed_request_ids or set())
    if not isinstance(parsed, dict) or set(parsed) != {"actions"}:
        return parsed if isinstance(parsed, dict) else None, ["ROOT_FIELDS_INVALID"]
    actions = parsed.get("actions")
    if not isinstance(actions, list) or not actions:
        return parsed, ["ACTIONS_REQUIRED"]
    for index, action in enumerate(actions):
        prefix = f"actions[{index}]"
        required = {"action", "reason_code", "reason", "evidence_refs", "requested_items"}
        if not isinstance(action, dict) or set(action) != required:
            errors.append(f"{prefix}:FIELDS_INVALID")
            continue
        expected_reason = ACTIONS.get(action["action"])
        if expected_reason is None:
            errors.append(f"{prefix}:ACTION_INVALID")
        elif action["reason_code"] != expected_reason:
            errors.append(f"{prefix}:REASON_CODE_INVALID")
        if not isinstance(action["reason"], str) or not action["reason"].strip():
            errors.append(f"{prefix}:REASON_REQUIRED")
        refs = action["evidence_refs"]
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            errors.append(f"{prefix}:EVIDENCE_REFS_INVALID")
        elif any(ref not in allowed_evidence_ids for ref in refs):
            errors.append(f"{prefix}:UNPROVIDED_EVIDENCE_REF")
        items = action["requested_items"]
        if (
            not isinstance(items, list)
            or len(items) != len(set(items))
            or any(not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in items)
        ):
            errors.append(f"{prefix}:REQUESTED_ITEMS_INVALID")
    return parsed, errors
