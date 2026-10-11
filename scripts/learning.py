"""Explainable learning actions. Pure planning; caller persists actual events."""
import argparse
import copy
import json
from datetime import date
from pathlib import Path
OPEN={'unanswered','partial','awaiting_evaluation','deferred','paused'}
def validate(questions):
    ids=[q['id'] for q in questions]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate ephemeral question IDs')
from review import CONFIG, grade

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'knowledge-light-v1'


def plan_actions(items, questions, goals, day, assigned=(), new_limit=2,
                 review_limit=5, minutes=None, focus_goal=None, energy='normal'):
    today = date.fromisoformat(day)
    for value in (new_limit, review_limit):
        if type(value) is not int or value < 0:
            raise ValueError('Limits must be nonnegative integers')
    if minutes is not None and (type(minutes) is not int or minutes < 0):
        raise ValueError('Minutes must be a nonnegative integer')
    if energy not in ('low', 'normal', 'high'):
        raise ValueError('Unknown energy')
    validate(questions)
    im = {i['id']: i for i in items}
    gm = {g['id']: g for g in goals}
    if len(im) != len(items) or len(gm) != len(goals):
        raise ValueError('Duplicate IDs')
    if any(q['knowledge_id'] not in im for q in questions):
        raise ValueError('Question references missing knowledge')
    for i in items:
        if any(p not in im for p in i.get('prerequisite_ids', [])):
            raise ValueError('Missing prerequisite')
        if any(l['goal_id'] not in gm for l in i.get('goal_links', [])):
            raise ValueError('Missing goal')
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('Prerequisite cycle')
        if key in visited:
            return
        visiting.add(key)
        for p in im[key].get('prerequisite_ids', []):
            visit(p)
        visiting.remove(key)
        visited.add(key)
    for key in im:
        visit(key)
    if focus_goal is not None and focus_goal not in gm:
        raise ValueError('Unknown focus goal')
    active_goals = {g['id']: g for g in goals if g.get('status') == 'active' or g['id'] == focus_goal}
    weights = {}
    for key, g in active_goals.items():
        # Null importance is not a personal preference: neutral fallback only.
        w = {'high': 3, 'medium': 2, 'low': 1}.get(g.get('importance'), 1)
        deadline = g.get('exact_date')
        if deadline and 0 <= (date.fromisoformat(deadline)-today).days <= 30:
            w += 1
        if g.get('gap') == 'large':
            w += 1
        weights[key] = w
    active = {q['knowledge_id']: q for q in questions if q['status'] in OPEN}
    excluded = set(assigned)
    excluded.update(q['knowledge_id'] for q in questions if q['id'] in excluded)
    covered = set()
    for question in questions:
        if question['status'] in OPEN or question['id'] in excluded:
            covered.update(question.get('canonical_ids', []))
    candidates, blocked, waiting = [], [], []
    for i in items:
        key = i['id']
        q = active.get(key)
        if q and q['status'] == 'awaiting_evaluation':
            waiting.append(q['id'])
            continue
        if i['status'] not in ('pending', 'review'):
            continue
        if q and (q['status'] == 'paused' or (q.get('resume_on') and q['resume_on'] > day)):
            continue
        if not q and key in excluded:
            continue
        scope = list(q.get('canonical_ids', [])) if q else list(i.get('canonical_ids', []))
        if not q and 'taxonomy' in i:
            if i['taxonomy']['entry_kind'] in ('container', 'resource') or i.get('requires_scope_review'):
                blocked.append(dict(knowledge_id=key, reason='catalogue_scope_requires_preparation'))
                continue
            scope = [c for c in scope if c not in covered]
            if not scope:
                continue
        links = [l for l in i.get('goal_links', []) if l['goal_id'] in active_goals]
        if focus_goal:
            links = [l for l in links if l['goal_id'] == focus_goal]
            if not links:
                continue
        if not links and not q:
            continue
        if i.get('priority') == 'low' and not focus_goal and not q:
            continue
        if i['status'] == 'review' and not i.get('due'):
            raise ValueError('Review item missing due date')
        if i.get('due'):
            date.fromisoformat(i['due'])
        if not q and i['status'] == 'review' and i['due'] > day:
            continue
        kind = q['kind'] if q else ('new' if i['status'] == 'pending' else 'review')
        missing = [p for p in i.get('prerequisite_ids', [])
                   if im[p].get('mastery', {}).get('apply', {}).get('state') != 'demonstrated']
        if missing and not q:
            blocked.append(dict(knowledge_id=key, prerequisite_ids=missing))
            continue
        contribution = {'high': 0, 'medium': 1, 'low': 2}
        links.sort(key=lambda l: (contribution.get(l.get('contribution'), 3), l['goal_id']))
        goal = links[0]['goal_id'] if links else 'continuation'
        weights.setdefault(goal, 1)
        weak = i.get('understanding') in ('needs_relearning', 'needs_prompt', 'needs_hint')
        if q:
            action = 'continue_question'
        elif kind == 'new':
            action = 'diagnose'
        elif weak:
            action = 'relearn'
        elif i.get('mastery', {}).get('apply', {}).get('state') != 'demonstrated':
            action = 'apply'
        else:
            action = 'delayed_review'
        estimated = i.get('estimated_minutes')
        if estimated is not None and (type(estimated) is not int or estimated <= 0):
            raise ValueError('Invalid estimated minutes')
        cost = estimated or (5 if energy == 'low' else 10)
        reasons = ['续接已派题' if q else '关联当前目标',
                   '已有薄弱证据，先补学再验证' if weak else '收集独立表现证据']
        if links:
            reasons.append('目标贡献：' + str(links[0].get('contribution', 'unknown')))
        if i.get('due'):
            reasons.append('到期日：' + i['due'])
        if estimated is None:
            reasons.append('时长为临时估计，完成后校准')
        foundational = any(key in other.get('prerequisite_ids', []) for other in items)
        rank = (0 if q else 1, contribution.get(links[0].get('contribution'), 3) if links else 3,
                0 if foundational else 1, 0 if weak else 1, i.get('due') or day, cost, key)
        candidates.append(dict(knowledge_id=key, question_id=q['id'] if q else None,
                               goal_id=goal, kind=kind, action=action, canonical_ids=scope, estimated_minutes=cost,
                               estimate_basis='item' if estimated else 'provisional_default',
                               reasons=reasons, _rank=rank))
    counts = dict(new=0, review=0)
    budgets = dict(new=new_limit, review=review_limit)
    used = {g: 0 for g in weights}
    selected, elapsed = [], 0
    while True:
        eligible = [c for c in candidates if counts[c['kind']] < budgets[c['kind']]]
        if minutes is not None:
            eligible = [c for c in eligible if elapsed+c['estimated_minutes'] <= minutes]
        if not eligible:
            break
        # Weighted fair allocation by planned minutes; resumptions first.
        chosen = min(eligible, key=lambda c: (c['_rank'][0], used[c['goal_id']]/weights[c['goal_id']], c['_rank'][1:]))
        candidates.remove(chosen)
        # Preserve existing open questions, but never newly test a shared scope twice.
        chosen_scope = set(chosen['canonical_ids'])
        for candidate in list(candidates):
            if candidate['question_id'] or not candidate['canonical_ids']:
                continue
            candidate['canonical_ids'] = [c for c in candidate['canonical_ids'] if c not in chosen_scope]
            if not candidate['canonical_ids']:
                candidates.remove(candidate)
        counts[chosen['kind']] += 1
        used[chosen['goal_id']] += chosen['estimated_minutes']
        elapsed += chosen['estimated_minutes']
        selected.append({k:v for k,v in chosen.items() if k != '_rank'})
    return dict(version=VERSION, day=day, actions=selected,
                awaiting_evaluation_ids=waiting, blocked=blocked,
                estimated_minutes=elapsed, goal_allocation_weights=weights,
                note='候选计划，不是已派题或已完成；未知重要性使用中性份额。')


