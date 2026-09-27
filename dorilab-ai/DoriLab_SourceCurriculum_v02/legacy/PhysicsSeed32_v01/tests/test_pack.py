import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from tools.common import ROOT, action_errors, changed_paths, matches_gold, read_jsonl
from tools.validate_pack import validate
from tools.export_reviewed import select_approved
from tools.fetch_sources import is_expected_file
from runtime.physics_prompts_v01 import build_messages


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read_jsonl(ROOT / "data/physics_cases_seed32_v01.jsonl")
        cls.facts = read_jsonl(ROOT / "data/source_facts_v01.jsonl")
        cls.sft = read_jsonl(ROOT / "data/physics_sft_seed32_candidate_v01.jsonl")
        cls.schema = json.loads((ROOT / "data/action_schema_v01.json").read_text())
        with (ROOT / "data/review_decisions.csv").open(encoding="utf-8-sig", newline="") as f:
            cls.decisions = list(csv.DictReader(f))

    def test_whole_pack_integrity(self):
        self.assertEqual(validate()["errors"], [])

    def test_counts(self):
        self.assertEqual(len(self.cases), 32)
        self.assertEqual(len(self.facts), 16)
        self.assertEqual(len(self.sft), 32)

    def test_every_pair_changes_one_leaf_and_action(self):
        groups = {}
        for c in self.cases:
            groups.setdefault(c["pair_id"], []).append(c)
        self.assertEqual(len(groups), 16)
        for members in groups.values():
            self.assertEqual(len(members), 2)
            a, b = members
            self.assertEqual(len(changed_paths(a["packet"], b["packet"])), 1)
            self.assertNotEqual(a["expected"]["action"], b["expected"]["action"])

    def test_canonical_messages(self):
        by_id = {r["id"]: r for r in self.sft}
        for c in self.cases:
            self.assertEqual(by_id[c["case_id"]]["messages"], build_messages(c["role"], c["packet"], c["expected"]))

    def test_source_refs_present(self):
        for c in self.cases:
            self.assertEqual(action_errors(c["expected"], c["packet"], self.schema), [])

    def test_missing_action_rejected(self):
        c = self.cases[0]
        bad = dict(c["expected"])
        bad.pop("action")
        self.assertTrue(action_errors(bad, c["packet"], self.schema))

    def test_unknown_reference_rejected(self):
        c = self.cases[0]
        bad = copy.deepcopy(c["expected"])
        bad["evidence_refs"].append("INVENTED_SOURCE")
        self.assertTrue(action_errors(bad, c["packet"], self.schema))

    def test_wrong_claim_rejected(self):
        c = self.cases[0]
        bad = dict(c["expected"], claim_id="ANOTHER_CLAIM")
        self.assertTrue(action_errors(bad, c["packet"], self.schema))

    def test_extra_fields_rejected(self):
        c = self.cases[0]
        self.assertTrue(action_errors(dict(c["expected"], approved=True), c["packet"], self.schema))

    def test_citation_order_not_semantic_failure(self):
        c = self.cases[0]
        reordered = copy.deepcopy(c["expected"])
        reordered["evidence_refs"].reverse()
        self.assertTrue(matches_gold(c["expected"], reordered))

    def test_repeated_citation_fails(self):
        c = self.cases[0]
        bad = copy.deepcopy(c["expected"])
        bad["evidence_refs"].append(bad["evidence_refs"][0])
        self.assertFalse(matches_gold(c["expected"], bad))

    def test_pending_reviews_not_exportable(self):
        with self.assertRaises(ValueError):
            select_approved(self.cases, self.decisions)

    def test_partial_pair_not_exportable(self):
        decisions = copy.deepcopy(self.decisions)
        decisions[0].update(decision="APPROVED", reviewer="Test reviewer", reviewed_at="2026-09-13")
        with self.assertRaises(ValueError):
            select_approved(self.cases, decisions)

    def test_approved_pair_exports_two(self):
        decisions = copy.deepcopy(self.decisions)
        pair = decisions[0]["pair_id"]
        for d in decisions:
            if d["pair_id"] == pair:
                d.update(decision="APPROVED", reviewer="Unit-test reviewer", reviewed_at="2026-09-13")
        self.assertEqual(len(select_approved(self.cases, decisions)), 2)

    def test_approval_requires_review_identity(self):
        decisions = copy.deepcopy(self.decisions)
        for d in decisions[:2]:
            d["decision"] = "APPROVED"
        with self.assertRaises(ValueError):
            select_approved(self.cases, decisions)

    def test_html_is_not_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "response.pdf"
            p.write_bytes(b"<html>403 Forbidden</html>")
            self.assertFalse(is_expected_file(p, "pdf"))
            p.write_bytes(b"%PDF-1.7\n% test signature only")
            self.assertTrue(is_expected_file(p, "pdf"))

    def test_no_human_or_raw_experiment_claim(self):
        for c in self.cases:
            self.assertEqual(c["human_review_status"], "PENDING")
            self.assertFalse(c["raw_measurement_available"])
            self.assertEqual(c["basis"], "SYNTHETIC_COUNTERFACTUAL")

if __name__ == "__main__":
    unittest.main()
