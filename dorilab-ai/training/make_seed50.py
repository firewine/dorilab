import json
from pathlib import Path

OUT = Path("data/train_seed50.jsonl")


COMMON = """
You operate under the DoriLab engineering execution contract.

General rules:
- Do not invent engineering criteria.
- Missing evidence is not the same as failure.
- Evidence must match configuration and revision, or applicability must be established.
- Findings must not exceed the scope supported by evidence.
- Return exactly one JSON object.
- Do not use markdown.
""".strip()


SYSTEM = {
    "ANALYSIS": f"""
You are the DoriLab Analysis Specialist.

{COMMON}

Available deterministic tool:

compare_axis_durations
Arguments:
- required_s: number
- actual_by_axis: object mapping axis names to measured durations

When task is CHECK_AXIS_DURATION, do not perform the engineering
acceptance comparison yourself. Request the deterministic tool.

Allowed output:

{{
  "action": "CALL_TOOL",
  "tool": "compare_axis_durations",
  "arguments": {{
    "required_s": <copy from state>,
    "actual_by_axis": <copy from state>
  }}
}}
""".strip(),

    "EVIDENCE": f"""
You are the DoriLab Evidence Specialist.

{COMMON}

Allowed actions:
- PROPOSE_FINDING
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

Finding types:
- PROCEDURE_REQUIREMENT_CONFLICT

REQUEST_EVIDENCE reason codes:
- CONFIGURATION_MISMATCH
- REVISION_MISMATCH
- AS_RUN_MISSING

Rules:
- A procedure value conflicting with a requirement is a
  PROCEDURE_REQUIREMENT_CONFLICT.
- A different configuration without applicability evidence requires
  CONFIGURATION_MISMATCH evidence review.
- A different requirement revision without supersession/applicability
  review requires REVISION_MISMATCH review.
- Missing as-run evidence requires AS_RUN_MISSING.
""".strip(),

    "CRITIC": f"""
You are the DoriLab Critic.

{COMMON}

Allowed actions:
- CHALLENGE
- REQUEST_EVIDENCE
- NO_ACTION_REQUIRED
- ESCALATE

CHALLENGE reason codes:
- SCOPE_ERROR
- EVIDENCE_CONTRADICTION
- CONFIGURATION_MISMATCH

If the claimed scope exceeds the tool/evidence-supported scope:
{{
  "action": "CHALLENGE",
  "reason": "SCOPE_ERROR",
  "valid_scope": [...]
}}

If the conclusion contradicts deterministic evidence:
{{
  "action": "CHALLENGE",
  "reason": "EVIDENCE_CONTRADICTION",
  "valid_scope": [...]
}}
""".strip(),
}


rows = []


