"""Explicit single-episode capture using the existing serial file worker and quota."""
import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import article_fetch
import local_files as files
import media_buffer
import podcast_feed
import podcast_text
import store
from source_contract import PodcastSource

router=APIRouter(prefix='/api/podcasts')
EVENTS={}
PREVIEWS=threading.BoundedSemaphore(2)


def init():
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS podcast_feeds (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS podcast_imports (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS source_associations (task_id TEXT NOT NULL,hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(task_id,hash))')


def get(table,ident):
    if table not in {'podcast_feeds','podcast_imports'} or not re.fullmatch('[a-f0-9]{16}',ident):raise HTTPException(404,'播客记录不存在')
    with store.connect() as db:
        row=db.execute(f'SELECT payload FROM {table} WHERE id=?',(ident,)).fetchone()
    if not row:raise HTTPException(404,'播客记录不存在')
    return json.loads(row[0])


def save(table,value):
    if table not in {'podcast_feeds','podcast_imports'}:raise ValueError('记录类型无效')
    with store.connect() as db:
        db.execute(f'INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(value['id'],json.dumps(value,ensure_ascii=False)))


class FeedInput(BaseModel):
    url:str=Field(min_length=8,max_length=4000)


@router.post('/feeds')
def preview(body:FeedInput):
    if not PREVIEWS.acquire(blocking=False):raise HTTPException(429,'正在读取其他节目，请稍后重试')
    try:
        url=article_fetch.public_url(body.url)
        if any(re.search('token|secret|password|auth|key',k,re.I) for k,v in parse_qsl(urlsplit(url).query)):
            raise ValueError('首版不支持私密或带凭据的RSS')
        parts=[]
        response=article_fetch.stream(url,parts.append,podcast_feed.MAX_FEED_BYTES,budget=30)
        value=podcast_feed.parse(b''.join(parts),response['url'])
        value.update(id=uuid.uuid4().hex[:16],created_at=time.time())
        with files.LOCK:
            init()
            with store.connect() as db:
                db.execute('DELETE FROM podcast_feeds WHERE rowid NOT IN (SELECT rowid FROM podcast_feeds ORDER BY rowid DESC LIMIT 19)')
            save('podcast_feeds',value)
        return value
    except ValueError as exc:raise HTTPException(400,str(exc))
    except Exception:raise HTTPException(502,'RSS暂时无法读取，请核对公开RSS地址或稍后重试')
    finally:PREVIEWS.release()


class ImportInput(BaseModel):
    feed_id:str=Field(pattern=r'^[a-f0-9]{16}$')
    episode_id:str=Field(min_length=1,max_length=64)
    mode:str=Field(pattern='^(audio|text)$')
    transcript_index:int=Field(default=0,ge=0,le=20)


@router.post('/imports',status_code=201)
def create(body:ImportInput):
    with files.LOCK:
        init();feed=get('podcast_feeds',body.feed_id)
        episode=next((e for e in feed['episodes'] if e['id']==body.episode_id),None)
        if not episode:raise HTTPException(404,'单集不在这份RSS快照中，请刷新列表')
        if episode.get('duration_seconds',0) and episode['duration_seconds']>7200:raise HTTPException(400,'首版仅处理两小时以内单集')
        if body.mode=='audio' and not episode['audio_url']:raise HTTPException(400,'这集没有可用的音频地址')
        if body.mode=='audio':
            from transcribe import MODEL
            if not all(p.is_file() for p in (MODEL/'model.int8.onnx',MODEL/'tokens.txt',store.ROOT/'models/silero_vad.onnx')):
                raise HTTPException(409,'本地识别模型尚未就绪，请先按README准备模型；节目提供文字仍可导入')
        if body.mode=='text' and body.transcript_index>=len(episode['transcripts']):raise HTTPException(400,'这集没有支持格式的节目文字')
        with store.connect() as db:
            pending=sum(json.loads(r[0])['status'] in {'queued','running','waiting_space','cancelling'} for r in db.execute('SELECT payload FROM podcast_imports'))
        if pending>=20:raise HTTPException(429,'待获取单集已满，请先完成或取消已有任务')
        value={'id':uuid.uuid4().hex[:16],'status':'queued','stage':'queued','created_at':time.time(),
               'feed':{k:feed[k] for k in ('feed_url','title','feed_hash')},'episode':episode,
               'mode':body.mode,'transcript_index':body.transcript_index,'bytes':0,'message':'等待串行获取这一集'}
        save('podcast_imports',value);files.TASKS.put('podcast:'+value['id'])
        return value


@router.get('/imports/{ident}')
def status(ident:str):
    init();return get('podcast_imports',ident)


@router.delete('/imports/{ident}')
def cancel(ident:str):
    with files.LOCK:
        value=get('podcast_imports',ident)
        if value['status']=='accepted':raise HTTPException(409,'单集已入库，不能按获取暂存取消')
        if ident in EVENTS:
            EVENTS[ident].set();value.update(status='cancelling',message='正在停止网络读取并清理暂存')
        else:value.update(status='cancelled',message='已取消，尚未获取或已清理暂存')
        save('podcast_imports',value)
        return value


@router.post('/imports/{ident}/retry')
def retry(ident:str):
    with files.LOCK:
        value=get('podcast_imports',ident)
        if value['status'] not in {'failed','interrupted','waiting_space','cancelled'}:raise HTTPException(409,'当前获取无需重试')
        value.update(status='queued',stage='queued',bytes=0,error=None,message='等待重新获取，将校验已有内容')
        save('podcast_imports',value);files.TASKS.put('podcast:'+ident)
        return value


def associate(task_id,source):
    encoded=json.dumps(source,ensure_ascii=False,sort_keys=True)
    with store.connect() as db:
        db.execute('INSERT OR IGNORE INTO source_associations VALUES (?,?,?)',(task_id,hashlib.sha256(encoded.encode()).hexdigest(),encoded))


def accept_text(value,source,result,event):
    ident=hashlib.sha256((source['sha256']+'|publisher|'+str(source['text_format'])).encode()).hexdigest()[:16]
    with files.LOCK:
        if event.is_set() or files.STOP.is_set():raise InterruptedError('获取已取消')
        existing=store.get(ident)
        if existing:
            if existing.get('source',{}).get('sha256')!=source['sha256'] or existing.get('source',{}).get('ingest')!='publisher_text':raise ValueError('内容编号冲突，未覆盖旧文稿')
        else:
            path=files.directory(ident);path.mkdir(parents=True,exist_ok=True)
            result.update(source=source,title=source['episode_title'],author=source['show_title'])
            store.atomic_json(path/'transcript.json',result)
            (path/'transcript.txt').write_text(result['text'],encoding='utf-8')
            (path/'transcript.md').write_text('# '+source['episode_title']+'\n\n来源：'+source['transcript_url']+'\n\n> '+result['review_note']+'\n\n'+result['text'],encoding='utf-8')
            task={'id':ident,'source':source,'title':source['episode_title'],'author':source['show_title'],
                  'provider':'publisher','status':'completed','stage':'completed','created_at':time.time(),'completed_at':time.time(),
                  'duration':value['episode'].get('duration_seconds'),'progress':1,'result':result,'media_available':False,
                  'message':'节目文字已保存；完整性未人工核验，没有下载音频或调用ASR','warnings':[result['review_note']]}
        value.update(status='accepted',stage='accepted',task_id=ident,cached=bool(existing),message='节目文字已入库')
        encoded=json.dumps(source,ensure_ascii=False,sort_keys=True)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not existing:db.execute('INSERT INTO tasks VALUES (?,?)',(ident,json.dumps(task,ensure_ascii=False)))
            db.execute('INSERT OR IGNORE INTO source_associations VALUES (?,?,?)',(ident,hashlib.sha256(encoded.encode()).hexdigest(),encoded))
            db.execute('UPDATE podcast_imports SET payload=? WHERE id=?',(json.dumps(value,ensure_ascii=False),value['id']))


def process(ident):
    upload=None;event=threading.Event();slot=False;accepted=False;final_state=None
    try:
        with files.LOCK:
            value=get('podcast_imports',ident)
            if value['status']!='queued':return
            EVENTS[ident]=event
            value.update(status='running',stage='fetching',message='正在获取你选择的这一集',bytes=0)
            save('podcast_imports',value)
            slot=files.UPLOAD_SLOT.acquire(blocking=False)
            if not slot:raise ValueError('当前有文件上传，请在上传结束后重试这集')
            upload=files.create_upload(files.UploadInput(filename='podcast.mp3'))['upload_id']
            value['upload_id']=upload;save('podcast_imports',value)
            session=files.upload_get(upload);session['status']='receiving';files.upload_save(session)
        episode=value['episode'];mode=value['mode'];selected=episode['transcripts'][value['transcript_index']] if mode=='text' else None
        url=selected['url'] if selected else episode['audio_url'];hasher=hashlib.sha256();count=0;last=[0]
        def stopped():return event.is_set() or files.STOP.is_set()
        def chunk(block):
            nonlocal count
            if stopped():raise InterruptedError('获取已取消')
            count=files.write_chunk(upload,event,block,hasher,count)
            if time.monotonic()-last[0]>.5:
                with files.LOCK:
                    value.update(bytes=count);save('podcast_imports',value)
                last[0]=time.monotonic()
        response=article_fetch.stream(url,chunk,2_000_000 if selected else 1_000_000_000,stopped=stopped,
                                      declared_size=media_buffer.ensure_space)
        path=files.directory(upload)/'original.part'
        if stopped():raise InterruptedError('获取已取消')
        if selected:name='podcast.txt'
        else:
            with path.open('rb') as f:head=f.read(16)
            suffix='.wav' if head[:4]==b'RIFF' else '.flac' if head[:4]==b'fLaC' else '.m4a' if head[4:8] in {b'ftyp',b'moov',b'mdat',b'wide',b'free'} else '.mp3'
            name='podcast'+suffix
        source=PodcastSource(original_name=name,feed_url=value['feed']['feed_url'],show_title=value['feed']['title'],
            episode_title=episode['title'],guid=episode['guid'],audio_url=episode['audio_url'],chapters_url=episode.get('chapters_url'),
            transcript_url=response['url'] if selected else None,ingest='publisher_text' if selected else 'local_asr',
            text_format=selected['type'] if selected else None,sha256=hasher.hexdigest(),size_bytes=count,fetched_at=time.time()).model_dump()
        with files.LOCK:
            if stopped():raise InterruptedError('获取已取消')
            value.update(source=source,bytes=count,stage='validating',message='获取结束，正在校验入库');save('podcast_imports',value)
        if selected:
            result=podcast_text.parse(path.read_bytes(),selected['type'])
            accept_text(value,source,result,event)
        else:
            session['filename']=name
            with files.LOCK:
                if stopped():raise InterruptedError('获取已取消')
            result=files.accept(session,hasher.hexdigest(),count,event,source)
            with files.LOCK:
                associate(result['id'],source)
                value.update(status='accepted',stage='accepted',task_id=result['id'],cached=result['cached'],bytes=count,message='已接收并进入本地处理队列')
                save('podcast_imports',value)
        accepted=True
    except Exception as exc:
        with files.LOCK:
            if 'value' not in locals():return
            admission=files.upload_get(upload) if upload else None
            if admission and admission['status']=='accepted':
                accepted=True
                value.update(status='accepted',stage='accepted',task_id=admission['task_id'],message='单集已入库，获取暂存不再删除')
                save('podcast_imports',value)
                return
            state='waiting_space' if isinstance(exc,media_buffer.BufferFull) else 'cancelled' if event.is_set() else 'interrupted' if files.STOP.is_set() else 'failed'
            message=str(exc) if isinstance(exc,(ValueError,media_buffer.BufferFull)) else '获取中断，请重试；未改动已有文稿'
            final_state=(state,message)
    finally:
        with files.LOCK:
            if upload:files.abort(upload,'discarded' if accepted else 'interrupted')
            EVENTS.pop(ident,None)
            if slot:files.UPLOAD_SLOT.release()
            if final_state:
                state,message=final_state
                if upload and (files.directory(upload)/'original.part').exists():
                    state='failed';message='网络获取已停止，但暂存仍被占用；请重启服务重试清理，剩余字节仍计入缓冲'
                elif state=='cancelled':message='获取已取消，受管暂存已清理'
                value.update(status=state,error=None if state=='cancelled' else message,message=message)
                save('podcast_imports',value)


def recover():
    init()
    with store.connect() as db:values=[json.loads(r[0]) for r in db.execute('SELECT payload FROM podcast_imports')]
    for value in values:
        if value['status']=='accepted' and value.get('source') and value.get('task_id'):
            associate(value['task_id'],value['source'])
        if value['status']=='queued':files.TASKS.put('podcast:'+value['id'])
        elif value['status'] in {'running','cancelling'}:
            admission=files.upload_get(value['upload_id']) if value.get('upload_id') else None
            if admission and admission['status']=='accepted':
                if value.get('source'):associate(admission['task_id'],value['source'])
                value.update(status='accepted',task_id=admission['task_id'],message='已恢复入库结果')
            else:value.update(status='interrupted',message='上次获取已中断，请重试，不支持半文件续传')
            save('podcast_imports',value)
