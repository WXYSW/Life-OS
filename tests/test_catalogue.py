import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from catalogue import ROOT, load_context, validate_catalogue
from learning import plan_actions
from questions import issue

def item(k,scope):
 return dict(id=k,status='pending',goal_links=[dict(goal_id='G',contribution='high')],taxonomy={'entry_kind':'bundle'},canonical_ids=scope)
class CatalogueTests(unittest.TestCase):
 def test_catalogue_is_complete_and_archive_preserved(self):
  stats=validate_catalogue()
  self.assertEqual(stats['source_entries'],161)
  self.assertEqual(stats['archived_legacy_entries'],73)
  self.assertEqual(stats['canonical_long_term_verified'],0)
  self.assertEqual(stats['historical_unique_attempts'],19)
 def test_partial_overlap_preserves_remaining_scope(self):
  p=plan_actions([item('A',['X']),item('B',['X','Y'])],[],[dict(id='G',status='active')],'2026-10-12',new_limit=2)
  self.assertEqual([a['canonical_ids'] for a in p['actions']],[['X'],['Y']])
 def test_full_duplicate_is_selected_once(self):
  p=plan_actions([item('A',['X']),item('B',['X'])],[],[dict(id='G',status='active')],'2026-10-12',new_limit=2)
  self.assertEqual(len(p['actions']),1)
 def test_existing_open_scope_blocks_new_alias(self):
  qs=issue([],'Q','A','new','prompt','2026-10-11',canonical_ids=['X'])
  p=plan_actions([item('A',['X']),item('B',['X'])],qs,[dict(id='G',status='active')],'2026-10-12')
  self.assertEqual([a['knowledge_id'] for a in p['actions']],['A'])
  with self.assertRaises(ValueError):issue(qs,'Q2','B','new','same concept','2026-10-12',canonical_ids=['X'])
 def test_current_session_scope_blocks_new_alias(self):
  qs=issue([],'Q','A','new','prompt','2026-10-11',canonical_ids=['X']);qs[0]['status']='evaluated'
  p=plan_actions([item('A',['X']),item('B',['X'])],qs,[dict(id='G',status='active')],'2026-10-12',assigned=['Q'])
  self.assertEqual(p['actions'],[])
 def test_container_does_not_become_test(self):
  i=item('A',['X']);i['taxonomy']['entry_kind']='container'
  p=plan_actions([i],[],[dict(id='G',status='active')],'2026-10-12')
  self.assertEqual(p['actions'],[])
 def test_limit_evidence_does_not_cover_lhopital(self):
  read=lambda p:json.loads((ROOT/p).read_text())
  q=read('knowledge/migrations/2026-10-11-legacy-schedules.json')['items'];qs=[]
  original=copy.deepcopy(q);enriched,_=load_context(ROOT,q,qs)
  nodes={n['id']:n['title'] for n in read('knowledge/catalog/nodes.json')['nodes']}
  i=next(x for x in enriched if x['id']=='K-IMPORT-063')
  self.assertEqual([nodes[c] for c in i['canonical_ids']],['基本极限计算'])
  self.assertEqual(q,original)
if __name__=='__main__':unittest.main()
