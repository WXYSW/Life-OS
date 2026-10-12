"""Knowledge lifecycle v1. Pure transitions; repository writes are explicit and local.
Life records/reports are outside this module's write scope.
"""
import argparse
import copy
import json
from collections import Counter
from datetime import date
from pathlib import Path
from review import grade

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'lifecycle-v1'
MATCHES = {'direct', 'prerequisite', 'related', 'uncertain', 'unrelated'}
CLOSED_GOALS = {'completed', 'cancelled', 'archived'}
SCHEDULE_FIELDS = ('status','stage','due','last_review','review_phase','consolidation_passes',
                   'long_interval_passes','recent_review_outcomes','scheduled_interval_days',
                   'actual_gap_days','schedule_reason','rule_version','pre_lapse_stage')
EVIDENCE_FIELDS = {'id','day','action','dimension','outcome','independent','delayed','transfer',
                   'schedule_eligible','basis','quality','error_type','weakness','lookup_used','target_date'}

def check_day(day):
    date.fromisoformat(day)

def goal_map(goals):
    result = {g['id']:g for g in goals}
    if len(result) != len(goals): raise ValueError('Duplicate goal IDs')
    return result

def classify(item, goals):
    """Missing or uncertain matches are never interpreted as unrelated."""
    gm = goal_map(goals)
    links = {l['goal_id']:l for l in item.get('goal_links', [])}
    active, future, unresolved = [], [], []
    for key, g in gm.items():
        if g['status'] in CLOSED_GOALS: continue
        link = links.get(key)
        outdated = bool(g.get('syllabus_ids') and link and link.get('syllabus_id') not in g['syllabus_ids'])
        if not link or outdated or link.get('relation') == 'uncertain' or link.get('applicability') == 'pending':
            unresolved.append(key)
        elif link.get('relation') in ('direct','prerequisite','related'):
            (active if g['status'] == 'active' else future).append(key)
    if item['availability'] == 'archived': route = 'archived'
    elif item['assessment'] == 'untested': route = 'intake'
    elif active:
        from review_engine import formal_review_ready
        if item.get('verification',{}).get('status')!='verified':route='verification_pending'
        elif not formal_review_ready(item):route='assessment_pending'
        else:route='review'
    elif unresolved: route = 'classification_pending'
    elif future: route = 'retained'
    elif item.get('retention_choice') == 'interest': route = 'retained'
    else: route = 'decision_required'
    return dict(route=route, active_goal_ids=sorted(active), future_goal_ids=sorted(future),
                unresolved_goal_ids=sorted(unresolved))

def refresh(items, goals, day):
    check_day(day)
    result = copy.deepcopy(items)
    for i in result:
        i['routing'] = classify(i, goals)
        i['routing_checked_on'] = day
        from review_engine import memory_snapshot
        i['memory']=memory_snapshot(i,day)
    return result

def create_intake(knowledge_id, title, source_ids, day, *, content=None):
    check_day(day)
    if not knowledge_id or not title or not source_ids: raise ValueError('ID, title and source required')
    if not knowledge_id.startswith('KP-') or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in knowledge_id):raise ValueError('Use a stable KP- identifier')
    return dict(id=knowledge_id, record_type='knowledge', title=title, content=content,
                source_ids=list(dict.fromkeys(source_ids)), source_item_ids=[],
                created_on=day, verification={'status':'needs_validation','basis':None},
                assessment='untested', availability='active', goal_links=[],
                evidence=[], mastery={}, schedule={'status':'pending','stage':-1,'due':None},
                routing={'route':'intake','active_goal_ids':[], 'future_goal_ids':[], 'unresolved_goal_ids':[]},
                lifecycle_version=VERSION)

def verify_content(item, basis, day):
    check_day(day)
    if not isinstance(basis,str) or not basis.strip(): raise ValueError('Verification source/basis required')
    result=copy.deepcopy(item)
    result['verification']={'status':'verified','basis':basis,'checked_on':day}
    return result

