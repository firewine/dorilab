"""Frozen metric membership; unresolved B05 never enters primary reason/strict."""
from common import *
from exporter import require,verify_bindings
def accepted_membership(approval):
 plan=read(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json');verify_bindings(plan['source_file_sha256'])
 require(approval.get('status')=='APPROVED_FOR_EVALUATION','evaluation not approved')
 require(approval.get('reviewer') and approval.get('reviewed_at'),'evaluation reviewer/time missing')
 require(approval.get('evaluation_membership_sha256')==sha(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json'),'evaluation membership changed')
 require(approval.get('accepted_primary_strict_ids')==plan['primary_strict_ids'],'primary strict IDs not frozen as reviewed')
 require(approval.get('accepted_reason_review_ids')==plan['primary_reason_applicable_ids'],'reason-review IDs not frozen as reviewed')
 require(approval.get('accepted_sufficient_reference_sets_sha256')==sha(RC2/'dev16/GOLD_AI_CANDIDATE.jsonl'),'reference-set review binding changed')
 return {'strict_ids':plan['primary_strict_ids'],'reason_ids':plan['primary_reason_applicable_ids'],'diagnostic_ids':plan['diagnostic_ids'],'complete_family_ids':plan['complete_primary_family_ids'],'strict_denominator':len(plan['primary_strict_ids']),'reason_denominator':len(plan['primary_reason_applicable_ids'])}
