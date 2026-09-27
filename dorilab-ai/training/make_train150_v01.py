import json
import hashlib
from pathlib import Path
from collections import Counter

OUT = Path("data/train150_v01.jsonl")
MANIFEST = Path("data/train150_v01_manifest.json")

if OUT.exists() or MANIFEST.exists():
    raise SystemExit(
        "train150_v01 already exists. "
        "Rename/remove it explicitly if regeneration is intended."
    )

COMMON = """
You operate under the DoriLab engineering execution contract.

Core rules:

1. Do not invent engineering criteria, tolerance or approval.
2. Missing evidence is not equivalent to pass or failure.
3. CURRENT evidence takes precedence over SUPERSEDED evidence.
4. Configuration or revision mismatch requires applicability evidence.
5. Approved applicability is valid only for explicitly approved scopes.
6. Findings must match the exact scope supported by evidence.
7. Return exactly one JSON object.
8. The root decision key is always "action", never "status".
9. Do not use markdown.
""".strip()


SYSTEM = {

    "ANALYSIS": f"""
You are the DoriLab Analysis Specialist.

{COMMON}

Available deterministic tool:

compare_axis_durations

Arguments:
- required_s
- actual_by_axis

Rules for CHECK_AXIS_DURATION:

- If required_s or actual_by_axis is missing:
  REQUEST_EVIDENCE with reason DURATION_INPUT_MISSING.

- If a CURRENT valid tool_result is already present:
  NO_ACTION_REQUIRED.

- A tool_result with status STALE is not current evidence.

- Otherwise call compare_axis_durations and copy the
  required_s and actual_by_axis values exactly.

Allowed actions:

CALL_TOOL
REQUEST_EVIDENCE
NO_ACTION_REQUIRED
""".strip(),

    "EVIDENCE": f"""
You are the DoriLab Evidence Specialist.

{COMMON}

Allowed actions:

PROPOSE_FINDING
REQUEST_EVIDENCE
NO_ACTION_REQUIRED

Finding type:

PROCEDURE_REQUIREMENT_CONFLICT

REQUEST_EVIDENCE reasons:

CONFIGURATION_MISMATCH
REVISION_MISMATCH
AS_RUN_MISSING

Rules:

- Compare CURRENT requirement and CURRENT procedure.
- Requirement-document revision and procedure-document revision
  do NOT need to have the same revision number.
- REVISION_MISMATCH applies to current-vs-evidence revision
  of the same requirement/evidence lineage.
- Ignore SUPERSEDED procedure values for a current conflict.
- Different current requirement/procedure values produce
  PROCEDURE_REQUIREMENT_CONFLICT.
- Missing as_run requires AS_RUN_MISSING.
- Different configurations require CONFIGURATION_MISMATCH
  unless an APPROVED_EQUIVALENT applicability review covers
  the exact claim_scope.
- Different requirement revisions require REVISION_MISMATCH
  unless an APPROVED_APPLICABLE supersession review covers
  the exact claim_scope.
""".strip(),

    "CRITIC": f"""
You are the DoriLab Critic.

{COMMON}

Allowed actions:

CHALLENGE
REQUEST_EVIDENCE
NO_ACTION_REQUIRED

CHALLENGE reasons:

SCOPE_ERROR
EVIDENCE_CONTRADICTION
CONFIGURATION_MISMATCH

REQUEST_EVIDENCE reason:

SUPPORTING_EVIDENCE_MISSING

Rules:

- If supporting evidence/tool result is absent for a factual claim,
  REQUEST_EVIDENCE.

- If finding scope differs from deterministic affected_axes,
  CHALLENGE with SCOPE_ERROR and valid_scope equal to affected_axes.

- If a finding says compliant/satisfied but current deterministic
  evidence is NON_COMPLIANT, use EVIDENCE_CONTRADICTION.

- If a finding claims a configuration is supported by different
  configuration evidence, CHALLENGE unless approved applicability
  covers the exact claim scope.

- Ignore SUPERSEDED evidence when CURRENT evidence resolves the issue.

- If the finding is already supported exactly, NO_ACTION_REQUIRED.
""".strip(),
}


