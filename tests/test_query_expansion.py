import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import library,personal_kb,query_expansion,store,topic_search
class BilingualTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3')]
  for p in self.ps:p.start()
  store.init()
  for ident,text in [('a'*16,'Machine learning uses neural network models.'),('b'*16,'摄影课程讲解光圈和快门。')]:store.save({'id':ident,'title':'检索测试','status':'completed','created_at':time.time(),'result':{'text':text}})
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def test_chinese_english_bidirectional_and_scope(self):
  library.sync();self.assertEqual(library.retrieve('机器学习')[0]['uid'],'audio:'+'a'*16);self.assertEqual(library.retrieve('photography')[0]['uid'],'audio:'+'b'*16)
  self.assertEqual(library.retrieve('机器学习',uid='audio:'+'b'*16),[])
  personal_kb.sync();self.assertTrue(personal_kb.search('神经网络'))
 def test_query_only_expansion_and_ascii_word_boundaries(self):
  self.assertIn('machine',topic_search.query_terms('机器学习'));self.assertIn('摄影',topic_search.query_terms('photography'));self.assertEqual(query_expansion.phrases('chair'),['chair']);self.assertIn('ai',topic_search.query_terms('ＡＩ'))
  self.assertEqual(topic_search.terms('photography'),['photography'])

if __name__=='__main__':unittest.main()
