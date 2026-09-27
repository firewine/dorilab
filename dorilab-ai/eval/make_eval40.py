import json
import hashlib
from pathlib import Path

INPUTS = Path("eval/eval40_inputs_v1.jsonl")
GOLD = Path("eval/eval40_gold_v1.jsonl")
MANIFEST = Path("eval/eval40_manifest_v1.json")

for p in [INPUTS, GOLD, MANIFEST]:
    if p.exists():
        raise SystemExit(
            f"{p} already exists. "
            "Evaluation set is locked; do not overwrite it."
        )

cases = []

def add(case_id, split, role, state, expected):
    cases.append({
        "id": case_id,
        "split": split,
        "role": role,
        "input": state,
        "expected": expected,
    })


# =========================================================
# DEV: 20
# =========================================================

# ---------- ANALYSIS: 6 ----------

add(
    "DEV-AN-001", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 40,
        "actual_by_axis": {"X": 40, "Y": 39, "Z": 40},
        "tool_result": None,
    },
    {
        "action": "CALL_TOOL",
        "tool": "compare_axis_durations",
        "arguments": {
            "required_s": 40,
            "actual_by_axis": {"X": 40, "Y": 39, "Z": 40},
        },
    },
)

add(
    "DEV-AN-002", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 55,
        "actual_by_axis": {"X": 55, "Y": 55, "Z": 55},
        "tool_result": None,
    },
    {
        "action": "CALL_TOOL",
        "tool": "compare_axis_durations",
        "arguments": {
            "required_s": 55,
            "actual_by_axis": {"X": 55, "Y": 55, "Z": 55},
        },
    },
)

add(
    "DEV-AN-003", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": None,
        "actual_by_axis": {"X": 60, "Y": 60, "Z": 60},
        "tool_result": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "DURATION_INPUT_MISSING",
    },
)

add(
    "DEV-AN-004", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 60,
        "actual_by_axis": None,
        "tool_result": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "DURATION_INPUT_MISSING",
    },
)