rows = []


def add(case_id, role, state, answer):
    rows.append({
        "id": case_id,
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
        ],
    })


# ============================================================
# ANALYSIS 30
# 10 CALL_TOOL / 10 REQUEST_EVIDENCE / 10 NO_ACTION_REQUIRED
# ============================================================

analysis_sets = [
    (35, {"X":35, "Y":34, "Z":35}),
    (50, {"X":50, "Y":50, "Z":49}),
    (65, {"X":64, "Y":65, "Z":65}),
    (75, {"X":75, "Y":74, "Z":73}),
    (85, {"X":85, "Y":85, "Z":85}),
    (95, {"ROLL":95, "PITCH":92, "YAW":95}),
    (105, {"A":105, "B":103, "C":105}),
    (125, {"X":121, "Y":125, "Z":125}),
    (140, {"ROLL":140, "PITCH":140, "YAW":138}),
    (165, {"A":165, "B":164, "C":163}),
]

for i, (req, actual) in enumerate(analysis_sets, 1):

    state = {
        "task": "CHECK_AXIS_DURATION",
        "requirement_s": req,
        "actual_by_axis": actual,
        "tool_result": None,
    }

    if i in (4, 8):
        state["tool_result"] = {
            "status": "STALE",
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["OLD"],
        }

    add(
        f"TR-AN-CALL-{i:02d}",
        "ANALYSIS",
        state,
        {
            "action": "CALL_TOOL",
            "tool": "compare_axis_durations",
            "arguments": {
                "required_s": req,
                "actual_by_axis": actual,
            },
        },
    )


for i in range(10):

    if i % 2 == 0:
        state = {
            "task": "CHECK_AXIS_DURATION",
            "requirement_s": None,
            "actual_by_axis": {
                "X": 45 + i,
                "Y": 45 + i,
                "Z": 45 + i,
            },
            "tool_result": None,
        }
    else:
        state = {
            "task": "CHECK_AXIS_DURATION",
            "requirement_s": 50 + i,
            "actual_by_axis": None,
            "tool_result": None,
        }

    if i in (3, 7):
        state["tool_result"] = {
            "status": "STALE",
            "verdict": "NON_COMPLIANT",
            "affected_axes": ["Z"],
        }

    add(
        f"TR-AN-MISS-{i+1:02d}",
        "ANALYSIS",
        state,
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "DURATION_INPUT_MISSING",
        },
    )


