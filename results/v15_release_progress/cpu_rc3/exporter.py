"""Mixed native-contract exporter. Preview by default; release requires hash-bound approval."""
import argparse,json
from pathlib import Path
from common import *
from analysis_contract import RULES,decide

class ReleaseBlocked(ValueError):pass
def require(ok,message):
 if not ok:raise ReleaseBlocked(message)
def verify_bindings(bindings):
 for path,h in bindings.items():require(Path(path).is_file() and sha(path)==h,'bound file changed: '+path)
def validate_record(record):
 msgs=record['messages'];require([m['role'] for m in msgs]==['system','user','assistant'],'single native turn required')
 require(all(isinstance(m['content'],str) for m in msgs),'text-only messages required')
 require(all(not any(s in m['content'] for s in ('<|im_start|>','<|im_end|>')) for m in msgs),'reserved chat delimiters in message')
 target=json.loads(msgs[2]['content']);route=record['contract_route'];system=msgs[0]['content'];user=msgs[1]['content']
 require(digest(msgs[:-1])==record['input_sha256'],'input hash changed')
 require(digest(target)==record['gold_sha256'] and digest(msgs[2]['content'])==record['assistant_content_sha256'],'gold hash changed')
 require(digest(msgs)==record['messages_sha256'],'messages hash changed')
 if route=='analysis_alias_rc3':
  require(system==RULES,'Analysis system mismatch')
  require(decide(json.loads(user.split('STATE:',1)[1]))==target,'Analysis target mismatch')
 elif route=='legacy_contract':
  require('v15' not in system,'legacy contract policy contamination')
  action=target['action'];reason=target.get('reason');require(action in system and (not reason or reason in system),'native action/reason undeclared')
  fields={'action'}
  if action=='REQUEST_EVIDENCE':fields.add('reason')
  elif action=='CHALLENGE':
   fields.add('reason')
   if reason in ('SCOPE_ERROR','EVIDENCE_CONTRADICTION'):fields.add('valid_scope')
  elif action=='PROPOSE_FINDING':fields.add('finding_type')
  require(set(target)==fields,'native contract output fields changed')
 elif route in ('legacy_physics','v15_rc1'):
  u=json.loads(user);p=u['case_packet'] if route=='legacy_physics' else u['packet'];fields={'action','claim_id','evidence_refs'}
  require(target['action'] in ('CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'),'invalid source-review action')
  if target['action']!='NO_ACTION_REQUIRED':fields.add('reason');require(target['reason'] in system,'reason not in actual system')
  if target['action']=='REQUEST_EVIDENCE':
   fields.add('requested_evidence');allowed=u['allowed_request_ids'] if route=='legacy_physics' else [x['request_id'] for x in p['request_catalog']]
   refs=target['requested_evidence'];require(refs and len(refs)==len(set(refs)) and set(refs)<=set(allowed),'invalid requests')
  require(set(target)==fields,'source-review output field mismatch')
  claim=u['claim_id'] if route=='legacy_physics' else p['claim_id'];require(target['claim_id']==claim,'claim mismatch')
  provided={x['reference_id'] for x in u['reference_context']}|{x['evidence_id'] for x in p['evidence' if route=='legacy_physics' else 'observations']}
  refs=target['evidence_refs'];require(refs and len(refs)==len(set(refs)) and set(refs)<=provided,'invalid evidence refs')
  if route=='legacy_physics':require('v15' not in system,'legacy physics policy contamination')
 else:raise ReleaseBlocked('unknown contract route')

