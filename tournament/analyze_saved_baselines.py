#!/usr/bin/env python3
"""Audit saved inference only; diagnostic extraction never changes official scores."""
import argparse, collections, json, re
from pathlib import Path
import dorilab_model_tournament as t

ROOT = Path('/workspace/dorilab/tournament/baseline_v1')
PROJECT = Path('/workspace/dorilab/dorilab-gemma4-e4b')

def inspect_output(row):
    parsed = row['score']['parsed']
    if isinstance(parsed, dict):
        return parsed, 'official_json'
    raw = row['raw_output']
    # Only observed empty channel prefixes; never discard free-form reasoning.
    channel_prefix = False
    for prefix in ('<|channel>thought\n<channel|>', '<channel|>'):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            channel_prefix = True
            break
    if channel_prefix:
        try:
            value = t.strict_json_text(raw)
            if isinstance(value, dict):
                return value, 'channel_prefix_diagnostic_only'
        except (ValueError, RuntimeError):
            pass
    match = re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*', raw, re.S)
    if match:
        try:
            value = t.strict_json_text(match.group(1))
            if isinstance(value, dict):
                return value, 'channel_and_fence_diagnostic_only' if channel_prefix else 'markdown_fence_diagnostic_only'
        except (ValueError, RuntimeError):
            pass
    return None, 'unreadable_or_noncontract_output'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--models', nargs='+', default=list(t.REGISTRY))
    args = ap.parse_args()
    schema, historical, inputs, frozen = t.validate_eval(PROJECT)
    assert frozen == t.read_json(ROOT / 'RUN_MANIFEST.json')['frozen_inputs_sha256']
    doctor = t.read_json(ROOT / 'DOCTOR.json')
    scorer = t.import_scorer(PROJECT)
    report = {'official_scores_unchanged': True, 'frozen_inputs_verified': True, 'models': {}, 'historical': historical['models']}
    cases = []
    for slug in args.models:
        dest = ROOT / slug
        summary = t.read_json(dest / 'summary.json')
        lock = t.read_json(dest / 'MODEL_LOCK.json')
        load = t.read_json(dest / 'LOAD_REPORT.json')
        assert summary['revision'] == lock['revision'] == doctor['models'][slug]['revision']
        assert summary['model'] == lock['model'] == t.REGISTRY[slug]['model']
        assert load == summary['load_report']
        for obj in [summary, lock]:
            assert obj['dtype'] == 'bfloat16' and obj['quantization'] is None
            assert obj['decoding'] == 'greedy_do_sample_false' and obj['max_new_tokens'] == 384
            assert obj['training_executed'] is False
        rows_all = []
        for suite, items in inputs.items():
            rows = t.read_jsonl(dest / 'results' / f'{suite}.jsonl')
            assert [r['case_id'] for r in rows] == [i['case_id'] for i in items]
            assert scorer.aggregate(rows) == summary['suites'][suite]
            rows_all += rows
            for row, item in zip(rows, items):
                assert row['messages_sha256'] == t.digest(item['messages'])
                assert row['revision'] == summary['revision'] and row['model'] == summary['model'] and row['adapter'] is None
                assert row['prompt_tokens'] + 384 <= 2048
                assert scorer.score(item, row['raw_output'], schema, row['hit_generation_limit']) == row['score']
                actual, view = inspect_output(row)
                expected = row['score']['expected']
                alternatives = item['case'].get('acceptable_answers') or [expected]
                tags = []
                if row['score']['validation_error']: tags.append('output_contract_invalid')
                if row['hit_generation_limit']: tags.append('generation_limit')
                if actual is None:
                    tags.append('semantic_unresolved')
                else:
                    if actual.get('action') != expected['action']: tags.append('action_mismatch')
                    if expected['action'] == 'CHALLENGE' and actual.get('action') == 'NO_ACTION_REQUIRED': tags.append('wrong_acceptance')
                    if expected['action'] == 'NO_ACTION_REQUIRED' and actual.get('action') != 'NO_ACTION_REQUIRED': tags.append('unnecessary_intervention')
                    if 'reason' in expected and actual.get('reason') != expected['reason']: tags.append('reason_mismatch')
                    if suite != 'contract20' and not any(scorer.field_equal('evidence_refs', e['evidence_refs'], actual.get('evidence_refs')) for e in alternatives): tags.append('reference_mismatch')
                    for key in expected:
                        if key not in ('action','reason','evidence_refs') and not scorer.field_equal(key,expected[key],actual.get(key)): tags.append('field_mismatch:'+key)
                cases.append({'model':slug,'suite':suite,'case_id':row['case_id'],'official_strict':row['score']['strict_contract_pass'],'official_action':row['score']['action_correct'],'official_wrong_acceptance':row['score']['wrongly_accepts_refuted_proposal'],'diagnostic_view':view,'tags':tags,'expected':expected,'diagnostic_actual':actual,'validation_error':row['score']['validation_error'],'raw_output':row['raw_output']})
        own = [c for c in cases if c['model']==slug]
        totals = {k:sum(s[k] for s in summary['suites'].values()) for k in ['cases','action_correct','strict_contract_pass','reference_exact','reference_eligible','wrongly_accepts_refuted_proposal','schema_and_refs_valid','reason_joint_correct','reason_cases','generation_seconds']}
        totals.update(peak_allocated_GiB=max(r['peak_allocated_GiB'] for r in rows_all),load_seconds=load['load_seconds'],seconds_per_case=totals['generation_seconds']/84,generated_tokens=sum(r['generated_tokens'] for r in rows_all))
        report['models'][slug]={'verified_cases':84,'revision':lock['revision'],'totals':totals,'suites':summary['suites'],'diagnostic_counts':dict(collections.Counter(tag for c in own for tag in c['tags'])),'diagnostic_views':dict(collections.Counter(c['diagnostic_view'] for c in own)),'wrong_acceptance_cases':[c['case_id'] for c in own if 'wrong_acceptance' in c['tags']],'action_mismatch_cases':[c['case_id'] for c in own if 'action_mismatch' in c['tags']],'reason_confusions':dict(collections.Counter(f"{c['expected'].get('reason')} -> {c['diagnostic_actual'].get('reason')}" for c in own if 'reason_mismatch' in c['tags']))}
    args.output.mkdir(parents=True,exist_ok=False)
    t.write_json(args.output/'analysis.json',report)
    with (args.output/'case_analysis.jsonl').open('x') as f:
        for c in cases: f.write(json.dumps(c,ensure_ascii=False)+'\n')
    lines=['# 저장된 baseline 검증 및 사례 분석','','공식 점수는 원본 그대로다. 코드 블록 내부 JSON은 오류 분류를 위한 진단에만 사용하며 공식 성공으로 재채점하지 않았다. 파싱 불가 사례의 잘못된 정상 판정 0건은 안전성 증거가 아니다.','','| 모델 | Action /84 | refs /64 | strict /84 | 공식 잘못된 수용 | 진단상 잘못된 수용 | 생성 초 | peak GiB |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for slug,m in report['models'].items():
        v=m['totals']; lines.append(f"| {slug} | {v['action_correct']} | {v['reference_exact']} | {v['strict_contract_pass']} | {v['wrongly_accepts_refuted_proposal']} | {len(m['wrong_acceptance_cases'])} | {v['generation_seconds']:.2f} | {v['peak_allocated_GiB']:.2f} |")
    lines+=['','reference exact의 대상은 NS10와 before40 64건이다. Contract20은 별도의 legacy 필드 비교다. 시간은 모델 로딩을 제외한 생성 시간이며 최초 warmup을 포함한다. VRAM은 PyTorch peak allocated 값이다. 기존 E4B LoRA는 다른 환경의 NF4 기록이므로 속도와 메모리를 직접 순위 비교하지 않는다.']
    for slug,m in report['models'].items():
        lines+=['',f'## {slug}','',f"오류 분류: `{json.dumps(m['diagnostic_counts'],ensure_ascii=False)}`",'', '| 사례 | 분류 | 기대 Action → 출력 Action | 기대 reason → 출력 reason |','|---|---|---|---|']
        for c in cases:
            if c['model']!=slug or c['official_strict']: continue
            actual=c['diagnostic_actual'] or {}
            lines.append(f"| {c['case_id']} | {', '.join(c['tags'])} | {c['expected']['action']} → {actual.get('action','해석 불가')} | {c['expected'].get('reason','—')} → {actual.get('reason','—')} |")
    (args.output/'CASE_ANALYSIS_KO.md').write_text('\n'.join(lines)+'\n')
    for slug,m in report['models'].items(): print(slug,json.dumps(m,ensure_ascii=False))

if __name__=='__main__': main()
