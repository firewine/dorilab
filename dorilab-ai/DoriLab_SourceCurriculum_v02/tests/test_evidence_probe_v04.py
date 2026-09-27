import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# From archive root, or from project when the helper is beside dcurr/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence_probe_v04 as p


class FakeCommon:
    """Small local contract for CPU tests; not the user's actual evaluator."""
    @staticmethod
    def validate_answer(answer, case):
        if not isinstance(answer, dict):
            raise ValueError('answer not object')
        actions = {'CHALLENGE', 'REQUEST_EVIDENCE', 'NO_ACTION_REQUIRED'}
        if answer.get('action') not in actions:
            raise ValueError('unknown action')
        if answer.get('claim_id') != case['packet']['claim_id']:
            raise ValueError('claim_id mismatch')
        refs = answer.get('evidence_refs')
        if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
            raise ValueError('reference type')
        if len(refs) != len(set(refs)):
            raise ValueError('duplicate reference')
        if not set(refs) <= set(p.definitions(case)):
            raise ValueError('unprovided evidence reference')
        if answer['action'] in {'CHALLENGE', 'REQUEST_EVIDENCE'} and not isinstance(answer.get('reason'), str):
            raise ValueError('reason missing')
        if answer['action'] == 'REQUEST_EVIDENCE':
            req = answer.get('requested_evidence')
            if not isinstance(req, list) or not req or any(not isinstance(x, str) for x in req):
                raise ValueError('request list')
            if not set(req) <= set(case['packet']['allowed_request_ids']):
                raise ValueError('unprovided request')
    @staticmethod
    def answer_matches(expected, actual):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            av = actual.get(k)
            if k == 'evidence_refs':
                if not isinstance(av, list) or not all(x in av for x in v):
                    return False
            elif isinstance(v, list):
                if not isinstance(av, list) or sorted(v) != sorted(av):
                    return False
            elif av != v:
                return False
        return True


def fixture(n_pairs=2):
    rows = []
    for i in range(n_pairs):
        for side in ('A', 'B'):
            gold = {'action': 'CHALLENGE' if side == 'A' else 'NO_ACTION_REQUIRED',
                    'claim_id': f'CLM-{i}', 'evidence_refs': [f'SF-{1000+i}', f'OBS-{2000+i}']}
            if side == 'A':
                gold['reason'] = 'WRONG_PROPOSAL'
            rows.append({
                'case_id': f'CASE-{i}-{side}', 'pair_id': f'PAIR-{i}', 'variant': side,
                'human_review_status': 'PENDING', 'source_id': 'TH-01',
                'basis': 'SYNTHETIC_COUNTERFACTUAL',
                'packet': {
                    'claim_id': f'CLM-{i}', 'review_question': 'Review the supplied proposal.',
                    'reference_context': [{'reference_id': f'SF-{1000+i}', 'source_id': 'TH-01',
                                           'text': 'A synthetic source principle for a test fixture.'}],
                    'case_packet': {'evidence': [{'evidence_id': f'OBS-{2000+i}',
                                                   'text': 'Synthetic engineering observation.'}],
                                    'proposal': f'Synthetic {side} proposal.'},
                    'allowed_request_ids': ['MEASUREMENTS'],
                },
                'expected': gold,
            })
    return rows


