import ast,copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from batch_guard import check_budget,check_lock,verify_rows
class BatchGuardTests(unittest.TestCase):
 def test_01_budget_boundary(self):check_budget([1664])
 def test_02_over_budget_stops(self):
  with self.assertRaisesRegex(ValueError,'NO_TRUNCATION'):check_budget([1665])
 def test_03_locked_conditions(self):
  lock=json.loads((ROOT/'EXPERIMENT_LOCK.json').read_text());check_lock(lock)
  for key,value in [('max_new_tokens',385),('revision','main'),('decoder','sample'),('precision','float16'),('transformers_git_commit','main')]:
   changed=copy.deepcopy(lock);changed[key]=value
   with self.assertRaises(ValueError):check_lock(changed)
 def test_04_message_hash_rejects_mutation(self):
  rows=[json.loads(x) for x in (ROOT/'inputs/dev8_direct_v14.jsonl').read_text().splitlines()];verify_rows(rows)
  rows[0]['messages'][0]['content']+='mutation'
  with self.assertRaisesRegex(ValueError,'hash'):verify_rows(rows)
 def test_05_runner_preflight_precedes_model_load(self):
  text=(ROOT/'scripts/run_direct_v14.py').read_text();ast.parse(text)
  self.assertLess(text.index('check_budget([len(ids)'),text.index('model=AutoModelForMultimodalLM.from_pretrained'))
  self.assertLess(text.index('if args.preflight_only:'),text.index('from transformers import AutoModelForMultimodalLM'))
  self.assertIn('truncation=False',text);self.assertIn('do_sample=False',text)
  self.assertNotIn('gold_candidate.jsonl',text);self.assertNotIn('load_split',text)
if __name__=='__main__':unittest.main()
