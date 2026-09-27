#!/usr/bin/env python3
"""DoriLab v02 evidence-selection probe: add two unrelated observations, then reorder.

Place beside dcurr/, data/, runs/ and id_probe_v03.py in the current v02 project.
Uses the prior ID probe's measured renamed inputs as control. No training, approval,
source reinterpretation, scorer patching or automatic repair of model output.
Python standard library only; build/compare import the project's existing dcurr.common.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import random
import shlex
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 'evidence-probe-v0.4.0'
DEFAULT_DIR = 'data/evidence_probe_v04'
ID_PROBE_MANIFEST = 'data/id_probe_v03/manifest.json'
SCRIPT_BASENAME = 'evidence_probe_v04.py'
MODELS = ('lr5e5', 'lr2e5')
VIEWS = ('control', 'after', 'before')
# These are deliberately easy, unrelated synthetic observations, not source facts.
# They say nothing about the test article, run, physics, acceptance criteria or claim.
DISTRACTOR_TEXTS = (
    'The office courier register records delivery of an envelope of staff meal vouchers to the reception desk.',
    'The office furniture inventory lists a spare visitor chair in the reception storage room.',
)


def strict_loads(text: str) -> Any:
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError('Duplicate JSON key: ' + str(k))
            obj[k] = v
        return obj
    def invalid(v):
        raise ValueError('Invalid JSON numeric constant: ' + str(v))
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = strict_loads(line)
        except ValueError as exc:
            raise ValueError(f'{path}:{n}: {exc}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'{path}:{n}: JSON object required')
        rows.append(row)
    return rows


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def dump_jsonl(rows) -> str:
    return ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)


def save_json(path: Path, data: Any) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def by_id(rows: list[dict]) -> dict[str, dict]:
    result = {}
    for r in rows:
        cid = r.get('case_id')
        if not isinstance(cid, str) or not cid or cid in result:
            raise ValueError('Missing or duplicate case_id')
        result[cid] = r
    return result


def result_ids(rows: list[dict], cases: list[dict]) -> dict[str, dict]:
    result = by_id(rows)
    expected = set(by_id(cases))
    if set(result) != expected:
        raise ValueError(f'Incomplete result: missing={sorted(expected-set(result))}, extra={sorted(set(result)-expected)}')
    return result


def local_path(root: Path, relative: str | Path) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Expected a relative path within the v02 project: ' + str(rel))
    p = root / rel
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes the project')
    return p


def definitions(case: dict) -> dict[str, str]:
    p = case['packet']
    defs = {}
    for entries, key, kind in (
        (p['reference_context'], 'reference_id', 'source_fact'),
        (p['case_packet']['evidence'], 'evidence_id', 'observation'),
    ):
        if not isinstance(entries, list) or not entries:
            raise ValueError('Nonempty lists of facts and observations required')
        for e in entries:
            ident = e.get(key) if isinstance(e, dict) else None
            if not isinstance(ident, str) or not ident or ident in defs:
                raise ValueError('Missing/duplicate local evidence handle')
            defs[ident] = kind
    return defs


def answer_variants(case: dict) -> list[dict]:
    values = case.get('acceptable_answers', [case['expected']])
    if not isinstance(values, list) or not values or any(not isinstance(x, dict) for x in values):
        raise ValueError('Nonempty acceptable_answers objects required')
    return values


def validate_gold_refs(case: dict) -> None:
    available = set(definitions(case))
    for answer in [case['expected'], *answer_variants(case)]:
        refs = answer.get('evidence_refs')
        if (not isinstance(refs, list) or not refs or
            any(not isinstance(x, str) or not x for x in refs) or
            len(set(refs)) != len(refs) or not set(refs) <= available):
            raise ValueError('Gold evidence_refs are not unique local IDs: ' + case['case_id'])


def make_views(cases: list[dict], seed: int) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
    """Keep IDs, reference prose, proposal, gold and metadata; insert observations only."""
    by_id(cases)
    if not cases:
        raise ValueError('No control cases')
    groups = defaultdict(list)
    used = set()
    for case in cases:
        validate_gold_refs(case)
        evidence = case['packet']['case_packet']['evidence']
        if len(evidence) != 1 or not isinstance(evidence[0].get('text'), str):
            raise ValueError('This probe requires the current one-observation case format')
        pid = case.get('pair_id')
        if not isinstance(pid, str) or not pid:
            raise ValueError('pair_id required')
        groups[pid].append(case)
        used.update(definitions(case))
        used.update(r.get('source_id', '') for r in case['packet']['reference_context'])
    if any(len(g) != 2 for g in groups.values()):
        raise ValueError('Use complete A/B pairs')
    rng = random.Random(seed)
    additions = {}
    for pid in sorted(groups):
        entries = []
        for text in DISTRACTOR_TEXTS:
            for _ in range(20000):
                handle = 'OBS-' + str(rng.randrange(1000, 10000))
                if handle not in used:
                    used.add(handle)
                    break
            else:
                raise ValueError('ID space exhausted')
            entries.append({'evidence_id': handle, 'text': text})
        additions[pid] = entries
    views = {'after': [], 'before': []}
    distractor_ids = {}
    for c in cases:
        extra = additions[c['pair_id']]
        distractor_ids[c['case_id']] = [e['evidence_id'] for e in extra]
        original_evidence = c['packet']['case_packet']['evidence']
        for name in views:
            modified = copy.deepcopy(c)
            modified['packet']['case_packet']['evidence'] = (
                copy.deepcopy(original_evidence + extra) if name == 'after'
                else copy.deepcopy(extra + original_evidence)
            )
            validate_gold_refs(modified)
            # Delete only generated additions: must recover the entire unchanged case.
            restored = copy.deepcopy(modified)
            restored['packet']['case_packet']['evidence'] = [
                x for x in restored['packet']['case_packet']['evidence']
                if x['evidence_id'] not in distractor_ids[c['case_id']]
            ]
            if restored != c:
                raise ValueError('Intervention changed something besides irrelevant observations')
            views[name].append(modified)
    return views, distractor_ids


def runtime_common(root: Path):
    expected = root / 'dcurr/common.py'
    if not expected.is_file():
        raise ValueError('Run in ~/dorilab-ai/DoriLab_SourceCurriculum_v02, beside dcurr/.')
    sys.path.insert(0, str(root))
    m = importlib.import_module('dcurr.common')
    if Path(m.__file__).resolve() != expected.resolve():
        raise ValueError('Imported dcurr.common from another project')
    for name in ('validate_answer', 'answer_matches'):
        if not callable(getattr(m, name, None)):
            raise ValueError('Missing current evaluator API: ' + name)
    return m


def score(common, case: dict, row: dict, distractor_ids: list[str]) -> dict:
    """Keep legacy subset score AND add stricter evidence-selection metrics.

    An extra supplied distractor may pass the old subset rule. Never change that
    old score; record its occurrence separately. Never strip/repair a model answer.
    """
    if 'parsed' not in row or not isinstance(row.get('contract_pass'), bool):
        raise ValueError('Expected dcurr result fields: parsed and boolean contract_pass')
    obj = row['parsed']
    valid = False
    validation_error = None
    try:
        common.validate_answer(obj, case)
        valid = True
    except Exception as exc:
        validation_error = {'type': type(exc).__name__, 'message': getattr(exc, 'message', str(exc))}
        if getattr(exc, 'absolute_path', None) is not None:
            validation_error['path'] = list(exc.absolute_path)
    variants = answer_variants(case)
    legacy_match = valid and any(common.answer_matches(a, obj) for a in variants)
    refs = obj.get('evidence_refs') if isinstance(obj, dict) else None
    list_ok = isinstance(refs, list) and all(isinstance(x, str) and x for x in refs)
    refset = set(refs) if list_ok else set()
    unique = list_ok and len(refs) == len(refset)
    expected_sets = [set(a['evidence_refs']) for a in variants]
    any_complete = list_ok and any(s <= refset for s in expected_sets)
    choice_exact = unique and any(refset == s for s in expected_sets)
    strict_contract = valid and unique and any(
        refset == set(a['evidence_refs']) and common.answer_matches(a, obj) for a in variants
    )
    primary = set(case['expected']['evidence_refs'])
    allowed = set(definitions(case))
    source_metadata = {r.get('source_id') for r in case['packet']['reference_context']}
    source_metadata.discard(None)
    row_result = {
        'action_correct': isinstance(obj, dict) and any(obj.get('action') == a.get('action') for a in variants),
        'schema_and_refs_valid': valid,
        'legacy_subset_contract_pass': bool(legacy_match),
        'stored_score_agrees': row['contract_pass'] == bool(legacy_match),
        'evidence_refs_list_of_strings': list_ok,
        'duplicate_reference_strings': list_ok and not unique,
        'required_refs_complete_any_allowed_set': bool(any_complete),
        'reference_choice_exact_any_allowed_set': bool(choice_exact),
        'strict_selection_contract_pass': bool(strict_contract),
        'distractor_reference_strings': sorted(refset & set(distractor_ids)),
        'metadata_source_id_in_evidence_refs': sorted((refset & source_metadata) - allowed),
        'unprovided_reference_strings': sorted(refset - allowed),
        'missing_primary_gold_references': sorted(primary - refset),
        'extra_vs_primary_gold': sorted(refset - primary),
        'primary_reference_recall': len(refset & primary) / len(primary) if list_ok else None,
        'primary_reference_precision': len(refset & primary) / len(refset) if refset and list_ok else None,
        'validation_error': validation_error,
        # Include the actual data now, so the user need not paste one case later.
        'expected_primary': case['expected'], 'parsed': obj, 'raw_output': row.get('raw_output'),
    }
    return row_result


def summarise(rows: list[dict]) -> dict:
    def n(k):
        return sum(bool(r['score'][k]) for r in rows)
    groups = defaultdict(list)
    for r in rows:
        groups[r['pair_id']].append(r['score'])
    complete = [g for g in groups.values() if len(g) == 2]
    return {
        'cases': len(rows),
        'action_correct': n('action_correct'),
        'schema_and_refs_valid': n('schema_and_refs_valid'),
        'legacy_subset_contract_pass': n('legacy_subset_contract_pass'),
        'required_refs_complete': n('required_refs_complete_any_allowed_set'),
        'reference_choice_exact': n('reference_choice_exact_any_allowed_set'),
        'strict_selection_contract_pass': n('strict_selection_contract_pass'),
        'rows_citing_distractors': n('distractor_reference_strings'),
        'rows_citing_metadata_source_ids': n('metadata_source_id_in_evidence_refs'),
        'rows_citing_unprovided_refs': n('unprovided_reference_strings'),
        'malformed_reference_rows': sum(not r['score']['evidence_refs_list_of_strings'] for r in rows),
        'duplicate_reference_rows': n('duplicate_reference_strings'),
        'complete_pairs': len(complete),
        'pair_action_both_correct': sum(all(s['action_correct'] for s in g) for g in complete),
        'pair_strict_selection_both_pass': sum(all(s['strict_selection_contract_pass'] for s in g) for g in complete),
    }


def freeze_check(root: Path, files: dict) -> None:
    for rel, expected in files.items():
        path = local_path(root, rel)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Frozen file changed/missing: ' + str(rel))


def runtime_contract_check(common, case: dict, extra_id: str) -> None:
    common.validate_answer(case['expected'], case)
    if not common.answer_matches(case['expected'], case['expected']):
        raise ValueError('Current answer matcher rejects its gold answer')
    enlarged = copy.deepcopy(case['expected'])
    enlarged['evidence_refs'].append(extra_id)
    common.validate_answer(enlarged, case)
    if not common.answer_matches(case['expected'], enlarged):
        raise ValueError('Expected legacy subset evidence semantics; scorer differs from prior experiment')
    probe = score(common, case, {'parsed': enlarged, 'contract_pass': True}, [extra_id])
    if not probe['stored_score_agrees'] or probe['strict_selection_contract_pass']:
        raise ValueError('Legacy/strict selection separation check failed')


def command_lines(root: Path, manifest: dict) -> str:
    lines = ['#!/usr/bin/env bash', 'set -euo pipefail', 'cd ' + shlex.quote(str(root)),
             '# Four sequential evaluations; no training and no pip installs.',
             '# If interrupted, preserve completed outputs and run only the unfinished command.']
    for label in MODELS:
        for view in ('after', 'before'):
            spec = manifest['model_specs'][label]
            args = [sys.executable, '-m', 'dcurr.evaluate', '--cases', manifest['files'][view],
                    '--adapter', spec['adapter'], '--out', spec['result_files'][view],
                    '--purpose', 'CANDIDATE_DIAGNOSTIC']
            lines.extend(['', f'echo {shlex.quote(label + " / " + view)}', shlex.join(args)])
    return '\n'.join(lines) + '\n'


def build(root: Path, outdir: Path, seed: int) -> None:
    root = root.resolve()
    target = local_path(root, outdir)
    if target.exists():
        raise ValueError('Output directory exists; preserve it and use a new experiment version.')
    prior_path = local_path(root, ID_PROBE_MANIFEST)
    prior = strict_loads(prior_path.read_text(encoding='utf-8'))
    if prior.get('version') != 'id-probe-v0.3.0':
        raise ValueError('This helper expects the completed v03 ID probe manifest')
    freeze_check(root, prior['frozen_files'])
    control_path = local_path(root, prior['probe_file'])
    if digest(control_path) != prior['probe_sha256']:
        raise ValueError('The measured ID-renamed control file changed')
    cases = read_jsonl(control_path)
    if len(cases) != 40:
        raise ValueError('Expected the measured 40 ID-renamed cases')
    views, distractors = make_views(cases, seed)
    common = runtime_common(root)
    for c in cases + views['after'] + views['before']:
        for gold in [c['expected'], *answer_variants(c)]:
            common.validate_answer(gold, c)
    for c in views['after']:
        runtime_contract_check(common, c, distractors[c['case_id']][0])
    frozen = dict(prior['frozen_files'])
    frozen[ID_PROBE_MANIFEST] = digest(prior_path)
    frozen[prior['probe_file']] = digest(control_path)
    specs = {}
    for label in MODELS:
        previous = prior['model_specs'][label]
        adapter = local_path(root, previous['adapter'])
        if digest(adapter / 'adapter_model.safetensors') != previous['weight_sha256']:
            raise ValueError(label + ': adapter is different from prior ID probe')
        result_file = previous['probe']
        outputs = result_ids(read_jsonl(local_path(root, result_file)), cases)
        for c in cases:
            if not score(common, c, outputs[c['case_id']], [])['stored_score_agrees']:
                raise ValueError(label + '/' + c['case_id'] + ': current scorer and saved control disagree')
        frozen[result_file] = digest(local_path(root, result_file))
        specs[label] = {
            'adapter': previous['adapter'], 'weight_sha256': previous['weight_sha256'],
            'result_files': {
                'control': result_file,
                'after': f'reports/physics20_{label}_evidence_v04_after.jsonl',
                'before': f'reports/physics20_{label}_evidence_v04_before.jsonl',
            },
        }
        for view in ('after', 'before'):
            if local_path(root, specs[label]['result_files'][view]).exists():
                raise ValueError('Result already exists: ' + specs[label]['result_files'][view])
    files = {
        'control': str(outdir / 'control40.jsonl'),
        'after': str(outdir / 'irrelevant_after40.jsonl'),
        'before': str(outdir / 'irrelevant_before40.jsonl'),
    }
    payloads = {'control': control_path.read_bytes(),
                'after': dump_jsonl(views['after']).encode('utf-8'),
                'before': dump_jsonl(views['before']).encode('utf-8')}
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        'version': VERSION, 'created_at_utc': now, 'seed': seed,
        'purpose': 'CANDIDATE_DIAGNOSTIC_EASY_IRRELEVANT_OBSERVATIONS_AND_POSITION',
        'base_cases': 40, 'base_pairs': 20, 'new_views_per_case': 2,
        'new_generations_per_model': 80, 'independent_new_cases': 0,
        'gold_policy': 'Original candidate actions/reasons/required reference IDs retained. New observations are unrelated office administrative records.',
        'changed': 'Two observations inserted. after=[original,d1,d2]; before=[d1,d2,original].',
        'unchanged': ['prompt', 'schema', 'model', 'local IDs from v03 control', 'reference_context',
                      'claim_id', 'question', 'proposal', 'original observation text', 'expected answers', 'review records'],
        'difficulty': 'EASY unrelated-topic distractors. Not near-domain conflicting/stale evidence.',
        'not_tested': ['legacy Contract20 overfitting', 'new-source/program generalization',
                       'withheld-evidence action switching', 'adversarial prompt injection',
                       'same-domain conflicting observations', 'new source fact selection'],
        'synthetic_distractor_texts': list(DISTRACTOR_TEXTS),
        'distractor_ids_by_case': distractors, 'files': files,
        'file_sha256': {view: hashlib.sha256(b).hexdigest() for view, b in payloads.items()},
        'model_specs': specs, 'frozen_files': frozen, 'script_sha256': digest(Path(__file__)),
        'metric_policy': 'Keep dcurr subset contract score. Add exact reference-set selection matched to an allowed answer; extra distractor citations count separately.',
        'build_environment_note': 'The generator has CPU tests. User GPU is exercised only by the generated evaluation commands.',
    }
    target.mkdir(parents=True, exist_ok=False)
    for view, body in payloads.items():
        local_path(root, files[view]).write_bytes(body)
    save_json(target / 'manifest.json', manifest)
    (target / 'run_evaluations.sh').write_text(command_lines(root, manifest), encoding='utf-8')
    (target / 'README_PROBE.txt').write_text(
        'Same 40 cases, not 120 independent questions. Existing renamed control is reused.\n'
        'Two synthetic office-administration observations are unrelated to the reviewed engineering proposal.\n'
        'Read manifest.json synthetic_distractor_texts before executing. No case/action or source approval was changed.\n'
        'Run the generated shell script from WSL, then evidence_probe_v04.py compare.\n', encoding='utf-8')
    print('EVIDENCE SELECTION BUILD: PASS')
    print('Same 40 cases / 20 pairs; two new 40-case views per model; no new independent cases.')
    print('Control reuses measured v03 ID-renamed results, including TH01-P05-A failures.')
    print('Local irrelevant observation IDs are VALID; copying them is detected by a NEW metric.')
    print('Source metadata IDs remain INVALID as evidence_refs; the existing validator is unchanged.')
    for text in DISTRACTOR_TEXTS:
        print('Synthetic distractor:', text)
    print('Execute:', 'bash ' + str(outdir / 'run_evaluations.sh'))


def action_value(sc):
    obj = sc['parsed']
    return obj.get('action') if isinstance(obj, dict) else None


def reference_signature(sc):
    obj = sc['parsed']
    refs = obj.get('evidence_refs') if isinstance(obj, dict) else None
    if sc['evidence_refs_list_of_strings']:
        return sorted(refs)  # Order is not relevant; preserve duplicates.
    return refs


def compare(root: Path, outdir: Path) -> None:
    root = root.resolve(); target = local_path(root, outdir)
    manifest = strict_loads((target / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != VERSION or manifest['script_sha256'] != digest(Path(__file__)):
        raise ValueError('Helper/manifest changed after build')
    freeze_check(root, manifest['frozen_files'])
    views = {}
    for view in VIEWS:
        path = local_path(root, manifest['files'][view])
        if digest(path) != manifest['file_sha256'][view]:
            raise ValueError('Probe data changed: ' + view)
        views[view] = by_id(read_jsonl(path))
    if any(set(views[v]) != set(views['control']) for v in VIEWS):
        raise ValueError('Different case sets across views')
    summary_path = target / 'comparison.json'; detail_path = target / 'comparison_cases.jsonl'
    if summary_path.exists() or detail_path.exists():
        raise ValueError('Comparison exists; nothing overwritten')
    common = runtime_common(root)
    details = []
    report = {
        'version': VERSION, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'interpretation': 'Same-case, easy irrelevant-observation and order diagnostic; not new-program generalization or proof against overfitting.',
        'base_cases': 40, 'base_pairs': 20, 'generated_views_are_not_independent_samples': True,
        'models': {}, 'generation_result_hashes': {},
        'metric_note': 'Legacy subset score permits extra supplied refs. Strict selection requires an exact allowed gold set plus legacy contract validity. Raw outputs are not repaired.',
    }
    for label in MODELS:
        data = {}; metrics = {}; records = []
        spec = manifest['model_specs'][label]
        for view in VIEWS:
            path = local_path(root, spec['result_files'][view])
            result = result_ids(read_jsonl(path), list(views[view].values()))
            scored = {}
            for cid, case in views[view].items():
                ids = [] if view == 'control' else manifest['distractor_ids_by_case'][cid]
                sc = score(common, case, result[cid], ids)
                if not sc['stored_score_agrees']:
                    raise ValueError(f'{label}/{view}/{cid}: stored and current scores disagree')
                scored[cid] = sc
            data[view] = scored
            metrics[view] = summarise([{'pair_id': views[view][cid]['pair_id'], 'score': s} for cid, s in scored.items()])
            report['generation_result_hashes'][label + '/' + view] = digest(path)
        for cid, case in views['control'].items():
            sc = {view: data[view][cid] for view in VIEWS}
            r = {
                'model': label, 'case_id': cid, 'pair_id': case['pair_id'],
                'scores': sc,
                'action_changed_control_to_after': action_value(sc['control']) != action_value(sc['after']),
                'action_changed_control_to_before': action_value(sc['control']) != action_value(sc['before']),
                'position_changed_action': action_value(sc['after']) != action_value(sc['before']),
                'position_changed_reference_choice': reference_signature(sc['after']) != reference_signature(sc['before']),
                'control_strict_pass_lost_after': sc['control']['strict_selection_contract_pass'] and not sc['after']['strict_selection_contract_pass'],
                'control_strict_pass_lost_before': sc['control']['strict_selection_contract_pass'] and not sc['before']['strict_selection_contract_pass'],
                'all_three_views_strict_pass': all(s['strict_selection_contract_pass'] for s in sc.values()),
            }
            records.append(r)
        report['models'][label] = {
            'views': metrics,
            'control_strict_pass_denominator': metrics['control']['strict_selection_contract_pass'],
            'action_changed_after': sum(r['action_changed_control_to_after'] for r in records),
            'action_changed_before': sum(r['action_changed_control_to_before'] for r in records),
            'position_changed_action': sum(r['position_changed_action'] for r in records),
            'position_changed_reference_choice': sum(r['position_changed_reference_choice'] for r in records),
            'control_strict_passes_lost_after': sum(r['control_strict_pass_lost_after'] for r in records),
            'control_strict_passes_lost_before': sum(r['control_strict_pass_lost_before'] for r in records),
            'all_three_views_strict_pass': sum(r['all_three_views_strict_pass'] for r in records),
        }
        details.extend(records)
    save_json(summary_path, report)
    with detail_path.open('x', encoding='utf-8') as f:
        f.write(dump_jsonl(details))
    print('EVIDENCE SELECTION — SAME CASES / NEW OBSERVATIONS / CHANGED ORDER')
    print('model     view      action  legacy  strict-select  exact-refs  extra-obs  metadata-ID')
    for label, result in report['models'].items():
        for view, m in result['views'].items():
            print(f"{label:9s} {view:9s} {m['action_correct']:2d}/40   {m['legacy_subset_contract_pass']:2d}/40   "
                  f"{m['strict_selection_contract_pass']:2d}/40          {m['reference_choice_exact']:2d}/40       "
                  f"{m['rows_citing_distractors']:2d}          {m['rows_citing_metadata_source_ids']:2d}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Saved:', summary_path)
    print('Case details INCLUDING parsed outputs and validation errors:', detail_path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('build', 'compare'):
        a = sub.add_parser(name)
        a.add_argument('--root', type=Path, default=Path.cwd())
        a.add_argument('--outdir', type=Path, default=Path(DEFAULT_DIR))
        if name == 'build':
            a.add_argument('--seed', type=int, default=2026091904)
    args = p.parse_args()
    if args.command == 'build':
        build(args.root, args.outdir, args.seed)
    else:
        compare(args.root, args.outdir)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise SystemExit(f'STOP: {exc}\nNo training, automatic approval or output repair was performed.')
