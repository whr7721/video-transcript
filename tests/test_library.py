import io,json,tempfile,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,library,store,documents

class LibraryTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'runtime';root.mkdir(exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=root);self.path=Path(self.temp.name)
  self.patches=[patch.object(store,'DATA',self.path),patch.object(store,'DB',self.path/'tasks.sqlite3')]
  for p in self.patches:p.start()
  store.init();self.tid='a'*16
  store.save({'id':self.tid,'title':'标题测试','created_at':time.time(),'status':'completed','duration':120,'source':{'platform':'youtube'},'result':{'subtitlesArray':[{'text':'字幕独有的量子纠缠知识','startTime':7,'end':9,'index':0}]}})
  with store.connect() as db:
   documents.init(db);db.execute('INSERT INTO generations VALUES (?,?)',('g',json.dumps({'task_id':self.tid,'status':'completed','action':'summary','items':[{'text':'摘要里的光谱分析'}]})))
   db.execute('CREATE TABLE article_items(id TEXT PRIMARY KEY,payload TEXT)');db.execute('INSERT INTO article_items VALUES (?,?)',('art',json.dumps({'id':'art','title':'文章','status':'ready','created_at':1,'blocks':[{'id':'p1','text':'图文的宇宙观察','type':'paragraph'}]})))
  self.client=TestClient(app.app)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def test_search_fields_scope_and_refresh(self):
  for q,uid in [('量子纠缠','audio:'+self.tid),('光谱分析','audio:'+self.tid),('宇宙观察','article:art'),('标题测试','audio:'+self.tid)]:
   r=self.client.get('/api/library',params={'q':q});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['items'][0]['uid'],uid)
  self.assertEqual(library.retrieve('宇宙',uid='audio:'+self.tid),[])
  t=store.get(self.tid);t['result']={'text':'更新后的显微镜'};store.save(t);library.sync()
  self.assertFalse(library.retrieve('量子纠缠'));self.assertTrue(library.retrieve('显微镜'))
 def test_star_collections_order_export_and_no_source_mutation(self):
  original=store.get(self.tid)['result'];uid='audio:'+self.tid
  self.client.post('/api/library/star',json={'uid':uid,'value':True})
  self.assertEqual(len(self.client.get('/api/library?starred=true').json()['items']),1)
  c=self.client.post('/api/library/collections',json={'name':'专题'}).json()['id'];base='/api/library/collections/'+c
  self.assertEqual(self.client.put(base+'/members',json={'uids':['article:art',uid]}).status_code,200)
  self.client.put(base,json={'name':'新专题'});self.assertEqual(self.client.get('/api/library/collections').json()[0]['name'],'新专题')
  self.assertEqual([i['uid'] for i in self.client.get('/api/library',params={'collection_id':c}).json()['items']],['article:art',uid])
  self.client.put(base+'/members',json={'uids':[uid,'article:art']})
  z=zipfile.ZipFile(io.BytesIO(self.client.get(base+'/export').content));manifest=json.loads(z.read('collection-manifest.json'));self.assertEqual(manifest['items'][0]['uid'],uid);self.assertIn('transcript.json',manifest['items'][0]['missing']);self.assertIn('002-source.txt',z.namelist())
  self.assertEqual(self.client.put(base+'/members',json={'uids':['missing']}).status_code,400)
  self.assertEqual(self.client.get(base+'/members').json(),[uid,'article:art'])
  self.client.put(base+'/members',json={'uids':[uid]});self.assertEqual(self.client.get(base+'/members').json(),[uid])
  self.assertEqual(store.get(self.tid)['result'],original)
 def test_statistics_and_single_chinese_character(self):
  v=library.listing(q='字',starred=False,collection_id=None);self.assertTrue(v['items']);self.assertEqual(v['stats']['total'],2);self.assertEqual(v['stats']['duration'],120)

if __name__=='__main__':unittest.main()
