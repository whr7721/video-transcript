import unittest
from experiments.retrieval_rerank.controls import Controls,query_parts,anchor_present


class RerankControlTests(unittest.TestCase):
 def pool(self):
  return [{'id':'a','text':'幼儿园招聘老师，讨论合同工时。','score':2.,'source_uid':'s1'},
          {'id':'b','text':'AI辅助幼儿教育，但没有成效研究。','score':1.,'source_uid':'s2'}]

 def test_explicit_entity_constraint_drops_only_common_word_hit(self):
  pool=self.pool();c=Controls(pool)
  rows=c.rank('AI 幼儿教育',pool,'constraints')
  self.assertNotIn('a',[p['id'] for p in rows]);self.assertEqual(rows[0]['id'],'b')

 def test_ascii_anchor_boundaries_prevent_chair_matching_ai(self):
  self.assertFalse(anchor_present('chair','ai'))
  self.assertTrue(anchor_present('用ai学习','ai'))
  self.assertTrue(anchor_present('wan2.2 视频','wan2.2'))

 def test_no_query_specific_synonyms_or_expected_answers(self):
  tokens,anchors=query_parts('如何找到小生意')
  self.assertNotIn('需求',tokens);self.assertEqual(anchors,[])
  self.assertNotIn('如何',tokens)

 def test_hard_constraint_can_lose_asr_alias_not_silently_fallback(self):
  pool=[{'id':'a','text':'使用cloud code学习。','score':1.,'source_uid':'s'}]
  c=Controls(pool)
  self.assertEqual(c.rank('Claude Code',pool,'constraints'),[])
  self.assertEqual([p['id'] for p in c.rank('Claude Code',pool,'lexical_rerank')],['a'])

 def test_reranking_does_not_inject_candidates_or_mutate_originals(self):
  import copy
  pool=self.pool();before=copy.deepcopy(pool);c=Controls(pool)
  for method in ('constraints','lexical_rerank'):
   result=c.rank('AI 幼儿教育',pool,method)
   self.assertTrue({p['id'] for p in result}<={p['id'] for p in pool})
  self.assertEqual(pool,before)
  self.assertEqual(c.rank('AI',[],'lexical_rerank'),[])

 def test_unknown_method_rejected(self):
  c=Controls(self.pool())
  with self.assertRaises(ValueError):c.rank('测试',self.pool(),'fake')