def set_match(item, goals, goal_id, relation, day, *, basis, syllabus_id=None,
              section_ids=(), importance=None, applicability='confirmed', mastery_requirement=None, requirement_basis=None):
    check_day(day);gm=goal_map(goals)
    if goal_id not in gm or relation not in MATCHES: raise ValueError('Invalid goal or relation')
    if not basis or importance not in (None,'high','medium','low'): raise ValueError('Match basis/importance invalid')
    if applicability not in ('confirmed','pending'): raise ValueError('Invalid applicability')
    from review_engine import REQUIREMENTS
    if mastery_requirement is not None and (mastery_requirement not in REQUIREMENTS or not requirement_basis):raise ValueError('Mastery requirement needs a valid level and basis')
    if relation in ('direct','prerequisite','related') and (not syllabus_id or not section_ids):
        raise ValueError('Positive matches require a versioned outline and sections')
    result=copy.deepcopy(item)
    result['goal_links']=[l for l in result.get('goal_links',[]) if l['goal_id']!=goal_id]
    result['goal_links'].append(dict(goal_id=goal_id,relation=relation,basis=basis,
                                    syllabus_id=syllabus_id,section_ids=list(section_ids),
                                    importance=importance,applicability=applicability,checked_on=day,
                                    relevance={'direct':'required','prerequisite':'prerequisite','related':'related','uncertain':'uncertain','unrelated':'unrelated'}[relation],
                                    mastery_requirement=mastery_requirement,requirement_basis=requirement_basis))
    return refresh([result],goals,day)[0]

def complete_goal(items, goals, goal_id, day, *, status='completed'):
    """Change goal status and recheck ALL shared references; no schedule mutation."""
    check_day(day)
    if status not in ('completed','cancelled','archived'): raise ValueError('Invalid terminal status')
    gs=copy.deepcopy(goals);gm=goal_map(gs)
    if goal_id not in gm: raise ValueError('Missing goal')
    gm[goal_id].update(status=status,closed_on=day)
    result=refresh(items,gs,day)
    affected=[i['id'] for i in result if any(l['goal_id']==goal_id for l in i.get('goal_links',[]))]
    return dict(items=result,goals=gs,affected_ids=affected,
                decisions=[i['id'] for i in result if i['id'] in affected and i['routing']['route']=='decision_required'])

def decide(item, goals, choice, day, *, reason):
    check_day(day)
    if not reason: raise ValueError('Decision reason required')
    if choice not in ('archive','restore','retain_interest'): raise ValueError('Deletion requires a separate reviewed file plan')
    result=copy.deepcopy(item)
    if choice=='archive':result['availability']='archived'
    elif choice=='restore':result['availability']='active'
    else:result['retention_choice']='interest'
    result.setdefault('lifecycle_decisions',[]).append(dict(day=day,choice=choice,reason=reason))
    return refresh([result],goals,day)[0]

def deletion_proposal(item, items, goals):
    """Read-only scope for user confirmation. Never writes/deletes automatically."""
    routing=classify(item,goals)
    dependents=[i['id'] for i in items if item['id'] in i.get('prerequisite_ids',[])]
    return dict(knowledge_id=item['id'],title=item['title'],requires_explicit_confirmation=True,
                active_goal_ids=routing['active_goal_ids'],future_goal_ids=routing['future_goal_ids'],
                unresolved_goal_ids=routing['unresolved_goal_ids'],dependent_ids=dependents,
                proposed_paths=['knowledge/items/'+item['id']+'.json','knowledge/review-plans/queue.json','knowledge/lifecycle/views.json','knowledge/catalog/nodes.json','knowledge/catalog/statistics.json'],
                proposed_removal=['knowledge record','compact evidence','review index entry','goal and catalogue references'],
                shared_source_item_ids=item.get('source_item_ids',[]),
                source_policy='inspect shared sources before removing specific knowledge evidence; never delete a shared source wholesale',
                excluded=['records/','reports/','Git history'],
                blocked=bool(routing['active_goal_ids'] or routing['future_goal_ids'] or routing['unresolved_goal_ids'] or dependents))