def record_evidence(item, event):
    """Append one assessable learning event; never infer delayed/transfer evidence."""
    required = {'id', 'day', 'action', 'dimension', 'outcome', 'independent',
                'delayed', 'transfer', 'schedule_eligible', 'basis'}
    if not required <= event.keys() or not event['basis'] or not event['id']:
        raise ValueError('Evidence fields and basis required')
    date.fromisoformat(event['day'])
    if event['dimension'] not in ('recall', 'explain', 'apply'):
        raise ValueError('Unknown dimension')
    if event['outcome'] not in ('correct', 'hinted', 'wrong', 'skip'):
        raise ValueError('Unknown outcome')
    if event['action'] not in ('diagnose', 'relearn', 'practice', 'apply', 'delayed_review', 'continue_question'):
        raise ValueError('Unknown action')
    for field in ('independent', 'delayed', 'transfer', 'schedule_eligible'):
        if type(event[field]) is not bool:
            raise ValueError('Evidence flags must be boolean')
    allowed = {'id','day','action','dimension','outcome','independent','delayed','transfer','schedule_eligible','basis','quality','error_type','target_date','canonical_ids','weakness','actual_minutes'}
    event = {k:copy.deepcopy(v) for k,v in event.items() if k in allowed}
    if 'taxonomy' in item:
        scopes=event.get('canonical_ids', [])
        if not scopes or not set(scopes)<=set(item['taxonomy']['canonical_ids']):
            raise ValueError('Explicit tested canonical scope required')
    result = copy.deepcopy(item)
    history = result.setdefault('learning_events', [])
    old = next((e for e in history if e['id'] == event['id']), None)
    if old:
        if old != event:
            raise ValueError('Event ID reused; append correction')
        return result
    if history and event['day'] < max(e['day'] for e in history):
        raise ValueError('Late evidence requires chronological replay')
    effective = event['outcome']
    if effective == 'correct' and not event['independent']:
        effective = 'hinted'
    if event['schedule_eligible'] and event['action'] not in ('relearn', 'practice'):
        if result.get('last_review') != event['day']:
            result = grade(result, effective, event['day'],
                           quality=event.get('quality') or 'stable',
                           error_type=event.get('error_type') or 'unknown',
                           target_date=event.get('target_date'))
    if effective != 'skip':
        result['understanding'] = {'correct':'independent', 'hinted':'needs_prompt', 'wrong':'needs_relearning'}[effective]
        dimension = result.setdefault('mastery', {}).setdefault(event['dimension'], {})
        dimension.update(state={'correct':'demonstrated', 'hinted':'supported', 'wrong':'gap'}[effective],
                         evidence_id=event['id'], observed_on=event['day'])
        if event['delayed'] and event['independent']:
            dimension['delayed_evidence_id'] = event['id']
        if event['transfer'] and event['independent']:
            dimension['transfer_evidence_id'] = event['id']
    result.setdefault('learning_events', []).append(copy.deepcopy(event))
    for position, scope in enumerate(event.get('canonical_ids', []), 1):
        result.setdefault('diagnostic_evidence', []).append(dict(
            attempt_id=event['id'], canonical_id=scope, position=position,
            recorded_result=effective, answered_on=event['day'], independent=event['independent'],
            delayed=event['delayed'], mapping_status='mapped', basis=event['basis'],
            long_term_verified=False))
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--day', required=True)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--new-limit', type=int, default=CONFIG['new_limit'])
    p.add_argument('--review-limit', type=int, default=CONFIG['review_limit'])
    p.add_argument('--minutes', type=int)
    p.add_argument('--focus-goal')
    p.add_argument('--energy', choices=['low','normal','high'], default='normal')
    a = p.parse_args(argv)
    def read(path):
        return json.loads((a.root/path).read_text(encoding='utf-8'))
    items = read('knowledge/review-plans/queue.json')
    for i in items:
        path = a.root/'knowledge/items'/f"{i['id']}.json"
        if path.exists():
            detail = json.loads(path.read_text(encoding='utf-8'))
            # Queue owns scheduling; items own content and evidence.
            for key in ('goal_links','capability_ids','prerequisite_ids','mastery','estimated_minutes'):
                if key in detail:
                    i[key] = detail[key]
    qs = [] # Questions and assigned IDs live only in the current conversation.
    assigned = []
    from catalogue import load_context
    items, qs = load_context(a.root, items, qs)
    print(json.dumps(plan_actions(items, qs, read('goals/initial.json')['goals'], a.day,
                                 assigned, a.new_limit, a.review_limit, a.minutes,
                                 a.focus_goal, a.energy), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
