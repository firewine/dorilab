"""Record the actual bounded user authorization; export with the unchanged RC3 gate.

This CPU-only script does not launch the missing GPU runtime or create a substitute.
"""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parent
PROGRESS = RUN.parent
RC3 = PROGRESS / 'cpu_rc3'
sys.path.insert(0, str(RC3))
from common import sha, read
from exporter import load_candidates, verify_bindings, export_release, verify_training_release
from evaluation_gate import accepted_membership

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def write(name, obj):
    with (RUN / name).open('x') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def status(stage, done, held, blockers, paths):
    directory = PROGRESS / 'status_versions'
    n = max(int(p.name.split('.')[1]) for p in directory.glob('STATUS.*.json')) + 1
    obj = dict(version=n, current_stage=stage, last_updated_utc=now(),
        release_directory=str(RUN), completed_items=done, failed_or_held_items=held,
        file_paths=[str(RUN / p) for p in paths],
        next_tasks=['지정 /root/venvs/dorilab-tournament 런타임이 복구된 후 무결성과 GPU 전제를 재확인',
                    '기존 1회 승인의 범위에서 GPU 검증 → base → 단일 학습 → 저장/reload 평가; 현재 실행 중단·대기'],
        blockers=blockers, gpu_required=True,
        gpu_status='지정 런타임 경로 부재. GPU 할당/추론/forward/backward/학습 모두 미실행.',
        authorization_status='USER_APPROVED_ONE_BOUNDED_EXPERIMENT',
        constraints=dict(lora_executed=False, gpu_inference_executed=False,
                         pod_lock_touched=False, stop_touched=False,
                         reserved_evaluatoronly_opened=False))
    text = '\n\n'.join(['# SourceReview v15 RC3 실행 상태',
        '현재 단계: ' + stage, '최종 수정 시각: ' + obj['last_updated_utc'],
        'GPU 필요 여부: 필요. 지정 런타임 부재로 미실행. 승인 자체는 수신됨.'] +
        [heading + '\n\n' + '\n'.join('- ' + x for x in values)
         for heading, values in [('완료 항목', done), ('실패/보류', held),
         ('파일 경로', obj['file_paths']), ('다음 작업', obj['next_tasks']), ('Blocker', blockers)]]) + '\n'
    for ext, content in [('json', json.dumps(obj, ensure_ascii=False, indent=2)+'\n'), ('md', text)]:
        path = directory / f'STATUS.{n:03d}.{ext}'
        with path.open('x') as f:
            f.write(content)
        temp = PROGRESS / f'.STATUS.{ext}.rc3-experiment-next'
        temp.symlink_to(path.relative_to(PROGRESS))
        os.replace(temp, PROGRESS / ('STATUS.' + ext))
    print(json.dumps({'stage': stage, 'status_version': n}), flush=True)
    return obj

EXPECTED = {
    'APPROVAL_BUNDLE_v2.json': '96fe9d736ff82ded687a73a5a9501827b03df3f3276719e4f622cdb3a6ef3190',
    'TRAIN_RELEASE_CANDIDATE_v15_RC3.json': '0aeb543532fe6f3fb34ca2fe5d118dc6932233f98c9c7be4b472f5aa2a68af5e',
    'LORA_SINGLE_CONFIG.json': '765c78042edbbb76019e50d4478d2e49ea047f2fa6953ed4b3cecfacc40e85fa',
    'DEV_EVALUATION_MEMBERSHIP_RC3.json': '977af1e1ce66eeeab33b4e9480d000779c6639fa93717fcadcd0663d434136b2',
}