def evaluate(item, event, goals):
    """One scope per event. All persisted fields are compact learning evidence."""
    required={'id','day','action','dimension','outcome','independent','delayed','transfer','schedule_eligible','basis'}
    if not required<=event.keys() or not event['id'] or not event['basis']:raise ValueError('Incomplete evidence')
    check_day(event['day'])
    if event['dimension'] not in ('recall','explain','apply'):raise ValueError('Invalid dimension')
    if event['action'] not in ('diagnose','apply','delayed_review','practice','relearn','reinforce'):raise ValueError('Invalid action')
    if event['outcome'] not in ('correct','hinted','wrong','skip','unknown','partial'):raise ValueError('Invalid outcome')
    for key in ('independent','delayed','transfer'):
        if event[key] is not None and type(event[key]) is not bool:raise ValueError('Invalid evidence flag')
    if type(event['schedule_eligible']) is not bool:raise ValueError('Invalid schedule flag')
    if event.get('knowledge_id',item['id'])!=item['id']:raise ValueError('Scope mismatch')
    if 'canonical_ids' in event and event['canonical_ids']!=[item['id']]:raise ValueError('Evaluate each scope separately')
    e={k:copy.deepcopy(v) for k,v in event.items() if k in EVIDENCE_FIELDS}
    if e['action'] in ('reinforce','practice','relearn'):e['schedule_eligible']=False
    if any(isinstance(e.get(k),str) and len(e[k])>500 for k in ('basis','weakness')):raise ValueError('Use compact evidence, not transcripts')
    if e.get('quality','stable') not in ('effortful','stable','transfer'):raise ValueError('Invalid quality')
    if e.get('error_type','unknown') not in ('unknown','forgetting','conceptual','slip'):raise ValueError('Invalid error type')
    result=copy.deepcopy(item);history=result.setdefault('evidence',[])
    old=next((x for x in history if x['id']==e['id']),None)
    if old:
        if {k:v for k,v in old.items() if k not in ('actual_gap_days','scheduled_interval_before','schedule_changed','memory_effect')}!=e:raise ValueError('Event ID conflict; explicit correction/replay required')
        return result
    if history and e['day']<max(x['day'] for x in history):raise ValueError('Late evidence requires chronological replay')
    if item['availability']=='archived':raise ValueError('Restore knowledge before evaluating')
    if item['verification']['status']!='verified':raise ValueError('Verify content before evaluating')
    effective=e['outcome']
    if effective=='correct' and (e['independent'] is False or e.get('lookup_used') is True):effective='hinted'
    if effective!='skip' and e['action'] not in ('practice','relearn','reinforce'):
        result['assessment']='tested'
    eligible=(e['schedule_eligible'] and e['action'] not in ('practice','relearn','reinforce')
              and effective in ('correct','hinted','wrong')
              and not (effective=='correct' and e['independent'] is None))
    exposed_today=any(x['day']==e['day'] and x.get('action') in ('practice','relearn','reinforce') for x in history)
    eligible=eligible and not exposed_today
    schedule=result['schedule']
    e['schedule_changed']=False
    e['memory_effect']='same_day_practice_exposure' if exposed_today else 'evidence_only'
    e['actual_gap_days']=(date.fromisoformat(e['day'])-date.fromisoformat(schedule['last_review'])).days if schedule.get('last_review') else None
    e['scheduled_interval_before']=schedule.get('scheduled_interval_days')
    if eligible and schedule.get('last_review')!=e['day']:
        # The same ladder applies even when classification is pending; route controls dispatch.
        schedule=grade(schedule,effective,e['day'],quality=e.get('quality','stable'),error_type=e.get('error_type','unknown'),target_date=e.get('target_date'))
        result['schedule']=schedule
        e['schedule_changed']=True
        e['memory_effect']='formal_ladder_update'
    if effective!='skip':
        state={'correct':'demonstrated' if e['independent'] is True else 'unverified',
               'hinted':'supported','wrong':'gap','unknown':'unknown','partial':'partial'}[effective]
        dim=result.setdefault('mastery',{}).setdefault(e['dimension'],{})
        dim.update(state=state,evidence_id=e['id'],observed_on=e['day'])
        if effective=='correct' and e['independent'] is True and e['delayed'] is True and e['schedule_changed']:
            dim['delayed_evidence_id']=e['id']
        if effective=='correct' and e['independent'] is True and e['transfer'] is True:
            dim['transfer_evidence_id']=e['id']
        if e.get('weakness'):result['weakness']=e['weakness']
    history.append(e)
    return refresh([result],goals,e['day'])[0]

