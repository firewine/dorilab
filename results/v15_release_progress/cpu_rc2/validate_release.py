"""Read-only checks of source inputs and generated CPU artifacts; writes new logs only."""
import collections
import io
import json
import unittest
from build_release import ROOT, OUT, RC1, V15, PACK, LEGACY, HOLDS, read, rows, sha, digest, write, textfile, status, now

class ReleaseChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=read(OUT/'TRAIN_RELEASE_CANDIDATE_v15.json')
        cls.audit=read(OUT/'LEGACY_V15_MESSAGE_AUDIT.json')

    def test_01_membership_from_parent_and_whole_family_hold(self):
        parent=read(V15/'TRAIN_BUILD_CANDIDATE_v15.json')['members']
        changes={c['case_id']:c for c in rows(V15/'LABEL_CHANGESET_v15.jsonl')}
        expected={m['member_id'] for m in parent if m['component']!='NEW_TRAIN' or changes[m['member_id']]['system_provenance']['authoring_source_principle']['fact_id'] not in HOLDS}
        members=self.manifest['members'];ids=[m['member_id'] for m in members]
        self.assertEqual(set(ids),expected);self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(ids),206)
        self.assertEqual(collections.Counter(m['component'] for m in members),{'CONTRACT_REPLAY':150,'UNIQUE_PHYSICS_STATE':20,'NEW_TRAIN':36})
        held=self.manifest['excluded_family_members']
        self.assertEqual(collections.Counter(m['authoring_fact_family'] for m in held),{f:4 for f in HOLDS})
        self.assertFalse(set(ids)&{m['member_id'] for m in held})
        self.assertTrue(all(m['candidate_repetitions']==1 and m['training_eligible'] is False for m in members))

    def test_02_actual_legacy_messages_and_assistant_content_unchanged(self):
        legacy=rows(LEGACY);n=0
        for e in self.audit['entries']:
            if e['component']=='NEW_TRAIN':continue
            loc=e['source_locator'];r=legacy[loc['source_row_index_0based']]
            self.assertEqual(digest(r),loc['source_row_sha256'])
            self.assertEqual(e['input_messages'],[m for m in r['messages'] if m['role']!='assistant'])
            a=next(m for m in r['messages'] if m['role']=='assistant')
            self.assertEqual(a,e['original_assistant_message']);self.assertEqual(json.loads(a['content']),e['assistant_target'])
            self.assertEqual(digest(e['input_messages']),e['input_messages_sha256']);n+=1
        self.assertEqual(n,170)

    def test_03_train36_targets_bound_to_actual_candidate_labels(self):
        labels={r['case_id']:r for r in rows(RC1/'TRAIN36_LABEL_CANDIDATE.jsonl')}
        for e in self.audit['entries']:
            if e['component']!='NEW_TRAIN':continue
            self.assertIsNone(e['original_assistant_message'])
            self.assertEqual(labels[e['member_id']]['expected'],e['assistant_target'])
            self.assertEqual(digest(e['assistant_target']),e['assistant_target_sha256'])
            self.assertFalse(labels[e['member_id']]['training_eligible'])

    def test_04_blocker_scope_matches_actual_input_conditions(self):
        analysis=[e for e in self.audit['entries'] if '<ROLE>ANALYSIS</ROLE>' in e['input_messages'][1]['content']]
        self.assertEqual(len(analysis),30)
        held=[];warnings=[]
        for e in analysis:
            user=json.loads(e['input_messages'][1]['content'].split('STATE:',1)[1])
            self.assertIn('requirement_s',user);self.assertNotIn('required_s',user)
            self.assertIn('If required_s or actual_by_axis is missing',e['input_messages'][0]['content'])
            if e['assistant_target']['action']=='REQUEST_EVIDENCE':
                self.assertFalse(e['blocker_ids']);warnings.append(e)
            else:self.assertIn('B02_ANALYSIS_FIELD_ALIAS',e['blocker_ids']);held.append(e)
        self.assertEqual(collections.Counter(e['assistant_target']['action'] for e in held),{'CALL_TOOL':10,'NO_ACTION_REQUIRED':10})
        self.assertEqual(len(warnings),10)
        blocked=[e for e in self.audit['entries'] if e['blocker_ids']]
        self.assertEqual(len(blocked),21);self.assertEqual(self.manifest['counts']['no_row_blocker_candidates'],185)
        physics=next(e for e in blocked if e['member_id']=='PHY-EE02-P01-A')
        self.assertEqual(physics['assistant_target']['reason'],'EVIDENCE_INTERPRETATION_ERROR')
        self.assertEqual(self.audit['same_full_input_conflicting_targets'],[])

    def test_05_primary_sources_reacquired_and_anchors_in_new_body(self):
        verification=read(OUT/'sources/PRIMARY_SOURCE_VERIFICATION.json');anchor_count=0
        for s in verification['sources']:
            log=s['reacquisition'];self.assertEqual(log['http_status'],200)
            p=OUT/'sources'/s['source']['pdf'];self.assertEqual(sha(p),log['sha256']);self.assertEqual(p.stat().st_size,log['bytes'])
            self.assertTrue(p.read_bytes().startswith(b'%PDF-'))
            first=(OUT/s['page_artifacts'][0]['path']).read_text();self.assertIn(s['source']['doi'],first)
            for a in s['anchor_checks']:
                p=OUT/'sources'/a['path'].rsplit('/',1)[1]
                self.assertEqual(sha(p),a['page_sha256'])
                norm=' '.join(p.read_text().split());self.assertTrue(norm[a['normalized_character_start']:].startswith(a['normalized_anchor']));anchor_count+=1
        self.assertEqual(len(verification['sources']),2);self.assertEqual(anchor_count,8)
        self.assertFalse(verification['replacement_sources_needed']);self.assertFalse(verification['search_snippets_used'])

    def test_06_dev16_freeze_and_semantic_hold_without_relabel(self):
        freeze=read(OUT/'dev16/PRE_OUTPUT_FREEZE_RC2.json')
        for p,h in freeze['file_sha256'].items():self.assertEqual(sha(OUT/p),h)
        for p in ['INPUTS.jsonl','GOLD_AI_CANDIDATE.jsonl','METADATA.jsonl','MODEL_INPUT_PREVIEWS.jsonl','INPUT_FACTS.json']:
            self.assertEqual(sha(OUT/'dev16'/p),sha(RC1/'dev16'/p))
        labels=rows(OUT/'dev16/GOLD_AI_CANDIDATE.jsonl');metas=rows(OUT/'dev16/METADATA.jsonl')
        self.assertEqual(collections.Counter(r['expected']['action'] for r in labels),{'CHALLENGE':4,'REQUEST_EVIDENCE':4,'NO_ACTION_REQUIRED':8})
        self.assertEqual(sum(r['source_required'] for r in metas),8)
        self.assertTrue(all(r['reference_requirement']['approved'] is False for r in labels))
        b=read(OUT/'dev16/SEMANTIC_REVIEW_RC2.json')['blockers'][0]
        self.assertEqual(next(l for l in labels if l['case_id']==b['case_id'])['expected']['reason'],b['current_reason'])

    def test_07_train_dev_split_from_public_metadata(self):
        train=rows(PACK/'data/train/metadata.jsonl');dev=rows(OUT/'dev16/METADATA.jsonl')
        ts={r['source_id'] for r in train};tp={r['program_group'] for r in train}
        for r in rows(LEGACY):ts.update(r.get('metadata',{}).get('source_ids',[]));tp.update(r.get('metadata',{}).get('program_groups',[]))
        self.assertFalse(ts&{r['source_id'] for r in dev});self.assertFalse(tp&{r['program_group'] for r in dev})
        tids={r['member_id'] for r in self.manifest['members']}
        self.assertFalse(tids&({r['case_id'] for r in dev}|{r['parent_case_id'] for r in dev}))

    def test_08_no_gold_metadata_in_train_or_dev_inputs(self):
        bad={'expected','rationale_ko','acceptable_reason_codes','reference_requirement','sufficient_sets','training_eligible','supporting_fact_ids','supporting_observation_ids'}
        def separated(x):
            if isinstance(x,dict):return not(set(x)&bad) and all(separated(v) for v in x.values())
            if isinstance(x,list):return all(separated(v) for v in x)
            return True
        inputs=[e['input_messages'] for e in self.audit['entries'] if e['component']=='NEW_TRAIN']
        inputs += [r['messages'] for r in rows(OUT/'dev16/MODEL_INPUT_PREVIEWS.jsonl')]
        for messages in inputs:
            self.assertEqual([m['role'] for m in messages],['system','user'])
            self.assertTrue(separated(json.loads(messages[1]['content'])))

    def test_09_reference_contract_positive_and_negative_boundaries(self):
        namespace={};exec(compile((RC1/'reference_contract.py').read_text(),str(RC1/'reference_contract.py'),'exec'),namespace)
        gate=namespace['evaluate_approved_metadata']
        md={'approved':True,'sufficient_sets':[['S-demo','O-demo']]}
        self.assertTrue(gate(['O-demo','S-demo'],['S-demo','O-demo'],md))
        self.assertFalse(gate(['S-demo','O-demo','NOISE'],['S-demo','O-demo','NOISE'],md))
        for refs in [[],['UNKNOWN'],['S-demo'],['S-demo','O-demo','O-demo']]:self.assertFalse(gate(refs,['S-demo','O-demo'],md))
        self.assertIsNone(gate(['S-demo','O-demo'],['S-demo','O-demo'],dict(md,approved=False)))

    def test_10_prior_input_artifacts_preserved(self):
        baseline=read(OUT/'INPUT_PRESERVATION_BEFORE.json')['files']
        self.assertTrue(baseline)
        for p,h in baseline.items():self.assertEqual(sha(p),h,p)

