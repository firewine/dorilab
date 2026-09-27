import copy,json,tempfile,unittest
from pathlib import Path
from dfactory.core import Store,load_jsonl,validate_case,public_case,model_input,readability_gaps
from dfactory.discovery import normalize
ROOT=Path(__file__).resolve().parents[1]

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name))
        self.rows=load_jsonl(ROOT/'examples/j7_review_demo.jsonl')
        self.store.add_many(self.rows,'demo','sha')
    def tearDown(self):self.temp.cleanup()
    def body(self,id='UI-J7-A'):
        return {'request_id':'r1','content_hash':self.store.get(id)['content_hash'],'reviewer':'tester',
                'verdict':'SUPPORTED','decision':'DEFER','notes':'샘플 근거 검토 중','source_checked':False,'reference_seen':False}
    def test_demo_valid(self):
        self.assertEqual([],validate_case(self.rows[0]))
    def test_import_idempotent(self):
        self.assertEqual(0,self.store.add_many(self.rows,'demo','sha'))
    def test_changed_source_not_overwritten(self):
        cs=copy.deepcopy(self.rows);cs[0]['proposal']='다른 제안'
        with self.assertRaises(ValueError):self.store.add_many(cs,'demo2','sha2')
        self.assertEqual(self.rows[0]['proposal'],self.store.get('UI-J7-A')['proposal'])
    def test_unknown_reference_blocked(self):
        cs=copy.deepcopy(self.rows[0]);cs['reference_draft']['expected']['evidence_refs']=['BAD']
        self.assertIn('unavailable:reference_evidence',validate_case(cs))
    def test_public_hides_gold(self):
        pub=public_case(self.store.get('UI-J7-A'))
        self.assertNotIn('reference_draft',pub);self.assertNotIn('legacy_record',pub)
    def test_model_input_no_answers(self):
        p=model_input(self.store.get('UI-J7-A'))
        self.assertNotIn('reference_draft',p);self.assertNotIn('model_result',p);self.assertNotIn('pair_id',p);self.assertNotIn('variant',p)
    def test_missing_model_reason_not_filled(self):
        self.assertIsNone(self.store.get('UI-J7-A')['model_result']['rationale'])
    def test_review_save(self):
        self.assertTrue(self.store.record('UI-J7-A','REVIEW',self.body())['saved'])
        self.assertEqual(len(self.store.reviews()),1)
    def test_review_retry(self):
        b=self.body();self.store.record('UI-J7-A','REVIEW',b)
        self.assertTrue(self.store.record('UI-J7-A','REVIEW',b)['duplicate'])
        self.assertEqual(len(self.store.reviews()),1)
    def test_request_id_conflict(self):
        b=self.body();self.store.record('UI-J7-A','REVIEW',b);b['notes']='changed'
        with self.assertRaises(ValueError):self.store.record('UI-J7-A','REVIEW',b)
    def test_stale_review(self):
        b=self.body();b['content_hash']='old'
        with self.assertRaises(ValueError):self.store.record('UI-J7-A','REVIEW',b)
    def test_actor_required(self):
        b=self.body();b['reviewer']=''
        with self.assertRaises(ValueError):self.store.record('UI-J7-A','REVIEW',b)
    def test_reason_required(self):
        b=self.body();b['notes']=''
        with self.assertRaises(ValueError):self.store.record('UI-J7-A','REVIEW',b)
    def test_demo_no_approve(self):
        b=self.body();b.update(decision='ACCEPT_DRAFT',reference_seen=True,source_checked=True)
        with self.assertRaises(ValueError):self.store.record('UI-J7-A','REVIEW',b)
    def test_source_check_required(self):
        c=copy.deepcopy(self.rows[0]);c['case_id']='real1';c['demo_only']=False
        self.store.add_many([c],'real1','shar')
        b=self.body('real1');b.update(decision='ACCEPT_DRAFT',reference_seen=True)
        with self.assertRaises(ValueError):self.store.record('real1','REVIEW',b)
    def test_readability(self):
        self.assertEqual([],readability_gaps(self.rows[0]))
        c=copy.deepcopy(self.rows[0]);c['reference_draft']['verdict']=None
        self.assertIn('verdict',readability_gaps(c))
    def test_crossref_rights_pending(self):
        n=normalize({'DOI':'10.1/ABC','title':['Test'],'license':[{'URL':'x'}]},'THERMAL','q')
        self.assertEqual(n['rights_decision'],'PENDING');self.assertEqual(n['doi'],'10.1/abc')
    def test_labels_separate_record(self):
        self.store.record('UI-J7-A','REVIEW',self.body())
        self.assertEqual(self.store.get('UI-J7-A')['reference_draft']['review_status'],'DEMO_NOT_APPROVED')

if __name__=='__main__':unittest.main()
