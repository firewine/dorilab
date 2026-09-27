"""CPU-only native-message review and immutable candidate manifests."""
import collections
import copy
import json
import re
import sys
from build_release import ROOT, OUT, RC1, V15, PACK, LEGACY, HOLDS, read, rows, sha, digest, write, textfile, status, now

def assistant(row):
    return next(m for m in row['messages'] if m['role']=='assistant')

def output_check(target, user, reasons, physics=False):
    packet=user['case_packet'] if physics else user['packet']
    claim=user['claim_id'] if physics else packet['claim_id']
    action=target['action']; fields={'action','claim_id','evidence_refs'}
    assert action in {'CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'}
    if action!='NO_ACTION_REQUIRED':
        fields.add('reason');assert target['reason'] in reasons
    provided={r['reference_id'] for r in user['reference_context']}
    provided|={r['evidence_id'] for r in packet['evidence' if physics else 'observations']}
    if action=='REQUEST_EVIDENCE':
        fields.add('requested_evidence')
        allowed=user['allowed_request_ids'] if physics else [r['request_id'] for r in packet['request_catalog']]
        requested=target['requested_evidence'];assert requested and len(set(requested))==len(requested) and set(requested)<=set(allowed)
    refs=target['evidence_refs']
    assert set(target)==fields and target['claim_id']==claim
    assert refs and len(refs)==len(set(refs)) and set(refs)<=provided

def native_contract_semantics(role, state, target):
    """Check supplied conditions without changing data; alias assumption explicitly reported."""
    action=None; reason=None; extras={}; assumptions=[]
    if role=='ANALYSIS':
        # This branch is a diagnostic interpretation, not an approved alias or relabel.
        assumptions.append('requirement_s interpreted as required_s; actual system does not declare this mapping')
        if state.get('requirement_s') is None or state.get('actual_by_axis') is None:
            action='REQUEST_EVIDENCE';reason='DURATION_INPUT_MISSING'
        elif (state.get('tool_result') or {}).get('status')=='CURRENT': action='NO_ACTION_REQUIRED'
        else:
            action='CALL_TOOL';extras={'tool':'compare_axis_durations','arguments':{'required_s':state['requirement_s'],'actual_by_axis':state['actual_by_axis']}}
    elif role=='EVIDENCE':
        if 'current_requirement' in state:
            conflict=state['current_requirement']['duration']!=state['current_procedure']['duration']
            action='PROPOSE_FINDING' if conflict else 'NO_ACTION_REQUIRED'
            if conflict: extras={'finding_type':'PROCEDURE_REQUIREMENT_CONFLICT'}
        elif 'as_run' in state:
            action='REQUEST_EVIDENCE' if state['as_run'] is None else 'NO_ACTION_REQUIRED'
            if action=='REQUEST_EVIDENCE':reason='AS_RUN_MISSING'
        elif 'current_configuration' in state:
            a=state.get('applicability_review') or {}
            fits=state['current_configuration']==state['evidence_configuration'] or (a.get('status')=='APPROVED_EQUIVALENT' and state['claim_scope'] in a.get('approved_scopes',[]))
            action='NO_ACTION_REQUIRED' if fits else 'REQUEST_EVIDENCE'
            if not fits:reason='CONFIGURATION_MISMATCH'
        elif 'current_requirement_revision' in state:
            a=state.get('supersession_review') or {}
            fits=state['current_requirement_revision']==state['evidence_requirement_revision'] or (a.get('status')=='APPROVED_APPLICABLE' and state['claim_scope'] in a.get('approved_scopes',[]))
            action='NO_ACTION_REQUIRED' if fits else 'REQUEST_EVIDENCE'
            if not fits:reason='REVISION_MISMATCH'
    elif role=='CRITIC':
        finding=state['finding'];tool=state.get('tool_result');evidence=state.get('evidence')
        if 'current_configuration' in state:
            a=state.get('applicability_review') or {}
            fits=state['current_configuration']==state['evidence_configuration'] or (a.get('status')=='APPROVED_EQUIVALENT' and finding['scope'] in a.get('approved_scopes',[]))
            action='NO_ACTION_REQUIRED' if fits else 'CHALLENGE'
            if not fits:reason='CONFIGURATION_MISMATCH'
        elif tool:
            if 'satisfied' in finding['statement'].lower() and tool['verdict']=='NON_COMPLIANT':
                action='CHALLENGE';reason='EVIDENCE_CONTRADICTION';extras={'valid_scope':tool['affected_axes']}
            elif set(finding['scope'])!=set(tool['affected_axes']):
                action='CHALLENGE';reason='SCOPE_ERROR';extras={'valid_scope':tool['affected_axes']}
            else:action='NO_ACTION_REQUIRED'
        elif evidence:action='NO_ACTION_REQUIRED'
        else:action='REQUEST_EVIDENCE';reason='SUPPORTING_EVIDENCE_MISSING'
    assert action is not None, (role,state)
    expected={'action':action,**extras}
    if reason:expected['reason']=reason
    return {'matches_under_stated_interpretation':target==expected,'diagnostic_expected':expected,'assumptions':assumptions}

