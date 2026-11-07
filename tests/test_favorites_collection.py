import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch,AsyncMock,MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,subscriptions as s,source_enumeration,link_batches,douyin_favorites as f

class CollectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');root=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3'),patch.object(s.EXECUTOR,'submit')]
  for p in self.patches:p.start()
  store.init();s.init();app=FastAPI();app.include_router(s.router);self.client=TestClient(app)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def source(self):return self.client.post('/api/subscriptions/favorites').json()
 def result(self,ids=('1234567890123456',),identity='account-A'):
  return {'identity':identity,'title':'收藏','status':'ok','items':[{'id':x,'title':x,'url':'https://www.douyin.com/video/'+x} for x in ids]}
 def check(self,c,ids=('1234567890123456',),identity='account-A'):
  with patch.object(source_enumeration,'enumerate_source',return_value=self.result(ids,identity)):s.check(c['id'],20)
 def enable(self,c,**kw):return self.client.put('/api/subscriptions/channels/'+c['id']+'/automation',json={'enabled':True,'auto_extract':True,**kw})
 def test_explicit_add_dedup_no_requests(self):
  c=self.source();self.assertEqual(c['id'],self.source()['id']);s.EXECUTOR.submit.assert_not_called();self.assertEqual(s.feed(),[])
 def test_first_check_must_precede_auto(self):
  c=self.source();self.assertEqual(self.enable(c).status_code,400);self.check(c);self.assertEqual(self.enable(c).status_code,200);self.assertFalse(s.feed()[0]['auto_pending']);self.assertEqual(link_batches.all_batches(),[])
 def test_new_items_existing_batch_and_repeated_check(self):
  c=self.source();self.check(c);self.enable(c)
  ids=('2234567890123456','1234567890123456');self.check(c,ids);self.check(c,ids)
  batches=link_batches.all_batches();self.assertEqual(len(batches),1);self.assertEqual(batches[0]['status'],'active');self.assertEqual(len(batches[0]['items']),1);self.assertFalse(batches[0]['items'][0]['summarize']);self.assertEqual(s.get(c['id'])['auto_count'],1)
 def test_daily_cap_pending_and_next_day(self):
  c=self.source();self.check(c);self.enable(c,daily_limit=1);self.check(c,('2234567890123456','3234567890123456'))
  self.assertEqual(len(link_batches.all_batches()),1);self.assertEqual(sum(r['auto_pending'] for r in s.feed(False)),1)
  channel=s.get(c['id']);channel['auto_day']='2000-01-01';s.save(channel);s.dispatch_auto(c['id']);self.assertEqual(len(link_batches.all_batches()),2)
 def test_account_switch_rejected_no_feed_pollution(self):
  c=self.source();self.check(c);self.check(c,('2234567890123456',),'account-B');self.assertEqual(len(s.feed()),1);self.assertIn('账号已变化',s.get(c['id'])['error'])
 def test_cancel_favorite_keeps_content(self):
  c=self.source();self.check(c);self.check(c,());self.assertEqual(len(s.feed(False)),1)
 def test_tick_only_due_enabled_and_future_deadline(self):
  c=self.source();s.tick(10**10);s.EXECUTOR.submit.assert_not_called()
  self.client.put('/api/subscriptions/channels/'+c['id']+'/automation',json={'enabled':True,'interval_minutes':60})
  s.tick(10**10);self.assertEqual(s.EXECUTOR.submit.call_count,1);self.assertEqual(s.get(c['id'])['next_check'],10**10+3600);s.tick(10**10);self.assertEqual(s.EXECUTOR.submit.call_count,1)
 def test_recover_due_once_and_disabled_never_runs(self):
  c=self.source();self.check(c);self.enable(c);channel=s.get(c['id']);channel.update(status='checking',next_check=1);s.save(channel);s.recover();s.tick(2);self.assertEqual(s.EXECUTOR.submit.call_count,1)
 def test_draft_reservation_restarts_same_batch(self):
  c=self.source();self.check(c);self.enable(c)
  with patch.object(link_batches,'control',side_effect=RuntimeError('interrupted')):self.check(c,('2234567890123456',))
  b=link_batches.all_batches();self.assertEqual(len(b),1);self.assertEqual(b[0]['status'],'draft');s.dispatch_auto(c['id']);self.assertEqual(len(link_batches.all_batches()),1);self.assertEqual(link_batches.get(b[0]['id'])['status'],'active')
 def test_public_reject_and_interval_bounds(self):
  c=self.source();self.assertEqual(self.enable(c,interval_minutes=1).status_code,422)
  with patch.dict('os.environ',{'SHIWEN_PUBLIC':'1'}):self.assertEqual(self.client.post('/api/subscriptions/favorites').status_code,403);s.tick(10**10)
 def test_malformed_or_auth_errors_not_empty_success(self):
  for raw in [{},{'status_code':8,'has_more':0,'aweme_list':[]},{'has_more':1,'aweme_list':None}]:
   with self.assertRaises(RuntimeError):f.parse_page(raw)
 def test_images_metadata_and_no_cookie(self):
  result=f.metadata({'account':'account','posts':[{'aweme_id':'1234567890123456','images':[{}],'author':{'nickname':'作者'},'desc':'图文'}]});self.assertIn('/note/',result['items'][0]['url']);self.assertNotIn('cookie',json.dumps(result))

 def test_full_new_window_warns_not_claim_complete(self):
  c=self.source();self.check(c)
  result=self.result(('2234567890123456',));result['window_has_more']=True
  with patch.object(source_enumeration,'enumerate_source',return_value=result):s.check(c['id'],20)
  self.assertEqual(s.get(c['id'])['status'],'partial');self.assertIn('窗口',s.get(c['id'])['error'])

