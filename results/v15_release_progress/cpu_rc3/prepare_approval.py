"""Reuse only verified historical review scope; never fabricate a reviewer or approval."""
import collections,csv,json,math,sys,importlib.metadata as metadata
from common import *

DATA=ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data'
def csvrows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def inspect():
 old=read(DATA/'train_curriculum_physics20_v02_r1.manifest.json')
 for n in ['train_curriculum_physics20_v02_r1.jsonl','train_curriculum_physics20_v02.jsonl','review_decisions.csv','source_review.csv']:
  p=DATA/n;print(n,p.exists(),sha(p) if p.exists() else None)
 approval=read(DATA/'evidence_training_v05/approval.json')
 for arm in ['repeat','position']:
  p=DATA/f'evidence_training_v05/{arm}210.jsonl';print(arm,'hash_approved',sha(p)==approval['dataset_sha256'][arm])
 original=rows(LEGACY);members=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json')['members']
 for arm in ['repeat','position']:
  hh={digest(x['messages']) for x in rows(DATA/f'evidence_training_v05/{arm}210.jsonl')}
  print(arm,'native170exact',sum(digest(original[m['source_row_index_0based']]['messages']) in hh for m in members if m['component']!='NEW_TRAIN'))
 index=read(ROOT/'results/source_review_v13_qwen27/model_lock_assets/model.safetensors.index.json')
 names=[k for k in index['weight_map'] if k.startswith('model.language_model.layers.0.')]
 print('layer0_weights',names)

