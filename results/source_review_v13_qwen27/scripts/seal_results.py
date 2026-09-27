from pathlib import Path
import json,hashlib,datetime,os
root=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((root/p).read_text())
required=['FINAL_REPORT_KO.md','RUN_MANIFEST.json','SUMMARY.json','CASE_RESULTS.jsonl','RAW_OFFICIAL_SCORE.json','RAW_OFFICIAL_CASE_RESULTS.jsonl','DIAGNOSTIC_SEMANTIC_VIEW.json','DIAGNOSTIC_SEMANTIC_CASE_RESULTS.jsonl','SOURCE_AUDIT.json','SOURCE_SPAN_REVIEW_v2.json','CASE_SOURCE_REVIEW_v2.jsonl','PRESERVATION_AFTER.json','LABEL_REVIEW_STATUS.json','DEV_SUBSET_MANIFEST.json','TOKEN_PREFLIGHT.json','MODEL_TARGET_AUDIT.json','EXPERIMENT_LOCK.json']
assert all((root/p).is_file() for p in required)
o=read('RAW_OFFICIAL_SCORE.json');d=read('DIAGNOSTIC_SEMANTIC_VIEW.json');s=read('SUMMARY.json');m=read('RUN_MANIFEST.json');pres=read('PRESERVATION_AFTER.json');seal=read('baseline_direct/OUTPUT_SEAL.json');sub=read('DEV_SUBSET_MANIFEST.json')
assert (o['json_valid'],o['schema_valid'],o['strict'])==(8,4,3)
assert o['reason_code_error_class']=='OUTPUT_CONTRACT_FIELD_ERROR' and len(o['reason_code_case_ids'])==4
assert d['official_score'] is False and d['action_matches_candidate']==8 and not d['reason_code_renamed']
assert sha(root/'baseline_direct/predictions.jsonl')==seal['output_sha256']==s['output_sha256']==m['output_sha256']
assert sha(root/'inputs/dev8_hypso_public_v13_source_available_v1.jsonl')==sub['subset_inputs_sha256']==m['input_sha256']
assert pres['changes']==[] and pres['files_checked']==4969
assert not m['training_executed'] and not m['reserved_test_accessed'] and not s['training_eligible'] and not s['human_review_performed']
assert not m['source_program_audit_complete']
assert m['runtime']['transformers']=='5.18.0.dev0' and m['runtime']['transformers_git_commit']=='002e1edf5b5198488297f401dd853056b6521d02'
for src in read('SOURCE_AUDIT.json')['sources']:
 if src['raw_file_sha256']:assert sha(root/src['verified_local_source_path'])==src['raw_file_sha256']
 else:assert src['status']=='SOURCE_UNAVAILABLE'
for casefile in ['RAW_OFFICIAL_CASE_RESULTS.jsonl','DIAGNOSTIC_SEMANTIC_CASE_RESULTS.jsonl']:
 rr=list(map(json.loads,(root/casefile).read_text().splitlines()));assert len(rr)==8 and {x['case_id'] for x in rr}==set(sub['included_case_ids'])
report=(root/'FINAL_REPORT_KO.md').read_text()
for term in ['RAW OFFICIAL SCORE','DIAGNOSTIC SEMANTIC VIEW','OUTPUT_CONTRACT_FIELD_ERROR','SOURCE_GROUNDED_AI_CANDIDATE','LoRA 필요성을 입증하지 못했다','HUMAN_REVIEW_PENDING','SOURCE_UNAVAILABLE','RAG index 미확인 때문에 완료로 선언하지 않는다','RESERVED_TEST에는 접근하지 않았다']:assert term in report,term
# Existing stopping script appends to COMPLETED.txt. Preserve a checksummed pre-stop snapshot.
completed='''COMPLETED_SCOPE=CPU_SOURCE_AUDIT_AND_DEV8_DIRECT_DIAGNOSTIC
FULL_V13_LORA_COMPARISON=NOT_COMPLETED_PENDING_SOURCE_LABEL_RAG_REVIEW
RAW_OFFICIAL_JSON_VALID=8/8
RAW_OFFICIAL_SCHEMA_VALID=4/8
RAW_OFFICIAL_STRICT=3/8
DIAGNOSTIC_ACTION_CANDIDATE_AGREEMENT=8/8_NOT_OFFICIAL_SEMANTIC_ACCURACY
OUTPUT_CONTRACT_FIELD_ERROR=4
HUMAN_REVIEW_PERFORMED=false
TRAINING_ELIGIBLE=false
RESERVED_TEST_ACCESSED=false
HISTORICAL420_AND_FROZEN84_PRESERVED=true
POD_STOP_STATUS=REQUEST_PENDING_LAST_COMMAND
'''
for name in ['COMPLETED.txt','COMPLETED.pre_stop.txt']:
 with (root/name).open('x') as f:f.write(completed)
checks={'verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PRE_STOP_ARTIFACT_CONTENT_CHECKS_PASSED','required_files':required,'immutable_output_sha256':seal['output_sha256'],'completed_pre_stop_sha256':sha(root/'COMPLETED.txt'),'shutdown_script_mutates':['COMPLETED.txt','stop_requested_at.txt'],'note':'Completion refers only to audit and diagnostic scope. Stop outcome is recorded by finish_and_stop.sh; no subsequent verification after that command.'}
with (root/'PRE_STOP_VALIDATION.json').open('x') as f:json.dump(checks,f,indent=2)
exclude={'SHA256SUMS.txt','CHECKSUM_VERIFICATION.json','COMPLETED.txt','stop_requested_at.txt'}
files=[p for p in sorted(root.rglob('*')) if p.is_file() and p.relative_to(root).as_posix() not in exclude]
entries=[(sha(p),p.relative_to(root).as_posix()) for p in files]
with (root/'SHA256SUMS.txt').open('x') as f:
 for h,p in entries:f.write(h+'  '+p+'\n')
for h,p in entries:assert sha(root/p)==h,p
assert sha(root/'COMPLETED.txt')==sha(root/'COMPLETED.pre_stop.txt')
with (root/'CHECKSUM_VERIFICATION.json').open('x') as f:json.dump({'status':'PASS','verified_files':len(entries),'sha256sums_sha256':sha(root/'SHA256SUMS.txt'),'excluded':sorted(exclude),'completed_verified_before_stop':True,'completed_snapshot':'COMPLETED.pre_stop.txt','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},f,indent=2)
print('VERIFIED',len(entries),'artifact hashes; COMPLETED marker verified; ready for sync then final stop command')
