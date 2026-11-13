"""Metadata enumeration shared by batch expansion and subscriptions."""
import hashlib,json,re,subprocess,time,uuid,os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlencode
import httpx,store

def normalize(text):
 """从粘贴文本里取出唯一链接。"""
 urls=re.findall(r'https://[^\s<>"\']+',text)
 if len(urls)!=1:raise ValueError('请一次粘贴一个HTTPS链接')
 return urls[0].rstrip('，。；！）)]}')

def identify(text):
 text=text.strip()
 if '://' not in text:raise ValueError('请提供完整链接（抖音主页 / RSS / 频道）')
 url=normalize(text)
 from link_ingest import platform
 platform(url)
 p=urlsplit(url);host=p.hostname or ''
 if host in {'youtube.com','www.youtube.com','m.youtube.com'} and (p.path.startswith(('/@','/channel/','/c/','/user/')) or p.path=='/playlist'):return 'youtube',url
 if host=='space.bilibili.com' and re.match(r'^/\d+',p.path):return 'bilibili',url
 if host in {'www.douyin.com','douyin.com'} and p.path.startswith('/user/'):return 'douyin',url
 return 'single',url


def metadata_process(command,env,cwd):
 process=subprocess.Popen(command,env=env,cwd=cwd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
 try:process.wait(timeout=300)
 except subprocess.TimeoutExpired:
  if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
  else:process.kill()
  process.wait(timeout=15)

def enumerate_source(kind,url,limit=20,*,_directory=None,_max_duration_sec=600):
 if not 1<=limit<=100:raise ValueError('条数须在1到100之间')
 if kind=='rss':
  import article_fetch,podcast_feed
  chunks=[];article_fetch.stream(url,chunks.append,podcast_feed.MAX_FEED_BYTES,budget=30);feed=podcast_feed.parse(b''.join(chunks),url)
  return {'identity':feed['feed_url'],'title':feed['title'],'items':[{'id':hashlib.sha256((feed['feed_url']+'\n'+e['guid']).encode()).hexdigest()[:24] if e.get('guid') else e['id'],'episode_guid':e.get('guid'),'episode_snapshot':e,'title':e['title'],'url':url,'published':e['published'],'duration':e['duration_seconds'],'episode_id':e['id']} for e in feed['episodes'][:limit]],'status':'ok'}
 if kind=='youtube':
  import yt_dlp
  p=urlsplit(url)
  if p.path!='/playlist':url=url.split('?')[0].rstrip('/').removesuffix('/videos').removesuffix('/shorts')+'/videos'
  with yt_dlp.YoutubeDL({'extract_flat':True,'skip_download':True,'playlist_items':f'1:{limit}','quiet':True,'socket_timeout':20,'retries':1}) as y:info=y.extract_info(url,download=False)
  rows=[{'id':e['id'],'title':e.get('title') or '未命名视频','url':'https://www.youtube.com/watch?v='+e['id'],'published':e.get('timestamp') or e.get('upload_date'),'duration':e.get('duration')} for e in list(info.get('entries') or [])[:limit] if e and e.get('id')]
  return {'identity':str(info.get('id') or url),'title':info.get('title') or url,'items':rows,'status':'ok'}
 if kind=='bilibili':
  import bilibili_auth as auth
  state,cookies,nav=auth.validated()
  if state['status']!='logged_in':raise ValueError('B站需要有效登录态，请在设置登录后重试')
  mid=re.match(r'^/(\d+)',urlsplit(url).path)[1];rows=[];title='B站 UP '+mid
  for page in range(1,(limit+29)//30+1):
   raw=auth.bilibili_api_get('/x/space/wbi/arc/search',cookies=cookies,params=auth.wbi_signed({'mid':mid,'pn':page,'ps':30,'order':'pubdate'},nav))
   if raw.get('code')!=0:raise ValueError('B站空间检查失败或触发风控，请稍后手动重试')
   videos=((raw.get('data') or {}).get('list') or {}).get('vlist') or []
   for e in videos:
    title=e.get('author') or title;rows.append({'id':e['bvid'],'title':e['title'],'url':'https://www.bilibili.com/video/'+e['bvid'],'published':e.get('created'),'duration':e.get('length')})
   if len(videos)<30:break
   time.sleep(2)
  return {'identity':mid,'title':title,'items':rows[:limit],'status':'ok'}
 if kind=='douyin_favorites':
  from douyin_session_guard import session_guard
  from pipeline import MC_PY,ROOT
  from session import prepare_session
  from douyin_favorites import metadata
  folder=store.DATA/'enumerations'/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=True);output=folder/'result.json'
  with session_guard():
   prepare_session()
   env={k:v for k,v in os.environ.items() if k.lower() not in {'http_proxy','https_proxy','all_proxy'}}
   env.update(SHIWEN_DATA_DIR=str(store.DATA),SHIWEN_SESSION_LOCK_HELD='1')
   metadata_process([str(MC_PY),'-B','-X','utf8',str(ROOT/'extractor.py'),'favorites','--limit',str(limit),'--output',str(output)],env,ROOT)
   if not output.exists():raise ValueError('收藏读取未完成，请检查登录状态后重试')
   result=json.loads(output.read_text(encoding='utf8'))
  if result.get('status')!='ok':raise ValueError(result.get('error') or '收藏读取失败，请检查登录状态后重试')
  return metadata(result)
 if kind=='douyin':
  from douyin_session_guard import session_guard
  from pipeline import MC_PY,ROOT
  from session import prepare_session
  from batch_rules import creator_id
  ident=creator_id(url)
  if not ident:raise ValueError('请输入有效抖音博主主页')
  folder=Path(_directory) if _directory else store.DATA/'enumerations'/uuid.uuid4().hex
  folder.mkdir(parents=True,exist_ok=True);output=folder/('listing.json' if _directory else 'result.json')
  with session_guard():
   prepare_session()
   command=[str(MC_PY),'-B','-X','utf8',str(ROOT/'extractor.py'),'creator','--sec-uid',ident,'--limit',str(limit),'--max-duration-sec',str(_max_duration_sec),'--output',str(output)]
   if _directory is None:command.append('--metadata-only')
   env={k:v for k,v in os.environ.items() if k.lower() not in {'http_proxy','https_proxy','all_proxy'}}
   env.update(SHIWEN_DATA_DIR=str(store.DATA),SHIWEN_SESSION_LOCK_HELD='1')
   metadata_process(command,env,ROOT)
   if not output.exists():raise ValueError('抖音列表组件未完成，请检查安装依赖或登录状态')
   result=json.loads(output.read_text(encoding='utf8'))
  status=result.get('status')
  def stat(e):
   s=e.get('statistics') or {}
   return {'likes':s.get('digg_count'),'collects':s.get('collect_count'),
           'comments':s.get('comment_count'),'shares':s.get('share_count'),'top':bool(e.get('is_top'))}
  rows=[{'id':str(e['aweme_id']),'title':e.get('desc') or '未命名视频','url':'https://www.douyin.com/video/'+str(e['aweme_id']),'published':e.get('create_time'),'duration':(e.get('video',{}).get('duration') or 0)/1000,**stat(e)} for e in result.get('posts',[]) if isinstance(e.get('video'),dict) and not e.get('images')]
  title=result.get('author') or next((p.get('author',{}).get('nickname') for p in result.get('posts',[]) if p.get('author',{}).get('nickname')),None) or url
  if status not in {'ok','partial'} and not rows:raise ValueError('抖音检查未完成：'+str(status)+'；请检查登录或稍后重试')
  return {'identity':ident,'title':title,'items':rows[:limit],'total':result.get('total'),'raw_count':len(result.get('posts',[])),'excluded_nonvideo':len(result.get('posts',[]))-len(rows),'status':'ok' if status=='ok' else 'partial','message':result.get('error') or result.get('stopped_reason') or ('仅返回部分结果，请稍后手动检查' if status!='ok' else None)}
 raise ValueError('不支持的源类型')
