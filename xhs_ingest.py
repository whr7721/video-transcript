"""Own single-note parser; authenticated API only, credential-free media requests."""
import json,re
from urllib.parse import urlsplit,urljoin,parse_qs
import httpx
import article_fetch,articles,image_documents,store,xhs_auth

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
 ident,card=detail(task['url']);metadata.update(title=card.get('title') or (card.get('desc') or '小红书笔记')[:80],description=card.get('desc',''),publishedDate=card.get('time'),platform='xiaohongshu')
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
 checkpoint=directory/'xhs-article.json';old=json.loads(checkpoint.read_text()) if checkpoint.is_file() else {}
 item=articles.get(old.get('id','')) if old else None
 if not item:
  item=image_documents.create(metadata['title'],len(images),source_url=task['url'],description=card.get('desc',''));store.atomic_json(checkpoint,{'id':item['id']})
 image_documents.update(item['id'],image_status='fetching',status='running')
 for index,image in enumerate(images):
  block=next(b for b in articles.get(item['id'])['blocks'] if b.get('type')=='image' and b.get('page')==index+1)
  if block.get('asset_status')=='saved':continue
  url=image.get('url_default') or next((r.get('url') for r in image.get('info_list',[]) if r.get('url')),None)
  if not url:raise ValueError('笔记图片地址缺失，未将部分内容冒充完整')
  data,_,_=article_fetch.fetch(url,limit=image_documents.MAX_IMAGE_BYTES,referer='https://www.xiaohongshu.com/')
  image_documents.put_image(item['id'],index,data)
 update(stage='transcribing',message='正在本地图集OCR')
 image_documents.run_ocr(item['id']);item=articles.get(item['id'])
 if item.get('completeness')=='partial' or item.get('image_status')=='failed':raise ValueError('图集OCR未完整完成，请检查本地OCR组件后重试')
 blocks=[b for b in item['blocks'] if b.get('text','').strip() and b.get('type')!='image']
 text='\n\n'.join(b['text'] for b in blocks)
 if not text.strip():raise ValueError('图集未识别到可读文字')
 metadata['article_id']=item['id'];return {'text':text,'segments':[{'text':b['text']} for b in blocks],'engine':'image_ocr','timing_precision':'none'}

def register():
 import link_ingest
 link_ingest.INGESTERS['xiaohongshu']=ingest
