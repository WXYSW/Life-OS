import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from questions import issue, change, plan


def items():
    return [dict(id=f'N{i}', status='pending', priority='core', due=None) for i in range(1,4)]


class QuestionLifecycleTests(unittest.TestCase):
    def test_cross_day_continuation_occupies_new_slot(self):
        q = issue([], 'Q1', 'N1', 'new', 'Explain the concept', '2026-10-10')
        p = plan(items(), q, '2026-10-11')
        self.assertEqual(p['resume_question_ids'], ['Q1'])
        self.assertEqual(p['new_ids'], ['N2'])
        self.assertEqual(q[0]['status'], 'unanswered')

    def test_partial_fragments_and_idempotent_retry(self):
        q = issue([], 'Q1', 'N1', 'new', 'Explain and apply', '2026-10-10')
        q = change(q, 'Q1', 'answer', '2026-10-10', 'A1', 'Explanation')
        self.assertEqual(q[0]['status'], 'partial')
        retry = change(q, 'Q1', 'answer', '2026-10-10', 'A1', 'Explanation')
        self.assertEqual(retry, q)
        with self.assertRaises(ValueError):
            change(q, 'Q1', 'answer', '2026-10-10', 'A1', 'Changed explanation')
        self.assertEqual(plan(items(), q, '2026-10-11')['resume_question_ids'], ['Q1'])
        q = change(q, 'Q1', 'answer', '2026-10-11', 'A2', 'Application', complete=True)
        p = plan(items(), q, '2026-10-11')
        self.assertEqual(p['awaiting_evaluation_ids'], ['Q1'])
        self.assertNotIn('N1', p['new_ids'])
        self.assertEqual(len(q[0]['answer_fragments']), 2)

    def test_skip_pause_resume_preserve_history(self):
        q = issue([], 'Q1', 'N1', 'new', 'Question', '2026-10-10')
        q = change(q, 'Q1', 'skip', '2026-10-10', 'S1')
        self.assertEqual(plan(items(), q, '2026-10-10')['resume_question_ids'], [])
        self.assertEqual(plan(items(), q, '2026-10-11')['resume_question_ids'], ['Q1'])
        q = change(q, 'Q1', 'pause', '2026-10-11', 'P1')
        self.assertNotIn('N1', plan(items(), q, '2026-10-12')['new_ids'])
        q = change(q, 'Q1', 'resume', '2026-10-12', 'R1')
        self.assertEqual(q[0]['prompt'], 'Question')

    def test_duplicate_question_is_rejected(self):
        q = issue([], 'Q1', 'N1', 'new', 'Question', '2026-10-10')
        with self.assertRaises(ValueError):
            issue(q, 'Q2', 'N1', 'new', 'Other', '2026-10-11')

    def test_evaluation_requires_completion_and_not_rescheduled_by_plan(self):
        q = issue([], 'Q1', 'N1', 'new', 'Question', '2026-10-10')
        with self.assertRaises(ValueError):
            change(q, 'Q1', 'evaluate', '2026-10-10', 'E1')
        q = change(q, 'Q1', 'answer', '2026-10-11', 'A1', 'Answer', complete=True)
        q = change(q, 'Q1', 'evaluate', '2026-10-11', 'E1')
        updated = items()
        updated[0].update(status='review', due='2026-10-12')
        self.assertNotIn('N1', plan(updated, q, '2026-10-11')['new_ids'])

    def test_review_continuation_blocks_duplicate_due_item(self):
        its = [dict(id='R1', status='review', due='2026-10-01', priority='core')]
        q = issue([], 'Q1', 'R1', 'review', 'Question', '2026-10-10')
        p = plan(its, q, '2026-10-11')
        self.assertEqual(p['resume_question_ids'], ['Q1'])
        self.assertEqual(p['review_ids'], [])
        self.assertEqual(its[0]['due'], '2026-10-01')

    def test_zero_budget_and_session_exclusion(self):
        q = issue([], 'Q1', 'N1', 'new', 'Question', '2026-10-10')
        p = plan(items(), q, '2026-10-11', new_limit=0, review_limit=0)
        self.assertEqual((p['resume_question_ids'], p['new_ids']), ([], []))
        p = plan(items(), q, '2026-10-11', assigned=['N2'])
        self.assertEqual(p['new_ids'], ['N3'])


if __name__ == '__main__':
    unittest.main()
