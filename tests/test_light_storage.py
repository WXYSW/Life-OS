import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from learning import record_evidence,main
from review import grade
class LightStorageTests(unittest.TestCase):
 def test_no_question_storage_and_evidence_preserved(self):
  for p in ('knowledge/questions','knowledge/attempts','knowledge/sessions','knowledge/catalog/evidence-map.json','knowledge/catalog/question-map.json'):
   self.assertFalse((ROOT/p).exists())
  records=[json.loads(p.read_text()) for p in (ROOT/'knowledge/items').glob('*.json')]
  evidence=[e for i in records for e in i.get('diagnostic_evidence',[])]
  self.assertEqual(len(evidence),53)
  self.assertEqual(len({e['attempt_id'] for e in evidence}),19)
  self.assertEqual(len({e['canonical_id'] for e in evidence}),47)
  for i in records:self.assertNotIn('diagnostic_question',i)
 def test_raw_text_dropped_schedule_matches_grade_and_idempotent(self):
  i=dict(id='K',stage=-1,status='pending',taxonomy={'canonical_ids':['X']})
  e=dict(id='E',day='2026-10-11',action='diagnose',dimension='recall',outcome='wrong',independent=True,delayed=False,transfer=False,schedule_eligible=True,basis='动名词规则缺口',canonical_ids=['X'],answer_text='private raw',prompt='full prompt',options=['a','b'])
  before=copy.deepcopy(i);got=record_evidence(i,e);expected=grade(i,'wrong','2026-10-11')
  for k in expected:self.assertEqual(got[k],expected[k])
  self.assertNotIn('answer_text',got['learning_events'][0]);self.assertNotIn('prompt',got['learning_events'][0]);self.assertNotIn('options',got['learning_events'][0])
  self.assertEqual(record_evidence(got,e),got);self.assertEqual(i,before)
  self.assertEqual(got['diagnostic_evidence'][0]['canonical_id'],'X')
 def test_explicit_scope_required(self):
  i=dict(id='K',taxonomy={'canonical_ids':['X']})
  e=dict(id='E',day='2026-10-11',action='diagnose',dimension='recall',outcome='correct',independent=True,delayed=False,transfer=False,schedule_eligible=False,basis='独立正确')
  with self.assertRaises(ValueError):record_evidence(i,e)
