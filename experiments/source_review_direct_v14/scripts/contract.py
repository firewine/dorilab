"""Diagnostic field-contract checks only; never repairs outputs or replaces v13 scoring."""
import json
FIELDS = {
 'NO_ACTION_REQUIRED': {'action','claim_id','evidence_refs'},
 'CHALLENGE': {'action','claim_id','evidence_refs','reason'},
 'REQUEST_EVIDENCE': {'action','claim_id','evidence_refs','reason','requested_evidence'},
 'CALL_TOOL': {'action','claim_id','evidence_refs','tool','arguments'},
 'PROPOSE_FINDING': {'action','claim_id','evidence_refs','finding_type'},
}
FORBIDDEN = {'gold','expected','rationale','rationale_ko','reference_requirement',
 'acceptable_reason_codes','relation_to_target','label_status','candidate_expected',
 'correct_references','gold_references','answer','required_reference_ids'}
def assert_public(obj):
 if isinstance(obj,dict):
  bad=set(obj)&FORBIDDEN
  if bad: raise ValueError('nonpublic fields: '+','.join(sorted(bad)))
  for value in obj.values(): assert_public(value)
 elif isinstance(obj,list):
  for value in obj: assert_public(value)
def violations(answer,packet):
 if not isinstance(answer,dict): return ['not_object']
 issues=[];action=answer.get('action');wanted=FIELDS.get(action)
 if wanted is None:return ['unknown_action']
 if 'reason_code' in answer:issues.append('reason_code')
 issues += ['missing:'+k for k in sorted(wanted-set(answer))]
 issues += ['unnecessary:'+k for k in sorted(set(answer)-wanted)]
 if answer.get('claim_id')!=packet['claim_id']:issues.append('claim_id_mismatch')
 refs=answer.get('evidence_refs');allowed={r['reference_id'] for r in packet['source_refs']}|{r['evidence_id'] for r in packet['observations']}
 if isinstance(refs,list) and all(isinstance(x,str) for x in refs):
  if not set(refs)<=allowed:issues.append('unprovided_reference')
 if action=='REQUEST_EVIDENCE' and not answer.get('requested_evidence'):issues.append('empty_or_missing_request')
 return issues
