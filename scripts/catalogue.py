"""Canonical scope overlay and reproducible statistics; no writes by default."""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPEN={'unanswered','partial','awaiting_evaluation','deferred','paused'}

def load_context(root, items, questions):
    root=Path(root)
    path=root/'knowledge/catalog/legacy-map.json'
    if not path.exists():
        return copy.deepcopy(items), copy.deepcopy(questions)
    read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    maps={m['legacy_id']:m for m in read('knowledge/catalog/legacy-map.json')['entries']}
    nodes={n['id']:n for n in read('knowledge/catalog/nodes.json')['nodes']}
    qmaps={}
    evidence=[dict(e, legacy_id=m['legacy_id']) for m in read('knowledge/catalog/legacy-map.json')['entries'] for e in read('knowledge/items/'+m['legacy_id']+'.json').get('diagnostic_evidence', [])]
    tested={e['canonical_id'] for e in evidence if e.get('canonical_id') and e.get('mapping_status')=='mapped'}
    scopes={}
    for e in evidence:
        if e.get('canonical_id'):
            scopes.setdefault(e['legacy_id'],set()).add(e['canonical_id'])
    output=copy.deepcopy(items)
    for i in output:
        m=maps.get(i['id'])
        if not m:continue
        i['taxonomy']=m
        valid=[c for c in m['canonical_ids'] if nodes[c].get('assessable')]
        if i['status']=='review':
            i['canonical_ids']=sorted(scopes.get(i['id'],set()))
        else:
            i['canonical_ids']=[c for c in valid if c not in tested]
        i['requires_scope_review']=not i['canonical_ids']
    qs=copy.deepcopy(questions)
    for q in qs:
        if 'canonical_ids' not in q:
            q['canonical_ids']=qmaps.get(q['id'],{}).get('canonical_ids',[])
    return output,qs


def statistics(root=ROOT):
    from lifecycle import load, classify
    from review_engine import memory_snapshot
    root=Path(root)
    items,goals=load(root)
    sources=[json.loads(p.read_text()) for p in (root/'knowledge/items').glob('*.json')]
    sources=[i for i in sources if i.get('record_type')=='legacy_source']
    evidence=[e for i in items for e in i.get('evidence',[])]
    observed=[i for i in items if i['assessment']=='tested']
    assessed_legacy={e['legacy_source_id'] for e in evidence if e.get('legacy_source_id')}
    archived_legacy={i['id'] for i in sources if i.get('status')=='paused'}
    return dict(version='taxonomy-v2',source_entries=len(sources),
                canonical_assessable_scopes=len(items),canonical_scopes_with_diagnostic_evidence=len(observed),
                canonical_long_term_verified=sum(memory_snapshot(i, i.get('routing_checked_on') or '2026-10-11')['long_term_verified'] for i in items),
                unique_attempts=len({e.get('legacy_attempt_id',e['id']) for e in evidence}),
                historical_unique_attempts=len({e['legacy_attempt_id'] for e in evidence if e.get('legacy_attempt_id')}),
                mapped_subanswer_evidence=len(evidence),legacy_entries_with_attempts=len(assessed_legacy),
                archived_legacy_entries=len(archived_legacy),active_legacy_entries_with_attempts=len(assessed_legacy-archived_legacy),
                lifecycle_counts=dict(Counter(classify(i,goals)['route'] for i in items)),
                verification_counts=dict(Counter(i['verification']['status'] for i in items)),
                evidence_scope='knowledge/items/KP-*.json evidence; legacy sources are historical snapshots',
                coverage_complete=False)


def validate_catalogue(root=ROOT):
    from lifecycle import load, validate, classify
    root=Path(root);read=lambda p:json.loads((root/p).read_text())
    items,goals=load(root)
    validate(items,goals,[json.loads(p.read_text()) for p in (root/'goals/syllabuses').glob('*.json')])
    entries=read('knowledge/catalog/legacy-map.json')['entries'];ns=read('knowledge/catalog/nodes.json')['nodes']
    nodes={n['id']:n for n in ns}
    if len(nodes)!=len(ns):raise ValueError('Duplicate canonical IDs')
    for n in ns:
        seen=set();cur=n
        while cur.get('parent_id'):
            if cur['id'] in seen:raise ValueError('Hierarchy cycle')
            seen.add(cur['id']);cur=nodes[cur['parent_id']]
    ids={i['id'] for i in items}
    if {n['id'] for n in ns if n.get('assessable')}!=ids:raise ValueError('Canonical catalogue mismatch')
    for m in entries:
        if not m['canonical_ids'] or any(c not in nodes for c in m['canonical_ids']):raise ValueError('Missing legacy node')
        item=read('knowledge/items/'+m['legacy_id']+'.json')
        if item.get('taxonomy')!=m:raise ValueError('Legacy taxonomy drift')
    expected=[dict(id=i['id'],title=i['title'],**i['schedule'],active_goal_ids=classify(i,goals)['active_goal_ids']) for i in items if classify(i,goals)['route']=='review']
    queue=read('knowledge/review-plans/queue.json')
    if {i['id']:i for i in queue}!={i['id']:i for i in expected}:raise ValueError('Derived queue drift')
    return statistics(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--validate',action='store_true');a=p.parse_args()
    print(json.dumps(validate_catalogue(a.root) if a.validate else statistics(a.root),ensure_ascii=False,indent=2))
