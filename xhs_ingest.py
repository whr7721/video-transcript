"""Own single-note parser; authenticated API only, credential-free media requests."""
import json,re
from urllib.parse import urlsplit,urljoin,parse_qs
import httpx
import article_fetch,image_documents,store,xhs_auth

def resolve(url):
 for _ in range(6):
  p=urlsplit(url)
  if p.scheme!='https' or p.username or p.password or p.port not in (None,443):raise ValueError('请输入小红书HTTPS链接')
  if p.hostname in {'xiaohongshu.com','www.xiaohongshu.com'}:
   m=re.fullmatch(r'/(?:explore|discovery/item)/([a-fA-F0-9]{24})/?',p.path)
   if not m:raise ValueError('请提供单条小红书笔记链接')
   return url,m[1]
  if p.hostname not in {'xhslink.com','www.xhslink.com'}:raise ValueError('短链没有指向小红书笔记')
  with httpx.Client(trust_env=False,timeout=15,follow_redirects=False) as c:r=c.get(url,headers={'User-Agent':'Mozilla/5.0'})
  if r.status_code not in {301,302,303,307,308} or not r.headers.get('location'):raise ValueError('小红书短链暂不可展开，请复制完整笔记链接')
  url=urljoin(url,r.headers['location'])
 raise ValueError('小红书短链跳转过多')

def detail(url):
 url,ident=resolve(url);state,cookies,_=xhs_auth.validated()
 if state['status']!='logged_in':raise ValueError('请先在设置扫码登录小红书；失效时请重新登录')
 q=parse_qs(urlsplit(url).query)
 response=xhs_auth.xhs_api('/api/sns/web/v1/feed',cookies=cookies,payload={'source_note_id':ident,'image_formats':['jpg','webp'],'extra':{'need_body_topic':'1'},'xsec_source':(q.get('xsec_source',['pc_feed'])[0] or 'pc_feed'),'xsec_token':q.get('xsec_token',[''])[0]})
 items=(response.get('data') or {}).get('items') or []
 card=next((r.get('note_card') for r in items if r.get('id')==ident or (r.get('note_card') or {}).get('note_id')==ident),None)
 if not card:raise ValueError('未获取到对应笔记；请复制含xsec_token的完整分享链接或在平台完成验证')
 return ident,card

def ingest(task,update,directory,metadata):
 ident,card=detail(task['url']);metadata.update(channelId=(card.get('user') or {}).get('user_id'),channelTitle=(card.get('user') or {}).get('nickname'),title=card.get('title') or (card.get('desc') or '小红书笔记')[:80],description=card.get('desc',''),publishedDate=card.get('time'),platform='xiaohongshu')
 store.atomic_json(directory/'xhs-note.json',{'note_id':ident,'type':card.get('type'),'title':metadata['title']})
 if card.get('type')=='video':
  streams=((card.get('video') or {}).get('media') or {}).get('stream') or {}
  urls=[v.get('master_url') for fmt in streams.values() if isinstance(fmt,list) for v in fmt if v.get('master_url')]
  if not urls:raise ValueError('此视频没有可访问的完整媒体地址')
  video=directory/'original.mp4'
  if not video.is_file():
   update(stage='downloading',message='正在下载小红书视频（不发送Cookie）')
   with video.with_suffix('.part').open('wb') as out:article_fetch.stream(urls[0],out.write,1_000_000_000,budget=300)
   video.with_suffix('.part').replace(video)
  from media_io import extract_audio,probe_media
  from transcribe import local_transcribe
  duration=probe_media(video)
  if duration>10800:raise ValueError('最多支持3小时')
  metadata['duration']=duration;audio=directory/'audio.wav';extract_audio(video,audio)
  update(stage='transcribing',message='正在本地转写小红书视频')
  return local_transcribe(audio,directory/'local_chunks',lambda f,n,t:update(progress=f,segment_count=n),language=task.get('language','auto'))
 images=card.get('image_list') or []
 if not images:raise ValueError('笔记没有可提取的视频或图片')
 urls=[]
 for image in images:
  url=image.get('url_default') or next((r.get('url') for r in image.get('info_list',[]) if r.get('url')),None)
  urls.append([url] if isinstance(url,str) else [])
 text,blocks,article_id=image_documents.to_document(metadata['title'],urls,source_url=task['url'],checkpoint=directory/'xhs-article.json',referer='https://www.xiaohongshu.com/',description=card.get('desc',''),progress=update)
 metadata['article_id']=article_id;return {'text':text,'segments':[{'text':b['text']} for b in blocks],'engine':'image_ocr','timing_precision':'none'}

def register():
 import link_ingest
 link_ingest.INGESTERS['xiaohongshu']=ingest
