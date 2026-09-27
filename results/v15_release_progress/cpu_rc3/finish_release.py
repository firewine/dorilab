"""Create review-facing reports and an immutable technical-readiness seal."""
import collections,json,sys
from common import *

def fixtures():
 fixture=ROOT/'dorilab-ai/data/train150_v01.jsonl'
 generator=ROOT/'dorilab-ai/training/make_train150_v01.py'
 oldmanifest=read(ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data/train_curriculum_physics20_v02_r1.manifest.json')
 assert sha(fixture)==oldmanifest['contract_file_sha256']
 records=rows(fixture);analysis=[r for r in records if '<ROLE>ANALYSIS</ROLE>' in r['messages'][1]['content']]
 oldrows=rows(LEGACY);candidate=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json')
 selected=[m for m in candidate['members'] if m['contract_route']=='analysis_alias_rc3']
 assert {digest(r['messages']) for r in analysis}=={digest(oldrows[m['source_row_index_0based']]['messages']) for m in selected}
 states=[json.loads(r['messages'][1]['content'].split('STATE:',1)[1]) for r in analysis]
 counts=collections.Counter((s.get('tool_result') or {}).get('status','ABSENT') for s in states)
 verdicts=collections.Counter(s['tool_result']['verdict'] for s in states if (s.get('tool_result') or {}).get('status')=='CURRENT')
 trainer=ROOT/'venvs/dorilab-tournament/lib/python3.12/site-packages/transformers/trainer.py'
 report={'created_at_utc':now(),'fixture_path':str(fixture),'fixture_sha256':sha(fixture),'matches_prior_contract_file_sha256':True,'generator_path':str(generator),'generator_sha256':sha(generator),'generator_analysis_lines':[186,308],'generator_executed':False,'analysis_rows':len(analysis),'all_30_original_messages_exactly_match_candidate_parents':True,'result_status_counts':dict(counts),'current_verdict_counts':dict(verdicts),'current_representation_fields':['status','verdict','affected_axes'],'no_extra_provenance_fields_required':True,'trainer_source_path':str(trainer),'trainer_source_sha256':sha(trainer),'step_count_source_lines':[1798,1813,2439,2446],'step_rule':'ceil(206/4)=52 updates per epoch, 2 epochs=104; final accumulation has2 microbatches'}
 put('ANALYSIS_FIXTURE_AND_STEP_AUDIT.json',report)
 print(json.dumps(report,ensure_ascii=False))

def finish():
 tests=sorted((OUT/'tests').glob('run_*.json'));test=read(tests[-1]);assert test['status']=='PASS'
 from exporter import verify_bindings,load_candidates
 m,records=load_candidates();pre=read(PREFLIGHT);bundle=read(BUNDLE);cfg=read(OUT/'LORA_SINGLE_CONFIG.json')
 verify_bindings(pre['input_file_sha256']);verify_bindings(bundle['implementation_file_sha256']);verify_bindings(bundle['evidence_file_sha256'])
 baseline=read(OUT/'PRESERVATION_BEFORE.json')['files'];assert all(sha(p)==h for p,h in baseline.items())
 put('PRESERVATION_AFTER.json',{'checked_at_utc':now(),'all_preserved':True,'tracked_files':len(baseline),'files':{p:sha(p) for p in baseline}})
 put('RELEASE_READINESS.json',{'created_at_utc':now(),'status':'TECHNICAL_CPU_READY_PENDING_EXPERIMENT_REVIEW_AND_GPU_VALIDATION','B01':'RESOLVED_NATIVE_LEGACY_CONTRACT','B02':'RESOLVED_COMMON_SYSTEM_30_TARGETS_UNCHANGED','B05':'DIAGNOSTIC_ONLY_SCOPE_PROPOSAL_FROZEN','B04':'IMPLEMENTED_CPU_VALIDATED_GPU_RUNTIME_NOT_EXECUTED','B03':'REVIEW_BUNDLE_READY_NOT_APPROVED','training_candidate_rows':206,'actual_approved_release_rows':0,'primary_strict_max_cases':15,'reason_candidate_cases':7,'reason_current_approved_cases':0,'diagnostic_cases':1,'complete_primary_families':3,'cpu_boundary_tests':test['tests_run'],'active_preflight':PREFLIGHT.name,'active_approval_bundle':BUNDLE.name,'single_configuration_sha256':sha(OUT/'LORA_SINGLE_CONFIG.json'),'formal_training_executed':False,'gpu_inference_executed':False,'gpu_inventory_only':True,'model_weights_loaded':False,'pod_lock_touched':False,'stop_touched':False,'reserved_evaluatoronly_opened':False,'new_paper_search':False})
 text('APPROVAL_BUNDLE_KO.md',f'''# 한 번에 검토할 실험용 승인 묶음

**현재 승인 상태는 PENDING이다.** [승인 묶음 v2]({BUNDLE.name})에 정책·사례·membership·source/rights/split·설정안을 현행 hash로 연결했다. 검토 결과를 [대기 양식]({PENDING_APPROVAL.name})에 기록할 수 있다. 이 양식의 reviewer/reviewed_at은 비어 있으며 실제 승인 전에 채우지 않았다.

| 검토 결정 | 확인할 내용 | 연결 근거 |
|---|---|---|
| 정책/계약 | B01 legacy reason 유지, Analysis 공통 별칭·CURRENT 우선순위·출력 계약30행 | B01_RESOLUTION.json, B02_COMPARISON_30.json, contracts/analysis_alias_rc3.txt |
| 사례/학습자료 | 기존 TRAIN36 후보 label·충분 reference 정책 수락 및 기존 legacy 검토의 명시된 범위 재사용 | 206행 input/gold/assistant hash, 기존 Physics20 검토 원문 및 augmentation 승인 |
| Membership/source 사용 | 정확히206행, 보류 family12건 제외, DEV 제외. 원문 내용·이용권·공개 corpus 범위의 split 검토 | TRAIN_RELEASE_CANDIDATE_v15_RC3.json, source_states, source_evidence_binding_sha256 |
| 평가 범위 | DEV 원본 보존, 주 strict15·reason7·진단1·완전 family3와 충분 reference 집합 검토 | DEV_EVALUATION_MEMBERSHIP_RC3.json, EVALUATION_APPROVAL_PENDING.json |
| 단일 실행 계획 | 아래 고정 설정과 준비 조건 충족 후 같은 Pod GPU 메모리 검증·첫 실험용 학습 계획 | LORA_SINGLE_CONFIG.json, LORA_TARGET_MODULES.json |

단일 배치 검토로 이 그룹들을 함께 수락할 수 있다. 실제 확인되지 않은 source 권리나 사례를 승인했다고 간주하지 않으며, 미해결 항목이 있으면 이유와 범위를 남기고 새 버전을 만든다. 실험용 학습 허용은 독립 공학적 승인·요구조건 합격·시험 실행 권한과 다르다. 이번 요청은 기술 준비 승인으로만 반영했다.

## 재사용한 실제 검토 이력

`review_decisions.csv`의 Physics20 APPROVED와 `source_review.csv`의 TH-01/VB-X1/EE-02/EE-03 REVIEWED_OK 기록은 과거 manifest의 hash와 일치한다. 원래 reviewer는 firewine이고 원래 날짜는2026-09-18이며 새 검토를 수행한 것으로 날짜를 바꾸지 않았다. 2026-09-19의 별도 augmentation 승인도 원래 파일과 dataset hash가 일치한다. 선택한 legacy170의 원래 메시지는 승인된 position210 안의 canonical messages와170/170 일치하며, Physics20도20/20 연결된다.

이 이력은 기존 사례와 무관 관측 추가의 적용 범위에만 재사용한다. 새 Analysis system30행, 새 TRAIN36, 새 실험 전체의 승인을 소급해 만들지 않는다. 변경되지 않은 legacy120 contract와 Physics20, 변경된 Analysis30을 분리해 검토할 수 있다.

## source/rights/split 범위

기존4 source는 **LEGACY_REPLAY**다. 이미 알고 있는 source라는 사실을 숨기고 신규라고 승인할 필요가 없다. 원래 source 사용 검토를 재사용할지와 학습/DEV 역할 및 분리(`split_role_verified`)를 확인한다. 신규 TRAIN source3개는 내용·rights·split/novelty 검토가 필요하다. 신규 source gate의 요구를 legacy replay에 잘못 적용한 초안은 보존하고 v2에서 역할을 구분했다.

CANYVAL/PROBA-V는 RC2에서 확보한 PDF·감사·hash를 DEV용으로 재사용하며 새 논문을 찾지 않았다. 공개 TRAIN/DEV와 실제 legacy metadata 범위의 중복 감사만 주장한다. RESERVED/EvaluatorOnly를 열어 독립성을 증명하지 않았으며 외부 전체 corpus 무중복도 주장하지 않는다. 그러므로 legacy_corpus_audit_pass 수락에는 이 명시된 감사 범위가 포함되어야 한다.

기존 양식의 false/null을 자동으로 true/실명/시간으로 바꾸지 않았다. 테스트용 승인 객체는 메모리 안에서만 사용했으며 실제 승인 파일·release·SFT를 생성하지 않았다.

승인 근거 hash:

- TRAIN manifest: `{sha(OUT/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json')}`
- 단일 설정안: `{sha(OUT/'LORA_SINGLE_CONFIG.json')}`
- DEV membership: `{sha(OUT/'DEV_EVALUATION_MEMBERSHIP_RC3.json')}`
- 활성 승인 묶음: `{sha(BUNDLE)}`
''')
 text('LORA_SINGLE_CONFIG_KO.md',f'''# 첫 Qwen27 LoRA 단일 설정안

상태: **하나의 설정안 고정, 미승인·미실행**. CPU 길이 실측에 근거해 설정안을 작성했으며 승인을 기다린다는 이유로 작성을 미루지 않았다. Sweep이나 대체 설정 후보는 없다.

| 항목 | 고정안 |
|---|---|
| 모델 | {cfg['model']} / revision `{REVISION}` |
| 데이터 | TRAIN206, 각 행1회/epoch, 2 epochs →412 example presentations |
| LoRA | rank16, alpha32, dropout0.05, bias none |
| 대상 | 언어 decoder64개 layer의 indexed projection496개; vision/embedding/lm_head 제외 |
| 예상 trainable | {cfg['estimated_lora_parameters']:,} LoRA parameters; 실제 loaded module/parameter 수는 GPU 준비 단계에서 assert |
| Optimizer | AdamW(torch), lr5e-5, betas0.9/0.999, eps1e-8, weight decay0.01, max grad norm1.0 |
| Scheduler | linear, warmup6 steps |
| Batch | single GPU, micro-batch1, accumulation4, effective batch4, drop_last=false |
| Step | epoch당 ceil(206/4)=52, 총104. 마지막 accumulation은2 microbatches. 예제 누락 없음 |
| 길이 | max4096, dynamic right padding, packing=false, truncation=false |
| 정밀도/연산 | BF16 base, quantization 없음, SDPA, gradient checkpointing(non-reentrant), use_cache=false |
| Seed | model/data42 |
| 저장 | 별도 새 run 디렉터리, 자동 resume 없음, 최종 adapter1개. sweep/checkpoint 성능 선택 없음 |
| 비교 | 같은 base/adapter DEV 입력·template·평가 membership, greedy, thinking=false, max_new_tokens384 |

대상은 `q/k/v/o_proj`, linear attention의 `in_proj_qkv/z/b/a`, `out_proj`, MLP의 `gate/up/down_proj`이다. 문자 suffix를 vision까지 전역 적용하지 않고 [496개 정확한 경로](LORA_TARGET_MODULES.json)를 사용한다. 고정 weight index·config 및 로컬 모델 코드에서 확인했으며 모델을 로드한 실제 module type 검증은 아직 하지 않았다.

현재 Trainer 소스의 accumulation remainder와 ceil step 계산을 확인했다. [fixture/step 근거](ANALYSIS_FIXTURE_AND_STEP_AUDIT.json)를 참조한다. Trainer에서는 max_steps=-1와 epochs2를 사용하고 완료 후 global_step104를 검증한다.

## 길이·메모리 검증

CPU 실제 길이: TRAIN 최소{pre['train_min_tokens']}, 최대{pre['train_max_tokens']} tokens. DEV prompt 최대{pre['dev_max_prompt_tokens']}, 응답384 예약 포함{pre['dev_max_reserved_tokens']}. 기존2048은 충분하지 않다. 4096에서 잘림 없이 native turn 전체를 검사했다. 실제 배치는 동적 padding이므로 무조건4096까지 padding하지 않는다.

GPU inventory만 조회했다: RTX PRO6000 Blackwell Server Edition, 총97,887MiB / 조회 시 여유97,252MiB. **학습 메모리 적합성 확인이 아니다.** BF16 27B weights는 대략54GB(decimal) 규모이며, FP32 adapter weights/gradients/Adam states 추정은{cfg['memory_plan']['adapter_fp32_weights_grads_adam_bytes_estimate']:,} bytes다. Activation·workspace·driver 여유는 미측정이다.

승인 뒤 같은 고정 checkpoint의 shard hash·module 집합·언어 LoRA-only trainables를 확인하고 가장 긴 실제 TRAIN 사례로 forward/backward 메모리를 검증한다. 이 검증은 optimizer.step과 adapter 저장 없이 수행하고 optimizer state 예상량까지 여유에 포함해야 한다. OOM/불일치가 나면 중단하며 batch/rank/길이를 자동 변경하지 않는다. GPU receipt가 현재 release/config/preflight/trainer hash와 일치해야 학습 진입점이 통과한다. GPU 검증 receipt는 이번에 생성하지 않았다.

실제 라이브러리: `{json.dumps(cfg['packages_observed'],ensure_ascii=False)}`. 이번에 모델·CUDA 학습을 실행하지 않았다.
''')
 eos=pre['training_token_stats'][0]['assistant_end_token_id']
 text('B04_EXPORTER_CPU_REPORT_KO.md',f'''# 혼합 exporter 및 CPU preflight

`exporter.py`는 승인 전에는206행 **NOT_RELEASED 미리보기 검증만** 수행한다. 실제 SFT export와 `train_once.py` 진입에는 현행 승인 manifest/input/gold/assistant hash·설정안·코드·source 검토의 일치가 필요하다. 기존 v13 공통 system으로 데이터를 다시 쓰지 않는다.

| 확인 항목 | 결과 |
|---|---|
| Membership | RC2의 고정206 TRAIN allowlist와 일치, 중복/변경/DEV/보류 family 삽입 거부 |
| 계약 라우팅 | legacy physics·legacy Evidence/Critic 원래 system, Analysis 공통 새 system30, v15 RC1 system36 |
| User/assistant 보존 | Analysis 포함 기존 user/assistant byte 내용 유지; 새 TRAIN36 기존 expected 그대로 |
| 필드/arguments | native 필수 필드·reason·claim/reference/request ID 검증. CALL_TOOL JSON arguments.required_s 및 actual_by_axis 보존 |
| 추론 입력 | system/user만 허용. assistant/gold/rationale/정답 reference-set metadata 포함 시 차단 |
| Native template | 단일 system→user→assistant, thinking=false prefix, 전체 native render와 토큰 prefix 일치 |
| Loss | system/user/assistant header/빈 thinking prefix는-100, 정답 JSON과 native im_end({eos})은 지도 |
| 끝/패딩 | native trailing newline은-100, padding attention0/label-100. 실제 종료 토큰을 padding과 혼동해 삭제하지 않음 |
| 길이 | TRAIN206/DEV16 전수 토큰화; max4096, silent truncation 없음. 의도적 한도 초과는 오류 |
| 승인 실패 | PENDING approval, stale input/gold, DEV/unknown membership, source gate 누락, 변경된 bundle/config 차단 |
| 학습 진입 | NOT_RELEASED 입력은 checkpoint 읽기·torch/model import 전에 거부. approved release 및 no-update GPU receipt 필요 |

활성 CPU 결과는 [{PREFLIGHT.name}]({PREFLIGHT.name})다. 최초 시도는 processor의 batched 반환 형태 비교 때문에 실패했고, 명시적 return_dict/input_ids 단일 batch 정규화 뒤 실제 token ID 비교가 통과했다. 초기 실패 기록과 이전 측정 보고서를 보존했다. v3/v4는 tokenizer·assets·입력/정답 및 측정에 쓰이는 exporter 함수의 동일성을 확인한 뒤 guard-only 코드 hash를 연결한 기록이다. 전체 토큰 측정 결과를 새 모델 결과로 표현하지 않는다.

최종 경계 테스트: **{test['tests_run']} PASS**, 실패0/오류0. 원래 Analysis30 외에 별칭 충돌·동일 별칭·CURRENT 입력 부족·STALE·결과 모순·invalid 숫자·unknown/duplicate axis, 승인/범위/hash 거부, native EOS/padding/truncation을 검사했다. synthetic 승인 fixture는 메모리에만 있고 실제 SFT export는0개다.

기존 v13 `packtool.export_sft`와 dcurr 학습기를 이 RC의 우회 경로로 사용하지 않는다. 새 exporter의 source gate는 legacy replay 사용/분리 확인과 신규 source content/rights/novelty 검토를 역할에 맞게 구분한다. 없는 source 권리·검증 이력을 생성하지 않는다.

기술 한계: 모델 weight 로드, GPU forward/backward, optimizer 실제 실행, 모듈 타입/VRAM fit은 아직 검증하지 않았다. 현 단계에서는 실행 가능한 학습 release0행이다.
''')
 distribution='\n'.join(f'| {a} | {n} |' for a,n in m['action_distribution'].items())
 text('TECHNICAL_READINESS_REPORT_KO.md',f'''# SourceReview v15 RC2 후속 기술 준비 — RC3

{now()} 기준, **CPU 기술 준비·승인 묶음·단일 LoRA 설정안을 완료했다. 정식 학습은 실행하지 않았다.** 기존 RC2·raw output·DEV input/gold·과거 snapshot은 보존했다.

## B01/B02 및 TRAIN

B01 PHY-EE02-P01-A는 v15 정책 혼입이 없음을 실제 메시지와 원본 hash로 확인했다. 질문은 시험 중 관측과 사후 회복의 해석이며 source에 방법이 있다는 이유만으로 method reason으로 바꾸지 않았다. 기존 CHALLENGE / EVIDENCE_INTERPRETATION_ERROR를 유지하여 compatibility blocker를 해소했다. 새 사람 label 승인 완료로 표시하지 않았다.

B02는 공통 Analysis 계약을30행 전체에 적용했다. requirement_s/required_s 입력 별칭, arguments의 required_s, 충돌 시 자료 요청, 사용 가능한 CURRENT 우선, 그 외 입력 준비에 따른 CALL_TOOL/REQUEST_EVIDENCE, NO_ACTION의 제한된 의미를 명시했다. 기존 assistant와 **30/30 일치**, 실제 불일치0건, target 자동 수정0건이다. CURRENT는 기존 fixture의 상태 주장으로 취급하며 없는 provenance/검증 history는 만들지 않았다. 원래 fixture30행과 generator도 확인했다.

**최종 후보206=contract150+legacy physics20+TRAIN36.** 3 family12건은 계속 제외한다. RC2의185행 subset은 선택하지 않았다. 그것을 쓰면 CALL_TOOL 양성10개가 전부 없어지지만 RC3에는10개를 모두 포함한다. 공식 승인·실제 SFT export는 아직0행이다.

| Action | 후보 행수 |
|---|---:|
{distribution}

## DEV 주 평가와 진단

DEV16 input/gold는 그대로 보존한다. B05 CASE-RC1-1a26698cec를 별도 진단1건으로 관리하며, 주 Action/strict는 최대15건이다. 주 reason 후보는 적용 가능한7건이고 검토 수락 전 공식 분모는0이다. 실제 평가에 들어가기 전에7개 ID와 충분 reference 집합을 승인·동결해야 한다. 생성된 답변을 보고 분모를 바꾸지 않는다.

미확정1건이 들어 있는 family는 완전 family 지표에서 제외한다. 완전 채점 후보는3 family다. 나머지3 variant의 case 지표를 family 완주 점수로 바꾸지 않는다. CANYVAL/PROBA-V는 RC2 원문·감사만 재사용했고 새 논문 검색과 정책 확대를 하지 않았다.

## Exporter/CPU 검증

혼합 native 계약 exporter와 approved-release-only 학습 진입점을 구현했다. 미리보기와 실제 SFT를 구분하고 membership·현행 input/gold·설정·source·코드 hash가 바뀌면 gate를 차단한다. Native template/역할/turn 경계, 정답과 종료 토큰 loss, system/user 및 padding 마스킹, 필수 필드/tool arguments를 CPU에서 확인했다.

TRAIN 최대**2,338**, DEV prompt 최대**1,769**, 응답384 예약 포함**2,153** tokens. 단일 설정은4096·동적 padding·packing 없음·truncation 금지다. CPU 경계 테스트 **{test['tests_run']}/{test['tests_run']} PASS**. 이전 CPU 시도·failure·보고서는 보존했다. GPU inventory 조회 외에 GPU 계산은 하지 않았다.

## 단일 실행 설정안

rank16 / alpha32 / dropout0.05 / lr5e-5 / epochs2 / seed42. Micro-batch1, accumulation4, AdamW, linear scheduler, warmup6, BF16/SDPA, gradient checkpointing. 206행×2epoch=412 example presentations, **104 optimizer steps**. 고정 모델 index의 언어 projection**496개**, 예상 LoRA parameter**116,727,808개**를 대상으로 하며 vision/embedding/lm_head는 제외한다.

GPU 메모리 fit·실제 module type·forward/backward는 미검증이다. RTX PRO6000 Blackwell 약96GiB라는 inventory만으로 적합 판정을 내리지 않았다. 승인 후 같은 구성으로 no-update GPU 검증을 수행하고 실패하면 자동 축소/sweep 없이 중단한다. 여러 설정 후보는 만들지 않았다.

## 사용자에게 필요한 실제 승인

[한 번에 검토할 승인 묶음](APPROVAL_BUNDLE_KO.md)에 아래 결정을 현재 hash와 연결했다.

1. B01 유지와 Analysis 공통 계약30행, TRAIN36 candidate label/reference 정책, 명시된 과거 legacy 검토 재사용 범위를 수락할지.
2. 정확히206행 membership과 source/rights/split 검토 범위를 실험용으로 사용할지. 기존 Physics20/source4의 실제 검토 이력은 재사용 가능 범위만 제시했다. 신규 source의 승인으로 확대하지 않았다.
3. DEV 주15/reason7/진단1/완전 family3의 출력 전 평가 범위와 reference 집합을 수락할지.
4. 단일 LoRA 설정안 및 승인 후 GPU 검증/첫 실험 실행 계획을 수락할지. 이 단계에서는 정식 학습을 실행하지 않는다.

없는 reviewer/reviewed_at/human review를 만들지 않았다. 실험용 승인과 공학적 승인은 별도다. 현재 남은 것은 사용자 release 검토와 승인 후 GPU runtime/메모리 검증이며, 설정안 작성과 CPU 구현은 완료됐다.

## 주요 파일

- [B01/B02 검토](B01_B02_CONTRACT_REVIEW_KO.md), [Analysis fixture/step 원천](ANALYSIS_FIXTURE_AND_STEP_AUDIT.json)
- [TRAIN206 manifest](TRAIN_RELEASE_CANDIDATE_v15_RC3.json), [NOT_RELEASED 미리보기](NOT_RELEASED_MESSAGE_PREVIEWS.jsonl)
- [DEV 평가 범위](DEV_EVALUATION_SCOPE_KO.md), [출력 전 membership](DEV_EVALUATION_MEMBERSHIP_RC3.json)
- [Exporter/CPU 보고](B04_EXPORTER_CPU_REPORT_KO.md), [최종 preflight]({PREFLIGHT.name})
- [단일 설정안](LORA_SINGLE_CONFIG_KO.md), [기계 판독 config](LORA_SINGLE_CONFIG.json)
- [활성 승인 묶음 v2]({BUNDLE.name}), [승인 대기 양식 v2]({PENDING_APPROVAL.name})
- [준비 상태](RELEASE_READINESS.json), [검증 로그]({tests[-1].with_suffix('.log').relative_to(OUT)}), [SHA256SUMS.txt](SHA256SUMS.txt)

읽기 전용 확인: `python exporter.py`(미리보기 검증), `python -m unittest test_release -v`(CPU), `sha256sum --check --quiet SHA256SUMS.txt`(cpu_rc3에서 실행). tokenizer 검사는 `/workspace/dorilab/venvs/dorilab-tournament/bin/python`을 사용한다. 생성 스크립트는 완료 폴더에 재실행하지 말고 새 revision을 사용한다.

정식 LoRA·추론·추가 모델 비교·sweep·DPO/RL·prompt 탐색은 실행하지 않았다. RESERVED/EvaluatorOnly를 열지 않았고 Pod lock/STOP을 건드리지 않았다. 현재 Pod를 유지하고 저장 후 대기한다.
''')
 status('RC3_TECHNICAL_READY_WAITING_EXPERIMENT_REVIEW',['B01 native 유지 근거로 해소; 새 사람 승인 생성 없음','B02 공통계약30/30 일치, 실제 mismatch0','TRAIN206 및 CALL_TOOL10 유지; DEV 주15/reason후보7/진단1/완전family3','혼합 exporter·승인/hash gate·native CPU token/loss 검증 완료',f'CPU 경계 테스트 {test["tests_run"]} PASS; 단일104step 설정안 고정'],['실제 학습/evaluation release 승인 미완료; 실행가능0행','GPU module/forward-backward/VRAM fit 미검증'],['TECHNICAL_READINESS_REPORT_KO.md','APPROVAL_BUNDLE_KO.md',BUNDLE.name,PENDING_APPROVAL.name,'TRAIN_RELEASE_CANDIDATE_v15_RC3.json','DEV_EVALUATION_MEMBERSHIP_RC3.json','LORA_SINGLE_CONFIG.json',PREFLIGHT.name,'RELEASE_READINESS.json','SHA256SUMS.txt'],['사용자가 현재 hash에 연결된 계약·사례·membership·source/rights/split·평가·단일 설정안을 검토','승인 후 no-update GPU 메모리/module 검증 및 일치하는 receipt 확인','이번 단계에서는 정식 학습하지 않고 현재 Pod 유지·대기'],['B03_EXPERIMENT_RELEASE_REVIEW_PENDING','EVALUATION_RELEASE_PENDING','GPU_RUNTIME_MEMORY_UNVERIFIED'])
 for ext in ['md','json']:text('STATUS_FINAL_SNAPSHOT.'+ext,(PROGRESS/('STATUS.'+ext)).read_text())
 put('STATUS_HISTORY.json',{'versions':{str(p):sha(p) for p in sorted((PROGRESS/'status_versions').glob('STATUS.*'))}})
 # Include original approval drafts and preflight revisions, never overwrite them.
 payload=[p for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='SHA256SUMS.txt']
 text('SHA256SUMS.txt',''.join(f'{sha(p)}  {p.relative_to(OUT)}\n' for p in payload))
 for line in (OUT/'SHA256SUMS.txt').read_text().splitlines():
  h,p=line.split('  ',1);assert sha(OUT/p)==h,p
 print(json.dumps({'status':'TECHNICAL_CPU_READY_NOT_RELEASED','files_sealed':len(payload),'tests':test['tests_run'],'candidates':206,'action_distribution':m['action_distribution'],'active_approval_bundle':BUNDLE.name,'active_preflight':PREFLIGHT.name,'preserved_inputs':len(baseline)},ensure_ascii=False))

if __name__=='__main__':globals()[sys.argv[1]]()
