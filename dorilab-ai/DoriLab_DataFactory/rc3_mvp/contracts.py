import json,math

FORBIDDEN={'gold','expected','rationale','rationale_ko','acceptable_reason_codes','reference_requirement','sufficient_sets','assistant','messages','target','label','supporting_fact_ids','supporting_observation_ids','training_eligible'}
def parse_json(text):
 def pairs(ps):
  result={}
  for k,v in ps:
   if k in result:raise ValueError('DUPLICATE_JSON_KEY: '+k)
   result[k]=v
  return result
 return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON: '+x)))
def check_packet(value):
 errors=[]
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in FORBIDDEN:errors.append('ANSWER_METADATA_NOT_ALLOWED: '+k)
    walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
  elif isinstance(x,str) and any(t in x for t in ['<|im_start|>','<|im_end|>']):errors.append('CHAT_DELIMITER_NOT_ALLOWED')
  elif isinstance(x,float) and not math.isfinite(x):errors.append('NONFINITE_NUMBER')
 walk(value)
 def string(v):return isinstance(v,str) and bool(v.strip())
 if not isinstance(value,dict):return ['PACKET_OBJECT_REQUIRED']
 if set(value)!={'case_id','packet','reference_context'}:errors.append('REQUIRED_TOP_LEVEL: case_id, packet, reference_context')
 if not string(value.get('case_id')):errors.append('CASE_ID_REQUIRED')
 p=value.get('packet');refs=value.get('reference_context')
 if not isinstance(p,dict):return errors+['PACKET_BODY_REQUIRED']
 for k in ['claim_id','review_question']:
  if not string(p.get(k)):errors.append('REQUIRED_STRING: '+k)
 if not isinstance(p.get('review_target'),dict) or not string(p['review_target'].get('text')):errors.append('REVIEW_TARGET_TEXT_REQUIRED')
 ids=[]
 for collection,key in [(refs,'reference_id'),(p.get('observations'),'evidence_id')]:
  if not isinstance(collection,list):errors.append('EVIDENCE_LIST_REQUIRED: '+key);continue
  for row in collection:
   if not isinstance(row,dict) or not string(row.get(key)) or not string(row.get('text')):errors.append('INVALID_EVIDENCE: '+key)
   else:ids.append(row[key])
 if not ids:errors.append('PROVIDED_EVIDENCE_REQUIRED')
 if len(ids)!=len(set(ids)):errors.append('DUPLICATE_PROVIDED_REFERENCE_ID')
 requests=p.get('request_catalog')
 if not isinstance(requests,list):errors.append('REQUEST_CATALOG_REQUIRED')
 else:
  rids=[]
  for r in requests:
   if not isinstance(r,dict) or not string(r.get('request_id')) or not string(r.get('description')):errors.append('INVALID_REQUEST_CATALOG')
   else:rids.append(r['request_id'])
  if len(rids)!=len(set(rids)):errors.append('DUPLICATE_REQUEST_ID')
 if 'source_refs' in p:
  if not isinstance(p['source_refs'],list):errors.append('INVALID_SOURCE_REFS')
  elif any(not isinstance(r,dict) or r.get('reference_id') not in ids for r in p['source_refs']):errors.append('SOURCE_REF_NOT_PROVIDED')
 return list(dict.fromkeys(errors))
def evidence_index(packet):
 out={}
 for key,kind,collection in [('reference_id','SOURCE_CONTEXT',packet['reference_context']),('evidence_id','OBSERVATION',packet['packet']['observations'])]:
  for row in collection:out[row[key]]={'id':row[key],'kind':kind,'provided_content':row}
 return out
def validate_output(text,packet,reason_codes,length_exceeded=False):
 errors=[];parsed=None
 try:
  parsed=parse_json(text)
  if not isinstance(parsed,dict):errors.append('OUTPUT_OBJECT_REQUIRED')
 except (ValueError,TypeError) as e:errors.append('INVALID_JSON: '+str(e))
 if length_exceeded:errors.append('OUTPUT_LENGTH_LIMIT_REACHED')
 provided=evidence_index(packet);cited=[];unknown=[]
 if isinstance(parsed,dict):
  action=parsed.get('action');fields={'action','claim_id','evidence_refs'}
  if not isinstance(action,str):
   errors.append('ACTION_STRING_REQUIRED');action=None
  if action not in {'NO_ACTION_REQUIRED','REQUEST_EVIDENCE','CHALLENGE'}:errors.append('UNSUPPORTED_ACTION_NO_EXECUTION')
  if action in {'CHALLENGE','REQUEST_EVIDENCE'}:
   fields.add('reason')
   if not isinstance(parsed.get('reason'),str) or parsed['reason'] not in reason_codes:errors.append('INVALID_REASON_CODE')
  if action=='REQUEST_EVIDENCE':
   fields.add('requested_evidence');r=parsed.get('requested_evidence');allowed={v['request_id'] for v in packet['packet']['request_catalog']}
   if not isinstance(r,list) or not r or any(not isinstance(i,str) for i in r):errors.append('REQUEST_IDS_REQUIRED')
   elif len(r)!=len(set(r)) or not set(r)<=allowed:errors.append('INVALID_REQUEST_IDS')
  if set(parsed)!=fields:errors.append('OUTPUT_FIELDS_MISMATCH')
  if parsed.get('claim_id')!=packet['packet']['claim_id']:errors.append('CLAIM_ID_MISMATCH')
  refs=parsed.get('evidence_refs')
  if not isinstance(refs,list) or not refs or any(not isinstance(i,str) for i in refs):errors.append('REFERENCE_IDS_REQUIRED')
  else:
   if len(refs)!=len(set(refs)):errors.append('DUPLICATE_REFERENCE_ID')
   cited=list(dict.fromkeys(refs));unknown=[r for r in cited if r not in provided]
   if unknown:errors.append('UNPROVIDED_REFERENCE: '+', '.join(unknown))
 return dict(status='CONTRACT_FAILED' if errors else 'CONTRACT_VALID_REVIEW_REQUIRED',errors=errors,parsed=parsed,
   cited_reference_ids=cited,unprovided_reference_ids=unknown,
   presented_evidence=[provided[r] for r in cited if r in provided],
   semantic_reference_sufficiency='NOT_AUTOMATICALLY_VERIFIED',reason_correctness='REQUIRES_HUMAN_REVIEW',
   engineering_approval=False,tool_execution=False)
