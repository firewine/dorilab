"""CPU fixtures only: the training gate below mirrors the user's pasted checks.
No real model/Transformers installation or GPU is used.
"""
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ASSETS = Path(__file__).resolve().parents[1]
SUPPORT = ASSETS / 'test_support'
sys.path.insert(0, str(SUPPORT))
sys.path.insert(0, str(ASSETS))
import evidence_training_v05 as original
import repair_evidence_training_v05_manifest as repair
spec = importlib.util.spec_from_file_location('previous_cpu_fixture', Path(__file__).with_name('fixture_original_wrapper.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.ROOT = SUPPORT

# Kept intentionally close to the three exact checks shown by the user.
# Anything after GATE PASS in the real trainer (tokenizer/model/backprop) is NOT tested.
TRAINER_GATE = '''from pathlib import Path
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-length');p.add_argument('--epochs');p.add_argument('--lr');p.add_argument('--rank')
    p.add_argument('--model');p.add_argument('--revision');a=p.parse_args()
    if a.out.exists():raise SystemExit('Output exists. Use a new run directory; no overwrite or implicit resume.')
    mf=a.data.with_suffix('.manifest.json')
    if not mf.exists():raise SystemExit('Run dcurr.prepare first; data manifest missing')
    manifest=json.loads(mf.read_text())
    if manifest['data_sha256']!=sha256(a.data):raise SystemExit('Training data hash changed')
    if manifest['prompt_file_sha256']!=sha256(ROOT/'dcurr/prompts.py') or manifest['legacy_prompt_sha256']!=sha256(ROOT/'dcurr/prompts_legacy.py'):raise SystemExit('Prompt changed since build. Rebuild with a new version.')
    print('CPU TRAINER GATE: PASS; model/GPU stage intentionally not executed')
if __name__=='__main__':main()
'''


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


class ManifestRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = fixture.make_project(self.tmp.name)
        shutil.copy(SUPPORT/'evidence_training_v05.py', self.root/'evidence_training_v05.py')
        (self.root/'dcurr/train.py').write_text(TRAINER_GATE)
        (self.root/'transformers.py').write_text('def set_seed(seed):\n    pass  # CPU fixture only\n')
        rw = repair.load_wrapper(self.root)
        self.parent_data = self.root/rw.TRAIN
        self.parent_path = self.parent_data.with_suffix('.manifest.json')
        selected = rw.recover_selected(rw.read_jsonl(self.parent_data), rw.read_jsonl(self.root.parent/'data/train150_v01.jsonl'), rw.read_jsonl(self.root/rw.CASES))
        parent = {
            'build':'curriculum-v0.2', 'records':170,'contract_records':150,'physics_records':20,'pairs':10,
            'data_sha256':repair.sha256(self.parent_data),
            'prompt_file_sha256':repair.sha256(self.root/'dcurr/prompts.py'),
            'legacy_prompt_sha256':repair.sha256(self.root/'dcurr/prompts_legacy.py'),
            'review_csv_sha256':repair.sha256(self.root/'data/review_decisions.csv'),
            'source_review_sha256':repair.sha256(self.root/'data/source_review.csv'),
            'contract_file_sha256':repair.sha256(self.root.parent/'data/train150_v01.jsonl'),
            'source_ids':sorted({x['case']['source_id'] for x in selected.values()}),
            'program_groups':sorted({g for x in selected.values() for g in x['case']['source_program_groups']}),
            'system_prompt_hashes':repair.system_hashes(rw.read_jsonl(self.parent_data)),
        }
        write(self.parent_path, parent)
        with patch.multiple(rw, TRAIN_SHA=repair.sha256(self.parent_data), CONTRACT_SHA=parent['contract_file_sha256'], CASES_SHA=repair.sha256(self.root/rw.CASES)), redirect_stdout(io.StringIO()):
            rw.build(self.root, Path(repair.DEFAULT_OUTDIR), 14)
            rw.approve(self.root, Path(repair.DEFAULT_OUTDIR), 'CPU_FIXTURE_NOT_ACTUAL_APPROVAL', 'Temporary synthetic data review only')
        self.target = self.root/repair.DEFAULT_OUTDIR
        self.plan = repair.read_json(self.target/'manifest.json')
        write(self.target/'base_revision.json',{'revision':'a'*40,'model':self.plan['model']})
        write(self.target/'preflight_pair.json',{'arms':{a:{'status':'PASS','records':210,'silent_truncation':False,'data_sha256':self.plan['candidate_sha256'][a],'total_answer_tokens':5086} for a in rw.ARMS}})
        (self.target/'logs').mkdir()
        (self.target/'logs/prior_failure.log').write_text('Run dcurr.prepare first; data manifest missing\n')
        self.wrapper = rw

    def tearDown(self):
        rootstr = str(self.root)
        for key in list(sys.modules):
            if key == 'dcurr' or key.startswith('dcurr.'):
                del sys.modules[key]
        sys.path[:] = [s for s in sys.path if s != rootstr]
        self.tmp.cleanup()

    def go(self, check_only=False):
        with redirect_stdout(io.StringIO()):
            return repair.run(self.root, Path(repair.DEFAULT_OUTDIR), check_only=check_only)

    def sidecar(self, arm='repeat'):
        return (self.root/self.plan['arms'][arm]['training_data']).with_suffix('.manifest.json')

    def no_sidecars(self):
        self.assertFalse(self.sidecar('repeat').exists())
        self.assertFalse(self.sidecar('position').exists())

    def worker(self,arm):
        return subprocess.run([sys.executable,str(self.root/'evidence_training_v05.py'),'_train-worker','--root',str(self.root),'--outdir',repair.DEFAULT_OUTDIR,'--arm',arm],cwd=self.root,text=True,capture_output=True,timeout=15)

    def test_01_missing_manifest_reproduces_reported_error(self):
        result=self.worker('repeat')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Run dcurr.prepare first; data manifest missing',result.stderr+result.stdout)
        self.assertFalse((self.root/self.plan['arms']['repeat']['adapter']).exists())

    def test_02_both_user_gates_pass_after_repair(self):
        self.go()
        for a in self.wrapper.ARMS:
            result=self.worker(a)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('CPU TRAINER GATE: PASS',result.stdout)
            self.assertFalse((self.root/self.plan['arms'][a]['adapter']).exists())

    def test_03_correct_three_required_fields(self):
        self.go()
        for a in self.wrapper.ARMS:
            m=repair.read_json(self.sidecar(a))
            self.assertEqual(m['data_sha256'],repair.sha256(self.root/self.plan['arms'][a]['training_data']))
            self.assertEqual(m['prompt_file_sha256'],repair.sha256(self.root/'dcurr/prompts.py'))
            self.assertEqual(m['legacy_prompt_sha256'],repair.sha256(self.root/'dcurr/prompts_legacy.py'))

    def test_04_counts_do_not_claim_60_independent_cases(self):
        self.go();m=repair.read_json(self.sidecar())
        self.assertEqual((m['records'],m['contract_records'],m['physics_records'],m['unique_physics_cases'],m['pairs']),(210,150,60,20,10))

    def test_05_original_bytes_and_logs_preserved(self):
        before={p:repair.sha256(p) for p in self.root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        self.go()
        for p,h in before.items():self.assertEqual(repair.sha256(p),h,str(p))

    def test_06_original_freeze_gate_still_passes(self):
        self.go()
        self.wrapper.load_plan(self.root,Path(repair.DEFAULT_OUTDIR),True)

    def test_07_rerun_preserves_sidecars_receipt(self):
        self.go();paths=[self.sidecar(a) for a in self.wrapper.ARMS]+[self.target/'manifest_repair_v05_r1.json']
        before={p:repair.sha256(p) for p in paths};self.go()
        self.assertEqual(before,{p:repair.sha256(p) for p in paths})

    def test_08_check_only_writes_nothing(self):
        self.assertEqual(self.go(True)['status'],'CHECK_PASS');self.no_sidecars()
        self.assertFalse((self.target/'manifest_repair_v05_r1.json').exists())

    def test_09_unapproved_stops_without_creating_sidecars(self):
        p=self.target/'approval.json';a=repair.read_json(p);a['decision']='PENDING';write(p,a)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_10_bad_approval_hash_stops(self):
        p=self.target/'approval.json';a=repair.read_json(p);a['manifest_sha256']='0'*64;write(p,a)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_11_released_data_changed_stops(self):
        p=self.root/self.plan['arms']['repeat']['training_data'];p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_12_prompt_changed_stops(self):
        (self.root/'dcurr/prompts.py').write_text('changed')
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_13_trainer_changed_stops(self):
        (self.root/'dcurr/train.py').write_text('changed')
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_14_changed_review_stops(self):
        p=self.root/'data/review_decisions.csv';p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_15_parent_manifest_hash_mismatch_stops(self):
        m=repair.read_json(self.parent_path);m['data_sha256']='0'*64;write(self.parent_path,m)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_16_existing_incompatible_sidecar_not_overwritten(self):
        write(self.sidecar('position'),{'data_sha256':'wrong'})
        h=repair.sha256(self.sidecar('position'))
        with self.assertRaises(ValueError):self.go()
        self.assertEqual(repair.sha256(self.sidecar('position')),h)
        self.assertFalse(self.sidecar().exists())

    def test_17_existing_run_is_not_removed(self):
        p=self.root/self.plan['arms']['repeat']['adapter'];p.mkdir(parents=True)
        with self.assertRaises(ValueError):self.go()
        self.assertTrue(p.exists());self.no_sidecars()

    def test_18_preflight_hash_mismatch_stops(self):
        p=self.target/'preflight_pair.json';a=repair.read_json(p);a['arms']['repeat']['data_sha256']='0'*64;write(p,a)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_19_preflight_target_tokens_mismatch_stops(self):
        p=self.target/'preflight_pair.json';a=repair.read_json(p);a['arms']['repeat']['total_answer_tokens']=1;write(p,a)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_20_wrong_source_metadata_stops(self):
        m=repair.read_json(self.parent_path);m['source_ids']=['MADE_UP'];write(self.parent_path,m)
        with self.assertRaises(ValueError):self.go()
        self.no_sidecars()

    def test_21_sidecars_record_existing_approval_not_new_approval(self):
        self.go();m=repair.read_json(self.sidecar())
        self.assertEqual(m['augmentation_approval_sha256'],repair.sha256(self.target/'approval.json'))
        self.assertEqual(m['parent_data_manifest_sha256'],repair.sha256(self.parent_path))
        self.assertNotIn('reviewer',m)

    def test_22_trainer_rejects_tampered_data_hash_after_repair(self):
        self.go();m=repair.read_json(self.sidecar());m['data_sha256']='0'*64;write(self.sidecar(),m)
        result=self.worker('repeat')
        self.assertNotEqual(result.returncode,0);self.assertIn('Training data hash changed',result.stderr)

    def test_23_trainer_rejects_tampered_prompt_hash_after_repair(self):
        self.go();m=repair.read_json(self.sidecar());m['legacy_prompt_sha256']='0'*64;write(self.sidecar(),m)
        result=self.worker('repeat')
        self.assertNotEqual(result.returncode,0);self.assertIn('Prompt changed since build',result.stderr)

    def test_24_partial_previous_repair_can_finish_without_overwrite(self):
        result=repair.plan_repair(self.root,Path(repair.DEFAULT_OUTDIR))
        item=result['plans']['repeat'];self.wrapper.write_json(item['path'],item['manifest']);h=repair.sha256(item['path'])
        self.go();self.assertEqual(repair.sha256(item['path']),h);self.assertTrue(self.sidecar('position').exists())

    def test_25_duplicate_json_keys_rejected(self):
        p=self.target/'test_duplicate.json';p.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):repair.read_json(p)

    def test_26_protected_plan_approval_hashes_unchanged(self):
        paths=[self.target/'manifest.json',self.target/'approval.json',self.target/'base_revision.json',self.parent_path]
        before={p:repair.sha256(p) for p in paths}
        report=self.go()
        self.assertTrue(report['protected_files_unchanged'])
        self.assertEqual(before,{p:repair.sha256(p) for p in paths})

    def test_27_no_model_library_import_in_repair(self):
        self.go()
        self.assertFalse((self.root/self.plan['arms']['repeat']['adapter']).exists())
        self.assertFalse((self.root/self.plan['arms']['position']['adapter']).exists())
        receipt=repair.read_json(self.target/'manifest_repair_v05_r1.json')
        self.assertFalse(receipt['gpu_training_performed_by_repair'])

if __name__=='__main__':unittest.main()
