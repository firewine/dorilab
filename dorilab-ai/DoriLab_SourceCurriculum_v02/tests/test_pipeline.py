import unittest,copy,tempfile,json
from pathlib import Path
from dcurr.common import *
from dcurr.prompts import build_messages
from dcurr.prepare import select_approved

class PipelineTests(unittest.TestCase):
    def setUp(self):self.cs=cases();self.ss=sources()
    def test_01_source_count(self):self.assertEqual(len(self.ss),27)
    def test_02_six_domains(self):self.assertEqual(len({s['primary_domain'] for s in self.ss.values()}),6)
    def test_03_case_count(self):self.assertEqual(len(self.cs),40)
    def test_04_seed_unchanged(self):self.assertEqual(sha256(ROOT/'data/legacy32_unmodified.jsonl'),sha256(ROOT/'legacy/PhysicsSeed32_v01/data/physics_cases_seed32_v01.jsonl'))
    def test_05_all_answers_valid(self):
        for c in self.cs:validate_answer(c['expected'],c)
    def test_06_unknown_ref(self):
        c=self.cs[0];a=copy.deepcopy(c['expected']);a['evidence_refs']=['DOES_NOT_EXIST']
        with self.assertRaises(ValueError):validate_answer(a,c)
    def test_07_claim_mismatch(self):
        c=self.cs[0];a=copy.deepcopy(c['expected']);a['claim_id']='wrong'
        with self.assertRaises(ValueError):validate_answer(a,c)
    def test_08_strict_json_trailing(self):self.assertIsNone(strict_parse('{"action":"x"}|'))
    def test_09_strict_json_markdown(self):self.assertIsNone(strict_parse('```json\n{}\n```'))
    def test_10_json_array_not_object(self):self.assertIsNone(strict_parse('[]'))
    def test_11_no_gold_in_model_input(self):
        c=copy.deepcopy(self.cs[0]);c['expected']={'special':'GOLD_SENTINEL'};c['rationale_ko']='RATIONALE_SENTINEL'
        text=json.dumps(build_messages(c['role'],c['packet']))
        self.assertNotIn('GOLD_SENTINEL',text);self.assertNotIn('RATIONALE_SENTINEL',text)
    def test_12_mask_prefix(self):
        x=mask_completion([1,2],[3,4],9,10);self.assertEqual(x['labels'],[-100,-100,3,4,9])
    def test_13_no_silent_truncation(self):
        with self.assertRaises(ValueError):mask_completion([1,2],[3,4],9,4)
    def test_14_real_eos_supervised(self):
        self.assertEqual(mask_completion([8],[5],8,4)['labels'],[-100,5,8])
    def test_15_pad_labels(self):
        try:import torch
        except ImportError:self.skipTest('torch not installed')
        batch=collate_rows([mask_completion([1],[2],9,5),mask_completion([1,2],[3],9,5)],9)
        self.assertEqual(batch['labels'][0,-1].item(),-100);self.assertEqual(batch['labels'][0,-2].item(),9)
    def _fresh_review_state(self):
        r=copy.deepcopy(read_csv(ROOT/'data/review_decisions.csv'))
        sr=copy.deepcopy(read_csv(ROOT/'data/source_review.csv'))

        for x in r:
            x.update(
                decision='PENDING',
                reviewer='',
                reviewed_at='',
                notes=''
            )

        for x in sr:
            x.update(
                permission_review='PENDING',
                reviewer='',
                reviewed_at='',
                notes=''
            )

        return r,sr

    def test_16_pending_exports_none(self):
        r,sr=self._fresh_review_state()
        self.assertEqual(select_approved(self.cs,r,sr,self.ss),[])

    def test_17_incomplete_pair(self):
        r,sr=self._fresh_review_state()
        r[0].update(
            decision='APPROVED',
            reviewer='test',
            reviewed_at='2026'
        )
        with self.assertRaises(ValueError):
            select_approved(self.cs,r,sr,self.ss)

    def test_18_complete_pair_export(self):
        r,sr=self._fresh_review_state()
        ids={
            x['case_id']
            for x in self.cs
            if x['pair_id']==self.cs[0]['pair_id']
        }

        for x in r:
            if x['case_id'] in ids:
                x.update(
                    decision='APPROVED',
                    reviewer='test',
                    reviewed_at='2026'
                )

        for x in sr:
            x.update(
                permission_review='REVIEWED_OK',
                reviewer='test',
                reviewed_at='2026'
            )

        self.assertEqual(
            len(select_approved(self.cs,r,sr,self.ss)),
            2
        )
    def test_19_orderless_refs(self):
        e=self.cs[0]['expected'];a=copy.deepcopy(e);a['evidence_refs'].reverse();self.assertTrue(answer_matches(e,a))
    def test_20_missing_ref_fails(self):
        e=self.cs[0]['expected'];a=copy.deepcopy(e);a['evidence_refs']=[];self.assertFalse(answer_matches(e,a))
    def test_21_pair_action_flip(self):
        from collections import defaultdict
        ps=defaultdict(list)
        for c in self.cs:ps[c['pair_id']].append(c)
        self.assertEqual(len(ps),20)
        for pp in ps.values():self.assertEqual(len({c['expected']['action'] for c in pp}),2)
    def test_22_reserved_not_train(self):
        for c in self.cs:self.assertFalse(self.ss[c['source_id']]['proposed_use'].startswith('EVAL'))
    def test_23_prompt_same_training_inference(self):
        c=self.cs[0];with_answer=build_messages(c['role'],c['packet'],c['expected']);without=build_messages(c['role'],c['packet']);self.assertEqual(with_answer[:-1],without)
    def test_24_known_source_limits(self):
        self.assertEqual(self.ss['FL-03']['rights_statement'],'NOT_CONFIRMED');self.assertEqual(self.ss['SW-03']['rights_statement'],'NOT_CONFIRMED')
if __name__=='__main__':unittest.main()
