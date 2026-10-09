"""Run three synthetic SourceReview shape checks through the authenticated loopback API."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


HERE = Path('/workspace/dorilab/inference')
TOKEN = Path('/root/.config/dorilab/inference.token')
OVERLAY = HERE / 'contracts/service_contracts.json'
BASE_URL = 'http://127.0.0.1:8080'
ALLOWED_REASONS = {
    'AS_RUN_MISSING', 'BOUNDARY_CONDITION_UNRESOLVED', 'CONFIGURATION_SCOPE_UNRESOLVED',
    'EVIDENCE_INTERPRETATION_ERROR', 'MEASUREMENT_MAPPING_MISMATCH',
    'METHOD_INTERPRETATION_ERROR', 'MODAL_INPUTS_MISSING', 'MODEL_SCOPE_EXCEEDED',
    'MODE_SELECTION_MISMATCH', 'MONITORING_COVERAGE_INSUFFICIENT',
    'SUPPORTING_EVIDENCE_MISSING', 'TEST_ARTIFACT_UNMODELED',
}


def packet(claim_id, question, target, scope, observations):
    return {
        'claim_id': claim_id,
        'review_question': question,
        'review_target': target,
        'scope': scope,
        'source_refs': [],
        'observations': observations,
        'request_catalog': [
            {'request_id': 'CURRENT_SCOPE_SUPPORTING_EVIDENCE',
             'description': 'Supporting evidence applicable to the current unit, configuration and run'},
            {'request_id': 'CURRENT_CONFIGURATION_RECORD',
             'description': 'The configuration record needed to establish applicability'},
            {'request_id': 'CURRENT_RUN_RECORD',
             'description': 'The as-run record needed to establish execution identity and conditions'},
        ],
        'scope_of_result': 'Synthetic contract-shape check only; no approval, compliance, or verification closure.',
    }


CASES = [
    {
        'name': 'missing',
        'expected_action': 'REQUEST_EVIDENCE',
        'packet': packet(
            'SYN-MISSING-01',
            'Is current-scope supporting evidence present for this synthetic input-readiness review?',
            {'kind': 'INPUT_READINESS', 'text': 'Review whether evidence is present for this synthetic question.'},
            {'unit_id': 'DORI-SYN', 'configuration_id': 'TVAC-SYN', 'run_id': 'RUN-SYN'},
            [],
        ),
    },
    {
        'name': 'sufficient',
        'expected_action': 'NO_ACTION_REQUIRED',
        'packet': packet(
            'SYN-SUFFICIENT-01',
            'Is the explicitly supplied current-scope input record present for this synthetic readiness review?',
            {'kind': 'INPUT_READINESS', 'text': 'Review only whether the named synthetic input record is present.'},
            {'unit_id': 'DORI-SYN', 'configuration_id': 'TVAC-SYN', 'run_id': 'RUN-SYN'},
            [{
                'evidence_id': 'OBS-SYN-CURRENT-INPUTS',
                'display_id': 'OBS-SYN-CURRENT-INPUTS',
                'scope': {'unit_id': 'DORI-SYN', 'configuration_id': 'TVAC-SYN', 'run_id': 'RUN-SYN'},
                'text': ('Synthetic current-scope record: the input record named by this limited presence '
                         'question is present for DORI-SYN, TVAC-SYN, RUN-SYN. It makes no compliance claim.'),
                'origin': 'SYNTHETIC_CONTRACT_TEST',
            }],
        ),
    },
    {
        'name': 'contradiction',
        'expected_action': 'CHALLENGE',
        'packet': packet(
            'SYN-CONTRADICTION-01',
            'Does the supplied observation support treating TVAC-OLD evidence as directly applicable to TVAC-NEW?',
            {'kind': 'PROPOSAL',
             'text': 'Treat OBS-SYN-WRONG-CONFIG as directly applicable to TVAC-NEW without an applicability record.'},
            {'unit_id': 'DORI-SYN', 'configuration_id': 'TVAC-NEW', 'run_id': 'RUN-SYN'},
            [{
                'evidence_id': 'OBS-SYN-WRONG-CONFIG',
                'display_id': 'OBS-SYN-WRONG-CONFIG',
                'scope': {'unit_id': 'DORI-SYN', 'configuration_id': 'TVAC-OLD', 'run_id': 'RUN-SYN'},
                'text': ('Synthetic record: this observation applies only to TVAC-OLD and does not establish '
                         'applicability to TVAC-NEW.'),
                'origin': 'SYNTHETIC_CONTRACT_TEST',
            }],
        ),
    },
]


def call(path, token, body=None):
    headers = {'Authorization': 'Bearer ' + token}
    raw = None
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE_URL + path, data=raw, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def validate(value, case):
    action = value.get('action')
    fields = {
        'NO_ACTION_REQUIRED': {'action', 'claim_id', 'evidence_refs'},
        'CHALLENGE': {'action', 'claim_id', 'reason', 'evidence_refs'},
        'REQUEST_EVIDENCE': {'action', 'claim_id', 'reason', 'evidence_refs', 'requested_evidence'},
    }
    errors = []
    if action != case['expected_action']:
        errors.append('ACTION_MISMATCH')
    if action not in fields or set(value) != fields.get(action):
        errors.append('ROOT_FIELDS_INVALID')
    if value.get('claim_id') != case['packet']['claim_id']:
        errors.append('CLAIM_ID_MISMATCH')
    supplied = {row['reference_id'] for row in case['packet']['source_refs']}
    supplied.update(row['evidence_id'] for row in case['packet']['observations'])
    refs = value.get('evidence_refs')
    if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(ref not in supplied for ref in refs):
        errors.append('EVIDENCE_REFS_INVALID')
    if action in {'CHALLENGE', 'REQUEST_EVIDENCE'} and value.get('reason') not in ALLOWED_REASONS:
        errors.append('REASON_INVALID')
    if action == 'REQUEST_EVIDENCE':
        allowed = {row['request_id'] for row in case['packet']['request_catalog']}
        requested = value.get('requested_evidence')
        if not isinstance(requested, list) or not requested or len(requested) != len(set(requested)) or any(v not in allowed for v in requested):
            errors.append('REQUESTED_EVIDENCE_INVALID')
    return errors


def main():
    token = TOKEN.read_text(encoding='utf-8').strip()
    overlay = json.loads(OVERLAY.read_text(encoding='utf-8'))
    contract = next(row for row in overlay['contracts'] if row['route'] == 'v15_rc1_cf1')
    output_dir = HERE / 'artifacts' / ('contract-conformance-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    output_dir.mkdir(exist_ok=False)
    receipts = []
    for case in CASES:
        print('CASE', case['name'], 'SUBMIT', flush=True)
        request = {
            'request_id': 'contractfix1-' + case['name'] + '-' + uuid.uuid4().hex,
            'contract_id': contract['id'],
            'user': json.dumps(case['packet'], ensure_ascii=False, sort_keys=True, separators=(',', ':')),
            'max_new_tokens': 384,
        }
        status, accepted = call('/v1/generations', token, request)
        if status != 202:
            raise RuntimeError(f"{case['name']}: submit HTTP {status}: {accepted}")
        while True:
            status, result = call('/v1/generations/' + accepted['id'], token)
            if status != 200:
                raise RuntimeError(f"{case['name']}: poll HTTP {status}: {result}")
            if result['status'] in {'completed', 'failed'}:
                break
            time.sleep(0.5)
        if result['status'] != 'completed':
            raise RuntimeError(f"{case['name']}: generation failed")
        try:
            parsed = json.loads(result['text'])
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{case['name']}: invalid JSON: {error.msg}") from error
        errors = validate(parsed, case)
        record = {
            'case': case['name'], 'expected_action': case['expected_action'], 'request': request,
            'accepted': accepted, 'result': result, 'parsed': parsed, 'validation_errors': errors,
        }
        (output_dir / (case['name'] + '.json')).write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('CASE', case['name'], 'RESULT', parsed.get('action'), errors or 'PASS', flush=True)
        receipts.append({
            'case': case['name'], 'expected_action': case['expected_action'],
            'actual_action': parsed.get('action'), 'validation_errors': errors,
            'request_id': result.get('request_id'), 'output_sha256': result.get('output_sha256'),
            'input_tokens': result.get('input_tokens'), 'generated_tokens': result.get('generated_tokens'),
            'elapsed_seconds': result.get('elapsed_seconds'), 'boot_id': result.get('boot_id'),
        })
    receipt = {
        'schema': 'dorilab.contract-conformance.v1', 'contract_id': contract['id'],
        'contract_route': contract['route'], 'parent_id': contract['parent_id'],
        'passed': all(not row['validation_errors'] for row in receipts), 'cases': receipts,
    }
    receipt['receipt_sha256'] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    (output_dir / 'CONFORMANCE_RECEIPT.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'directory': str(output_dir), **receipt}, ensure_ascii=False), flush=True)
    if not receipt['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
