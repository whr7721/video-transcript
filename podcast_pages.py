"""Single public episode pages; previews and protected streams are never full episodes."""
import hashlib,json,re,httpx
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import article_fetch

def parse_page(raw,url,kind):
 p=urlsplit(url);pattern=r'/episode/([a-fA-F0-9]{24})/?' if kind=='xiaoyuzhou' else r'/(?:intl-[a-z]+/)?episode/([A-Za-z0-9]+)/?'
 match=re.fullmatch(pattern,p.path)
 if not match:raise ValueError('仅支持Spotify播客单集，不支持音乐类内容' if kind=='spotify' else '请提供小宇宙单集页链接')
 ident=match[1];soup=BeautifulSoup(raw,'html.parser');objects=[]
 for script in soup.find_all('script'):
  if script.get('id')=='__NEXT_DATA__' or script.get('type')=='application/ld+json':
   try:objects.append(json.loads(script.string or script.get_text()))
   except ValueError:continue
 def walk(v):
  if isinstance(v,dict):
   yield v
   for x in v.values():yield from walk(x)
  elif isinstance(v,list):
   for x in v:yield from walk(x)
 candidates=[]
 for obj in objects:
  for row in walk(obj):
   identity=str(row.get('id') or row.get('eid') or row.get('_id') or row.get('uri') or row.get('@id') or '')
   if ident not in identity:continue
   if row.get('isDRM') or row.get('drm'):continue
   enclosure=row.get('enclosure') or {};audio=enclosure.get('url') if isinstance(enclosure,dict) else None
   if not audio:audio=row.get('contentUrl') if row.get('@type') in {'PodcastEpisode','AudioObject'} else None
   if isinstance(audio,str) and urlsplit(audio).scheme=='https' and not re.search('preview|\.m3u8|\.mpd',audio,re.I):candidates.append((row,audio))
 if not candidates:raise ValueError('请在小宇宙获取该播客的 RSS 地址订阅' if kind=='xiaoyuzhou' else 'Spotify未提供完整公开音频直链（可能为DRM或仅有预览）；请获取该播客的 RSS 地址订阅')
 row,audio=candidates[0];article_fetch.public_url(audio)
 return {'id':hashlib.sha256((kind+':'+ident).encode()).hexdigest()[:24],'guid':kind+':'+ident,'title':str(row.get('title') or row.get('name') or '播客单集')[:500],'published':row.get('pubDate') or row.get('datePublished'),'duration_seconds':row.get('duration') if isinstance(row.get('duration'),(int,float)) else None,'audio_url':audio,'transcripts':[],'chapters_url':None,'importable':True}

def episode_page(url,kind):
 # Reject Spotify music before any request.
 if kind=='spotify' and not re.fullmatch(r'/(?:intl-[a-z]+/)?episode/[A-Za-z0-9]+/?',urlsplit(url).path):raise ValueError('仅支持Spotify播客单集，不支持音乐类内容')
 try:raw,_,_=article_fetch.fetch(url,limit=4_000_000);return parse_page(raw,url,kind)
 except (ValueError,httpx.HTTPError) as e:
  if 'RSS' in str(e) or '音乐' in str(e):raise
  raise ValueError('请在小宇宙获取该播客的 RSS 地址订阅' if kind=='xiaoyuzhou' else 'Spotify单集暂不可读取；请获取该播客的 RSS 地址订阅') from None
