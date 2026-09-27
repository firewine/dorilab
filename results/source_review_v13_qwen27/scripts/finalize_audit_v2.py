from pathlib import Path
import json,hashlib,datetime,sys,collections,shutil,subprocess,os
root=Path(__file__).resolve().parents[1];pkg=Path('/workspace/dorilab/research/DoriLab_SourceReview_v13');sys.path.insert(0,str(pkg));import packtool
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def put(name,obj):
 with (root/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
# Correct the audit's case hash field to the export contract (full public envelope), preserving v1.
records=[]
public={r['case_id']:r for split in ['train','dev'] for r in packtool.rows(pkg/f'data/{split}/inputs.jsonl')}
for r in packtool.rows(root/'CASE_SOURCE_REVIEW.jsonl'):
 r['packet_sha256']=r['case_sha256'];r['case_sha256']=packtool.digest(public[r['case_id']]);r['audit_version']='v2_full_public_envelope_hash';records.append(r)
assert packtool.rows(root/'CASE_SOURCE_REVIEW_v2.jsonl') == records
# Precise normalized offsets into preserved page text, without adding content to inference inputs.
spans=json.load(open(root/'SOURCE_SPAN_REVIEW.json'))
bounds={
 'SR13-TIRS-GSE':{4:('IV. TIRS TV Testing Setup Lessons Learned','Since the two main')},
 'SR13-TIRS-ASBUILT':{5:('A. Pre-Test Model Audit',None),6:('hardware as well','B. Pre-Test Data Audit')},
 'SR13-TIRS-BASELINE':{6:('C. Pre-Correlation Check',None)},
 'SR13-TIRS-CULL':{7:('VI. TIRS TV Analysis Techniques Lessons Learned','As a means of model connectivity')},
 'SR13-NEA-LEVELS':{1:('Executive Summary','1 George'),2:('During the first','After the failure investigation')},
 'SR13-NEA-COIL':{2:('After the failure investigation',None),3:('immediately after running','The July test')},
 'SR13-NEA-TRANSLATION':{3:('The AMT motors performed nominally','This investigation')},
 'SR13-NEA-PLANNED':{3:('This investigation',None)},
 'SR13-RHOBC-RAILS':{2:('A power supply gating circuit','High-energy proton')},
 'SR13-RHOBC-MONITOR':{3:('3.1 Hardware','In addition, the resistors')},
 'SR13-RHOBC-EFFECTS':{11:('6 Conclusions','7 References')},
 'SR13-RHOBC-BOOT':{11:('The peripherals on board','7 References')},
 'SR13-HYPSO-RANGE':{3:('2 Experimental','The chamber has one')},
 'SR13-HYPSO-IR':{3:('The presence of radiative','The complete list')},
}
for r in spans:
 for s in r['spans']:
  t=' '.join((root/s['text_artifact']).read_text().split());a,b=bounds[r['fact_id']][s['pdf_page_1based']];start=t.find(a);end=t.find(b,start+len(a)) if b else len(t)
  assert start>=0 and end>start,(r['fact_id'],a,b)
  s.update(normalized_anchor=a,normalized_character_start=start,normalized_character_end_exclusive=end,normalized_span_sha256=hashlib.sha256(t[start:end].encode()).hexdigest(),normalization='Unicode split whitespace then join with single space')
put('SOURCE_SPAN_REVIEW_v2.json',spans)
put('AUDIT_AMENDMENTS.json',{'author':'Codex AI','changes':[{'superseded':'CASE_SOURCE_REVIEW.jsonl','current':'CASE_SOURCE_REVIEW_v2.jsonl','reason':'Use digest(full public envelope) as required by export_sft; retain separate packet hash'},{'superseded':'SOURCE_SPAN_REVIEW.json','current':'SOURCE_SPAN_REVIEW_v2.json','reason':'Add precise end offsets; replace ambiguous NEA planned-work anchor with This investigation'}],'original_package_modified':False,'labels_modified':False,'baseline_inputs_modified':False})
# Candidate membership plan is deliberately not an SFT export.
build=json.load(open(root/'TRAIN_BUILD_MANIFEST.json'));old=Path('/workspace/dorilab/dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl');rr=packtool.rows(old);membership=[]
for i,r in enumerate(rr):
 if r.get('v05_metadata',{}).get('kind')=='contract':membership.append({'role':'CONTRACT_REPLAY','parent_row_index_0based':i,'parent_row_id':r['id'],'parent_row_sha256':packtool.digest(r)})
for parent,indices in build['physics_parent_groups'].items():
 i=indices[0];membership.append({'role':'UNIQUE_PHYSICS_STATE','parent_case_id':parent,'candidate_representative_row_index_0based':i,'candidate_row_sha256':packtool.digest(rr[i]),'all_replay_indices':indices,'representative_review_required':True})
for r in records:
 if r['split']=='TRAIN':membership.append({'role':'UNRELEASED_TRAIN_CANDIDATE','case_id':r['case_id'],'case_sha256':r['case_sha256'],'gold_sha256':r['gold_sha256'],'training_eligible':False})
put('TRAIN_BUILD_CANDIDATE_MEMBERSHIP_v1.json',{'status':'PLANNING_ONLY_NOT_TRAINING_EXPORT','rows':membership,'count':len(membership),'supervised_token_allocation':'UNMEASURED_NO_RELEASE','human_review_performed':False})
# Full before/after preservation verification.
before=json.load(open(root/'cpu_source_audit/PRESERVATION_BEFORE.json'));changes=[]
for e in before['files']:
 p=Path(e['path'])
 if not p.is_file():changes.append({'path':str(p),'status':'MISSING'})
 elif sha(p)!=e['sha256']:changes.append({'path':str(p),'status':'HASH_CHANGED','before':e['sha256'],'after':sha(p)})
package_manifest=packtool.verify_package_manifest(pkg)
put('PRESERVATION_AFTER.json',{'checked_at':now,'files_checked':len(before['files']),'changes':changes,'status':'UNCHANGED' if not changes else 'CHANGES_FOUND','package_manifest_entries_verified':len(package_manifest['files']),'exclusions':before['excluded']})
assert not changes,changes
# Persist the exact baseline runtime and immutable small model artifacts onto /workspace.
cache=json.load(open(root/'cpu_source_audit/MODEL_CACHE_RESTORE.json'));snap=Path(cache['snapshot_path']);model_dest=root/'model_lock_assets';model_dest.mkdir()
for name in ['config.json','generation_config.json','chat_template.jinja','tokenizer_config.json','model.safetensors.index.json','LICENSE']:
 shutil.copy2(snap/name,model_dest/name)
for src in ['/workspace/dorilab/tournament/baseline_v1/DOCTOR.json','/workspace/dorilab/tournament/baseline_v1/qwen38_27b/MODEL_LOCK.json','/workspace/dorilab/runtime/qwen27_20260924/RUNTIME.txt','/workspace/dorilab/runtime/qwen27_20260924/pip.freeze.txt','/workspace/dorilab/runtime/transformers_qwen27.lock.txt','/workspace/dorilab/runtime/transformers_qwen27.sha']:
 shutil.copy2(src,model_dest/Path(src).name)
(root/'runtime_current.freeze.txt').write_text(subprocess.check_output(['/root/venvs/dorilab-tournament/bin/python','-m','pip','freeze'],text=True))
summary=json.load(open(root/'SUMMARY.json'));baseline=json.load(open(root/'baseline_direct/RUN_MANIFEST.json'));seal=json.load(open(root/'baseline_direct/OUTPUT_SEAL.json'))
put('RUN_MANIFEST.json',{'status':'CPU_SOURCE_AUDIT_AND_DEV8_DIRECT_DIAGNOSTIC_COMPLETE','created_at':now,'output_root':str(root),'model':baseline['model'],'revision':baseline['revision'],'runtime':{k:baseline[k] for k in ['transformers','transformers_git_commit','torch','cuda','peft','attention_implementation','precision','quantization','native_template_sha256','enable_thinking','seed','max_total_tokens','max_new_tokens','gpu','gpu_total_GiB']},'input_sha256':baseline['input_sha256'],'output_sha256':seal['output_sha256'],'source_status_file':'SOURCE_AUDIT.json','source_span_current':'SOURCE_SPAN_REVIEW_v2.json','case_source_review_current':'CASE_SOURCE_REVIEW_v2.jsonl','case_results':'CASE_RESULTS.jsonl','cpu':{'validate_exit_code':0,'unittest_exit_code':0,'tests_passed':34,'structural_only':True},'historical_baselines':{'models':5,'raw_outputs':420,'frozen_cases':84,'modified':False,'rerun':False},'training_build_candidate_membership_sha256':sha(root/'TRAIN_BUILD_CANDIDATE_MEMBERSHIP_v1.json'),'training_export_created':False,'training_executed':False,'human_review_performed':False,'training_eligible':False,'ledger_comparison_executed':False,'route_selected':False,'reserved_test_accessed':False,'os_security_seal':False,'rights_approval':'PENDING','rag_audit':'LOCAL_MANIFEST_EXPORT_REFERENCE_AND_SQLITE_CHECKED; SEPARATE_OR_EXTERNAL_INDEX_NOT_LOCATED','preservation_check':'PRESERVATION_AFTER.json','completion_scope':'CPU audit, source-available DEV8 diagnostic, immutable cache restoration; full v13 learning comparison remains gated','shutdown':{'command':'/workspace/dorilab/finish_and_stop.sh /workspace/dorilab/results/source_review_v13_qwen27','policy':'Run only after reports and checksums verified and sync; no subsequent tool work','script_sha256':sha(Path('/workspace/dorilab/finish_and_stop.sh')),'preconditions':{'runpodctl_present':bool(shutil.which('runpodctl')),'pod_id_present':bool(os.environ.get('RUNPOD_POD_ID'))}}})
print('preservation',len(before['files']),'unchanged; package manifest verified; final manifest written')
