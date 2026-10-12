"""Transparent review decisions. Cold-start ladder stays authoritative.
Risk levels and observed stability are evidence summaries, never calibrated probabilities.
"""
from collections import Counter
from datetime import date
from statistics import median
from review import CONFIG

VERSION = 'review-v3'
REQUIREMENTS = {'recognition','understanding','application','integration'}
FORMAL_ACTIONS = {'diagnose','apply','delayed_review'}
PROFILES = {'light': {'max_scopes':3}, 'standard': {'max_scopes':5}, 'deep': {'max_scopes':8}}


def assessed_events(item, day=None):
    """Compact observed tests, excluding skip, teaching and targeted practice."""
    out=[]
    for e in item.get('evidence',[]):
        if e.get('action') not in FORMAL_ACTIONS or e.get('outcome') not in ('correct','wrong','hinted','partial','unknown'):
            continue
        if not e.get('id') or not e.get('basis') or not e.get('day'):continue
        date.fromisoformat(e['day'])
        if day and e['day']>day:continue
        out.append(e)
    return sorted(out,key=lambda e:e['day']) # Stable sort preserves within-day observation order.


def formal_review_ready(item):
    s=item.get('schedule',{})
    return (item.get('assessment')=='tested' and item.get('verification',{}).get('status')=='verified'
            and bool(assessed_events(item)) and s.get('status')=='review' and bool(s.get('due'))
            and bool(s.get('last_review')))


def effective_outcome(e):
    if e.get('outcome')=='correct' and (e.get('independent') is False or e.get('lookup_used') is True):return 'hinted'
    return e.get('outcome')


def interval_successes(item, day=None):
    """Distinct-day, full-gap, stable independent successes after latest formal lapse.
    Legacy unknown evidence remains unknown; same-day extra answers cannot add passes.
    """
    passes=[];seen=set()
    for e in assessed_events(item,day):
        if not e.get('schedule_eligible') or e.get('schedule_changed') is False:continue
        if e['day'] in seen:continue
        seen.add(e['day'])
        outcome=effective_outcome(e)
        if outcome in ('wrong','hinted'):
            passes=[];continue
        gap=e.get('actual_gap_days');interval=e.get('scheduled_interval_before')
        if (outcome=='correct' and e.get('independent') is True and e.get('lookup_used') is not True
                and e.get('quality') in ('stable','transfer') and isinstance(gap,(int,float))
                and isinstance(interval,(int,float)) and gap>=max(1,interval)):
            passes.append(e)
    return passes


def memory_snapshot(item, day):
    today=date.fromisoformat(day);s=item.get('schedule',{});events=assessed_events(item,day)
    latest=events[-1] if events else None
    last=date.fromisoformat(s['last_review']) if s.get('last_review') else None
    gap=(today-last).days if last else None
    due=date.fromisoformat(s['due']) if s.get('due') else None
    overdue=max(0,(today-due).days) if due else None
    due_now=due is not None and due<=today
    passes=interval_successes(item,day)
    long_passes=[e for e in passes if e['actual_gap_days']>=30]
    stable_passes=[e for e in passes if e['actual_gap_days']>=7]
    latest_outcome=effective_outcome(latest) if latest else None
    effortful=bool(latest and latest_outcome=='correct' and latest.get('quality')=='effortful')
    if effortful:state='consolidation'
    elif latest_outcome in ('wrong','hinted','partial','unknown'):state='consolidation'
    elif len(long_passes)>=2:state='long_term'
    elif len(stable_passes)>=2:state='stable_retention'
    elif latest_outcome=='correct' and latest.get('independent') is True:state='short_term'
    else:state='unverified'
    interval=s.get('scheduled_interval_days')
    weak=effortful or latest_outcome in ('wrong','hinted','partial','unknown')
    failure=latest_outcome in ('wrong','hinted')
    error_type=latest.get('error_type','unknown') if latest else 'unknown'
    critical_failure=latest_outcome=='hinted' or (latest_outcome=='wrong' and error_type!='slip')
    reasons=[]
    if due_now:
        reasons.append('已逾期'+str(overdue)+'天' if overdue else '今日到期')
    if failure:
        reasons.append('最近测试有错误或依赖提示，需独立验证')
        if error_type=='slip':reasons.append('错误有明确局部失误依据，不等同严重遗忘')
        elif error_type=='forgetting':reasons.append('错误类型为记忆遗忘')
        elif error_type=='conceptual':reasons.append('错误类型为理解或概念缺口')
    elif effortful:reasons.append('最近独立答对仍费力，优先巩固')
    elif weak:reasons.append('最近测试证据仍不完整')
    if due_now and (critical_failure or (overdue and overdue>=max(1,interval or 1))):risk='high'
    elif due_now:risk='due'
    elif not due:risk='unknown'
    elif weak:risk='watch'
    else:risk='low'
    independent=[e for e in events if effective_outcome(e)=='correct' and e.get('independent') is True]
    independent_gap=(today-date.fromisoformat(independent[-1]['day'])).days if independent else None
    long_unvalidated=due_now and gap is not None and gap>=30 and (independent_gap is None or independent_gap>=30)
    if long_unvalidated:reasons.append('长期缺少新的独立验证')
    return dict(as_of=day,model='ladder-v2-cold-start',state=state,risk=risk,
                risk_basis='ordinal_due_and_observed_performance_not_probability',
                observed_stability_days=median(e['actual_gap_days'] for e in passes) if passes else None,
                stability_basis='median_full_gap_independent_stable_passes_since_lapse',
                supporting_passes=len(passes),long_interval_successes=len(long_passes),
                long_term_verified=state=='long_term',elapsed_days=gap,overdue_days=overdue,
                next_review=s.get('due'),due_now=due_now,long_unvalidated=bool(long_unvalidated),
                latest_result=latest_outcome,critical_failure=critical_failure,effortful=effortful,error_type=error_type,reasons=reasons)


