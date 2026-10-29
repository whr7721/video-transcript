"""Shared synchronous ingestion used by the CLI and serial Web media workers."""
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
    p = urlsplit(url)
    if p.scheme != 'https' or p.username or p.password or (p.port not in (None, 443)):
        raise ValueError('请输入公开 HTTPS 链接')
    host = (p.hostname or '').lower()
    if host in {'douyin.com', 'www.douyin.com', 'v.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com'}:
        return 'douyin'
    if host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}:
        return 'youtube'
    if host in {'bilibili.com', 'www.bilibili.com', 'm.bilibili.com', 'b23.tv'}:
        return 'bilibili'
    return 'rss'

def stamp(seconds):
    ms = round(seconds * 1000)
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def export(directory, result, metadata):
    rows = []
    for s in result.get('segments', []):
        if 'start' not in s or 'end' not in s:
            continue
        if s['end'] <= s['start'] or s['start'] < 0:
            raise ValueError('字幕时间轴无效')
        rows.append({'startTime': s['start'], 'end': s['end'], 'text': s['text'], 'index': len(rows)})
    result = {**result, **metadata, 'subtitlesArray': rows}
    store.atomic_json(directory / 'transcript.json', result)
    (directory / 'transcript.txt').write_text(result['text'], encoding='utf8')
    if rows:
        (directory / 'transcript.srt').write_text('\n\n'.join((f"{i + 1}\n{stamp(s['startTime'])} --> {stamp(s['end'])}\n{s['text']}" for i, s in enumerate(rows))) + '\n', encoding='utf8')
    return result

def ytdlp(url, directory, language, progress=lambda **f: None):
    precheck=PRECHECKS.get(platform(url))
    if precheck:
        fast=precheck(url,language,progress)
        if fast:return fast
    import yt_dlp
    opts = {'noplaylist': True, 'outtmpl': str(directory / 'original.%(ext)s'), 'format': 'bestaudio/best', 'quiet': True, 'socket_timeout': 30, 'retries': 2, 'continuedl': True}
    if platform(url) == 'bilibili':
        opts['proxy'] = ''
    with yt_dlp.YoutubeDL(opts) as y:
        try:
            progress(stage='subtitles',message='正在获取字幕')
            info = y.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError:
            if platform(url) != 'bilibili':
                raise
            info = {'webpage_url': url}
            result = FALLBACKS.get('bilibili', lambda *a: None)(info, language)
            if result:
                return (info, result, None)
            raise
        candidates = []
        for field in ('subtitles', 'automatic_captions'):
            tracks = info.get(field) or {}
            for lang, formats in tracks.items():
                if lang == 'live_chat' or (language != 'auto' and (not lang.startswith(language))):
                    continue
                for f in formats:
                    if f.get('ext') in {'json3', 'vtt'} and f.get('url'):
                        candidates.append((lang, f))
        for lang, f in candidates:
            try:
                raw = y.urlopen(f['url']).read(2000001)
                if len(raw) > 2000000:
                    continue
                if f['ext'] == 'json3':
                    events = json.loads(raw)['events']
                    segments = []
                    for e in events:
                        text = ''.join((s.get('utf8', '') for s in e.get('segs', []))).strip()
                        if text and e.get('dDurationMs', 0) > 0:
                            segments.append({'start': e['tStartMs'] / 1000, 'end': (e['tStartMs'] + e['dDurationMs']) / 1000, 'text': text})
                else:
                    import podcast_text
                    segments = podcast_text.parse(raw, 'text/vtt')['segments']
                if segments:
                    return (info, {'text': '\n'.join((s['text'] for s in segments)), 'segments': segments, 'engine': 'publisher_subtitles', 'language': lang, 'timing_precision': 'publisher_cues'}, None)
            except (ValueError, KeyError, httpx.HTTPError):
                continue
        if 'bilibili.com' in (urlsplit(info.get('webpage_url', '')).hostname or ''):
            try:
                result = FALLBACKS.get('bilibili', lambda *a: None)(info, language)
                if result:
                    return (info, result, None)
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        if (info.get('duration') or 0) > 10800:
            raise ValueError('最多支持3小时')
        progress(stage='downloading',message='正在下载音频')
        y.download([url])
        media = next((p for p in directory.glob('original.*') if p.suffix not in {'.part', '.json', '.ytdl'}), None)
        if not media:
            raise RuntimeError('没有取得完整音频')
        return (info, None, media)

def prepare(args):
    local = Path(args.url).expanduser()
    is_file = local.is_file()
    if not is_file and '://' not in args.url:
        raise ValueError('本地文件不存在，请检查文件路径；链接请包含https://')
    if is_file and local.stat().st_size > 1000000000:
        raise ValueError('本地文件超过1GB限制')
    kind = 'local_file' if is_file else platform(args.url)
    if kind not in getattr(args,'allowed', {'local_file','youtube','rss','bilibili','douyin'}):
        raise ValueError('此版本不支持抖音链接' if kind=='douyin' else '此版本不支持此平台链接')
    customer = (Path(__file__).resolve().parent / 'customer-package.json').exists()
    if customer and kind not in {'local_file', 'rss', 'youtube'}:
        raise ValueError('此版本不支持抖音链接' if kind == 'douyin' else '此版本不支持此平台链接')
    episode = None
    if kind == 'rss':
        import article_fetch, podcast_feed
        if getattr(args,'episode_snapshot',None):
            feed={'episodes':[args.episode_snapshot]};args.episode=1
        else:
            chunks = []
            article_fetch.stream(args.url, chunks.append, podcast_feed.MAX_FEED_BYTES, budget=30)
            feed = podcast_feed.parse(b''.join(chunks), args.url)
        if getattr(args,'episode_guid',None):
            match=next((i for i,e in enumerate(feed['episodes'],1) if e.get('guid')==args.episode_guid),None)
            if match is None:raise ValueError('该单集已不在当前RSS中，未按旧序号提取其他内容')
            args.episode=match
        elif getattr(args,'episode_id',None):
            match=next((i for i,e in enumerate(feed['episodes'],1) if e['id']==args.episode_id),None)
            if match is None:raise ValueError('该单集已不在当前RSS中，未按旧序号提取其他内容')
            args.episode=match
        if args.episode is None:
            return {'feed':feed}
        if not 1 <= args.episode <= len(feed['episodes']):
            raise ValueError('单集序号超出范围')
        episode = feed['episodes'][args.episode - 1]
    if is_file:
        with local.open('rb') as stream:
            identity = hashlib.file_digest(stream, 'sha256').hexdigest()
    else:
        identity = episode['id'] if episode else args.url
    ident = hashlib.sha256((identity + '|' + args.language).encode()).hexdigest()[:16]
    return dict(kind=kind,episode=episode,ident=ident,local=local)


