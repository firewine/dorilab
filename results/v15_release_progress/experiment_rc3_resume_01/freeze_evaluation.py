"""Freeze evaluation inputs and scoring membership before the first model output."""
from run_common import *
from evaluation_gate import accepted_membership
from tokenization import processor,inference
def main():
    release,records,cfg=gate();membership=accepted_membership(read(PRIOR/'EVALUATION_APPROVAL.json'))
    devdir=RUN.parent/'cpu_rc2/dev16';meta={x['case_id']:x for x in rows(devdir/'METADATA.jsonl')}
    gold={x['case_id']:x for x in rows(devdir/'GOLD_AI_CANDIDATE.jsonl')}
    inputs=[];targets=[];proc,_=processor()
    for r in rows(devdir/'MODEL_INPUT_PREVIEWS.jsonl'):
        cid=r['case_id'];g=gold[cid]
        inputs.append(dict(id=cid,messages=r['messages'],cohort='DEV',contract_route='v15_rc1'))
        targets.append(dict(id=cid,cohort='DEV',expected=g['expected'],acceptable_reason_codes=g['acceptable_reason_codes'],
            sufficient_sets=g['reference_requirement']['sufficient_sets'],family_id=meta[cid]['family_id']))
    # Only already-approved TRAIN legacy members: a replay regression diagnostic,
    # explicitly not a held-out evaluation or extra model/prompt experiment.
    for r in records:
        if r['contract_route']=='v15_rc1':continue
        inputs.append(dict(id=r['member_id'],messages=r['messages'][:-1],cohort='LEGACY_TRAIN_REPLAY',contract_route=r['contract_route']))
        expected=json.loads(r['messages'][-1]['content'])
        targets.append(dict(id=r['member_id'],cohort='LEGACY_TRAIN_REPLAY',expected=expected,
            acceptable_reason_codes=[expected['reason']] if 'reason' in expected else [],
            sufficient_sets=[expected['evidence_refs']] if 'evidence_refs' in expected else [],family_id=None))
    legacy=[x['id'] for x in inputs if x['cohort']=='LEGACY_TRAIN_REPLAY'];require(len(legacy)==170,'legacy replay membership')
    tokenstats=[]
    for r in inputs:
        rendered,ids=inference(proc,r['messages']);require(len(ids)+cfg['comparison']['max_new_tokens']<=cfg['max_length'],'inference budget overflow')
        tokenstats.append(dict(id=r['id'],input_sha256=digest(r['messages']),prompt_tokens=len(ids),token_ids_sha256=digest(ids),rendered_sha256=digest(rendered)))
    for name,data in [('EVALUATION_INPUTS.jsonl',inputs),('EVALUATION_TARGETS.jsonl',targets)]:
        with (RUN/name).open('x') as f:
            for row in data:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    save('EVALUATION_TOKEN_BINDINGS.json',tokenstats)
    targetby={r['id']:r for r in targets}
    cohorts={}
    for name,ids in [('DEV_PRIMARY',membership['strict_ids']),('DEV_DIAGNOSTIC',membership['diagnostic_ids']),('LEGACY_TRAIN_REPLAY',legacy)]:
        cohorts[name]=dict(ids=ids,action_ids=ids,strict_ids=ids,
            reason_ids=membership['reason_ids'] if name=='DEV_PRIMARY' else [i for i in ids if 'reason' in targetby[i]['expected']],
            request_ids=[i for i in ids if 'requested_evidence' in targetby[i]['expected']],
            tool_argument_ids=[i for i in ids if 'arguments' in targetby[i]['expected']],
            reference_ids=[i for i in ids if 'evidence_refs' in targetby[i]['expected']])
    plan=dict(status='FROZEN_BEFORE_OUTPUTS',frozen_at=now(),existing_evaluation_approval_sha256=sha(PRIOR/'EVALUATION_APPROVAL.json'),
        approved_dev_membership_sha256=sha(RC3/'DEV_EVALUATION_MEMBERSHIP_RC3.json'),release_manifest_sha256=sha(RELEASE),
        input_file_sha256=sha(RUN/'EVALUATION_INPUTS.jsonl'),target_file_sha256=sha(RUN/'EVALUATION_TARGETS.jsonl'),
        token_bindings_sha256=sha(RUN/'EVALUATION_TOKEN_BINDINGS.json'),cohorts=cohorts,complete_family_ids=membership['complete_family_ids'],
        comparison=cfg['comparison'],legacy_scope='All 170 approved legacy TRAIN rows, unchanged native RC3 messages including approved common Analysis30. In-sample replay regression only, not held-out. No new source or locked evaluator opened.',
        scoring='No output correction or regeneration. Parse exactly one JSON object, then native contract validity. Report parsed Action, contract-qualified Action, applicable reason, exact request/tool arguments, exact sufficient reference sets, full strict. Strict requires exact other target fields and valid native contract; reason may match frozen accepted codes and references frozen sufficient sets. No denominator changes. Diagnostic B05 excluded from all primary metrics/family aggregates.',
        independent_generalization_or_safety_claim=False)
    save('EVALUATION_PLAN.json',plan)
    status('RC3_EVALUATION_SCOPE_FROZEN',['DEV15/reason7/진단1/family3 및 reference 기존 승인 유지','legacy170 학습 재현 회귀 진단 입력/분모 고정','추론 입력은 system/user만 포함'],['모델 출력 미생성'])
if __name__=='__main__':main()
