"""Register the completed RC3 candidate and inspect SAVED results only."""
import datetime,hashlib,json,os,re,sys
from pathlib import Path
ROOT=Path('/workspace/dorilab');OUT=Path(__file__).resolve().parent
EXP=OUT.parent/'experiment_rc3_resume_01';RC3=OUT.parent/'cpu_rc3'
EXPECTED_ADAPTER='d90dee59f00f7c987c1b61ae334f928464bfb412ddb26110d692b92b9a46a689'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def save(name,o):
 with (OUT/name).open('x') as f:json.dump(o,f,ensure_ascii=False,indent=2);f.write('\n')
def status(stage,done,held=(),blockers=()):
 p=OUT.parent;d=p/'status_versions';n=max(int(x.name.split('.')[1]) for x in d.glob('STATUS.*.json'))+1
 o=dict(version=n,current_stage=stage,last_updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),release_directory=str(OUT),completed_items=list(done),failed_or_held_items=list(held),file_paths=[str(OUT)],next_tasks=['새 학습 없이 내부 검토 MVP 연결·통합 smoke 검증'],gpu_required=True,blockers=list(blockers),additional_training=False,pod_lock_touched=False,stop_touched=False)
 for ext,txt in [('json',json.dumps(o,ensure_ascii=False,indent=2)),('md','\n\n'.join(['# RC3 내부 검토 MVP','현재 단계: '+stage,'최종 수정: '+o['last_updated_utc'],'완료: '+'; '.join(done),'보류/실패: '+'; '.join(held),'파일: '+str(OUT),'다음: '+o['next_tasks'][0],'GPU: LIVE smoke에만 필요','Blocker: '+'; '.join(blockers)]))]:
  q=d/f'STATUS.{n:03d}.{ext}'
  with q.open('x') as f:f.write(txt+'\n')
  t=p/f'.STATUS.{ext}.mvp-next';t.symlink_to(q.relative_to(p));os.replace(t,p/f'STATUS.{ext}')