def plan(items,goals,day,*,mode='review',limit=None,minutes=None,focus_goal=None,assigned=(),energy='normal',profile='standard'):
    check_day(day)
    if mode in ('review','reinforce'):
        from review_engine import plan_round
        return plan_round(items,goals,day,mode=mode,profile=profile,limit=limit,minutes=minutes,focus_goal=focus_goal,assigned=assigned,energy=energy)
    if energy not in ('low','normal','high'):raise ValueError('Invalid energy')
    if mode not in ('review','diagnose'):raise ValueError('Choose review or diagnose explicitly')
    limit=(5 if mode=='review' else 2) if limit is None else limit
    if type(limit) is not int or limit<0:raise ValueError('Invalid limit')
    if minutes is not None and (type(minutes) is not int or minutes<0):raise ValueError('Invalid time budget')
    gm=goal_map(goals)
    if focus_goal is not None and focus_goal not in gm:raise ValueError('Missing focus goal')
    candidates=[];blocked=[];seen=set(assigned)
    for i in items:
        if i['id'] in seen or i['availability']=='archived':continue
        routing=classify(i,goals)
        if mode=='diagnose' and i['assessment']!='untested' and routing['route']!='assessment_pending':continue
        if mode=='review' and routing['route']!='review':continue
        if i['verification']['status']!='verified':
            blocked.append(dict(knowledge_id=i['id'],reason='verify_content_first'));continue
        links=[l for l in i.get('goal_links',[]) if l['goal_id'] in routing['active_goal_ids']]
        if focus_goal:
            links=[l for l in links if l['goal_id']==focus_goal]
            if not links:continue
        missing=[p for p in i.get('prerequisite_ids',[]) if not any(x['id']==p and x.get('mastery',{}).get('apply',{}).get('state')=='demonstrated' for x in items)]
        if missing and mode=='diagnose':
            blocked.append(dict(knowledge_id=i['id'],reason='prerequisites',ids=missing));continue
        sched=i['schedule']
        if mode=='review' and sched.get('due') and sched['due']>day:continue
        if mode=='review' and sched.get('last_review')==day:continue
        link=min(links,key=lambda l:({'direct':0,'prerequisite':1,'related':2}[l['relation']],{'high':0,'medium':1,'low':2}.get(l.get('importance'),3),l['goal_id'])) if links else None
        goal=link['goal_id'] if link else 'unclassified_intake'
        cost=i.get('estimated_minutes') or (5 if energy=='low' else 10)
        if type(cost) is not int or cost<=0:raise ValueError('Invalid estimated minutes')
        weak=any(d.get('state') in ('gap','supported','partial') for d in i.get('mastery',{}).values())
        candidates.append(dict(knowledge_id=i['id'],title=i['title'],goal_id=goal,
            action='diagnose' if mode=='diagnose' or not sched.get('due') else ('relearn_then_verify' if weak else 'delayed_review'),
            due=sched.get('due'),estimated_minutes=cost,
            _rank=({'direct':0,'prerequisite':1,'related':2}.get(link['relation'],3) if link else 2,
                   {'high':0,'medium':1,'low':2}.get(link.get('importance'),3) if link else 3,
                   0 if any(i['id'] in x.get('prerequisite_ids',[]) for x in items) else 1,
                   0 if weak else 1,sched.get('due') or day,i['id'])))
    selected=[];used=Counter();elapsed=0
    while candidates and len(selected)<limit:
        eligible=[c for c in candidates if minutes is None or elapsed+c['estimated_minutes']<=minutes]
        if not eligible:break
        def order(c):
            g=gm.get(c['goal_id'],{});weight={'high':3,'medium':2,'low':1}.get(g.get('importance'),1)
            if g.get('exact_date') and 0<=(date.fromisoformat(g['exact_date'])-date.fromisoformat(day)).days<=30:weight+=1
            if g.get('gap')=='large':weight+=1
            return (used[c['goal_id']]/weight,c['_rank'])
        c=min(eligible,key=order);candidates.remove(c);elapsed+=c['estimated_minutes'];used[c['goal_id']]+=c['estimated_minutes']
        selected.append({k:v for k,v in c.items() if k!='_rank'})
    return dict(version=VERSION,mode=mode,day=day,actions=selected,blocked=blocked,estimated_minutes=elapsed,
                note='仅候选，题目临时生成；诊断须用户主动启动。')

