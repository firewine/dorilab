import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'audit_reason_exposure_v11.py'
spec = importlib.util.spec_from_file_location('audit_reason', SCRIPT)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def row(rid='R1', reason='R_A', parent='P1', kind='physics', system='R_A R_B'):
    ans = {'action':'REQUEST_EVIDENCE'}
    if reason is not None: ans['reason'] = reason
    return {'id':rid, 'v05_metadata':{'kind':kind,'parent_case_id':parent},
            'messages':[{'role':'system','content':system},{'role':'user','content':'data'},
                        {'role':'assistant','content':json.dumps(ans)}]}


def case(cid='C1', gold='R_B', predicted='R_A'):
    expected = {'action':'REQUEST_EVIDENCE','reason':gold}
    arm = {'expected':expected,'parsed':{'action':'REQUEST_EVIDENCE','reason':predicted},
           'strict_contract_pass': gold == predicted}
    return {'case_id':cid,'baseline':copy.deepcopy(arm),'guide':copy.deepcopy(arm)}


class Tests(unittest.TestCase):
    def test_01_row_vs_parent(self):
        r=a.analyze([row('1'),row('2'),row('3')],[case()])
        self.assertEqual(r['reason_codes']['R_A']['supervised_rows'],3)
        self.assertEqual(r['reason_codes']['R_A']['unique_physics_parent_cases'],1)

    def test_02_prompt_not_target(self):
        r=a.analyze([row()],[case()])
        self.assertEqual(r['reason_codes']['R_B']['supervised_rows'],0)
        self.assertEqual(r['reason_codes']['R_B']['rows_with_literal_code_in_system'],1)
        self.assertEqual(r['baseline_failures'][0]['diagnostic_label'],'NO_TARGET_EXAMPLE_FOR_CODE_IN_THIS_EXPORT')

    def test_03_contract_not_physics(self):
        r=a.analyze([row(kind='contract',parent=None)],[case(gold='R_A',predicted='R_A')])
        self.assertEqual(r['physics_rows'],0)
        self.assertEqual(r['reason_codes']['R_A']['supervised_contract_rows'],1)

    def test_04_no_reason(self):
        r=a.analyze([row(reason=None)],[case()])
        self.assertEqual(r['rows_with_supervised_reason'],0)

    def test_05_duplicate_keys(self):
        with self.assertRaises(ValueError): a.strict_json('{"x":1,"x":2}')

    def test_06_nonfinite(self):
        with self.assertRaises(ValueError): a.strict_json('{"x":NaN}')

    def test_07_duplicate_training_id(self):
        with self.assertRaises(ValueError): a.analyze([row(),row()],[case()])

    def test_08_duplicate_eval_id(self):
        with self.assertRaises(ValueError): a.analyze([row()],[case(),case()])

    def test_09_gold_not_equal(self):
        c=case(); c['guide']['expected']['reason']='R_C'
        with self.assertRaises(ValueError): a.analyze([row()],[c])

    def test_10_reject_ambiguous_supervision(self):
        r=row();r['messages'].insert(2,{'role':'assistant','content':'{}'})
        with self.assertRaises(ValueError): a.analyze([r],[case()])

    def test_11_run_and_non_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); data=root/'train.jsonl';run=root/'run.json'; ev=root/'eval.jsonl'
            data.write_text(json.dumps(row())+'\n')
            dm={'data_sha256':a.file_sha(data),'records':1}
            data.with_suffix('.manifest.json').write_text(json.dumps(dm))
            run.write_text(json.dumps({'data_manifest':dm,'epochs_requested':2}))
            ev.write_text(json.dumps(case())+'\n')
            before={p.name:a.file_sha(p) for p in root.iterdir() if p.is_file()}
            with contextlib.redirect_stdout(io.StringIO()):
                result=a.run(root,'train.jsonl','run.json','eval.jsonl','output')
            self.assertTrue((root/'output/audit.json').is_file())
            self.assertEqual(result['run_epochs_requested'],2)
            for name,h in before.items():self.assertEqual(a.file_sha(root/name),h)
            with self.assertRaises(ValueError):a.run(root,'train.jsonl','run.json','eval.jsonl','output')

    def test_12_mismatching_recorded_training(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'train.jsonl';data.write_text(json.dumps(row())+'\n')
            data.with_suffix('.manifest.json').write_text(json.dumps({'data_sha256':a.file_sha(data),'records':1}))
            (root/'run.json').write_text(json.dumps({'data_manifest':{'data_sha256':'bad'}}))
            (root/'eval.jsonl').write_text(json.dumps(case())+'\n')
            with self.assertRaises(ValueError):a.run(root,'train.jsonl','run.json','eval.jsonl','output')
            self.assertFalse((root/'output').exists())

    def test_13_name_boundary(self):
        r=a.analyze([row(system='R_B_EXTRA')],[case()])
        self.assertEqual(r['reason_codes']['R_B']['rows_with_literal_code_in_system'],0)

    def test_14_request_does_not_mean_reason_learned(self):
        r=row();ans={'action':'REQUEST_EVIDENCE','reason':'R_A','requested_evidence':['R_B']}
        r['messages'][-1]['content']=json.dumps(ans)
        out=a.analyze([r],[case()]);self.assertEqual(out['reason_codes']['R_B']['supervised_rows'],0)


if __name__=='__main__':unittest.main(verbosity=2)
