"""Build an immutable SourceReview contract overlay from the preserved RC3 allowlist."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "reference/runpod/inference/contracts/system_allowlist.json"
TARGET = Path(__file__).resolve().parent / "contracts/service_contracts.json"
PARENT_ID = "4fe243c2300a5084f54833e7b6fd8aa45f55592c9dfcf6aaa53cc07692e0282f"
ROUTE = "v15_rc1_cf1"


def main() -> None:
    allowlist = json.loads(SOURCE.read_text(encoding="utf-8"))
    parent = next(row for row in allowlist["contracts"] if row["id"] == PARENT_ID)
    old = (
        "Output exactly one JSON object without Markdown. For NO_ACTION_REQUIRED use exactly action, "
        "claim_id, evidence_refs. For CHALLENGE add reason. For REQUEST_EVIDENCE add reason and a "
        "nonempty requested_evidence array of unique provided request_catalog IDs. Omit all unrelated "
        "fields and empty request arrays. Use reason, never reason_code. Copy claim_id exactly."
    )
    new = (
        "Output exactly one JSON object without Markdown. The evidence_refs key is mandatory for every "
        "action. If no provided reference or observation directly supports the judgment, return exactly "
        "\"evidence_refs\":[]; never omit the key. For NO_ACTION_REQUIRED use exactly action, claim_id, "
        "evidence_refs. For CHALLENGE add reason. For REQUEST_EVIDENCE add reason and a nonempty "
        "requested_evidence array of unique provided request_catalog IDs. Omit all unrelated fields. "
        "requested_evidence is present only for REQUEST_EVIDENCE and must never be empty. Use reason, "
        "never reason_code. Copy claim_id exactly."
    )
    if parent["system"].count(old) != 1:
        raise RuntimeError("preserved parent contract text no longer matches the reviewed source")
    system = parent["system"].replace(old, new)
    contract_id = hashlib.sha256(system.encode("utf-8")).hexdigest()
    row = {
        "id": contract_id,
        "route": ROUTE,
        "system_sha256": contract_id,
        "parent_id": PARENT_ID,
        "change": "Require evidence_refs for every action and require [] when no supplied evidence supports it.",
        "system": system,
    }
    document = {"schema_version": 1, "contracts": [row]}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(contract_id)


if __name__ == "__main__":
    main()