def load(root=ROOT):
    root=Path(root)
    items=[json.loads(p.read_text()) for p in sorted((root/'knowledge/items').glob('*.json'))]
    return [i for i in items if i.get('record_type')=='knowledge'],json.loads((root/'goals/initial.json').read_text())['goals']

def indexes(items,goals,day):
    current=refresh(items,goals,day)
    views={k:[] for k in ('intake','review','verification_pending','assessment_pending','archived','retained','classification_pending','decision_required')}
    for i in current:views[i['routing']['route']].append(i['id'])
    return dict(version=VERSION,as_of=day,views=views,counts={k:len(v) for k,v in views.items()},
                deletion_candidates=[deletion_proposal(i,current,goals) for i in current if i['routing']['route']=='decision_required'])

def validate(items,goals,syllabuses=()):
    gm=goal_map(goals);ids={i['id'] for i in items}
    if len(ids)!=len(items):raise ValueError('Duplicate knowledge IDs')
    sm={s['id']:s for s in syllabuses}
    for i in items:
        if not i['id'].startswith('KP-') or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in i['id']):raise ValueError('Invalid ID')
        if i['verification']['status'] not in ('verified','needs_validation'):raise ValueError('Invalid verification status')
        if i['verification']['status']=='verified' and not i['verification'].get('basis'):raise ValueError('Verification basis missing')
        if i['assessment'] not in ('untested','tested') or i['availability'] not in ('active','archived'):raise ValueError('Bad lifecycle')
        links=i.get('goal_links',[])
        if len({l['goal_id'] for l in links})!=len(links):raise ValueError('Duplicate goal links')
        for l in links:
            if l['goal_id'] not in gm or l['relation'] not in MATCHES:raise ValueError('Dangling goal')
            from review_engine import REQUIREMENTS
            expected_relevance={'direct':'required','prerequisite':'prerequisite','related':'related','uncertain':'uncertain','unrelated':'unrelated'}[l['relation']]
            if l.get('relevance',expected_relevance)!=expected_relevance:raise ValueError('Relevance contradicts goal relation')
            if l.get('mastery_requirement') is not None and (l['mastery_requirement'] not in REQUIREMENTS or not l.get('requirement_basis')):raise ValueError('Invalid mastery requirement/basis')
            if l['relation'] in ('direct','prerequisite','related'):
                syllabus=sm.get(l.get('syllabus_id'))
                if not syllabus or not l.get('section_ids') or not set(l['section_ids'])<={s['id'] for s in syllabus['sections']}:raise ValueError('Missing outline reference')
        if not set(i.get('prerequisite_ids',[]))<=ids:raise ValueError('Dangling prerequisite')
        if i['schedule'].get('due'):check_day(i['schedule']['due'])
        evidence=i.get('evidence',[])
        if len({e['id'] for e in evidence})!=len(evidence):raise ValueError('Duplicate evidence IDs')
        if i['assessment']=='untested' and i['schedule'].get('due'):raise ValueError('Untested knowledge has fabricated due date')
        if i.get('routing')!=classify(i,goals):raise ValueError('Stale routing; refresh before saving')
    visiting=set();visited=set();im={i['id']:i for i in items}
    def visit(key):
        if key in visiting:raise ValueError('Prerequisite cycle')
        if key in visited:return
        visiting.add(key)
        for p in im[key].get('prerequisite_ids',[]):visit(p)
        visiting.remove(key);visited.add(key)
    for key in ids:visit(key)
    return dict(knowledge_count=len(items),tested=sum(i['assessment']=='tested' for i in items),
                route_counts=dict(Counter(classify(i,goals)['route'] for i in items)))

