"""Compare saved selected field values only. Never imports or invokes the scorer or gold."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
WORK=ROOT.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 rows=[json.loads(x) for x in p.read_text().splitlines()]
 byid={r['case_id']:r for r in rows}
 if len(byid)!=len(rows):raise ValueError('duplicate case IDs')
 return byid
def main():
 old_path=WORK/'results/source_review_v13_qwen27/baseline_direct/predictions.jsonl'
 new_path=ROOT.parent/'runs/direct_v14_checked_01/predictions.jsonl'
 old=load(old_path);new=load(new_path)
 if len(old)!=8 or set(old)!=set(new):raise ValueError('DEV8 membership mismatch')
 details=[]
 for cid in old:
  a=json.loads(old[cid]['raw_output']);b=json.loads(new[cid]['raw_output'])
  reason_applicable='reason_code' in a or 'reason' in b
  is_request=a.get('action')=='REQUEST_EVIDENCE' or b.get('action')=='REQUEST_EVIDENCE'
  entry={'case_id':cid,'action_v13':a.get('action'),'action_v14':b.get('action'),'action_identical':a.get('action')==b.get('action'),
   'claim_id_v13':a.get('claim_id'),'claim_id_v14':b.get('claim_id'),'claim_id_identical':a.get('claim_id')==b.get('claim_id'),
   'evidence_refs_v13_as_saved':a['evidence_refs'],'evidence_refs_v14_as_saved':b['evidence_refs'],
   'evidence_refs_set_identical':set(a['evidence_refs'])==set(b['evidence_refs']),
   'reason_code_v13':a.get('reason_code'),'reason_v14':b.get('reason'),
   'reason_string_identical':a.get('reason_code')==b.get('reason') if reason_applicable else None,
   'requested_evidence_v13_present':'requested_evidence' in a,'requested_evidence_v14_present':'requested_evidence' in b,
   'requested_evidence_v13':a.get('requested_evidence'),'requested_evidence_v14':b.get('requested_evidence'),
   'request_list_identical_for_request_action':a.get('requested_evidence')==b.get('requested_evidence') if is_request else None,
   'keys_removed_from_v13':sorted(set(a)-set(b)),'keys_added_in_v14':sorted(set(b)-set(a))}
  details.append(entry)
 result={'scope':'OUTPUT_FIELD_VALUE_IDENTITY_ONLY_NOT_A_SCORE','old_file_sha256':sha(old_path),'new_file_sha256':sha(new_path),
  'v13_reason_semantics_rescored':False,'gold_read':False,'scorer_called':False,'raw_output_changed':False,'cases':details}
 with (ROOT/'OUTPUT_SELECTION_IDENTITY.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print('Identity comparison recorded; no scoring performed.')
if __name__=='__main__':main()