def configuration():
 pre=read(PREFLIGHT);candidate=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json')
 indexpath=ROOT/'results/source_review_v13_qwen27/model_lock_assets/model.safetensors.index.json'
 weights=read(indexpath)['weight_map'];cfg=read(ASSETS/'config.json')['text_config']
 suffixes={'q_proj','k_proj','v_proj','o_proj','in_proj_qkv','in_proj_z','in_proj_b','in_proj_a','out_proj','gate_proj','up_proj','down_proj'}
 targets=sorted(k[:-7] for k in weights if k.startswith('model.language_model.layers.') and k.endswith('.weight') and k.rsplit('.',2)[-2] in suffixes)
 require_count=48*8+16*7
 assert len(targets)==require_count,(len(targets),targets[:3])
 put('LORA_TARGET_MODULES.json',{'source_index_path':str(indexpath),'source_index_sha256':sha(indexpath),'config_sha256':sha(ASSETS/'config.json'),'target_modules':targets,'count':len(targets),'selection':'All indexed Linear projections in the 64 language decoder layers, no vision/embedding/lm_head; runtime class and exact name-set assertion required','runtime_module_type_checked':False})
 h=cfg['hidden_size'];inter=cfg['intermediate_size'];head=cfg['head_dim'];att=cfg['num_attention_heads'];kv=cfg['num_key_value_heads']
 dims={'q_proj':(h,att*head*2),'k_proj':(h,kv*head),'v_proj':(h,kv*head),'o_proj':(att*head,h),'gate_proj':(h,inter),'up_proj':(h,inter),'down_proj':(inter,h),
       'in_proj_qkv':(h,2*cfg['linear_num_key_heads']*cfg['linear_key_head_dim']+cfg['linear_num_value_heads']*cfg['linear_value_head_dim']),
       'in_proj_z':(h,cfg['linear_num_value_heads']*cfg['linear_value_head_dim']),'in_proj_b':(h,cfg['linear_num_value_heads']),'in_proj_a':(h,cfg['linear_num_value_heads']),'out_proj':(cfg['linear_num_value_heads']*cfg['linear_value_head_dim'],h)}
 params=sum(16*sum(dims[n.rsplit('.',1)[-1]]) for n in targets)
 n=candidate['candidate_count'];batch=1;acc=4;epochs=2;steps=math.ceil(n/(batch*acc))*epochs
 code=ROOT/'venvs/dorilab-tournament/lib/python3.12/site-packages/transformers/models/qwen3_5/modeling_qwen3_5.py'
 packages={}
 for name in ['torch','transformers','peft','accelerate','tokenizers']:
  try:packages[name]=metadata.version(name)
  except metadata.PackageNotFoundError:packages[name]='NOT_INSTALLED'
 plan={'version':'qwen27-lora-one-config-rc3','status':'SINGLE_PROPOSAL_FROZEN_NOT_APPROVED','model':'Qwen/Qwen3.8-27B','revision':REVISION,'candidate_count':n,'candidate_manifest_sha256':sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),'rank':16,'alpha':32,'dropout':0.05,'learning_rate':5e-5,'epochs':2,'seed':42,'data_seed':42,
       'target_modules_file':'LORA_TARGET_MODULES.json','target_modules_sha256':sha(OUT/'LORA_TARGET_MODULES.json'),'target_module_count':len(targets),'estimated_lora_parameters':params,'module_source_file':str(code),'module_source_sha256':sha(code),
       'per_device_train_batch_size':batch,'gradient_accumulation_steps':acc,'world_size':1,'effective_batch_size':4,'dataloader_drop_last':False,'microbatches_per_epoch':206,'last_accumulation_microbatches':2,'optimizer_steps_per_epoch':52,'total_optimizer_steps':steps,'total_example_presentations':n*epochs,
       'optimizer':'adamw_torch','adam_beta1':0.9,'adam_beta2':0.999,'adam_epsilon':1e-8,'weight_decay':0.01,'scheduler':'linear','warmup_steps':6,'max_grad_norm':1.0,'precision':'bfloat16','quantization':None,'attention_implementation':'sdpa','gradient_checkpointing':True,'gradient_checkpointing_use_reentrant':False,'use_cache':False,
       'max_length':4096,'packing':False,'padding':'dynamic_right','loss':'assistant target plus native im_end only; system/user/assistant header/empty thinking prefix/native trailing newline/padding -100','truncation':False,
       'cpu_measured':{'train_max_tokens':pre['train_max_tokens'],'dev_max_prompt_tokens':pre['dev_max_prompt_tokens'],'dev_response_budget':384,'native_masking':'PASS'},
       'packages_observed':packages,'gpu_inventory_observed':{'name':'NVIDIA RTX PRO 6000 Blackwell Server Edition','memory_total_mib':97887,'memory_free_mib_at_query':97252,'method':'read-only nvidia-smi inventory; not allocation/fit validation'},
       'gpu_memory_fit_verified':False,'gpu_forward_backward_verified':False,'runtime_target_modules_verified':False,'memory_plan':{'base_weight_order_of_magnitude':'27B BF16 about54GB decimal, not a measured allocation','adapter_fp32_weights_grads_adam_bytes_estimate':params*16,'activation_and_kernel_workspace':'unmeasured; gradient checkpointing and actual longest sequence required','required_check':'After release approval, load same fixed model, assert exact language Linear targets and trainables; CPU/tokenizer hashes rechecked. Run longest actual train record forward/backward without optimizer.step or saved adapter; measure allocated/reserved peak and free-memory margin including optimizer state estimate. Stop on OOM or mismatch; no automatic batch/rank/length fallback.'},
       'comparison':{'base_and_adapter':'same fixed model revision, DEV input/prompt/template/decoding','eval_membership_sha256':sha(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json'),'strict_max_n':15,'reason_candidate_n':7,'diagnostic_n':1,'fully_scorable_families':3,'max_new_tokens':384,'do_sample':False,'enable_thinking':False,'no_prompt_search':True,'no_hyperparameter_sweep':True},'engineering_approval':False,'training_executed':False}
 put('LORA_SINGLE_CONFIG.json',plan)
 print(json.dumps({'modules':len(targets),'estimated_lora_params':params,'steps':steps,'packages':packages}))

def bundle():
 manifest=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json');orig=rows(LEGACY)
 reviews={r['case_id']:r for r in csvrows(DATA/'review_decisions.csv')};sources={r['source_id']:r for r in csvrows(DATA/'source_review.csv')}
 previous=read(DATA/'train_curriculum_physics20_v02_r1.manifest.json')
 matching={'case_review_csv_matches_prior_manifest':sha(DATA/'review_decisions.csv')==previous['review_csv_sha256'],'source_review_csv_matches_prior_manifest':sha(DATA/'source_review.csv')==previous['source_review_sha256']}
 aug=read(DATA/'evidence_training_v05/approval.json');assert aug['decision']=='APPROVED'
 arms={}
 for arm in ['repeat','position']:
  path=DATA/f'evidence_training_v05/{arm}210.jsonl';assert sha(path)==aug['dataset_sha256'][arm]
  arms[arm]={digest(r['messages']) for r in rows(path)}
 assert sha(DATA/'evidence_training_v05/manifest.json')==aug['manifest_sha256']
 exact=[];prior_case=[]
 for m in manifest['members']:
  if m['component']=='NEW_TRAIN':continue
  r=orig[m['source_row_index_0based']];found=[arm for arm,hs in arms.items() if digest(r['messages']) in hs]
  exact.append({'member_id':m['member_id'],'matched_approved_dataset_arms':found,'rc3_system_changed':m['contract_route']=='analysis_alias_rc3','native_messages_sha256':digest(r['messages'])})
  if m['component']=='UNIQUE_PHYSICS_STATE':
   review=reviews[m['member_id']];assert review['decision']=='APPROVED' and review['reviewer'] and review['reviewed_at']
   prior_case.append({'member_id':m['member_id'],'original_review':review,'scope':'historical Physics20 case decision + separately approved irrelevant-observation augmentation; no newly performed human review','augmentation_exact_match':found,'reuse_status':'REUSABLE_SCOPED_HISTORY_PENDING_CURRENT_EXPERIMENT_ACCEPTANCE' if found and all(matching.values()) else 'HISTORICAL_CONTEXT_ONLY_NEEDS_BINDING_REVIEW'})
 evidence_files=[DATA/'review_decisions.csv',DATA/'source_review.csv',DATA/'train_curriculum_physics20_v02_r1.manifest.json',DATA/'evidence_training_v05/approval.json',DATA/'evidence_training_v05/manifest.json',DATA/'evidence_training_v05/repeat210.jsonl',DATA/'evidence_training_v05/position210.jsonl']
 legacy_sids=['EE-02','EE-03','TH-01','VB-X1'];train_sids=legacy_sids+['SR13-NEA','SR13-RHOBC','SR13-TIRS']
 source_states={sid:{'prior_review':sources[sid],'status':'SCOPED_HISTORICAL_REVIEW_PENDING_EXPERIMENT_REUSE_ACCEPTANCE','bound_source_review_file_sha256':sha(DATA/'source_review.csv')} for sid in legacy_sids}
 prior_audit=ROOT/'results/source_review_v13_qwen27/cpu_source_audit/verified_sources'
 for sid in ['SR13-NEA','SR13-RHOBC','SR13-TIRS']:
  pdf=prior_audit/(sid+'.pdf')
  assert pdf.read_bytes().startswith(b'%PDF')
  source_states[sid]={'status':'EXISTING_PRIMARY_PDF_AI_AUDIT_NOT_HUMAN_RIGHTS_APPROVAL','pdf_path':str(pdf),'pdf_sha256':sha(pdf),'content_review':'existing RC1/RC2 source review reused; no new paper search','rights_approved':False,'human_review_performed':False};evidence_files.append(pdf)
 source_states['SR13-CANYVAL']={'status':'RC2_PRIMARY_SOURCE_VERIFIED_DEV_ONLY','audit_path':str(RC2/'sources/PRIMARY_SOURCE_VERIFICATION.json'),'audit_sha256':sha(RC2/'sources/PRIMARY_SOURCE_VERIFICATION.json'),'source_pdf_sha256':sha(RC2/'sources/CANYVAL_ASSET.pdf'),'rights_or_label_release_approved':False}
 source_states['SR13-PROBAV']={'status':'RC2_PRIMARY_SOURCE_VERIFIED_DEV_ONLY','audit_path':str(RC2/'sources/PRIMARY_SOURCE_VERIFICATION.json'),'audit_sha256':sha(RC2/'sources/PRIMARY_SOURCE_VERIFICATION.json'),'source_pdf_sha256':sha(RC2/'sources/PROBAV_ASSET.pdf'),'rights_or_label_release_approved':False}
 for sid in legacy_sids:source_states[sid]['use_role']='LEGACY_REPLAY'
 for sid in ['SR13-NEA','SR13-RHOBC','SR13-TIRS']:source_states[sid]['use_role']='NEW_SOURCE_TRAIN'
 evidence_files += [RC2/'sources/PRIMARY_SOURCE_VERIFICATION.json',RC2/'dev16/VALIDATION_RC2.json',OUT/'B01_RESOLUTION.json',OUT/'B02_COMPARISON_30.json',OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json',OUT/'LORA_SINGLE_CONFIG.json']
 implementation=[OUT/n for n in ['common.py','analysis_contract.py','exporter.py','tokenization.py','train_once.py','run_preflight.py','evaluation_gate.py']]
 payload={'created_at_utc':now(),'status':'ONE_REVIEW_BUNDLE_NOT_RELEASED','candidate_manifest_sha256':sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),'training_configuration_sha256':sha(OUT/'LORA_SINGLE_CONFIG.json'),'required_training_source_ids':train_sids,'source_states':source_states,'source_evidence_binding_sha256':{sid:digest(source_states[sid]) for sid in train_sids},'evidence_file_sha256':{str(p):sha(p) for p in evidence_files},'implementation_file_sha256':{str(p):sha(p) for p in implementation},'historical_review_reuse':{'matching_checks':matching,'physics_case_reviews':prior_case,'augmentation_approval_original':aug,'exact_message_matches':exact},'changes':{'B01':'native system and target unchanged; only compatibility interpretation resolved','B02':'one common Analysis system changes30 rows; all user/assistant bytes unchanged','TRAIN36':'RC1 inputs/labels unchanged','membership':'206, restores21 row holds; keeps original12 family exclusions','DEV':'input/gold unchanged; primary15 reason7 diagnostic1 completefamilies3'},'required_user_decisions':['Accept B01 native reason retention and Analysis common contract30','Accept current TRAIN36 candidate labels and reference policy; accept scoped reuse of existing legacy reviews','Approve exactly206 membership, source/rights/split scope and exclusion12','Accept pre-output DEV primary15/reason7/diagnostic1 membership and completed reason/reference review','Approve one fixed experimental LoRA configuration and post-approval GPU memory validation scope; engineering approval remains separate'], 'new_human_review_performed':False,'experimental_training_approved':False,'engineering_approved':False}
 put(BUNDLE.name,payload)
 pending={'status':'PENDING','reviewer':None,'reviewed_at':None,'candidate_manifest_sha256':payload['candidate_manifest_sha256'],'training_configuration_sha256':payload['training_configuration_sha256'],'approval_bundle_sha256':sha(BUNDLE),'approved_member_ids':[m['member_id'] for m in manifest['members']],'engineering_approval_granted':False,
          **{key:False for key in ('source_program_split_audit_pass','legacy_corpus_audit_pass','candidate_label_policy_accepted','approved_training_experiment','analysis_contract_change_accepted','prior_review_reuse_accepted')},
          'case_reviews':[{'member_id':m['member_id'],'decision':'PENDING','reviewer':None,'reviewed_at':None,**{k:m[k] for k in ('input_sha256','gold_sha256','assistant_content_sha256')}} for m in manifest['members']],
          'source_reviews':[{'source_id':sid,'use_role':source_states[sid]['use_role'],'reviewer':None,'reviewed_at':None,'content_verified':False,'rights_approved':False,'split_novelty_verified':False,'split_role_verified':False,'evidence_binding_sha256':payload['source_evidence_binding_sha256'][sid]} for sid in train_sids],
          'note':'An explicit batch review can approve these bound groups together. Record the actual reviewer/time then; current placeholders are not approval. Historical receipts are retained separately without changing dates.'}
 put(PENDING_APPROVAL.name,pending)
 eval_pending={'status':'PENDING','reviewer':None,'reviewed_at':None,'evaluation_membership_sha256':sha(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json'),'accepted_primary_strict_ids':[],'accepted_reason_review_ids':[],'accepted_sufficient_reference_sets_sha256':sha(RC2/'dev16/GOLD_AI_CANDIDATE.jsonl'),'note':'Approve current15/7 IDs before outputs; never select based on generated answers.'}
 if (OUT/'EVALUATION_APPROVAL_PENDING.json').exists():assert read(OUT/'EVALUATION_APPROVAL_PENDING.json')==eval_pending
 else:put('EVALUATION_APPROVAL_PENDING.json',eval_pending)
 status('RC3_APPROVAL_BUNDLE_AND_SINGLE_CONFIG_READY',['기존 Physics20/source4 실제 검토 이력과 augmentation hash 연결','206행 현행 input/gold hash 승인 묶음; legacy replay와 새 source gate 분리','단일 rank16/alpha32/dropout0.05/lr5e-5/epochs2/seed42 설정안 작성'],['실험용 사용/평가 release 승인 미완료','GPU fit 및 actual module type 미검증'],[BUNDLE.name,PENDING_APPROVAL.name,'EVALUATION_APPROVAL_PENDING.json','LORA_SINGLE_CONFIG.json'],['학습 진입점 gate 및 CPU 경계 테스트','최종 보고·봉인'],['B03_USER_REVIEW','GPU_MEMORY_UNVERIFIED'])

if __name__=='__main__':globals()[sys.argv[1]]()
