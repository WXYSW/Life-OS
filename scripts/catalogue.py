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
    root=Path(root);read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    entries=read('knowledge/catalog/legacy-map.json')['entries']
    nodes=read('knowledge/catalog/nodes.json')['nodes']
    evidence=[dict(e, legacy_id=m['legacy_id']) for m in read('knowledge/catalog/legacy-map.json')['entries'] for e in read('knowledge/items/'+m['legacy_id']+'.json').get('diagnostic_evidence', [])]
    queue=read('knowledge/review-plans/queue.json')
    qs=[]
    leaves=[n for n in nodes if n.get('assessable')]
    observed={e['canonical_id'] for e in evidence if e.get('canonical_id')}
    assessed_legacy={e['legacy_id'] for e in evidence}
    archived={i['id'] for i in queue if i['status']=='paused' and i.get('archive',{}).get('kind')=='temporary'}
    return dict(version='taxonomy-v1',source_entries=len(entries),canonical_assessable_scopes=len(leaves),
                canonical_scopes_with_diagnostic_evidence=len(observed),
                canonical_long_term_verified=sum(n.get('long_term_verified') is True for n in leaves),
                unique_attempts=len({e['attempt_id'] for e in evidence}),mapped_subanswer_evidence=sum(e.get('canonical_id') is not None for e in evidence),
                legacy_entries_with_attempts=len(assessed_legacy),archived_legacy_entries=len(archived),
                active_legacy_entries_with_attempts=len(assessed_legacy-archived),
                queue_status_counts=dict(Counter(i['status'] for i in queue)),
                question_status_counts=dict(Counter(q['status'] for q in qs)),
                entry_kind_counts=dict(Counter(m['entry_kind'] for m in entries)),
                evidence_scope='knowledge/items/*.json diagnostic_evidence; derived index',
                coverage_complete=False)


def validate_catalogue(root=ROOT):
    root=Path(root);read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    entries=read('knowledge/catalog/legacy-map.json')['entries'];ns=read('knowledge/catalog/nodes.json')['nodes']
    nodes={n['id']:n for n in ns}
    if len(nodes)!=len(ns):raise ValueError('Duplicate canonical IDs')
    queue=read('knowledge/review-plans/queue.json');ids={i['id'] for i in queue}
    if {m['legacy_id'] for m in entries}!=ids or len(entries)!=len(ids):raise ValueError('Incomplete legacy mapping')
    for n in ns:
        seen=set();cur=n
        while cur.get('parent_id'):
            if cur['id'] in seen:raise ValueError('Hierarchy cycle')
            seen.add(cur['id']);cur=nodes[cur['parent_id']]
    for m in entries:
        if not m['canonical_ids'] or any(c not in nodes for c in m['canonical_ids']):raise ValueError('Missing node')
        item=read('knowledge/items/'+m['legacy_id']+'.json')
        if item.get('taxonomy')!=m:raise ValueError('Item taxonomy drift')
    for m in entries:
        item=read('knowledge/items/'+m['legacy_id']+'.json')
        for e in item.get('diagnostic_evidence', []):
            if e.get('canonical_id') and e['canonical_id'] not in nodes:raise ValueError('Bad evidence scope')
    return statistics(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--validate',action='store_true');a=p.parse_args()
    print(json.dumps(validate_catalogue(a.root) if a.validate else statistics(a.root),ensure_ascii=False,indent=2))
