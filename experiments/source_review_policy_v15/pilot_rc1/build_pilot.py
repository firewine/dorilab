"""CPU-only candidate builder. Does not export SFT or import model/scorer code."""
import copy,hashlib,json,datetime
from pathlib import Path
from collections import Counter
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
V15=OUT.parent
PACK=ROOT/'research/DoriLab_SourceReview_v13'
LEGACY=ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl'
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def jsonl(name,data):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data))
def input_messages(inp,facts):
 # No gold or sufficient-reference argument: all explicitly provided facts are included.
 p=inp['packet'];ctx=[dict(facts[x['fact_id']],reference_id=x['reference_id']) for x in p['source_refs']]
 return [{'role':'system','content':(OUT/'prompts/direct_v15_pilot_rc1.txt').read_text()},
         {'role':'user','content':json.dumps({'case_id':inp['case_id'],'reference_context':ctx,'packet':p},ensure_ascii=False,sort_keys=True)}]
HOLD_FACTS={'SR13-TIRS-BASELINE','SR13-NEA-TRANSLATION','SR13-RHOBC-BOOT'}
LEGACY_HOLD={'PHY-EE02-P01-A':'일반 EVIDENCE_INTERPRETATION_ERROR와, source의 stimulus 중 관측을 전후 baseline과 함께 평가하는 명시된 방법을 무시한 METHOD_INTERPRETATION_ERROR가 겹친다. 관측은 존재하므로 monitoring 결손은 아니다. v15의 구체 우선 정책에서 method 적용 여부를 사람이 결정하기 전 잠정 충돌로 보류. 원래 target/messages는 수정하지 않는다.'}
LEGACY_REVIEW={
'PHY-VBX1-P02':'configuration-specific C-squared 선정 근거의 유무. FORCE_LIMIT_BASIS_UNRESOLVED는 legacy system에 명시된 구체 코드이며 v15 enum에 없다는 사실만으로 충돌은 아니다.',
'PHY-EE02-P02':'시간 이력/자극 로그 결손과 제공 상태 대조. 구체 monitoring은 질문의 시간 귀속에 직접 적용된다.',
'PHY-VBX1-P07':'분포·범위 가정 결손/제공. legacy 고유 probabilistic 코드가 실제 system에 명시되며 새 AS_RUN 확대와 무관하다.',
'PHY-EE02-P01':'자극 중 변화와 사후 복구를 분리하는 대조. A는 일반/방법 코드 경계 보류, B는 관측 보존의 적절한 제안이다.',
'PHY-TH01-P05':'부품별 전력·위치 입력 결손/제공. POWER_DISSIPATION_UNRESOLVED는 legacy 구체 코드로 명시된다.',
'PHY-TH01-P03':'capacitance 식별에 맞는 transient 사용 여부. legacy parameter-identification은 method보다 더 구체적인 명시 코드이며 서로 다른 코드 체계를 같은 enum으로 강제하지 않는다.',
'PHY-VBX1-P01':'support impedance 경계 차이와 acceleration 동일성 대조. boundary reason은 구체 우선 정책과 양립한다.',
'PHY-TH01-P02':'배경 복사 이력 결손을 무시한 capacitance 원인 단정. boundary code는 실제 결손을 지정하며 일반 원인 추론보다 우선할 근거가 있다.',
'PHY-EE03-P01':'SEL current와 SET output 관측 경로의 획득 결손. 신호 변환을 제안한 것이 아니므로 monitoring이 직접적이며 mapping으로 자동 변경하지 않는다.',
'PHY-VBX1-P03':'원문 turnover mode 정의와 다른 최저 주파수 선택. mode selection이라는 구체 코드가 legacy/v15에 모두 존재한다.'}

