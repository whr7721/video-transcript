import tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,subscriptions as sub,source_expand as expand,source_enumeration as sources,link_ingest,link_batches
class FeedTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.temp.name)
  self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(sub.EXECUTOR,'submit')]
  for p in self.ps:p.start()
  store.init();sub.init();app=FastAPI();app.include_router(sub.router);app.include_router(expand.router);self.c=TestClient(app)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.temp.cleanup()
 def add(self,url='https://example.org/feed'):return self.c.post('/api/subscriptions/channels',json={'url':url}).json()
 def result(self,items):return {'identity':'example','title':'节目','status':'ok','items':[{'id':i,'title':i,'url':'https://youtu.be/'+i} for i in items]}
 def test_url_dedupe_and_no_automatic_check(self):
  a=self.add();self.assertEqual(self.add()['id'],a['id']);self.assertEqual(store.all_tasks(),[]);sub.EXECUTOR.submit.assert_not_called()
 def test_id_dedupe_seen_cursor_metadata_update_and_refresh(self):
  c=self.add()
  with patch.object(sources,'enumerate_source',return_value=self.result(['a','b'])):sub.check(c['id'],20);sub.check(c['id'],20)
  self.assertEqual(len(sub.feed()),2);self.c.post('/api/subscriptions/seen',json={'channel_id':c['id']});self.assertEqual(sub.feed(),[])
  with patch.object(sources,'enumerate_source',return_value=self.result(['c','a','b'])):sub.check(c['id'],20)
  self.assertEqual([r['id'] for r in sub.feed()],['c']);self.c.post('/api/subscriptions/seen',json={'seq':sub.feed()[0]['seq']});self.assertEqual(sub.feed(),[]);self.assertEqual(len(sub.feed(False)),3)
 def test_mark_read_during_check_is_not_overwritten(self):
  c=self.add()
  with patch.object(sources,'enumerate_source',return_value=self.result(['a'])):sub.check(c['id'],20)
  def fetch(*a):sub.seen(sub.Seen(channel_id=c['id']));return self.result(['b','a'])
  with patch.object(sources,'enumerate_source',fetch):sub.check(c['id'],20)
  self.assertEqual([i['id'] for i in sub.feed()],['b'])
 def test_failure_isolated_and_unsubscribe_keeps_tasks(self):
  good=self.add();bad=self.add('https://bad.example/feed')
  with patch.object(sources,'enumerate_source',return_value=self.result(['a'])):sub.check(good['id'],20)
  with patch.object(sources,'enumerate_source',side_effect=ValueError('坏源')):sub.check(bad['id'],20)
  self.assertEqual(sub.get(bad['id'])['status'],'error');self.assertEqual(len(sub.feed()),1)
  store.save({'id':'a'*16,'status':'completed','created_at':1,'result':{'text':'保留'}});self.c.delete('/api/subscriptions/channels/'+good['id']);self.assertIsNotNone(store.get('a'*16));self.assertEqual(sub.feed(),[])
 def test_free_text_gate_before_search_and_partial_selection(self):
  with patch.object(sources,'enumerate_source',return_value=self.result(['a','b','c','d','e','f'])) as fetch:
   r=self.c.post('/api/source-expand/preview',json={'rows':['Python'],'limit':20}).json();self.assertTrue(r['confirmation_required']);fetch.assert_not_called()
   r=self.c.post('/api/source-expand/preview',json={'rows':['Python'],'limit':20,'confirm_topics':True}).json();self.assertEqual(len(r['groups'][0]['items']),6)
  keys=[i['key'] for i in r['groups'][0]['items'][:5]]
  with patch.object(link_batches,'preview',return_value={'id':'draft'}) as preview:
   self.assertEqual(self.c.post('/api/source-expand/'+r['id']+'/batch',json={'keys':keys}).status_code,200);self.assertEqual(len(preview.call_args[0][0].rows),5)
  self.assertEqual(self.c.post('/api/source-expand/'+r['id']+'/batch',json={'keys':['forged']}).status_code,400)
 def test_rss_guid_resolves_reordered_episode_and_missing_does_not_fallback(self):
  episode={'id':'newhash','guid':'stable-guid','title':'标题更新'};feed={'episodes':[{'id':'other','guid':'other'},episode]}
  args=SimpleNamespace(url='https://example.org/feed',episode=1,episode_id='oldhash',episode_guid='stable-guid',language='auto',allowed=['rss'])
  with patch('article_fetch.stream',side_effect=lambda u,w,*a,**k:w(b'feed')),patch('podcast_feed.parse',return_value=feed):
   plan=link_ingest.prepare(args);self.assertEqual(plan['episode']['guid'],'stable-guid');self.assertEqual(args.episode,2)
   args.episode_guid='missing'
   with self.assertRaises(ValueError):link_ingest.prepare(args)
 def test_rss_identity_survives_title_change(self):
  episode={'id':'first','guid':'publisher-guid','title':'原标题','published':'date','duration_seconds':3}
  feed={'feed_url':'https://example.org/feed','title':'节目','episodes':[episode]}
  with patch('article_fetch.stream',side_effect=lambda u,w,*a,**k:w(b'feed')),patch('podcast_feed.parse',return_value=feed):
   first=sources.enumerate_source('rss',feed['feed_url'],20)['items'][0]
   episode.update(title='更新标题',id='second')
   second=sources.enumerate_source('rss',feed['feed_url'],20)['items'][0]
  self.assertEqual(first['id'],second['id']);self.assertNotEqual(first['episode_id'],second['episode_id'])

 def test_rss_snapshot_works_when_item_has_left_latest_feed(self):
  episode={'id':'old-episode','guid':'retained-guid','title':'已发现单集','audio_url':'https://example.org/old.mp3','transcripts':[]}
  args=SimpleNamespace(url='https://example.org/feed',language='auto',episode=None,episode_guid='retained-guid',episode_snapshot=episode,allowed=['rss'])
  with patch('article_fetch.stream',side_effect=AssertionError('不应依赖当前Feed序号')):
   plan=link_ingest.prepare(args)
  self.assertEqual(plan['episode']['id'],'old-episode')
 def test_feed_batch_preview_retains_stable_snapshot(self):
  c=self.add();episode={'id':'raw-id','guid':'guid','title':'标题','audio_url':'https://example.org/a.mp3','transcripts':[]}
  result={'identity':'feed','title':'节目','status':'ok','items':[{'id':'stable-id','title':'标题','url':c['url'],'episode_guid':'guid','episode_id':'raw-id','episode_snapshot':episode}]}
  with patch.object(sources,'enumerate_source',return_value=result):sub.check(c['id'],20)
  seq=sub.feed()[0]['seq']
  with patch('article_fetch.stream',side_effect=AssertionError('不应重复取Feed')):
   preview=sub.batch(sub.Extract(seqs=[seq]));again=link_batches.preview(link_batches.Preview(rows=[link_batches.Row(text=c['url'],feed_seq=seq)]))
  self.assertEqual(preview['items'][0]['status'],'waiting');self.assertEqual(again['items'][0]['plan']['episode']['guid'],'guid');self.assertEqual(store.all_tasks(),[])

 def test_topic_not_subscribable_and_restart_does_not_auto_check(self):
  self.assertEqual(self.c.post('/api/subscriptions/channels',json={'url':'Python'}).status_code,400)
  c=self.add();c['status']='checking';sub.save(c);sub.recover();self.assertEqual(sub.get(c['id'])['status'],'error');sub.EXECUTOR.submit.assert_not_called()

 def test_confirmed_topic_subscription_dedupes_video_ids(self):
  r=self.c.post('/api/subscriptions/channels',json={'url':'Ｐｙｔｈｏｎ','confirm_topic':True});self.assertEqual(r.status_code,200)
  c=r.json();self.assertEqual(c['platform'],'douyin_topic');self.assertEqual(c['query'],'Python')
  self.assertEqual(self.c.post('/api/subscriptions/channels',json={'url':'python','confirm_topic':True}).json()['id'],c['id'])
  sub.EXECUTOR.submit.assert_not_called()
  result={'identity':'Python','title':'Python话题','status':'ok','items':[{'id':'video-1','title':'第一条','url':'https://www.douyin.com/video/1234567890123456'}]}
  with patch.object(sources,'enumerate_source',return_value=result) as adapter:
   sub.check(c['id'],10);sub.check(c['id'],10);adapter.assert_called_with('douyin_topic','Python',10)
  self.assertEqual(len(sub.feed()),1);seq=sub.feed()[0]['seq'];sub.seen(sub.Seen(channel_id=c['id']))
  result['items'].insert(0,{'id':'video-2','title':'新条目','url':'https://www.douyin.com/video/2234567890123456'})
  with patch.object(sources,'enumerate_source',return_value=result):sub.check(c['id'],10)
  self.assertEqual(len(sub.feed()),1);self.assertGreater(sub.feed()[0]['seq'],seq);self.assertEqual(sub.feed()[0]['id'],'video-2')
if __name__=='__main__':unittest.main()