if __name__=='__main__':
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseChecks))
    textfile('CPU_VALIDATION_LOG.txt',stream.getvalue())
    report={'created_at_utc':now(),'status':'PASS_CPU_ARTIFACT_VALIDATION' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'validation_scope':'CPU input integrity, candidate membership, actual messages, source bytes/body anchors, DEV freeze/split, no label leakage, reference boundary behavior',
            'not_established':['human label approval','model performance','token lengths / loss masks / GPU fit','runnable SFT exporter'],
            'training_executed':False,'gpu_inference_executed':False,'pod_lock_or_stop_touched':False,'reserved_evaluatoronly_opened':False}
    write('CPU_VALIDATION.json',report)
    status('04_CPU_VALIDATION_COMPLETE' if result.wasSuccessful() else '04_CPU_VALIDATION_FAILED',
           [f'CPU 검사 {result.testsRun}개 실행, 실패 {len(result.failures)}, 오류 {len(result.errors)}'],
           ['학습·평가 release blocker는 구조 검사 PASS와 별개로 유지'],[str(OUT/'CPU_VALIDATION.json'),str(OUT/'CPU_VALIDATION_LOG.txt')],
           ['최종 보고서 작성 및 checksum 봉인'],['B01','B02','B03','B04','B05'])
    print(stream.getvalue());raise SystemExit(not result.wasSuccessful())