def main():
 original={}
 for folder in [EXP,RC3,OUT.parent/'experiment_rc3_01']:
  for line in (folder/'SHA256SUMS.txt').read_text().splitlines():
   h,n=line.split('  ',1);assert sha(folder/n)==h,n;original[str(folder/n)]=h
 final=read(EXP/'FINAL_RESULT.json');checkpoint=read(EXP/'CHECKPOINT_HASHES.json');saved=read(EXP/'ADAPTER_SAVED.json');loaded=read(EXP/'ADAPTER_RELOADED.json')
 assert final['status']=='COMPLETE_ONE_APPROVED_EXPERIMENT' and loaded['status']=='PASS'
 assert sha(EXP/'CHECKPOINT_HASHES.json')==final['hashes']['checkpoint_hash_receipt_sha256']
 assert sha(EXP/'ADAPTER_SAVED.json')==loaded['adapter_receipt_sha256']
 adapter=Path(loaded['source']);weights=[Path(p) for p,h in saved['file_sha256'].items() if Path(p).name=='adapter_model.safetensors'];assert len(weights)==1
 assert weights[0].parent==adapter and sha(weights[0])==EXPECTED_ADAPTER
 for p,h in saved['file_sha256'].items():assert sha(p)==h
 ready_paths=[p for p in (ROOT/'runtime').glob('recovery*/RUNTIME_READY.json') if sha(p)==final['hashes']['runtime_ready_sha256']];assert len(ready_paths)==1
 runtime_path=ready_paths[0];runtime=read(runtime_path)
 inference=read(EXP/'lora_INFERENCE_RUNTIME.json');assets=inference['runtime']['asset_sha256'];asset_roots={str(Path(p).parent) for p in assets};assert len(asset_roots)==1
 inputs=rows(EXP/'EVALUATION_INPUTS.jsonl');dev=[x for x in inputs if x['cohort']=='DEV'];system=dev[0]['messages'][0]['content'];assert all(x['messages'][0]['content']==system for x in dev)
 with (OUT/'V15_SYSTEM.txt').open('x') as f:f.write(system)
 sources=[EXP/n for n in ['FINAL_RESULT.json','CHECKPOINT_HASHES.json','ADAPTER_SAVED.json','ADAPTER_RELOADED.json','lora_INFERENCE_RUNTIME.json','RESUME_PROVENANCE.json','training/RUN_INPUTS.json','EVALUATION_INPUTS.jsonl','lora_RAW.jsonl','lora_RAW_SEALED.json']]+[runtime_path,RC3/'LORA_SINGLE_CONFIG.json',RC3/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json',RC3/'tokenization.py',RC3/'exporter.py',RC3/'common.py',OUT/'V15_SYSTEM.txt']
 bound={str(p):sha(p) for p in sources};bound.update(assets);bound.update(saved['file_sha256'])
 registry=dict(candidate_id='SOURCEREVIEW_V15_RC3_QWEN27_LORA_INTERNAL_01',status='INTERNAL_MVP_CANDIDATE',registered_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  model=checkpoint['model'],revision=checkpoint['revision'],snapshot=checkpoint['snapshot'],checkpoint_shards=checkpoint['shards'],adapter_directory=str(adapter),adapter_weights=str(weights[0]),adapter_sha256=EXPECTED_ADAPTER,
  adapter_config=str(adapter/'adapter_config.json'),runtime_python=runtime['runtime']['sys_executable'],runtime_record=str(runtime_path),runtime=runtime['runtime'],
  processor_assets_directory=next(iter(asset_roots)),processor_asset_sha256=assets,system_path=str(OUT/'V15_SYSTEM.txt'),system_sha256=sha(OUT/'V15_SYSTEM.txt'),
  input_contract='v15_rc1 native SourceReview user object; fixed system from actual RC3 evaluation',training_contract_manifest=str(RC3/'TRAIN_RELEASE_CANDIDATE_v15_RC3.json'),
  actual_training_record=str(EXP/'training/RUN_INPUTS.json'),generation=inference['generation'],enable_thinking=False,max_total_tokens=4096,
  sealed_tokenization_module=str(RC3/'tokenization.py'),evaluation_inputs_path=str(EXP/'EVALUATION_INPUTS.jsonl'),replay_raw_path=str(EXP/'lora_RAW.jsonl'),
  bindings=bound,engineering_approval=False,official_deployment_approval=False,automatic_feedback_training=False,
  tokenizer_note='Use the original processor assets used by actual RC3 inference; adapter-save tokenizer serialization hashes differ and are recorded separately. No silent switch to saved tokenizer files.')
 assert registry['model']=='Qwen/Qwen3.8-27B' and registry['revision']=='1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
 save('INTERNAL_MVP_CANDIDATE.json',registry);save('PRESERVATION_BEFORE.json',original)
 # Select one per requested workflow from the first matching frozen input order,
 # not from the current integration output or a new model comparison.
 gold={r['id']:r for r in rows(EXP/'EVALUATION_TARGETS.jsonl')};scenarios=[]
 for action in ['NO_ACTION_REQUIRED','REQUEST_EVIDENCE','CHALLENGE']:
  row=next(r for r in dev if gold[r['id']]['expected']['action']==action)
  packet=json.loads(row['messages'][1]['content']);assert json.dumps(packet,ensure_ascii=False,sort_keys=True)==row['messages'][1]['content']
  scenarios.append(dict(id=row['id'],label=action,expected_action=action,packet=packet,input_messages_sha256=hashlib.sha256(json.dumps(row['messages'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()))
 save('SMOKE_SCENARIOS.json',dict(scope='3 integration flows only, not a new independent model performance evaluation',frozen_before_live_smoke=True,scenarios=scenarios))
 compare=read(EXP/'COMPARISON.json');base=read(EXP/'base_SCORED.json')['cases'];lora=read(EXP/'lora_SCORED.json')['cases'];plan=read(EXP/'EVALUATION_PLAN.json');inputby={x['id']:x for x in inputs};raw={k:{r['id']:r for r in rows(EXP/(k+'_RAW.jsonl'))} for k in ['base','lora']}
 selected=set(i for i in plan['cohorts']['DEV_PRIMARY']['reason_ids'] if lora[i]['reason'] is False)
 selected.update(i for group in ['DEV_PRIMARY','DEV_DIAGNOSTIC'] for i in plan['cohorts'][group]['reference_ids'] if lora[i]['reference'] is False)
 records=[]
 for cid in sorted(selected):
  u=json.loads(inputby[cid]['messages'][1]['content']);b=base[cid]['parsed'];l=lora[cid]['parsed'];g=gold[cid]['expected']
  records.append(dict(id=cid,question=u['packet']['review_question'],packet=u,expected=g,base=b,lora=l,
   reason_mismatch=lora[cid]['reason'] is False,reference_mismatch=lora[cid]['reference'] is False,diagnostic=cid in plan['cohorts']['DEV_DIAGNOSTIC']['ids'],
   sufficient_reference_sets=gold[cid]['sufficient_sets'],base_raw_sha256=raw['base'][cid]['output_text_sha256'],lora_raw_sha256=raw['lora'][cid]['output_text_sha256'],
   action_changed=b.get('action')!=l.get('action'),requested_evidence_changed=b.get('requested_evidence')!=l.get('requested_evidence'),
   actual_downstream_routing='No implemented RC3 operational routing found; reason does not determine execution, approval or owner in this MVP. Semantic review may change human interpretation; no automatic action inferred.'))
 save('SAVED_ERROR_REVIEW.json',dict(source_comparison_sha256=sha(EXP/'COMPARISON.json'),records=records,new_generation=False,gold_changed=False,new_scores=False))
 text=['# 保存 결과 기반 남은 오류 검토','기존 점수와 정답을 유지했다. 새 추론이나 재채점 없이 COMPARISON 및 양쪽 raw/scored를 대조했다. 아래 사례 모두 Action 및 요청 자료 ID는 base/LoRA 간 동일하다. 실제 운영 담당자/시험/승인 라우팅 구현은 없으므로 영향을 추정하지 않는다. 오류는 사람의 설명 해석과 인용 근거 선택에 영향을 줄 수 있다.']
 for r in records:
  g,b,l=r['expected'],r['base'],r['lora'];text += ['## '+r['id']+(' — 진단 전용' if r['diagnostic'] else ''),'질문: '+r['question'],
   '검토 제안: '+str(r['packet']['packet']['review_target']),
   'reason: 기대 `'+str(g.get('reason'))+'`, base `'+str(b.get('reason'))+'`, LoRA `'+str(l.get('reason'))+'`.',
   'reference: 충분 집합 '+json.dumps(r['sufficient_reference_sets'])+'; base '+json.dumps(b.get('evidence_refs'))+'; LoRA '+json.dumps(l.get('evidence_refs'))+'.',
   'Action: '+str(l['action'])+' (변화 없음). 요청 자료: '+json.dumps(l.get('requested_evidence',[]))+' (변화 없음). 후속 업무는 사용자 검토 전 자동 확정하지 않는다.']
 regression=next(x for x in records if x['id']=='CASE-RC1-a006de0cbd')
 text+=['## reason 회귀의 입력·기대값·원문','회귀는 METHOD_INTERPRETATION_ERROR → MODE_SELECTION_MISMATCH다. static/dynamic 운용 방식의 기술을 검토하는 질문이며 코드 변경만으로 담당자나 실행을 정하지 않는다.','```json\n'+json.dumps(regression,ensure_ascii=False,indent=2)+'\n```',
 '## reference 오류 영향','주 평가 CASE-RC1-715e076e01, CASE-RC1-976b75a909 및 진단 CASE-RC1-1a26698cec는 제공된 ID를 인용했지만 동결된 충분 집합과 다르다. 미제공 ID 검사만으로 이 의미적 오류를 잡을 수 없다. MVP는 실제 인용된 근거만 펼쳐 보여주고 사람이 충분성을 검토한다. reason 불일치 및 reference 오류로 정답이나 운영 정책을 자동 변경하지 않는다.']
 with (OUT/'SAVED_ERROR_REVIEW_KO.md').open('x') as f:f.write('\n\n'.join(text)+'\n')
 status('RC3_INTERNAL_MVP_CANDIDATE_REGISTERED',['실제 receipt 경로·adapter SHA 검증','INTERNAL_MVP_CANDIDATE 등록','저장 결과 오류 검토·3개 통합 시나리오 고정'],['MVP 실행 연결 및 smoke 검증 진행'])
if __name__=='__main__':main()