def load_candidates():
 manifest=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json');verify_bindings(manifest['source_file_sha256'])
 path=OUT/'NOT_RELEASED_MESSAGE_PREVIEWS.jsonl';require(sha(path)==manifest['previews_sha256'],'preview modified')
 records=rows(path);ids=[r['member_id'] for r in records]
 require(len(ids)==len(set(ids))==206,'unexpected candidate size or duplicate')
 require(ids==[m['member_id'] for m in manifest['members']],'candidate order or membership changed')
 require(set(ids)=={m['member_id'] for m in read(RC2/'TRAIN_RELEASE_CANDIDATE_v15.json')['members']},'candidate must stay within fixed RC2 TRAIN allowlist')
 forbidden={m['member_id'] for m in manifest['excluded_family_members']}
 devmeta=rows(RC2/'dev16/METADATA.jsonl');forbidden|={r[k] for r in devmeta for k in ('case_id','parent_case_id')}
 require(not(set(ids)&forbidden),'held/DEV membership included')
 require(not manifest['row_blockers'],'unresolved target mismatch')
 for r,m in zip(records,manifest['members']):
  require(r['status']=='NOT_RELEASED','preview promoted without release')
  require(all(r[k]==m[k] for k in ('input_sha256','gold_sha256','assistant_content_sha256','messages_sha256','contract_route')),'manifest binding mismatch')
  validate_record(r)
 return manifest,records

def inference_messages(record):
 # Input-only API has no gold, rationale, reference-set or label argument.
 msgs=record['messages'];require([m['role'] for m in msgs]==['system','user'],'inference requires only system/user')
 bad={'expected','gold','rationale_ko','acceptable_reason_codes','reference_requirement','sufficient_sets','training_eligible','supporting_fact_ids','supporting_observation_ids'}
 def clean(x):
  if isinstance(x,dict):return not(set(x)&bad) and all(clean(v) for v in x.values())
  if isinstance(x,list):return all(clean(v) for v in x)
  return True
 user=msgs[1]['content'];value=json.loads(user.split('STATE:',1)[-1]);require(clean(value),'gold metadata in inference input')
 return msgs

def approval_check(approval,manifest,records,configuration_sha256):
 require(approval.get('status')=='APPROVED_FOR_EXPERIMENTAL_TRAINING','release not approved')
 require(approval.get('reviewer') and approval.get('reviewed_at'),'release reviewer/time missing')
 require(approval.get('candidate_manifest_sha256')==sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),'candidate manifest hash not approved')
 require(approval.get('training_configuration_sha256')==configuration_sha256,'configuration hash not approved')
 require(approval.get('approval_bundle_sha256')==sha(BUNDLE),'approval evidence bundle changed')
 verify_bindings(read(BUNDLE)['evidence_file_sha256'])
 for key in ('source_program_split_audit_pass','legacy_corpus_audit_pass','candidate_label_policy_accepted','approved_training_experiment','analysis_contract_change_accepted','prior_review_reuse_accepted'):
  require(approval.get(key) is True,'approval missing: '+key)
 require(approval.get('engineering_approval_granted') is False,'experimental release must not grant engineering approval')
 ids=[r['member_id'] for r in records];require(approval.get('approved_member_ids')==ids,'approved membership differs')
 reviews=approval.get('case_reviews',[]);require(len(reviews)==len(ids) and len({r['member_id'] for r in reviews})==len(ids),'case review missing/duplicate')
 byid={r['member_id']:r for r in reviews}
 for r in records:
  a=byid.get(r['member_id'],{});require(a.get('decision')=='APPROVED_FOR_TRAINING' and a.get('reviewer') and a.get('reviewed_at'),'case unapproved: '+r['member_id'])
  for key in ('input_sha256','gold_sha256','assistant_content_sha256'):require(a.get(key)==r[key],'stale case approval: '+r['member_id']+'/'+key)
 bundle=read(BUNDLE);required_sources=bundle['required_training_source_ids']
 sources=approval.get('source_reviews',[]);require(len({s['source_id'] for s in sources})==len(sources),'duplicate source review')
 sources={s['source_id']:s for s in sources}
 for sid in required_sources:
  s=sources.get(sid,{});require(s.get('reviewer') and s.get('reviewed_at'),'source reviewer/time missing: '+sid)
  for key in ('content_verified','rights_approved'):require(s.get(key) is True,'source approval missing '+sid+'/'+key)
  role=bundle['source_states'][sid]['use_role'];require(s.get('use_role')==role,'source role differs: '+sid)
  if role=='LEGACY_REPLAY':require(s.get('split_role_verified') is True,'legacy replay split role not verified: '+sid)
  else:require(s.get('split_novelty_verified') is True,'new TRAIN source novelty/split not verified: '+sid)
  require(s.get('evidence_binding_sha256')==bundle['source_evidence_binding_sha256'][sid],'source evidence approval changed: '+sid)