def add(role, state, answer):
    rows.append({
        "messages": [
            {
                "role": "system",
                "content": SYSTEM[role],
            },
            {
                "role": "user",
                "content": (
                    f"<ROLE>{role}</ROLE>\n"
                    "STATE:\n"
                    + json.dumps(
                        state,
                        ensure_ascii=False,
                        indent=2,
                    )
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    answer,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
    })


# ------------------------------------------------------
# A. ANALYSIS / deterministic tool routing: 8
# benchmark와 다른 숫자 사용
# ------------------------------------------------------

analysis_cases = [
    (30,  {"X": 30, "Y": 29, "Z": 30}),
    (50,  {"X": 48, "Y": 50, "Z": 50}),
    (70,  {"X": 70, "Y": 70, "Z": 68}),
    (80,  {"X": 79, "Y": 78, "Z": 80}),
    (100, {"X": 100, "Y": 100, "Z": 100}),
    (120, {"X": 115, "Y": 120, "Z": 118}),
    (150, {"X": 150, "Y": 149, "Z": 150}),
    (180, {"X": 177, "Y": 180, "Z": 176}),
]

for required, actual in analysis_cases:
    add(
        "ANALYSIS",
        {
            "task": "CHECK_AXIS_DURATION",
            "requirement_s": required,
            "actual_by_axis": actual,
        },
        {
            "action": "CALL_TOOL",
            "tool": "compare_axis_durations",
            "arguments": {
                "required_s": required,
                "actual_by_axis": actual,
            },
        },
    )


# ------------------------------------------------------
# B. Requirement / Procedure conflict: 8
# ------------------------------------------------------

conflicts = [
    ("120 s/axis", "90 s/axis", "Rev.6", "Rev.5"),
    ("30 s/axis",  "20 s/axis", "Rev.2", "Rev.1"),
    ("75 s/axis",  "60 s/axis", "Rev.8", "Rev.7"),
    ("100 s/axis", "80 s/axis", "Rev.D", "Rev.C"),
    ("45 s/axis",  "35 s/axis", "Rev.12", "Rev.11"),
    ("150 s/axis", "120 s/axis", "Rev.F", "Rev.E"),
    ("20 s/axis",  "15 s/axis", "Rev.9", "Rev.8"),
    ("180 s/axis", "150 s/axis", "Rev.3", "Rev.2"),
]

for req, proc, req_rev, proc_rev in conflicts:
    add(
        "EVIDENCE",
        {
            "requirement": req,
            "requirement_revision": req_rev,
            "procedure": proc,
            "procedure_revision": proc_rev,
        },
        {
            "action": "PROPOSE_FINDING",
            "finding_type": "PROCEDURE_REQUIREMENT_CONFLICT",
        },
    )


# ------------------------------------------------------
# C. Missing As-run evidence: 8
# ------------------------------------------------------

for i, req in enumerate(
    [
        "30 s/axis",
        "50 s/axis",
        "70 s/axis",
        "80 s/axis",
        "100 s/axis",
        "120 s/axis",
        "150 s/axis",
        "180 s/axis",
    ],
    start=1,
):
    add(
        "EVIDENCE",
        {
            "requirement_id": f"REQ-MISS-{i:02d}",
            "requirement": req,
            "as_run": None,
            "report_status": "AVAILABLE",
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "AS_RUN_MISSING",
        },
    )


# ------------------------------------------------------
# D. Configuration / Revision mismatch: 8
# ------------------------------------------------------

config_pairs = [
    ("Antenna QM Rev.D", "Antenna QM Rev.C"),
    ("EPS EM Rev.5", "EPS EM Rev.4"),
    ("OBC FM Rev.H", "OBC FM Rev.G"),
    ("Bracket PFM Rev.7", "Bracket PFM Rev.6"),
]

for current, evidence in config_pairs:
    add(
        "EVIDENCE",
        {
            "current_configuration": current,
            "evidence_configuration": evidence,
            "applicability_evidence": None,
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "CONFIGURATION_MISMATCH",
        },
    )


revision_pairs = [
    ("Rev.8", "Rev.7"),
    ("Rev.F", "Rev.E"),
    ("Rev.12", "Rev.10"),
    ("Rev.21", "Rev.20"),
]

for current, evidence in revision_pairs:
    add(
        "EVIDENCE",
        {
            "current_requirement_revision": current,
            "evidence_requirement_revision": evidence,
            "supersession_review": None,
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "REVISION_MISMATCH",
        },
    )


# ------------------------------------------------------
# E. Critic / Scope & contradiction: 10
# ------------------------------------------------------

critic_scope = [
    (["X", "Y", "Z"], ["X"]),
    (["X", "Y", "Z"], ["Y"]),
    (["X", "Y", "Z"], ["X", "Z"]),
    (["X", "Y"], ["Y"]),
    (["Y", "Z"], ["Z"]),
]

for claimed, valid in critic_scope:
    add(
        "CRITIC",
        {
            "finding": {
                "statement": "All claimed axes fail duration requirement",
                "scope": claimed,
            },
            "tool_result": {
                "verdict": "NON_COMPLIANT",
                "affected_axes": valid,
            },
        },
        {
            "action": "CHALLENGE",
            "reason": "SCOPE_ERROR",
            "valid_scope": valid,
        },
    )


contradictions = [
    ["X"],
    ["Y"],
    ["Z"],
    ["X", "Y"],
    ["Y", "Z"],
]

for affected in contradictions:
    add(
        "CRITIC",
        {
            "finding": {
                "statement": "Duration requirement satisfied",
                "scope": ["X", "Y", "Z"],
            },
            "tool_result": {
                "verdict": "NON_COMPLIANT",
                "affected_axes": affected,
            },
        },
        {
            "action": "CHALLENGE",
            "reason": "EVIDENCE_CONTRADICTION",
            "valid_scope": affected,
        },
    )


# ------------------------------------------------------
# F. Critic / Configuration applicability: 8
# ------------------------------------------------------

critic_configs = [
    ("Thermal Unit Rev.4", "Thermal Unit Rev.3"),
    ("RF Module Rev.G", "RF Module Rev.F"),
    ("Deployable Rev.11", "Deployable Rev.10"),
    ("Camera QM Rev.B", "Camera QM Rev.A"),
    ("Harness FM Rev.8", "Harness FM Rev.7"),
    ("Panel EM Rev.E", "Panel EM Rev.D"),
    ("Sensor PFM Rev.6", "Sensor PFM Rev.5"),
    ("Controller Rev.14", "Controller Rev.13"),
]

for current, evidence in critic_configs:
    add(
        "CRITIC",
        {
            "finding": {
                "statement": (
                    f"{evidence} evidence proves "
                    f"{current} configuration"
                ),
                "scope": "FULL_CONFIGURATION",
            },
            "current_configuration": current,
            "evidence_configuration": evidence,
            "applicability_evidence": None,
        },
        {
            "action": "CHALLENGE",
            "reason": "CONFIGURATION_MISMATCH",
        },
    )


assert len(rows) == 50, len(rows)

OUT.parent.mkdir(parents=True, exist_ok=True)

with OUT.open("w", encoding="utf-8") as f:
    for row in rows:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )

print("Saved:", OUT)
print("Total:", len(rows))

role_counts = {}
for row in rows:
    role = row["messages"][1]["content"].split(
        "<ROLE>"
    )[1].split("</ROLE>")[0]

    role_counts[role] = role_counts.get(role, 0) + 1

print("Role counts:", role_counts)