def requirement_gap(item, link, day):
    """Goal-specific requirements, never infer a higher level from a recall result."""
    required=link.get('mastery_requirement')
    if required is not None and required not in REQUIREMENTS:raise ValueError('Invalid mastery requirement')
    if required is None:return dict(required=None,current=None,status='unknown',reason='目标掌握要求待明确')
    dim={'recognition':'recall','understanding':'explain','application':'apply','integration':'apply'}[required]
    ev=[e for e in item.get('evidence',[]) if e.get('dimension')==dim and e.get('day','9999')<=day
        and e.get('outcome') in ('correct','wrong','hinted','partial','unknown')
        and e.get('action') in FORMAL_ACTIONS|{'reinforce','practice'}]
    ev.sort(key=lambda e:e['day'])
    if not ev:return dict(required=required,current=None,status='unknown',reason='缺少对应能力维度的测试证据')
    last=ev[-1];outcome=effective_outcome(last)
    if outcome=='correct' and last.get('independent') is True:
        met=(required!='integration' or last.get('transfer') is True)
        return dict(required=required,current=required if met else 'application',status='met' if met else 'partial',
                    evidence_id=last['id'],reason='独立表现满足该目标层级' if met else '已有应用证据，缺少迁移整合证据')
    if outcome in ('wrong','hinted'):status='unmet'
    elif outcome=='partial':status='partial'
    else:status='unknown'
    return dict(required=required,current=None,status=status,evidence_id=last['id'],reason='最近对应表现仍有缺口或不确定')


def goal_demands(item, goals, day):
    from lifecycle import classify
    routing=classify(item,goals);active=set(routing['active_goal_ids']);gm={g['id']:g for g in goals}
    result=[]
    for link in item.get('goal_links',[]):
        if link['goal_id'] not in active:continue
        g=gm[link['goal_id']];deadline=g.get('exact_date')
        remaining=(date.fromisoformat(deadline)-date.fromisoformat(day)).days if deadline else None
        urgency='unknown' if remaining is None else ('date_passed' if remaining<0 else 'imminent' if remaining<=7 else 'near' if remaining<=30 else 'normal')
        result.append(dict(goal_id=g['id'],relevance=link.get('relevance') or {'direct':'required','prerequisite':'prerequisite','related':'related'}.get(link['relation']),
                           importance=link.get('importance'),goal_importance=g.get('importance'),deadline=deadline,
                           days_remaining=remaining,urgency=urgency,gap=requirement_gap(item,link,day)))
    return result


def _benefit(demand):
    return ({'required':0,'prerequisite':1,'related':2}.get(demand['relevance'],3),
            {'unmet':0,'partial':1,'unknown':2,'met':3}[demand['gap']['status']],
            {'high':0,'medium':1,'low':2}.get(demand['importance'],1),
            {'imminent':0,'near':1}.get(demand['urgency'],2),
            {'high':0,'medium':1,'low':2}.get(demand['goal_importance'],1))


