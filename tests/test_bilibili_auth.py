import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import store,bilibili_auth as auth,link_private,link_ingest

class BilibiliLogin(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(auth,'protect')]
  for p in self.patches:p.start()
  auth.CACHE.clear();auth.LOGIN=None;auth.LOGIN_ERROR=None
  app=FastAPI();app.include_router(auth.router);self.client=TestClient(app)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def cookie(self):auth.save_cookies([{'name':'SESSDATA','value':'fixture-secret','domain':'.bilibili.com','path':'/'}])
 def test_no_cookie_no_network(self):
  with patch.object(auth,'bilibili_api_get',side_effect=AssertionError('不应联网')):self.assertEqual(self.client.get('/api/bilibili/status').json()['status'],'not_logged_in')
 def test_valid_expired_network_error_and_redacted_status(self):
  self.cookie()
  with patch.object(auth,'bilibili_api_get',return_value={'code':0,'data':{'isLogin':True}}):
   r=self.client.get('/api/bilibili/status');self.assertEqual(r.json()['status'],'logged_in');self.assertNotIn('fixture-secret',r.text)
  auth.CACHE.clear()
  with patch.object(auth,'bilibili_api_get',return_value={'code':-101,'data':{'isLogin':False}}):self.assertEqual(auth.validated()[0]['status'],'expired');self.assertEqual(auth.validated()[1],[])
  auth.CACHE.clear()
  with patch.object(auth,'bilibili_api_get',return_value={'code':-412}):self.assertEqual(auth.validated()[0]['status'],'unknown')
  auth.CACHE.clear()
  with patch.object(auth,'bilibili_api_get',side_effect=httpx.ConnectError('fixture-secret')):
   r=self.client.get('/api/bilibili/status');self.assertEqual(r.json()['status'],'unknown');self.assertNotIn('fixture-secret',r.text)
 def test_logout_removes_cookie_profile_and_blocks_late_save(self):
  self.cookie();auth.profile_path().mkdir();(auth.profile_path()/'Cookies').write_text('fixture')
  old=auth.LOGIN_EPOCH;r=self.client.delete('/api/bilibili/login');self.assertEqual(r.status_code,200)
  self.assertFalse(auth.cookie_path().exists());self.assertFalse(auth.profile_path().exists());self.assertFalse(auth.save_cookies([],old))
 def test_logout_refuses_profile_outside_data(self):
  with patch.object(auth,'profile_path',return_value=self.root.parent/'not-owned-profile'):
   self.assertEqual(self.client.delete('/api/bilibili/login').status_code,409)

 def test_login_singleton_cancel(self):
  async def browser(epoch):await asyncio.Event().wait()
  with patch.object(auth,'login_browser',browser),TestClient(self.client.app) as c:
   self.assertEqual(c.post('/api/bilibili/login').status_code,200);task=auth.LOGIN
   c.post('/api/bilibili/login');self.assertIs(auth.LOGIN,task)
   self.assertEqual(c.delete('/api/bilibili/login').status_code,200);self.assertTrue(task.cancelled())
 def test_authenticated_precheck_bypasses_ytdlp_and_cdn_receives_no_cookie(self):
  info={'webpage_url':'https://www.bilibili.com/video/BV1GJ411x7h7'};calls=[]
  cookies=[{'name':'SESSDATA','value':'fixture-secret','domain':'.bilibili.com'}]
  def api(path,**kw):
   calls.append((path,kw.get('cookies')))
   return {'code':0,'data':{'cid':1,'title':'字幕','duration':1}} if path.endswith('/view') else {'data':{'subtitle':{'subtitles':[{'lan':'zh-CN','subtitle_url':'https://aisubtitle.hdslb.com/test'}]}}}
  def cdn(request):
   self.assertNotIn('cookie',request.headers);return httpx.Response(200,json={'body':[{'from':0,'to':1,'content':'字幕快路'}]})
  original=httpx.Client
  def client(**kw):return original(transport=httpx.MockTransport(cdn),**kw)
  with patch.object(auth,'validated',return_value=({'status':'logged_in'},cookies,{})),patch.object(auth,'bilibili_api_get',side_effect=api),patch.object(link_private.httpx,'Client',client),patch.dict(link_ingest.PRECHECKS,{'bilibili':link_private.probe}),patch('yt_dlp.YoutubeDL',side_effect=AssertionError('不可调用媒体提取器')):
   _,r,media=link_ingest.ytdlp(info['webpage_url'],self.root,'auto');self.assertEqual(r['engine'],'bilibili_subtitles');self.assertIsNone(media)
  self.assertTrue(all(c[1]==cookies for c in calls))
 def test_empty_authenticated_list_retries_anonymous(self):
  calls=[];cookies=[{'name':'SESSDATA','value':'fixture','domain':'.bilibili.com'}]
  def api(path,**kw):
   calls.append(kw.get('cookies'));return {'data':{'cid':1}} if path.endswith('/view') else {'data':{'subtitle':{'subtitles':[]}}}
  with patch.object(auth,'validated',return_value=({},cookies,{})),patch.object(auth,'bilibili_api_get',side_effect=api):self.assertIsNone(link_private.bili_subtitles({'bvid':'BVtest'},'auto'))
  self.assertIn([],calls)

if __name__=='__main__':unittest.main()