def main():
    recorded = now()
    auth = dict(status='EXPLICIT_USER_AUTHORIZATION_RECEIVED', recorded_at_utc=recorded,
        message_event_timestamp_utc=None,
        timestamp_note='정확한 사용자 메시지 전송 시각은 API 문맥에 제공되지 않았다. 기록 시각을 전송 시각으로 주장하지 않는다.',
        author='current conversation user', author_real_name=None,
        message_path=str(RUN / 'USER_AUTHORIZATION.txt'), message_sha256=sha(RUN / 'USER_AUTHORIZATION.txt'),
        approved_file_sha256=EXPECTED, experiment_limit=1,
        independent_case_expert_review_performed=False, engineering_approval=False,
        historical_review_records_modified=False)
    write('AUTHORIZATION_RECEIPT.json', auth)
    runtime = dict(checked_at_utc=now(), requested_runtime='/root/venvs/dorilab-tournament',
        parent_exists=Path('/root/venvs').exists(), runtime_exists=Path('/root/venvs/dorilab-tournament').exists(),
        python_exists=Path('/root/venvs/dorilab-tournament/bin/python').exists(),
        observed_error="ls: cannot access '/root/venvs': No such file or directory",
        cpu_recorded_runtime='/workspace/dorilab/venvs/dorilab-tournament',
        cpu_recorded_python_exists=Path('/workspace/dorilab/venvs/dorilab-tournament/bin/python').exists(),
        alternate_runtime_used_for_gpu=False, runtime_recreated_or_symlinked=False,
        status='BLOCKED_REQUIRED_RUNTIME_MISSING', gpu_hardware_availability_rechecked=False,
        runtime_commit_tokenizer_template_token_ids_compared=False)
    assert not runtime['runtime_exists'], 'Runtime state changed; do not use this stopped-run recorder'
    write('RUNTIME_PATH_CHECK.json', runtime)
    status('RC3_AUTHORIZATION_RECORDED_RUNTIME_BLOCKED', ['실제 사용자 승인 원문 및 기록 시각 보존'],
           ['지정 GPU 런타임 /root/venvs/dorilab-tournament 없음'], ['REQUIRED_GPU_RUNTIME_MISSING'],
           ['AUTHORIZATION_RECEIPT.json', 'USER_AUTHORIZATION.txt', 'RUNTIME_PATH_CHECK.json'])

    actual = {f: sha(RC3 / f) for f in EXPECTED}
    assert actual == EXPECTED, 'RELEASE_HASH_MISMATCH'
    sealed = {}
    for line in (RC3 / 'SHA256SUMS.txt').read_text().splitlines():
        expected, name = line.split('  ', 1)
        path = RC3 / name
        assert sha(path) == expected, 'RC3 sealed file changed: ' + name
        sealed[str(path)] = expected
    bundle = read(RC3 / 'APPROVAL_BUNDLE_v2.json')
    verify_bindings(bundle['evidence_file_sha256'])
    verify_bindings(bundle['implementation_file_sha256'])
    manifest, records = load_candidates()
    write('INTEGRITY_CHECK.json', dict(status='PASS', checked_at_utc=now(), approved_hashes=actual,
        rc3_sealed_files_checked=len(sealed), sealed_file_sha256=sealed,
        evidence_files_checked=len(bundle['evidence_file_sha256']),
        implementation_files_checked=len(bundle['implementation_file_sha256']),
        candidate_count=len(records), candidate_membership_and_native_messages='PASS'))

    catalog_root = Path('/workspace/dorilab/results/source_review_v13_qwen27/cpu_source_audit/verified_sources')
    rights = []
    for sid in ['SR13-NEA', 'SR13-RHOBC', 'SR13-TIRS']:
        path = catalog_root / (sid + '.catalog.json')
        cat = read(path)
        assert cat['distribution'] == 'PUBLIC'
        assert cat['copyright']['determinationType'] == 'PUBLIC_USE_PERMITTED'
        rights.append(dict(source_id=sid, catalog_path=str(path), catalog_sha256=sha(path),
            distribution=cat['distribution'], copyright_metadata=cat['copyright'],
            pdf_sha256=sha(catalog_root / (sid + '.pdf'))))
    write('SOURCE_ACCEPTANCE_SCOPE.json', dict(status='ACCEPTED_FOR_THIS_EXPERIMENT_WITH_DOCUMENTED_LIMITS',
        user_authorization_receipt_sha256=sha(RUN / 'AUTHORIZATION_RECEIPT.json'),
        primary_catalog_evidence=rights, historical_review_reuse=bundle['historical_review_reuse'],
        original_source_states=bundle['source_states'],
        scope='기존 legacy4 검토의 문서화된 범위 재사용, 신규 TRAIN3 PUBLIC_USE_PERMITTED 로컬 catalog 및 원문 감사, DEV2 기존 CC BY4.0 원문 감사. 사용자 명시적 실험용 수락.',
        limits='배포/독립 공학 승인 아님. 새 전문가 사례별 검토 없음. 외부 전체 corpus 또는 RESERVED 무중복을 검증했다고 주장하지 않음. PUBLIC_USE_PERMITTED를 public domain으로 바꾸어 기록하지 않음.',
        unresolved_mandatory_source_rights_items_within_accepted_scope=[]))
    status('RC3_APPROVAL_INTEGRITY_VERIFIED', ['승인 4 hash 일치', 'RC3 봉인 파일·연결 근거 및 206행 native 메시지 검사 통과',
           '기존 source 근거 확인 및 이번 실험용 수락 범위 기록'],
           ['GPU runtime 검사 불가: 지정 경로 없음'], ['REQUIRED_GPU_RUNTIME_MISSING'],
           ['INTEGRITY_CHECK.json', 'SOURCE_ACCEPTANCE_SCOPE.json', 'AUTHORIZATION_RECEIPT.json'])

    semantics = dict(reviewer='current conversation user (explicit batch authorization)', reviewed_at=recorded,
        reviewed_at_semantics='authorization recorded_at_utc; exact message event time unavailable',
        approval_kind='EXPERIMENTAL_BATCH_ACCEPTANCE_OF_BOUND_RECORDS',
        independent_case_expert_review_performed=False,
        authorization_receipt_path=str(RUN / 'AUTHORIZATION_RECEIPT.json'),
        authorization_receipt_sha256=sha(RUN / 'AUTHORIZATION_RECEIPT.json'))
    approval = read(RC3 / 'RELEASE_APPROVAL_PENDING_v2.json')
    approval.update(semantics)
    approval['status'] = 'APPROVED_FOR_EXPERIMENTAL_TRAINING'
    for key in ['source_program_split_audit_pass', 'legacy_corpus_audit_pass', 'candidate_label_policy_accepted',
                'approved_training_experiment', 'analysis_contract_change_accepted', 'prior_review_reuse_accepted']:
        approval[key] = True
    for case in approval['case_reviews']:
        case.update(semantics)
        case['decision'] = 'APPROVED_FOR_TRAINING'
    for source in approval['source_reviews']:
        source.update(semantics)
        source['content_verified'] = True
        source['rights_approved'] = True
        source['split_role_verified' if source['use_role'] == 'LEGACY_REPLAY' else 'split_novelty_verified'] = True
        source['scope'] = 'User acceptance of documented evidence and audit scope for this single experiment; not a new independent source/case review.'
    approval['note'] = 'Actual explicit user batch authorization, bound to unchanged RC3 hashes. Per-case entries inherit this batch acceptance; they are not claims of 206 newly performed human reviews. Historical files and dates unchanged.'
    write('RELEASE_APPROVAL.json', approval)
    evaluation = read(RC3 / 'EVALUATION_APPROVAL_PENDING.json')
    plan = read(RC3 / 'DEV_EVALUATION_MEMBERSHIP_RC3.json')
    evaluation.update(semantics)
    evaluation.update(status='APPROVED_FOR_EVALUATION',
        accepted_primary_strict_ids=plan['primary_strict_ids'],
        accepted_reason_review_ids=plan['primary_reason_applicable_ids'])
    write('EVALUATION_APPROVAL.json', evaluation)
    frozen = accepted_membership(evaluation)
    write('FROZEN_EVALUATION_MEMBERSHIP.json', frozen)
    release = export_release(RUN / 'RELEASE_APPROVAL.json', RUN / 'release')
    verified, exported = verify_training_release(RUN / 'release/RELEASE_MANIFEST.json')
    assert len(exported) == 206
    actions = dict(collections.Counter(json.loads(r['messages'][-1]['content'])['action'] for r in records))
    routes = dict(collections.Counter(r['contract_route'] for r in records))
    write('EXPORT_VERIFICATION.json', dict(status='PASS', release_manifest_sha256=sha(RUN / 'release/RELEASE_MANIFEST.json'),
        data_sha256=release['data_sha256'], count=len(exported), actions=actions, contract_routes=routes,
        original_gate_used=True, approval_and_current_input_gold_hashes='PASS',
        held_family_excluded_count=len(manifest['excluded_family_members']), dev_excluded=True,
        train_source='unchanged explicit RC2/RC3 TRAIN allowlist only', reserved_evaluatoronly_opened=False))
    for path, expected in sealed.items():
        assert sha(path) == expected, 'sealed RC3 file modified during export: ' + path
    write('FINAL_RESULT.json', dict(status='STOPPED_BEFORE_GPU_REQUIRED_RUNTIME_MISSING',
        recorded_at_utc=now(), authorization_received=True, training_export_rows=206,
        optimizer_steps=0, example_presentations=0, training_started=False,
        base_inference_started=False, gpu_forward_backward_started=False,
        adapter_saved=False, adapter_reloaded=False, loss=None, measured_gpu_memory=None,
        runtime_hash=None, model_weight_hashes_reverified=False,
        planned_model_revision=read(RC3 / 'LORA_SINGLE_CONFIG.json')['revision'],
        planned_optimizer_steps=104, planned_example_presentations=412,
        metric_results=None, experiment_execution_count=0, rc3_preservation='PASS',
        blocker='REQUIRED_GPU_RUNTIME_MISSING',
        missing_path='/root/venvs/dorilab-tournament',
        no_settings_changed=True, pod_lock_touched=False, stop_touched=False))
    report = f'''# RC3 승인·export 완료, GPU 실행 전 중단

사용자의 제한된 1회 실험 승인을 원문과 hash로 보존했다. 네 승인 hash와 RC3 봉인 {len(sealed)}개 파일, 연결 근거가 일치하며 기존 release gate를 그대로 통과했다. 과거 reviewer/reviewed_at은 변경하지 않았다. 새 승인 기록의 reviewer는 현재 대화 사용자이고, reviewed_at은 승인 **기록** 시각이다. 메시지의 정확한 전송 시각은 제공되지 않아 null로 남겼다. 사례별 항목은 이번 묶음 수락의 연결이며 새 전문가 검토 이력이 아니다.

206행을 release/train.jsonl로 정식 export하고 저장 후 기존 gate로 재검증했다. Action 분포: {json.dumps(actions, ensure_ascii=False)}. 계약별 분포: {json.dumps(routes, ensure_ascii=False)}. 보류 세 family 12건 및 DEV 제외, 기존 TRAIN allowlist만 사용했다. RESERVED/EvaluatorOnly는 열지 않았다. 데이터 SHA256: `{release['data_sha256']}`.

DEV 주15·reason7·진단1·완전 family3의 기존 membership/reference 승인과 hash를 고정했다. 아직 모델 출력과 채점은 없다. legacy 회귀 실행 및 계측은 GPU 단계가 열리지 않아 미수행이다.

신규 TRAIN3의 기존 NASA catalog는 PUBLIC / PUBLIC_USE_PERMITTED이고, legacy4는 문서화된 기존 검토를 재사용했다. DEV2는 기존 원문 CC BY4.0 감사와 이번 명시적 실험용 수락 범위다. 이 범위에서 추가로 확인된 미해결 source 필수항목은 없다. 독립 법률 판단이나 공학 승인으로 확대하지 않는다.

**중단 사유: 지정 `/root/venvs/dorilab-tournament` 및 상위 `/root/venvs`가 없다.** CPU 기록 경로 `/workspace/dorilab/venvs/dorilab-tournament`는 존재하지만 지정 GPU 환경으로 대체하지 않았다. 따라서 GPU runtime commit/tokenizer/template/token ID 대조, model shard 재검증, 실제 target/type/파라미터 검사, no-update forward/backward와 첫 optimizer step 메모리 검증은 모두 미실행이다. GPU 하드웨어 사용 불가라고 판단한 것이 아니다.

실제 optimizer step 0, 사례 제시 0, base/LoRA 출력 0, adapter 저장/reload 없음. loss·메모리·Action/요청/도구 인자/reason/reference/strict 점수와 개선·회귀는 미측정이다. 계획104 steps·412회 제시는 실행 결과가 아니다. 기존 단일 설정은 변경하지 않았으며 승인된 실험 실행 횟수는 아직 0이다.

지정 런타임이 복구되면 현재 승인과 release hash를 재확인하고 승인 범위의 GPU 검증부터 이어갈 수 있다. 이 실행은 여기서 중단·대기한다. Pod 잠금과 STOP은 건드리지 않았다.
'''
    with (RUN / 'RUN_REPORT_KO.md').open('x') as f:
        f.write(report)
    final = status('RC3_APPROVED_EXPORTED_STOPPED_RUNTIME_MISSING',
        ['실제 사용자 묶음 승인 및 4 hash 확인 완료', '기존 gate 통과: 206행 정식 export 및 저장 후 검증',
         'DEV 15/7/1/family3 승인 membership 고정', 'RC3 기존 산출물 보존 확인'],
        ['지정 GPU runtime 경로 없음', 'GPU 검증·base/LoRA 학습·평가·adapter 저장/reload 미실행'],
        ['REQUIRED_GPU_RUNTIME_MISSING'],
        ['RUN_REPORT_KO.md', 'AUTHORIZATION_RECEIPT.json', 'RELEASE_APPROVAL.json',
         'EVALUATION_APPROVAL.json', 'release/RELEASE_MANIFEST.json', 'EXPORT_VERIFICATION.json',
         'RUNTIME_PATH_CHECK.json', 'FINAL_RESULT.json', 'SHA256SUMS.txt'])
    write('STATUS_FINAL_SNAPSHOT.json', final)
    files = sorted(p for p in RUN.rglob('*') if p.is_file())
    with (RUN / 'SHA256SUMS.txt').open('x') as f:
        for path in files:
            f.write(sha(path) + '  ' + str(path.relative_to(RUN)) + '\n')
    print(json.dumps({'result': 'STOPPED_REQUIRED_RUNTIME_MISSING', 'export_rows': 206,
        'actions': actions, 'artifact_files_hashed': len(files)}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