def plan_round(items,goals,day,*,mode='review',profile='standard',limit=None,minutes=None,
               focus_goal=None,assigned=(),energy='normal'):
    from lifecycle import classify,goal_map
    date.fromisoformat(day);gm=goal_map(goals)
    if mode not in ('review','reinforce'):raise ValueError('Unknown review mode')
    if profile not in PROFILES or energy not in ('low','normal','high'):raise ValueError('Invalid round profile')
    configured=CONFIG.get('round_profiles',PROFILES)
    limit=configured.get(profile,PROFILES[profile])['max_scopes'] if limit is None else limit
    if type(limit) is not int or limit<0:raise ValueError('Invalid limit')
    if minutes is not None and (type(minutes) is not int or minutes<0):raise ValueError('Invalid minutes')
    if focus_goal is not None and focus_goal not in gm:raise ValueError('Missing focus goal')
    if len({i['id'] for i in items})!=len(items):raise ValueError('Duplicate knowledge IDs')
    excluded=set(assigned);candidates=[];blocked=[]
    for i in items:
        if i['id'] in excluded or i.get('availability')=='archived':continue
        routing=classify(i,goals)
        if not routing['active_goal_ids'] or i.get('assessment')!='tested':continue
        if i['verification']['status']!='verified':
            blocked.append(dict(knowledge_id=i['id'],reason='verify_content_first'));continue
        if not formal_review_ready(i):
            blocked.append(dict(knowledge_id=i['id'],reason='complete_diagnosis_first'));continue
        # Formal reviews never immediately re-test a scope already assessed today.
        if mode=='review' and (i['schedule'].get('last_review')==day or any(e.get('day')==day and e.get('action') in FORMAL_ACTIONS|{'reinforce','practice','relearn'} for e in i.get('evidence',[]))):continue
        demands=goal_demands(i,goals,day)
        if focus_goal:demands=[d for d in demands if d['goal_id']==focus_goal]
        if not demands:continue
        memory=memory_snapshot(i,day)
        if mode=='review' and not memory['due_now']:continue
        demand=min(demands,key=_benefit)
        dependent_ids=[x['id'] for x in items if i['id'] in x.get('prerequisite_ids',[]) and x.get('availability')!='archived'
                       and classify(x,goals)['active_goal_ids']]
        # A prerequisite only raises risk when actual application evidence is missing.
        application_gap=requirement_gap(i,dict(mastery_requirement='application'),day)
        blocking=bool(dependent_ids and application_gap['status']!='met')
        if mode=='reinforce':tier=3
        elif memory['due_now'] and (memory['critical_failure'] or blocking):tier=0
        elif memory['risk']=='high' or (memory['overdue_days'] or 0)>0 or memory['long_unvalidated'] or memory['effortful']:tier=1
        else:tier=2
        reasons=list(memory['reasons'])
        if blocking:reasons.append('是后续学习的前置知识，应用证据仍不足')
        reasons.append('目标关联：'+str(demand['relevance']))
        reasons.append(demand['gap']['reason'])
        if demand['urgency']=='imminent':reasons.append('明确目标日期在7天内')
        elif demand['urgency']=='near':reasons.append('明确目标日期在30天内')
        elif demand['urgency']=='date_passed':reasons.append('目标日期已过，目标状态待核对')
        if mode=='reinforce':reasons.append('用户主动选择目标强化，本轮不推进记忆阶梯')
        cost=i.get('estimated_minutes') or (5 if energy=='low' or profile=='light' else 10)
        if type(cost) is not int or cost<=0:raise ValueError('Invalid estimated minutes')
        required=demand['gap']['required']
        task='transfer_application' if required=='integration' else 'application' if required=='application' else 'explanation' if required=='understanding' else 'independent_retrieval'
        candidates.append(dict(knowledge_id=i['id'],title=i['title'],goal_id=demand['goal_id'],
            served_goal_ids=[d['goal_id'] for d in demands],goal_demands=demands,
            action='reinforce' if mode=='reinforce' else ('relearn_then_verify' if memory['state']=='consolidation' else 'delayed_review'),
            task_intent=task,question_count=None,schedule_eligible=mode=='review',due=i['schedule']['due'],
            estimated_minutes=cost,estimate_basis='item' if i.get('estimated_minutes') else 'provisional_default',
            priority_tier=tier,memory=memory,reasons=reasons,
            _benefit=_benefit(demand),_module=i.get('module_id') or i.get('subject_id') or i['id'],
            _urgent=demand['urgency']=='imminent' and demand['gap']['status'] in ('unmet','partial')))
    selected=[];goal_counts=Counter();module_counts=Counter();elapsed=0
    while candidates and len(selected)<limit:
        fits=[c for c in candidates if minutes is None or elapsed+c['estimated_minutes']<=minutes]
        if not fits:break
        tier=min(c['priority_tier'] for c in fits);same=[c for c in fits if c['priority_tier']==tier]
        urgent=[c for c in same if c['_urgent']]
        pool=urgent or same
        if urgent:chosen=min(pool,key=lambda c:(c['_benefit'],goal_counts[c['goal_id']],module_counts[c['_module']],c['due'],c['knowledge_id']))
        else:chosen=min(pool,key=lambda c:(goal_counts[c['goal_id']],module_counts[c['_module']],c['_benefit'],c['due'],c['estimated_minutes'],c['knowledge_id']))
        candidates.remove(chosen)
        chosen['reasons'].append('同风险层有明确临近目标缺口，允许集中安排' if urgent else '同风险层兼顾目标和知识类别')
        goal_counts[chosen['goal_id']]+=1;module_counts[chosen['_module']]+=1;elapsed+=chosen['estimated_minutes']
        selected.append({k:v for k,v in chosen.items() if not k.startswith('_')})
    return dict(version=VERSION,mode=mode,profile=profile,day=day,max_scopes=limit,actions=selected,
                blocked=blocked,estimated_minutes=elapsed,time_budget_minutes=minutes,
                scope_count=len(selected),question_count=None,remaining_candidates=len(candidates),
                note='一轮最多指定知识范围，不凑数；题数按评价需要临时决定。完成后读取最新状态重新规划。')
