"""Personal link ingestion CLI. No cloud inference is used."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import store


def platform(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443):
        raise ValueError('请输入公开 HTTPS 链接')
    host=(p.hostname or '').lower()
    if host in {'douyin.com','www.douyin.com','v.douyin.com','iesdouyin.com','www.iesdouyin.com'}:return 'douyin'
    if host in {'youtube.com','www.youtube.com','m.youtube.com','youtu.be'}:return 'youtube'
    if host in {'bilibili.com','www.bilibili.com','m.bilibili.com','b23.tv'}:return 'bilibili'
    return 'rss'


def stamp(seconds):
    ms=round(seconds*1000);s,ms=divmod(ms,1000);m,s=divmod(s,60);h,m=divmod(m,60)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def export(directory,result,metadata):
    rows=[]
    for s in result.get('segments',[]):
        if 'start' not in s or 'end' not in s:continue
        if s['end']<=s['start'] or s['start']<0:raise ValueError('字幕时间轴无效')
        rows.append({'startTime':s['start'],'end':s['end'],'text':s['text'],'index':len(rows)})
    result={**result,**metadata,'subtitlesArray':rows}
    store.atomic_json(directory/'transcript.json',result)
    (directory/'transcript.txt').write_text(result['text'],encoding='utf8')
    if rows:
        (directory/'transcript.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(s['startTime'])} --> {stamp(s['end'])}\n{s['text']}" for i,s in enumerate(rows))+'\n',encoding='utf8')
    return result


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


def ytdlp(url,directory,language):
    import yt_dlp
    opts={'noplaylist':True,'outtmpl':str(directory/'original.%(ext)s'),'format':'bestaudio/best','quiet':True,'socket_timeout':30,'retries':2,'continuedl':True}
    if platform(url)=='bilibili':opts['proxy']=''
    with yt_dlp.YoutubeDL(opts) as y:
        try:info=y.extract_info(url,download=False)
        except yt_dlp.utils.DownloadError:
            if platform(url)!='bilibili':raise
            info={'webpage_url':url}
            result=bili_subtitles(info,language)
            if result:return info,result,None
            raise
        candidates=[]
        for field in ('subtitles','automatic_captions'):
            tracks=info.get(field) or {}
            for lang,formats in tracks.items():
                if lang=='live_chat' or (language!='auto' and not lang.startswith(language)):continue
                for f in formats:
                    if f.get('ext') in {'json3','vtt'} and f.get('url'):candidates.append((lang,f))
        for lang,f in candidates:
            try:
                raw=y.urlopen(f['url']).read(2_000_001)
                if len(raw)>2_000_000:continue
                if f['ext']=='json3':
                    events=json.loads(raw)['events'];segments=[]
                    for e in events:
                        text=''.join(s.get('utf8','') for s in e.get('segs',[])).strip()
                        if text and e.get('dDurationMs',0)>0:segments.append({'start':e['tStartMs']/1000,'end':(e['tStartMs']+e['dDurationMs'])/1000,'text':text})
                else:
                    import podcast_text
                    segments=podcast_text.parse(raw,'text/vtt')['segments']
                if segments:return info,{'text':'\n'.join(s['text'] for s in segments),'segments':segments,'engine':'publisher_subtitles','language':lang,'timing_precision':'publisher_cues'},None
            except (ValueError,KeyError,httpx.HTTPError):continue
        if 'bilibili.com' in (urlsplit(info.get('webpage_url','')).hostname or ''):
            try:
                result=bili_subtitles(info,language)
                if result:return info,result,None
            except (httpx.HTTPError,ValueError,KeyError):pass
        if (info.get('duration') or 0)>10800:raise ValueError('最多支持3小时')
        y.download([url])
        media=next((p for p in directory.glob('original.*') if p.suffix not in {'.part','.json','.ytdl'}),None)
        if not media:raise RuntimeError('没有取得完整音频')
        return info,None,media


def add(args):
    kind=platform(args.url)
    episode=None
    if kind=='rss':
        import article_fetch,podcast_feed
        chunks=[];article_fetch.stream(args.url,chunks.append,podcast_feed.MAX_FEED_BYTES,budget=30)
        feed=podcast_feed.parse(b''.join(chunks),args.url)
        if args.episode is None:
            for i,e in enumerate(feed['episodes'],1):print(i,e['title'])
            print('使用 --episode 序号选择一集');return
        if not 1<=args.episode<=len(feed['episodes']):raise ValueError('单集序号超出范围')
        episode=feed['episodes'][args.episode-1]
    identity=episode['id'] if episode else args.url
    ident=hashlib.sha256((identity+'|'+args.language).encode()).hexdigest()[:16]
    directory=store.DATA/'jobs'/ident;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'transcript.json').exists():
        print(directory/'transcript.json')
        if getattr(args,'summarize',False):
            from cli_summary import summarize
            summarize(directory)
            print(directory/'summary.md');print(directory/'mindmap.html')
        return
    store.init()
    task={'id':ident,'url':args.url,'provider':'local','language':args.language,'created_at':time.time(),'status':'queued'}
    def update(**fields):task.update(fields);store.save(task)
    metadata={'sourceUrl':args.url,'cover':None,'duration':None,'publishedDate':None,'platform':kind}
    if kind=='douyin':
        import pipeline
        pipeline.run_task(task,update)
        result=task['result'];metadata.update(title=result.get('title'),duration=result.get('duration'))
        detail=json.loads((directory/'source.json').read_text(encoding='utf8')).get('detail',{})
        metadata.update(cover=(detail.get('video',{}).get('cover',{}).get('url_list') or [None])[0],publishedDate=detail.get('create_time'),description=detail.get('desc'),tags=[x.get('hashtag_name') for x in detail.get('text_extra',[]) if x.get('hashtag_name')])
    else:
        media=None;result=None
        if kind=='rss':
            import article_fetch,podcast_feed,podcast_text
            e=episode;metadata.update(title=e['title'],publishedDate=e['published'],duration=e['duration_seconds'])
            for tr in e['transcripts']:
                try:
                    chunks=[];article_fetch.stream(tr['url'],chunks.append,2_000_000,budget=30)
                    result=podcast_text.parse(b''.join(chunks),tr['type']);result['engine']='publisher_text';break
                except ValueError:continue
            if result is None:
                if not e['audio_url']:raise ValueError('此集无可用音频')
                info,result,media=ytdlp(e['audio_url'],directory,args.language)
        else:
            info,result,media=ytdlp(args.url,directory,args.language)
            metadata.update(title=info.get('title'),author=info.get('uploader'),cover=info.get('thumbnail'),duration=info.get('duration'),publishedDate=info.get('upload_date'))
        if result is None:
            from media_io import extract_audio,probe_media
            from transcribe import local_transcribe
            duration=probe_media(media)
            if duration>10800:raise ValueError('最多支持3小时')
            audio=directory/'audio.wav';extract_audio(media,audio)
            result=local_transcribe(audio,directory/'local_chunks',lambda *a:None,language=args.language)
            metadata['duration']=duration
    result=export(directory,result,metadata)
    update(status='completed',stage='completed',title=metadata.get('title'),result=result)
    print(directory/'transcript.json')
    if getattr(args,'summarize',False):
        from cli_summary import summarize
        print('本地转写已保存；开始模型整理（共享每日30次请求配额，成功阶段缓存不重复调用）。',flush=True)
        summarize(directory)
        print(directory/'summary.md');print(directory/'mindmap.html')


def main():
    parser=argparse.ArgumentParser(prog='shiwen');sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('add');p.add_argument('url');p.add_argument('--episode',type=int);p.add_argument('--language',choices=['auto','zh','en','ja','ko','yue'],default='auto');p.add_argument('--summarize',action='store_true',help='原稿保存后用模型生成完整稿、精华、金句与离线导图；共享每日请求配额')
    args=parser.parse_args()
    try:add(args)
    except Exception as e:parser.exit(1,f'处理失败：{e}\n')

if __name__=='__main__':main()
