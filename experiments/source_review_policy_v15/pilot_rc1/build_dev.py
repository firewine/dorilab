"""Build pre-output AI DEV candidates using locally acquired primary PDFs; CPU only."""
import copy,datetime
from build_pilot import ROOT,OUT,PACK,read,rows,sha,digest,write,jsonl,input_messages
SRC=OUT/'sources'
def span(name,page,anchor):
 path=SRC/f'{name}.page{page:02d}.txt';norm=' '.join(path.read_text().split());start=norm.index(anchor)
 return {'pdf_page_1based':page,'text_artifact':str(path.relative_to(OUT)),'text_sha256':sha(path),'normalized_anchor':anchor,'normalized_character_start':start,'normalization':'split whitespace and join single space','anchor_sha256':digest(anchor),'visual_review_performed':False}
def main():
 sources=[{'source_id':'SR13-CANYVAL','program_group':'CANYVAL_C_TIMON_PUMBAA','title':'Novel Structure and Thermal Design and Analysis for CubeSats in Formation Flying','doi':'10.3390/aerospace8060150','pdf':'CANYVAL_ASSET.pdf','pages':25},
 {'source_id':'SR13-PROBAV','program_group':'PROBAV_SAMSUNG_SRAM_RADEF_PSI','title':'Investigation of Single-Event Effects for Space Applications: Instrumentation for In-Depth System Monitoring','doi':'10.3390/electronics13101822','pdf':'PROBAV_ASSET.pdf','pages':15}]
 logs=read(SRC/'FETCH_LOG.json')
 for s in sources:
  name=s['pdf'].split('_')[0];fetch=next(x for x in logs if x['name']==name+'_ASSET')
  s.update(local_pdf=str((SRC/s['pdf']).relative_to(OUT)),pdf_sha256=sha(SRC/s['pdf']),download_url=fetch['url'],fetch_status=fetch['status'],bytes=fetch['bytes'],status='PRIMARY_PDF_ACQUIRED_AI_BODY_REVIEWED',rights_statement='CC BY 4.0 statement in first page; institutional dataset-use approval remains pending',human_review_performed=False,rights_approved=False,engineering_approved=False,source_identity_check='Title, authors/journal DOI on first page and body sections checked; PDF metadata alone not used')
 newfacts=[
 {'fact_id':'SR15-CANYVAL-HRM-METHOD','source_id':'SR13-CANYVAL','section':'5.1 Vibration Testing','pdf_pages_1based':[17,18],'text':'In the reported structural comparison, the strongly bounded HRM case has its two parts in direct contact. The other two representations connect parts indirectly with nylon wire, distinguished as face-to-edge and edge-to-edge. These alternatives represent changed restraint/tightening conditions; they are not identical boundary models. This describes the authors\' comparison, not a universal requirement for every panel.','spans':[span('CANYVAL',18,'With the strongly bounded condition')]},
 {'fact_id':'SR15-PROBAV-MODES','source_id':'SR13-PROBAV','section':'3.2 Test Execution and Monitoring','pdf_pages_1based':[6],'text':'The paper defines static testing as writing the memory and reading it after a waiting period. Dynamic testing continually reads and writes with March C- or March Dynamic Stress and reports errors on read accesses. A final stored image alone does not reproduce that dynamic observation path. Standby and chip-enabled are separate modes. These are this instrumentation\'s mode definitions, not certification requirements.','spans':[span('PROBAV',6,'Four test modes were used')]}
 ]
 oldfacts={x['fact_id']:x for x in read(PACK/'sources/facts.json')}
 factspans={'SR13-CANYVAL-PRELOAD':[span('CANYVAL',17,'The constraints of the backlash'),span('CANYVAL',18,'With the strongly bounded condition')],
 'SR13-CANYVAL-DAMAGE':[span('CANYVAL',23,'Although neither CubeSats')],
 'SR13-PROBAV-SYNC':[span('PROBAV',4,'It is important to acquire'),span('PROBAV',12,'coherent timestamping')],
 'SR13-PROBAV-CENSOR':[span('PROBAV',9,'If the SEL rate is exceedingly high')]}
 reviewed=[]
 for fid,sp in factspans.items():reviewed.append({'fact_id':fid,'old_fact_sha256':digest(oldfacts[fid]),'status':'AI_PRIMARY_BODY_LINK_CHECKED_NOT_LABEL_APPROVAL','spans':sp,'synthetic_numbers_not_from_source':True,'human_review_performed':False})
 write('sources/SOURCE_AUDIT_RC1.json',{'sources':sources,'original_fact_review':reviewed,'new_method_facts':newfacts,'replacement_sources_needed':False,'search_snippet_used_as_source_acquisition':False,'pdf_render_or_table_numeric_transcription_used':False,'review_environment':'/tmp/sr15_policy_cpu, pypdf 6.1.0; no CUDA/model/tokenizer import'})
 facts=dict(oldfacts);facts.update({f['fact_id']:{k:v for k,v in f.items() if k!='spans'} for f in newfacts})
 inputs={x['case_id']:x for x in rows(PACK/'data/dev/inputs.jsonl')};gs={x['case_id']:x for x in rows(PACK/'data/dev/gold_candidate.jsonl')}
 ms=[x for x in rows(PACK/'data/dev/metadata.jsonl') if x['source_id'] in {'SR13-CANYVAL','SR13-PROBAV'}]
 outinputs=[];labels=[];metas=[];previews=[];reviews=[]
 for m in ms:
  parent=m['case_id'];old=inputs[parent];g=gs[parent];v=m['variant_index'];p=copy.deepcopy(old['packet'])
  cid='CASE-RC1-'+digest(parent)[:10];newfid=None
  if m['family_id']=='F-e14546bbe1':newfid='SR15-CANYVAL-HRM-METHOD'
  if m['family_id']=='F-e5cd6d3740':newfid='SR15-PROBAV-MODES'
  source_required=bool(newfid)
  if newfid:
   p['claim_id']='CLM-RC1-'+digest(cid)[:10]
   ref='REF-RC1-'+digest(cid+'source')[:10];obs='OBS-RC1-'+digest(cid+'observation')[:10];noise='OBS-RC1-'+digest(cid+'noise')[:10]
   oldsupport=g['review_note']['supporting_fact_ids'][0]
   p['source_refs']=[{'reference_id':ref,'fact_id':newfid}]+[r for r in p['source_refs'] if r['fact_id']!=oldsupport]
   if newfid=='SR15-CANYVAL-HRM-METHOD':
    p['review_question']='Using the HRM representation definitions in the supplied Section 5.1, review the proposed method label.' if v<2 else 'Are the geometry records available to reproduce the paper-defined edge-to-edge HRM representation? Judge input readiness only.'
    observation=("A synthetic implementation record describes direct contact between the two HRM parts, with no intervening wire connection in that model." if v<2 else
     "The HRM parts are identified, but the dossier omits the connection drawing, contact declaration and wire-end attachment locations; no equivalent topology record is supplied." if v==2 else
     "The revision-matched geometry record and drawing are supplied. They show a nylon-wire element connecting an edge on each HRM part; the parts are not in direct contact. This record concerns representation topology, not predicted frequency or acceptance.")
    proposal=("Label this implementation as the paper's edge-to-edge wire-connected representation." if v==0 else
     "Label this implementation as the paper's strongly bounded direct-contact representation; do not label it as either indirect wire representation." if v==1 else 'Record the next input-readiness action for the named representation.')
    reason='METHOD_INTERPRETATION_ERROR' if v==0 else 'CONFIGURATION_SCOPE_UNRESOLVED'
    req='HRM_CONNECTION_RECORD';request_desc='Revision-matched HRM contact/connection drawing with wire attachment locations'
    rationale=['원문은 direct contact를 strongly bounded로 정의한다. 관측의 direct-contact 구현을 edge-to-edge라고 명명하는 제안을 반박한다. 일반적인 구조 안전 판정이 아니다.',
      '원문의 세 표현 정의와 관측을 대조하면 direct-contact 구현의 strongly bounded 명명이 맞다. 이 제한된 방법 명명에 추가 반박이 없다.',
      'edge-to-edge 표현을 재현하려면 원문이 구분한 연결 형태를 알 수 있어야 한다. 현재 attachment/contact 도면이 없으므로 연결관계 자료를 요청한다.',
      '원문이 정의한 edge-to-edge 연결과 대응하는 geometry/attachment 자료가 있다. 표현 재현 입력 준비만 확인하며 해석 결과나 구조 안전을 승인하지 않는다.'][v]
    removed='원문을 제거하면 strongly bounded/edge-to-edge라는 논문 고유 명칭과 구현 topology의 대응 정의가 없다. 관측은 topology를 기술하지만 그 명칭이 올바른지는 규정하지 않는다.'
   else:
    p['review_question']='Under the supplied Section 3.2 definitions, does the proposed static/dynamic test-mode description match the recorded operation?' if v<2 else 'Are operation and error-observation records available to reproduce the dynamic monitoring mode defined in the supplied Section 3.2? Judge input readiness only.'
    observation=("A synthetic run record contains one full-array write, a waiting interval, and one final full-array read. No read/write operations occur during the waiting interval. The record does not assign a static or dynamic mode label." if v<2 else
     "A final memory image and total exposure are supplied. The algorithm identity, ordered memory-operation trace and read-access error records are absent; no equivalent operation record is present." if v==2 else
     "The selected March C- algorithm identity, continuous ordered read/write execution trace and error records for read accesses are supplied with a common time reference. The task is whether the specified monitoring records exist, not the device's radiation tolerance.")
    proposal=("Describe this as the paper's dynamic test mode with continuously repeated read/write observation." if v==0 else
     "Describe this as the paper's static write-wait-read mode, without claiming dynamic read-access coverage during the waiting interval." if v==1 else 'Record the next input-readiness action for the named monitoring mode.')
    reason='METHOD_INTERPRETATION_ERROR' if v==0 else 'MONITORING_COVERAGE_INSUFFICIENT'
    req='DYNAMIC_OPERATION_ERROR_RECORDS';request_desc='Algorithm identity, ordered memory operations and read-access error records with timing'
    rationale=['원문은 static write-wait-read와 dynamic 반복 read/write를 구분한다. 관측의 단발 write-wait-read를 논문의 dynamic mode라 부르는 것은 정의와 충돌한다.',
      '제안은 원문의 static mode 정의에 맞고 관측되지 않은 dynamic coverage를 주장하지 않는다. 시험 내구성 판정이 아니다.',
      '원문 dynamic mode의 관찰 단위는 반복 연산과 read 시의 error 보고다. 최종 image만으로 그 기록 준비를 확인할 수 없어 필요한 operation/error records를 요청한다.',
      '논문 dynamic mode에 해당하는 알고리즘/반복 연산/read error 자료가 있다. 입력 준비를 확인할 뿐 SEE 발생률이나 신뢰성을 승인하지 않는다.'][v]
    removed='원문을 제거하면 논문에서 static/dynamic을 어떻게 정의하고 어떤 관측 경로를 사용했는지 주어지지 않는다. 합성 run의 연산 패턴은 있지만 source-specific 재현 여부를 확정할 계약이 없다.'
   p['review_target']={'kind':'PROPOSED_DISPOSITION' if v<2 else 'INPUT_READINESS','text':proposal}
   p['observations']=[{'evidence_id':obs,'scope':p['scope'],'text':observation,'origin':'SYNTHETIC_CASE_RECORD'},
                     {'evidence_id':noise,'scope':p['scope'],'text':'The archive cover lists the recording workstation name and supplies no additional method or engineering observation.','origin':'SYNTHETIC_CASE_RECORD'}]
   p['request_catalog']=[{'request_id':req,'description':request_desc},{'request_id':'DOCUMENT_REVISION_INDEX','description':'Document index only'}]
   action=['CHALLENGE','NO_ACTION_REQUIRED','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'][v]
   expected={'action':action,'claim_id':p['claim_id'],'evidence_refs':[ref,obs]}
   if action in {'CHALLENGE','REQUEST_EVIDENCE'}:expected['reason']=reason
   if action=='REQUEST_EVIDENCE':expected['requested_evidence']=[req]
   sets=[sorted([ref,obs])];family=m['family_id']+'-RC1-METHOD';supportfact=newfid
  else:
   expected=copy.deepcopy(g['expected']);supportfact=g['review_note']['supporting_fact_ids'][0]
   # Specificity now applied to previously source-unavailable candidates, with no model output consulted.
   if m['family_id']=='F-c7a41a91dd' and v==0:expected['reason']='MONITORING_COVERAGE_INSUFFICIENT'
   obsids=list(g['review_note']['supporting_observation_ids']);srcids=[r['reference_id'] for r in p['source_refs'] if r['fact_id']==supportfact]
   sets=[sorted(obsids),sorted(obsids+srcids)];family=m['family_id']
   rationale=('원인이 분별되지 않은 관측을 유일 원인 확정과 구분한다. source 원문은 그런 분별의 중요성을 보강하나 현재 합성 관측만으로 지정된 제안/준비 판단이 가능하다.' if m['family_id']=='F-e6c49196e6' else '시간 기준이 맞지 않거나 per-event 로그가 없는 상태와, 해당 자료가 모두 공급된 상태를 구분한다. 시간 귀속 관찰 결손에는 monitoring이라는 구체 코드를 적용한다. 동기화 자료 준비는 사건의 실제 인과를 입증하지 않는다.')+' '+g['review_note']['rationale_ko']
   removed='관측만으로 현재 결손/제안의 문제가 명시돼 있다. source 의존을 주장하지 않는 대조 사례이며 관측 충분 집합을 허용한다.'
  inp={'case_id':cid,'packet':p};msgs=input_messages(inp,facts)
  label={'case_id':cid,'expected':expected,'acceptable_reason_codes':[expected['reason']] if 'reason' in expected else [],
         'reference_requirement':{'mode':'SUFFICIENT_EXACT_SETS_V15_RC1','sufficient_sets':sets,'approved':False,'extra_refs_allowed':False},
         'rationale_ko':rationale,'status':'SOURCE_GROUNDED_AI_CANDIDATE','human_review_performed':False,'training_eligible':False,'engineering_approved':False,'model_outputs_seen_for_this_candidate':False,'policy_is_post_dev8_output_review':True}
  meta={'case_id':cid,'parent_case_id':parent,'parent_input_sha256':digest(old),'parent_gold_sha256':digest(g),'parent_family_id':m['family_id'],'family_id':family,'variant_index':v,'split':'DEV','source_id':m['source_id'],'program_group':m['program_group'],'kind':'METHOD_DEPENDENT_REVISION' if newfid else 'OBSERVATION_SUFFICIENT_CONTROL','source_required':source_required,'source_removal_reasoning':removed,'removal_check_method':'AI counterfactual reading of source-only definitions, not model ablation or human verification','support_fact_id':supportfact,'source_pdf_sha256':next(s['pdf_sha256'] for s in sources if s['source_id']==m['source_id']),'input_sha256':digest(inp),'label_sha256':digest(label),'messages_sha256':digest(msgs),'system_provenance_not_model_citation':True,'human_review_performed':False,'evaluation_role':'SOURCE_FAMILY_DEVELOPMENT_CANDIDATE_NOT_INDEPENDENT_HOLDOUT'}
  outinputs.append(inp);labels.append(label);metas.append(meta);previews.append({'case_id':cid,'messages':msgs,'messages_sha256':digest(msgs),'artifact_kind':'CPU_DEV_INPUT_PREVIEW_NOT_INFERENCE'})
 jsonl('dev16/INPUTS.jsonl',outinputs);jsonl('dev16/GOLD_AI_CANDIDATE.jsonl',labels);jsonl('dev16/METADATA.jsonl',metas);jsonl('dev16/MODEL_INPUT_PREVIEWS.jsonl',previews)
 used={r['fact_id'] for inp in outinputs for r in inp['packet']['source_refs']};write('dev16/INPUT_FACTS.json',{k:facts[k] for k in sorted(used)})
 # Inspect allowed TRAIN and chosen legacy membership only; do not open evaluator-controlled data.
 trainmeta=rows(PACK/'data/train/metadata.jsonl');legacy=rows(ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl')
 train_sources={m['source_id'] for m in trainmeta};train_programs={m['program_group'] for m in trainmeta};train_families={m['family_id'] for m in trainmeta}
 for r in legacy:
  train_sources.update(r.get('metadata',{}).get('source_ids',[]));train_programs.update(r.get('metadata',{}).get('program_groups',[]))
 ds={m['source_id'] for m in metas};dp={m['program_group'] for m in metas};df={m['family_id'] for m in metas}
 assert not(ds&train_sources or dp&train_programs or df&train_families)
 write('dev16/SPLIT_AUDIT.json',{'train_sources':sorted(train_sources),'dev_sources':sorted(ds),'train_programs':sorted(train_programs),'dev_programs':sorted(dp),'source_overlap':sorted(ds&train_sources),'program_overlap':sorted(dp&train_programs),'family_overlap':sorted(df&train_families),'scope':'Public TRAIN48 and actual legacy repeat246 metadata; full external-corpus/evaluator audit still pending','reserved_evaluatoronly_opened':False,'independent_generalization_claim':False})
 freeze_names=['dev16/INPUTS.jsonl','dev16/GOLD_AI_CANDIDATE.jsonl','dev16/METADATA.jsonl','dev16/MODEL_INPUT_PREVIEWS.jsonl','dev16/INPUT_FACTS.json','prompts/direct_v15_pilot_rc1.txt','POLICY_v15_RC1.md','sources/SOURCE_AUDIT_RC1.json']
 write('dev16/PRE_OUTPUT_FREEZE.json',{'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'AI_CANDIDATE_CONTENT_FROZEN_BEFORE_NEXT_MODEL_OUTPUT_NOT_RELEASE_APPROVAL','case_count':16,'source_method_dependent_cases':8,'observation_sufficient_controls':8,'file_sha256':{n:sha(OUT/n) for n in freeze_names},'model_inference_executed':False,'human_review_performed':False,'training_use_approval':False,'revision_rule':'Any reviewer changes require a new freeze manifest before inference; never silently amend this snapshot.'})
 print('DEV candidates',len(outinputs),'source-dependent',sum(m['source_required'] for m in metas))
if __name__=='__main__':main()
