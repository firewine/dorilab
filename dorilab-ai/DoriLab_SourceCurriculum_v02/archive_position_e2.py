#!/usr/bin/env python3
"""Read-only project snapshot for the evaluated position e2 candidate.

Run from ~/dorilab-ai/DoriLab_SourceCurriculum_v02.
No model loading, training, package installation, source edits, or implicit resume.
The ZIP includes the LoRA adapter, not the base-model weights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile

ADAPTER_SHA256 = 'c16813cc75b33133fbdc4065e991ff0bea9580a75440900eae0fc2be2e4d44c5'
TRAINING_DATA_SHA256 = '52045fec4cbab795b7863f9e32e366aa3485c2f66f07ddc9a7142a52b5fd1c81'
VIEWS = ('control', 'after', 'before')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if any(not isinstance(r, dict) for r in rows):
        raise ValueError(f'Expected object rows: {path}')
    return rows


def collect(root: Path, expected_adapter: str = ADAPTER_SHA256,
            expected_data: str = TRAINING_DATA_SHA256) -> tuple[dict[str, Path], dict]:
    root = root.resolve()
    adapter = root / 'runs/evidence_training_v05_position_e2'
    required = [
        adapter / 'adapter_model.safetensors', adapter / 'adapter_config.json',
        adapter / 'RUN_MANIFEST.json', adapter / 'TRAIN_RESULT.json',
        root / 'data/evidence_training_v05/position210.jsonl',
        root / 'data/evidence_training_v05/position210.manifest.json',
        root / 'data/evidence_training_v05/manifest.json',
        root / 'data/evidence_training_v05/approval.json',
        root / 'data/evidence_training_v05/comparison.json',
        root / 'data/evidence_training_v05/comparison_cases.jsonl',
        root / 'data/action_schema_v02.json', root / 'data/physics_candidates40_v02.jsonl',
        root / 'data/review_decisions.csv', root / 'data/source_review.csv',
    ]
    casefiles = dict(control='control40.jsonl', after='irrelevant_after40.jsonl', before='irrelevant_before40.jsonl')
    for view in VIEWS:
        required += [root / f'reports/evidence_training_v05_position_e2_{view}.jsonl',
                     root / f'reports/evidence_training_v05_position_e2_{view}.summary.json',
                     root / 'data/evidence_probe_v04' / casefiles[view]]
    for name in ('common.py', 'train.py', 'model_io.py', 'evaluate.py', 'prompts.py', 'prompts_legacy.py'):
        required.append(root / 'dcurr' / name)
    contract = root.parent / 'eval/results/evidence_training_v05_position_e2_contract_dev.jsonl'
    required.append(contract)
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise ValueError('Required file(s) missing; no training is needed. Check paths:\n' + '\n'.join(missing))
    if sha256(adapter / 'adapter_model.safetensors') != expected_adapter:
        raise ValueError('Adapter hash differs from the evaluated e2 model; snapshot stopped.')
    if sha256(root / 'data/evidence_training_v05/position210.jsonl') != expected_data:
        raise ValueError('position210 training data differs from the evaluated experiment.')
    run = json.loads((adapter / 'RUN_MANIFEST.json').read_text(encoding='utf-8'))
    snapshots = {}
    ids = None
    for view in VIEWS:
        rows = read_jsonl(root / f'reports/evidence_training_v05_position_e2_{view}.jsonl')
        sm = json.loads((root / f'reports/evidence_training_v05_position_e2_{view}.summary.json').read_text(encoding='utf-8'))
        current_ids = [r['case_id'] for r in rows]
        if len(rows) != 40 or len(set(current_ids)) != 40:
            raise ValueError(f'{view}: expected 40 unique cases.')
        if ids is not None and set(current_ids) != ids:
            raise ValueError('Different case IDs across views.')
        ids = set(current_ids)
        if sm['adapter_sha256'] != expected_adapter:
            raise ValueError(f'{view}: evaluation adapter identity mismatch.')
        if sm['case_file_sha256'] != sha256(root / 'data/evidence_probe_v04' / casefiles[view]):
            raise ValueError(f'{view}: evaluation input file changed.')
        for sm_key, row_key in [('strict_json_valid', 'strict_json_valid'), ('schema_and_refs_valid', 'schema_and_refs_valid'),
                                ('action_correct', 'action_ok'), ('contract_pass', 'contract_pass')]:
            if sum(bool(r[row_key]) for r in rows) != sm[sm_key]:
                raise ValueError(f'{view}: summary/raw result mismatch: {sm_key}')
        snapshots[view] = {'action_correct': sm['action_correct'], 'contract_pass': sm['contract_pass'], 'records': sm['records']}
    cr = read_jsonl(contract)
    if len(cr) != 20 or len({r.get('id', r.get('case_id')) for r in cr}) != 20:
        raise ValueError('Contract regression file must contain 20 distinct cases.')
    # Save current source files with identity. This records current code, not a claim
    # that every file has been independently verified against training-time code.
    paths = {('legacy_eval/' + p.name) if p == contract else p.relative_to(root).as_posix(): p for p in required}
    for p in sorted(adapter.iterdir()):
        if p.is_file() and p.suffix.lower() not in {'.ttf', '.otf', '.woff', '.woff2'}:
            paths[p.relative_to(root).as_posix()] = p
    for p in sorted((root / 'dcurr').glob('*.py')):
        paths[p.relative_to(root).as_posix()] = p
    for name in ('evidence_training_v05.py', 'evidence_probe_v04.py', 'id_probe_v03.py', 'repair_evidence_training_v05_manifest.py'):
        p = root / name
        if p.is_file():
            paths[p.relative_to(root).as_posix()] = p
    metadata = {
        'snapshot_version': 'position-e2-development-candidate-v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'DEVELOPMENT_CANDIDATE_SNAPSHOT_NOT_PRODUCTION_APPROVAL',
        'project_root': str(root), 'base_weights_included': False,
        'base_model': run.get('base_model'),
        'base_revision_requested': run.get('base_revision_requested'),
        'base_revision_resolved': run.get('base_revision_resolved'),
        'adapter_sha256': expected_adapter, 'training_data_sha256': expected_data,
        'physics_results': snapshots,
        'contract_dev': {'records': len(cr), 'pass': sum(bool(r.get('pass')) for r in cr)},
        'scope_note': 'Known-case development evaluation. Three views are not independent samples. No files relabelled, no model inference or training.',
        'file_table': {name: {'bytes': p.stat().st_size, 'sha256': sha256(p)} for name, p in sorted(paths.items())},
    }
    return paths, metadata


def write_archive(path: Path, paths: dict[str, Path], metadata: dict) -> None:
    if path.exists():
        raise FileExistsError(f'Existing archive preserved: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for name, p in sorted(paths.items()):
            if sha256(p) != metadata['file_table'][name]['sha256']:
                raise ValueError(f'File changed during snapshot: {p}. Incomplete ZIP preserved.')
            z.write(p, name)
        z.writestr('SNAPSHOT_MANIFEST.json', json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC test failed.')
        for name, rec in metadata['file_table'].items():
            h = hashlib.sha256()
            with z.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(block)
            if h.hexdigest() != rec['sha256']:
                raise ValueError(f'Archived hash mismatch: {name}')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--out', type=Path, default=Path('reports/position_e2_candidate_v01.zip'))
    a = p.parse_args()
    root = a.root.resolve()
    out = a.out if a.out.is_absolute() else root / a.out
    if out.exists():
        raise SystemExit(f'Existing archive preserved: {out}')
    paths, metadata = collect(root)
    write_archive(out, paths, metadata)
    print('POSITION E2 SNAPSHOT: PASS')
    print('Archive:', out)
    print('SHA256:', sha256(out))
    print('Base weights not included; original files are unchanged.')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(f'STOP: {exc}')
