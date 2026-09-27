"""Strict offline scores; inference never receives case gold fields."""
from __future__ import annotations
from collections import defaultdict
from .common import require, strict_json, canon

ORDERLESS = {'evidence_refs','requested_evidence','valid_scope','affected_axes','axes'}

def matches(expected, actual):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and field_equal(k,v,actual[k]) for k,v in expected.items())
    return type(expected) is type(actual) and expected==actual

def field_equal(key, expected, actual):
    if isinstance(expected,list):
        if not isinstance(actual,list): return False
        if key in ORDERLESS:
            return len(actual)==len(expected) and sorted(map(canon,actual))==sorted(map(canon,expected))
        return expected==actual
    if isinstance(expected,dict): return matches(expected,actual)
    # bool must not compare equal to 1. Numbers may be represented as 1 vs 1.0.
    if isinstance(expected,bool) or isinstance(actual,bool): return type(expected) is type(actual) and expected==actual
    return expected==actual

def score(item, raw, schema, hit_limit=False):
    import jsonschema
    parsed=None; error=None; valid=False
    try:
        parsed=strict_json(raw)
        require(isinstance(parsed,dict),'Output must be one JSON object')
        require(not hit_limit,'Generation budget reached without termination')
        if item['suite']=='contract20':
            # Legacy runner parity is verified on historical output during import.
            require(isinstance(parsed.get('action'),str),'Missing action')
        else:
            c=item['case']; packet=c['packet']
            jsonschema.Draft202012Validator(schema).validate(parsed)
            require(parsed['claim_id']==packet['claim_id'],'claim_id mismatch')
            refs=parsed.get('evidence_refs')
            require(isinstance(refs,list) and all(isinstance(x,str) for x in refs),'evidence_refs must be string list')
            require(len(refs)==len(set(refs)),'Duplicate evidence_refs')
            allowed={r['reference_id'] for r in packet['reference_context']} | {r['evidence_id'] for r in packet['case_packet']['evidence']}
            require(set(refs)<=allowed,'unprovided evidence reference')
            req=parsed.get('requested_evidence',[])
            require(isinstance(req,list) and all(isinstance(x,str) for x in req),'requested_evidence must be string list')
            require(len(req)==len(set(req)),'Duplicate request IDs')
            require(set(req)<=set(packet.get('allowed_request_ids',[])),'unprovided request id')
        valid=True
    except Exception as ex:
        error={'type':type(ex).__name__,'message':getattr(ex,'message',str(ex))}
    c=item['case']; expected=c['expected']; alternatives=c.get('acceptable_answers') or [expected]
    action=isinstance(parsed,dict) and parsed.get('action')==expected['action']
    reason_cases='reason' in expected
    ref_exact=None
    if item['suite']!='contract20':
        refs=parsed.get('evidence_refs') if isinstance(parsed,dict) else None
        ref_exact=bool(isinstance(refs,list) and all(isinstance(x,str) for x in refs) and
            len(refs)==len(set(refs)) and any(set(refs)==set(e['evidence_refs']) for e in alternatives))
    full=bool(valid and any(matches(e,parsed) for e in alternatives) and (ref_exact is not False))
    return {'action_correct':bool(action),'schema_and_refs_valid':valid,
            'reference_exact':ref_exact,'strict_contract_pass':full,
            'reason_applicable':reason_cases,
            'reason_joint_correct':bool(reason_cases and action and parsed.get('reason')==expected['reason']),
            'wrongly_accepts_refuted_proposal':bool(expected['action']=='CHALLENGE' and isinstance(parsed,dict) and parsed.get('action')=='NO_ACTION_REQUIRED'),
            'unnecessary_intervention':bool(expected['action']=='NO_ACTION_REQUIRED' and isinstance(parsed,dict) and parsed.get('action') not in (None,'NO_ACTION_REQUIRED')),
            'parsed':parsed,'expected':expected,'validation_error':error,
            'contract_schema_note':'Legacy answer-field comparison, not Physics JSON Schema' if item['suite']=='contract20' else None}

def aggregate(rows):
    result={'cases':len(rows)}
    for key in ('action_correct','schema_and_refs_valid','strict_contract_pass','wrongly_accepts_refuted_proposal','unnecessary_intervention'):
        result[key]=sum(r['score'][key] is True for r in rows)
    result['reference_exact']=sum(r['score']['reference_exact'] is True for r in rows)
    result['reference_eligible']=sum(r['score']['reference_exact'] is not None for r in rows)
    result['reason_joint_correct']=sum(r['score']['reason_joint_correct'] for r in rows)
    result['reason_cases']=sum(r['score']['reason_applicable'] for r in rows)
    groups=defaultdict(list)
    for r in rows:
        if r.get('pair_id'):groups[r['pair_id']].append(r)
    pairs=[g for g in groups.values() if len(g)==2]
    result['complete_pairs']=len(pairs)
    result['both_pair_states_pass']=sum(all(x['score']['strict_contract_pass'] for x in g) for g in pairs)
    result['generation_seconds']=sum(r.get('generation_seconds',0) for r in rows)
    return result
