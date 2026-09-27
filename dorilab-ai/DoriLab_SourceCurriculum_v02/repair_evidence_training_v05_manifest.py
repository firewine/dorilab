#!/usr/bin/env python3
"""Restore missing dataset sidecars for an already approved DoriLab v05 experiment.

Run beside evidence_training_v05.py and dcurr/. Uses that unchanged script's
load_plan(..., approved=True) to verify the original frozen experiment.
Creates only repeat210.manifest.json, position210.manifest.json and a repair
receipt. Does not create/reapprove data, patch the trainer, train, or remove runs.
Python standard library only in this file; no model/GPU initialization.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 'evidence-training-v05-sidecar-repair-1'
DEFAULT_OUTDIR = 'data/evidence_training_v05'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f'Duplicate JSON key: {key}')
            value[key] = item
        return value
    def invalid(value):
        raise ValueError(f'Invalid JSON constant: {value}')
    value = json.loads(path.read_text(encoding='utf-8-sig'),
                       object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError(f'JSON object required: {path}')
    return value


def load_wrapper(root: Path):
    path = root / 'evidence_training_v05.py'
    if not path.is_file():
        raise ValueError('Run in DoriLab_SourceCurriculum_v02 beside evidence_training_v05.py.')
    spec = importlib.util.spec_from_file_location('_v05_sidecar_repair_wrapper', path)
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load the existing v05 wrapper.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.VERSION != 'evidence-training-v0.5.0':
        raise ValueError('This repair targets the unmodified evidence-training-v0.5.0 script.')
    return module


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def system_hashes(rows: list[dict[str, Any]]) -> list[str]:
    values = set()
    for row in rows:
        messages = row.get('messages')
        if not isinstance(messages, list) or not messages:
            raise ValueError('Training row has no messages.')
        if messages[0].get('role') != 'system' or messages[-1].get('role') != 'assistant':
            raise ValueError('Expected the existing system ... assistant message contract.')
        if not all(isinstance(m.get('content'), str) for m in messages):
            raise ValueError('This repair supports the released text-only training rows.')
        values.add(hashlib.sha256(messages[0]['content'].encode('utf-8')).hexdigest())
    return sorted(values)


def plan_repair(root: Path, outdir: Path) -> dict[str, Any]:
    wrapper = load_wrapper(root)
    # Validates the wrapper hash, all frozen inputs, approval, candidate/released
    # bytes and unchanged user review files. Never bypass this validation.
    target, plan, _ = wrapper.load_plan(root, outdir, True)
    approval_path = target / 'approval.json'
    approval = read_json(approval_path)
    if approval.get('dataset_sha256') != plan['candidate_sha256']:
        raise ValueError('Approval dataset hashes do not match the frozen plan.')

    parent_data = wrapper.relpath(root, wrapper.TRAIN)
    parent_path = parent_data.with_suffix('.manifest.json')
    parent = read_json(parent_path)
    required = ('data_sha256', 'prompt_file_sha256', 'legacy_prompt_sha256',
                'review_csv_sha256', 'source_review_sha256', 'contract_file_sha256',
                'source_ids', 'program_groups', 'system_prompt_hashes')
    missing = [key for key in required if key not in parent]
    if missing:
        raise ValueError('Original reviewed 170-row manifest lacks: ' + ', '.join(missing))
    if parent.get('records') != 170 or parent.get('physics_records') != 20 or parent.get('pairs') != 10 or parent.get('contract_records') != 150:
        raise ValueError('Original reviewed build must be 170 rows / 20 Physics / 10 pairs / 150 Contract.')
    comparisons = {
        parent_data: parent['data_sha256'],
        root / 'dcurr/prompts.py': parent['prompt_file_sha256'],
        root / 'dcurr/prompts_legacy.py': parent['legacy_prompt_sha256'],
        root / 'data/review_decisions.csv': parent['review_csv_sha256'],
        root / 'data/source_review.csv': parent['source_review_sha256'],
        root.parent / 'data/train150_v01.jsonl': parent['contract_file_sha256'],
    }
    for path, expected in comparisons.items():
        if sha256(path) != expected:
            raise ValueError(f'Original reviewed build no longer matches: {path}. Preserve files; do not re-hash to hide a change.')

    mixed = wrapper.read_jsonl(parent_data)
    contract = wrapper.read_jsonl(root.parent / 'data/train150_v01.jsonl')
    cases = wrapper.read_jsonl(wrapper.relpath(root, wrapper.CASES))
    selected = wrapper.recover_selected(mixed, contract, cases)
    wrapper.check_reviews(root, selected)
    if sorted(selected) != plan['selected_case_ids']:
        raise ValueError('Approved case selection differs from the frozen augmentation plan.')
    sources = sorted({item['case']['source_id'] for item in selected.values()})
    groups = sorted({g for item in selected.values() for g in item['case']['source_program_groups']})
    if sources != sorted(parent['source_ids']) or groups != sorted(parent['program_groups']):
        raise ValueError('Source/program metadata disagrees with the reviewed parent dataset.')
    if (plan['rows_per_arm'], plan['contract_rows'], plan['physics_presentations'], plan['independent_physics_cases']) != (210, 150, 60, 20):
        raise ValueError('Unexpected v05 data budget.')
    if len(plan['selected_pair_ids']) != 10:
        raise ValueError('Expected ten original Physics pairs.')

    plans = {}
    rows_by_arm = {}
    contract_messages = Counter(wrapper.canon(r['messages']) for r in contract)
    for arm in wrapper.ARMS:
        data_path = wrapper.relpath(root, plan['arms'][arm]['training_data'])
        rows = wrapper.read_jsonl(data_path)
        rows_by_arm[arm] = rows
        if len(rows) != 210 or len({r['id'] for r in rows}) != 210:
            raise ValueError(f'{arm}: expected 210 unique row IDs.')
        kinds = Counter(r.get('v05_metadata', {}).get('kind') for r in rows)
        if kinds != {'contract': 150, 'physics': 60}:
            raise ValueError(f'{arm}: presentation counts differ: {kinds}')
        physics = [r for r in rows if r['v05_metadata']['kind'] == 'physics']
        exposure = Counter(r['v05_metadata']['parent_case_id'] for r in physics)
        if exposure != {cid: 3 for cid in selected}:
            raise ValueError(f'{arm}: not three presentations of each approved Physics case.')
        if any(r['v05_metadata'].get('arm') != arm for r in rows):
            raise ValueError(f'{arm}: row arm tag differs.')
        observed_contract = Counter(wrapper.canon(r['messages']) for r in rows if r['v05_metadata']['kind'] == 'contract')
        if observed_contract != contract_messages:
            raise ValueError(f'{arm}: Contract150 messages changed.')
        sh = system_hashes(rows)
        if sh != sorted(parent['system_prompt_hashes']):
            raise ValueError(f'{arm}: embedded system prompts differ from reviewed parent.')

        manifest = {
            'build': VERSION,
            'data_sha256': sha256(data_path),
            'records': 210,
            'contract_records': 150,
            'physics_records': 60,
            'unique_physics_cases': 20,
            'pairs': 10,
            'counting_note': 'physics_records counts 60 presentations of 20 original cases; pairs counts 10 original pairs, not 30 independent pairs.',
            'source_ids': sources,
            'program_groups': groups,
            'prompt_file_sha256': parent['prompt_file_sha256'],
            'legacy_prompt_sha256': parent['legacy_prompt_sha256'],
            'system_prompt_hashes': sh,
            'review_csv_sha256': parent['review_csv_sha256'],
            'source_review_sha256': parent['source_review_sha256'],
            'contract_file_sha256': parent['contract_file_sha256'],
            'parent_training_data': rel(root, parent_data),
            'parent_training_data_sha256': parent['data_sha256'],
            'parent_data_manifest': rel(root, parent_path),
            'parent_data_manifest_sha256': sha256(parent_path),
            'augmentation_arm': arm,
            'augmentation_manifest': rel(root, target / 'manifest.json'),
            'augmentation_manifest_sha256': sha256(target / 'manifest.json'),
            'augmentation_approval_file': rel(root, approval_path),
            'augmentation_approval_sha256': sha256(approval_path),
            'augmentation_approval_scope': approval.get('scope'),
            'row_alignment_sha256': sha256(target / 'row_alignment.json'),
            'repair_script_sha256': sha256(Path(__file__)),
            'separation_note': plan['interpretation'],
            'provenance_note': 'Compatibility sidecar for an already approved augmentation; no original source/case review was changed or automatically granted.',
        }
        sidecar = data_path.with_suffix('.manifest.json')
        if sidecar.exists():
            if sidecar.is_symlink() or read_json(sidecar) != manifest:
                raise ValueError(f'An incompatible sidecar already exists: {sidecar}. It was not overwritten.')
            action = 'PRESERVE_IDENTICAL'
        else:
            action = 'CREATE'
            adapter = wrapper.relpath(root, plan['arms'][arm]['adapter'])
            if adapter.exists() or wrapper.training_record(target, arm).exists():
                raise ValueError(f'{arm}: a run directory/completion record already exists. This repair does not remove, resume or rewrite runs.')
        plans[arm] = {'path': sidecar, 'manifest': manifest, 'action': action}

    repeat, position = (rows_by_arm[a] for a in wrapper.ARMS)
    if any(a['id'] != b['id'] or a['messages'][0] != b['messages'][0] or a['messages'][-1] != b['messages'][-1] for a, b in zip(repeat, position)):
        raise ValueError('Arms differ in row schedule, system message or exact answer text.')

    # Preserve the already completed tokenizer audit and pinned model revision.
    audit_path = target / 'preflight_pair.json'
    if audit_path.exists():
        audit = read_json(audit_path)
        for arm in wrapper.ARMS:
            report = audit['arms'][arm]
            if (report.get('status'), report.get('records'), report.get('silent_truncation')) != ('PASS', 210, False):
                raise ValueError('Previous preflight is not a complete PASS for ' + arm)
            if report.get('data_sha256') != plans[arm]['manifest']['data_sha256']:
                raise ValueError('Preflight/data hashes differ for ' + arm)
        if audit['arms']['repeat']['total_answer_tokens'] != audit['arms']['position']['total_answer_tokens']:
            raise ValueError('Preflight answer-token counts differ.')
    revision_path = target / 'base_revision.json'
    if revision_path.exists():
        revision = read_json(revision_path)
        if revision.get('model') != plan['model'] or not isinstance(revision.get('revision'), str) or len(revision['revision']) != 40:
            raise ValueError('Invalid pinned base revision record.')

    protected = set(comparisons) | {parent_path, target / 'manifest.json', approval_path,
                                    root / 'evidence_training_v05.py'}
    protected |= {wrapper.relpath(root, p) for p in plan['frozen_files']}
    protected |= {Path(p) for p in plan['external_frozen_files']}
    protected |= {wrapper.relpath(root, plan['arms'][a]['training_data']) for a in wrapper.ARMS}
    protected |= {p for p in (audit_path, revision_path) if p.exists()}
    snapshot = {str(p.resolve()): sha256(p) for p in protected}
    return {'wrapper': wrapper, 'target': target, 'plan': plan, 'plans': plans, 'protected': snapshot}


def run(root: Path, outdir: Path, *, check_only: bool = False) -> dict[str, Any]:
    result = plan_repair(root, outdir)
    wrapper = result['wrapper']
    receipt_path = result['target'] / 'manifest_repair_v05_r1.json'
    if receipt_path.exists():
        old_receipt = read_json(receipt_path)
        if old_receipt.get('repair_version') != VERSION:
            raise ValueError('Unknown existing repair receipt; preserved.')
        if old_receipt.get('repair_script_sha256') != sha256(Path(__file__)):
            raise ValueError('Repair script differs from the prior receipt; preserved.')
        if old_receipt.get('augmentation_manifest_sha256') != sha256(result['target'] / 'manifest.json'):
            raise ValueError('Repair receipt belongs to another plan.')
        for arm, item in result['plans'].items():
            if item['path'].exists() and sha256(item['path']) != old_receipt['sidecars'][arm]['sha256']:
                raise ValueError('Sidecar differs from the repair receipt.')
    for arm, item in result['plans'].items():
        print(f"{arm}: {item['action']} {rel(root, item['path'])}")
        print('  210 rows = 150 Contract + 60 Physics presentations (20 unique cases / 10 original pairs)')
    if check_only:
        print('CHECK PASS. No files written. Run without --check-only to create the missing sidecars.')
        return {'status': 'CHECK_PASS'}

    for item in result['plans'].values():
        if item['action'] == 'CREATE':
            wrapper.write_json(item['path'], item['manifest'])  # exclusive creation, no overwrite
    # Re-run the original frozen-plan gate after writing only NEW sidecars.
    wrapper.load_plan(root, outdir, True)
    for filename, digest in result['protected'].items():
        if sha256(Path(filename)) != digest:
            raise ValueError('A protected original changed during repair: ' + filename)
    receipt = {
        'repair_version': VERSION,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'repair_script_sha256': sha256(Path(__file__)),
        'augmentation_manifest_sha256': sha256(result['target'] / 'manifest.json'),
        'sidecars': {arm: {'path': rel(root, item['path']), 'sha256': sha256(item['path'])}
                     for arm, item in result['plans'].items()},
        'protected_files_unchanged': True,
        'protected_file_count': len(result['protected']),
        'original_plan_and_approval_gate': 'PASS',
        'gpu_training_performed_by_repair': False,
    }
    if not receipt_path.exists():
        wrapper.write_json(receipt_path, receipt)
    print('MANIFEST REPAIR: PASS')
    print('Original data, review CSVs, prompts, trainer, plan, approval and logs preserved.')
    print('No model loaded and no training started by this repair.')
    print('Next: python evidence_training_v05.py train')
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--outdir', type=Path, default=Path(DEFAULT_OUTDIR))
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    run(args.root.resolve(), args.outdir, check_only=args.check_only)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as exc:
        raise SystemExit('STOP: ' + str(exc) + '\nExisting files were not deliberately overwritten or reset. Preserve the message and logs.')