def save(root,items,goals,day):
    """Explicit local commit staging. Only allowlisted knowledge/goal paths are written."""
    root=Path(root);items=refresh(items,goals,day)
    syllabuses=[json.loads(p.read_text()) for p in (root/'goals/syllabuses').glob('*.json')]
    validate(items,goals,syllabuses)
    def write(path,obj):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    for i in items:
        if '/' in i['id'] or '..' in i['id']:raise ValueError('Invalid ID')
    for i in items:write('knowledge/items/'+i['id']+'.json',i)
    doc=json.loads((root/'goals/initial.json').read_text());doc.update(goals=goals,updated_on=day);write('goals/initial.json',doc)
    write('knowledge/lifecycle/views.json',indexes(items,goals,day))
    write('knowledge/review-plans/queue.json',[dict(id=i['id'],title=i['title'],**i['schedule'],active_goal_ids=classify(i,goals)['active_goal_ids']) for i in items if classify(i,goals)['route']=='review'])
    # Derived catalogue nodes, statistics and the knowledge-only status are rebuilt together.
    node_path=root/'knowledge/catalog/nodes.json'
    node_doc=json.loads(node_path.read_text()) if node_path.exists() else {'version':'taxonomy-v2','nodes':[]}
    by_id={n['id']:n for n in node_doc['nodes']}
    for i in items:
        n=by_id.setdefault(i['id'],dict(id=i['id'],title=i['title'],level='concept',parent_id=i.get('taxonomy',{}).get('parent_id'),assessable=True))
        n.update(knowledge_id=i['id'],title=i['title'],source_ids=i.get('source_ids',[]),legacy_ids=i.get('source_item_ids',[]),
                 evidence_refs=[dict(knowledge_id=i['id'],evidence_id=e['id']) for e in i.get('evidence',[])])
    node_doc.update(version='taxonomy-v2',nodes=list(by_id.values()));write('knowledge/catalog/nodes.json',node_doc)
    from catalogue import statistics
    stats=statistics(root);write('knowledge/catalog/statistics.json',stats)
    views=indexes(items,goals,day)
    catalogue=['# 知识目录','','当前KP实体按范围独立管理。原资料映射见legacy-map.json，最新统计见statistics.json，状态视图见../lifecycle/views.json。','','| ID | 范围 | 状态 | 原资料ID |','|---|---|---|---|']
    catalogue += ['| '+i['id']+' | '+i['title'].replace('|','/')+' | '+i['routing']['route']+' | '+', '.join(i.get('source_item_ids',[]))+' |' for i in sorted(items,key=lambda x:x['id'])]
    (root/'knowledge/catalog/README.md').write_text('\n'.join(catalogue)+'\n')
    status='# 知识板块当前状态\n\n更新：'+day+'。由 lifecycle.py 生成；不包含生活数据。\n\n'
    status+='知识范围 '+str(len(items))+' 个；已测试 '+str(stats['canonical_scopes_with_diagnostic_evidence'])+' 个；长期验证 '+str(stats['canonical_long_term_verified'])+' 个。\n\n'
    labels={'intake':'待检测','review':'正式复习','verification_pending':'评分依据待核验','assessment_pending':'待补充检测','archived':'归档','retained':'保留','classification_pending':'分类待确认','decision_required':'待用户处理'}
    status+='\n'.join('- '+labels[k]+'：'+str(v) for k,v in views['counts'].items())+'\n\n正式复习仅含已核验、有有效测试证据及日期的知识；待核验和待补测单列。目标匹配不确定不等于无用。\n'
    status+='\n按标准范围统计，与旧资料条目数量不可直接比较。当前题目只在对话中生成，未答不计错。\n'
    (root/'state').mkdir(exist_ok=True);(root/'state/knowledge.md').write_text(status)



