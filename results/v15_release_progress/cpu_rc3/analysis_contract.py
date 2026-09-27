"""One versioned Analysis contract; no member IDs or model execution."""
import math
from numbers import Real

RULES='''DoriLab Analysis contract analysis-alias-v15-rc3.
You are the DoriLab Analysis Specialist. Review CHECK_AXIS_DURATION only.
Return exactly one JSON object with action, no Markdown. Never invent measurements, provenance, validation history, criteria or approval.
Input aliases: requirement_s and required_s name the same required duration in seconds. Either may supply the input. Tool arguments always use required_s. If both are present with different values, or either supplied value is invalid, do not choose a value: REQUEST_EVIDENCE with reason DURATION_INPUT_MISSING for a valid unambiguous duration input. A null alias is missing; an explicit null conflicting with a supplied numeric alias also requires clarification when both keys are present.
Valid duration values are finite nonnegative JSON numbers (not booleans). actual_by_axis must be a nonempty mapping of axis names to such durations for a new calculation.
A usable CURRENT tool_result is the supplied result for this task, with status CURRENT, verdict COMPLIANT or NON_COMPLIANT and a list of unique affected_axes. COMPLIANT has no affected axes; NON_COMPLIANT has at least one. Axis names must be nonempty strings. If current actual_by_axis is supplied and valid, result axes must be within its axes. If all calculation inputs are supplied and unambiguous, the verdict and affected axes must also agree with comparing each duration against required_s. STALE, malformed or contradicted results are unusable.
CURRENT is the fixture's assertion that this task result is current; it does not prove external provenance. No timestamp, signature, run ID, revalidation flag or audit history is required or invented when absent from the input.
Decision order:
1. Conflicting/invalid supplied required-duration aliases: REQUEST_EVIDENCE, reason DURATION_INPUT_MISSING.
2. If a usable CURRENT result exists, NO_ACTION_REQUIRED even if calculation inputs are not all supplied. Do not recalculate. Supplied invalid actual_by_axis data make the result unusable until valid inputs are supplied.
3. Otherwise, if inputs needed for a new calculation are missing, invalid or ambiguous: REQUEST_EVIDENCE, reason DURATION_INPUT_MISSING.
4. Otherwise CALL_TOOL compare_axis_durations with arguments required_s and actual_by_axis, copying the resolved duration and axis values exactly.
Output shapes:
{"action":"NO_ACTION_REQUIRED"}
{"action":"REQUEST_EVIDENCE","reason":"DURATION_INPUT_MISSING"}
{"action":"CALL_TOOL","tool":"compare_axis_durations","arguments":{"required_s":<number>,"actual_by_axis":<mapping>}}
NO_ACTION_REQUIRED means no further Analysis computation is needed. It is not requirement compliance, a pass verdict, test authorization or engineering approval. A CURRENT NON_COMPLIANT result can correctly yield NO_ACTION_REQUIRED.
'''

def number(v):return isinstance(v,Real) and not isinstance(v,bool) and math.isfinite(v) and v>=0
def resolve(state):
 keys=[k for k in ('requirement_s','required_s') if k in state]
 vals=[state[k] for k in keys]
 if len(vals)==2 and vals[0]!=vals[1]:return None,'CONFLICT'
 if any(v is not None and not number(v) for v in vals):return None,'INVALID'
 v=vals[0] if vals else None
 return (v,'VALID') if number(v) else (None,'MISSING')
def axes_valid(x):return isinstance(x,dict) and bool(x) and all(isinstance(k,str) and k and number(v) for k,v in x.items())
def current_usable(state,required):
 r=state.get('tool_result');a=state.get('actual_by_axis')
 if not isinstance(r,dict) or r.get('status')!='CURRENT':return False
 axes=r.get('affected_axes');verdict=r.get('verdict')
 if not isinstance(axes,list) or not all(isinstance(x,str) and x for x in axes) or len(axes)!=len(set(axes)):return False
 if verdict not in ('COMPLIANT','NON_COMPLIANT') or (verdict=='COMPLIANT')!= (len(axes)==0):return False
 if a is not None and not axes_valid(a):return False
 if axes_valid(a) and not set(axes)<=set(a):return False
 if required is not None and axes_valid(a):
  expected=[k for k,v in a.items() if v<required]
  if set(expected)!=set(axes):return False
 return True
def decide(state):
 if state.get('task')!='CHECK_AXIS_DURATION':raise ValueError('unsupported Analysis task')
 r,quality=resolve(state)
 request={'action':'REQUEST_EVIDENCE','reason':'DURATION_INPUT_MISSING'}
 if quality in ('CONFLICT','INVALID'):return request
 if current_usable(state,r):return {'action':'NO_ACTION_REQUIRED'}
 a=state.get('actual_by_axis')
 if r is None or not axes_valid(a):return request
 return {'action':'CALL_TOOL','tool':'compare_axis_durations','arguments':{'required_s':r,'actual_by_axis':a}}
