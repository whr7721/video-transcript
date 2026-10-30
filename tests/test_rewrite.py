import copy,io,json,tempfile,time,unittest,contextlib
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import rewrite as r,store,organizer,shiwen
class RewriteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(r.settings,'cloud_key',return_value='fixture')]
  for p in self.ps:p.start()
  store.init();self.id='3'*16;self.row={'id':self.id,'status':'completed','title':'测试','created_at':time.time(),'result':{'text':'注意力是有限的。','segments':[{'text':'注意力是有限的。','start':0,'end':2,'speaker':'说话人1'}]}};store.save(self.row)
  a=FastAPI();a.include_router(r.router);self.c=TestClient(a)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def raw(self):return {'title':'把注意力留给重要的事','blocks':[{'text':'作者认为，注意力是有限的。','kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}],'reused_quotes':[],'notes':['素材较短，未扩写凑字']}
 def test_four_styles_cache_edit_conflict_and_source_unchanged(self):
  before=copy.deepcopy(store.get(self.id)['result'])
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as m:
   versions=[r.submit(self.id,s) for s in r.STYLES];self.assertTrue(all(v['status']=='completed' for v in versions));self.assertEqual(m.call_count,4)
   for s in r.STYLES:r.submit(self.id,s)
   self.assertEqual(m.call_count,4)
  v=versions[0];res=self.c.put('/api/rewrites/'+v['id'],json={'revision':0,'text':'我的编辑稿'});self.assertEqual(res.status_code,200)
  self.assertEqual(self.c.put('/api/rewrites/'+v['id'],json={'revision':0,'text':'旧窗口覆盖'}).status_code,409)
  with patch.object(organizer,'request_json') as m:self.assertEqual(r.submit(self.id,v['style'])['text'],'我的编辑稿');m.assert_not_called()
  self.assertIn('作者认为',r.get(v['id'])['original']);self.assertEqual(self.c.get('/api/rewrites/'+v['id']+'/markdown').text,'我的编辑稿');self.assertEqual(store.get(self.id)['result'],before)
 def test_invalid_evidence_extension_and_quote(self):
  p=r.context(self.id)
  for field,value in [('evidence','不存在'),('kind','other')]:
   raw=self.raw();raw['blocks'][0][field]=value;self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
  raw=self.raw();raw['blocks'][0]['kind']='extension';self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu');raw['blocks'][0]['text']='（延伸）可以试着减少输入。';self.assertTrue(r.checked(raw,p,'xiaohongshu'))
  raw=self.raw();raw['reused_quotes']=['虚构金句'];self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_verified_quote_stale_and_recover(self):
  import documents
  documents.generation_save({'id':'quote','task_id':self.id,'action':'quotes','status':'completed','items':[{'text':'注意力是有限的。'},{'text':'假的'}]})
  self.assertEqual(r.context(self.id)['verified_quotes'],['注意力是有限的。'])
  raw=self.raw();raw['reused_quotes']=['注意力是有限的。']
  with patch.object(organizer,'request_json',return_value=(raw,{})):v=r.submit(self.id,'moments');self.assertEqual(v['status'],'completed')
  row=store.get(self.id);row['result']['segments'][0]['text']='原文已改变';store.save(row);self.assertTrue(r.listing(self.id)['versions'][0]['stale'])
  v.update(status='running');r.save(v);r.recover();self.assertEqual(r.get(v['id'])['status'],'failed')
 def test_failure_retry_and_cli_json_cache(self):
  with patch.object(organizer,'request_json',side_effect=RuntimeError('fixture failure')):v=r.submit(self.id,'xiaohongshu');self.assertEqual(v['status'],'failed')
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as m:v=r.submit(self.id,'xiaohongshu');self.assertEqual(m.call_count,1)
  out=io.StringIO()
  with patch.object(organizer,'request_json') as m,contextlib.redirect_stdout(out):shiwen.main(['rewrite',self.id,'--json']);m.assert_not_called()
  self.assertEqual(json.loads(out.getvalue())['id'],v['id']);self.assertFalse(self.c.get('/api/rewrites/'+v['id']+'/card-payload').json()['implemented'])
if __name__=='__main__':unittest.main()
