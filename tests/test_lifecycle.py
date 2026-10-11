import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from lifecycle import (create_intake,verify_content,set_match,refresh,classify,evaluate,
                       plan,complete_goal,decide,deletion_proposal,validate,load,save)
from review import grade
DAY='2026-10-11'

def goals():return [dict(id='G1',status='active'),dict(id='G2',status='active')]
def item(k='KP-A',tested=False):
    i=verify_content(create_intake(k,'概念'+k,['S'],DAY),'已核验教材定义',DAY)
    if tested:i.update(assessment='tested',schedule=dict(status='review',stage=0,due='2026-10-12',last_review=DAY,scheduled_interval_days=1))
    return i
def match(i,g='G1',rel='direct'):
    return set_match(i,goals(),g,rel,DAY,basis='大纲条目核对',syllabus_id='S1',section_ids=['SEC'])
def event(**kw):
    e=dict(id='E1',day='2026-10-12',action='diagnose',dimension='recall',outcome='correct',independent=True,delayed=False,transfer=False,schedule_eligible=True,basis='独立准确解释规则',quality='stable',error_type='unknown')
    e.update(kw);return e

class LifecycleTests(unittest.TestCase):
    def test_default_review_never_takes_intake(self):
        i=match(item());self.assertEqual(plan([i],goals(),DAY)['actions'],[])
        self.assertEqual(plan([i],goals(),DAY,mode='diagnose')['actions'][0]['knowledge_id'],i['id'])
    def test_intake_diagnosis_without_goal_is_possible(self):
        i=item();self.assertEqual(len(plan([i],goals(),DAY,mode='diagnose')['actions']),1)
    def test_unverified_and_archived_never_tested(self):
        i=create_intake('KP-A','概念',['S'],DAY)
        self.assertEqual(plan([i],goals(),DAY,mode='diagnose')['blocked'][0]['reason'],'verify_content_first')
        with self.assertRaises(ValueError):evaluate(i,event(),goals())
        i=decide(verify_content(i,'教材',DAY),goals(),'archive',DAY,reason='用户归档')
        self.assertEqual(plan([i],goals(),DAY,mode='diagnose')['actions'],[])
        with self.assertRaises(ValueError):evaluate(i,event(),goals())
    def test_wrong_is_tested_and_schedule_is_original_ladder(self):
        i=match(item());before=copy.deepcopy(i);e=event(outcome='wrong',error_type='conceptual')
        result=evaluate(i,e,goals());self.assertEqual(result['assessment'],'tested')
        self.assertEqual(result['schedule'],grade(i['schedule'],'wrong',e['day'],error_type='conceptual'))
        self.assertEqual(result['routing']['route'],'review');self.assertEqual(i,before)
    def test_same_day_and_idempotency(self):
        i=evaluate(match(item()),event(),goals())
        self.assertEqual(evaluate(i,event(),goals()),i)
        j=evaluate(i,event(id='E2',outcome='wrong'),goals())
        self.assertEqual(j['schedule'],i['schedule']);self.assertEqual(len(j['evidence']),2)
        with self.assertRaises(ValueError):evaluate(i,event(outcome='wrong'),goals())
    def test_raw_question_fields_are_discarded(self):
        r=evaluate(item(),event(prompt='full question',answer_text='raw answer',options=['a','b']),goals())
        e=r['evidence'][0]
        for key in ('prompt','answer_text','options'):self.assertNotIn(key,e)
    def test_unknown_independence_does_not_promote(self):
        i=item();r=evaluate(i,event(independent=None),goals())
        self.assertEqual(r['schedule'],i['schedule']);self.assertEqual(r['mastery']['recall']['state'],'unverified')
    def test_wrong_delayed_answer_never_counts_as_delayed_success(self):
        r=evaluate(item(),event(outcome='wrong',delayed=True,transfer=True),goals())
        self.assertNotIn('delayed_evidence_id',r['mastery']['recall']);self.assertNotIn('transfer_evidence_id',r['mastery']['recall'])
    def test_partial_unknown_practice_skip(self):
        for outcome in ('partial','unknown'):
            i=item();r=evaluate(i,event(outcome=outcome),goals())
            self.assertEqual(r['assessment'],'tested');self.assertEqual(r['schedule'],i['schedule'])
        for ev in (event(action='practice'),event(outcome='skip')):
            r=evaluate(item(),ev,goals());self.assertEqual(r['assessment'],'untested');self.assertIsNone(r['schedule']['due'])
    def test_scope_does_not_change_siblings(self):
        a,b=item('KP-A'),item('KP-B');old=copy.deepcopy(b)
        evaluate(a,event(knowledge_id='KP-A'),goals());self.assertEqual(b,old)
        with self.assertRaises(ValueError):evaluate(a,event(canonical_ids=['KP-A','KP-B']),goals())
    def test_completed_goal_protects_shared_knowledge(self):
        i=match(match(item(tested=True)),g='G2');old=copy.deepcopy(i['schedule'])
        result=complete_goal([i],goals(),'G1',DAY)
        self.assertEqual(result['items'][0]['routing']['route'],'review')
        self.assertEqual(result['items'][0]['routing']['active_goal_ids'],['G2'])
        self.assertEqual(result['items'][0]['schedule'],old)
        self.assertEqual(result['decisions'],[])
    def test_no_goal_match_requests_decision(self):
        i=match(match(item(tested=True)),g='G2',rel='unrelated')
        result=complete_goal([i],goals(),'G1',DAY)
        self.assertEqual(result['decisions'],[i['id']]);self.assertEqual(result['items'][0]['evidence'],i['evidence'])
    def test_uncertainty_never_becomes_delete_candidate(self):
        i=match(item(tested=True));r=complete_goal([i],goals(),'G1',DAY)
        self.assertEqual(r['items'][0]['routing']['route'],'classification_pending');self.assertEqual(r['decisions'],[])
        self.assertTrue(deletion_proposal(r['items'][0],r['items'],r['goals'])['blocked'])
    def test_future_goal_retains_and_blocks_deletion(self):
        i=match(match(item(tested=True)),g='G2');gs=goals();gs[1]['status']='aspiration'
        r=complete_goal([i],gs,'G1',DAY)
        self.assertEqual(r['items'][0]['routing']['route'],'retained')
        self.assertTrue(deletion_proposal(r['items'][0],r['items'],r['goals'])['blocked'])
    def test_archival_restoration_keeps_memory(self):
        i=match(item(tested=True));arch=decide(i,goals(),'archive',DAY,reason='暂停')
        self.assertEqual(plan([arch],goals(),'2026-11-12')['actions'],[])
        restored=decide(arch,goals(),'restore','2026-11-12',reason='恢复')
        self.assertEqual(restored['schedule'],i['schedule'])
        self.assertEqual(len(plan([restored],goals(),'2026-11-12')['actions']),1)
    def test_invalid_or_missing_outline_rejected(self):
        i=match(item());i=refresh([i],goals(),DAY)[0]
        with self.assertRaises(ValueError):validate([i],goals(),[])
        with self.assertRaises(ValueError):set_match(i,goals(),'G1','direct',DAY,basis='guess')
    def test_new_goal_requires_reclassification(self):
        i=match(match(item(tested=True),rel='unrelated'),g='G2',rel='unrelated')
        self.assertEqual(classify(i,goals())['route'],'decision_required')
        self.assertEqual(classify(i,goals()+[dict(id='G3',status='active')])['route'],'classification_pending')
    def test_outline_version_change_reopens_classification(self):
        i=match(match(item(tested=True)),g='G2',rel='unrelated')
        gs=goals();gs[0]['syllabus_ids']=['S2']
        self.assertEqual(classify(i,gs)['route'],'classification_pending')
        self.assertIn('G1',classify(i,gs)['unresolved_goal_ids'])

    def test_budget_no_duplicate_and_zero(self):
        items=[match(item('KP-'+str(i),tested=True)) for i in range(4)]
        self.assertEqual(len(plan(items,goals(),'2026-10-12',minutes=20)['actions']),2)
        self.assertEqual(plan(items,goals(),'2026-10-12',limit=0)['actions'],[])
        self.assertEqual(len(plan(items,goals(),'2026-10-12',assigned=['KP-0'])['actions']),3)
    def test_migration_preserves_evidence_dates_and_archives(self):
        items,gs=load(ROOT);self.assertEqual(len(items),277)
        self.assertEqual(sum(len(i['evidence']) for i in items),53)
        self.assertEqual(sum(i['assessment']=='tested' for i in items),47)
        for i in items:
            if i['assessment']=='untested':self.assertIsNone(i['schedule'].get('due'))
            if i.get('schedule_migration'):self.assertEqual(i['schedule']['due'],'2026-10-12')
        sources=[json.loads(p.read_text()) for p in (ROOT/'knowledge/items').glob('*.json')]
        self.assertEqual(sum(i.get('record_type')=='legacy_source' and i.get('status')=='paused' for i in sources),73)
    def test_write_rebuilds_indexes_without_touching_life_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('__pycache__'))
            (root/'records').mkdir();(root/'records/day.json').write_text('{"english_minutes":30}')
            (root/'reports').mkdir();(root/'reports/day.md').write_text('生活报告')
            items,gs=load(root);new=create_intake('KP-TEST-NEW','测试新增范围',['S'],DAY)
            save(root,items+[new],gs,DAY)
            from catalogue import validate_catalogue
            self.assertEqual(validate_catalogue(root)['canonical_assessable_scopes'],278)
            self.assertEqual((root/'records/day.json').read_text(),'{"english_minutes":30}')
            self.assertEqual((root/'reports/day.md').read_text(),'生活报告')
            views=json.loads((root/'knowledge/lifecycle/views.json').read_text())
            self.assertIn(new['id'],views['views']['intake'])
    def test_cli_requires_explicit_diagnosis_mode(self):
        r=subprocess.run([sys.executable,str(ROOT/'scripts/learning.py'),'--day',DAY,'--new-limit','2'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('--mode diagnose',r.stderr)

if __name__=='__main__':unittest.main()
