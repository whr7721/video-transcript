"""Private adapters; never imported or shipped by the core entry."""
import json,re
from urllib.parse import urlsplit
import httpx
def bili_subtitles(info, language):
    """Community player API fallback; no account credentials are inferred."""
    bvid=info.get('bvid') or next(iter(re.findall(r'BV[0-9A-Za-z]+',info.get('webpage_url',''))),None)
    if not bvid:return None
    with httpx.Client(trust_env=False,timeout=25,headers={'Referer':'https://www.bilibili.com/','User-Agent':'Mozilla/5.0'}) as c:
        view=c.get('https://api.bilibili.com/x/web-interface/view',params={'bvid':bvid});view.raise_for_status()
        data=view.json().get('data') or {};cid=info.get('cid') or data.get('cid')
        if not cid:return None
        r=c.get('https://api.bilibili.com/x/player/v2',params={'bvid':bvid,'cid':cid});r.raise_for_status()
        for tr in (r.json().get('data') or {}).get('subtitle',{}).get('subtitles',[]):
            if language!='auto' and not tr.get('lan','').removeprefix('ai-').startswith(language):continue
            url=tr.get('subtitle_url','')
            if url.startswith('//'):url='https:'+url
            host=urlsplit(url).hostname or ''
            if not (host.endswith('.hdslb.com') and url.startswith('https://')):continue
            response=c.get(url);response.raise_for_status()
            rows=[{'start':x['from'],'end':x['to'],'text':x['content']} for x in response.json().get('body',[])]
            if rows:return {'text':'\n'.join(x['text'] for x in rows),'segments':rows,'engine':'bilibili_subtitles'}
    return None

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
    link_ingest.INGESTERS["douyin"]=ingest
    link_ingest.FALLBACKS["bilibili"]=bili_subtitles