PHYSICS_NOTES={
 'PHY-VBX1-P02':'구성별 C² 선정 근거의 부재/제공. legacy 전용 FORCE_LIMIT_BASIS_UNRESOLVED는 원래 system에 선언되어 있다.',
 'PHY-EE02-P02':'채널 시간 이력과 자극 시간 로그의 부재/제공. monitoring 적용과 readiness Action이 양립한다.',
 'PHY-VBX1-P07':'계산 전 필요한 범위·분포 가정의 부재/제공. 계산 실행 결과로 AS_RUN을 확대할 이유가 없다.',
 'PHY-EE02-P01':'자극 중 변화가 있고 사후 baseline은 복구됐다. A의 사건 부정은 CHALLENGE이나 source 방법 위반과 일반 관측 오해의 reason 경계가 남는다. B는 관측과 복구를 구분한다.',
 'PHY-TH01-P05':'부품별 소산 전력·위치 자료의 부재/제공. legacy 전용 power reason은 온도 mapping 오류와 다르다.',
 'PHY-TH01-P03':'정상상태만으로 capacitance 식별을 제안한 A와 cold-soak transient를 사용하는 B. legacy 전용 parameter reason이 구체적이다.',
 'PHY-VBX1-P01':'지지 impedance 차이를 무시한 force 등가 주장/적절한 제한. v15 boundary 정의와 양립한다.',
 'PHY-TH01-P02':'미확인 background radiation을 배제한 원인 단정/환경 확인 제안. boundary reason과 양립한다.',
 'PHY-EE03-P01':'SEL current 기록은 있고 SET 출력 획득은 꺼져 있다. 질문은 변환 계수보다 관측 coverage이므로 monitoring이 직접적이다.',
 'PHY-VBX1-P03':'turnover mode 정의에 맞는 effective mass가 있는 모드/단순 최저 주파수 대조. mode selection이 구체적이다.'}

