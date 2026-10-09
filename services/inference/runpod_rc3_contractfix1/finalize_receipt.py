"""Write a non-secret deployment receipt after a verified contractfix run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request


HERE = Path('/workspace/dorilab/inference')
TOKEN = Path('/root/.config/dorilab/inference.token')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    conformance_dir = Path(sys.argv[1]).resolve()
    artifacts = (HERE / 'artifacts').resolve()
    if artifacts not in conformance_dir.parents:
        raise SystemExit('conformance receipt must be under the inference artifacts directory')
    conformance_path = conformance_dir / 'CONFORMANCE_RECEIPT.json'
    conformance = json.loads(conformance_path.read_text(encoding='utf-8'))
    if conformance.get('passed') is not True:
        raise SystemExit('conformance receipt is not passing')

    token = TOKEN.read_text(encoding='utf-8').strip()
    request = urllib.request.Request(
        'http://127.0.0.1:8080/version', headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=10) as response:
        version = json.load(response)
    model_receipt_path = HERE / 'run' / version['boot_id'] / 'model_receipt.json'
    model_receipt = json.loads(model_receipt_path.read_text(encoding='utf-8'))
    release_receipt = dict(model_receipt)
    release_receipt.pop('boot_id', None)
    release_receipt_id = hashlib.sha256(canonical(release_receipt)).hexdigest()
    if release_receipt_id != version['model_receipt_id']:
        raise SystemExit('model release receipt still depends on boot or does not match /version')
    if not any(row['id'] == conformance['contract_id'] for row in version['contracts']):
        raise SystemExit('passing contract is absent from /version')

    service = json.loads((HERE / 'run/service.json').read_text(encoding='utf-8'))
    manifest = {
        'schema': 'dorilab.contractfix-deployment.v2',
        'deployed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'state': 'READY_CONFORMANCE_PASS',
        'contract_id': conformance['contract_id'],
        'contract_route': conformance['contract_route'],
        'parent_id': conformance['parent_id'],
        'boot_id': version['boot_id'],
        'pid': service['pid'],
        'model_release_receipt_id': release_receipt_id,
        'model_runtime_sha256': sha(HERE / 'model_runtime.py'),
        'conformance_receipt': str(conformance_path),
        'conformance_receipt_sha256': sha(conformance_path),
        'conformance_cases': len(conformance['cases']),
        'weights_changed': False,
        'adapter_changed': False,
        'validator_relaxed': False,
        'output_repaired': False,
    }
    manifest['manifest_sha256'] = hashlib.sha256(canonical(manifest)).hexdigest()
    output = HERE / 'artifacts/contractfix1-deployment.json'
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
