from pathlib import Path
import json,hashlib,sys,collections
root=Path(__file__).resolve().parents[1];pkg=Path('/workspace/dorilab/research/DoriLab_SourceReview_v13');sys.path.insert(0,str(pkg));import packtool
def put(name,obj):
 with (root/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def putrows(name,rows):
 with (root/name).open('x') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
pred=packtool.rows(root/'baseline_direct/predictions.jsonl');seal=json.load(open(root/'baseline_direct/OUTPUT_SEAL.json'));assert packtool.file_sha(root/'baseline_direct/predictions.jsonl')==seal['output_sha256']
ins,gold,meta=packtool.load_split(pkg,'DEV');im={r['case_id']:r for r in ins};reasons=packtool.read_json(pkg/'schemas/reason_definitions_v13.json');official=[];diagnostic=[];ids=[]
for p in pred:
 cid=p['case_id'];r=packtool.evaluate_output(im[cid],gold[cid],p['raw_output'],reasons,False)
 if p['hit_generation_limit']:r.update(strict_pass=False,error='GENERATION_LIMIT_REACHED',hit_generation_limit=True)
 has_wrong_key=isinstance(r.get('parsed'),dict) and 'reason_code' in r['parsed']
 if has_wrong_key:ids.append(cid)
 official.append({'case_id':cid,'scorer_result_unchanged':r,'error_classification':'OUTPUT_CONTRACT_FIELD_ERROR' if has_wrong_key else ('EVIDENCE_REFERENCE_MISMATCH' if r['schema_valid'] and not r.get('reference_exact') else None),'classification_is_additional_audit_metadata':True,'raw_reason_code':r.get('parsed',{}).get('reason_code'),'raw_reason':r.get('parsed',{}).get('reason'),'candidate_expected':gold[cid]['expected'],'candidate_status':'SOURCE_GROUNDED_AI_CANDIDATE'})
 parsed=packtool.strict_json(p['raw_output']);readable=isinstance(parsed,dict) and isinstance(parsed.get('action'),str)
 diagnostic.append({'case_id':cid,'official_score':False,'action_readable':readable,'raw_action':parsed.get('action') if readable else None,'candidate_action':gold[cid]['expected']['action'],'action_matches_candidate':parsed['action']==gold[cid]['expected']['action'] if readable else None,'raw_schema_valid':r['schema_valid'],'reason_fields_repaired':False,'reason_semantics_evaluated':False,'candidate_status':'SOURCE_GROUNDED_AI_CANDIDATE','expert_approved_accuracy':False,'generalization_claim':False})
putrows('RAW_OFFICIAL_CASE_RESULTS.jsonl',official);putrows('DIAGNOSTIC_SEMANTIC_CASE_RESULTS.jsonl',diagnostic)
put('RAW_OFFICIAL_SCORE.json',{'title':'RAW OFFICIAL SCORE','track':'RAW_STRICT_V13_DEV8','scorer':'packtool.evaluate_output(..., normalize=False)','raw_output_modified':False,'score_recomputed_with_repaired_reason':False,'cases':8,'gold_status':'SOURCE_GROUNDED_AI_CANDIDATE','json_valid':8,'schema_valid':4,'strict':3,'action':{'current_scorer_true':8,'denominator':8,'note':'Current scorer computes action_correct before schema validation. These are not eight contract-valid successes.'},'reason':{'correct':0,'candidate_applicable':4,'not_evaluated_due_schema_error':4,'semantically_wrong_reason_count':None,'note':'No reason_code -> reason coercion; OUTPUT_CONTRACT_FIELD_ERROR is not SEMANTIC_REASON_ERROR.'},'evidence_refs':{'exact_true':3,'exact_false':1,'not_evaluated_due_schema_error':4,'total_cases':8},'parser_errors':0,'schema_errors':4,'schema_error_messages':{'unexpected answer fields':4},'reason_code_case_ids':ids,'reason_code_error_class':'OUTPUT_CONTRACT_FIELD_ERROR','scorer_sha256':packtool.file_sha(pkg/'packtool.py'),'output_sha256':seal['output_sha256'],'human_review_performed':False,'engineering_approved':False})
put('DIAGNOSTIC_SEMANTIC_VIEW.json',{'title':'DIAGNOSTIC SEMANTIC VIEW','official_score':False,'scope':'Only raw JSON action value comparison where readable','action_readable':8,'action_matches_candidate':8,'candidate_denominator':8,'candidate_status':'SOURCE_GROUNDED_AI_CANDIDATE','reason_code_renamed':False,'reason_semantics_evaluated':False,'official_rescoring_with_repair':False,'human_review_performed':False,'expert_approved_accuracy':False,'generalization_performance':False,'interpretation':'8/8 is agreement with AI-authored candidate actions only, not expert-approved accuracy, contract validity, safety rate or source generalization.'})
print('separate score layers written; OUTPUT_CONTRACT_FIELD_ERROR IDs:',ids)
