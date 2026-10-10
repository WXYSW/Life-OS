import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review import grade, select


def item(key='K1', **kwargs):
    return dict(id=key, status='pending', stage=-1, due=None, priority='normal', **kwargs)


class SchedulingTests(unittest.TestCase):
    def test_first_then_late_pass_uses_actual_date(self):
        original = item()
        first = grade(original, 'correct', '2026-10-10')
        self.assertEqual(first['due'], '2026-10-11')
        late = grade(first, 'correct', '2026-10-20')
        self.assertEqual(late['due'], '2026-10-23')
        self.assertEqual(original['stage'], -1)

    def test_hint_wrong_skip(self):
        old = dict(id='K1', status='review', stage=3, due='2026-10-10', priority='core')
        hint = grade(old, 'hinted', '2026-10-10')
        self.assertEqual((hint['stage'], hint['due']), (0, '2026-10-11'))
        self.assertEqual(hint['review_phase'], 'consolidation')
        self.assertEqual(grade(old, 'wrong', '2026-10-10')['stage'], 0)
        self.assertEqual(grade(old, 'skip', '2026-10-10'), old)

    def test_no_same_day_advancement(self):
        first = grade(item(), 'correct', '2026-10-10')
        with self.assertRaises(ValueError):
            grade(first, 'correct', '2026-10-10')

    def test_max_stage_and_year_boundary(self):
        old = dict(id='K1', status='review', stage=4)
        new = grade(old, 'correct', '2026-12-20')
        self.assertEqual((new['stage'], new['due']), (4, '2027-01-19'))

    def test_selection_excludes_assigned_reference_and_future(self):
        items = [item('N1'), item('N2'), item('N3'),
                 dict(id='R1', status='review', stage=0, due='2026-10-01', priority='normal'),
                 dict(id='R2', status='review', stage=0, due='2026-10-10', priority='core'),
                 dict(id='F', status='review', stage=0, due='2026-10-11', priority='core'),
                 dict(id='L', status='reference', priority='low')]
        chosen = select(items, '2026-10-10', ['N1'])
        self.assertEqual(chosen['new_ids'], ['N2', 'N3'])
        self.assertEqual(chosen['review_ids'], ['R2', 'R1'])
        self.assertEqual(select(items, '2026-10-10', new_limit=0)['new_ids'], [])

    def test_reject_duplicates(self):
        with self.assertRaises(ValueError):
            select([item(), item()], '2026-10-10')


if __name__ == '__main__':
    unittest.main()