def add(args, progress=lambda **f: None):
    plan=getattr(args,'plan',None) or prepare(args)
    if 'feed' in plan:
        for i,e in enumerate(plan['feed']['episodes'],1):print(i,e['title'])
        print('使用 --episode 序号选择一集');return
    kind,episode,ident,local=(plan[k] for k in ('kind','episode','ident','local'))
    directory = store.DATA / 'jobs' / ident
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'transcript.json').exists():
        progress(stage='cached',message='已命中转写缓存',cached=True)
        print(directory / 'transcript.json')
        if getattr(args, 'summarize', False):
            from cli_summary import summarize
            summarize(directory)
            print(directory / 'summary.md')
            print(directory / 'mindmap.html')
        return ident
    store.init()
    task = store.get(ident) or {'id': ident, 'url': args.url, 'provider': 'local', 'language': args.language, 'created_at': time.time(), 'status': 'queued', 'source': {'kind':'link','platform':kind}}

    def update(**fields):
        task.update(fields)
        store.save(task)
        progress(**fields)
    metadata = {'sourceUrl': args.url, 'cover': None, 'duration': None, 'publishedDate': None, 'platform': kind}
    if kind == 'local_file':
        import shutil
        from media_io import extract_audio, probe_media
        from transcribe import local_transcribe
        duration = probe_media(local)
        if duration > 10800:
            raise ValueError('最多支持3小时')
        audio = directory / 'audio.wav'
        extract_audio(local, audio)
        progress(stage='transcribing',message='正在本地转写')
        result = local_transcribe(audio, directory / 'local_chunks', lambda fraction,count,text: progress(stage='transcribing',progress=fraction,segment_count=count), language=args.language)
        metadata.update(title=local.stem, duration=duration, sourceUrl=None, original_name=local.name)
    elif kind == 'douyin':
        if kind not in INGESTERS:raise ValueError('此版本不支持抖音链接')
        result = INGESTERS[kind](task, update, directory, metadata)
    else:
        media = None
        result = None
        if kind == 'rss':
            import article_fetch, podcast_feed, podcast_text
            e = episode
            progress(stage='subtitles',message='正在获取节目文字')
            metadata.update(title=e['title'], publishedDate=e['published'], duration=e['duration_seconds'])
            for tr in e['transcripts']:
                try:
                    chunks = []
                    article_fetch.stream(tr['url'], chunks.append, 2000000, budget=30)
                    result = podcast_text.parse(b''.join(chunks), tr['type'])
                    result['engine'] = 'publisher_text'
                    break
                except ValueError:
                    continue
            if result is None:
                if not e['audio_url']:
                    raise ValueError('此集无可用音频')
                progress(stage='downloading',message='正在下载节目音频')
                media=directory/'podcast.audio'
                if not media.exists():
                    part=directory/'podcast.part'
                    with part.open('wb') as output:
                        article_fetch.stream(e['audio_url'],output.write,1_000_000_000,budget=300)
                    part.replace(media)
        else:
            info, result, media = ytdlp(args.url, directory, args.language, progress)
            metadata.update(title=info.get('title'), author=info.get('uploader'), cover=info.get('thumbnail'), duration=info.get('duration'), publishedDate=info.get('upload_date'))
        if result is None:
            from media_io import extract_audio, probe_media
            from transcribe import local_transcribe
            duration = probe_media(media)
            if duration > 10800:
                raise ValueError('最多支持3小时')
            audio = directory / 'audio.wav'
            extract_audio(media, audio)
            progress(stage='transcribing',message='正在本地转写')
            result = local_transcribe(audio, directory / 'local_chunks', lambda fraction,count,text: progress(stage='transcribing',progress=fraction,segment_count=count), language=args.language)
            metadata['duration'] = duration
    result = export(directory, result, metadata)
    update(status='completed', stage='completed', title=metadata.get('title'), duration=metadata.get('duration'), result=result)
    print(directory / 'transcript.json')
    if getattr(args, 'summarize', False):
        from cli_summary import summarize
        print('本地转写已保存；开始模型整理（共享每日30次请求配额，成功阶段缓存不重复调用）。', flush=True)
        progress(stage='summarizing',message='正在整理，原稿已保存')
        summarize(directory)
        print(directory / 'summary.md')
        print(directory / 'mindmap.html')
    return ident

PRECHECKS={}
INGESTERS={}
FALLBACKS={}

def configure(private=False):
    if private:
        import link_private
        link_private.register()
