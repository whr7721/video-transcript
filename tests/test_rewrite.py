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
 def test_evidence_matches_after_normalization_but_not_different_content(self):
  p=r.context(self.id)
  for evidence in ['注意力是有限的！','注意力是有限的','注意力是有限的.','注 意 力是有限的','注意力是有限的；']:
   raw=self.raw();raw['blocks'][0]['evidence']=evidence;self.assertTrue(r.checked(raw,p,'xiaohongshu') is not None)
  for evidence in ['这句话在原文里不存在','！！！','。。']:
   raw=self.raw();raw['blocks'][0]['evidence']=evidence;self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_evidence_spans_segments_and_corrects_loose_provenance(self):
  wid='4'*16;store.save({'id':wid,'status':'completed','title':'跨段','created_at':time.time(),'result':{'text':'甲乙。丙丁。','segments':[{'text':'甲乙。','start':0,'end':1,'speaker':''},{'text':'丙丁。','start':1,'end':2,'speaker':''}]}})
  p=r.context(wid);raw=self.raw()
  raw['blocks'][0]={'text':'作者先说甲乙，再说丙丁。','kind':'source','source_ids':['seg-0','seg-1'],'evidence':'甲乙。丙丁。'}
  self.assertEqual(r.checked(raw,p,'xiaohongshu')['blocks'][0]['source_ids'],['seg-0','seg-1'])
  raw['blocks'][0]['source_ids']=['seg-1','seg-0'];self.assertTrue(r.checked(raw,p,'xiaohongshu'))
  raw['blocks'][0]['source_ids']=['seg-1'];result=r.checked(raw,p,'xiaohongshu')
  self.assertEqual(result['blocks'][0]['source_ids'],['seg-0','seg-1']);self.assertIn('已按原文实际位置校正',''.join(result['notes']))
  raw['blocks'][0]['evidence']='原文完全没有的句子';self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_moments_over_limit_truncates_but_other_platforms_reject(self):
  p=r.context(self.id)
  over=self.raw();over['title']='短题';over['blocks']=[{'text':'今天聊到一个很关键的话题。'*40,'kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  result=r.checked(over,p,'moments')
  self.assertLess(result['character_count']+len(result['title']),100);self.assertIn('正文超平台上限已截断',result['notes'])
  self.assertTrue(all('（延伸）' in b['text'] for b in result['blocks'] if b.get('kind')=='extension'))
  extension=self.raw();extension['blocks']=[{'text':('可以试着减少输入。'*20)+'（延伸）','kind':'extension','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  self.assertRaises(ValueError,r.checked,extension,p,'moments')
  zhihu=self.raw();zhihu['blocks']=[{'text':'长'*1600,'kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  self.assertRaises(ValueError,r.checked,zhihu,p,'zhihu')
 def test_output_ceiling_12000_and_raw_kept_only_on_failure(self):
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as m,patch.object(r.personal_kb,'reserve_budget',return_value=1) as b,patch.object(r.personal_kb,'settle_budget'):
   self.assertEqual(r.submit(self.id,'zhihu')['status'],'completed')
   self.assertEqual(m.call_args.args[2],12000);self.assertEqual(b.call_args.args[1],12000)
  bad=self.raw();bad['blocks'][0]['evidence']='凭空编造的原文句子'
  with patch.object(organizer,'request_json',return_value=(bad,{})):
   v=r.submit(self.id,'gongzhonghao');self.assertEqual(v['status'],'failed');self.assertEqual(r.get(v['id'])['raw'],bad)
   self.assertTrue(all('raw' not in x for x in r.listing(self.id)['versions']))
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})):
   self.assertEqual(r.submit(self.id,v['style'])['status'],'completed');self.assertNotIn('raw',r.get(v['id']))
if __name__=='__main__':unittest.main()