def gate_current_release(approval_path):
 manifest,records=load_candidates();config=read(OUT/'LORA_SINGLE_CONFIG.json')
 require(read(PREFLIGHT)['status']=='PASS','CPU preflight not passed')
 verify_bindings(read(PREFLIGHT)['input_file_sha256'])
 verify_bindings(read(BUNDLE)['implementation_file_sha256'])
 require(sha(OUT/'LORA_TARGET_MODULES.json')==config['target_modules_sha256'],'approved target module list changed')
 require(config['candidate_count']==len(records),'configuration count mismatch')
 approval=read(approval_path);approval_check(approval,manifest,records,sha(OUT/'LORA_SINGLE_CONFIG.json'))
 return manifest,records,approval

def export_release(approval_path,output):
 manifest,records,approval=gate_current_release(approval_path)
 output=Path(output);require(not output.exists(),'output exists');output.mkdir(parents=True,exist_ok=False)
 data=output/'train.jsonl'
 with data.open('x') as f:
  for r in records:f.write(json.dumps({'id':r['member_id'],'messages':r['messages'],'contract_route':r['contract_route']},ensure_ascii=False)+'\n')
 release={'status':'RELEASED_FOR_EXPERIMENTAL_TRAINING','candidate_manifest_sha256':sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),'approval_path':str(Path(approval_path).resolve()),'approval_sha256':sha(approval_path),'training_configuration_sha256':sha(OUT/'LORA_SINGLE_CONFIG.json'),'cpu_preflight_sha256':sha(PREFLIGHT),'data_path':str(data.resolve()),'data_sha256':sha(data),'count':len(records),'member_ids':[r['member_id'] for r in records],'current_case_bindings':[{k:r[k] for k in ('member_id','input_sha256','gold_sha256','assistant_content_sha256','messages_sha256')} for r in records],'created_at_utc':now(),'engineering_approved':False}
 with (output/'RELEASE_MANIFEST.json').open('x') as f:json.dump(release,f,ensure_ascii=False,indent=2)
 return release

def verify_training_release(path):
 release=read(path);require(release.get('status')=='RELEASED_FOR_EXPERIMENTAL_TRAINING','trainer requires approved release, not preview')
 require(sha(release['approval_path'])==release['approval_sha256'],'release approval changed')
 _,records,_=gate_current_release(release['approval_path'])
 require(release['candidate_manifest_sha256']==sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),'release candidate changed')
 require(release['training_configuration_sha256']==sha(OUT/'LORA_SINGLE_CONFIG.json'),'release configuration changed')
 require(release['cpu_preflight_sha256']==sha(PREFLIGHT),'release preflight changed')
 require(sha(release['data_path'])==release['data_sha256'],'SFT file changed')
 expected=[{'id':r['member_id'],'messages':r['messages'],'contract_route':r['contract_route']} for r in records]
 require(rows(release['data_path'])==expected,'SFT does not match current inputs/gold')
 require(release['member_ids']==[r['member_id'] for r in records] and release['count']==len(records),'release membership changed')
 require(release['current_case_bindings']==[{k:r[k] for k in ('member_id','input_sha256','gold_sha256','assistant_content_sha256','messages_sha256')} for r in records],'release case hashes changed')
 return release,records

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--approval',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.approval:
  require(a.output is not None,'new output directory required');export_release(a.approval,a.output)
 else:
  m,r=load_candidates();print(json.dumps({'status':'NOT_RELEASED','validated_candidates':len(r),'export_created':False}))
