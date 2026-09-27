"""CPU-only proposal builder. No inference, tokenization, scoring or SFT export."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PACK = ROOT / 'research/DoriLab_SourceReview_v13'
AUDIT = ROOT / 'results/source_review_v13_qwen27'

def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

# These are case-authoring decisions keyed by source principle, NOT inference rules.
# Each entry is a review of both contrasting proposal variants and both readiness variants.
FAMILIES = {
 'SR13-TIRS-GSE': ('국소값과 평균', '국소 온도와 평균의 대응을 혼동한 제안은 mapping이다. 평균 일치를 보존하면서 국소 대응 미확정을 표시하는 제안은 적절하다.', '좌표/샘플링 대응표 부재는 mapping, 위치별 출력과 대응표가 모두 있으면 준비 완료다.'),
 'SR13-TIRS-ASBUILT': ('as-built 면적과 원인 단정', '알려진 면적 차이와 미정인 물성 불확실성으로 방사율을 유일 원인으로 단정할 수 없다. 구성은 알려져 있어 configuration 정보 결손 코드가 자동 적용되지 않는다. 일반 해석 오류를 유지한다.', '실제 면적/blanket 경계가 없으면 configuration, revision 일치 형상 자료가 있으면 준비 완료다.'),
 'SR13-TIRS-BASELINE': ('pre-test 비교 방법', 'B에서 형상/접촉까지 바꾼 잔차를 A의 원래 오차라 부르는 것은 방법 위반이다. 원문 V.C의 비교 절차가 판단 전제다.', 'A-derived 실행 결과가 없으므로 AS_RUN을 제안한다. 계산 실행 포함 여부는 v15 승인 항목이다. 자료가 모두 있으면 준비 완료다.'),
 'SR13-TIRS-CULL': ('복사 경로 생략', '합성 관측이 식과 0.5 W 기준을 직접 주므로 k의 숫자만으로 생략하면 방법 위반이다. 계산값/기준은 논문 수치가 아니다.', 'cold-side 온도와 대체 경계가 없으면 boundary, 식/단위/온도가 모두 있으면 준비 완료다.'),
 'SR13-NEA-LEVELS': ('시험 종류의 실증 범위', '진동 통과를 진공 구동 실증으로 확장하므로 MODEL_SCOPE를 제안한다. 실증 범위를 한정하는 반대 variant도 함께 확인한다.', '해당 설치의 진공 구동 실행 자료 결손은 AS_RUN을 제안한다. 해당 run의 압력/온도/명령/이송이 있으면 준비 완료다.'),
 'SR13-NEA-COIL': ('하우징과 코일', '하우징 측정을 코일 한계값과 직접 비교하므로 mapping을 유지한다. 코일 미확정을 보존하는 제안은 적절하다.', '코일 측정 또는 검증된 변환이 없으면 mapping, 코일 측정/보정과 한계가 있으면 준비 완료다.'),
 'SR13-NEA-TRANSLATION': ('회전과 실제 이송', '회전 완료를 별도 물리량인 실제 이송 요구 충족으로 대체하므로 mapping을 제안한다. 유효 encoder의 4 mm 대 12 mm 결손을 보존한다.', '이송 측정도 검증된 운동학 대응도 없으므로 mapping과 monitoring이 모두 직접 관련된다. mapping은 후보이나 LABEL_OVERLAP_PENDING으로 보류한다. 이송/명령/보정이 있으면 준비 완료다.'),
 'SR13-NEA-PLANNED': ('계획과 실행', '승인된 재설계/예정표로 재시험 완료를 주장한다. 현재 질문의 직접 결손인 실행 이력에 따라 AS_RUN을 제안한다. MODEL_SCOPE와 겹치나 실행 기록 결손을 직접 지목할 수 있다.', '실행 ID/로그/측정 결과가 없으면 AS_RUN 유지, 새 run 자료가 있으면 준비 완료이며 공식 closure는 별개다.'),
 'SR13-RHOBC-RAILS': ('제어 도달 범위', '연결이 이미 명시됐으므로 구성 정보 결손은 아니다. 알려진 CAN 전원 스위치를 FRAM에 적용한 일반 해석 오류를 유지한다.', 'switch-to-rail 연결이 없으면 configuration, netlist가 있으면 도달 범위 판단 준비 완료다.'),
 'SR13-RHOBC-MONITOR': ('부품별 고장 관찰', '보드 heartbeat와 전체 전류만으로 ADC 원인을 단정할 수 없어 monitoring을 유지한다.', '부품별 outage 관측이 없으면 monitoring, 동기화된 각 채널 상태가 있으면 준비 완료다.'),
 'SR13-RHOBC-EFFECTS': ('비파괴와 기능중단', '두 interruption 기록은 존재한다. 영구 손상 없음이 기능중단 없음이라는 해석은 일반 오류이며 관측 결손으로 바꾸지 않는다.', '복구/기능 이력이 없으면 monitoring, 해당 이력이 있으면 결과를 구분할 준비가 된 것이다.'),
 'SR13-RHOBC-BOOT': ('복구 경로와 fault model', '주어진 지속성 fault-clear 규칙과 MCU reset 제안의 충돌이므로 method를 유지한다. 관측의 합성 fault model을 논문의 보편 고장 규칙으로 만들지 않는다.', 'power-control 연결 부재에는 configuration이 구체 적용되므로 일반 missing 대신 후보로 제안한다. fault-clear behavior 결손도 요청에 남기며, 단일 코드 대표성은 사람 검토가 필요하다.'),
 'SR13-HYPSO-RANGE': ('실험 온도 범위', '가열 범위로 -15 C 실증을 주장하므로 MODEL_SCOPE 유지. 범위를 한정하는 제안도 확인했다.', '측정 또는 승인된 검증 외삽 어느 하나가 필요하므로 실행 결과 하나로 한정하지 않고 일반 missing 유지. 별도 run 자료가 있으면 준비 완료다.'),
 'SR13-HYPSO-IR': ('측정 신호와 표면 온도', '광학 경로를 통한 신호-물리량 변환이 질문에 직접 연결돼 mapping 유지. 확정되지 않은 window 원인을 단정하지 않는다.', 'window/emissivity/reflection 자료 결손도 mapping 범위다. 모두 공급되면 비교 입력 준비 완료다. IR_PATH_CALIBRATION 요청은 변경하지 않는다.'),
 'SR13-CANYVAL-PRELOAD': ('구속 조건', '원문 미확보. 합성 입력상 preload 차이와 boundary 후보의 관계만 확인할 수 있다.', '원문 미확보. 준비/결손 대조와 기존 boundary 후보는 잠정 기록만 유지한다.'),
 'SR13-CANYVAL-DAMAGE': ('주파수 변화와 원인', '원문 미확보. 원인 미분별의 일반 해석 코드와 구속 효과 코드의 경계를 후속 검토한다.', '원문 미확보. 구속 검사와 damage 분별 자료를 함께 요구하는 일반 missing의 적절성은 미확정이다.'),
 'SR13-PROBAV-SYNC': ('이벤트 시간 연결', '원문 미확보. 합성 문면에서는 시간별 관측 결손의 monitoring이 일반 해석보다 구체적인 후보이나 적용을 보류한다.', '원문 미확보. timestamp/per-event 결손과 준비 상태는 후속 검토 대상으로 남긴다.'),
 'SR13-PROBAV-CENSOR': ('관측 손실', '원문 미확보. 합성 문면에서는 acquisition 공백의 monitoring이 일반 해석보다 구체적인 후보이나 적용을 보류한다.', '원문 미확보. acquisition/recovery 기록의 준비 여부를 원문 확보 후 검토한다.'),
}

REASON_CHANGES = {
 'CASE-acec2b7b89': 'AS_RUN_MISSING',
 'CASE-7e2ce553dd': 'MODEL_SCOPE_EXCEEDED',
 'CASE-c51cdfeccd': 'AS_RUN_MISSING',
 'CASE-d5e287468e': 'MEASUREMENT_MAPPING_MISMATCH',
 'CASE-cf088dcb3c': 'MEASUREMENT_MAPPING_MISMATCH',
 'CASE-6de39fe5d2': 'AS_RUN_MISSING',
 'CASE-9d61b185f8': 'CONFIGURATION_SCOPE_UNRESOLVED',
}
TIRS_RATIONALES = {
 'CASE-79c814ab47': '질문은 제안 자체의 적절성이다. 281/300/319 K의 평균과 300 K 단일 노드의 일치는 유지하되, 제안은 위치별 상관에 사용하기 전에 국소 대응의 미확정을 표시한다. 따라서 이 제안을 반박할 이유가 없어 NO_ACTION_REQUIRED다. 국소 대응 자료가 완비됐다거나 위치별 온도가 일치한다는 결론은 아니다.',
 'CASE-424419171a': '질문은 국소 온도 상관을 위한 입력 준비 여부다. 세 센서 온도와 단일 노드 평균은 있으나 센서 좌표와 모델-센서 샘플링 대응표가 없고 대체 국소 대응도 제공되지 않았다. 필요한 대응 자료가 결손됐으므로 REQUEST_EVIDENCE / MEASUREMENT_MAPPING_MISMATCH로 SENSOR_NODE_MAP을 요청한다. 부적절한 제안이 있었다고 가정해 반박하지 않는다.',
 'CASE-e00c7fe02d': '질문은 입력 준비 여부다. 보정된 국소 온도, 센서 좌표, 모델 샘플링 대응표와 각 대응 위치의 별도 모델 출력이 제공됐다. 해당 비교를 시작할 입력이 있으므로 NO_ACTION_REQUIRED다. 단일 평균으로 국소 차이를 덮었다고 설명하지 않는다. 계산된 일치도, 요구조건 충족 및 공학적 승인은 이 준비 판단의 결론이 아니다.',
}

def public_input(inp, facts):
    # Deliberately has no gold, changeset, rationale or reference-allowlist argument.
    return {'case_id': inp['case_id'], 'packet': copy.deepcopy(inp['packet']),
            'reference_context': [dict(facts[r['fact_id']], reference_id=r['reference_id'])
                                  for r in inp['packet']['source_refs']]}

def main():
    facts = {x['fact_id']: x for x in read(PACK / 'sources/facts.json')}
    spans = {x['fact_id']: x for x in read(AUDIT / 'SOURCE_SPAN_REVIEW_v2.json')}
    impact = read(ROOT / 'experiments/source_review_direct_v14/policy_review_v1/PROPOSED_POLICY_IMPACT.json')['policies']
    # DEV8 membership is already public in the completed subset manifest / HYPSO families.
    changes = []
    for split in ['TRAIN', 'DEV']:
        base = PACK / 'data' / split.lower()
        inputs = {x['case_id']: x for x in rows(base / 'inputs.jsonl')}
        metas = {x['case_id']: x for x in rows(base / 'metadata.jsonl')}
        for g in rows(base / 'gold_candidate.jsonl'):
            cid = g['case_id']; inp = inputs[cid]; p = inp['packet']; m = metas[cid]
            fid, = g['review_note']['supporting_fact_ids']
            title, proposal_note, readiness_note = FAMILIES[fid]
            unavailable = m['source_id'] in {'SR13-CANYVAL', 'SR13-PROBAV'}
            after = copy.deepcopy({k: g[k] for k in ['expected','acceptable_reason_codes','reference_requirement']})
            after['rationale_ko'] = g['review_note']['rationale_ko']
            before = copy.deepcopy(after)
            if cid in REASON_CHANGES:
                after['expected']['reason'] = REASON_CHANGES[cid]
                after['acceptable_reason_codes'] = [REASON_CHANGES[cid]]
            if cid in TIRS_RATIONALES:
                after['rationale_ko'] = TIRS_RATIONALES[cid]
            if cid in REASON_CHANGES:
                after['rationale_ko'] += ' v15 분류 보완: ' + (readiness_note if m['variant_index'] == 2 else proposal_note)
            # Independently inspect all observation text; exclude only the two explicitly inert records.
            obs = [o['evidence_id'] for o in p['observations']
                   if not o['text'].startswith(('The archive index contains', 'The document-control export lists'))]
            assert set(obs) == set(g['review_note']['supporting_observation_ids']), cid
            src = [r['reference_id'] for r in p['source_refs'] if r['fact_id'] == fid]
            method_required = fid == 'SR13-TIRS-BASELINE'
            ref_note = ('원문의 pre-correlation 절차가 어떤 A-derived 비교가 적절한지 정한다. source 방법 전제와 해당 버전/실행 상태 관측을 결합하는 집합만 제안한다. 이 보수적 필수성은 사람 검토 대상이다.' if method_required else
                        '질문의 범위와 아래 관련 관측에 결론의 전제가 명시돼 있다. 관측 집합만으로 판단 가능하며, 같은 검토 원리를 직접 설명하는 해당 source 하나를 결합한 집합도 보강 근거로 제안한다. 다른 source/무관 기록은 포함하지 않는다.')
            sets = [] if unavailable else ([sorted(obs + src)] if method_required else [sorted(obs), sorted(obs + src)])
            metadata = None if unavailable else {
                'mode': 'SUFFICIENT_EXACT_SETS_V15_DRAFT',
                'sufficient_sets': sets, 'permitted_extra': [],
                'source_is_required': method_required,
                'sufficiency_argument': ref_note,
                'observation_support': [{'id': o['evidence_id'], 'text': o['text']} for o in p['observations'] if o['evidence_id'] in obs],
                'source_role': 'REQUIRED_METHOD_PREMISE' if method_required else 'OPTIONAL_DIRECTLY_RELEVANT_CORROBORATION',
                'approved': False}
            if not unavailable:
                after['reference_requirement'] = metadata
            fields = {k: {'before': before[k], 'after': after[k]} for k in before if before[k] != after[k]}
            clauses = ['R1','R2','R3','R4','C1','C2','C3','F1','D1','D2']
            exposure = split == 'DEV' and m['source_id'] == 'SR13-HYPSO'
            record = {
                'case_id': cid, 'split': split, 'family_id': m['family_id'], 'variant_index': m['variant_index'],
                'source_id': m['source_id'], 'program_group': m['program_group'],
                'original': {'case_path': str((base/'inputs.jsonl').relative_to(ROOT)), 'gold_path': str((base/'gold_candidate.jsonl').relative_to(ROOT)),
                             'case_sha256': digest(inp), 'packet_sha256': digest(p), 'gold_sha256': digest(g), 'metadata_sha256': digest(m)},
                'policy_clauses': clauses, 'impact_groups': [k for k,v in impact.items() if cid in v['case_ids']],
                'before': before, 'after_proposed': after, 'field_changes': fields,
                'review_question': p['review_question'], 'review_target': p['review_target'],
                'reason_review': {'decision': 'PROPOSE_CHANGE' if cid in REASON_CHANGES else 'RETAIN_CANDIDATE',
                                 'proposal_variant_reasoning': proposal_note, 'readiness_variant_reasoning': readiness_note,
                                 'unresolved_overlap': cid == 'CASE-cf088dcb3c',
                                 'not_retroactive_v13_rule': True},
                'reference_review': {'status': 'SOURCE_UNAVAILABLE' if unavailable else 'AI_SUFFICIENCY_PROPOSAL',
                                     'metadata_proposed': metadata, 'rationale': ref_note if not unavailable else '원문 미확보로 충분 집합과 source 필수성을 승인하지 않는다.'},
                'system_provenance': {'model_use_or_citation_claim': False,
                                      'provided_source_refs': p['source_refs'], 'provided_observation_ids': [o['evidence_id'] for o in p['observations']],
                                      'authoring_source_principle': facts[fid], 'prior_source_span_audit': spans[fid],
                                      'source_status': 'SOURCE_UNAVAILABLE' if unavailable else 'PRIOR_AI_SOURCE_AUDIT_AVAILABLE_NOT_HUMAN_APPROVAL'},
                'synthetic_assumptions': g['synthetic_assumptions'], 'synthetic_observations': p['observations'],
                'calculation_preserved': g['calculation'],
                'change_reason': (readiness_note if m['variant_index'] >= 2 else proposal_note) + (' 원문 미확보로 변경 적용 보류.' if unavailable else ' 판단용 인용과 provenance를 분리하는 새 평가 metadata 제안.'),
                'post_model_output_review': True, 'dev8_output_seen': exposure,
                'other_case_output_exposure': 'NO_DIRECT_OUTPUT_USED_IN_THIS_BUILD; historical exposure not certified absent',
                'evaluation_role': 'ERROR_INFORMED_REGRESSION' if exposure else ('DEVELOPMENT_NOT_TRAINING' if split == 'DEV' else 'TRAIN_CANDIDATE'),
                'review_status': 'SOURCE_UNAVAILABLE' if unavailable else ('LABEL_OVERLAP_PENDING' if cid == 'CASE-cf088dcb3c' else 'HUMAN_REVIEW_PENDING'),
                'label_status': 'SOURCE_GROUNDED_AI_CANDIDATE', 'human_review_performed': False,
                'training_eligible': False, 'engineering_approved': False,
                'action_observation_calculation_changes': False,
            }
            if unavailable and fid in {'SR13-PROBAV-SYNC','SR13-PROBAV-CENSOR'} and m['variant_index'] == 0:
                record['reason_review']['unapplied_alternative'] = 'MONITORING_COVERAGE_INSUFFICIENT'
            changes.append(record)
    (OUT/'LABEL_CHANGESET_v15.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in changes))

    legacy_path = ROOT/'dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl'
    legacy = rows(legacy_path)
    old_plan = read(AUDIT/'TRAIN_BUILD_CANDIDATE_MEMBERSHIP_v1.json')
    membership = []
    for member in old_plan['rows']:
        role = member['role']
        if role == 'UNRELEASED_TRAIN_CANDIDATE':
            continue
        i = member['parent_row_index_0based'] if role == 'CONTRACT_REPLAY' else member['candidate_representative_row_index_0based']
        row = legacy[i]
        assert digest(row) == member.get('parent_row_sha256', member.get('candidate_row_sha256'))
        answer = json.loads(next(x['content'] for x in row['messages'] if x['role']=='assistant'))
        membership.append({'component': role, 'member_id': member.get('parent_case_id', row['id']),
                           'source_file': str(legacy_path.relative_to(ROOT)), 'source_row_index_0based': i,
                           'source_row_sha256': digest(row), 'source_row_id': row['id'],
                           'input_content_sha256': digest([x for x in row['messages'] if x['role']!='assistant']),
                           'original_occurrences': len(member.get('all_replay_indices', [i])),
                           'original_indices': member.get('all_replay_indices',[i]), 'candidate_repetitions': 1,
                           'action': answer['action'], 'reason': answer.get('reason','NOT_APPLICABLE'),
                           'selection_status': 'PENDING_LEGACY_COMPATIBILITY_AND_RELEASE_REVIEW',
                           'legacy_review_claim_not_promoted_to_human_approval': True,
                           'training_eligible': False, 'engineering_approved': False})
    for c in changes:
        if c['split'] != 'TRAIN':
            continue
        a = c['after_proposed']['expected']
        membership.append({'component':'NEW_TRAIN', 'member_id': c['case_id'], 'family_id':c['family_id'],
                           'source_id':c['source_id'], 'source_file':c['original']['case_path'],
                           'case_sha256': c['original']['case_sha256'], 'gold_sha256':c['original']['gold_sha256'],
                           'proposed_label_view_sha256':digest(c['after_proposed']),
                           'original_occurrences':1, 'candidate_repetitions':1,
                           'action':a['action'], 'reason':a.get('reason','NOT_APPLICABLE'),
                           'selection_status':c['review_status'], 'training_eligible':False,
                           'human_review_performed':False, 'engineering_approved':False})
    def distribution(rr):
        return {'rows':len(rr), 'action':dict(sorted(Counter(x['action'] for x in rr).items())),
                'reason':dict(sorted(Counter(x['reason'] for x in rr).items()))}
    build = {'status':'CANDIDATE_MEMBERSHIP_ONLY_NO_SFT_EXPORT', 'version':'v15-draft',
             'source_legacy_sha256':sha(legacy_path), 'label_changeset_sha256':sha(OUT/'LABEL_CHANGESET_v15.jsonl'),
             'members':membership, 'summary':distribution(membership),
             'component_distributions':{k:distribution([r for r in membership if r['component']==k]) for k in ['CONTRACT_REPLAY','UNIQUE_PHYSICS_STATE','NEW_TRAIN']},
             'counting':{'legacy_original_rows':len(legacy), 'legacy_contract_rows':150, 'legacy_physics_occurrences':96,
                         'legacy_physics_parent_states':20, 'legacy_physics_repeat_histogram':dict(sorted(Counter(x['original_occurrences'] for x in membership if x['component']=='UNIQUE_PHYSICS_STATE').items())),
                         'legacy_contract_distinct_input_hashes':len({x['input_content_sha256'] for x in membership if x['component']=='CONTRACT_REPLAY'}),
                         'new_train_distinct_case_states':48, 'new_train_related_families':12,
                         'physics_and_new_train_state_keys':68, 'all_member_keys':len({x['member_id'] for x in membership}),
                         'candidate_occurrences':len(membership), 'eligible_now':0,
                         'semantic_independence_claim':False,
                         'note':'20 legacy parent states + 48 new question/variant states = 68 engineering state keys, not independent observations. Contract input hashes are exact content counts, not a completed semantic-dedup audit.'},
             'excluded':[{'case_id':c['case_id'],'reason':'DEV_EXCLUDED_FROM_TRAIN','evaluation_role':c['evaluation_role']} for c in changes if c['split']=='DEV'],
             'replay_reduction':{'duplicate_physics_occurrences_not_selected':76,'original_rows_preserved':True},
             'unselected_other_legacy_builds':'coverage246 and other prior variants are not silently unioned; this proposal follows the preserved v13 repeat246 membership plan.',
             'release_gates':['Policy approval','Resolve LABEL_OVERLAP_PENDING','Independent source/case review with reviewer/time and frozen hashes',
                              'Source rights and source/program split audit including authorized evaluator metadata check',
                              'Legacy contract/physics prompt and reason compatibility audit; no automatic relabel',
                              'New versioned export path with original approval gates preserved; no v13 exporter bypass',
                              'Approved single Qwen27 LoRA protocol and separate later GPU authorization'],
             'human_review_performed':False, 'approved_training_experiment':False, 'engineering_approved':False,
             'export_created':False, 'training_executed':False}
    write('TRAIN_BUILD_CANDIDATE_v15.json', build)

if __name__ == '__main__':
    main()