def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--day',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('views');sub.add_parser('validate')
    rp=sub.add_parser('recheck');rp.add_argument('--write',action='store_true')
    ip=sub.add_parser('intake');ip.add_argument('knowledge_id');ip.add_argument('--title',required=True);ip.add_argument('--source',required=True);ip.add_argument('--write',action='store_true')
    mp=sub.add_parser('match');mp.add_argument('knowledge_id');mp.add_argument('goal_id');mp.add_argument('relation',choices=sorted(MATCHES));mp.add_argument('--basis',required=True);mp.add_argument('--syllabus');mp.add_argument('--section',action='append',default=[]);mp.add_argument('--importance',choices=['high','medium','low']);mp.add_argument('--applicability',choices=['confirmed','pending'],default='confirmed');mp.add_argument('--mastery-requirement',choices=['recognition','understanding','application','integration']);mp.add_argument('--requirement-basis');mp.add_argument('--write',action='store_true')
    pp=sub.add_parser('plan');pp.add_argument('--mode',choices=['review','diagnose','reinforce'],default='review');pp.add_argument('--limit',type=int);pp.add_argument('--minutes',type=int);pp.add_argument('--focus-goal');pp.add_argument('--profile',choices=['light','standard','deep'],default='standard');pp.add_argument('--assigned',action='append',default=[])
    cp=sub.add_parser('close-goal');cp.add_argument('goal_id');cp.add_argument('--status',choices=sorted(CLOSED_GOALS),default='completed');cp.add_argument('--write',action='store_true')
    dp=sub.add_parser('decide');dp.add_argument('knowledge_id');dp.add_argument('choice',choices=['archive','restore','retain_interest','delete_proposal']);dp.add_argument('--reason',default='用户明确选择');dp.add_argument('--write',action='store_true')
    vp=sub.add_parser('verify');vp.add_argument('knowledge_id');vp.add_argument('--basis',required=True);vp.add_argument('--write',action='store_true')
    ep=sub.add_parser('evaluate');ep.add_argument('knowledge_id');ep.add_argument('event_file',type=Path);ep.add_argument('--write',action='store_true')
    a=p.parse_args(argv);items,goals=load(a.root)
    if a.command=='views':result=indexes(items,goals,a.day)
    elif a.command=='validate':result=validate(items,goals,[json.loads(x.read_text()) for x in (a.root/'goals/syllabuses').glob('*.json')])
    elif a.command=='plan':result=plan(items,goals,a.day,mode=a.mode,limit=a.limit,minutes=a.minutes,focus_goal=a.focus_goal,profile=a.profile,assigned=a.assigned)
    elif a.command=='recheck':
        result=indexes(items,goals,a.day)
        if a.write:save(a.root,items,goals,a.day)
    elif a.command=='intake':
        if (a.root/'knowledge/items'/f'{a.knowledge_id}.json').exists():raise ValueError('ID already exists; merge source into existing knowledge')
        if any(i['title'].strip().casefold()==a.title.strip().casefold() for i in items):raise ValueError('Title already exists; reuse stable ID')
        result=create_intake(a.knowledge_id,a.title,[a.source],a.day)
        if a.write:save(a.root,items+[result],goals,a.day)
    elif a.command=='close-goal':
        result=complete_goal(items,goals,a.goal_id,a.day,status=a.status)
        if a.write:save(a.root,result['items'],result['goals'],a.day)
    else:
        im={i['id']:i for i in items}
        if a.knowledge_id not in im:raise ValueError('Missing knowledge ID')
        if a.command=='decide' and a.choice=='delete_proposal':
            if a.write:raise ValueError('A deletion proposal is read-only; confirm a concrete file change separately')
            result=deletion_proposal(im[a.knowledge_id],items,goals)
        else:
            if a.command=='match':result=set_match(im[a.knowledge_id],goals,a.goal_id,a.relation,a.day,basis=a.basis,syllabus_id=a.syllabus,section_ids=a.section,importance=a.importance,applicability=a.applicability,mastery_requirement=a.mastery_requirement,requirement_basis=a.requirement_basis)
            elif a.command=='verify':result=verify_content(im[a.knowledge_id],a.basis,a.day)
            elif a.command=='evaluate':
                event=json.loads(a.event_file.read_text())
                if event['day']!=a.day:raise ValueError('Event date mismatch')
                result=evaluate(im[a.knowledge_id],event,goals)
            else:result=decide(im[a.knowledge_id],goals,a.choice,a.day,reason=a.reason)
            if a.write:save(a.root,[result if i['id']==result['id'] else i for i in items],goals,a.day)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
