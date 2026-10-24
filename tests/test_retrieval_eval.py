import copy
import unittest
from experiments.retrieval import projection,baselines,evaluate


class RetrievalEvalTests(unittest.TestCase):
 def docs(self):
  blocks=[{'id':'b0','text':'🙂中文检索先确认出处。显卡缓存和向量检索有不同用途。'},
          {'id':'b1','text':'同样谈显卡，但没有记录某个新型号的购买价格。'}]
  return [{'uid':'article:test','kind':'article','item_id':'test','title':'工具说明','version':'original',
           'source_hash':projection.fingerprint(blocks),'blocks':blocks}]

 def test_projection_roundtrip_offsets_and_staleness(self):
  docs=self.docs();before=copy.deepcopy(docs)
  parts=projection.passages(docs,9)
  self.assertTrue(all(projection.resolve(docs,p)==p['text'] for p in parts))
  spans=[r for p in parts for r in p['ranges'] if r['block_id']=='b0']
  self.assertEqual(spans[0]['start'],0);self.assertEqual(spans[-1]['end'],len(docs[0]['blocks'][0]['text']))
  self.assertEqual(sum(r['end']-r['start'] for r in spans),len(docs[0]['blocks'][0]['text']))
  self.assertEqual(docs,before)
  corrupted=copy.deepcopy(parts[0]);corrupted['source_hash']='old'
  with self.assertRaises(ValueError):projection.resolve(docs,corrupted)

 def test_trigram_short_terms_fail_bigram_matches(self):
  engine=baselines.Baselines(projection.passages(self.docs()))
  try:
   self.assertEqual(engine.search('缓存','trigram_bm25'),[])
   self.assertTrue(engine.search('缓存','bigram_bm25'))
   self.assertTrue(engine.search('向量检索','trigram_bm25'))
  finally:engine.close()

 def test_query_operators_are_data_and_limits_reject(self):
  engine=baselines.Baselines(projection.passages(self.docs()))
  try:
   for method in baselines.METHODS:
    engine.search('缓存 OR " NOT * % _',method)
    with self.assertRaises(ValueError):engine.search('',method)
    with self.assertRaises(ValueError):engine.search('字'*201,method)
    with self.assertRaises(ValueError):engine.search('缓存',method,0)
  finally:engine.close()

 def test_metrics_distinguish_source_evidence_and_no_answer(self):
  docs=self.docs();parts=projection.passages(docs,12)
  last=parts[-1]['ranges'][-1]
  gold=[{'source_uid':docs[0]['uid'],'source_hash':docs[0]['source_hash'],**last}]
  first=evaluate.score([parts[0]],gold)
  self.assertTrue(first['source_success']);self.assertFalse(first['evidence_success'])
  matched=evaluate.score([parts[0],parts[-1]],gold)
  self.assertTrue(matched['evidence_success']);self.assertEqual(matched['known_mrr'],.5)
  self.assertEqual(evaluate.score([parts[0]],[]),{'nonempty':True})
  self.assertEqual(evaluate.score([],[]),{'nonempty':False})

 def test_frozen_gold_requires_original_snapshot(self):
  docs=self.docs();text=docs[0]['blocks'][0]['text'];start=text.index('检索')
  gold={'source_uid':docs[0]['uid'],'source_hash':docs[0]['source_hash'],'block_id':'b0','start':start,'end':start+2,
        'evidence_hash':projection.fingerprint('检索')}
  dataset={'cases':[{'gold':[gold]}]};evaluate.validate_labels(docs,dataset)
  bad=copy.deepcopy(dataset);bad['cases'][0]['gold'][0]['start']+=1
  with self.assertRaises(ValueError):evaluate.validate_labels(docs,bad)

 def test_document_term_frequencies_preserved(self):
  self.assertEqual(baselines.terms('缓存缓存',2,unique=False).count('缓存'),2)
  self.assertEqual(baselines.terms('缓存缓存',2).count('缓存'),1)
  self.assertIn('comfyui',baselines.terms('ＣｏｍｆｙＵＩ',2))

 def test_evaluation_sources_are_read_only(self):
  import sqlite3,tempfile,json
  from pathlib import Path
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'profile').mkdir();path=root/'profile/tasks.sqlite3'
   db=sqlite3.connect(path);db.execute('CREATE TABLE tasks (id TEXT,payload TEXT)')
   value={'id':'x','status':'completed','title':'说明','result':{'text':'本地测试文本'}}
   db.execute('INSERT INTO tasks VALUES (?,?)',('x',json.dumps(value)));db.commit();db.close()
   before=path.read_bytes()
   with patch.object(projection,'SOURCES',[('profile','tasks','x')]):docs,manifest=projection.load(root)
   self.assertEqual(before,path.read_bytes());self.assertTrue(manifest[0]['read_only'])
   self.assertNotIn('start',docs[0]['blocks'][0])
