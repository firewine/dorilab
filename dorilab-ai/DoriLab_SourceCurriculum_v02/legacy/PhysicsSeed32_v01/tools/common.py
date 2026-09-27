from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected an object")
            result.append(row)
    return result


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def changed_paths(a: Any, b: Any, prefix: str = "") -> list[str]:
    if type(a) is not type(b):
        return [prefix]
    if isinstance(a, dict):
        paths = []
        for key in sorted(set(a) | set(b)):
            p = f"{prefix}.{key}" if prefix else key
            paths.extend([p] if key not in a or key not in b else changed_paths(a[key], b[key], p))
        return paths
    if isinstance(a, list):
        if len(a) != len(b):
            return [prefix]
        return [p for i, (x, y) in enumerate(zip(a, b))
                for p in changed_paths(x, y, f"{prefix}.{i}")]
    return [] if a == b else [prefix]


def action_errors(value: Any, packet: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate the deliberately small action contract with the Python standard library.

    This validates structure/references, NOT the engineering correctness of a conclusion.
    """
    if not isinstance(value, dict):
        return ["root must be a JSON object"]
    branches = schema["oneOf"]
    branch = next((b for b in branches
                   if b["properties"]["action"]["const"] == value.get("action")), None)
    if branch is None:
        return ["unknown or missing action"]
    errors = []
    for k in branch["required"]:
        if k not in value:
            errors.append(f"missing field: {k}")
    extra = set(value) - set(branch["properties"])
    if extra:
        errors.append("unexpected fields: " + ", ".join(sorted(extra)))
    if value.get("claim_id") != packet["claim_id"]:
        errors.append("claim_id does not match the input")
    if "reason" in value:
        allowed = branch["properties"].get("reason", {}).get("enum", [])
        if value["reason"] not in allowed:
            errors.append("unknown reason")
    for field in ("evidence_refs", "requested_evidence"):
        if field not in branch["properties"] or field not in value:
            continue
        refs = value[field]
        if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
            errors.append(f"{field} must be a nonempty string array")
            continue
        if len(refs) != len(set(refs)):
            errors.append(f"duplicate {field}")
        if field == "evidence_refs":
            allowed_ids = {x["reference_id"] for x in packet["reference_context"]}
            allowed_ids |= {x["evidence_id"] for x in packet["case_packet"]["evidence"]}
        else:
            allowed_ids = set(packet["allowed_request_ids"])
        if set(refs) - allowed_ids:
            errors.append(f"unknown {field}: {sorted(set(refs) - allowed_ids)}")
    return errors


def matches_gold(expected: dict[str, Any], actual: Any) -> bool:
    """Exact fields, with order-insensitive citation/request ID arrays only."""
    if not isinstance(actual, dict) or set(actual) != set(expected):
        return False
    for k, v in expected.items():
        if k in {"evidence_refs", "requested_evidence"}:
            other = actual[k]
            if not isinstance(other, list) or any(not isinstance(x, str) for x in other):
                return False
            if len(other) != len(set(other)) or set(other) != set(v):
                return False
        elif actual[k] != v:
            return False
    return True
