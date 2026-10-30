import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import httpx
import link_ingest,podcast_pages,platform_urls,store,xhs_auth,xhs_ingest

class PlatformTests(unittest.TestCase):
 def test_identify_and_canonical_short_hosts(self):
  for url,kind in [('https://vm.tiktok.com/abc','tiktok'),('https://vxtiktok.com/@u/video/123','tiktok'),('https://x.com/u/status/123','twitter'),('https://www.xiaoyuzhoufm.com/episode/'+'a'*24,'xiaoyuzhou'),('https://open.spotify.com/episode/abc','spotify'),('https://xhslink.com/a/abc','xiaohongshu')]:self.assertEqual(link_ingest.platform(url),kind)
  self.assertEqual(platform_urls.canonical('https://vxtiktok.com/@u/video/123'),'https://www.tiktok.com/@u/video/123')
  self.assertEqual(platform_urls.canonical('https://x.com/u/status/123'),'https://twitter.com/u/status/123')
  with self.assertRaises(ValueError):platform_urls.canonical('https://x.com/u')
 def test_public_episode_and_preview_rejection(self):
  ident='a'*24;url='https://www.xiaoyuzhoufm.com/episode/'+ident
  data={'props':{'pageProps':{'episode':{'eid':ident,'id':ident,'title':'节目','enclosure':{'url':'https://media.xyzcdn.net/audio.mp3'},'duration':30}}}}
  raw='<script id="__NEXT_DATA__">'+json.dumps(data)+'</script>'
  with patch.object(podcast_pages.article_fetch,'public_url',side_effect=lambda x:x):
   value=podcast_pages.parse_page(raw,url,'xiaoyuzhou');self.assertEqual(value['duration_seconds'],30)
  with self.assertRaisesRegex(ValueError,'RSS'):podcast_pages.parse_page('<script id="__NEXT_DATA__">'+json.dumps({'id':'abc','audioPreview':{'url':'https://cdn/preview.mp3'}})+'</script>','https://open.spotify.com/episode/abc','spotify')
  with self.assertRaisesRegex(ValueError,'音乐'),patch.object(podcast_pages.article_fetch,'fetch',side_effect=AssertionError('music must not fetch')):podcast_pages.episode_page('https://open.spotify.com/track/abc','spotify')
 def test_xhs_redirect_rejects_foreign_domain(self):
  with self.assertRaises(ValueError):xhs_ingest.resolve('https://xiaohongshu.com.evil.example/explore/'+'a'*24)
 def test_xhs_api_cookie_only_fixed_domain_and_no_redirect(self):
  requests=[]
  class Client:
   def __init__(self,**kw):self.kw=kw
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def request(self,method,url,**kw):requests.append((method,url,kw,self.kw));return httpx.Response(200,json={'success':True,'data':{}},request=httpx.Request(method,url))
  with patch.object(xhs_auth.httpx,'Client',Client):
   xhs_auth.xhs_api('/api/sns/web/v1/user/selfinfo',cookies=[{'name':'a1','value':'fixture'}])
  self.assertEqual(requests[0][1],'https://edith.xiaohongshu.com/api/sns/web/v1/user/selfinfo');self.assertFalse(requests[0][3]['follow_redirects'])
  with self.assertRaises(ValueError):xhs_auth.xhs_api('https://cdn.example/file',cookies=[])
 def test_xhs_cookie_filter_and_epoch_protect(self):
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)),patch.object(xhs_auth,'protect'):
   self.assertFalse(xhs_auth.save_cookies([],epoch=xhs_auth.LOGIN_EPOCH-1))
   xhs_auth.save_cookies([{'domain':'.xiaohongshu.com','name':'a1','value':'fixture'},{'domain':'evil.example','name':'a','value':'bad'}])
   self.assertEqual(len(xhs_auth.read_cookies()),1)

class NativeExtractorTests(unittest.TestCase):
 def test_subtitles_skip_download_and_preserve_proxy_environment(self):
  import io,yt_dlp
  class Y:
   def __init__(self,opts):self.opts=opts;assert 'proxy' not in opts
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def extract_info(self,*a,**kw):return {'automatic_captions':{'en':[{'ext':'json3','url':'https://cdn.example/sub'}]}}
   def urlopen(self,url):return io.BytesIO(b'{"events":[{"tStartMs":0,"dDurationMs":1000,"segs":[{"utf8":"hello"}]}]}')
   def download(self,*a):raise AssertionError('subtitle fast path must not download')
  with patch.object(yt_dlp,'YoutubeDL',Y),tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
   _,result,media=link_ingest.ytdlp('https://www.tiktok.com/@u/video/123',Path(tmp),'auto')
  self.assertEqual(result['engine'],'publisher_subtitles');self.assertIsNone(media)
 def test_tweet_text_and_network_errors_are_distinct(self):
  import yt_dlp
  class Y:
   def __init__(self,*a):pass
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def extract_info(self,*a,**kw):return {'title':'text only'}
  with patch.object(yt_dlp,'YoutubeDL',Y),tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
   with self.assertRaisesRegex(ValueError,'仅支持视频推文'):link_ingest.ytdlp('https://twitter.com/u/status/123',Path(tmp),'auto')
   with patch.object(Y,'extract_info',side_effect=yt_dlp.utils.DownloadError('network unavailable')):
    with self.assertRaises(yt_dlp.utils.DownloadError):link_ingest.ytdlp('https://twitter.com/u/status/123',Path(tmp),'auto')
 def test_signed_share_tokens_do_not_split_identity(self):
  def args(token):return SimpleNamespace(url='https://www.xiaohongshu.com/explore/'+'a'*24+'?xsec_token='+token,language='auto')
  self.assertEqual(link_ingest.prepare(args('one'))['ident'],link_ingest.prepare(args('two'))['ident'])
 def test_private_platform_rejected_before_auth_in_core(self):
  args=SimpleNamespace(url='https://www.xiaohongshu.com/explore/'+'a'*24,language='auto',allowed=['youtube','rss'])
  with patch.object(xhs_ingest,'resolve',side_effect=AssertionError('must not authenticate')):
   with self.assertRaisesRegex(ValueError,'此版本不支持'):link_ingest.prepare(args)
 def test_xhs_logout_removes_owned_state_and_invalidates_writer(self):
  import asyncio
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)):
   xhs_auth.cookie_path().parent.mkdir();xhs_auth.cookie_path().write_text('[]');xhs_auth.profile_path().mkdir();epoch=xhs_auth.LOGIN_EPOCH
   asyncio.run(xhs_auth.logout());self.assertFalse(xhs_auth.cookie_path().exists());self.assertFalse(xhs_auth.profile_path().exists())
   self.assertFalse(xhs_auth.save_cookies([],epoch=epoch))

if __name__=='__main__':unittest.main()
