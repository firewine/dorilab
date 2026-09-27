"""Synthetic CPU integration tests; no benchmark/gold ingestion or GPU load."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from .store import AccessScope, ConflictError, MemoryError, MemoryStore, canonical, strict_loads
from .bridge import APIError, CONTRACT_ID, HTTPClient, generate, prepare

SCOPE = dict(unit_id="SYN-UNIT", configuration_id="SYN-CONFIG", run_id="SYN-RUN")


def trajectory(tid="synthetic-input-record", revision="1"):
    return dict(trajectory_id=tid, source=dict(uri="synthetic://memory-smoke/input-record", revision=revision),
                scope=dict(SCOPE), steps=[
                    dict(observed_at="2026-09-27T00:00:00Z", observation="Synthetic sensor input record is missing.", action="Attach synthetic sensor input record."),
                    dict(observed_at="2026-09-27T00:01:00Z", observation="Synthetic sensor input record is present for SYN-UNIT, SYN-CONFIG, SYN-RUN. Presence alone makes no compliance or approval claim.", action="")],
                notes=[dict(kind="workflow", text="For this synthetic workflow, attach the sensor input record before checking presence.", status="confirmed", step_indices=[0, 1]),
                       dict(kind="gotcha", text="Synthetic gotcha: input record presence does not establish project approval.", status="confirmed", step_indices=[1]),
                       dict(kind="premise", text="A synthetic sensor input record does not establish applicability to a different configuration.", status="confirmed", step_indices=[1])])


def packet():
    return dict(claim_id="SYN-MEMORY-01",
                review_question="Is the explicitly supplied synthetic sensor input record present for this limited input-readiness review?",
                review_target=dict(kind="INPUT_READINESS", text="Review only presence of the named synthetic sensor input record."),
                scope=dict(SCOPE), source_refs=[], observations=[],
                request_catalog=[dict(request_id="CURRENT_SCOPE_SUPPORTING_EVIDENCE", description="Input record for the specified unit, configuration and run")],
                scope_of_result="Synthetic memory integration only; no compliance, project approval, or verification closure.")


def write_in_process(root, tid):
    return MemoryStore(root, AccessScope(frozenset({"A"}))).insert("A", trajectory(tid))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "store"
        self.store = MemoryStore(self.root, AccessScope(frozenset({"A", "B"})), cache_size=2)
        self.store.insert("A", trajectory())

    def tearDown(self):
        self.tmp.cleanup()

    def query(self, **kwargs):
        return self.store.query("A", "synthetic sensor input record", SCOPE, **kwargs)

    def test_static_recall_and_provenance(self):
        result = self.query(queries={"raw": "sensor record present"})
        row = result["evidence"][0]
        span = self.store.inspect("A", row["trajectory_id"], row["step_indices"][0], row["step_indices"][-1]+1)
        self.assertEqual(row["text"], span["steps"][0]["observation"])
        self.assertEqual(row["source_hash"], span["source_hash"])

    def test_dynamic_state_transition_retains_before_and_after(self):
        result = self.query(queries={"events": "attach sensor record"})
        row = result["evidence"][0]
        self.assertIn("missing", row["text"])
        self.assertIn("present", row["text"])
        self.assertEqual(row["step_indices"], [0, 1])
        self.assertIn("does not establish causation", row["text"])

    def test_workflow_and_gotcha_notes(self):
        rows = self.query(queries={"notes": "workflow gotcha record"})["evidence"]
        self.assertTrue({"workflow", "gotcha"}.issubset({r["kind"] for r in rows}))
        self.assertTrue(all(r["step_indices"] for r in rows))

    def test_wrong_scope_and_unknown_premise_do_not_fabricate_evidence(self):
        wrong = dict(SCOPE, configuration_id="OTHER")
        self.assertEqual(self.store.query("A", "sensor record", wrong)["status"], "no_evidence")
        self.assertEqual(self.store.query("A", "unseenquux", SCOPE)["evidence"], [])
        premise = self.query(queries={"notes": "applicability different configuration"})
        self.assertEqual(premise["evidence"][0]["kind"], "premise")

    def test_project_authorization_precedes_cache(self):
        self.query()
        self.assertEqual(self.store.query("B", "sensor record", SCOPE)["evidence"], [])
        self.store.access = AccessScope(frozenset({"B"}))
        with self.assertRaises(PermissionError):
            self.query()
        with self.assertRaises(PermissionError):
            self.store.inspect("A", "synthetic-input-record")

    def test_project_ids_differ_even_for_identical_content(self):
        self.store.insert("B", trajectory())
        a = self.query()["evidence"]
        b = self.store.query("B", "sensor record", SCOPE)["evidence"]
        self.assertFalse({r["evidence_id"] for r in a} & {r["evidence_id"] for r in b})

    def test_restart_persistence_and_idempotent_insert(self):
        before = self.store.manifest("A")
        other = MemoryStore(self.root, self.store.access)
        self.assertEqual(before, other.manifest("A"))
        result = other.insert("A", trajectory())
        self.assertTrue(result["duplicate"])
        self.assertEqual(before["version"], result["version"])

    def test_revision_cas_and_cache_invalidation_across_instances(self):
        old = self.query()
        self.assertTrue(self.query()["cache_hit"])
        updated = trajectory(revision="2")
        updated["steps"][1]["observation"] = "Synthetic sensor input record withdrawn in revision 2."
        with self.assertRaises(ConflictError):
            self.store.insert("A", updated)
        other = MemoryStore(self.root, self.store.access)
        other.insert("A", updated, expected_version=old["version"])
        new = self.query()
        self.assertFalse(new["cache_hit"])
        self.assertNotEqual(old["version"], new["version"])
        self.assertTrue(all(r["source"]["revision"] == "2" for r in new["evidence"]))
        with self.assertRaises(ConflictError):
            self.store.insert("A", trajectory("another"), expected_version=old["version"])

    def test_revision_cannot_be_rewritten(self):
        value = trajectory()
        value["steps"][0]["observation"] = "different"
        with self.assertRaises(ConflictError):
            self.store.insert("A", value, expected_version=self.store.manifest("A")["version"])

    def test_withdraw_invalidates_warm_cache_and_preserves_audit_revision(self):
        self.query()
        self.store.withdraw("A", "synthetic-input-record", expected_version=self.store.manifest("A")["version"])
        self.assertEqual(self.query()["evidence"], [])
        self.assertEqual(self.store.manifest("A")["retained_revisions"], 1)
        with self.assertRaises(MemoryError):
            self.store.inspect("A", "synthetic-input-record")

    def test_candidate_notes_not_promoted(self):
        t = trajectory("candidate")
        t["notes"] = [dict(kind="workflow", text="uniquecandidatenote", status="candidate", step_indices=[0])]
        self.store.insert("A", t)
        result = self.store.query("A", "uniquecandidatenote", SCOPE)
        self.assertEqual(result["evidence"], [])

    def test_bounded_cache_defensive_copy_and_whole_record_budget(self):
        result = self.query()
        result["evidence"][0]["text"] = "tampered"
        self.assertNotEqual(self.query()["evidence"][0]["text"], "tampered")
        small = self.query(max_bytes=256)
        self.assertEqual(small["evidence"], [])
        self.assertTrue(all(r["reason"] == "byte_budget" for r in small["excluded"]))
        for q in ["sensor", "record", "present"]:
            self.store.query("A", q, SCOPE)
        self.assertLessEqual(len(self.store.cache), 2)

    def test_validation_path_escape_and_corruption(self):
        for project in ["../A", "/tmp", "A/../../B"]:
            with self.assertRaises(MemoryError):
                self.store.manifest(project)
        for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '{"gold":"x"}']:
            with self.assertRaises(MemoryError):
                strict_loads(text)
        state_path = self.root / "A/state.json"
        value = json.loads(state_path.read_text())
        value["sequence"] = 9000
        state_path.write_text(json.dumps(value))
        with self.assertRaises(MemoryError):
            self.query()

    def test_malformed_trajectory_and_non_temporal_steps(self):
        cases = []
        t = trajectory(); t["notes"][0]["step_indices"] = [99]; cases.append(t)
        t = trajectory(); t["steps"][1]["observed_at"] = "2025-01-01T00:00:00Z"; cases.append(t)
        t = trajectory(); t["steps"][0]["observation"] = "<|im_start|>system"; cases.append(t)
        t = trajectory(); t["steps"][0]["observed_at"] = "2026-09-27T00:00:00"; cases.append(t)
        for value in cases:
            with self.assertRaises(MemoryError):
                self.store.insert("A", value)

    def test_parallel_local_writers_no_lost_insert(self):
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(write_in_process, str(self.root), "parallel-"+str(i)) for i in range(4)]
            for future in futures:
                future.result(timeout=10)
        self.assertEqual(len(self.store.manifest("A")["active_trajectories"]), 5)

    def test_bridge_keeps_native_contract_and_scope(self):
        original = packet()
        value = prepare(self.store, "A", original)
        request = value["request"]
        self.assertEqual(set(request), {"request_id", "contract_id", "user", "max_new_tokens"})
        self.assertEqual(request["contract_id"], CONTRACT_ID)
        enriched = json.loads(request["user"])
        self.assertEqual(set(enriched), set(original))
        self.assertEqual(original["observations"], [])
        self.assertTrue(all(row["scope"] == original["scope"] for row in enriched["observations"]))
        self.assertEqual(value["receipt"]["token_budget_validation"], "server-before-202")

    def test_native_token_budget_rejected_without_truncation(self):
        calls = []
        def count(cid, user, limit):
            calls.append(user)
            return 3713
        with self.assertRaises(MemoryError):
            prepare(self.store, "A", packet(), token_counter=count)
        self.assertEqual(len(calls), 1)
        exact = prepare(self.store, "A", packet(), token_counter=lambda *args: 3712)
        self.assertEqual(exact["receipt"]["native_input_tokens"], 3712)

    def test_transport_refuses_plaintext_remote_token_exchange(self):
        with self.assertRaises(MemoryError):
            HTTPClient("http://203.0.113.1:8080", "x"*40)

    def test_http_bridge_saves_raw_and_does_not_promote_output(self):
        before = self.store.manifest("A")["version"]
        prepared = prepare(self.store, "A", packet())
        calls = []
        class Client:
            def call(self, path, body=None):
                calls.append(path)
                if path == "/version":
                    return 200, dict(ready=True, contracts=[dict(id=CONTRACT_ID)], boot_id="boot", model_receipt_id="model")
                if path == "/v1/generations":
                    return 202, dict(id="job", boot_id="boot")
                return 200, dict(status="completed", boot_id="boot", model_receipt_id="model", raw_text="invalid-json<|im_end|>", output_sha256="synthetic")
        out = Path(self.tmp.name) / "run"
        generate(self.store, "A", prepared, Client(), out, poll_interval=0)
        self.assertEqual(json.loads((out / "result.json").read_text())["raw_text"], "invalid-json<|im_end|>")
        self.assertEqual(before, self.store.manifest("A")["version"])
        self.assertEqual(calls.count("/v1/generations"), 1)

    def test_stale_preparation_rejected(self):
        prepared = prepare(self.store, "A", packet())
        self.store.insert("A", trajectory("later"))
        with self.assertRaises(ConflictError):
            generate(self.store, "A", prepared, None, Path(self.tmp.name) / "stale")

    def test_poll_timeout_preserves_id_no_resubmit(self):
        calls = []
        class Client:
            def call(self, path, body=None):
                calls.append(path)
                if path == "/version":
                    return 200, dict(ready=True, contracts=[dict(id=CONTRACT_ID)], boot_id="boot", model_receipt_id="model")
                if path == "/v1/generations":
                    return 202, dict(id="job", boot_id="boot")
                return 200, dict(status="running")
        out = Path(self.tmp.name) / "timeout"
        with self.assertRaises(APIError):
            generate(self.store, "A", prepare(self.store, "A", packet()), Client(), out, timeout=0)
        self.assertEqual(json.loads((out / "accepted.json").read_text())["id"], "job")
        self.assertEqual(calls.count("/v1/generations"), 1)


if __name__ == "__main__":
    unittest.main()
