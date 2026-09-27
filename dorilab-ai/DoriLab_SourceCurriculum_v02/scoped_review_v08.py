#!/usr/bin/env python3
"""DoriLab scoped-review integration smoke. No training or changes to dcurr.

From the existing project root:
  python scoped_review_v08.py prepare
  python scoped_review_v08.py run

Uses the reviewed v06 LAST-view packets, the audited v07 gate, and the existing
v02 evaluator for twelve new e2 generations. Labels are used by the offline
scorer, never by the scope gate or the output-validation function. This is a
batch integration smoke, not an autonomous engineering approval service.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'scoped-review-integration-v0.8.0'
DEFAULT_OUT = 'data/scoped_review_v08'
APP = 'data/applicability_probe_v06'
AUDIT = 'data/scope_gate_v07'
E2_SHA = 'c16813cc75b33133fbdc4065e991ff0bea9580a75440900eae0fc2be2e4d44c5'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def strict_loads(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('DUPLICATE_JSON_KEY: ' + k)
            result[k] = v
        return result
    def bad(value):
        raise ValueError('NONFINITE_JSON_VALUE: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


def readj(path):
    return strict_loads(Path(path).read_text(encoding='utf-8-sig'))


def readl(path):
    rows = [strict_loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    require(all(isinstance(r, dict) for r in rows), 'JSONL rows must be objects: ' + str(path))
    return rows


def writej(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def writel(path, rows):
    with Path(path).open('x', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def object_sha(obj):
    text = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def local(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, 'Project-relative path required: ' + str(p))
    path = root / p
    require(path.resolve().is_relative_to(root.resolve()), 'Path outside project: ' + str(p))
    return path


def load_module(path, name):
    require(Path(path).is_file(), 'Required existing file missing: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def helpers(root):
    gate = load_module(root / 'scope_gate_v07.py', '_dori_scope_gate_v07')
    helper = load_module(root / 'evidence_probe_v04.py', '_dori_evidence_probe_v04')
    return gate, helper, helper.runtime_common(root)


def index(rows):
    d = {}
    for row in rows:
        cid = row.get('case_id')
        require(isinstance(cid, str) and cid and cid not in d, 'Missing/duplicate case_id')
        d[cid] = row
    return d


def envelope(row):
    return {'role': copy.deepcopy(row['role']), 'packet': copy.deepcopy(row['packet'])}


def frozen_check(root, values):
    for rel, digest in values.items():
        path = local(root, rel)
        require(path.is_file() and sha(path) == digest, 'Frozen file changed/missing: ' + rel)


def check_output(common, inputs, raw, hit_limit=False):
    """Runtime boundary: NO expected/gold/authoring fields accepted or consulted."""
    require(set(inputs) == {'role', 'packet'}, 'Output validator accepts role+packet only')
    parsed = None
    error = None
    try:
        require(isinstance(raw, str), 'Raw output must be text')
        parsed = strict_loads(raw)
        require(isinstance(parsed, dict), 'JSON object required')
        require(not hit_limit, 'GENERATION_LIMIT_REACHED')
        common.validate_answer(parsed, inputs)
        for key in ('evidence_refs', 'requested_evidence'):
            if key not in parsed:
                continue
            refs = parsed[key]
            require(isinstance(refs, list) and all(isinstance(x, str) and x for x in refs), 'Invalid reference list: ' + key)
            require(len(refs) == len(set(refs)), 'DUPLICATE_REFERENCE_STRING: ' + key)
    except (ValueError, TypeError, KeyError) as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    except Exception as exc:
        # jsonschema errors are deliberately kept as rejected outputs; do not repair.
        error = {'type': type(exc).__name__, 'message': getattr(exc, 'message', str(exc))}
    return {'status': 'OUTPUT_REJECTED' if error else 'OUTPUT_VALIDATED',
            'parsed': parsed, 'raw_output': raw, 'validation_error': error,
            'engineering_approved': False, 'human_review_required': True,
            'meaning': 'OUTPUT_VALIDATED checks syntax/schema/allowed IDs only; not semantic correctness.'}


def guard_checks(gate, sample):
    """Synthetic CPU stop/retention tests; no engineering labels or model calls."""
    results = []
    def blocked(name, value):
        try:
            gate.gate_input(value)
        except gate.GateError as exc:
            results.append({'check': name, 'pass': True, 'observed': 'GATE_BLOCKED', 'message': str(exc)})
        else:
            raise ValueError('Gate unexpectedly allowed guard case: ' + name)
    def edited():
        return copy.deepcopy(sample)
    x = edited(); x['packet']['review_question'] = 'No structured scope header.'
    blocked('missing_query_scope', x)
    x = edited(); x['packet']['review_question'] = x['packet']['review_question'].replace(gate.POLICY, 'Carryover applicability must be assessed.', 1)
    blocked('unsupported_carryover_policy', x)
    passed, _ = gate.gate_input(sample)
    keep_ids = {r['evidence_id'] for r in passed['packet']['case_packet']['evidence']}
    x = edited(); x['packet']['case_packet']['evidence'] = [r for r in x['packet']['case_packet']['evidence'] if r['evidence_id'] not in keep_ids]
    blocked('no_current_scope_record', x)
    x = edited(); x['packet']['case_packet']['evidence'][0]['text'] = 'Unparseable scope, even on an archival record.'
    blocked('malformed_record_scope', x)
    x = edited(); ev = x['packet']['case_packet']['evidence']; ev[1]['evidence_id'] = ev[0]['evidence_id']
    blocked('duplicate_record_id', x)
    x = edited(); x['expected'] = {'action': 'NO_ACTION_REQUIRED'}
    blocked('gate_rejects_gold_envelope', x)
    x = edited(); y = copy.deepcopy(passed['packet']['case_packet']['evidence'][0])
    y['evidence_id'] = 'OBS-V08-SECOND-MATCH'
    x['packet']['case_packet']['evidence'].append(y)
    kept, _ = gate.gate_input(x)
    require(len(kept['packet']['case_packet']['evidence']) == 2, 'Gate discarded a second same-scope record')
    results.append({'check': 'keep_all_same_scope_records', 'pass': True,
                    'meaning': 'No semantic conflict resolution or source preference is inferred.'})
    try:
        strict_loads('{"evidence_refs":["A"],"evidence_refs":["B"]}')
    except ValueError:
        results.append({'check': 'reject_duplicate_json_key', 'pass': True})
    else:
        raise ValueError('Duplicate-key parser guard failed')
    return results


def prepare(root, outdir):
    root = root.resolve(); dest = local(root, outdir)
    require(not dest.exists(), 'Output exists; preserved: ' + str(dest))
    gate, helper, common = helpers(root)
    auditpath = root / AUDIT / 'audit.json'
    a = readj(auditpath)
    require(a.get('version') == 'scope-gate-v0.7.0' and a.get('status') == 'PASS', 'Completed v07 audit required')
    require(a.get('gold_used_for_selection') is False, 'Unexpected gate provenance')
    require(sha(root / 'scope_gate_v07.py') == a['script_sha256'], 'Gate differs from the audited gate')
    frozen_check(root, a['input_sha256'])
    source = root / APP
    app = readj(source / 'manifest.json')
    review = readj(source / 'review.json')
    require(app.get('version') == 'applicability-probe-v0.6.0', 'Expected v06 source')
    require(review.get('decision') == 'ACCEPTED_FOR_DIAGNOSTIC' and review.get('reviewer'), 'Existing scenario review required')
    require(review['manifest_sha256'] == sha(source / 'manifest.json'), 'Scenario review/manifest mismatch')
    frozen_check(root, {**app['frozen_files'], **app['generated_files']})
    spec = app['models']['e2']
    require(spec['weight_sha256'] == E2_SHA, 'This smoke is fixed to the measured position-e2 adapter')
    require(sha(local(root, spec['adapter']) / 'adapter_model.safetensors') == E2_SHA, 'e2 weights changed')
    original = readl(local(root, app['case_files']['last']))
    original_map = index(original)
    clean = index(readl(local(root, app['case_files']['clean'])))
    old_gate_path = root / AUDIT / 'inputs_last.jsonl'
    old_gated = index(readl(old_gate_path))
    require(len(original) == 12 and set(original_map) == set(clean) == set(old_gated), 'Expected the same 12 scenarios')
    guard = guard_checks(gate, envelope(original[0]))
    combined, inputs, notes, labels = [], [], [], []
    for case in original:
        cid = case['case_id']
        # Gate only receives model input; gold, variant and authoring are NOT passed.
        inp, event = gate.gate_input(envelope(case))
        require(inp == envelope(clean[cid]) == envelope(old_gated[cid]), 'Gated content differs from audited clean: ' + cid)
        require(json.dumps(inp, ensure_ascii=False) == json.dumps(envelope(clean[cid]), ensure_ascii=False), 'Packet serialization order differs: ' + cid)
        # Labels enter only the existing evaluation harness AFTER gate selection.
        scored = {k: copy.deepcopy(case[k]) for k in ('case_id','pair_id','domain','source_id','role')}
        scored['packet'] = inp['packet']
        scored['expected'] = copy.deepcopy(case['expected'])
        scored['acceptable_answers'] = copy.deepcopy(case.get('acceptable_answers', [case['expected']]))
        scored['planned_split'] = 'DEV_DIAGNOSTIC'
        for answer in scored['acceptable_answers'] + [scored['expected']]:
            common.validate_answer(answer, inp)
        combined.append(scored)
        inputs.append({'case_id': cid, **inp})
        labels.append({'case_id': cid, 'expected': scored['expected'], 'acceptable_answers': scored['acceptable_answers']})
        notes.append({'case_id': cid, 'event': 'SCOPE_FILTERED', **event})
    prior = readj(source / 'comparison.json')
    prior_output = local(root, spec['outputs']['clean'])
    prior_summary_path = prior_output.with_suffix('.summary.json')
    require(sha(prior_output) == prior['result_sha256']['e2/clean'], 'Prior clean raw outputs changed')
    prior_summary = readj(prior_summary_path)
    require(prior_summary.get('adapter_sha256') == E2_SHA and prior_summary.get('records') == 12,
            'Prior clean model identity/count changed')
    require(prior_summary.get('case_file_sha256') == sha(local(root, app['case_files']['clean'])),
            'Prior clean case identity changed')
    frozen = {**app['frozen_files'], **app['generated_files'], **a['input_sha256']}
    for path in (auditpath, old_gate_path, prior_output, prior_summary_path, root/'scope_gate_v07.py', root/'evidence_probe_v04.py'):
        frozen[str(path.relative_to(root))] = sha(path)
    dest.mkdir(parents=True)
    writel(dest/'inputs12.jsonl', inputs)
    writel(dest/'labels_for_offline_scoring.jsonl', labels)
    writel(dest/'evaluation_cases12.jsonl', combined)
    writel(dest/'gate_events.jsonl', notes)
    writej(dest/'guard_checks.json', {'tests': guard, 'model_calls': 0})
    files = {p.name: sha(p) for p in dest.iterdir() if p.is_file()}
    manifest = {'version': VERSION, 'created_at_utc': now(), 'script_sha256': sha(Path(__file__)),
                'source_view': 'last', 'scenarios': 12, 'new_model_calls_planned': 12,
                'model': app['model'], 'revision': app['base_revision'], 'adapter': spec['adapter'],
                'adapter_sha256': E2_SHA, 'max_new_tokens': app['generation_budget'],
                'frozen_files': frozen, 'generated_files': files,
                'previous_clean': prior['models']['e2']['views']['clean'],
                'prior_clean_result': spec['outputs']['clean'],
                'labels_policy': 'Gate and output-validation use role+packet only. Existing dcurr evaluator carries labels solely for offline scoring.',
                'scope': 'New batch integration measurement on the same 12 scenarios; not a new independent benchmark or production service.'}
    writej(dest/'manifest.json', manifest)
    print('SCOPED REVIEW PREPARE: PASS')
    print('12 original packets -> gate -> 12 label-free model inputs; 24 records excluded from context.')
    print('CPU boundary guards:', len(guard), 'PASS. No model loaded.')
    print('Next: python scoped_review_v08.py run')


def plan(root, outdir):
    dest = local(root, outdir); m = readj(dest/'manifest.json')
    require(m['version'] == VERSION and m['script_sha256'] == sha(Path(__file__)), 'Wrapper/version changed after prepare')
    frozen_check(root, m['frozen_files'])
    for name, digest in m['generated_files'].items():
        require(sha(local(dest, name)) == digest, 'Prepared file changed: ' + name)
    require(sha(local(root, m['adapter'])/'adapter_model.safetensors') == m['adapter_sha256'], 'e2 adapter changed')
    return dest, m


def checked_run(root, dest, m):
    path = dest/'model_outputs.jsonl'; sp = path.with_suffix('.summary.json')
    rows = readl(path); mapped = index(rows); cases = index(readl(dest/'evaluation_cases12.jsonl'))
    require(set(mapped) == set(cases) and len(mapped) == 12, 'Incomplete/wrong model result set; keep outputs and logs')
    summary = readj(sp)
    for key, value in {'records':12, 'model':m['model'], 'adapter_sha256':m['adapter_sha256'],
                       'case_file_sha256':sha(dest/'evaluation_cases12.jsonl'),
                       'prompt_sha256':sha(root/'dcurr/prompts.py'), 'purpose':'CANDIDATE_DIAGNOSTIC'}.items():
        require(summary.get(key) == value, 'Model result identity differs: ' + key)
    for sk, rk in [('strict_json_valid','strict_json_valid'),('schema_and_refs_valid','schema_and_refs_valid'),
                   ('action_correct','action_ok'),('contract_pass','contract_pass')]:
        require(summary.get(sk) == sum(bool(r.get(rk)) for r in rows), 'Result summary/rows differ: ' + sk)
    return mapped, cases, summary


def run(root, outdir):
    dest, m = plan(root, outdir)
    output = dest/'model_outputs.jsonl'
    command = [sys.executable, '-m', 'dcurr.evaluate', '--cases', str((dest/'evaluation_cases12.jsonl').relative_to(root)),
               '--adapter', m['adapter'], '--out', str(output.relative_to(root)), '--model', m['model'],
               '--revision', m['revision'], '--max-new-tokens', str(m['max_new_tokens']), '--purpose', 'CANDIDATE_DIAGNOSTIC']
    started = dest/'run_started.json'; completed = dest/'run_completed.json'
    if completed.exists():
        done = readj(completed)
        require(done['command'] == command, 'Existing invocation differs')
        require(sha(output) == done['result_sha256'] and sha(output.with_suffix('.summary.json')) == done['summary_sha256'], 'Completed result changed')
        checked_run(root, dest, m)
        print('SKIP VERIFIED COMPLETE MODEL RUN')
    else:
        require(not started.exists() and not output.exists() and not output.with_suffix('.summary.json').exists(),
                'Prior incomplete invocation/output exists. Preserve it; prepare with a NEW --outdir, no silent resume.')
        writej(started, {'at_utc':now(), 'command':command, 'manifest_sha256':sha(dest/'manifest.json')})
        log = dest/'inference.log'; start = time.perf_counter()
        print('RUN:', shlex.join(command), flush=True)
        with log.open('x', encoding='utf-8') as f:
            f.write('COMMAND '+shlex.join(command)+'\n'); f.flush()
            with subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace') as proc:
                for line in proc.stdout:
                    print(line, end='', flush=True); f.write(line); f.flush()
                code = proc.wait()
        require(code == 0, f'Model subprocess stopped ({code}); preserved log: {log}')
        checked_run(root, dest, m)
        writej(completed, {'completed_at_utc':now(), 'command':command, 'result_sha256':sha(output),
                           'summary_sha256':sha(output.with_suffix('.summary.json')),
                           'subprocess_wall_seconds':time.perf_counter()-start,
                           'timing_note':'Includes subprocess setup/model load/generation/scoring; excludes prepare and subsequent report writing.'})
    summarize(root, outdir)


def summarize(root, outdir):
    dest, m = plan(root, outdir)
    require((dest/'run_completed.json').is_file(), 'No completed new model run')
    completion = readj(dest/'run_completed.json')
    require(sha(dest/'model_outputs.jsonl') == completion['result_sha256'] and
            sha(dest/'model_outputs.summary.json') == completion['summary_sha256'],
            'Completed model result changed')
    out = dest/'comparison.json'
    if out.exists():
        previous = readj(out)
        require(previous['model_outputs_sha256'] == sha(dest/'model_outputs.jsonl'), 'Existing comparison differs')
        for name, digest in previous['report_files_sha256'].items():
            require(sha(local(dest, name)) == digest, 'Existing report changed: ' + name)
        print('Comparison already complete:', out); return
    _, h, common = helpers(root)
    results, cases, summary = checked_run(root, dest, m)
    notes = index(readl(dest/'gate_events.jsonl'))
    prior = index(readl(local(root, m['prior_clean_result'])))
    counts = Counter(); runtime_rows = []; details = []
    for cid, case in cases.items():
        row = results[cid]; inp = envelope(case)
        status = check_output(common, inp, row.get('raw_output'), bool(row.get('hit_generation_limit')))
        raw_validated = status['status'] == 'OUTPUT_VALIDATED'
        if raw_validated:
            require(status['parsed'] == row.get('parsed'), 'Raw/parsed output mismatch: ' + cid)
        scored = h.score(common, case, row, [])  # Gold is consulted ONLY here.
        require(scored['stored_score_agrees'], 'Current offline scorer disagrees with stored result: ' + cid)
        final_pass = raw_validated and scored['strict_selection_contract_pass']
        counts['cases'] += 1; counts['runtime_valid'] += raw_validated
        counts['runtime_rejected'] += not raw_validated
        counts['action_correct'] += bool(raw_validated and scored['action_correct'])
        counts['exact_reference_choice'] += bool(raw_validated and scored['reference_choice_exact_any_allowed_set'])
        counts['strict_contract_pass'] += bool(final_pass)
        counts['same_action_as_prior_clean'] += bool(isinstance(status['parsed'],dict) and isinstance(prior[cid].get('parsed'),dict) and status['parsed'].get('action') == prior[cid]['parsed'].get('action'))
        excluded = {r['evidence_id'] for r in notes[cid]['excluded_from_model_context']}
        refs = status['parsed'].get('evidence_refs', []) if isinstance(status['parsed'], dict) else []
        strings = set(x for x in refs if isinstance(x,str)) if isinstance(refs,list) else set()
        counts['cites_excluded_records'] += bool(strings & excluded)
        record = {'case_id':cid, 'claim_id':inp['packet']['claim_id'], 'scope':notes[cid]['target_scope'],
                  'gate_input_sha256':notes[cid]['original_inference_envelope_sha256'],
                  'gated_input_sha256':notes[cid]['gated_inference_envelope_sha256'],
                  'excluded_record_ids':sorted(excluded), 'adapter_sha256':m['adapter_sha256'], **status}
        runtime_rows.append(record)
        details.append({'case_id':cid,'pair_id':case['pair_id'],'runtime':record,'offline_score':scored,
                        'prior_clean_parsed':prior[cid].get('parsed'),'strict_runtime_and_contract_pass':bool(final_pass)})
    writel(dest/'review_records.jsonl', runtime_rows)
    writel(dest/'comparison_cases.jsonl', details)
    report = {'version':VERSION, 'at_utc':now(), 'inference_executed':True, 'training_executed':False,
              'scenarios':12, 'source_view':'last', 'counts':dict(counts), 'previous_clean_reference_only':m['previous_clean'],
              'model_outputs_sha256':sha(dest/'model_outputs.jsonl'), 'adapter_sha256':m['adapter_sha256'],
              'runtime_note':'OUTPUT_VALIDATED is syntactic/reference validation, not gold correctness or engineering approval. Every result still requires human review.',
              'measurement_note':'Twelve new generations from the same gated inputs. Do not count this as new-program generalization or combine with raw model scores.',
              'record_note':'review_records excludes gold. evaluation_cases and comparison_cases include offline labels. Existing dcurr evaluator is unchanged.'}
    text = [
        '# 범위 게이트 + e2 실제 연결 결과', '',
        '이 실행은 기존 12개 시나리오의 배치 연결 검사입니다. 새 학습·독립 시험·제품 승인이 아닙니다.', '',
        f"- 실제 신규 추론: {counts['cases']}건",
        f"- 출력 형식·허용 ID 검증 통과: {counts['runtime_valid']}/12",
        f"- 출력 거부: {counts['runtime_rejected']}/12",
        f"- 오프라인 action 정답: {counts['action_correct']}/12",
        f"- 오프라인 근거 정확 선택: {counts['exact_reference_choice']}/12",
        f"- 엄격한 출력 + 전체 계약 통과: {counts['strict_contract_pass']}/12",
        f"- 제외한 기록의 재인용: {counts['cites_excluded_records']}건", '',
        '**형식 검증 통과와 공학적으로 옳은 판단은 별개입니다.** 모든 review record에 engineering_approved=false를 남깁니다.', '',
        '## 파일',
        '`review_records.jsonl`: 정답 없는 검토 후보와 제외 이력 연결. 검증 실패 출력도 삭제하지 않습니다.',
        '`comparison_cases.jsonl`: 기준 정답과 실제 출력·구체적 실패 원인이 있는 오프라인 비교.',
        '`comparison.json`: 집계와 해시. `inference.log`: 실제 평가기 로그.', '',
        '다음은 이 배치 smoke를 독립 소스의 검토 업무로 확장하는 단계입니다. 동일 12개 결과를 더 반복 튜닝하는 것이 목적은 아닙니다.',
    ]
    (dest/'RESULTS_KO.md').write_text('\n'.join(text)+'\n', encoding='utf-8')
    report['report_files_sha256'] = {name:sha(dest/name) for name in ('review_records.jsonl','comparison_cases.jsonl','RESULTS_KO.md')}
    writej(out, report)
    print('SCOPED REVIEW RUN: COMPLETE — this is execution completion, not 100% engineering accuracy')
    print(json.dumps(dict(counts), indent=2, ensure_ascii=False))
    print('RESULT FOLDER:', dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','run','summarize'])
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--outdir', default=DEFAULT_OUT)
    a = p.parse_args(); root = a.root.resolve()
    try:
        {'prepare':prepare,'run':run,'summarize':summarize}[a.command](root,a.outdir)
    except (ValueError, KeyError, OSError, ImportError, RuntimeError) as exc:
        print('STOP:', exc, file=sys.stderr)
        print('Old data/code/models were not overwritten. Keep any partial output/log; do not rerun training.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
