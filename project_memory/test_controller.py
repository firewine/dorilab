"""Synthetic controller and actual PEFT CPU state-transition regressions."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from .store import AccessScope, ConflictError, MemoryStore, canonical
from .bridge import prepare
from .controller import PlanError, QwenPlanner, RulePlanner, SearchController, validate_plan
from .planner_contract import CONTRACT_ID
from .test_memory import trajectory, packet, SCOPE


class ScriptedPlanner:
    name = "scripted-test"
    def __init__(self, fn): self.fn = fn; self.seen = []
    def __call__(self, context, timeout):
        self.seen.append(context)
        return self.fn(context, len(self.seen))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name)/"store", AccessScope(frozenset({"A", "B"})))
        self.store.insert("A", trajectory())
    def tearDown(self): self.tmp.cleanup()
    def gather(self, planner=None, **options):
        return SearchController(planner, **options).gather(self.store, "A", "sensor record present", SCOPE, top_k=3, max_bytes=6500)

    def test_inspect_then_finish_verified(self):
        def fn(c, n):
            ids = [c["candidates"][0]["evidence_id"]]
            return canonical(dict(action="inspect", evidence_ids=ids) if n == 1 else
                             dict(action="finish", evidence_ids=ids, assessment="sufficient", missing=[]))
        planner = ScriptedPlanner(fn)
        result = self.gather(planner)
        self.assertFalse(result["controller"]["fallback"])
        self.assertEqual(result["controller"]["assessment"], "sufficient")
        self.assertEqual(len(result["evidence"]), 1)
        self.assertTrue(planner.seen[1]["inspected"])

    def test_adaptive_search_then_source_inspection(self):
        def fn(c, n):
            if n == 1:
                return canonical(dict(action="search", queries={"notes":"different configuration applicability"}))
            rows = [r for r in c["candidates"] if r.get("kind") == "premise"]
            return canonical(dict(action="inspect", evidence_ids=[rows[0]["evidence_id"]]) if n == 2 else
                             dict(action="finish", evidence_ids=[rows[0]["evidence_id"]], assessment="conflict", missing=["Configuration applicability is not established."]))
        result = self.gather(ScriptedPlanner(fn))
        self.assertEqual(result["controller"]["searches"], 2)
        self.assertEqual(result["evidence"][0]["kind"], "premise")
        self.assertEqual(result["controller"]["assessment"], "conflict")

    def test_malformed_invented_and_privilege_escalation_plans_fallback(self):
        for raw in ['not JSON', '{"action":"finish","action":"search"}', '{"action":[]}',
                    '{"action":"finish","evidence_ids":[],"assessment":[],"missing":[]}',
                    canonical(dict(action="search", queries={"raw":"x"}, project_id="B")),
                    canonical(dict(action="finish", evidence_ids=["invented"], assessment="sufficient", missing=[]))]:
            result = self.gather(ScriptedPlanner(lambda c,n: raw))
            self.assertTrue(result["controller"]["fallback"])
            self.assertTrue(all(r["project_id"] == "A" for r in result["evidence"]))

    def test_scope_never_comes_from_model_and_other_scope_not_sent(self):
        wrong = trajectory("private")
        wrong["scope"]["run_id"] = "OTHER"
        wrong["steps"][0]["observation"] = "other-scope-private"
        self.store.insert("A", wrong)
        self.store.insert("B", trajectory("other-project-private"))
        planner = ScriptedPlanner(lambda c,n: canonical(dict(action="search", queries={"raw":"other-scope-private"}, scope=wrong["scope"])))
        result = self.gather(planner)
        self.assertNotIn("other-scope-private", canonical(planner.seen))
        self.assertTrue(result["controller"]["fallback"])

    def test_repeat_and_search_limit(self):
        repeated = ScriptedPlanner(lambda c,n: canonical(dict(action="search", queries={"raw":"sensor record present","events":"sensor record present","notes":"sensor record present"})))
        self.assertEqual(self.gather(repeated)["controller"]["stop_reason"], "repeated_query")
        planner = ScriptedPlanner(lambda c,n: canonical(dict(action="search", queries={"raw":"sensor "+str(n)})))
        result = self.gather(planner)
        self.assertEqual(result["controller"]["searches"], 3)
        self.assertEqual(result["controller"]["stop_reason"], "search_limit")

    def test_timeout_and_backend_failure_fallback(self):
        def failure(c,n): raise TimeoutError("synthetic")
        self.assertTrue(self.gather(ScriptedPlanner(failure))["controller"]["fallback"])
        ticks = iter([0, 0, 0, 0, 5, 5, 5])
        with patch('project_memory.controller.time.monotonic', side_effect=lambda: next(ticks, 5)):
            result = self.gather(ScriptedPlanner(lambda c,n: '{}'), timeout=1)
        self.assertTrue(result["controller"]["fallback"])

    def test_memory_change_during_plan_fails_closed(self):
        def change(c,n):
            self.store.insert("A", trajectory("new"))
            return canonical(dict(action="finish", evidence_ids=[], assessment="insufficient", missing=["none"]))
        with self.assertRaises(ConflictError): self.gather(ScriptedPlanner(change))

    def test_rules_and_empty_memory_do_not_claim_sufficiency(self):
        result = self.gather()
        self.assertEqual(result["controller"]["assessment"], "insufficient")
        self.assertTrue(result["controller"]["inspected"])
        empty = SearchController().gather(self.store,"B","sensor",SCOPE)
        self.assertEqual(empty["status"],"no_evidence")

    def test_skipped_inspection_downgrades_sufficient(self):
        planner=ScriptedPlanner(lambda c,n: canonical(dict(action="finish", evidence_ids=[c['candidates'][0]['evidence_id']], assessment="sufficient", missing=[])))
        result=self.gather(planner)
        self.assertEqual(result['controller']['assessment'],'insufficient')
        self.assertTrue(result['controller']['inspected'])

    def test_bridge_excludes_control_instructions_from_rc3_input(self):
        result=prepare(self.store,'A',packet(),controller=SearchController(),top_k=3,max_bytes=6500)
        self.assertIn('controller',result['memory'])
        self.assertNotIn('remaining_searches',result['request']['user'])
        self.assertNotIn('controller',json.loads(result['request']['user']))

    def test_qwen_transport_pinned_mode_and_raw_receipts(self):
        class Client:
            def call(self,path,body=None,**kwargs):
                if path=='/version': return 200,dict(ready=True,contracts=[dict(id=CONTRACT_ID)],boot_id='boot',model_receipt_id='release')
                if path=='/v1/generations':
                    assert body['contract_id']==CONTRACT_ID
                    return 202,dict(id='job',boot_id='boot')
                return 200,dict(status='completed',boot_id='boot',model_receipt_id='release',execution_mode='memory_planner',adapter_applied=False,text='invalid-json',raw_text='invalid-json<|im_end|>')
        directory=Path(self.tmp.name)/'planner'
        planner=QwenPlanner(Client(),directory)
        self.assertEqual(planner({},10),'invalid-json')
        self.assertEqual(json.loads((directory/'1/result.json').read_text())['raw_text'],'invalid-json<|im_end|>')

    def test_peft_restores_real_adapter_on_success_and_exception(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'inference'))
        from model_runtime import ModelRuntime
        import torch
        from peft import LoraConfig, get_peft_model
        class Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.linear=torch.nn.Linear(4,4); self.disabled_seen=[]; self.fail=False
            def forward(self,x): return self.linear(x)
            def generate(self, input_ids, **kwargs):
                self.disabled_seen.append(self.linear.disable_adapters)
                if self.fail: raise RuntimeError('synthetic generation error')
                return torch.cat((input_ids,torch.tensor([[248046]])),dim=1)
        base=Tiny()
        model=get_peft_model(base,LoraConfig(r=2,target_modules=['linear']))
        class Tok:
            def decode(self,ids,**kwargs): return str(ids)
        class Proc: tokenizer=Tok()
        runtime=ModelRuntime('cpu',Path(self.tmp.name)); runtime.model=model; runtime.proc=Proc(); runtime.receipt_id='cpu'
        runtime.generation=dict(do_sample=False,use_cache=True,pad_token_id=0,eos_token_id=248046)
        prepared=dict(ids=[1,2],input_sha256='x',prompt_token_ids_sha256='x',rendered_sha256='x',execution_mode='memory_planner')
        real=torch.tensor
        def cpu(*args,**kwargs): kwargs['device']='cpu'; return real(*args,**kwargs)
        with patch.object(torch,'tensor',side_effect=cpu):
            result=runtime.generate(prepared,2)
            self.assertFalse(result['adapter_applied'])
            self.assertTrue(model.get_model_status().enabled)
            runtime.generate(dict(prepared,execution_mode='rc3'),2)
            self.assertEqual(base.disabled_seen,[True,False])
            base.fail=True
            with self.assertRaises(RuntimeError): runtime.generate(prepared,2)
            self.assertTrue(model.get_model_status().enabled)


if __name__=='__main__': unittest.main()
