import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compare_results import aggregate,transitions,index
class ComparisonTests(unittest.TestCase):
 def item(self):return dict(json_valid=True,schema_valid=False,parsed_action_correct=True,schema_qualified_action_correct=False,reference_exact=None,strict_pass=False,contract_violations=['reason_code'],generation_seconds=1.5,hit_generation_limit=False)
 def test_01_action_counts_and_reference_null_are_separate(self):
  r=aggregate([self.item()]);self.assertEqual(r['parsed_action_correct'],1);self.assertEqual(r['schema_qualified_action_correct'],0)
  self.assertEqual(r['reference_exact'],{'true':0,'false':0,'not_evaluated':1})
 def test_02_improvements_and_regressions(self):
  old=self.item();new={**old,'schema_valid':True,'strict_pass':True,'reference_exact':True,'contract_violations':[]}
  r=transitions(old,new);self.assertEqual(r['strict_pass']['transition'],'improved')
  self.assertEqual(r['reference_exact']['transition'],'evaluation_availability_changed')
  self.assertEqual(transitions(new,old)['strict_pass']['transition'],'regressed')
 def test_03_duplicate_cases_rejected(self):
  with self.assertRaises(ValueError):index([{'case_id':'x'},{'case_id':'x'}])
if __name__=='__main__':unittest.main()
