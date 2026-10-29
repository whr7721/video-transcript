"""Link workflow tests always use isolated runtime data."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,documents,link_jobs,link_ingest,organizer

class LinkJobs(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3')]
  for p in self.patches:p.start()
  store.init();self.queue=[];app=FastAPI();app.include_router(link_jobs.router(self.queue.append,('youtube','rss')));self.client=TestClient(app)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def submit(self,**extra):return self.client.post('/api/link',json={'url':'https://youtu.be/test',**extra}).json()
 def execute(self):
  t=store.get(self.queue.pop(0))
  def update(**f):v=store.get(t['id']);v.update(f);store.save(v)
  link_jobs.run(t,update)
 def subtitles(self,url,directory,language,progress):
  progress(stage='subtitles',message='获取字幕')
  return {'title':'字幕样例','duration':1},{'text':'真实结构','segments':[{'start':0,'end':1,'text':'真实结构'}],'engine':'publisher_subtitles'},None
 def test_subtitles_cache_no_asr(self):
  with patch.object(link_ingest,'ytdlp',self.subtitles),patch('transcribe.local_transcribe',side_effect=AssertionError('不应ASR')):
   j=self.submit();self.execute();done=self.client.get('/api/link/'+j['id']).json()
   self.assertEqual(done['status'],'completed');self.assertNotIn('transcribing',[s['stage'] for s in done['stages']])
   self.assertTrue(self.submit()['cached']);self.assertEqual(self.queue,[])
   self.assertEqual(store.get(j['task_id'])['result']['subtitlesArray'][0]['index'],0)
 def test_summary_failure_preserves_bytes_retry_only_summary(self):
  with patch.object(link_ingest,'ytdlp',self.subtitles):
   j=self.submit(summarize=True)
   with patch('cli_summary.summarize',side_effect=ValueError('配额不足')):self.execute()
  folder=self.root/'jobs'/j['task_id'];before={p.name:p.read_bytes() for p in folder.glob('transcript.*')}
  self.assertEqual(store.get(j['task_id'])['status'],'completed')
  self.assertEqual(link_jobs.get(j['id'])['status'],'failed')
  self.client.post('/api/link/'+j['id']+'/retry')
  with patch.object(link_ingest,'ytdlp',side_effect=AssertionError('不可重新下载')),patch('cli_summary.summarize') as summary:self.execute();summary.assert_called_once_with(folder)
  self.assertEqual(before,{p.name:p.read_bytes() for p in folder.glob('transcript.*')})
 def test_rss_audio_download_fallback_is_shared(self):
  from types import SimpleNamespace
  episode={'id':'ep','title':'播客','published':'','duration_seconds':1,'audio_url':'https://example.org/audio.mp3','transcripts':[]}
  plan={'kind':'rss','episode':episode,'ident':'b'*16,'local':Path('.')}
  args=SimpleNamespace(url='https://example.org/rss',language='auto',episode=1,summarize=False,plan=plan)
  def stream(url,write,*a,**kw):write(b'audio')
  result={'text':'播客原话','segments':[{'start':0,'end':1,'text':'播客原话'}]}
  with patch('article_fetch.stream',stream),patch('media_io.probe_media',return_value=1),patch('media_io.extract_audio'),patch('transcribe.local_transcribe',return_value=result) as asr:
   link_ingest.add(args);self.assertEqual(asr.call_count,1)
  self.assertEqual((self.root/'jobs'/('b'*16)/'podcast.audio').read_bytes(),b'audio')

 def test_core_reject_before_network_and_export_traversal(self):
  with patch.object(link_ingest,'prepare',side_effect=AssertionError('不应联网')):
   r=self.client.post('/api/link',json={'url':'https://v.douyin.com/test'});self.assertEqual(r.status_code,400);self.assertIn('此版本不支持抖音链接',r.text)
  self.assertEqual(self.client.get('/api/link/aaaaaaaaaaaaaaaa/export/not-allowed').status_code,404)
 def test_recovery_owned_by_link_not_organizer(self):
  j=self.submit();organizer.recover();self.assertEqual(link_jobs.get(j['id'])['status'],'queued')
  link_jobs.recover();self.assertEqual(link_jobs.get(j['id'])['status'],'failed');self.assertEqual(store.get(j['task_id'])['status'],'failed')
 def test_legacy_recovery_does_not_take_over_standalone_cli(self):
  import app
  record={'id':'c'*16,'source':{'kind':'link','platform':'youtube'},'status':'running','created_at':1,'title':'CLI独立任务'}
  store.save(record);before=store.get(record['id'])
  with TestClient(app.app):self.assertEqual(store.get(record['id']),before)
  self.assertEqual(store.get(record['id']),before)

 def test_rss_preview_does_not_create_task(self):
  with patch.object(link_ingest,'prepare',return_value={'feed':{'title':'播客','episodes':[{'title':'第一集'}]}}):
   result=self.client.post('/api/link',json={'url':'https://example.org/rss'}).json()
  self.assertTrue(result['selection_required']);self.assertEqual(store.all_tasks(),[]);self.assertEqual(self.queue,[])

if __name__=='__main__':unittest.main()
