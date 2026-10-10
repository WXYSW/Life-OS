"""Ladder grading and legacy selector. Use learning.py for goal-aware planning."""
import argparse
import copy
import json
from datetime import date, timedelta
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'config/review.json').read_text(encoding='utf-8'))


def grade(item, outcome, day, *, quality='stable', error_type='unknown', target_date=None):
    """Evidence-informed ladder. Inputs are assessed by caller, never inferred from text."""
    current = date.fromisoformat(day)
    if outcome not in ('correct', 'hinted', 'wrong', 'skip'):
        raise ValueError('Unknown outcome')
    if quality not in ('effortful', 'stable', 'transfer'):
        raise ValueError('Unknown quality')
    if error_type not in ('unknown', 'forgetting', 'conceptual', 'slip'):
        raise ValueError('Unknown error type')
    target = date.fromisoformat(target_date) if target_date else None
    if target and target < current:
        raise ValueError('Target date is in the past')
    result = copy.deepcopy(item)
    if outcome == 'skip':
        return result
    if item['status'] not in ('pending', 'review'):
        raise ValueError('Activate reference or paused item before grading')
    last = item.get('last_review')
    gap = (current-date.fromisoformat(last)).days if last else None
    if gap is not None and gap <= 0:
        raise ValueError('One schedule-changing attempt per day; corrections require history replay')
    intervals = CONFIG['intervals_days']
    if len(intervals) < 3 or any(type(n) is not int or n <= 0 for n in intervals) or intervals != sorted(set(intervals)):
        raise ValueError('Intervals must be increasing positive integers')
    stage = item.get('stage', -1)
    if type(stage) is not int or not -1 <= stage < len(intervals):
        raise ValueError('Invalid stage')
    phase = item.get('review_phase', 'initial' if stage < 0 else 'retention')
    if phase not in ('initial', 'consolidation', 'retention'):
        raise ValueError('Invalid review phase')
    passes = item.get('consolidation_passes', 0)
    long_passes = item.get('long_interval_passes', 0)
    recent = list(item.get('recent_review_outcomes', []))[-4:]
    failures = sum(o in ('wrong', 'hinted') for o in recent)
    previous_interval = item.get('scheduled_interval_days', intervals[stage] if stage >= 0 else 1)
    delayed = gap is not None and gap >= previous_interval
    reason = ''
    if outcome == 'hinted' or (outcome == 'wrong' and error_type != 'slip'):
        result['pre_lapse_stage'] = stage
        stage, phase, passes, long_passes, interval = 0, 'consolidation', 0, 0, 1
        reason = '提示/遗忘/概念缺口：短期巩固，1天后独立验证'
    elif outcome == 'wrong':
        stage = max(0, min(stage-1, 2))
        interval = intervals[stage]
        long_passes = 0
        if phase == 'consolidation':
            passes, stage, interval = 0, 0, 1
        else:
            phase = 'retention'
        reason = '有依据的局部失误：缩短间隔；不清空既有证据'
    elif stage < 0:
        stage, phase, passes, interval = 0, 'initial', 0, 1
        reason = '首次独立完成：1天后验证'
    elif quality == 'effortful':
        interval = min(intervals[stage], 3)
        long_passes = 0
        reason = '费力答对：暂不升阶，最多3天后验证'
    elif not delayed:
        interval = previous_interval
        reason = '提前作答：保存证据，不升阶'
    elif phase == 'consolidation':
        passes += 1
        stage = min(passes, 2)
        interval = intervals[stage]
        if passes >= 2:
            phase = 'retention'
        reason = '巩固通过：先3天、再7天，不直接恢复旧长间隔'
    elif failures >= 2:
        interval = min(intervals[stage], 7)
        long_passes = 0
        reason = '近期多次失败：暂缓升阶，继续验证'
    elif intervals[stage] >= 30:
        if gap >= intervals[stage]:
            long_passes += 1
        else:
            long_passes = 0
        if long_passes >= CONFIG.get('schedule_policy', {}).get('long_interval_required_passes', 2):
            stage = min(stage+1, len(intervals)-1)
            long_passes = 0
        interval = intervals[stage]
        phase = 'retention'
        reason = '长间隔需两次足间隔独立通过，才向60/90天延长'
    else:
        stage = min(stage+1, len(intervals)-1)
        interval = intervals[stage]
        phase = 'retention'
        reason = '稳定独立完成：升一阶'
    due = current + timedelta(days=interval)
    # One pre-target check; does not change memory stage or prove long retention.
    if target and target > current:
        check = max(current+timedelta(days=1), target-timedelta(days=1))
        if check < due:
            due = check
            reason += '；目标前安排验证'
    result.update(status='review', stage=stage, last_review=day, due=due.isoformat(),
                  review_phase=phase, consolidation_passes=passes,
                  long_interval_passes=long_passes,
                  recent_review_outcomes=(recent+[outcome])[-5:],
                  scheduled_interval_days=(due-current).days,
                  actual_gap_days=gap, schedule_reason=reason,
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
    parser.add_argument('--new-limit', type=int, default=CONFIG['new_limit'])
    parser.add_argument('--review-limit', type=int, default=CONFIG['review_limit'],
                        help='User-selected batch size; no fixed daily cap (0 pauses reviews)')
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
                      args.new_limit, args.review_limit)
    else:
        result = select(items, args.day, assigned, args.new_limit, args.review_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
