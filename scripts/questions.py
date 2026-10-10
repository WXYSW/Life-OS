"""Persistent-question lifecycle as pure functions; caller commits returned state."""
import copy
from datetime import date, timedelta
from review import CONFIG, select

OPEN = {'unanswered', 'partial', 'awaiting_evaluation', 'deferred', 'paused'}


def validate(questions):
    if len({q['id'] for q in questions}) != len(questions):
        raise ValueError('Duplicate question IDs')
    if any(q['status'] not in OPEN | {'evaluated', 'cancelled'} for q in questions):
        raise ValueError('Unknown question status')
    active = [q['knowledge_id'] for q in questions if q['status'] in OPEN]
    if len(active) != len(set(active)):
        raise ValueError('More than one open question for the same knowledge')


def issue(questions, question_id, knowledge_id, kind, prompt, day, priority='normal',
          evaluation_criteria=(), prompt_version=1):
    date.fromisoformat(day)
    validate(questions)
    if not question_id or not prompt or kind not in ('new', 'review'):
        raise ValueError('Question ID, prompt and valid kind required')
    if any(q['id'] == question_id for q in questions):
        raise ValueError('Question ID already exists')
    if any(q['knowledge_id'] == knowledge_id and q['status'] in OPEN for q in questions):
        raise ValueError('Continue the existing open question')
    result = copy.deepcopy(questions)
    result.append(dict(id=question_id, knowledge_id=knowledge_id, kind=kind, prompt=prompt,
                       prompt_version=prompt_version, evaluation_criteria=list(evaluation_criteria),
                       priority=priority, issued_on=day, status='unanswered', resume_on=None,
                       answer_fragments=[], events=[dict(type='issued', day=day)]))
    return result


def change(questions, question_id, action, day, event_id, text=None, complete=False):
    date.fromisoformat(day)
    validate(questions)
    if not event_id:
        raise ValueError('Stable event ID required for retry safety')
    result = copy.deepcopy(questions)
    q = next((q for q in result if q['id'] == question_id), None)
    if q is None:
        raise ValueError('Unknown question')
    event = dict(id=event_id, type=action, day=day, text=text, complete=complete)
    old_event = next((e for e in q['events'] if e.get('id') == event_id), None)
    if old_event:
        if old_event != event:
            raise ValueError('Event ID reused with different content; append a revision')
        return result
    if q['status'] in ('evaluated', 'cancelled'):
        raise ValueError('Closed question; corrections require revision')
    if day < q['issued_on']:
        raise ValueError('Event predates question')
    if action == 'answer':
        if not text:
            raise ValueError('Answer text required')
        q['answer_fragments'].append(dict(id=event_id, day=day, text=text))
        q['status'] = 'awaiting_evaluation' if complete else 'partial'
        q['resume_on'] = None
    elif action == 'evaluate':
        if q['status'] != 'awaiting_evaluation':
            raise ValueError('Only an assessable answer can be evaluated')
        q['status'] = 'evaluated'
    elif action == 'skip':
        q['status'] = 'deferred'
        q['resume_on'] = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    elif action == 'pause':
        q['status'] = 'paused'
        q['resume_on'] = None
    elif action == 'resume':
        q['status'] = 'partial' if q['answer_fragments'] else 'unanswered'
        q['resume_on'] = None
    elif action == 'cancel':
        q['status'] = 'cancelled'
    else:
        raise ValueError('Unknown action')
    q['events'].append(event)
    return result


def plan(items, questions, day, assigned=(), new_limit=None, review_limit=None):
    date.fromisoformat(day)
    validate(questions)
    new_limit = CONFIG['new_limit'] if new_limit is None else new_limit
    review_limit = CONFIG['review_limit'] if review_limit is None else review_limit
    if min(new_limit, review_limit) < 0:
        raise ValueError('Limits must be nonnegative')
    item_map = {x['id']: x for x in items}
    if len(item_map) != len(items):
        raise ValueError('Duplicate knowledge IDs')
    if any(q['knowledge_id'] not in item_map for q in questions):
        raise ValueError('Question references missing knowledge')
    active = [q for q in questions if q['status'] in OPEN]
    waiting = [q['id'] for q in active if q['status'] == 'awaiting_evaluation']
    resumable = [q for q in active if q['status'] not in ('paused', 'awaiting_evaluation')
                 and (not q.get('resume_on') or q['resume_on'] <= day)
                 and item_map[q['knowledge_id']]['status'] not in ('paused', 'reference', 'needs_validation')]
    resumable.sort(key=lambda q: (0 if item_map[q['knowledge_id']].get('priority') == 'core' else 1,
                                 q['issued_on'], q['id']))
    resumed, counts = [], dict(new=0, review=0)
    limits = dict(new=new_limit, review=review_limit)
    for q in resumable:
        if counts[q['kind']] < limits[q['kind']]:
            resumed.append(q['id'])
            counts[q['kind']] += 1
    excluded = set(assigned) | {q['knowledge_id'] for q in active}
    selected = select(items, day, excluded, new_limit-counts['new'], review_limit-counts['review'])
    return dict(day=day, resume_question_ids=resumed, awaiting_evaluation_ids=waiting,
                new_ids=selected['new_ids'], review_ids=selected['review_ids'],
                remaining_open_count=len(active)-len(resumed)-len(waiting))
