import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from learning import plan_actions, record_evidence
from questions import issue, plan

DAY='2026-10-12'
def goal(k='G', **kw):return dict(id=k,status='active',**kw)
def item(k='K',g='G',**kw):
 d=dict(id=k,status='pending',priority='normal',stage=-1,goal_links=[dict(goal_id=g,contribution='high')],prerequisite_ids=[])
 d.update(kw);return d
class LearningTests(unittest.TestCase):
 def test_goal_switch_and_no_mutation(self):
  items=[item('A','G'),item('B','H')];goals=[goal(),goal('H',status_unused=None)]
  p=plan_actions(items,[],goals,DAY,focus_goal='H')
  self.assertEqual([a['knowledge_id'] for a in p['actions']],['B'])
  self.assertEqual(items[1]['status'],'pending')
 def test_fair_allocation_and_time(self):
  items=[item(str(i),'G' if i<5 else 'H',estimated_minutes=5) for i in range(10)]
  p=plan_actions(items,[],[goal(importance='high'),goal('H',importance='low')],DAY,new_limit=4,minutes=20)
  self.assertEqual({a['goal_id'] for a in p['actions']},{'G','H'})
  self.assertEqual(p['estimated_minutes'],20)
  self.assertEqual(plan_actions(items,[],[goal(),goal('H')],DAY,minutes=0)['actions'],[])
 def test_prerequisite_and_cycle(self):
  items=[item('A'),item('B',prerequisite_ids=['A'])]
  p=plan_actions(items,[],[goal()],DAY)
  self.assertEqual([a['knowledge_id'] for a in p['actions']],['A'])
  self.assertEqual(p['blocked'][0]['knowledge_id'],'B')
  items[0]['prerequisite_ids']=['B']
  with self.assertRaises(ValueError):plan_actions(items,[],[goal()],DAY)
 def test_question_ids_resume_and_closed_dedup(self):
  its=[item('A'),item('B')];qs=issue([], 'Q', 'A', 'new','test', '2026-10-11')
  p=plan_actions(its,qs,[goal()],DAY,assigned=['Q'],new_limit=1)
  self.assertEqual(p['actions'][0]['action'],'continue_question')
  qs[0]['status']='evaluated'
  self.assertEqual([a['knowledge_id'] for a in plan_actions(its,qs,[goal()],DAY,assigned=['Q'])['actions']],['B'])
  self.assertEqual(plan(its,qs,DAY,assigned=['Q'])['new_ids'],['B'])
 def test_due_weak_and_future(self):
  its=[item('A',status='review',due=DAY,understanding='needs_relearning'),item('B',status='review',due='2026-10-13')]
  self.assertEqual(plan_actions(its,[],[goal()],DAY)['actions'][0]['action'],'relearn')
  self.assertEqual(len(plan_actions(its,[],[goal()],DAY)['actions']),1)
 def test_pause_waiting_and_validation(self):
  its=[item('A'),item('B',status='needs_validation')]
  qs=issue([], 'Q', 'A', 'new','test','2026-10-11');qs[0]['status']='paused'
  self.assertEqual(plan_actions(its,qs,[goal()],DAY)['actions'],[])
  qs[0]['status']='awaiting_evaluation'
  self.assertEqual(plan_actions(its,qs,[goal()],DAY)['awaiting_evaluation_ids'],['Q'])
 def event(self,**kw):
  e=dict(id='E',day=DAY,action='diagnose',dimension='recall',outcome='correct',independent=True,delayed=False,transfer=False,schedule_eligible=True,basis='attempt-A')
  e.update(kw);return e
 def test_evidence_idempotency_and_hints(self):
  i=item();e=self.event(independent=False)
  r=record_evidence(i,e)
  self.assertEqual(r['mastery']['recall']['state'],'supported')
  self.assertEqual(r['due'],'2026-10-13')
  self.assertEqual(record_evidence(r,e),r)
  with self.assertRaises(ValueError):record_evidence(r,self.event())
 def test_practice_no_promotion_and_same_day(self):
  r=record_evidence(item(),self.event())
  s=record_evidence(r,self.event(id='E2',action='practice'))
  self.assertEqual((s['stage'],s['due']),(r['stage'],r['due']))
  s=record_evidence(s,self.event(id='E3',action='apply'))
  self.assertEqual(s['stage'],0)
  self.assertEqual(len(s['learning_events']),3)
 def test_skip_preserves_and_unknown_goal(self):
  r=record_evidence(item(),self.event(outcome='skip'))
  self.assertNotIn('mastery',r)
  with self.assertRaises(ValueError):plan_actions([item()],[],[goal()],DAY,focus_goal='X')
if __name__=='__main__':unittest.main()
