"""Score only sealed raw outputs against the pre-output frozen plan; no repair."""
import math
from run_common import *
sys.path.insert(0,str(ROOT/'experiments/source_review_policy_v15/pilot_rc1'))
from reference_contract import matches_sufficient_set
def unique_strings(x):return isinstance(x,list) and bool(x) and all(isinstance(v,str) for v in x) and len(x)==len(set(x))
def parse(text):
    def pairs(ps):
        out={}
        for k,v in ps:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    try:
        x=json.loads(text,object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
        return x if isinstance(x,dict) else None
    except (ValueError,TypeError):return None
def contract(pred,inp):
    if not isinstance(pred,dict):return False
    route=inp['contract_route'];a=pred.get('action');system=inp['messages'][0]['content']
    if not isinstance(a,str) or a not in system:return False
    fields={'action'}
    if route in ('legacy_physics','v15_rc1'):
        if a not in ['CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED']:return False
        fields|={'claim_id','evidence_refs'}
        u=json.loads(inp['messages'][1]['content']);p=u['case_packet'] if route=='legacy_physics' else u['packet']
        claim=u['claim_id'] if route=='legacy_physics' else p['claim_id']
        refs={x['reference_id'] for x in u['reference_context']}|{x['evidence_id'] for x in p['evidence' if route=='legacy_physics' else 'observations']}
        if pred.get('claim_id')!=claim or not unique_strings(pred.get('evidence_refs')) or not set(pred['evidence_refs'])<=refs:return False
        if a!='NO_ACTION_REQUIRED':
            fields.add('reason')
            if not isinstance(pred.get('reason'),str) or pred['reason'] not in system:return False
        if a=='REQUEST_EVIDENCE':
            fields.add('requested_evidence');allowed=u['allowed_request_ids'] if route=='legacy_physics' else [x['request_id'] for x in p['request_catalog']]
            if not unique_strings(pred.get('requested_evidence')) or not set(pred['requested_evidence'])<=set(allowed):return False
    elif route=='analysis_alias_rc3':
        if a=='REQUEST_EVIDENCE':
            fields.add('reason')
            if pred.get('reason')!='DURATION_INPUT_MISSING':return False
        elif a=='CALL_TOOL':
            fields|={'tool','arguments'};args=pred.get('arguments')
            if pred.get('tool')!='compare_axis_durations' or not isinstance(args,dict) or set(args)!={'required_s','actual_by_axis'}:return False
            def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0
            if not number(args['required_s']) or not isinstance(args['actual_by_axis'],dict) or not args['actual_by_axis']:return False
            if not all(isinstance(k,str) and bool(k.strip()) and number(v) for k,v in args['actual_by_axis'].items()):return False
        elif a!='NO_ACTION_REQUIRED':return False
    else:
        if a=='REQUEST_EVIDENCE':fields.add('reason')
        elif a=='CHALLENGE':
            fields.add('reason')
            if pred.get('reason') in ('SCOPE_ERROR','EVIDENCE_CONTRADICTION'):fields.add('valid_scope')
        elif a=='PROPOSE_FINDING':fields.add('finding_type')
        elif a!='NO_ACTION_REQUIRED':return False
        for k in ['reason','finding_type']:
            if k in fields and (not isinstance(pred.get(k),str) or pred[k] not in system):return False
    return set(pred)==fields
def evaluate(text,inp,target):
    p=parse(text);g=target['expected'];valid=contract(p,inp)
    a=bool(p and p.get('action')==g['action'])
    reason=bool(p and p.get('reason') in target['acceptable_reason_codes']) if 'reason' in g else None
    request=bool(p and unique_strings(p.get('requested_evidence')) and set(p['requested_evidence'])==set(g['requested_evidence'])) if 'requested_evidence' in g else None
    tool=bool(p and p.get('tool')==g['tool'] and p.get('arguments')==g['arguments']) if 'arguments' in g else None
    ref=None
    if 'evidence_refs' in g:
        u=json.loads(inp['messages'][1]['content']);packet=u['case_packet'] if inp['contract_route']=='legacy_physics' else u['packet']
        provided={x['reference_id'] for x in u['reference_context']}|{x['evidence_id'] for x in packet['evidence' if inp['contract_route']=='legacy_physics' else 'observations']}
        ref=bool(p and matches_sufficient_set(p.get('evidence_refs'),provided,target['sufficient_sets']))
    others=bool(p and all(p.get(k)==v for k,v in g.items() if k not in ['reason','evidence_refs','requested_evidence','arguments','tool']))
    strict=bool(valid and a and others and all(v is not False for v in [reason,request,tool,ref]) and set(p)==set(g))
    return dict(json_object=p is not None,contract_valid=valid,parsed_action=a,qualified_action=a and valid,
                reason=reason,requests=request,tool_arguments=tool,reference=ref,strict=strict,parsed=p)
def fixtures():
    plan=read(RUN/'EVALUATION_PLAN.json');inputs={r['id']:r for r in rows(RUN/'EVALUATION_INPUTS.jsonl')};targets=rows(RUN/'EVALUATION_TARGETS.jsonl')
    for t in targets:
        assert evaluate(json.dumps(t['expected']),inputs[t['id']],t)['strict'],t['id']
        assert not evaluate('```json\n'+json.dumps(t['expected'])+'\n```',inputs[t['id']],t)['json_object']
        if 'evidence_refs' in t['expected']:
            bad=dict(t['expected'],evidence_refs=['UNPROVIDED']);r=evaluate(json.dumps(bad),inputs[t['id']],t)
            assert not r['reference'] and not r['contract_valid'] and not r['strict']
    save('SCORER_FIXTURES.json',dict(status='PASS',gold_identity_cases=len(targets),markdown_not_repaired_cases=len(targets),unknown_references_rejected=True,code_sha256=sha(__file__),completed_before_outputs=True))
def main():
    plan=read(RUN/'EVALUATION_PLAN.json');require(sha(RUN/'EVALUATION_INPUTS.jsonl')==plan['input_file_sha256'],'input changed');require(sha(RUN/'EVALUATION_TARGETS.jsonl')==plan['target_file_sha256'],'target changed')
    require(sha(__file__)==read(RUN/'SCORER_FIXTURES.json')['code_sha256'],'scorer changed after freeze')
    inp={r['id']:r for r in rows(RUN/'EVALUATION_INPUTS.jsonl')};targets={r['id']:r for r in rows(RUN/'EVALUATION_TARGETS.jsonl')};results={};summaries={}
    for kind in ['base','lora']:
        seal=read(RUN/(kind+'_RAW_SEALED.json'));require(sha(seal['raw_path'])==seal['raw_sha256'],'raw output changed')
        raw=rows(seal['raw_path']);require([r['id'] for r in raw]==list(inp),'output membership/order changed')
        results[kind]={r['id']:evaluate(r['text'],inp[r['id']],targets[r['id']]) for r in raw}
        summaries[kind]={}
        for name,c in plan['cohorts'].items():
            metrics={}
            mapping={'json_object':'ids','contract_valid':'ids','parsed_action':'action_ids','qualified_action':'action_ids','strict':'strict_ids','reason':'reason_ids','requests':'request_ids','tool_arguments':'tool_argument_ids','reference':'reference_ids'}
            for metric,key in mapping.items():
                ids=c[key];metrics[metric]=dict(correct=sum(results[kind][i][metric] is True for i in ids),denominator=len(ids))
            summaries[kind][name]=metrics
        families={fid:all(results[kind][i]['strict'] for i in plan['cohorts']['DEV_PRIMARY']['ids'] if targets[i]['family_id']==fid) for fid in plan['complete_family_ids']}
        summaries[kind]['DEV_COMPLETE_FAMILIES']=dict(correct=sum(families.values()),denominator=len(families),families=families)
        save(kind+'_SCORED.json',dict(raw_sha256=seal['raw_sha256'],plan_sha256=sha(RUN/'EVALUATION_PLAN.json'),metrics=summaries[kind],cases=results[kind]))
    changes=[]
    for cid in inp:
        b=results['base'][cid];l=results['lora'][cid]
        metrics=[m for m in b if m!='parsed' and b[m]!=l[m]]
        if metrics:changes.append(dict(id=cid,cohort=inp[cid]['cohort'],changed_metrics={m:{'base':b[m],'lora':l[m]} for m in metrics},strict_improved=not b['strict'] and l['strict'],strict_regressed=b['strict'] and not l['strict']))
    save('COMPARISON.json',dict(metrics=summaries,case_changes=changes,plan_sha256=sha(RUN/'EVALUATION_PLAN.json'),comparison='same RC3 policy/revision only',legacy_scope=plan['legacy_scope'],diagnostic_gold_unresolved=True,generalization_or_safety_proof=False))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fixtures':fixtures()
    else:main()