class BrowserPaginationTests(unittest.IsolatedAsyncioTestCase):
 async def test_collection_paginates_dedupes_and_binds_account(self):
  page=AsyncMock();tab=AsyncMock();tab.count.return_value=0;page.get_by_text=MagicMock(return_value=tab);context=AsyncMock();context.cookies.return_value=[{'name':'sessionid','value':'not-logged'},{'name':'uid_tt','value':'owner'}]
  page.evaluate.side_effect=[{'has_more':True,'cursor':20,'aweme_list':[{'aweme_id':'1234567890123456'}]}, {'has_more':False,'cursor':40,'aweme_list':[{'aweme_id':'1234567890123456'},{'aweme_id':'2234567890123456'}]}]
  with patch.object(f.asyncio,'sleep',new_callable=AsyncMock):r=await f.collect(page,context,3)
  self.assertEqual(len(r['posts']),2);self.assertFalse(r['has_more']);self.assertNotIn('owner',r['account']);self.assertEqual(page.evaluate.call_count,2)
 async def test_missing_login_never_returns_empty_success(self):
  page=AsyncMock();tab=AsyncMock();tab.count.return_value=0;page.get_by_text=MagicMock(return_value=tab);context=AsyncMock();context.cookies.return_value=[]
  with patch.object(f.asyncio,'sleep',new_callable=AsyncMock):
   with self.assertRaisesRegex(RuntimeError,'登录'):await f.collect(page,context,10)
 async def test_stuck_cursor_is_error(self):
  page=AsyncMock();tab=AsyncMock();tab.count.return_value=0;page.get_by_text=MagicMock(return_value=tab);context=AsyncMock();context.cookies.return_value=[{'name':'sessionid','value':'test'},{'name':'uid_tt','value':'owner'}]
  page.evaluate.return_value={'has_more':True,'cursor':0,'aweme_list':[]}
  with patch.object(f.asyncio,'sleep',new_callable=AsyncMock):
   with self.assertRaisesRegex(RuntimeError,'分页'):await f.collect(page,context,10)

if __name__=='__main__':unittest.main()
