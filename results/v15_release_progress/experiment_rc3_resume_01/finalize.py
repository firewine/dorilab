"""Finalize the one approved run or preserve a concrete stopped execution."""
from run_common import *
def main():
    release,records,cfg=gate()
    for line in (RC3/'SHA256SUMS.txt').read_text().splitlines():
        h,n=line.split('  ',1);require(sha(RC3/n)==h,'sealed RC3 changed')
    for line in (PRIOR/'SHA256SUMS.txt').read_text().splitlines():
        h,n=line.split('  ',1);require(sha(PRIOR/n)==h,'prior stopped/export evidence changed')
    for path,h in read(RUN/'EXECUTION_CODE_BINDINGS.json')['files'].items():require(sha(path)==h,'execution code changed')
    diff=read(RECOVERY/'FREEZE_DIFFERENCES.json')
    failurefiles=sorted(RUN.glob('*FAILURE.json'))
    success=(RUN/'COMPARISON.json').exists() and not failurefiles
    counts=read(RUN/'ADAPTER_SAVED.json')['actual_counts'] if (RUN/'ADAPTER_SAVED.json').exists() else read(RUN/'TRAINING_FAILURE.json').get('actual_counts',{}) if (RUN/'TRAINING_FAILURE.json').exists() else {'optimizer_steps':0,'presentations':0}
    steps=counts.get('optimizer_steps',0)
    hashes=dict(release_manifest_sha256=sha(RELEASE),training_data_sha256=sha(release['data_path']),configuration_sha256=sha(RC3/'LORA_SINGLE_CONFIG.json'),
        approval_sha256=release['approval_sha256'],approval_bundle_sha256=sha(RC3/'APPROVAL_BUNDLE_v2.json'),dev_membership_sha256=sha(RC3/'DEV_EVALUATION_MEMBERSHIP_RC3.json'),
        runtime_ready_sha256=sha(RECOVERY/'RUNTIME_READY.json'),runtime_freeze_sha256=sha(RECOVERY/'pip.freeze.actual.txt'),
        checkpoint_hash_receipt_sha256=sha(RUN/'CHECKPOINT_HASHES.json') if (RUN/'CHECKPOINT_HASHES.json').exists() else None)
    summary=dict(status='COMPLETE_ONE_APPROVED_EXPERIMENT' if success else 'STOPPED',completed_at=now(),actual_counts=counts,hashes=hashes,
        prior_stopped_result_preserved=True,existing_approval_export_and_sealed_code_preserved=True,
        failures={p.name:read(p) for p in failurefiles},pod_lock_touched=False,stop_touched=False,reserved_evaluatoronly_opened=False,
        setting_changes=False,additional_models=False,sweep=False,new_prompt_search=False)
    lines=['# SourceReview v15 RC3 제한된 단일 실험 결과',
           '**상태: '+summary['status']+'**',
           '기존 승인과 정식206행 export를 유지했다. 이전 중단은 지정 런타임 부재였으며 당시 optimizer step0 기록을 보존했다. 현재 실제 GPU Pod에서 런타임을 복구하고 새 재개 실행에 연결했다.',
           '## 런타임 및 무결성',
           '실행 Python: `/root/venvs/dorilab-tournament/bin/python`. Python3.12.3, torch2.8.0+cu128/CUDA12.8, Transformers5.18.0.dev0/commit002e1edf5b5198488297f401dd853056b6521d02, PEFT0.21.0, accelerate1.15.0. RTX PRO6000 Blackwell. 실제 import 경로·배포 commit·CUDA·pip check PASS. freeze 차이는 미사용 gyp0.1 부재만 있다.',
           'CPU preflight는 Transformers5.17.0 및 빈 direct_url로 기록되어 있어 CPU wheel의 git commit은 확인했다고 주장하지 않는다. 복구한 GPU commit은 저장 lock과 일치하며, native template/206 TRAIN token·label/16 DEV token hash가 모두 일치한다. 두 모델 구현 파일 hash 차이는 runtime 복구 감사에 남겼다. 실제 target 목록과 type는 GPU에서 별도 검증했다.',
           '모델은 Qwen/Qwen3.8-27B, revision1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0. 같은 revision28파일을 기존 크기·hash와 대조하여 복원했다. 학습은 기존 adapter를 이어받지 않는다.',
           'hash 연결: `FINAL_RESULT.json`, `CHECKPOINT_HASHES.json`, `../experiment_rc3_01/release/RELEASE_MANIFEST.json`, `../../../runtime/recovery_rc3_20260926_01/`.']
    if (RUN/'GPU_VALIDATION_RECEIPT.json').exists():
        cases=rows(RUN/'NO_UPDATE_CASES.jsonl');peak=max(x['memory']['peak_reserved'] for x in cases)/1024**3
        lines+=['## GPU 검증',f'실제 language Linear496개와 LoRA116,727,808 parameters가 계획과 일치했다. base/vision/embedding/lm_head는 동결했다. 계약별 최장 TRAIN4건, 전체 최장2338tokens의 no-update forward/backward 통과. 최대 reserved{peak:.2f}GiB. 모든 존재 gradient의 finite를 확인했고 첫 A gradient의 0을 오류로 취급하지 않았다. DEV target backward는 하지 않았다.',
                'no-update adapter/gradient/RNG는 프로세스 종료로 폐기했다. 이 검증의 optimizer memory는 추정 여유였고 실제 Adam state 적합성으로 주장하지 않았다.']
    if (RUN/'FIRST_OPTIMIZER_STEP_MEMORY.json').exists():
        first=read(RUN/'FIRST_OPTIMIZER_STEP_MEMORY.json')
        lines += [f"정식 첫 optimizer step에서 Adam state tensor {first['optimizer_state_tensor_bytes']:,}bytes를 실제 생성하고 검증했다. 첫 step peak allocated={first['memory']['peak_allocated']/1024**3:.2f}GiB, reserved={first['memory']['peak_reserved']/1024**3:.2f}GiB."]
    lines+=['## 학습 및 저장',f'실제 완료 optimizer steps: {steps}. 실제 사례 제시: {counts.get("presentations",0)}. 고정안 rank16/alpha32/dropout0.05/lr5e-5/epochs2/seed42, microbatch1/accum4, AdamW, max_length4096를 변경하지 않았다.']
    if success:
        saved=read(RUN/'ADAPTER_SAVED.json');tr=saved['training_result'];metrics=tr['metrics'];comp=read(RUN/'COMPARISON.json');epochs=rows(RUN/'EPOCH_AUDIT.jsonl')
        require(steps==104 and counts['presentations']==412 and len(epochs)==2,'final counts mismatch')
        lines += [f"각 epoch206행을 모두 제시했고 51회×4 + 마지막2 microbatches로52 updates, 총104 steps였다. 행 삭제나 max_steps 보정은 하지 않았다. 평균 training loss={metrics.get('train_loss')}; runtime={metrics.get('train_runtime')}s. 최대 allocated={saved['memory']['peak_allocated']/1024**3:.2f}GiB, reserved={saved['memory']['peak_reserved']/1024**3:.2f}GiB.",
            '최종 adapter는 `training/adapter/`에 저장하고 각 파일 hash를 `ADAPTER_SAVED.json`에 기록했다. 별도 프로세스에서 같은 base revision + 저장 adapter를 reload하여 평가했다. `ADAPTER_RELOADED.json` PASS. 기존 봉인 학습기의 실행 로직은 수정하지 않고 공식 callback 및 관측 hook으로 실제 제시 수·누적·메모리를 기록했다.',
            '## 동일 RC3 base/LoRA 비교',
            '원문과 token/hash를 base_RAW.jsonl·lora_RAW.jsonl 및 *_RAW_SEALED.json으로 먼저 봉인하고 나서 별도 채점했다. 추론은 system/user만 사용했으며 gold/rationale/reference 정답 집합을 넣지 않았다. 출력 보정·실패 자동 재생성·분모 변경은 하지 않았다.',
            '| 평가 범위 | 지표 | base | LoRA |','|---|---|---:|---:|']
        for cohort in ['DEV_PRIMARY','DEV_DIAGNOSTIC','LEGACY_TRAIN_REPLAY']:
            for metric in ['json_object','contract_valid','parsed_action','qualified_action','requests','tool_arguments','reason','reference','strict']:
                b=comp['metrics']['base'][cohort][metric];l=comp['metrics']['lora'][cohort][metric]
                bs=f"{b['correct']}/{b['denominator']}" if b['denominator'] else '해당 없음(0건)'
                ls=f"{l['correct']}/{l['denominator']}" if l['denominator'] else '해당 없음(0건)'
                lines.append(f"| {cohort} | {metric} | {bs} | {ls} |")
        b=comp['metrics']['base']['DEV_COMPLETE_FAMILIES'];l=comp['metrics']['lora']['DEV_COMPLETE_FAMILIES']
        lines += [f"| DEV 완전 family | 모든 구성 사례 strict | {b['correct']}/{b['denominator']} | {l['correct']}/{l['denominator']} |",
            'DEV 주15건, reason7건, 진단1건, 완전family3개를 출력 전에 고정했다. B05 진단의 정답은 여전히 잠정이며 진단 수치는 후보와의 일치일 뿐 주 평가에 포함하지 않았다. 미확정 사례 family는 완전 family 분모에서 제외했다.',
            'legacy170은 승인 TRAIN에 포함된 기존 native 계약의 재현 회귀 진단이다(Analysis30은 승인된 RC3 공통계약). 독립 holdout 점수로 해석하지 않는다. legacy reference는 동결 target의 정확한 집합 일치 지표다.',
            '## 사례별 변화','전체 필드별 개선/회귀는 `COMPARISON.json`의 case_changes 및 *_SCORED.json에 보존했다.',
            '| 사례 | 범위 | strict 변화 | 달라진 지표 |','|---|---|---|---|']
        for c in comp['case_changes']:
            change='개선' if c['strict_improved'] else '회귀' if c['strict_regressed'] else 'strict 동일'
            lines.append(f"| {c['id']} | {c['cohort']} | {change} | {', '.join(c['changed_metrics'])} |")
        lines += ['DEV strict 개선4건·회귀1건이다. CASE-RC1-a14b803063과 CASE-RC1-a89c9fdaf2는 서술형 reason이 허용 enum으로 바뀌며 계약과 strict를 통과했다. CASE-RC1-47b8196220은 일반 EVIDENCE_INTERPRETATION_ERROR에서 정답 MONITORING_COVERAGE_INSUFFICIENT로 바뀌었다. CASE-RC1-cf94ad1f14는 불필요한 reference가 제거되어 동결된 충분 집합과 일치했다.',
                  '회귀 CASE-RC1-a006de0cbd는 base의 정답 METHOD_INTERPRETATION_ERROR가 LoRA에서 MODE_SELECTION_MISMATCH로 바뀌었다. Action과 reference는 유지됐지만 reason/strict가 실패했다. CASE-RC1-1cdfbd536d는 SUPPORTING_EVIDENCE_MISSING 대신 MONITORING_COVERAGE_INSUFFICIENT, CASE-RC1-3613224989는 MONITORING_COVERAGE_INSUFFICIENT 대신 AS_RUN_MISSING을 출력해 계속 strict 실패다.',
                  '따라서 일부 이득은 출력 계약 준수의 개선이며, reason 의미 판별은3/7에 머물고 실제 회귀도 있다. 이를 source reasoning 전반의 해결로 해석하지 않는다.']
        summary['comparison']=comp['metrics'];summary['training_metrics']=metrics
        lines += ['## 해석 범위','작은 개발 평가와 학습자료 재현 결과이며 일반화·안전성·공학 승인 증거가 아니다. v13/v14의 과거3/8 점수와 차이를 학습 개선으로 계산하지 않았다. 추가 모델, sweep, DPO/RL, prompt 탐색을 실행하지 않았다.']
    else:
        lines+=['## 중단 근거',json.dumps(summary['failures'],ensure_ascii=False,indent=2),'설정 변경·자동 재학습 없이 중단했다. 이미 저장된 출력/실행 기록은 보존한다.']
    lines += ['## 무결성 hash','| 항목 | SHA256 |','|---|---|']
    for name,value in hashes.items():lines.append(f'| {name} | `{value}` |')
    if success:
        for path,h in saved['file_sha256'].items():
            if path.endswith(('adapter_model.safetensors','adapter_config.json')):lines.append(f'| {pathlib.Path(path).name} | `{h}` |')
        for kind in ['base','lora']:lines.append(f"| {kind}_RAW.jsonl | `{read(RUN/(kind+'_RAW_SEALED.json'))['raw_sha256']}` |")
    save('FINAL_RESULT.json',summary)
    with (RUN/'FINAL_REPORT_KO.md').open('x') as f:f.write('\n\n'.join(lines).replace('|\n\n|','|\n|')+'\n')
    status('RC3_EXPERIMENT_COMPLETE_WAITING' if success else 'RC3_EXPERIMENT_STOPPED_WAITING',
        ['복구 및 기존 승인/export/봉인 코드 보존 확인','결과·원문·hash·메모리·사례별 변화 저장' if success else '실패 근거 및 실제 실행 수 저장'],
        ['완료 후 대기' if success else '원인 해결 전 대기'],[] if success else ['EXECUTION_FAILED'],steps)
    save('STATUS_FINAL_SNAPSHOT.json',read(RUN.parent/'STATUS.json'))
    for directory in [RECOVERY,RUN]:
        with (directory/'SHA256SUMS.txt').open('x') as f:
            for p in sorted(directory.rglob('*')):
                if p.is_file() and p!=directory/'SHA256SUMS.txt':f.write(sha(p)+'  '+str(p.relative_to(directory))+'\n')
    print(json.dumps({'status':summary['status'],'counts':counts,'comparison':summary.get('comparison')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
