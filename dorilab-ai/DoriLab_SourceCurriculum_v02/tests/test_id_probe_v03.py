import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('probe', str(Path(__file__).resolve().parents[1] / 'id_probe_v03.py'))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def case(i=1, variant='A'):
    r = {
        'case_id': f'C-{i}-{variant}', 'pair_id': f'P-{i}', 'variant': variant,
        'source_id': 'SOURCE', 'source_fact_ids': [f'SF-{i}'],
        'role': 'CRITIC', 'domain': 'TEST_ONLY',
        'packet': {
            'review_question': 'Review this synthetic proposal.', 'claim_id': f'CLM-{i}',
            'reference_context': [{'reference_id': f'SF-{i}', 'source_id': 'SOURCE', 'text': 'Synthetic source principle.'}],
            'case_packet': {'evidence': [{'evidence_id': 'OBS-1', 'text': 'Synthetic observation, not a real experiment.'}], 'proposal': 'Proposal ' + variant},
            'allowed_request_ids': ['INPUT_X'],
        },
        'expected': {'action': 'CHALLENGE' if variant == 'A' else 'NO_ACTION_REQUIRED',
                     'claim_id': f'CLM-{i}', 'evidence_refs': [f'SF-{i}', 'OBS-1']},
    }
    if variant == 'A':
        r['expected']['reason'] = 'TEST_REASON'
    return r


class FakeCommon:
    @staticmethod
    def validate_answer(a, c):
        if not isinstance(a, dict):
            raise ValueError('object')
        refs = a.get('evidence_refs')
        if not isinstance(refs, list) or not all(isinstance(x, str) for x in refs):
            raise ValueError('ref type')
        if not set(refs) <= set(p.evidence_definitions(c)):
            raise ValueError('unknown reference')
        if a.get('claim_id') != c['packet']['claim_id']:
            raise ValueError('claim')
        if a.get('action') not in {'CHALLENGE', 'NO_ACTION_REQUIRED'}:
            raise ValueError('action')

    @staticmethod
    def answer_matches(e, a):
        return all(set(v) <= set(a.get(k, [])) if k == 'evidence_refs' else a.get(k) == v
                   for k, v in e.items())


