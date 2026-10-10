"""Pure scheduling functions; caller persists records after privacy review."""
import argparse
import copy
import json
from datetime import date, timedelta
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'config/review.json').read_text(encoding='utf-8'))


def grade(item, outcome, day):
    current = date.fromisoformat(day)
    if outcome not in ('correct', 'hinted', 'wrong', 'skip'):
        raise ValueError('Unknown outcome')
    result = copy.deepcopy(item)
    if outcome == 'skip':
        return result
    if item['status'] not in ('pending', 'review'):
        raise ValueError('Activate reference or paused item before grading')
    last = item.get('last_review')
    if last and current <= date.fromisoformat(last):
        raise ValueError('One schedule-changing attempt per day; corrections require history replay')
    stage = item.get('stage', -1)
    if not isinstance(stage, int) or not -1 <= stage < len(CONFIG['intervals_days']):
        raise ValueError('Invalid stage')
    if outcome == 'correct':
        stage = min(stage + 1, len(CONFIG['intervals_days']) - 1)
        interval = CONFIG['intervals_days'][stage]
    elif outcome == 'hinted':
        stage, interval = max(0, stage), 1
    else:
        stage, interval = 0, 1
    result.update(status='review', stage=stage, last_review=day,
                  due=(current + timedelta(days=interval)).isoformat(),
                  rule_version=CONFIG['version'])
    return result


def select(items, day, assigned=(), new_limit=None, review_limit=None):
    date.fromisoformat(day)
    new_limit = CONFIG['new_limit'] if new_limit is None else new_limit
    review_limit = CONFIG['review_limit'] if review_limit is None else review_limit
    if min(new_limit, review_limit) < 0:
        raise ValueError('Limits must be nonnegative')
    if len({x['id'] for x in items}) != len(items):
        raise ValueError('Duplicate knowledge IDs')
    eligible = [x for x in items if x['id'] not in assigned and x.get('priority') != 'low']
    rank = lambda x: (0 if x.get('priority') == 'core' else 1, x.get('due') or '', x['id'])
    due = []
    for x in eligible:
        if x['status'] == 'review':
            if not x.get('due'):
                raise ValueError('Review item missing due date')
            if date.fromisoformat(x['due']) <= date.fromisoformat(day):
                due.append(x)
    pending = [x for x in eligible if x['status'] == 'pending']
    return {'day': day, 'new_ids': [x['id'] for x in sorted(pending, key=rank)[:new_limit]],
            'review_ids': [x['id'] for x in sorted(due, key=rank)[:review_limit]]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['select'])
    parser.add_argument('queue')
    parser.add_argument('--day', required=True)
    parser.add_argument('--session', help='Saved session JSON containing assigned_ids')
    parser.add_argument('--questions', help='Cross-day backlog; auto-detects knowledge/questions/backlog.json')
    args = parser.parse_args()
    items = json.loads(Path(args.queue).read_text(encoding='utf-8'))
    assigned = []
    if args.session:
        session = json.loads(Path(args.session).read_text(encoding='utf-8'))
        if session['day'] != args.day:
            raise ValueError('Session date mismatch')
        assigned = session['assigned_ids']
    question_path = Path(args.questions) if args.questions else Path(args.queue).parent.parent / 'questions/backlog.json'
    if question_path.exists():
        from questions import plan
        backlog = json.loads(question_path.read_text(encoding='utf-8'))
        result = plan(items, backlog['questions'], args.day, assigned,
                      CONFIG['new_limit'], CONFIG['review_limit'])
    else:
        result = select(items, args.day, assigned)
    print(json.dumps(result, ensure_ascii=False, indent=2))

