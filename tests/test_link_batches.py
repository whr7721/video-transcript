import io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,documents,link_batches as b,link_jobs,link_ingest

class Batches(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3')]
  for p in self.patches:p.start()
  store.init();b.init();b.INFLIGHT=None;b.CURSOR=None;b.BUSY=False
  self.q=[];app=FastAPI();app.include_router(b.router);self.c=TestClient(app)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def preview(self,urls,summarize=False):
  return self.c.post('/api/link-batches/preview',json={'rows':[{'text':u,'summarize':summarize} for u in urls]}).json()
 def start(self,batch):self.c.post('/api/link-batches/'+batch['id']+'/start')
 def pump(self):b.pump(self.q.append,lambda:not self.q)
 def execute(self,summary=None):
  task=store.get(self.q.pop(0))
  def update(**f):t=store.get(task['id']);t.update(f);store.save(t)
  def subtitles(url,directory,language,progress):
   progress(stage='subtitles');return {'title':'同名文稿'},{'text':'字幕','segments':[{'start':0,'end':1,'text':'字幕'}]},None
  with patch.object(link_ingest,'ytdlp',subtitles),patch('cli_summary.summarize',summary) if summary else patch('cli_summary.summarize'):
   link_jobs.run(task,update)
 def test_preview_dedup_invalid_and_quota(self):
  with store.connect() as db:db.execute('CREATE TABLE organizer_calls(day TEXT PRIMARY KEY,count INTEGER)');db.execute('INSERT INTO organizer_calls VALUES (?,?)',(b.quota()['day'],29))
  v=self.preview(['https://youtu.be/a','https://youtu.be/a','bad'],True)
  self.assertEqual([i['status'] for i in v['items']],['waiting','duplicate','invalid']);self.assertEqual(v['estimate']['requests'],2);self.assertEqual(v['estimate']['remaining'],1);self.assertEqual(self.q,[])
 def test_round_robin_shared_task_and_busy(self):
  one=self.preview(['https://youtu.be/a','https://youtu.be/b']);two=self.preview(['https://youtu.be/c','https://youtu.be/a']);self.start(one);self.start(two)
  b.BUSY=True;self.pump();self.assertEqual(self.q,[]);b.BUSY=False
  self.pump();self.assertEqual(len(self.q),1);self.pump();self.assertEqual(len(self.q),1);self.execute()
  self.pump();self.assertEqual(b.get(two['id'])['items'][0]['status'],'queued');self.execute()
  self.pump();self.execute();self.pump();self.assertEqual(self.q,[])
  for batch in (one,two):self.assertEqual(b.reconcile(b.get(batch['id']))['counts']['completed'],2)
 def test_low_quota_completes_transcript_waits_summary(self):
  with patch.object(b,'quota',return_value={'remaining':0,'limit':30,'day':'fixture'}):
   v=self.preview(['https://youtu.be/a'],True);self.start(v);self.pump();self.execute();self.pump()
   row=b.reconcile(b.get(v['id']))['items'][0];self.assertEqual(row['status'],'waiting_summary');self.assertEqual(self.q,[])
  original=(self.root/'jobs'/row['task_id']/'transcript.json').read_bytes()
  self.pump();self.execute();self.pump();self.assertEqual(b.reconcile(b.get(v['id']))['items'][0]['status'],'completed');self.assertEqual(original,(self.root/'jobs'/row['task_id']/'transcript.json').read_bytes())
 def test_pause_stop_and_zip_partial(self):
  v=self.preview(['https://youtu.be/a','https://youtu.be/b']);self.start(v);self.c.post('/api/link-batches/'+v['id']+'/pause');self.pump();self.assertEqual(self.q,[])
  self.c.post('/api/link-batches/'+v['id']+'/resume');self.pump();self.execute();self.c.post('/api/link-batches/'+v['id']+'/stop');self.pump();self.assertEqual(self.q,[])
  r=self.c.get('/api/link-batches/'+v['id']+'/export');z=zipfile.ZipFile(io.BytesIO(r.content));manifest=json.loads(z.read('batch-manifest.json'))
  self.assertEqual(len(manifest['items']),2);self.assertTrue(manifest['items'][1]['missing']);self.assertTrue(all(not n.startswith('/') and '..' not in n and not n.endswith('.wav') for n in z.namelist()))
 def test_pending_single_can_be_upgraded_to_summary(self):
  args=type('A',(),{})();args.url='https://youtu.be/a';args.language='auto';args.episode=None;args.allowed=['youtube'];args.summarize=False
  plan=link_ingest.prepare(args);plain=link_jobs.submit(args,plan,False,self.q.append);upgraded=link_jobs.submit(args,plan,True,self.q.append)
  self.assertEqual(plain['id'],upgraded['id']);self.assertTrue(upgraded['summarize']);self.assertEqual(len(self.q),1)
 def test_summary_upgrade_while_transcribing_is_not_lost(self):
  from types import SimpleNamespace
  args=SimpleNamespace(url='https://youtu.be/a',language='auto',episode=None,allowed=['youtube'],summarize=False)
  plan=link_ingest.prepare(args);job=link_jobs.submit(args,plan,False,self.q.append)
  def subtitles(url,directory,language,progress):
   link_jobs.submit(args,plan,True,self.q.append);progress(stage='subtitles')
   return {},{'text':'字幕','segments':[{'start':0,'end':1,'text':'字幕'}]},None
  t=store.get(self.q.pop(0))
  def update(**f):v=store.get(t['id']);v.update(f);store.save(v)
  with patch.object(link_ingest,'ytdlp',subtitles),patch('cli_summary.summarize') as summary:
   link_jobs.run(t,update);self.assertEqual(summary.call_count,1)
  self.assertEqual(self.q,[]);self.assertTrue(documents.generation_get(job['id'])['summarize'])
 def test_rss_requires_selection_without_creating_a_task(self):
  feed={'title':'播客','episodes':[{'title':'第一集'}]}
  with patch.object(link_ingest,'prepare',return_value={'feed':feed}):v=self.preview(['https://example.org/rss'])
  self.assertEqual(v['items'][0]['status'],'selection');self.assertEqual(self.c.post('/api/link-batches/'+v['id']+'/start').status_code,400);self.assertEqual(store.all_tasks(),[])
 def test_quota_race_is_waiting_not_failed(self):
  v=self.preview(['https://youtu.be/a'],True);self.start(v);self.pump();self.execute();self.pump()
  def fail(path):raise RuntimeError('今日文本整理已达30次请求上限')
  self.execute(fail)
  self.assertEqual(b.reconcile(b.get(v['id']))['items'][0]['status'],'waiting_summary')

 def test_stop_cancels_queued_owned_job_without_asr(self):
  v=self.preview(['https://youtu.be/a']);self.start(v);self.pump();item=b.get(v['id'])['items'][0]
  self.c.post('/api/link-batches/'+v['id']+'/stop')
  self.assertEqual(documents.generation_get(item['job_id'])['status'],'failed')
  with patch.object(link_ingest,'add',side_effect=AssertionError('已停止不能执行')):self.execute()
  self.assertEqual(b.get(v['id'])['items'][0]['status'],'stopped')
 def test_stop_preserves_job_requested_by_single_user(self):
  from types import SimpleNamespace
  v=self.preview(['https://youtu.be/a']);self.start(v);self.pump();item=b.get(v['id'])['items'][0]
  args=SimpleNamespace(url='https://youtu.be/a',language='auto',episode=None,allowed=['youtube'],summarize=False)
  link_jobs.submit(args,link_ingest.prepare(args),False,self.q.append)
  self.c.post('/api/link-batches/'+v['id']+'/stop');self.assertEqual(documents.generation_get(item['job_id'])['status'],'queued');self.execute()
  self.assertEqual(documents.generation_get(item['job_id'])['status'],'completed')

 def test_free_batch_is_complete_if_shared_summary_fails(self):
  from types import SimpleNamespace
  v=self.preview(['https://youtu.be/a']);self.start(v);self.pump()
  args=SimpleNamespace(url='https://youtu.be/a',language='auto',episode=None,allowed=['youtube'],summarize=False)
  link_jobs.submit(args,link_ingest.prepare(args),True,self.q.append)
  def fail(path):raise RuntimeError('今日文本整理已达30次请求上限')
  self.execute(fail)
  self.assertEqual(b.reconcile(b.get(v['id']))['items'][0]['status'],'completed')

 def test_restart_pauses_and_resume_recovers_interrupted(self):
  v=self.preview(['https://youtu.be/a']);self.start(v);self.pump();link_jobs.recover();b.start(self.q.append,lambda:False);b.stop()
  self.assertEqual(b.get(v['id'])['status'],'paused');self.c.post('/api/link-batches/'+v['id']+'/resume');self.assertEqual(b.get(v['id'])['items'][0]['status'],'waiting')

if __name__=='__main__':unittest.main()
