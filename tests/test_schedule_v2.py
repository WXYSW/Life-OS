import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review import grade
from learning import record_evidence

def old(**kw):
 i=dict(id='K',status='review',stage=4,last_review='2026-01-01',due='2026-01-31',review_phase='retention',scheduled_interval_days=30)
 i.update(kw);return i
class ScheduleV2(unittest.TestCase):
 def test_hint_recovery_does_not_jump(self):
  a=grade(old(),'hinted','2026-01-31')
  b=grade(a,'correct','2026-02-01')
  c=grade(b,'correct','2026-02-04')
  self.assertEqual((a['scheduled_interval_days'],b['scheduled_interval_days'],c['scheduled_interval_days']),(1,3,7))
  self.assertEqual(c['review_phase'],'retention')
 def test_repeated_hint_restarts_consolidation(self):
  a=grade(old(),'hinted','2026-01-31');a=grade(a,'correct','2026-02-01')
  a=grade(a,'hinted','2026-02-04')
  self.assertEqual((a['consolidation_passes'],a['scheduled_interval_days']),(0,1))
 def test_slip_and_conceptual_differ(self):
  a=grade(old(),'wrong','2026-01-31',error_type='slip')
  b=grade(old(),'wrong','2026-01-31',error_type='conceptual')
  self.assertEqual((a['scheduled_interval_days'],b['scheduled_interval_days']),(7,1))
 def test_effortful_and_early_no_promotion(self):
  self.assertEqual(grade(old(),'correct','2026-01-31',quality='effortful')['scheduled_interval_days'],3)
  a=grade(old(stage=2,scheduled_interval_days=7),'correct','2026-01-03')
  self.assertEqual(a['stage'],2)
 def test_long_interval_requires_two_full_passes(self):
  a=grade(old(),'correct','2026-01-31')
  self.assertEqual(a['scheduled_interval_days'],30)
  b=grade(a,'correct','2026-03-02',quality='transfer')
  self.assertEqual(b['scheduled_interval_days'],60)
  self.assertEqual(b['actual_gap_days'],30)
 def test_deadline_does_not_prove_long_retention(self):
  a=grade(old(),'correct','2026-01-31',target_date='2026-02-05')
  self.assertEqual(a['due'],'2026-02-04')
  b=grade(a,'correct','2026-02-04')
  self.assertEqual(b['scheduled_interval_days'],30)
  self.assertEqual(b['stage'],4)
 def test_recent_failure_hold(self):
  a=grade(old(stage=2,scheduled_interval_days=7,recent_review_outcomes=['wrong','hinted','correct']),'correct','2026-01-08')
  self.assertEqual((a['stage'],a['scheduled_interval_days']),(2,7))
 def test_record_forwards_quality_and_error(self):
  e=dict(id='E',day='2026-01-31',action='delayed_review',dimension='apply',outcome='wrong',independent=True,delayed=True,transfer=False,schedule_eligible=True,basis='observed slip',error_type='slip')
  self.assertEqual(record_evidence(old(),e)['scheduled_interval_days'],7)
 def test_max_interval_and_skip(self):
  i=old(stage=6,scheduled_interval_days=90,long_interval_passes=1)
  self.assertEqual(grade(i,'correct','2026-04-01')['scheduled_interval_days'],90)
  self.assertEqual(grade(i,'skip','2026-04-01'),i)
 def test_bad_metadata(self):
  with self.assertRaises(ValueError):grade(old(),'correct','2026-01-31',quality='guess')
  with self.assertRaises(ValueError):grade(old(),'correct','2026-01-31',target_date='2026-01-01')
if __name__=='__main__':unittest.main()