add(
    "DEV-AN-005", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 60,
        "actual_by_axis": {"X": 60, "Y": 60, "Z": 58},
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Z"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "DEV-AN-006", "dev", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 30,
        "actual_by_axis": {"X": 30, "Y": 30, "Z": 30},
        "tool_result": {
            "verdict": "COMPLIANT",
            "affected_axes": [],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)


# ---------- EVIDENCE: 7 ----------

add(
    "DEV-EV-001", "dev", "EVIDENCE",
    {
        "current_requirement": {
            "revision": "Rev.7",
            "duration": "80 s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": "Rev.6",
            "duration": "65 s/axis",
            "status": "CURRENT",
        },
    },
    {
        "action": "PROPOSE_FINDING",
        "finding_type": "PROCEDURE_REQUIREMENT_CONFLICT",
    },
)

add(
    "DEV-EV-002", "dev", "EVIDENCE",
    {
        "current_requirement": {
            "revision": "Rev.2",
            "duration": "45 s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": "Rev.3",
            "duration": "45 s/axis",
            "status": "CURRENT",
        },
        "old_procedure": {
            "revision": "Rev.1",
            "duration": "30 s/axis",
            "status": "SUPERSEDED",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "DEV-EV-003", "dev", "EVIDENCE",
    {
        "requirement": "90 s/axis",
        "as_run": None,
        "current_configuration": "EPS QM Rev.4",
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "AS_RUN_MISSING",
    },
)

add(
    "DEV-EV-004", "dev", "EVIDENCE",
    {
        "current_configuration": "Antenna FM Rev.D",
        "evidence_configuration": "Antenna FM Rev.C",
        "claim_scope": "VIBRATION",
        "applicability_review": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "CONFIGURATION_MISMATCH",
    },
)

add(
    "DEV-EV-005", "dev", "EVIDENCE",
    {
        "current_configuration": "Antenna FM Rev.D",
        "evidence_configuration": "Antenna FM Rev.C",
        "claim_scope": "THERMAL",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["THERMAL"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "DEV-EV-006", "dev", "EVIDENCE",
    {
        "current_requirement_revision": "Rev.9",
        "evidence_requirement_revision": "Rev.8",
        "claim_scope": "DURATION",
        "supersession_review": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "REVISION_MISMATCH",
    },
)

add(
    "DEV-EV-007", "dev", "EVIDENCE",
    {
        "current_requirement_revision": "Rev.9",
        "evidence_requirement_revision": "Rev.8",
        "claim_scope": "DURATION",
        "supersession_review": {
            "status": "APPROVED_APPLICABLE",
            "approved_scopes": ["DURATION"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)


# ---------- CRITIC: 7 ----------

add(
    "DEV-CR-001", "dev", "CRITIC",
    {
        "finding": {
            "statement": "X/Y/Z fail duration requirement",
            "scope": ["X", "Y", "Z"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Y"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "SCOPE_ERROR",
        "valid_scope": ["Y"],
    },
)

add(
    "DEV-CR-002", "dev", "CRITIC",
    {
        "finding": {
            "statement": "Y fails duration requirement",
            "scope": ["Y"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Y"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "DEV-CR-003", "dev", "CRITIC",
    {
        "finding": {
            "statement": "Duration requirement satisfied",
            "scope": ["X", "Y", "Z"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["X", "Z"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "EVIDENCE_CONTRADICTION",
        "valid_scope": ["X", "Z"],
    },
)

add(
    "DEV-CR-004", "dev", "CRITIC",
    {
        "finding": {
            "statement": "Rev.B evidence proves Rev.C vibration claim",
            "scope": "VIBRATION",
        },
        "current_configuration": "Rev.C",
        "evidence_configuration": "Rev.B",
        "applicability_review": None,
    },
    {
        "action": "CHALLENGE",
        "reason": "CONFIGURATION_MISMATCH",
    },
)

add(
    "DEV-CR-005", "dev", "CRITIC",
    {
        "finding": {
            "statement": "Rev.B evidence supports Rev.C thermal claim",
            "scope": "THERMAL",
        },
        "current_configuration": "Rev.C",
        "evidence_configuration": "Rev.B",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["THERMAL"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "DEV-CR-006", "dev", "CRITIC",
    {
        "finding": {
            "statement": "All duration axes satisfy requirement",
            "scope": ["X", "Y", "Z"],
        },
        "tool_result": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "SUPPORTING_EVIDENCE_MISSING",
    },
)

add(
    "DEV-CR-007", "dev", "CRITIC",
    {
        "finding": {
            "statement": "Procedure conflicts with requirement",
            "scope": "DURATION",
        },
        "evidence": {
            "current_requirement": "70 s/axis",
            "current_procedure": "55 s/axis",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)


# =========================================================
# HOLDOUT: 10
# =========================================================

add(
    "HOLD-AN-001", "holdout", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 110,
        "actual_by_axis": {
            "ROLL": 110,
            "PITCH": 107,
            "YAW": 110,
        },
        "tool_result": None,
    },
    {
        "action": "CALL_TOOL",
        "tool": "compare_axis_durations",
        "arguments": {
            "required_s": 110,
            "actual_by_axis": {
                "ROLL": 110,
                "PITCH": 107,
                "YAW": 110,
            },
        },
    },
)

add(
    "HOLD-AN-002", "holdout", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": None,
        "actual_by_axis": None,
        "tool_result": None,
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "DURATION_INPUT_MISSING",
    },
)

add(
    "HOLD-AN-003", "holdout", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 25,
        "actual_by_axis": {"A": 25, "B": 25},
        "tool_result": {
            "verdict": "COMPLIANT",
            "affected_axes": [],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "HOLD-EV-001", "holdout", "EVIDENCE",
    {
        "current_requirement": {
            "revision": "Rev.K",
            "duration": "100 s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": "Rev.J",
            "duration": "85 s/axis",
            "status": "CURRENT",
        },
    },
    {
        "action": "PROPOSE_FINDING",
        "finding_type": "PROCEDURE_REQUIREMENT_CONFLICT",
    },
)

add(
    "HOLD-EV-002", "holdout", "EVIDENCE",
    {
        "current_configuration": "Panel PFM Rev.12",
        "evidence_configuration": "Panel QM Rev.11",
        "claim_scope": "RANDOM_VIBRATION",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["THERMAL_BALANCE"],
        },
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "CONFIGURATION_MISMATCH",
    },
)

add(
    "HOLD-EV-003", "holdout", "EVIDENCE",
    {
        "current_requirement_revision": "Rev.15",
        "evidence_requirement_revision": "Rev.14",
        "claim_scope": "THERMAL_SURVIVAL",
        "supersession_review": {
            "status": "APPROVED_APPLICABLE",
            "approved_scopes": [
                "THERMAL_SURVIVAL",
                "THERMAL_OPERATIONAL",
            ],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "HOLD-EV-004", "holdout", "EVIDENCE",
    {
        "requirement": "120 s/axis",
        "as_run": {
            "source": "RUN-44",
            "status": "AVAILABLE",
        },
        "current_configuration": "OBC FM Rev.3",
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "HOLD-CR-001", "holdout", "CRITIC",
    {
        "finding": {
            "statement": "X and Z fail",
            "scope": ["X", "Z"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Z"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "SCOPE_ERROR",
        "valid_scope": ["Z"],
    },
)

add(
    "HOLD-CR-002", "holdout", "CRITIC",
    {
        "finding": {
            "statement": "Thermal evidence applies to current configuration",
            "scope": "THERMAL_BALANCE",
        },
        "current_configuration": "Panel Rev.C",
        "evidence_configuration": "Panel Rev.B",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["THERMAL_BALANCE"],
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "HOLD-CR-003", "holdout", "CRITIC",
    {
        "finding": {
            "statement": "Duration requirement satisfied",
            "scope": ["ROLL", "PITCH", "YAW"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["PITCH"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "EVIDENCE_CONTRADICTION",
        "valid_scope": ["PITCH"],
    },
)


# =========================================================
# ADVERSARIAL: 10
# =========================================================

add(
    "ADV-AN-001", "adversarial", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 60,
        "actual_by_axis": {
            "X": 60.0,
            "Y": 60.0,
            "Z": 60.0,
        },
        "tool_result": None,
        "note": (
            "Old report mentioned Z=58, "
            "but it is not the current run."
        ),
    },
    {
        "action": "CALL_TOOL",
        "tool": "compare_axis_durations",
        "arguments": {
            "required_s": 60,
            "actual_by_axis": {
                "X": 60.0,
                "Y": 60.0,
                "Z": 60.0,
            },
        },
    },
)

add(
    "ADV-AN-002", "adversarial", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 60,
        "actual_by_axis": None,
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Z"],
            "status": "STALE",
        },
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "DURATION_INPUT_MISSING",
    },
)

add(
    "ADV-AN-003", "adversarial", "ANALYSIS",
    {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": 70,
        "actual_by_axis": {
            "X": 70,
            "Y": 69,
            "Z": 70,
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Y"],
            "status": "CURRENT",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "ADV-EV-001", "adversarial", "EVIDENCE",
    {
        "current_requirement": {
            "revision": "Rev.5",
            "duration": "60 s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": "Rev.6",
            "duration": "60 s/axis",
            "status": "CURRENT",
        },
        "old_procedure": {
            "revision": "Rev.3",
            "duration": "45 s/axis",
            "status": "SUPERSEDED",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "ADV-EV-002", "adversarial", "EVIDENCE",
    {
        "current_configuration": "Camera FM Rev.C",
        "evidence_configuration": "Camera FM Rev.B",
        "claim_scope": "RANDOM_VIBRATION",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": [
                "THERMAL",
                "STATIC_LOAD",
            ],
        },
    },
    {
        "action": "REQUEST_EVIDENCE",
        "reason": "CONFIGURATION_MISMATCH",
    },
)

add(
    "ADV-EV-003", "adversarial", "EVIDENCE",
    {
        "current_requirement_revision": "Rev.10",
        "evidence_requirement_revision": "Rev.9",
        "claim_scope": "DURATION",
        "supersession_review": {
            "status": "APPROVED_APPLICABLE",
            "approved_scopes": ["DURATION"],
        },
        "older_conflicting_revision": {
            "revision": "Rev.7",
            "status": "SUPERSEDED",
            "duration": "45 s/axis",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "ADV-CR-001", "adversarial", "CRITIC",
    {
        "finding": {
            "statement": "Current run proves all axes compliant",
            "scope": ["X", "Y", "Z"],
        },
        "tool_result": {
            "verdict": "COMPLIANT",
            "affected_axes": [],
            "status": "CURRENT",
        },
        "old_tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Z"],
            "status": "SUPERSEDED",
        },
    },
    {
        "action": "NO_ACTION_REQUIRED",
    },
)

add(
    "ADV-CR-002", "adversarial", "CRITIC",
    {
        "finding": {
            "statement": "Rev.B evidence proves Rev.C vibration claim",
            "scope": "RANDOM_VIBRATION",
        },
        "current_configuration": "Rev.C",
        "evidence_configuration": "Rev.B",
        "applicability_review": {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["THERMAL_BALANCE"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "CONFIGURATION_MISMATCH",
    },
)

add(
    "ADV-CR-003", "adversarial", "CRITIC",
    {
        "finding": {
            "statement": "Only Z fails",
            "scope": ["Z"],
        },
        "tool_result": {
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["X", "Z"],
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "SCOPE_ERROR",
        "valid_scope": ["X", "Z"],
    },
)

add(
    "ADV-CR-004", "adversarial", "CRITIC",
    {
        "finding": {
            "statement": "Procedure mismatch exists",
            "scope": "DURATION",
        },
        "evidence": {
            "current_requirement": {
                "duration": "60 s/axis",
                "status": "CURRENT",
            },
            "current_procedure": {
                "duration": "60 s/axis",
                "status": "CURRENT",
            },
            "old_procedure": {
                "duration": "45 s/axis",
                "status": "SUPERSEDED",
            },
        },
    },
    {
        "action": "CHALLENGE",
        "reason": "EVIDENCE_CONTRADICTION",
        "valid_scope": "DURATION",
    },
)


assert len(cases) == 40
assert sum(x["split"] == "dev" for x in cases) == 20
assert sum(x["split"] == "holdout" for x in cases) == 10
assert sum(x["split"] == "adversarial" for x in cases) == 10


with INPUTS.open("w", encoding="utf-8") as f:
    for x in cases:
        f.write(json.dumps({
            "id": x["id"],
            "split": x["split"],
            "role": x["role"],
            "input": x["input"],
        }, ensure_ascii=False) + "\n")


with GOLD.open("w", encoding="utf-8") as f:
    for x in cases:
        f.write(json.dumps({
            "id": x["id"],
            "expected": x["expected"],
        }, ensure_ascii=False) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


manifest = {
    "version": "eval40-v1",
    "total_cases": 40,
    "splits": {
        "dev": 20,
        "holdout": 10,
        "adversarial": 10,
    },
    "roles": {
        "ANALYSIS": 12,
        "EVIDENCE": 14,
        "CRITIC": 14,
    },
    "inputs_sha256": sha256(INPUTS),
    "gold_sha256": sha256(GOLD),
}


MANIFEST.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8",
)

print("Created and LOCKED:")
print(INPUTS)
print(GOLD)
print(MANIFEST)
print()
print(json.dumps(manifest, indent=2))
