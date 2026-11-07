import copy,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,library,content_classification as c,organizer
class Classes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(c.settings,'cloud_key',return_value='fixture')]
  for p in self.ps:p.start()
  store.init();self.id='4'*16;self.uid='audio:'+self.id;self.row={'id':self.id,'status':'completed','created_at':time.time(),'title':'不是判断依据','result':{'segments':[{'text':'第一步安装软件，第二步填写配置。','start':0,'end':4}],'text':'第一步安装软件，第二步填写配置。'}};store.save(self.row)
  a=FastAPI();a.include_router(c.router);self.client=TestClient(a)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def raw(self):return {'primary':'tutorial','secondary':None,'topics':['软件安装'],'reason':'原文给出操作步骤','evidence':[{'id':'seg-0','quote':'第一步安装软件'}]}
 def test_source_cache_manual_and_filter(self):
  before=copy.deepcopy(store.get(self.id))
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as m:
   c.start(self.uid);c.start(self.uid);self.assertEqual(m.call_count,1)
  self.assertEqual(c.view(self.uid)['effective']['primary'],'tutorial')
  res=self.client.put('/api/classification',params={'uid':self.uid},json={'revision':0,'primary':'knowledge','topics':['我的修正']});self.assertEqual(res.status_code,200,res.text)
  self.assertEqual(self.client.put('/api/classification',params={'uid':self.uid},json={'revision':0,'primary':'case'}).status_code,409)
  with patch.object(organizer,'request_json') as m:c.start(self.uid);m.assert_not_called()
  self.assertEqual(len(library.listing(q='',starred=False,collection_id=None,channel_id=None,content_type='knowledge')['items']),1);self.assertEqual(store.get(self.id),before)
 def test_evidence_validation(self):
  blocks,_=c.source(self.uid);raw=self.raw();raw['evidence'][0]['quote']='虚构步骤';self.assertRaises(ValueError,c.validate,raw,blocks)
  raw=self.raw();raw['secondary']='tutorial';self.assertRaises(ValueError,c.validate,raw,blocks)
 def test_stale_suggestion_not_used(self):
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})):c.start(self.uid)
  row=store.get(self.id);row['result']['segments'][0]['text']='这是不同的观点';store.save(row);self.assertTrue(c.view(self.uid)['stale']);self.assertIsNone(c.view(self.uid)['effective'])
 def test_manual_wins_over_inflight_ai(self):
  blocks,fp=c.source(self.uid);v=c.get(self.uid);v['status']='running';c.save(v)
  self.client.put('/api/classification',params={'uid':self.uid},json={'revision':0,'primary':'case'})
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})):c.run(self.uid,fp,blocks,0)
  self.assertEqual(c.view(self.uid)['effective']['primary'],'case')
 def test_failure_and_restart_preserve_transcript(self):
  with patch.object(organizer,'request_json',side_effect=RuntimeError('fixture')):self.assertEqual(c.start(self.uid)['status'],'failed')
  v=c.get(self.uid);v['status']='running';c.save(v);c.recover();self.assertEqual(c.get(self.uid)['status'],'failed');self.assertEqual(store.get(self.id)['result'],self.row['result'])
 def test_scheduled_input_error_visible(self):
  with patch.object(c,'source',side_effect=ValueError('原文过长')):v=c.schedule(self.uid)
  self.assertEqual(v['status'],'failed');self.assertIn('原文过长',v['error']);self.assertEqual(store.get(self.id)['status'],'completed')
 def test_link_completed_hook_is_opt_in(self):
  import link_jobs,documents
  folder=self.root/'jobs'/self.id;folder.mkdir(parents=True);(folder/'transcript.json').write_text(json.dumps(self.row['result']),encoding='utf8')
  row=store.get(self.id);row['link_job_id']='5'*16;store.save(row)
  job={'id':row['link_job_id'],'task_id':self.id,'action':'link_ingest','status':'queued','classify':True,'arguments':{'plan':{'local':str(folder)},'url':'https://example.org/x'}};documents.generation_save(job)
  def update(**fields):
   t=store.get(self.id);t.update(fields);store.save(t)
  with patch.object(link_jobs.link_ingest,'add'),patch.object(c,'schedule') as schedule:link_jobs.run(row,update);schedule.assert_called_once_with(self.uid)
  self.assertEqual(store.get(self.id)['status'],'completed')
if __name__=='__main__':unittest.main()

