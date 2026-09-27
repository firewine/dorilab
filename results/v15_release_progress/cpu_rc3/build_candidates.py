"""Build NOT_RELEASED previews, review records and frozen evaluation membership."""
import collections,copy,csv,json,sys
from common import *
from analysis_contract import RULES,decide

def contracts():
 source_audit=read(RC2/'LEGACY_V15_MESSAGE_AUDIT.json')
 parent=read(RC2/'TRAIN_RELEASE_CANDIDATE_v15.json')
 original=rows(LEGACY);labels={x['case_id']:x for x in rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')}
 b1=next(e for e in source_audit['entries'] if e['member_id']=='PHY-EE02-P01-A')
 r=original[b1['source_locator']['source_row_index_0based']]
 assert b1['input_messages']==r['messages'][:-1] and b1['original_assistant_message']==r['messages'][-1]
 system=r['messages'][0]['content']
 assert 'v15' not in system and 'no applicable specific reason' not in system and 'First decide action' not in system
 assert json.loads(r['messages'][-1]['content'])['reason']=='EVIDENCE_INTERPRETATION_ERROR'
 put('B01_RESOLUTION.json',{'status':'COMPATIBILITY_BLOCKER_RESOLVED_UNDER_NATIVE_LEGACY_CONTRACT','member_id':b1['member_id'],'reason_retained':'EVIDENCE_INTERPRETATION_ERROR','action_retained':'CHALLENGE','v15_policy_mixed_into_actual_messages':False,'original_messages_sha256':digest(r['messages']),'rc2_input_sha256':b1['input_messages_sha256'],'source_row_sha256':digest(r),'basis_ko':'질문은 자극 중 관측과 사후 회복의 해석이다. 실제 source에 평가 방법이 있다는 사실만으로 방법 구현/절차 질문이 되지 않는다. 기존 general reason 정의가 관측 해석 오류를 명시적으로 허용한다. legacy system과 원래 assistant를 유지하며 v15 구체 우선 정책을 주입하지 않는다.','new_human_label_approval':False,'label_changed':False})
 text('contracts/analysis_alias_rc3.txt',RULES)
 previews=[];comparison=[];members=[]
 byid={m['member_id']:m for m in parent['members']}
 for e in source_audit['entries']:
  mid=e['member_id'];m=copy.deepcopy(byid[mid]);msgs=copy.deepcopy(e['input_messages'])
  if e['component']=='NEW_TRAIN':
   assert e['assistant_target']==labels[mid]['expected']
   answer={'role':'assistant','content':json.dumps(labels[mid]['expected'],ensure_ascii=False,separators=(',',':'))};route='v15_rc1'
  else:
   orig=original[m['source_row_index_0based']];assert digest(orig)==m['source_row_sha256']
   assert msgs==orig['messages'][:-1];answer=copy.deepcopy(orig['messages'][-1])
   route='legacy_physics' if e['component']=='UNIQUE_PHYSICS_STATE' else 'legacy_contract'
  if '<ROLE>ANALYSIS</ROLE>' in msgs[1]['content']:
   old=msgs[0]['content'];state=json.loads(msgs[1]['content'].split('STATE:',1)[1]);newtarget=decide(state);expected=json.loads(answer['content'])
   comparison.append({'member_id':mid,'old_system_sha256':digest(old),'new_system_sha256':digest(RULES),'user_sha256':digest(msgs[1]['content']),'original_assistant_content':answer['content'],'original_assistant_sha256':digest(answer),'computed_target':newtarget,'matches':newtarget==expected,'fixture_state':state})
   msgs[0]['content']=RULES;route='analysis_alias_rc3'
  full=msgs+[answer]
  m.update(contract_route=route,release_status='NOT_RELEASED_PENDING_APPROVAL',blocker_ids=[],warning_ids=[],input_sha256=digest(msgs),gold_sha256=digest(json.loads(answer['content'])),assistant_content_sha256=digest(answer['content']),messages_sha256=digest(full),training_eligible=False)
  if e['component']=='NEW_TRAIN':m['label_record_sha256']=digest(labels[mid])
  previews.append({'member_id':mid,'status':'NOT_RELEASED','contract_route':route,'messages':full,'input_sha256':m['input_sha256'],'gold_sha256':m['gold_sha256'],'assistant_content_sha256':m['assistant_content_sha256'],'messages_sha256':m['messages_sha256']})
  members.append(m)
 mismatches=[x for x in comparison if not x['matches']]
 assert len(comparison)==30
 put('B02_COMPARISON_30.json',{'status':'PASS' if not mismatches else 'BLOCKED_TARGET_MISMATCH','shared_contract_path':'contracts/analysis_alias_rc3.txt','rows':comparison,'mismatches':mismatches,'row_count':30,'current_result_fixtures':sum(x['fixture_state'].get('tool_result',{}).get('status')=='CURRENT' for x in comparison if isinstance(x['fixture_state'].get('tool_result'),dict)),'case_id_specific_exceptions':False,'assistant_targets_modified':False})
 # Keep any actual mismatches explicit; never fix targets or silently train a smaller subset.
 for m in members:
  if m['member_id'] in {x['member_id'] for x in mismatches}:m['blocker_ids']=['B02_ACTUAL_TARGET_MISMATCH']
 jsonl('NOT_RELEASED_MESSAGE_PREVIEWS.jsonl',previews)
 bindings=[LEGACY,RC2/'TRAIN_RELEASE_CANDIDATE_v15.json',RC2/'LEGACY_V15_MESSAGE_AUDIT.json',RC1/'TRAIN36_LABEL_CANDIDATE.jsonl',RC1/'TRAIN36_INPUTS.jsonl',RC1/'MODEL_INPUT_PREVIEWS.jsonl',RC1/'prompts/direct_v15_pilot_rc1.txt',OUT/'contracts/analysis_alias_rc3.txt',OUT/'analysis_contract.py']
 distribution=dict(sorted(collections.Counter(m['action'] for m in members).items()))
 old_clear=[m for m in parent['members'] if not m['blocker_ids']]
 manifest={'version':'source-review-v15-cpu-rc3','status':'NOT_RELEASED','parent_manifest_sha256':sha(RC2/'TRAIN_RELEASE_CANDIDATE_v15.json'),'members':members,'excluded_family_members':parent['excluded_family_members'],'candidate_count':len(members),'component_counts':dict(collections.Counter(m['component'] for m in members)),'action_distribution':distribution,'assistant_target_changes':0,'system_changes':30,'row_blockers':len(mismatches),'approved_training_rows':0,
  'rc2_185_subset_is_not_selected':True,'call_tool_check':{'rc2_185_count':sum(m['action']=='CALL_TOOL' for m in old_clear),'rc3_candidate_count':distribution['CALL_TOOL'],'all_10_positives_would_be_lost_with_rc2_185':True},
  'source_file_sha256':{str(p):sha(p) for p in bindings},'previews_sha256':sha(OUT/'NOT_RELEASED_MESSAGE_PREVIEWS.jsonl'),'approval_required':True,'dev_in_train':False}
 assert len(members)==206 and distribution['CALL_TOOL']==10
 put('TRAIN_RELEASE_CANDIDATE_v15_RC3.json',manifest)
 text('B01_B02_CONTRACT_REVIEW_KO.md',f'''# B01/B02 계약 검토

B01은 실제 legacy system/user/assistant를 원본 repeat246과 대조했고 v15 정책 혼입이 없다. 질문의 관측/사후 회복 해석에 CHALLENGE / EVIDENCE_INTERPRETATION_ERROR를 유지한다. 호환성 blocker만 해소하며 새 사람 label 승인을 만들지 않았다.

B02는 `analysis_alias_rc3.txt` 하나를 관련 Analysis30행 모두에 동일하게 적용했다. 보류20행과 warning10행에 case ID 예외를 두지 않는다. 기존 assistant와 결정 함수 비교: **{len(comparison)-len(mismatches)}/30 일치**, 불일치{len(mismatches)}건. 불일치가 있으면 `B02_COMPARISON_30.json`의 목록이 release를 차단한다. assistant 정답은 수정하지 않았다.

기존 fixture의 CURRENT는 status/verdict/affected_axes로 표현되는 현재 결과 주장이다. 원래10개 CURRENT fixture는 NON_COMPLIANT여도 추가 계산 없이 NO_ACTION_REQUIRED다. 새 계약은 결과 구조와, 제공된 계산 입력으로 대조 가능한 내용의 일관성만 확인한다. 제공되지 않은 timestamp/run identity/provenance 검증을 만들어 넣지 않는다. STALE·형식 오류·제공 입력과 모순인 결과는 재사용하지 않는다. 입력이 부족해도 사용 가능한 CURRENT 결과가 있으면 추가 계산을 생략한다. 별칭 충돌에는 임의 선택 없이 REQUEST_EVIDENCE / DURATION_INPUT_MISSING을 쓴다(유효하고 모호하지 않은 계산 입력이 없음).

최종 후보206=contract150+physics20+TRAIN36. Action 분포: `{json.dumps(distribution)}`. RC2의185행 subset에는 CALL_TOOL이0건이므로 그대로 학습에 쓰지 않는다. 이번 후보에 CALL_TOOL 양성10건을 모두 복원했다. 3 family12건 보류와 DEV 제외를 유지한다.
''')
 status('RC3_B01_B02_COMPLETE',['B01 native legacy 유지로 compatibility 해소',f'Analysis 공통계약30행: 불일치 {len(mismatches)}','후보206, CALL_TOOL10 유지'],['새 release 사용 승인은 미완료'],['B01_RESOLUTION.json','B02_COMPARISON_30.json','TRAIN_RELEASE_CANDIDATE_v15_RC3.json'],['DEV15+진단1 범위 동결','exporter와 tokenizer preflight'],['B03','B04']+(['B02_ACTUAL_TARGET_MISMATCH'] if mismatches else []))

def evaluation():
 meta=rows(RC2/'dev16/METADATA.jsonl');gold={g['case_id']:g for g in rows(RC2/'dev16/GOLD_AI_CANDIDATE.jsonl')}
 hold='CASE-RC1-1a26698cec';members=[]
 for m in meta:
  g=gold[m['case_id']];cid=m['case_id'];primary=cid!=hold
  members.append({'case_id':cid,'family_id':m['family_id'],'input_sha256':m['input_sha256'],'gold_sha256':m['label_sha256'],'action':g['expected']['action'],'primary_strict_candidate':primary,'diagnostic_only':not primary,'reason_applicable':'reason' in g['expected'],'reason_review_status':'HELD_B05' if not primary else 'AI_REVIEW_COMPLETE_PENDING_USER_ACCEPTANCE','human_review_performed':False,'source_required':m['source_required']})
 families={f:[m for m in members if m['family_id']==f] for f in sorted({m['family_id'] for m in members})}
 complete=[f for f,ms in families.items() if len(ms)==4 and all(m['primary_strict_candidate'] for m in ms)]
 reasons=[m['case_id'] for m in members if m['primary_strict_candidate'] and m['reason_applicable']]
 bindings={str(RC2/'dev16'/n):sha(RC2/'dev16'/n) for n in ['INPUTS.jsonl','GOLD_AI_CANDIDATE.jsonl','METADATA.jsonl','MODEL_INPUT_PREVIEWS.jsonl','INPUT_FACTS.json']}
 plan={'version':'DEV16-primary15-diagnostic1-rc3','status':'PRE_OUTPUT_MEMBERSHIP_FROZEN_PENDING_EVALUATION_RELEASE','selection_rule':'Exclude the identified unresolved B05 case from primary strict/reason before any new model output. No performance-dependent selection.','members':members,'primary_action_ids':[m['case_id'] for m in members if m['primary_strict_candidate']],'primary_strict_ids':[m['case_id'] for m in members if m['primary_strict_candidate']],'diagnostic_ids':[hold],'primary_strict_max_denominator':15,'primary_reason_applicable_ids':reasons,'primary_reason_candidate_denominator':len(reasons),'primary_reason_approved_denominator':0,'reason_denominator_rule':'Count only primary members with a reason-bearing gold and completed accepted case/reason review. Freeze accepted IDs before inference. No denominator change based on generated action.','complete_primary_family_ids':complete,'complete_primary_family_count':len(complete),'incomplete_primary_families':{f:[m['case_id'] for m in ms if m['diagnostic_only']] for f,ms in families.items() if f not in complete},'source_file_sha256':bindings,'input_gold_changed':False,'dev_in_train':False,'new_model_outputs_seen':False,'evaluation_release_approved':False}
 assert len(reasons)==7 and len(complete)==3
 put('DEV_EVALUATION_MEMBERSHIP_RC3.json',plan)
 text('DEV_EVALUATION_SCOPE_KO.md',f'''# 첫 비교 평가 범위 제안

DEV16 input/gold bytes는 RC2 원본 그대로 참조한다. CASE-RC1-1a26698cec만 별도 진단으로 두며, 주 Action/strict 후보는15건이다. 진단의 Action도 주 수치와 합산하지 않는다. 미확정 reason을 자동 변경하지 않는다.

주 reason 분모 후보는 reason이 있는7건이다(NO_ACTION8건 제외, B05 CHALLENGE1건 제외). 현재 공식 승인 분모는0이며, 사례/reason 검토를 사용자가 수락한 뒤 해당 ID7개를 출력 전에 고정해야 한다. 모델이 reason을 출력했는지에 따라 분모를 바꾸지 않는다.

완전한 family 주 지표는4 variant가 모두 주 평가에 있는3 family만 계산한다. B05가 있는 family의 나머지3개는 case 지표에는 포함되지만 완전 채점 family로 세지 않는다. 3/4 성공을 family 성공으로 환산하지 않는다.

선택 기준·ID·현재 input/gold hash는 DEV_EVALUATION_MEMBERSHIP_RC3.json에 저장했다. 새 모델 출력은 보지 않았다. release 전에 평가 검토가 바뀌면 새 freeze를 만들고 원본을 보존한다.
''')
 status('RC3_DEV_SCOPE_FROZEN',['DEV 입력/gold 보존','주 strict 최대15 / reason 후보7 / 진단1 / 완전 family3 동결'],['평가 사용 승인 분모는 아직0'],['DEV_EVALUATION_MEMBERSHIP_RC3.json','DEV_EVALUATION_SCOPE_KO.md'],['혼합 exporter CPU 구현','기존 승인 이력 재사용 및 단일 설정안'],['B03','B04'])

if __name__=='__main__':globals()[sys.argv[1]]()
