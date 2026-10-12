import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from lifecycle import create_intake,verify_content,set_match,refresh,evaluate,classify,plan
from review_engine import memory_snapshot,requirement_gap,formal_review_ready,plan_round
from review import grade
DAY='2026-10-12'

def goals():return [dict(id='G1',status='active',exact_date='2026-10-13'),dict(id='G2',status='active',exact_date='2027-06-01')]
def ev(id='E0',day='2026-10-11',**kw):
    d=dict(id=id,day=day,action='diagnose',dimension='recall',outcome='correct',independent=True,delayed=False,transfer=False,schedule_eligible=True,basis='Independent test',quality='stable',error_type='unknown',actual_gap_days=None,scheduled_interval_before=None)
    d.update(kw);return d

def item(k='KP-A',g='G1',outcome='correct',due=DAY):
    i=verify_content(create_intake(k,k,['S'],'2026-10-11'),'verified textbook','2026-10-11')
    i.update(assessment='tested',module_id='M1',evidence=[ev(outcome=outcome)],
             schedule=dict(status='review',stage=0,due=due,last_review='2026-10-11',scheduled_interval_days=1))
    i=set_match(i,goals(),g,'direct','2026-10-11',basis='outline',syllabus_id='S1',section_ids=['A'])
    return i

class ReviewEngineTests(unittest.TestCase):
    def test_urgent_goal_never_pulls_secure_future_item(self):
        i=item(due='2026-11-11');i['schedule'].update(stage=4,scheduled_interval_days=30)
        self.assertEqual(plan_round([i],goals(),DAY)['actions'],[])
        self.assertEqual(len(plan_round([i],goals(),DAY,mode='reinforce')['actions']),1)
    def test_overdue_failure_beats_near_exam_stable_item(self):
        secure=item('KP-A','G1');weak=item('KP-B','G2','wrong',due='2026-10-11')
        p=plan_round([secure,weak],goals(),DAY,limit=1)
        self.assertEqual(p['actions'][0]['knowledge_id'],'KP-B')
        self.assertIn('最近测试有错误或依赖提示，需独立验证',p['actions'][0]['reasons'])
    def test_slip_is_not_ranked_as_severe_forgetting(self):
        slip=item('KP-A',outcome='wrong');slip['evidence'][0]['error_type']='slip'
        forgotten=item('KP-B','G2',outcome='wrong');forgotten['evidence'][0]['error_type']='forgetting'
        p=plan_round([slip,forgotten],goals(),DAY)
        self.assertEqual(p['actions'][0]['knowledge_id'],'KP-B')
        self.assertFalse(memory_snapshot(slip,DAY)['critical_failure'])
    def test_effortful_correct_stays_in_consolidation(self):
        i=item();i['evidence'][0]['quality']='effortful'
        self.assertEqual(memory_snapshot(i,DAY)['state'],'consolidation')
        self.assertEqual(plan_round([i],goals(),DAY)['actions'][0]['priority_tier'],1)
    def test_risk_is_recomputed_not_read_from_stale_cache(self):
        i=item();i['memory']={'risk':'low','as_of':'2026-10-01'}
        self.assertEqual(plan_round([i],goals(),'2026-10-14')['actions'][0]['memory']['risk'],'high')

    def test_unknown_deadline_is_not_invented(self):
        gs=goals();gs[0].pop('exact_date');gs[0]['deadline']='2026-10'
        a=plan_round([item()],gs,DAY)['actions'][0]['goal_demands'][0]
        self.assertIsNone(a['days_remaining']);self.assertEqual(a['urgency'],'unknown')
    def test_missing_evidence_and_partial_schedule_return_to_assessment(self):
        i=item();i['evidence']=[]
        self.assertFalse(formal_review_ready(i));self.assertEqual(classify(i,goals())['route'],'assessment_pending')
        self.assertEqual(plan_round([i],goals(),DAY)['actions'],[])
        i['evidence']=[ev(outcome='partial')];i['schedule']={'status':'pending','stage':-1,'due':None}
        self.assertEqual(classify(i,goals())['route'],'assessment_pending')
        self.assertEqual(len(plan([i],goals(),DAY,mode='diagnose')['actions']),1)
    def test_unverified_never_enters_formal_queue(self):
        i=item();i['verification']={'status':'needs_validation','basis':None}
        self.assertEqual(classify(i,goals())['route'],'verification_pending')
        self.assertEqual(plan_round([i],goals(),DAY)['actions'],[])
    def test_multi_goal_is_one_scope(self):
        i=set_match(item(),goals(),'G2','direct','2026-10-11',basis='outline',syllabus_id='S1',section_ids=['B'])
        p=plan_round([i],goals(),DAY)
        self.assertEqual(p['scope_count'],1);self.assertEqual(len(p['actions'][0]['served_goal_ids']),2)
    def test_requirement_gap_is_goal_specific(self):
        i=item();i['evidence']=[ev(dimension='explain')]
        self.assertEqual(requirement_gap(i,{'mastery_requirement':'understanding'},DAY)['status'],'met')
        self.assertEqual(requirement_gap(i,{'mastery_requirement':'application'},DAY)['status'],'unknown')
        i['evidence'].append(ev(id='E1',dimension='apply',transfer=False))
        self.assertEqual(requirement_gap(i,{'mastery_requirement':'integration'},DAY)['status'],'partial')
        i['evidence'].append(ev(id='E2',dimension='apply',transfer=True))
        self.assertEqual(requirement_gap(i,{'mastery_requirement':'integration'},DAY)['status'],'met')
    def test_requirements_require_basis(self):
        with self.assertRaises(ValueError):set_match(item(),goals(),'G1','direct',DAY,basis='outline',syllabus_id='S1',section_ids=['A'],mastery_requirement='application')
    def test_latest_dimension_failure_overrides_previous_success(self):
        i=item();i['evidence']=[ev(dimension='apply'),ev(id='E1',dimension='apply',outcome='wrong')]
        self.assertEqual(requirement_gap(i,{'mastery_requirement':'application'},DAY)['status'],'unmet')
    def test_goal_and_module_diversity_at_same_risk(self):
        xs=[item('KP-A'),item('KP-B'),item('KP-C','G2')]
        xs[1]['module_id']='M2'
        p=plan_round(xs,goals(),DAY,limit=2)
        self.assertEqual({a['goal_id'] for a in p['actions']},{'G1','G2'})
        p=plan_round(xs[:2]+[item('KP-D')],goals(),DAY,limit=2)
        self.assertEqual([a['knowledge_id'] for a in p['actions']],['KP-A','KP-B'])
    def test_verified_imminent_gap_allows_concentration(self):
        xs=[item('KP-A'),item('KP-B'),item('KP-C','G2')]
        for i in xs[:2]:
            i['evidence'].append(ev(id='APPLY-'+i['id'],dimension='apply',outcome='partial'))
            i['goal_links'][0].update(mastery_requirement='application',requirement_basis='required application')
        p=plan_round(xs,goals(),DAY,limit=2)
        self.assertEqual([a['goal_id'] for a in p['actions']],['G1','G1'])
    def test_due_blocking_prerequisite_gets_priority(self):
        a,b=item('KP-A'),item('KP-B','G2')
        child=item('KP-C','G2',due='2026-12-01');child['prerequisite_ids']=['KP-B']
        p=plan_round([a,b,child],goals(),DAY,limit=1)
        self.assertEqual(p['actions'][0]['knowledge_id'],'KP-B')
    def test_profiles_budget_no_fill_and_explicit_override(self):
        xs=[item('KP-'+str(i)) for i in range(10)]
        for profile,n in [('light',3),('standard',5),('deep',8)]:
            self.assertEqual(plan_round(xs,goals(),DAY,profile=profile)['scope_count'],n)
        self.assertEqual(plan_round(xs[:2],goals(),DAY)['scope_count'],2)
        self.assertEqual(plan_round(xs,goals(),DAY,minutes=15)['scope_count'],1)
        self.assertEqual(plan_round(xs,goals(),DAY,minutes=0)['scope_count'],0)
        self.assertEqual(plan_round(xs,goals(),DAY,limit=7)['scope_count'],7)
        self.assertIsNone(plan_round(xs,goals(),DAY)['question_count'])
    def test_next_round_replans_from_latest_evidence(self):
        xs=[item('KP-'+str(i)) for i in range(7)];p=plan_round(xs,goals(),DAY)
        for action in p['actions']:
            i=next(i for i in xs if i['id']==action['knowledge_id'])
            result=evaluate(i,ev(id='NEW-'+i['id'],day=DAY,action='delayed_review',delayed=True),goals())
            i.clear();i.update(result)
        self.assertEqual(plan_round(xs,goals(),DAY)['scope_count'],2)
    def test_targeted_practice_never_changes_ladder_even_if_flag_true(self):
        i=item();old=copy.deepcopy(i['schedule'])
        e=ev(id='R1',day=DAY,action='reinforce',schedule_eligible=True,dimension='apply')
        r=evaluate(i,e,goals())
        self.assertEqual(r['schedule'],old);self.assertFalse(r['evidence'][-1]['schedule_eligible'])
        self.assertFalse(r['evidence'][-1]['schedule_changed'])
        self.assertEqual(evaluate(r,e,goals()),r)
        self.assertEqual(plan_round([r],goals(),DAY)['scope_count'],0)
    def test_formal_after_same_day_practice_has_no_memory_promotion(self):
        r=evaluate(item(),ev(id='P',day=DAY,action='practice'),goals());old=copy.deepcopy(r['schedule'])
        r=evaluate(r,ev(id='R',day=DAY,action='delayed_review',delayed=True),goals())
        self.assertEqual(r['schedule'],old);self.assertFalse(r['evidence'][-1]['schedule_changed'])
    def test_same_day_repetitions_never_prove_long_retention(self):
        i=item();i['evidence']=[ev(id=str(j),day='2026-10-11',actual_gap_days=30,scheduled_interval_before=30,delayed=True) for j in range(3)]
        m=memory_snapshot(i,DAY)
        self.assertEqual(m['supporting_passes'],1);self.assertFalse(m['long_term_verified'])
    def test_long_term_needs_two_full_gap_independent_stable_passes(self):
        i=item();i['evidence']=[ev(id='L1',day='2026-08-01',actual_gap_days=30,scheduled_interval_before=30),ev(id='L2',day='2026-09-01',actual_gap_days=31,scheduled_interval_before=30)]
        self.assertTrue(memory_snapshot(i,DAY)['long_term_verified'])
        i['evidence'].append(ev(id='L3',day='2026-10-01',outcome='wrong',actual_gap_days=30,scheduled_interval_before=30))
        self.assertFalse(memory_snapshot(i,DAY)['long_term_verified'])
        self.assertIsNone(memory_snapshot(i,DAY)['observed_stability_days'])
    def test_early_hinted_effortful_and_unknown_are_not_stability_passes(self):
        for patch in [dict(actual_gap_days=3),dict(independent=None),dict(independent=False),dict(quality='effortful'),dict(lookup_used=True),dict(schedule_changed=False)]:
            i=item();e=ev(actual_gap_days=30,scheduled_interval_before=30);e.update(patch);i['evidence']=[e]
            self.assertEqual(memory_snapshot(i,DAY)['supporting_passes'],0)
    def test_normal_grade_remains_identical(self):
        i=item();e=ev(id='NEW',day=DAY,action='delayed_review')
        r=evaluate(i,e,goals())
        self.assertEqual(r['schedule'],grade(i['schedule'],'correct',DAY))
    def test_read_only_planning_and_in_memory_assigned(self):
        i=item();old=copy.deepcopy(i)
        self.assertEqual(plan_round([i],goals(),DAY,assigned=[i['id']])['actions'],[])
        plan_round([i],goals(),DAY);self.assertEqual(i,old)
    def test_real_cli_profiles_and_reinforcement(self):
        for args in (['--profile','light'],['--profile','deep'],['--mode','reinforce','--review-limit','1']):
            p=subprocess.run([sys.executable,str(ROOT/'scripts/learning.py'),'--day',DAY]+args,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            obj=json.loads(p.stdout);self.assertEqual(obj['version'],'review-v3')

if __name__=='__main__':unittest.main()