def result(case, answer=None, common=FakeCommon):
    obj = copy.deepcopy(case['expected'] if answer is None else answer)
    valid = True
    try:
        common.validate_answer(obj, case)
    except Exception:
        valid = False
    matched = valid and any(common.answer_matches(a, obj) for a in p.answer_variants(case))
    return {'case_id': case['case_id'], 'parsed': obj, 'raw_output': json.dumps(obj),
            'contract_pass': bool(matched)}


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.cases = fixture()
        self.views, self.ids = p.make_views(self.cases, 123)
        self.case = self.views['after'][0]
        self.cid = self.case['case_id']

    def test_01_no_control_mutation(self):
        original = fixture(); snapshot = copy.deepcopy(original)
        p.make_views(original, 20)
        self.assertEqual(original, snapshot)

    def test_02_only_two_insertions(self):
        for view in self.views.values():
            for row in view:
                self.assertEqual(len(row['packet']['case_packet']['evidence']), 3)

    def test_03_gold_unchanged(self):
        for rows in self.views.values():
            for a, b in zip(rows, self.cases):
                self.assertEqual(a['expected'], b['expected'])

    def test_04_reference_text_unchanged(self):
        for a, b in zip(self.views['after'], self.cases):
            self.assertEqual(a['packet']['reference_context'], b['packet']['reference_context'])

    def test_05_proposal_unchanged(self):
        for a, b in zip(self.views['after'], self.cases):
            self.assertEqual(a['packet']['case_packet']['proposal'], b['packet']['case_packet']['proposal'])

    def test_06_source_metadata_unchanged(self):
        self.assertEqual(self.case['source_id'], 'TH-01')
        self.assertEqual(self.case['human_review_status'], 'PENDING')

    def test_07_same_new_ids_in_pair(self):
        self.assertEqual(self.ids[self.cases[0]['case_id']], self.ids[self.cases[1]['case_id']])

    def test_08_no_id_collisions(self):
        for c in self.views['before']:
            self.assertEqual(len(p.definitions(c)), 4)

    def test_09_same_content_other_order(self):
        for a, b in zip(self.views['after'], self.views['before']):
            ae = a['packet']['case_packet']['evidence']; be = b['packet']['case_packet']['evidence']
            self.assertEqual(ae[0], be[-1]); self.assertEqual(ae[1:], be[:2])

    def test_10_seed_reproducible(self):
        self.assertEqual(p.make_views(fixture(), 123), (self.views, self.ids))

    def test_11_incomplete_pair_rejected(self):
        with self.assertRaises(ValueError): p.make_views(fixture()[:-1], 123)

    def test_12_many_original_observations_rejected(self):
        cases = fixture(); cases[0]['packet']['case_packet']['evidence'].append({'evidence_id': 'OBS-99', 'text': 'extra'})
        with self.assertRaises(ValueError): p.make_views(cases, 123)

    def test_13_expected_unprovided_ref_rejected(self):
        cases = fixture(); cases[0]['expected']['evidence_refs'].append('TH-01')
        with self.assertRaises(ValueError): p.make_views(cases, 123)

    def test_14_perfect_selection_passes(self):
        sc = p.score(FakeCommon, self.case, result(self.case), self.ids[self.cid])
        self.assertTrue(sc['strict_selection_contract_pass']); self.assertTrue(sc['reference_choice_exact_any_allowed_set'])

    def test_15_superset_legacy_pass_strict_fail(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'].append(self.ids[self.cid][0])
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertTrue(sc['legacy_subset_contract_pass']); self.assertFalse(sc['strict_selection_contract_pass'])
        self.assertEqual(len(sc['distractor_reference_strings']), 1)

    def test_16_copy_all_refs_is_detected(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'] = list(p.definitions(self.case))
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertTrue(sc['required_refs_complete_any_allowed_set']); self.assertFalse(sc['reference_choice_exact_any_allowed_set'])
        self.assertEqual(sc['primary_reference_recall'], 1); self.assertEqual(sc['primary_reference_precision'], .5)

    def test_17_document_id_invalid_and_classified(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'].append('TH-01')
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertFalse(sc['schema_and_refs_valid']); self.assertEqual(sc['metadata_source_id_in_evidence_refs'], ['TH-01'])
        self.assertTrue(sc['reference_choice_exact_any_allowed_set'] is False)

    def test_18_missing_current_observation(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'] = [a['evidence_refs'][0]]
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertFalse(sc['required_refs_complete_any_allowed_set'])
        self.assertEqual(sc['missing_primary_gold_references'], ['OBS-2000'])

    def test_19_nested_refs_no_crash(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'] = [{'reference_id': 'SF-1000'}]
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertFalse(sc['evidence_refs_list_of_strings']); self.assertFalse(sc['strict_selection_contract_pass'])

    def test_20_ref_string_no_crash(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'] = 'SF-1000'
        self.assertFalse(p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])['evidence_refs_list_of_strings'])

    def test_21_wrong_reason_not_fixed_by_refs(self):
        a = copy.deepcopy(self.case['expected']); a['reason'] = 'OTHER_REASON'
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertTrue(sc['reference_choice_exact_any_allowed_set']); self.assertFalse(sc['strict_selection_contract_pass'])

    def test_22_duplicate_refs_rejected(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'].append(a['evidence_refs'][0])
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertTrue(sc['duplicate_reference_strings']); self.assertFalse(sc['reference_choice_exact_any_allowed_set'])

    def test_23_reference_order_irrelevant(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'].reverse()
        self.assertTrue(p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])['strict_selection_contract_pass'])

    def test_24_acceptable_alternative_respected(self):
        c = copy.deepcopy(self.case); alternative = copy.deepcopy(c['expected'])
        alternative['reason'] = 'AN_ALLOWED_REASON'
        c['acceptable_answers'] = [c['expected'], alternative]
        self.assertTrue(p.score(FakeCommon, c, result(c, alternative), self.ids[self.cid])['strict_selection_contract_pass'])

    def test_25_old_scorer_crosscheck_detects_disagreement(self):
        r = result(self.case); r['contract_pass'] = False
        self.assertFalse(p.score(FakeCommon, self.case, r, self.ids[self.cid])['stored_score_agrees'])

    def test_26_result_completeness_checked(self):
        with self.assertRaises(ValueError): p.result_ids([result(self.case)], self.views['after'])

    def test_27_json_duplicate_key_rejected(self):
        with self.assertRaises(ValueError): p.strict_loads('{"x":1,"x":2}')

    def test_28_json_nan_rejected(self):
        with self.assertRaises(ValueError): p.strict_loads('{"x":NaN}')

    def test_29_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError): p.local_path(Path(t), '../elsewhere')

    def test_30_local_contract_superset_check(self):
        p.runtime_contract_check(FakeCommon, self.case, self.ids[self.cid][0])

    def test_31_detail_preserves_output_and_error(self):
        a = copy.deepcopy(self.case['expected']); a['evidence_refs'].append('TH-01')
        sc = p.score(FakeCommon, self.case, result(self.case, a), self.ids[self.cid])
        self.assertEqual(sc['parsed'], a); self.assertEqual(sc['validation_error']['message'], 'unprovided evidence reference')

    def test_32_summary_counts_strict_separately(self):
        rows = []
        for case in self.views['after']:
            answer = copy.deepcopy(case['expected']); answer['evidence_refs'].append(self.ids[case['case_id']][0])
            rows.append({'pair_id': case['pair_id'], 'score': p.score(FakeCommon, case, result(case, answer), self.ids[case['case_id']])})
        s = p.summarise(rows)
        self.assertEqual(s['legacy_subset_contract_pass'], 4); self.assertEqual(s['strict_selection_contract_pass'], 0)
        self.assertEqual(s['rows_citing_distractors'], 4)

    def test_33_full_build_compare_in_temporary_project(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); prior_dir = root / 'data/id_probe_v03'; prior_dir.mkdir(parents=True)
            (root / 'reports').mkdir()
            cases = fixture(20)
            control = prior_dir / 'idrename40.jsonl'; control.write_text(p.dump_jsonl(cases), encoding='utf-8')
            specs = {}; frozen = {}
            for label in p.MODELS:
                rel = f'runs/{label}'; ad = root / rel; ad.mkdir(parents=True)
                for name in ('adapter_model.safetensors', 'adapter_config.json'):
                    f = ad / name; f.write_text('synthetic test fixture only', encoding='utf-8')
                    frozen[str(f.relative_to(root))] = p.digest(f)
                rf = f'reports/{label}_idprobe.jsonl'
                (root / rf).write_text(p.dump_jsonl([result(c) for c in cases]), encoding='utf-8')
                specs[label] = {'adapter': rel, 'weight_sha256': p.digest(ad / 'adapter_model.safetensors'), 'probe': rf}
            prior = {'version': 'id-probe-v0.3.0', 'frozen_files': frozen, 'probe_file': str(control.relative_to(root)),
                     'probe_sha256': p.digest(control), 'model_specs': specs}
            (prior_dir / 'manifest.json').write_text(json.dumps(prior), encoding='utf-8')
            with patch.object(p, 'runtime_common', return_value=FakeCommon):
                p.build(root, Path(p.DEFAULT_DIR), 123)
                d = root / p.DEFAULT_DIR; manifest = json.loads((d / 'manifest.json').read_text())
                for label in p.MODELS:
                    for view in ('after', 'before'):
                        modified = p.read_jsonl(root / manifest['files'][view]); answers = []
                        for c in modified:
                            a = copy.deepcopy(c['expected'])
                            if view == 'before': a['evidence_refs'].append(manifest['distractor_ids_by_case'][c['case_id']][0])
                            answers.append(result(c, a))
                        (root / manifest['model_specs'][label]['result_files'][view]).write_text(p.dump_jsonl(answers), encoding='utf-8')
                p.compare(root, Path(p.DEFAULT_DIR))
                summary = json.loads((d / 'comparison.json').read_text())
                for m in summary['models'].values():
                    self.assertEqual(m['views']['control']['strict_selection_contract_pass'], 40)
                    self.assertEqual(m['views']['after']['strict_selection_contract_pass'], 40)
                    self.assertEqual(m['views']['before']['legacy_subset_contract_pass'], 40)
                    self.assertEqual(m['views']['before']['strict_selection_contract_pass'], 0)
                    self.assertEqual(m['position_changed_action'], 0)
                    self.assertEqual(m['position_changed_reference_choice'], 40)
                self.assertEqual(len(p.read_jsonl(d / 'comparison_cases.jsonl')), 80)
                self.assertEqual(control.read_text(), p.dump_jsonl(cases))
                self.assertFalse((root / 'data/review_decisions.csv').exists())
                with self.assertRaises(ValueError): p.build(root, Path(p.DEFAULT_DIR), 123)
                with self.assertRaises(ValueError): p.compare(root, Path(p.DEFAULT_DIR))


if __name__ == '__main__':
    unittest.main()