class Tests(unittest.TestCase):
    def test_01_preserves_source_input_object(self):
        cases = [case(), case(variant='B')]; old = copy.deepcopy(cases)
        p.make_probe(cases, 9); self.assertEqual(cases, old)

    def test_02_deterministic(self):
        self.assertEqual(p.make_probe([case()], 9), p.make_probe([case()], 9))

    def test_03_seed_changes_ids(self):
        self.assertNotEqual(p.make_probe([case()], 9), p.make_probe([case()], 10))

    def test_04_pair_shared_mapping(self):
        _, maps = p.make_probe([case(), case(variant='B')], 9)
        self.assertEqual(maps[0]['id_mapping'], maps[1]['id_mapping'])

    def test_05_gold_id_update(self):
        rows, maps = p.make_probe([case()], 9)
        self.assertEqual(rows[0]['expected']['evidence_refs'], [maps[0]['id_mapping'][x] for x in case()['expected']['evidence_refs']])

    def test_06_source_metadata_unchanged(self):
        c = case(); new, _ = p.make_probe([c], 9)
        self.assertEqual(new[0]['source_fact_ids'], c['source_fact_ids'])
        self.assertEqual(new[0]['source_id'], c['source_id'])

    def test_07_claim_and_physics_text_unchanged(self):
        c = case(); new, _ = p.make_probe([c], 9)
        a, b = c['packet'], new[0]['packet']
        self.assertEqual(a['claim_id'], b['claim_id'])
        self.assertEqual(a['case_packet']['proposal'], b['case_packet']['proposal'])
        self.assertEqual(a['case_packet']['evidence'][0]['text'], b['case_packet']['evidence'][0]['text'])
        self.assertEqual(a['reference_context'][0]['text'], b['reference_context'][0]['text'])

    def test_08_actions_and_reasons_unchanged(self):
        c = case(); new, _ = p.make_probe([c], 9)
        self.assertEqual(c['expected']['action'], new[0]['expected']['action'])
        self.assertEqual(c['expected']['reason'], new[0]['expected']['reason'])

    def test_09_alternatives_updated(self):
        c = case(); c['acceptable_answers'] = [copy.deepcopy(c['expected'])]
        new, _ = p.make_probe([c], 9)
        self.assertEqual(new[0]['acceptable_answers'][0], new[0]['expected'])

    def test_10_embedded_id_blocks(self):
        c = case(); c['packet']['case_packet']['proposal'] = 'Use OBS-1 directly.'
        with self.assertRaisesRegex(ValueError, 'embedded ID'):
            p.make_probe([c], 9)

    def test_11_duplicate_case_id_blocks(self):
        with self.assertRaises(ValueError):p.make_probe([case(), case()], 9)

    def test_12_duplicate_local_id_blocks(self):
        c = case(); c['packet']['case_packet']['evidence'].append(copy.deepcopy(c['packet']['case_packet']['evidence'][0]))
        with self.assertRaises(ValueError):p.make_probe([c], 9)

    def test_13_unknown_gold_reference_blocks(self):
        c = case(); c['expected']['evidence_refs'].append('OBS-MADEUP')
        with self.assertRaises(ValueError):p.make_probe([c], 9)

    def test_14_nested_gold_reference_blocks(self):
        c = case(); c['expected']['evidence_refs'] = [{'id': 'OBS-1'}]
        with self.assertRaises(ValueError):p.make_probe([c], 9)

    def test_15_all_old_ids_gone_from_packet(self):
        c = case(); new, maps = p.make_probe([c], 9)
        self.assertFalse(set(maps[0]['id_mapping']) & set(p.collect_strings(new[0]['packet'])))

    def test_16_key_order_preserved(self):
        c = case(); new, _ = p.make_probe([c], 9)
        self.assertEqual(list(c['packet']), list(new[0]['packet']))
        self.assertEqual(list(c['expected']), list(new[0]['expected']))

    def test_17_incomplete_results_block(self):
        with self.assertRaises(ValueError):p.require_result_ids([{'case_id': 'C-1-A'}], [case(), case(variant='B')])

    def test_18_score_wrong_typed_refs_fails_without_crash(self):
        c = case(); obj = copy.deepcopy(c['expected']);obj['evidence_refs']=[{'id': 'OBS-1'}]
        s=p.score(FakeCommon,c,{'parsed':obj,'contract_pass':False})
        self.assertFalse(s['contract_pass']);self.assertFalse(s['schema_and_refs_valid'])

    def test_19_score_mismatch_detected(self):
        c=case();s=p.score(FakeCommon,c,{'parsed':c['expected'],'contract_pass':False})
        self.assertFalse(s['stored_score_agrees'])

    def test_20_json_duplicates_rejected(self):
        with self.assertRaises(ValueError):p.strict_loads('{"x":1,"x":2}')

    def test_21_freeze_change_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'a').write_text('a')
            m={'frozen_files':{'a':p.digest(root/'a')}}
            p.verify_frozen(root,m);(root/'a').write_text('b')
            with self.assertRaises(ValueError):p.verify_frozen(root,m)

    def test_22_integrated_build_and_compare_fake_runtime(self):
        # Synthetic cases and fake validator only. No user labels are approved here.
        cases=[case(i, v) for i in range(20) for v in ('A','B')]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();(root/'reports').mkdir();(root/'dcurr').mkdir()
            source=root/p.DEFAULT_CASES;source.write_text(p.dump_jsonl(cases),encoding='utf-8')
            specs=copy.deepcopy(p.MODELS)
            for rel in p.CODE_FILES:
                (root/rel).parent.mkdir(parents=True,exist_ok=True);(root/rel).write_text('# synthetic fixture')
            for label,s in specs.items():
                d=root/s['adapter'];d.mkdir(parents=True)
                (d/'adapter_model.safetensors').write_bytes(label.encode())
                (d/'adapter_config.json').write_text('{}')
                s['weight_sha256']=p.digest(d/'adapter_model.safetensors')
                rows=[{'case_id':c['case_id'],'parsed':copy.deepcopy(c['expected']),'contract_pass':True} for c in cases]
                (root/s['baseline']).write_text(p.dump_jsonl(rows))
            with patch.object(p,'MODELS',specs),patch.object(p,'EXPECTED_CASE_HASH',p.digest(source)),patch.object(p,'runtime_common',return_value=FakeCommon):
                p.build(root,Path(p.DEFAULT_DIR),9)
                probes=p.read_jsonl(root/p.DEFAULT_DIR/'idrename40.jsonl')
                for label,s in specs.items():
                    rows=[{'case_id':c['case_id'],'parsed':copy.deepcopy(c['expected']),'contract_pass':True} for c in probes]
                    (root/s['probe']).write_text(p.dump_jsonl(rows))
                p.compare(root,Path(p.DEFAULT_DIR))
                r=json.loads((root/p.DEFAULT_DIR/'comparison.json').read_text())
                self.assertEqual(r['models']['lr5e5']['id_renamed']['contract_pass'],40)
                self.assertEqual(r['models']['lr2e5']['rows_emitting_old_reference_ids'],0)
                # Existing output is refused; no overwrites.
                with self.assertRaises(ValueError):p.build(root,Path(p.DEFAULT_DIR),9)

    def test_23_missing_parsed_is_not_silently_inferred(self):
        with self.assertRaises(ValueError):p.result_output({'raw_output':'{}'})

    def test_24_new_ids_preserve_category_prefix(self):
        _,maps=p.make_probe([case()],9)
        for old,new in maps[0]['id_mapping'].items():
            self.assertEqual(old.split('-')[0],new.split('-')[0])
            self.assertNotEqual(old,new)

if __name__=='__main__':unittest.main(verbosity=2)
