from .prompts_legacy import SYSTEM_COMMON as LEGACY_COMMON
import json
POLICY_VERSION="physics-review-v0.2"
SCHEMA_VERSION="physics-review-action-v0.2"
EXTRA={'MONITORING_COVERAGE_INSUFFICIENT': 'The available acquisition does not cover the observable required for this review.', 'EXPOSURE_METADATA_UNRESOLVED': 'The run is missing exposure or electrical-configuration metadata needed to interpret its observations.', 'EVIDENCE_INTERPRETATION_ERROR': 'The proposal conflicts with the supplied observation or the interpretation method stated in the reference.'}
SYSTEM_COMMON=LEGACY_COMMON+"\nAdditional reason codes:\n"+"\n".join("- "+k+": "+v for k,v in EXTRA.items())
SYSTEM={r:SYSTEM_COMMON+"\nActive role: "+r for r in ("EVIDENCE","CRITIC")}
def build_messages(role, packet, answer=None):
    out=[{"role":"system","content":SYSTEM[role]}, {"role":"user","content":json.dumps(packet,ensure_ascii=False,indent=2)}]
    if answer is not None:out.append({"role":"assistant","content":json.dumps(answer,ensure_ascii=False,separators=(",",":"))})
    return out