def compatibility():
    membership=read(RC1/'PILOT_TRAIN_MEMBERSHIP.json');legacy=rows(LEGACY)
    members=membership['ceiling_206_members']
    previews={m['member_id']:m for m in rows(RC1/'MODEL_INPUT_PREVIEWS.jsonl')}
    labels={m['case_id']:m for m in rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')}
    prompt=(RC1/'prompts/direct_v15_pilot_rc1.txt').read_text()
    vdefs=json.loads(prompt.split('Reason definitions:\n',1)[1]);assert vdefs==read(RC1/'reason_definitions_rc1.json')
    entries=[];systems={};exact=collections.defaultdict(list);users=collections.defaultdict(list);alias_rows=[];held_alias=[];failures=[]
    reason_differences=[]
    for m in members:
        mid=m['member_id'];messages=previews[mid]['messages']
        assert digest(messages)==previews[mid]['messages_sha256']
        assert [x['role'] for x in messages]==['system','user']
        system,user=[x['content'] for x in messages]
        sh=digest(system)
        systems.setdefault(sh,{'system_content':system,'member_ids':[]})['member_ids'].append(mid)
        blocks=[];warnings=[];source_assistant=None
        if m['component']=='NEW_TRAIN':
            target=labels[mid]['expected'];u=json.loads(user)
            assert system==prompt
            output_check(target,u,vdefs)
            assert set(target['evidence_refs']) in [set(s) for s in labels[mid]['reference_requirement']['sufficient_sets']]
            note='v15 실제 system/user + AI candidate expected를 대조. 모델 assistant 생성은 미실행. generic reason 3건은 해당 구체 reason 조건이 충족되지 않는 관측 오해; 자동 변경 없음.'
            result={'v15_output_contract':'PASS','native_output_contract':'PASS'}
        else:
            row=legacy[m['source_row_index_0based']]
            assert digest(row)==m['source_row_sha256']
            assert [x for x in row['messages'] if x['role']!='assistant']==messages
            source_assistant=assistant(row);target=json.loads(source_assistant['content'])
            assert target['action']==m['action'] and target.get('reason','NOT_APPLICABLE')==m['reason']
            assert target['action'] in system and (not target.get('reason') or target['reason'] in system)
            if m['component']=='UNIQUE_PHYSICS_STATE':
                u=json.loads(user);defs=dict(re.findall(r'^- ([A-Z_]+): (.+)$',system,re.M))
                output_check(target,u,defs,physics=True)
                if mid=='PHY-EE02-P01-A':blocks.append('B01_GENERAL_SPECIFIC_REASON')
                note=PHYSICS_NOTES[mid.rsplit('-',1)[0]]
                result={'native_output_contract':'PASS','v15_output_contract':'PASS' if target.get('reason') in vdefs or 'reason' not in target else 'LEGACY_ONLY_REASON_NOT_A_NATIVE_ERROR'}
                for reason in sorted(defs.keys() & vdefs.keys()):
                    d={'reason':reason,'legacy_definition':defs[reason],'v15_definition':vdefs[reason]}
                    if d not in reason_differences:reason_differences.append(d)
            else:
                role=re.search(r'<ROLE>(.*?)</ROLE>',user).group(1);u=json.loads(user.split('STATE:',1)[1])
                semantic=native_contract_semantics(role,u,target)
                if not semantic['matches_under_stated_interpretation']:failures.append(mid)
                result={'native_output_contract':'PASS_DECLARED_ACTION_REASON','v15_output_contract':'INCOMPATIBLE_IF_SYSTEM_REPLACED','semantic_check':semantic}
                note='role별 legacy 출력 계약 유지 필요. v15 필드/Action 계약으로 직접 export 불가.'
                if role=='ANALYSIS' and 'requirement_s' in u and 'required_s' not in u:
                    alias_rows.append(mid)
                    if target['action']!='REQUEST_EVIDENCE':
                        blocks.append('B02_ANALYSIS_FIELD_ALIAS');held_alias.append(mid)
                    else:warnings.append('W01_ANALYSIS_ALIAS_SAME_ACTION_UNDER_BOTH_READINGS')
            assert source_assistant['role']=='assistant'
        entry=dict(member_id=mid,component=m['component'],source_locator={k:m[k] for k in ['source_file','source_row_index_0based','source_row_sha256'] if k in m},
                   input_messages=messages,input_messages_sha256=digest(messages),system_content_sha256=digest(system),user_content_sha256=digest(user),
                   original_assistant_message=source_assistant,assistant_target=target,assistant_target_sha256=digest(target),
                   assistant_provenance='ORIGINAL_LEGACY_ASSISTANT_CONTENT' if source_assistant else 'RC1_AI_CANDIDATE_EXPECTED_NOT_MODEL_OUTPUT',
                   comparison=result,semantic_review_ko=note,blocker_ids=blocks,warning_ids=warnings,auto_relabel_performed=False)
        entries.append(entry);exact[digest(messages)].append(entry);users[digest(user)].append(entry)
    assert not failures,failures
    collisions=[{'ids':[e['member_id'] for e in es],'input_sha256':key} for key,es in exact.items() if len({digest(e['assistant_target']) for e in es})>1]
    assert not collisions,collisions
    b1={'id':'B01_GENERAL_SPECIFIC_REASON','status':'OPEN','kind':'POTENTIAL_SEMANTIC_CONFLICT','affected_member_ids':['PHY-EE02-P01-A'],'resolution':'동일 관측과 source 방법 아래 일반 EVIDENCE_INTERPRETATION_ERROR 유지의 정당성 또는 METHOD_INTERPRETATION_ERROR 적용을 명시적으로 판정. 원본 label 자동 변경 금지.'}
    b2={'id':'B02_ANALYSIS_FIELD_ALIAS','status':'OPEN','kind':'POTENTIAL_NATIVE_INPUT_CONTRACT_AMBIGUITY','affected_member_ids':held_alias,'schema_affected_member_ids':alias_rows,'resolution':'requirement_s→required_s alias와 missing-input/CURRENT-result 우선순위를 명시적으로 결정한 새 계약 또는 기존 계약 유지 판정 필요. 10 CALL_TOOL, 10 NO_ACTION_REQUIRED를 잠정 보류. REQUEST_EVIDENCE 10건은 양쪽 해석에서 Action 일치.'}
    audit={'created_at_utc':now(),'scope':'150 legacy contract + 20 unique legacy physics + 36 new TRAIN; no inference','entries':entries,'system_variants':systems,'shared_reason_definitions':reason_differences,'same_full_input_conflicting_targets':collisions,
           'same_user_across_distinct_system_groups':[[e['member_id'] for e in es] for es in users.values() if len({e['system_content_sha256'] for e in es})>1],
           'row_blockers':[b1,b2],'counts':{'ceiling':206,'contract':150,'physics':20,'new_train':36,'row_blocked':sum(bool(e['blocker_ids']) for e in entries),'clear_of_row_blockers':sum(not e['blocker_ids'] for e in entries),'legacy_native_system_variants':len(systems)-1,'analysis_alias_schema_rows':len(alias_rows)},
           'training_export_created':False,'labels_modified':False,'human_review_performed':False}
    assert audit['counts']['row_blocked']==21 and len(alias_rows)==30 and len(held_alias)==20
    write('LEGACY_V15_MESSAGE_AUDIT.json',audit)
    table='\n'.join(f"| {e['member_id']} | {e['assistant_target']['action']} / {e['assistant_target'].get('reason','—')} | {', '.join(e['blocker_ids']) or '이번 대조에서 blocker 미발견'} |" for e in entries if e['component']=='UNIQUE_PHYSICS_STATE')
    defs='\n'.join(f"| {d['reason']} | {d['legacy_definition']} | {d['v15_definition']} |" for d in reason_differences)
    report=f'''# Legacy–v15 실제 메시지 호환성 — RC2

검사 시각: {now()}. legacy contract150 + physics20의 원래 system/user/assistant와 v15 TRAIN36의 실제 system/user 및 기존 AI candidate expected를 대조했다. v15 모델 assistant 출력은 생성하지 않았다. 원본 메시지·label은 변경하지 않았다.

**상한206 중 행 단위 잠정 blocker 21건, 이번 검사에서 blocker가 발견되지 않은 후보 185건. 학습 사용 가능 행수는 기존 release gate 미충족으로 0건이다.** 기존 RC1의 205 선정안은 보존하고 추가 발견을 이 RC2에만 기록한다.

## 동일 입력 조건 검사

system+user의 canonical SHA256으로 동일 입력/상이 target을 전수 검사했고 충돌 그룹은 0개였다. 실제 legacy system은 5종(Contract 3 role, Physics 2 active role), v15 system은 1종이다. 단순히 동일 입력 중복이 없다는 결과가 의미적 호환성을 보장하지 않으므로 아래 규칙·질문·관측도 대조했다.

`LEGACY_V15_MESSAGE_AUDIT.json`에 206행의 원래 입력 메시지, legacy assistant 원문, candidate target, 해시, 행 단위 결과를 기록했다. hash 함수는 UTF-8 canonical JSON(sort_keys=True, compact separators, ensure_ascii=False)이며 파일 SHA256과 구분한다. v15 candidate target은 추론 결과가 아니다.

## B01 — 일반 reason / source 방법 reason 경계 (1건, 잠정)

`PHY-EE02-P01-A`: 자극과 같은 시각에 functional channel이 변했고 사후 baseline은 복구됐다. 제안은 복구를 근거로 susceptibility event가 없었다고 선언한다. 실제 legacy assistant는 CHALLENGE / EVIDENCE_INTERPRETATION_ERROR이다. legacy system은 이 일반 코드에 source interpretation method 위반도 명시적으로 포함한다. v15는 구체 코드가 적용되지 않을 때만 일반 코드를 허용하며 METHOD_INTERPRETATION_ERROR를 제공한다. 제공 reference는 자극 중 데이터, 전후 baseline, sweep timing을 함께 평가하는 방법이다.

Action CHALLENGE에는 이견이 없지만 같은 조건의 방법 위반을 어느 reason으로 분류할지는 미결이다. 실제 legacy 계약 아래 확정 오류라고 단정하지 않는다. 구체 우선 정책으로 직접 재사용하기 전 판정이 필요하다. paired B는 관측과 복구를 구분하므로 보류하지 않는다. 자동 수정 없음.

## B02 — Analysis 입력 필드 이름과 우선순위 (20건, 잠정)

Analysis 실제 user 30건 모두 `requirement_s`를 쓰지만 system은 `required_s`를 복사하고 그것이 없으면 REQUEST_EVIDENCE / DURATION_INPUT_MISSING이라고 지시한다. alias 선언은 없다. `EV05-160`은 requirement_s=85, actual_by_axis={{X:85,Y:85,Z:85}}, tool_result=null이며 assistant는 CALL_TOOL의 arguments.required_s=85를 출력한다. 키를 문자 그대로 판정하면 missing-input 분기, 의미상 별칭을 허용하면 기존 CALL_TOOL이 된다.

10건은 CALL_TOOL, 10건은 CURRENT result를 근거로 NO_ACTION_REQUIRED다. 후자에는 system의 missing-input 지시와 CURRENT-result 지시 중 우선순위도 모호하다. 20건을 잠정 보류한다. 나머지 10건은 REQUEST_EVIDENCE로 양쪽 해석의 Action이 같아 warning만 기록한다. 값·필드·정답은 자동 수정하지 않았다. 이 발견은 v15가 만든 오류라는 뜻이 아니라 실제 legacy 메시지 내부의 계약 모호성이다.

해당 20건: {', '.join(held_alias)}.

## 출력 계약 차이와 라우팅

| 구성 | 원래 출력 계약 | v15 통일 시 문제 | 이번 처리 |
|---|---|---|---|
| contract150 | CALL_TOOL 10 / PROPOSE_FINDING 15 포함, NO_ACTION은 action만, 일부 valid_scope/tool/arguments/finding_type | v15 3 Action 및 필수 claim_id/evidence_refs와 충돌. claim/reference 입력 자체도 없음 | 원래 system/user/assistant 유지. 차이 자체로 150건 모두 label 오류 판정하지 않음 |
| physics20 | v15와 같은 3 Action/주요 필드, legacy 전용 reason 포함 | force-limit/power/parameter/probability 등 4개 target은 v15 enum에 없음 | 원래 system reason 정의 유지. enum 부재만으로 제거 안 함 |
| TRAIN36 | v15 prompt, source fact+packet, AI candidate expected | generic fallback 및 충분 reference 집합 준수 필요 | 구조·reference ID·후보 충분 집합 검증. 승인 완료로 승격하지 않음 |

모든 contract150은 alias를 명시적으로 가정하는 진단 해석에서 target과 일치했다. 이 진단을 alias 승인으로 사용하지 않는다. 공통 system 강제, legacy target의 v15 필드 자동 추가, reason enum 일괄 치환은 금지한다. 향후 exporter/collator의 행별 system 보존과 대화 경계·assistant-only loss 검증이 완료되어야 혼합 학습을 실행할 수 있다.

## 공유 reason 정의 실물

| reason | 실제 legacy physics system | 실제 v15 system |
|---|---|---|
{defs}

legacy AS_RUN_MISSING은 Evidence role의 missing as_run 입력(5건)이며 v15의 physical execution 결손(3건)과 충돌을 발견하지 못했다. 계산 실행까지 AS_RUN을 확대하지 않았다. legacy Critic의 SUPPORTING_EVIDENCE_MISSING(10건)은 근거 부재 일반 fallback이며 현재 입력에는 더 구체적인 v15 결손을 강제할 정보가 없다.

v15 일반 reason 후보 3건도 확인했다. 알려진 radiator 면적 차이를 버린 단일 원인 추론, 제공 배선과 다른 watchdog 전원 주장, 영구 손상 없음으로 일시 중단을 부정한 주장이다. 각 질문에 더 직접적인 적용 조건을 충족하는 구체 reason은 이번 대조에서 확인하지 못했다. 특히 마지막 사례는 EE02의 명시된 source 평가 절차와 다르다. 기존 label은 유지한다.

## Physics20 개별 결과

| 상태 | 원래 assistant | 판정 |
|---|---|---|
{table}

범위 한계: AI CPU 내용 검토이며 모델의 계약 준수 성능, 독립 사람 검토, legacy 원문 전체 재검토를 뜻하지 않는다. RESERVED/EvaluatorOnly 및 기존 모델 raw output은 열지 않았다.
'''
    textfile('LEGACY_V15_COMPATIBILITY.md',report)
    status('01_COMPATIBILITY_COMPLETE', ['206행 실제 입력/target 대조 완료','동일 system+user의 상충 target 0그룹','잠정 blocker 21행 기록; 자동 수정 없음'],
           ['B01 physics 1행','B02 Analysis 20행; 추가 10행 warning'],[str(OUT/'LEGACY_V15_COMPATIBILITY.md'),str(OUT/'LEGACY_V15_MESSAGE_AUDIT.json')],
           ['206행 TRAIN manifest 확정','DEV16 원문·동결 검증 완료'],['B01_GENERAL_SPECIFIC_REASON','B02_ANALYSIS_FIELD_ALIAS'])

def distribution(ms):
    return {'rows':len(ms),'actions':dict(sorted(collections.Counter(m['action'] for m in ms).items())),'reasons':dict(sorted(collections.Counter(m['reason'] for m in ms).items()))}

def train():
    parent=read(V15/'TRAIN_BUILD_CANDIDATE_v15.json');old=read(RC1/'PILOT_TRAIN_MEMBERSHIP.json')
    changes={c['case_id']:c for c in rows(V15/'LABEL_CHANGESET_v15.jsonl')}
    audit=read(OUT/'LEGACY_V15_MESSAGE_AUDIT.json');byid={e['member_id']:e for e in audit['entries']}
    labels={x['case_id']:x for x in rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')}
    excluded=[];members=[]
    for m0 in parent['members']:
        m=copy.deepcopy(m0);mid=m['member_id']
        if m['component']=='NEW_TRAIN':
            fact=changes[mid]['system_provenance']['authoring_source_principle']['fact_id']
            m['authoring_fact_family']=fact
            if fact in HOLDS:
                m.update(release_status='HELD_BY_USER_WHOLE_FAMILY',blocker_ids=['H01_USER_FAMILY_HOLD'])
                excluded.append(m);continue
        e=byid[mid]
        assert m['action']==e['assistant_target']['action'] and m['reason']==e['assistant_target'].get('reason','NOT_APPLICABLE')
        m.update(release_status='HELD_PENDING_COMPATIBILITY_DECISION' if e['blocker_ids'] else 'CANDIDATE_PENDING_RELEASE_GATES',blocker_ids=e['blocker_ids'],warning_ids=e['warning_ids'],
                 contract_route='v15_pilot_rc1' if m['component']=='NEW_TRAIN' else 'legacy_original_messages',
                 candidate_repetitions=1,input_messages_sha256=e['input_messages_sha256'],assistant_target_sha256=e['assistant_target_sha256'],
                 training_eligible=False,engineering_approved=False)
        if m['component']=='NEW_TRAIN':m.update(candidate_label_file=str(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl'),candidate_label_sha256=digest(labels[mid]))
        members.append(m)
    assert len(members)==206 and len(excluded)==12
    assert collections.Counter(m['authoring_fact_family'] for m in excluded)=={f:4 for f in HOLDS}
    assert {m['member_id'] for m in members}=={m['member_id'] for m in old['ceiling_206_members']}
    clear=[m for m in members if not m['blocker_ids']];held=[m for m in members if m['blocker_ids']]
    manifest={'format':'DoriLab.SourceReview.TRAIN_RELEASE_CANDIDATE.v15.rc2','created_at_utc':now(),'status':'CPU_CANDIDATE_FROZEN_EXECUTION_BLOCKED','members':members,'excluded_family_members':excluded,
              'counts':{'candidate_ceiling':206,'contract150':150,'legacy_physics20':20,'new_train36':36,'user_family_excluded':12,'compatibility_held_within_ceiling':len(held),'no_row_blocker_candidates':len(clear),'approved_training_rows':0,'exported_sft_rows':0},
              'candidate_distribution':distribution(members),'no_row_blocker_distribution':distribution(clear),'held_distribution':distribution(held),
              'component_distributions':{c:{'ceiling':distribution([m for m in members if m['component']==c]),'no_row_blocker':distribution([m for m in clear if m['component']==c])} for c in ['CONTRACT_REPLAY','UNIQUE_PHYSICS_STATE','NEW_TRAIN']},
              'parent_218_manifest':{'path':str(V15/'TRAIN_BUILD_CANDIDATE_v15.json'),'sha256':sha(V15/'TRAIN_BUILD_CANDIDATE_v15.json')},
              'rc1_manifest':{'path':str(RC1/'PILOT_TRAIN_MEMBERSHIP.json'),'sha256':sha(RC1/'PILOT_TRAIN_MEMBERSHIP.json'),'selected_count_preserved_as_history':205},
              'message_audit':{'path':str(OUT/'LEGACY_V15_MESSAGE_AUDIT.json'),'sha256':sha(OUT/'LEGACY_V15_MESSAGE_AUDIT.json')},
              'all_candidate_rows_are_training_ready':False,'human_review_performed':False,'auto_relabel_performed':False,'dev_cases_in_training':[],
              'selection_note':'206 is the requested maximum manifest, not an SFT export. 185 are clear of row-specific blockers only; use/review/export gates remain. Do not silently train the 185-row subset.',
              'held_family_scope':'Exclude the 12 case members of the three authoring families. Their public source fact can remain a supplied distractor in other unchanged inputs; no prompt rewriting was requested.',
              'release_gates':['Resolve B01/B02 or explicitly choose a revised membership in a new version','Existing label/source/use approval records must bind current hashes','Native-system exporter/collator and token/loss/EOS checks','Freeze and report one Qwen27 LoRA setting before executing training']}
    write('TRAIN_RELEASE_CANDIDATE_v15.json',manifest)
    status('02_TRAIN_MANIFEST_COMPLETE', ['TRAIN 상한206=contract150+physics20+새TRAIN36 manifest 고정','3 family 12건 완전 제외','행 blocker 없는 후보185 / 잠정보류21 / 실행가능0 구분'],
           ['잠정 보류21건 원본 label 유지','기존 학습 release 승인·export 검증 미충족'],[str(OUT/'TRAIN_RELEASE_CANDIDATE_v15.json')],
           ['DEV16 source release 문서 작성','CPU 검증·최종 checksum 봉인'],['B01_GENERAL_SPECIFIC_REASON','B02_ANALYSIS_FIELD_ALIAS','B03_EXISTING_RELEASE_GATES','B04_EXPORT_AND_PREFLIGHT'])

def inspect_dev():
    for inp,label,meta in zip(rows(RC1/'dev16/INPUTS.jsonl'),rows(RC1/'dev16/GOLD_AI_CANDIDATE.jsonl'),rows(RC1/'dev16/METADATA.jsonl')):
        p=inp['packet']
        print(json.dumps({'id':inp['case_id'],'source':meta['source_id'],'fact':meta['support_fact_id'],'source_required':meta['source_required'],'question':p['review_question'],'proposal':p['review_target']['text'],'observations':[o['text'] for o in p['observations'] if o['evidence_id'] in label['expected']['evidence_refs']],'target':label['expected']},ensure_ascii=False))

def dev():
    verification=read(OUT/'sources/PRIMARY_SOURCE_VERIFICATION.json')
    oldfreeze=read(RC1/'dev16/PRE_OUTPUT_FREEZE.json')
    for name,h in oldfreeze['file_sha256'].items():assert sha(RC1/name)==h
    inputs=rows(RC1/'dev16/INPUTS.jsonl');labels=rows(RC1/'dev16/GOLD_AI_CANDIDATE.jsonl');metas=rows(RC1/'dev16/METADATA.jsonl');previews=rows(RC1/'dev16/MODEL_INPUT_PREVIEWS.jsonl')
    facts=read(RC1/'dev16/INPUT_FACTS.json');defs=read(RC1/'reason_definitions_rc1.json')
    assert len(inputs)==len(labels)==len(metas)==len(previews)==16
    checks=[]
    for inp,label,meta,preview in zip(inputs,labels,metas,previews):
        cid=inp['case_id'];assert cid==label['case_id']==meta['case_id']==preview['case_id']
        assert digest(inp)==meta['input_sha256'] and digest(label)==meta['label_sha256']
        assert digest(preview['messages'])==meta['messages_sha256']==preview['messages_sha256']
        assert preview['messages'][0]['content']==(RC1/'prompts/direct_v15_pilot_rc1.txt').read_text()
        user=json.loads(preview['messages'][1]['content'])
        assert user['packet']==inp['packet']
        refs=inp['packet']['source_refs']
        assert user['reference_context']==[dict(facts[r['fact_id']],reference_id=r['reference_id']) for r in refs]
        output_check(label['expected'],user,defs)
        req=label['reference_requirement'];assert req['approved'] is False and set(label['expected']['evidence_refs']) in [set(s) for s in req['sufficient_sets']]
        assert not label['human_review_performed'] and not label['training_eligible']
        source=next(s for s in verification['sources'] if s['source']['source_id']==meta['source_id'])
        assert meta['source_pdf_sha256']==source['reacquisition']['sha256']
        supporting=[r['reference_id'] for r in refs if r['fact_id']==meta['support_fact_id']]
        assert supporting
        if meta['source_required']:assert all(set(supporting)&set(s) for s in req['sufficient_sets'])
        else:assert any(not any(x.startswith('REF-') for x in s) for s in req['sufficient_sets'])
        assert any(a['fact_id']==meta['support_fact_id'] for a in source['anchor_checks'])
        checks.append({'case_id':cid,'parent_case_id':meta['parent_case_id'],'source_id':meta['source_id'],'fact_id':meta['support_fact_id'],'source_required':meta['source_required'],'source_pdf_sha256':meta['source_pdf_sha256'],'input_sha256':digest(inp),'label_sha256':digest(label),'messages_sha256':digest(preview['messages']),'field_reference_and_source_bindings':'PASS','label_status':'UNCHANGED_AI_CANDIDATE_NOT_APPROVED'})
    trainmeta=rows(PACK/'data/train/metadata.jsonl');legacy=rows(LEGACY)
    ts={m['source_id'] for m in trainmeta};tp={m['program_group'] for m in trainmeta};tf={m['family_id'] for m in trainmeta}
    for r in legacy:ts.update(r.get('metadata',{}).get('source_ids',[]));tp.update(r.get('metadata',{}).get('program_groups',[]))
    ds={m['source_id'] for m in metas};dp={m['program_group'] for m in metas};df={m['family_id'] for m in metas}
    split={'source_overlap':sorted(ts&ds),'program_overlap':sorted(tp&dp),'family_overlap':sorted(tf&df),'scope':'Public TRAIN48 metadata + legacy repeat246 metadata + frozen public DEV16; no evaluator content','reserved_evaluatoronly_opened':False,'independent_generalization_claim':False}
    assert not any(split[k] for k in ['source_overlap','program_overlap','family_overlap'])
    assert {m['member_id'] for m in read(OUT/'TRAIN_RELEASE_CANDIDATE_v15.json')['members']}.isdisjoint({m['case_id'] for m in metas}|{m['parent_case_id'] for m in metas})
    copy_names=['dev16/INPUTS.jsonl','dev16/GOLD_AI_CANDIDATE.jsonl','dev16/METADATA.jsonl','dev16/MODEL_INPUT_PREVIEWS.jsonl','dev16/INPUT_FACTS.json','prompts/direct_v15_pilot_rc1.txt','POLICY_v15_RC1.md','reason_definitions_rc1.json']
    copies={}
    for name in copy_names:
        p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write((RC1/name).read_bytes())
        assert sha(p)==sha(RC1/name);copies[name]=sha(p)
    write('dev16/VALIDATION_RC2.json',{'created_at_utc':now(),'case_count':16,'source_dependent_cases':8,'observation_sufficient_controls':8,'case_checks':checks,'split_check':split,'labels_changed':False,'replacement_sources_needed':False,'human_label_approval':False})
    semantic={'created_at_utc':now(),'review_method':'AI content comparison, no model output or automatic relabel','blockers':[{'id':'B05_DEV_GENERAL_SPECIFIC_REASON','case_id':'CASE-RC1-1a26698cec','status':'OPEN_POTENTIAL_REASON_OVERLAP','current_reason':'EVIDENCE_INTERPRETATION_ERROR','candidate_specific_reason_to_review':'TEST_ARTIFACT_UNMODELED','basis_ko':'관측에는 진동 후 frequency 변화와 restraint-tension 변화가 모두 기록되어 있다. 제안은 cracking을 유일 원인으로 단정한다. v15는 identified test-setup effect를 무시하는 추론에 TEST_ARTIFACT_UNMODELED를 제공하므로 일반 reason fallback 조건 충족 여부를 재검토해야 한다. 실제 균열 또는 유일 원인은 단정하지 않는다. CHALLENGE Action과 원문 확보는 영향 없음.','label_modified':False}],
              'other_family_notes':['HRM direct-contact/edge-to-edge 판단은 논문 방법 명칭 해석이며 현행 METHOD_INTERPRETATION_ERROR와 부합한다.','PROBA-V static/dynamic은 실행된 operation pattern의 방법 해석이며 기계적 mode pairing으로 자동 변경하지 않는다.','CANYVAL causal input readiness는 원인 분별 자료가 없는 상태이며 이번 단계에서 SUPPORTING_EVIDENCE_MISSING을 자동 변경하지 않는다.'],
              'evaluation_release_ready':False,'source_acquisition_ready_cases':16,'semantic_review_held_cases':1}
    write('dev16/SEMANTIC_REVIEW_RC2.json',semantic)
    freeze={'created_at_utc':now(),'status':'CPU_SOURCE_REVALIDATED_AI_CANDIDATE_FROZEN_NOT_EXECUTION_RELEASE','parent_freeze_path':str(RC1/'dev16/PRE_OUTPUT_FREEZE.json'),'parent_freeze_sha256':sha(RC1/'dev16/PRE_OUTPUT_FREEZE.json'),
            'file_sha256':{**copies,'sources/PRIMARY_SOURCE_VERIFICATION.json':sha(OUT/'sources/PRIMARY_SOURCE_VERIFICATION.json'),'dev16/VALIDATION_RC2.json':sha(OUT/'dev16/VALIDATION_RC2.json'),'dev16/SEMANTIC_REVIEW_RC2.json':sha(OUT/'dev16/SEMANTIC_REVIEW_RC2.json')},
            'case_count':16,'human_review_performed':False,'labels_changed':False,'model_outputs_seen_for_this_candidate':False,'inference_executed':False,'search_snippet_label_approval':False}
    write('dev16/PRE_OUTPUT_FREEZE_RC2.json',freeze)
    source_rows='\n'.join(f"| [{s['source']['source_id']}]({s['reacquisition']['url']}) | {s['source']['doi']} | {s['page_count']} | {s['reacquisition']['bytes']:,} | `{s['reacquisition']['sha256']}` |" for s in verification['sources'])
    case_rows='\n'.join(f"| {c['case_id']} | {c['fact_id']} | {'필수' if c['source_required'] else '관측 충분'} |" for c in checks)
    textfile('DEV16_SOURCE_RELEASE_CANDIDATE.md',f'''# DEV16 source release candidate — RC2

{now()} 기준 **CANYVAL/PROBA-V 실제 원문 PDF 2개를 현재 Pod에서 HTTP 200으로 재확보했다. 대체 source는 필요하지 않다.** Web reader에서는 두 asset URL을 열지 못했지만 같은 공개 URL의 직접 HTTP PDF 응답을 저장하고 본문을 새로 추출했다. 검색 snippet은 source 확보나 label 승인에 사용하지 않았다.

| 원문 | DOI | 쪽수 | bytes | SHA256 |
|---|---|---:|---:|---|
{source_rows}

첫 페이지의 실제 제목·저자·DOI를 대조했다. CANYVAL은 Park/Kim/Park의 *Novel Structure and Thermal Design and Analysis for CubeSats in Formation Flying*, PROBA-V는 Mattos 외의 *Investigation of Single-Event Effects for Space Applications: Instrumentation for In-Depth System Monitoring*이다. 두 PDF 모두 RC1과 byte-identical이며 첫 페이지에 CC BY 4.0 고지가 있다. 이 사실을 프로젝트 학습자료 사용 승인이나 사람 label 검토 기록으로 바꾸지 않는다.

## 본문 근거와 DEV 목적

| source / 본문 위치 | 확인 내용 | 연결한 DEV 역할 |
|---|---|---|
| CANYVAL §5.1, PDF 17–18쪽 | HRM 직접 접촉과 간접 wire 연결, 세 constraint 표현 및 조임/제작 상태의 영향 | 논문 HRM 표현 방법 명명·재현 입력 준비 4건 |
| CANYVAL §6, PDF 23쪽 | 손상 없음과 고유진동수 변화가 함께 보고됨 | 합성 관측의 단일 원인 확정 한계를 보는 대조 4건 |
| PROBA-V §2.4 및 §5, PDF 4·12쪽 | 여러 관찰점의 일관된 timestamp로 전류와 논리 event를 연결 | 합성 event 시간 귀속 자료 부재/준비 대조 4건 |
| PROBA-V §3.2, PDF 6쪽 | static write–wait–read와 dynamic 연속 read/write 및 read-error 보고를 구분 | 논문 고유 mode 정의·관찰 경로 재현 4건 |
| PROBA-V §4.1, PDF 9쪽 | 잦은 SEL 재시작이 induced error 획득을 줄일 수 있음 | 입력에 함께 제공되는 censoring fact provenance 확인 |

두 PDF의 40쪽을 pypdf 6.1.0으로 새로 추출했다. 6개 fact에 연결된 8개 anchor 검증을 `sources/PRIMARY_SOURCE_VERIFICATION.json`에 남겼다(일부 동일 쪽/anchor 재사용). 도표 수치를 새 정답으로 전사하지 않았고 visual review 완료를 주장하지 않는다. 숫자·사건이 합성인 DEV 관측은 원문에서 실제 일어난 사건이라고 취급하지 않는다.

## 동결과 label 경계

기존 RC1의 4 family × 4 variant = 16건을 bytes 그대로 새 `dev16/`에 복사했다. 8건은 방법 정의에 원문이 필요하고, 8건은 관측만으로 충분한 대조 사례다. 입력·label·metadata·prompt hash, claim/request/reference 필드 및 source PDF 연결을 재검증했다. Action은 CHALLENGE4 / REQUEST_EVIDENCE4 / NO_ACTION_REQUIRED8이다.

`dev16/PRE_OUTPUT_FREEZE_RC2.json`은 이번 원문 검증 결과와 동일 label을 묶는 새 동결 manifest이다. Label은 **AI 후보**, 충분 reference 집합은 `approved=false`, 사람 검토·학습/평가 사용 승인 완료는 아니다. 기존 RC1 label을 자동 수정하지 않았다. 원문 방법에 대한 의존성은 AI 내용 검토이며 모델 ablation을 실행한 것이 아니다.

공개 TRAIN48과 legacy repeat246의 metadata 범위에서 DEV source/program/family 교집합은 0이고 TRAIN 후보와 DEV case ID 교집합도 0이다. 외부 전체 corpus의 독립성은 주장하지 않는다. RESERVED/EvaluatorOnly를 열어 이 검사를 확장하지 않았다.

| DEV case | 근거 fact | 충분 근거에서 source 역할 |
|---|---|---|
{case_rows}

## B05 — DEV reason 잠정 중첩 1건

`CASE-RC1-1a26698cec`에는 frequency 변화와 restraint-tension 변화가 함께 기록됐는데 cracking을 유일 원인으로 선언한다. 기존 target은 CHALLENGE / EVIDENCE_INTERPRETATION_ERROR다. v15의 TEST_ARTIFACT_UNMODELED가 알려진 test-setup effect를 무시한 추론에 적용될 가능성이 있으므로 일반 fallback 조건을 재검토해야 한다. **확정 오류나 자동 relabel이 아니다.** Action CHALLENGE와 원문 확보 결과는 유지한다. `dev16/SEMANTIC_REVIEW_RC2.json`에 근거를 기록하고 평가 릴리스 전 blocker로 둔다.

실패/보류: 원문 확보 실패는 해소됐다. DEV16 중 위 1건의 reason 경계 및 전체 label/충분 근거의 기존 release 검토는 남는다. GPU 추론·LoRA·추가 prompt 탐색을 실행하지 않았다.
''')
    status('03_DEV16_SOURCE_RELEASE_COMPLETE', ['두 원문 재확보·본문 확인 완료, 대체 source 불필요','DEV16 bytes 유지와 새 freeze 완료','8 method-dependent+8 observation control, TRAIN 교집합0 재검증'],
           ['DEV16 label/충분 reference 집합은 미승인 AI 후보; B05 잠정 reason 중첩1건','TRAIN compatibility blocker21건 유지'],[str(OUT/'DEV16_SOURCE_RELEASE_CANDIDATE.md'),str(OUT/'dev16/PRE_OUTPUT_FREEZE_RC2.json')],
           ['최종 CPU 검증','blocker 및 학습 준비 조건 보고','checksum 봉인 후 대기'],['B01_GENERAL_SPECIFIC_REASON','B02_ANALYSIS_FIELD_ALIAS','B03_EXISTING_RELEASE_GATES','B04_EXPORT_AND_PREFLIGHT','B05_DEV_GENERAL_SPECIFIC_REASON'])

if __name__=='__main__':
    assert sys.argv[1] in {'compatibility','train','inspect_dev','dev'}
    globals()[sys.argv[1]]()
