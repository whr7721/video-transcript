"""Private adapters; never imported or shipped by the core entry."""
import json,re
from urllib.parse import urlsplit
import httpx
def bili_subtitles(info, language):
    """Saved, validated login first; anonymous remains a functional fallback."""
    import bilibili_auth
    from datetime import datetime,timezone
    from urllib.parse import urlencode
    import hashlib,time
    bvid=info.get('bvid') or next(iter(re.findall(r'BV[0-9A-Za-z]+',info.get('webpage_url',''))),None)
    if not bvid:return None
    _,cookies,nav=bilibili_auth.validated()
    attempts=[cookies,[]] if cookies else [[]]
    for credentials in attempts:
      try:
        view=bilibili_auth.bilibili_api_get('/x/web-interface/view',cookies=credentials,params={'bvid':bvid})
        data=view.get('data') or {};cid=info.get('cid') or data.get('cid')
        if not cid:continue
        info.update(title=data.get('title'),duration=data.get('duration'),thumbnail=data.get('pic'),uploader=(data.get('owner') or {}).get('name'))
        if data.get('pubdate'):info['upload_date']=datetime.fromtimestamp(data['pubdate'],timezone.utc).strftime('%Y%m%d')
        params={'bvid':bvid,'cid':cid};endpoints=[]
        images=nav.get('wbi_img') or {}
        lookup=''.join((images.get(k,'').rsplit('/',1)[-1].split('.')[0] for k in ('img_url','sub_url')))
        if credentials and len(lookup)==64:
            # Public WBI permutation, also documented by API-collect and yt-dlp (Unlicense).
            order=[46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13]
            key=''.join(lookup[i] for i in order)
            signed={k:str(v) for k,v in sorted({**params,'wts':int(time.time())}.items())}
            signed['w_rid']=hashlib.md5((urlencode(signed)+key).encode()).hexdigest()
            endpoints.append(('/x/player/wbi/v2',signed))
        endpoints.append(('/x/player/v2',params))
        for endpoint,query in endpoints:
          try:response=bilibili_auth.bilibili_api_get(endpoint,cookies=credentials,params=query)
          except (httpx.HTTPError,ValueError):continue
          tracks=((response.get('data') or {}).get('subtitle') or {}).get('subtitles',[])
          for tr in tracks:
            lang=tr.get('lan','').removeprefix('ai-')
            if language!='auto' and not lang.startswith(language):continue
            url=tr.get('subtitle_url','')
            if url.startswith('//'):url='https:'+url
            parsed=urlsplit(url);host=parsed.hostname or ''
            if not (host.endswith('.hdslb.com') and parsed.scheme=='https' and not parsed.username and not parsed.password and parsed.port in (None,443)):continue
            # Never send Bilibili account cookies to subtitle CDN hosts.
            with httpx.Client(trust_env=False,timeout=10) as client:
              with client.stream('GET',url) as r:
                r.raise_for_status();raw=bytearray()
                for chunk in r.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>2_000_000:raise ValueError('字幕文件过大')
            rows=[{'start':x['from'],'end':x['to'],'text':x['content']} for x in json.loads(raw).get('body',[]) if isinstance(x.get('content'),str) and x['to']>x['from']>=0]
            if rows:return {'text':'\n'.join(x['text'] for x in rows),'segments':rows,'engine':'bilibili_subtitles','language':lang,'timing_precision':'publisher_cues'}
      except (httpx.HTTPError,ValueError,KeyError,TypeError):continue
    return None

def probe(url,language,progress):
    try:
        if (urlsplit(url).hostname or '')=='b23.tv':
            with httpx.Client(trust_env=False,timeout=6) as c:
                for _ in range(3):
                    r=c.get(url)
                    if not r.is_redirect:break
                    from urllib.parse import urljoin
                    url=urljoin(url,r.headers['location'])
                    if urlsplit(url).hostname not in {'b23.tv','www.bilibili.com','bilibili.com'}:return None
        info={'webpage_url':url}
        progress(stage='subtitles',message='正在优先获取B站字幕')
        result=bili_subtitles(info,language)
        return (info,result,None) if result else None
    except (httpx.HTTPError,ValueError,KeyError):return None


def ingest(task,update,directory,metadata):
    import pipeline
    pipeline.run_task(task, update)
    result = task['result']
    metadata.update(title=result.get('title'), duration=result.get('duration'))
    detail = json.loads((directory / 'source.json').read_text(encoding='utf8')).get('detail', {})
    metadata.update(cover=(detail.get('video', {}).get('cover', {}).get('url_list') or [None])[0], publishedDate=detail.get('create_time'), description=detail.get('desc'), tags=[x.get('hashtag_name') for x in detail.get('text_extra', []) if x.get('hashtag_name')])
    return result

def register():
    import link_ingest
    link_ingest.PRECHECKS["bilibili"]=probe
    link_ingest.INGESTERS["douyin"]=ingest
    link_ingest.FALLBACKS["bilibili"]=bili_subtitles