def main():
 old=read(V15/'TRAIN_BUILD_CANDIDATE_v15.json');changes=rows(V15/'LABEL_CHANGESET_v15.jsonl')
 cm={x['case_id']:x for x in changes};legacy=rows(LEGACY)
 inputs={};metas={};golds={}
 for sp in ['train','dev']:
  for name,d in [('inputs.jsonl',inputs),('metadata.jsonl',metas),('gold_candidate.jsonl',golds)]:d.update({x['case_id']:x for x in rows(PACK/'data'/sp/name)})
 facts={x['fact_id']:x for x in read(PACK/'sources/facts.json')}
 selected=[];holds=[];previews=[];audit=[];labels=[];traininputs=[]
 for member in old['members']:
  m=copy.deepcopy(member);mid=m['member_id']
  if m['component']=='NEW_TRAIN':
   c=cm[mid];fid=c['system_provenance']['authoring_source_principle']['fact_id']
   if fid in HOLD_FACTS:
    m.update(pilot_status='FAMILY_HELD_BY_USER',held_fact_family=fid);holds.append(m);continue
   inp=inputs[mid];messages=input_messages(inp,facts)
   label=copy.deepcopy(c['after_proposed']);label.update(case_id=mid,original=c['original'],status='AI_CANDIDATE_CASE_REVIEW_PENDING',human_review_performed=False,training_eligible=False,engineering_approved=False,post_model_output_policy_review=True)
   # No computational-run scope change survives the family hold.
   if mid in {'CASE-c51cdfeccd','CASE-6de39fe5d2'}:
    label['physical_as_run_fit_review']={'original_definition':read(PACK/'schemas/reason_definitions_v13.json')['AS_RUN_MISSING'],'question':inp['packet']['review_question'],'target':inp['packet']['review_target'],'basis':'Supplied observations explicitly lack physical vacuum-motion/retest execution records. AI fit review only; not automatic label approval.','human_approval':False}
   labels.append(label);traininputs.append(inp)
   m.update(pilot_status='SELECTED_CANDIDATE_PENDING_CASE_AND_USE_APPROVAL',contract_route='v15_pilot_rc1',candidate_label_sha256=digest(label))
   audit.append({'member_id':mid,'component':m['component'],'contract_route':'v15_pilot_rc1','message_discriminator':'Explicit v15 pilot RC1 system text plus policy/reason/field rules','system_sha256':digest(messages[0]),'conflict':'NONE_DETECTED_IN_CPU_CONTENT_REVIEW','human_review_performed':False})
  else:
   r=legacy[m['source_row_index_0based']];assert digest(r)==m['source_row_sha256']
   messages=[copy.deepcopy(x) for x in r['messages'] if x['role']!='assistant']
   target=next(x['content'] for x in r['messages'] if x['role']=='assistant')
   system='\n'.join(x['content'] for x in messages if x['role']=='system')
   reason=m['reason'];declared=reason=='NOT_APPLICABLE' or reason in system
   a={'member_id':mid,'component':m['component'],'contract_route':'legacy_original_messages','messages_unchanged':True,'full_original_messages_sha256':digest(r['messages']),'input_messages_sha256':digest(messages),'assistant_target_sha256':hashlib.sha256(target.encode()).hexdigest(),'system_sha256':digest([x for x in messages if x['role']=='system']),'system_excerpt':system[:260],'target_reason_declared_in_actual_system':declared,'human_review_performed':False}
   assert declared,mid
   if m['component']=='UNIQUE_PHYSICS_STATE':
    a['semantic_review']=LEGACY_REVIEW[mid.rsplit('-',1)[0]]
    a['conflict']='POTENTIAL_SPECIFIC_VS_GENERAL_LABEL_CONFLICT' if mid in LEGACY_HOLD else 'NO_BLOCKING_CONFLICT_IDENTIFIED_UNDER_EXPLICIT_LEGACY_CONTRACT'
   else:a['conflict']='DIFFERENT_SCOPED_CONTRACT_PRESERVED_NOT_V15_RELABEL'
   audit.append(a)
   if mid in LEGACY_HOLD:
    m.update(pilot_status='HELD_LEGACY_LABEL_COMPATIBILITY',hold_reason=LEGACY_HOLD[mid]);holds.append(m)
   else:m.update(pilot_status='SELECTED_CANDIDATE_PENDING_LEGACY_USE_APPROVAL',contract_route='legacy_original_messages')
  previews.append({'member_id':mid,'component':m['component'],'candidate_selected':mid not in LEGACY_HOLD,'messages':messages,'messages_sha256':digest(messages),'artifact_kind':'CPU_INPUT_PREVIEW_NOT_SFT_EXPORT'})
  if mid not in LEGACY_HOLD:selected.append(m)
 def dist(ms):return {'rows':len(ms),'action':dict(sorted(Counter(m['action'] for m in ms).items())),'reason':dict(sorted(Counter(m['reason'] for m in ms).items()))}
 cap=[m for m in old['members'] if m['member_id'] not in {h['member_id'] for h in holds if h['pilot_status']=='FAMILY_HELD_BY_USER'}]
 membership={'status':'PILOT_CANDIDATE_NOT_RELEASED','parent_218_sha256':sha(V15/'TRAIN_BUILD_CANDIDATE_v15.json'),'ceiling_206_members':cap,'selected_candidates':selected,'held_members':holds,'ceiling_distribution':dist(cap),'selected_distribution':dist(selected),'component_distributions':{k:dist([m for m in selected if m['component']==k]) for k in ['CONTRACT_REPLAY','UNIQUE_PHYSICS_STATE','NEW_TRAIN']},'selected_candidate_rows':len(selected),'approved_or_exportable_rows':0,'new_train_candidate_states':36,'new_train_families':9,'legacy_physics_selected_states':19,'candidate_repetitions_per_member':1,'policy_adoption':'USER_DIRECTED_RC_SCOPE_ONLY','case_review_approval':'PENDING','training_use_approval':'NOT_GRANTED','engineering_approval':'NOT_GRANTED','human_review_performed':False,'export_created':False,'dev_cases_in_training':[]}
 write('PILOT_TRAIN_MEMBERSHIP.json',membership)
 write('CONTRACT_COMPATIBILITY.json',{'status':'CPU_MESSAGE_CONTENT_REVIEW_NOT_MODEL_COMPLIANCE_TEST','entries':audit,'legacy_held':LEGACY_HOLD,'v15_prompt_sha256':sha(OUT/'prompts/direct_v15_pilot_rc1.txt'),'legacy_messages_mutated':False,'metadata_only_versioning':False,'training_use_approved':False})
 jsonl('TRAIN36_INPUTS.jsonl',traininputs);jsonl('TRAIN36_LABEL_CANDIDATE.jsonl',labels);jsonl('MODEL_INPUT_PREVIEWS.jsonl',previews)
 write('PILOT_APPROVAL_BOUNDARIES.json',{'policy_incorporation':'USER_REQUESTED','individual_case_approval':'PENDING','training_data_use_approval':'NOT_GRANTED','engineering_approval':'NOT_GRANTED','human_review_performed':False,'no_approval_record_created':True})
 print('candidate',len(selected),'held',len(holds),'previews',len(previews))
if __name__=='__main__':main()
