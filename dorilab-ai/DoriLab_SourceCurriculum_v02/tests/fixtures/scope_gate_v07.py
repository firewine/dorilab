#!/usr/bin/env python3
"""Input-only scope gate and offline equivalence audit for DoriLab v06.

Usage (from DoriLab_SourceCurriculum_v02):
    python scope_gate_v07.py audit

No training, inference, network, package installation, label repair, or old-file
modification. Reads the existing v06 bundle and writes a NEW audit directory.
This adapter supports only v06's explicit machine-formatted exact-scope policy.
It is not a general natural-language applicability engine.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'scope-gate-v0.7.0'
VIEWS = ('clean', 'first', 'middle', 'last')
POLICY = (
    'Only records matching all three scope identifiers may substantiate this check; '
    'any other supplied records are archival comparisons and no equivalence or carryover evidence is provided.'
)
FIELD = r'([A-Za-z0-9_-]+)'
QUERY = re.compile(r'\AReview scope: unit=' + FIELD + r'; configuration=' + FIELD + r'; run=' + FIELD + r'\. ')
RECORD = re.compile(r'\ARecord scope: unit=' + FIELD + r'; configuration=' + FIELD + r'; run=' + FIELD + r'\. ')
KEYS = ('unit', 'configuration', 'run')

class GateError(ValueError):
    """Stop without sending an uncertain packet to a model."""

def strict_loads(text: str):
    def pairs(xs):
        out = {}
        for key, value in xs:
            if key in out:
                raise GateError('DUPLICATE_JSON_KEY: ' + key)
            out[key] = value
        return out
    def constant(value):
        raise GateError('NONFINITE_JSON_VALUE: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)

def read_json(path: Path):
    return strict_loads(path.read_text(encoding='utf-8-sig'))

def read_rows(path: Path):
    rows = []
    for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if line.strip():
            value = strict_loads(line)
            if not isinstance(value, dict):
                raise GateError(f'{path}:{n}: object row required')
            rows.append(value)
    return rows

def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def object_sha(value) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def inside(root: Path, relative) -> Path:
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise GateError('Project-relative path required: ' + str(p))
    result = root / p
    if not result.resolve().is_relative_to(root.resolve()):
        raise GateError('Path escapes root: ' + str(p))
    return result

def require(condition, message):
    if not condition:
        raise GateError(message)

def parse_scope(text, pattern, where):
    require(isinstance(text, str), where + ': scope text must be a string')
    match = pattern.match(text)
    require(match is not None, where + ': unsupported/missing scope header; manual resolution required')
    require(bool(text[match.end():].strip()), where + ': body missing')
    return dict(zip(KEYS, match.groups())), match.end()

def gate_input(envelope: dict) -> tuple[dict, dict]:
    """Return (role+packet, exclusion audit), WITHOUT consulting any gold fields.

    Only explicit exact matching of unit/configuration/run is implemented.
    All matching observations remain, including contradictory ones. This gate
    does not determine which matching observation is relevant or which action is
    correct. Unsupported/missing metadata or zero matches causes a hard stop.
    """
    require(isinstance(envelope, dict) and set(envelope) == {'role', 'packet'},
            'Only the inference envelope {role, packet} is accepted; do not pass case labels/authoring metadata')
    require(isinstance(envelope['role'], str) and envelope['role'].strip(), 'role missing')
    packet = envelope['packet']
    require(isinstance(packet, dict), 'packet must be an object')
    question = packet.get('review_question')
    target, end = parse_scope(question, QUERY, 'review_question')
    require(question[end:].startswith(POLICY + ' '),
            'Unsupported applicability policy; exact scope gate cannot decide carryover/equivalence')
    require(bool(question[end + len(POLICY):].strip()), 'review question missing')
    cp = packet.get('case_packet')
    require(isinstance(cp, dict), 'case_packet missing')
    evidence = cp.get('evidence')
    require(isinstance(evidence, list) and evidence, 'No observations supplied; do not infer NO_ACTION')
    refs = packet.get('reference_context')
    require(isinstance(refs, list) and refs, 'reference_context missing')
    ids = set()
    reference_ids = []
    for ref in refs:
        require(isinstance(ref, dict), 'Invalid reference record')
        rid = ref.get('reference_id')
        require(isinstance(rid, str) and rid.strip() and rid not in ids, 'Invalid/duplicate reference_id')
        ids.add(rid); reference_ids.append(rid)
    kept, excluded, included = [], [], []
    # Validate ALL records, including off-scope records, before producing output.
    for record in evidence:
        require(isinstance(record, dict), 'Invalid observation record')
        rid = record.get('evidence_id')
        require(isinstance(rid, str) and rid.strip() and rid not in ids, 'Invalid/duplicate evidence_id')
        ids.add(rid)
        scope, _ = parse_scope(record.get('text'), RECORD, 'record ' + rid)
        mismatch = [key for key in KEYS if scope[key] != target[key]]
        entry = {'evidence_id': rid, 'record_scope': scope, 'record_sha256': object_sha(record)}
        if mismatch:
            excluded.append({**entry, 'reason': 'OUTSIDE_DECLARED_EXACT_SCOPE', 'mismatching_fields': mismatch})
        else:
            kept.append(copy.deepcopy(record)); included.append(entry)
    require(bool(kept), 'NO_EXACT_SCOPE_RECORD: request scope/evidence resolution; no automatic pass')
    result = copy.deepcopy(envelope)
    result['packet']['case_packet']['evidence'] = kept
    audit = {'policy': 'EXACT_UNIT_CONFIGURATION_RUN_NO_CARRYOVER', 'target_scope': target,
             'included': included, 'excluded_from_model_context': excluded,
             'allowed_reference_ids': reference_ids + [r['evidence_id'] for r in kept],
             'original_inference_envelope_sha256': object_sha(envelope),
             'gated_inference_envelope_sha256': object_sha(result),
             'does_not_establish': 'Physical validity, equivalence, semantic relevance among matching records, or final engineering action'}
    return result, audit

def index_cases(rows):
    result = {}
    for row in rows:
        cid = row.get('case_id')
        require(isinstance(cid, str) and cid not in result, 'Missing/duplicate case_id')
        result[cid] = row
    return result

def audit_bundle(root: Path, source: str, out: str):
    root = root.resolve(); src = inside(root, source); dest = inside(root, out)
    require(not dest.exists(), 'Output already exists; preserve it: ' + str(dest))
    mp = src / 'manifest.json'; rp = src / 'review.json'
    summary_path = src / 'comparison.json'; detail_path = src / 'comparison_cases.jsonl'
    m = read_json(mp); review = read_json(rp); summary = read_json(summary_path); details = read_rows(detail_path)
    require(m.get('version') == 'applicability-probe-v0.6.0', 'Unexpected v06 manifest version')
    require(summary.get('version') == m['version'], 'Comparison version mismatch')
    require(summary.get('manifest_sha256') == sha(mp), 'Comparison is for another input bundle')
    require(review.get('decision') == 'ACCEPTED_FOR_DIAGNOSTIC' and review.get('reviewer') and review.get('notes'),
            'Existing v06 diagnostic review not found; no approval is created by this tool')
    require(review.get('manifest_sha256') == sha(mp), 'Review belongs to another input bundle')
    require(set(m.get('case_files', {})) == set(VIEWS), 'Expected four v06 views')
    inputs, hashes = {}, {str(mp.relative_to(root)): sha(mp), str(rp.relative_to(root)): sha(rp),
                          str(summary_path.relative_to(root)): sha(summary_path), str(detail_path.relative_to(root)): sha(detail_path)}
    for view in VIEWS:
        path = inside(root, m['case_files'][view])
        key = str(path.relative_to(root))
        require(m['generated_files'].get(key) == sha(path), 'Input changed since review: ' + key)
        hashes[key] = sha(path); inputs[view] = read_rows(path)
    clean = index_cases(inputs['clean']); require(len(clean) == 12, 'Expected 12 reviewed v06 scenarios')
    require(len({c['pair_id'] for c in clean.values()}) == 6, 'Expected six v06 pairs')
    packets, rows, per_view = {}, [], {}
    for view in VIEWS:
        require(set(index_cases(inputs[view])) == set(clean), 'View membership differs')
        packets[view] = []; counts = Counter()
        for case in inputs[view]:
            # Only these TWO fields reach gate_input. No expected, source_fact_ids,
            # acceptable_answers, authoring or precomputed correct-record handle.
            envelope = {'role': case['role'], 'packet': case['packet']}
            gated, note = gate_input(envelope)
            baseline = {'role': clean[case['case_id']]['role'], 'packet': clean[case['case_id']]['packet']}
            identical = (canonical(gated) == canonical(baseline) and
                         json.dumps(gated, ensure_ascii=False) == json.dumps(baseline, ensure_ascii=False))
            counts['cases'] += 1; counts['equivalent_to_clean_role_packet'] += int(identical)
            counts['records_kept'] += len(note['included'])
            counts['records_excluded_from_context'] += len(note['excluded_from_model_context'])
            packets[view].append({'case_id': case['case_id'], 'role': gated['role'], 'packet': gated['packet']})
            rows.append({'view': view, 'case_id': case['case_id'], **note, 'equivalent_to_clean_role_packet': identical})
        require(counts['equivalent_to_clean_role_packet'] == counts['cases'],
                'Gate output is not the existing clean input in ' + view + '; no baseline reuse is justified')
        per_view[view] = dict(counts)
    models = m['models']; require(set(summary['models']) == set(models), 'Model comparison membership differs')
    require(len(details) == len(models) * len(clean), 'Comparison is incomplete')
    clean_baselines, duplicate_keys = {}, []
    for label in models:
        subset = [r for r in details if r['model'] == label]
        require(set(index_cases(subset)) == set(clean), 'Model detail membership differs')
        for view in VIEWS:
            sm = summary['models'][label]['views'][view]
            mapping = {'action_correct': 'action_correct', 'schema_and_refs_valid': 'schema_and_refs_valid',
                       'reference_choice_exact': 'reference_choice_exact_any_allowed_set',
                       'strict_selection_contract_pass': 'strict_selection_contract_pass',
                       'rows_citing_distractors': 'distractor_reference_strings'}
            for sk, dk in mapping.items():
                require(sm[sk] == sum(bool(r['scores'][view][dk]) for r in subset), 'Stored summary/detail mismatch')
            for r in subset:
                s = r['scores'][view]
                require(s['stored_score_agrees'] is True, 'Previously stored scoring mismatch')
                try:
                    decoded = strict_loads(s['raw_output'])
                    require(decoded == s['parsed'], 'Raw/parsed mismatch')
                except (ValueError, TypeError) as exc:
                    duplicate_keys.append({'model': label, 'view': view, 'case_id': r['case_id'],
                                           'error': str(exc), 'original_full_pass': s['strict_selection_contract_pass']})
        cb = summary['models'][label]['views']['clean']
        clean_baselines[label] = {
            'status': 'PREVIOUSLY_OBSERVED_CLEAN_RESULT_ONLY_NOT_NEW_INFERENCE',
            'cases': cb['cases'], 'action_correct': cb['action_correct'],
            'reference_choice_exact': cb['reference_choice_exact'],
            'strict_selection_contract_pass': cb['strict_selection_contract_pass'],
            'note': 'Input-equivalence audit only. No gated model run or runtime integration measured. Does not measure metadata extraction correctness.'}
    report = {'version': VERSION, 'at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'PASS', 'inference_executed': False, 'training_executed': False,
              'model_weights_loaded': False, 'unique_scenarios': 12, 'pairs': 6,
              'gate_input_fields': ['role', 'packet'], 'gold_used_for_selection': False,
              'gold_use': 'Clean packet used only AFTER selection to verify input equivalence; stored labels only describe prior clean scores.',
              'equivalence_check': 'role+packet structure AND order-preserving JSON serialization; no tokenizer execution',
              'views': per_view, 'previously_observed_clean_baselines': clean_baselines,
              'raw_output_serialization_flags': duplicate_keys,
              'old_scores_were_modified': False, 'script_sha256': sha(Path(__file__)),
              'input_sha256': hashes,
              'limits': ['Only v06 machine-formatted prefixes and explicit no-carryover policy are supported.',
                         'For deployment use authoritative structured metadata, not arbitrary self-declared free text.',
                         'All exact-scope records remain; relevance/conflicts within scope still need review.',
                         'Missing/ambiguous metadata or zero matches stops the gate; never implies engineering approval.',
                         'Filtering is a system intervention, not an improvement in raw model capability.',
                         'Same source, 12 related scenarios; no independent program generalization established.']}
    text = ['# v06 범위 게이트 입력 동등성 검사', '', '**GPU 추론·학습을 실행하지 않은 CPU 검사입니다.**', '',
            '질문의 unit/configuration/run과 관측 헤더를 정확히 대조해 현재 범위의 관측만 모델 문맥에 유지했습니다.',
            '원본 기록은 보존하며 제외 사유는 audit_cases.jsonl에 기록했습니다. 정답/authoring 필드는 선택 함수에 전달하지 않았습니다.', '',
            '| 조건 | 검사 수 | 기존 clean의 role+packet과 일치 | 유지 관측 | 문맥에서 제외 |', '|---|---:|---:|---:|---:|']
    for view, c in per_view.items():
        text.append(f"| {view} | {c['cases']} | {c['equivalent_to_clean_role_packet']} | {c['records_kept']} | {c['records_excluded_from_context']} |")
    text += ['', '## 기존 clean 결과: 새 게이트 모델 성능이 아님', '',
             '| 모델 | action | 근거 정확 선택 | 전체 계약 |', '|---|---:|---:|---:|']
    for label, s in clean_baselines.items():
        text.append(f"| {label} | {s['action_correct']}/12 | {s['reference_choice_exact']}/12 | {s['strict_selection_contract_pass']}/12 |")
    text += ['', '위 수치는 이미 측정한 clean 결과입니다. 이번 파일 변환에서 모델 능력이 향상된 것이 아니며 새 추론 점수가 아닙니다.',
             '제품 경로의 다음 구현 지점은 gate_input({role, packet}) → 모델 호출 → 승인된 근거 ID 검증입니다.',
             '운영에서는 업로드 자료의 self-declared 문자열이 아니라 검증된 구조화 metadata를 사용합니다. 동등성/이전 시험 재사용은 별도 승인 규칙입니다.',
             '', '## 원출력 직렬화 점검', f'추가 플래그: {len(duplicate_keys)}건. 기존 점수는 수정하지 않았습니다.',
             '중복 JSON key는 배열 안의 중복 ID와 다릅니다. 출력 검증기에 별도 거부 규칙을 두는 것을 권합니다.',
             '', '입력 파일은 label 없는 role+packet 모음으로 출력했습니다. dcurr.evaluate용 정답 포함 파일이 아닙니다.']
    # Check that inputs did not change while auditing; write only a NEW directory.
    for rel, digest in hashes.items():
        require(sha(inside(root, rel)) == digest, 'Input changed during audit: ' + rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.scope_gate_stage_', dir=dest.parent))
    try:
        (stage / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'audit_cases.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        for view, xs in packets.items():
            (stage / f'inputs_{view}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in xs), encoding='utf-8')
        (stage / 'RESULTS_KO.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
        require(not dest.exists(), 'Output appeared during audit; not overwritten')
        stage.rename(dest)
    except Exception:
        if stage.exists(): shutil.rmtree(stage)
        raise
    print('SCOPE GATE AUDIT: PASS')
    for v, c in per_view.items():
        print(f"{v}: {c['equivalent_to_clean_role_packet']}/{c['cases']} role+packet identical to existing clean")
    print('New inference: 0. New training: 0. Original scores/files unchanged.')
    print('RESULT FOLDER:', dest)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['audit'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--source', default='data/applicability_probe_v06')
    parser.add_argument('--out', default='data/scope_gate_v07')
    args = parser.parse_args()
    audit_bundle(args.root, args.source, args.out)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP:', exc, file=sys.stderr)
        raise SystemExit(1)