for i in range(10):

    req = 60 + i * 7

    actual = {
        "X": req,
        "Y": req if i % 2 == 0 else req - 1,
        "Z": req,
    }

    affected = [] if i % 2 == 0 else ["Y"]

    add(
        f"TR-AN-DONE-{i+1:02d}",
        "ANALYSIS",
        {
            "task": "CHECK_AXIS_DURATION",
            "requirement_s": req,
            "actual_by_axis": actual,
            "tool_result": {
                "status": "CURRENT",
                "verdict": (
                    "COMPLIANT"
                    if not affected
                    else "NON_COMPLIANT"
                ),
                "affected_axes": affected,
            },
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# ============================================================
# EVIDENCE 60
# 15 FINDING / 15 REQUEST / 30 NO_ACTION
# ============================================================

for i in range(15):

    req = 70 + i * 5
    proc = req - (5 + i % 3)

    state = {
        "current_requirement": {
            "revision": f"ReqRev.{10+i}",
            "duration": f"{req} s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": f"ProcRev.{20+i}",
            "duration": f"{proc} s/axis",
            "status": "CURRENT",
        },
    }

    if i % 3 == 0:
        state["old_procedure"] = {
            "revision": f"ProcRev.{i}",
            "duration": f"{proc-10} s/axis",
            "status": "SUPERSEDED",
        }

    add(
        f"TR-EV-CONFLICT-{i+1:02d}",
        "EVIDENCE",
        state,
        {
            "action": "PROPOSE_FINDING",
            "finding_type": "PROCEDURE_REQUIREMENT_CONFLICT",
        },
    )


# Missing As-run: 5
for i in range(5):
    add(
        f"TR-EV-ASRUN-{i+1:02d}",
        "EVIDENCE",
        {
            "requirement": f"{80+i*10} s/axis",
            "as_run": None,
            "current_configuration":
                f"TestArticle FM Rev.{i+2}",
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "AS_RUN_MISSING",
        },
    )


# Configuration mismatch: 5
for i in range(5):

    scope = [
        "VIBRATION",
        "THERMAL",
        "STATIC_LOAD",
        "EMC",
        "DEPLOYMENT",
    ][i]

    review = None

    # wrong-scope approval is still mismatch
    if i in (2, 4):
        review = {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["OTHER_SCOPE"],
        }

    add(
        f"TR-EV-CFGMISS-{i+1:02d}",
        "EVIDENCE",
        {
            "current_configuration":
                f"Unit FM Rev.{10+i}",
            "evidence_configuration":
                f"Unit FM Rev.{9+i}",
            "claim_scope": scope,
            "applicability_review": review,
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "CONFIGURATION_MISMATCH",
        },
    )


# Requirement revision mismatch: 5
for i in range(5):

    scope = [
        "DURATION",
        "THERMAL_SURVIVAL",
        "VIBRATION",
        "FUNCTIONAL",
        "POWER",
    ][i]

    review = None

    if i in (1, 3):
        review = {
            "status": "APPROVED_APPLICABLE",
            "approved_scopes": ["OTHER_SCOPE"],
        }

    add(
        f"TR-EV-REVMISS-{i+1:02d}",
        "EVIDENCE",
        {
            "current_requirement_revision":
                f"Rev.{30+i}",
            "evidence_requirement_revision":
                f"Rev.{29+i}",
            "claim_scope": scope,
            "supersession_review": review,
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "REVISION_MISMATCH",
        },
    )


# NO_ACTION: current req/procedure match: 10
for i in range(10):

    duration = 45 + i * 5

    state = {
        "current_requirement": {
            "revision": f"REQ-{50+i}",
            "duration": f"{duration} s/axis",
            "status": "CURRENT",
        },
        "current_procedure": {
            "revision": f"PROC-{80+i}",
            "duration": f"{duration} s/axis",
            "status": "CURRENT",
        },
    }

    if i % 2 == 0:
        state["old_procedure"] = {
            "revision": f"PROC-OLD-{i}",
            "duration": f"{duration-15} s/axis",
            "status": "SUPERSEDED",
        }

    add(
        f"TR-EV-MATCH-{i+1:02d}",
        "EVIDENCE",
        state,
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# NO_ACTION: configuration applicable: 10
scopes = [
    "THERMAL",
    "VIBRATION",
    "STATIC_LOAD",
    "EMC",
    "DEPLOYMENT",
]

for i in range(10):

    scope = scopes[i % len(scopes)]

    if i < 5:
        current = f"Panel Rev.{20+i}"
        evidence = f"Panel Rev.{19+i}"

        review = {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": [scope],
        }
    else:
        current = f"Panel Rev.{20+i}"
        evidence = current
        review = None

    add(
        f"TR-EV-CFGOK-{i+1:02d}",
        "EVIDENCE",
        {
            "current_configuration": current,
            "evidence_configuration": evidence,
            "claim_scope": scope,
            "applicability_review": review,
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# NO_ACTION: requirement revision applicable: 10
rev_scopes = [
    "DURATION",
    "THERMAL_SURVIVAL",
    "FUNCTIONAL",
    "POWER",
    "VIBRATION",
]

for i in range(10):

    scope = rev_scopes[i % len(rev_scopes)]

    if i < 5:
        current = f"Rev.{60+i}"
        evidence = f"Rev.{59+i}"

        review = {
            "status": "APPROVED_APPLICABLE",
            "approved_scopes": [scope],
        }
    else:
        current = f"Rev.{60+i}"
        evidence = current
        review = None

    add(
        f"TR-EV-REVOK-{i+1:02d}",
        "EVIDENCE",
        {
            "current_requirement_revision": current,
            "evidence_requirement_revision": evidence,
            "claim_scope": scope,
            "supersession_review": review,
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# ============================================================
# CRITIC 60
# 25 CHALLENGE / 25 NO_ACTION / 10 REQUEST_EVIDENCE
# ============================================================

# CHALLENGE / SCOPE_ERROR: 10
scope_pairs = [
    (["X","Y","Z"], ["X"]),
    (["X","Y","Z"], ["Y"]),
    (["X","Y","Z"], ["Z"]),
    (["X","Y"], ["X"]),
    (["X","Z"], ["Z"]),
    (["Y","Z"], ["Y"]),
    (["ROLL","PITCH","YAW"], ["PITCH"]),
    (["A","B","C"], ["A","C"]),
    (["X","Y","Z"], ["X","Y"]),
    (["ROLL","YAW"], ["YAW"]),
]

for i, (claimed, affected) in enumerate(scope_pairs, 1):

    add(
        f"TR-CR-SCOPE-{i:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Claimed axes fail duration requirement",
                "scope": claimed,
            },
            "tool_result": {
                "status": "CURRENT",
                "verdict": "NON_COMPLIANT",
                "affected_axes": affected,
            },
        },
        {
            "action": "CHALLENGE",
            "reason": "SCOPE_ERROR",
            "valid_scope": affected,
        },
    )


# CHALLENGE / EVIDENCE_CONTRADICTION: 8
affected_sets = [
    ["X"],
    ["Y"],
    ["Z"],
    ["X","Z"],
    ["X","Y"],
    ["Y","Z"],
    ["PITCH"],
    ["A","C"],
]

for i, affected in enumerate(affected_sets, 1):

    all_scope = (
        ["ROLL","PITCH","YAW"]
        if "PITCH" in affected
        else (
            ["A","B","C"]
            if "A" in affected
            else ["X","Y","Z"]
        )
    )

    add(
        f"TR-CR-CONTRA-{i:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Duration requirement satisfied",
                "scope": all_scope,
            },
            "tool_result": {
                "status": "CURRENT",
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


# CHALLENGE / CONFIGURATION_MISMATCH: 7
crit_scopes = [
    "VIBRATION",
    "THERMAL",
    "STATIC_LOAD",
    "EMC",
    "DEPLOYMENT",
    "FUNCTIONAL",
    "POWER",
]

for i, scope in enumerate(crit_scopes, 1):

    review = None

    if i in (3, 6):
        review = {
            "status": "APPROVED_EQUIVALENT",
            "approved_scopes": ["OTHER_SCOPE"],
        }

    add(
        f"TR-CR-CFG-{i:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Previous configuration evidence proves current claim",
                "scope": scope,
            },
            "current_configuration":
                f"Module Rev.{40+i}",
            "evidence_configuration":
                f"Module Rev.{39+i}",
            "applicability_review": review,
        },
        {
            "action": "CHALLENGE",
            "reason": "CONFIGURATION_MISMATCH",
        },
    )


# NO_ACTION: exact tool-result scope: 10
valid_sets = [
    ["X"],
    ["Y"],
    ["Z"],
    ["X","Z"],
    ["X","Y"],
    ["Y","Z"],
    ["PITCH"],
    ["ROLL"],
    ["A","C"],
    ["B"],
]

for i, affected in enumerate(valid_sets, 1):

    add(
        f"TR-CR-OKSCOPE-{i:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Finding matches deterministic affected scope",
                "scope": affected,
            },
            "tool_result": {
                "status": "CURRENT",
                "verdict": "NON_COMPLIANT",
                "affected_axes": affected,
            },
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# NO_ACTION: approved exact configuration scope: 8
for i in range(8):

    scope = crit_scopes[i % len(crit_scopes)]

    add(
        f"TR-CR-OKCFG-{i+1:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Previous configuration evidence supports current claim",
                "scope": scope,
            },
            "current_configuration":
                f"Assembly Rev.{70+i}",
            "evidence_configuration":
                f"Assembly Rev.{69+i}",
            "applicability_review": {
                "status": "APPROVED_EQUIVALENT",
                "approved_scopes": [scope],
            },
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# NO_ACTION: valid procedure conflict: 7
for i in range(7):

    req = 80 + i * 10
    proc = req - 10

    add(
        f"TR-CR-OKCONFLICT-{i+1:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Procedure conflicts with requirement",
                "scope": "DURATION",
            },
            "evidence": {
                "current_requirement": {
                    "duration": f"{req} s/axis",
                    "status": "CURRENT",
                },
                "current_procedure": {
                    "duration": f"{proc} s/axis",
                    "status": "CURRENT",
                },
            },
        },
        {
            "action": "NO_ACTION_REQUIRED",
        },
    )


# REQUEST_EVIDENCE: 10
for i in range(10):

    add(
        f"TR-CR-MISSING-{i+1:02d}",
        "CRITIC",
        {
            "finding": {
                "statement":
                    "Duration requirement satisfied",
                "scope": ["X","Y","Z"],
            },
            "tool_result": None,
            "evidence": None,
            "case_marker": f"MISSING-{i+1}",
        },
        {
            "action": "REQUEST_EVIDENCE",
            "reason": "SUPPORTING_EVIDENCE_MISSING",
        },
    )


assert len(rows) == 150, len(rows)


# ------------------------------------------------------------
# Exact leakage check against eval40
# ------------------------------------------------------------

eval_inputs_path = Path("eval/eval40_inputs_v1.jsonl")
eval_gold_path = Path("eval/eval40_gold_v1.jsonl")

if eval_inputs_path.exists() and eval_gold_path.exists():

    eval_inputs = {}

    with eval_inputs_path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            x = json.loads(line)
            eval_inputs[x["id"]] = x

    eval_gold = {}

    with eval_gold_path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            x = json.loads(line)
            eval_gold[x["id"]] = x["expected"]

    eval_fingerprints = set()

    for case_id, x in eval_inputs.items():

        fp = json.dumps(
            {
                "role": x["role"],
                "input": x["input"],
                "expected": eval_gold[case_id],
            },
            sort_keys=True,
            ensure_ascii=False,
        )

        eval_fingerprints.add(fp)

    for row in rows:

        user_content = row["messages"][1]["content"]

        state_text = user_content.split(
            "STATE:\n",
            1,
        )[1]

        state = json.loads(state_text)

        role = user_content.split(
            "<ROLE>",
            1,
        )[1].split(
            "</ROLE>",
            1,
        )[0]

        expected = json.loads(
            row["messages"][2]["content"]
        )

        fp = json.dumps(
            {
                "role": role,
                "input": state,
                "expected": expected,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

        assert fp not in eval_fingerprints, (
            "Exact train/eval duplicate found: "
            + row["id"]
        )


OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with OUT.open(
    "w",
    encoding="utf-8",
) as f:

    for row in rows:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


role_counts = Counter()
action_counts = Counter()
role_action = Counter()

for row in rows:

    role = row["messages"][1]["content"].split(
        "<ROLE>",
        1,
    )[1].split(
        "</ROLE>",
        1,
    )[0]

    action = json.loads(
        row["messages"][2]["content"]
    )["action"]

    role_counts[role] += 1
    action_counts[action] += 1
    role_action[(role, action)] += 1


manifest = {
    "version": "train150-v0.1",
    "total": len(rows),
    "sha256": sha256(OUT),
    "role_counts": dict(role_counts),
    "action_counts": dict(action_counts),
    "role_action_counts": {
        f"{r}/{a}": n
        for (r, a), n in sorted(
            role_action.items()
        )
    },
    "exact_eval_leakage": 0,
}


MANIFEST.write_text(
    json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print("Created:", OUT)
print("Manifest:", MANIFEST)
print()
print(
    json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    )
)
