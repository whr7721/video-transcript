"""Managed uploads and serial local-file tasks; no external source dependencies."""
import asyncio
import hashlib
import json
import queue
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
import store
import media_buffer
import local_media
from source_contract import FileSource
from transcribe import MODEL_VERSION

router=APIRouter(prefix='/api/files')
LOCK=threading.RLock()
ACTIVE={}
UPLOAD_SLOT=threading.Lock()
TASKS=queue.Queue()
STOP=threading.Event()
THREAD=None
HANDLERS=None


def init():
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS file_uploads (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS file_index (fingerprint TEXT PRIMARY KEY,task_id TEXT UNIQUE NOT NULL)')


def upload_get(ident):
    if len(ident)!=16 or any(c not in '0123456789abcdef' for c in ident):
        raise HTTPException(404,'上传不存在')
    with store.connect() as db:
        row=db.execute('SELECT payload FROM file_uploads WHERE id=?',(ident,)).fetchone()
    if not row: raise HTTPException(404,'上传不存在')
    return json.loads(row[0])


def upload_save(value):
    with store.connect() as db:
        db.execute('INSERT INTO file_uploads VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                   (value['id'],json.dumps(value,ensure_ascii=False)))


def directory(ident):
    path=store.DATA/'jobs'/ident
    base=(store.DATA/'jobs').resolve()
    if not base.is_relative_to(store.DATA.resolve()) or path.is_symlink() or not path.resolve().is_relative_to(base):
        raise ValueError('受管目录路径无效')
    return path


def abort(ident, status='cancelled'):
    with LOCK,media_buffer.LOCK:
        value=upload_get(ident)
        if value['status']=='accepted': return
        if status=='interrupted' and value['status'] in {'cancelled','expired'}:status=value['status']
        if ident in ACTIVE: ACTIVE[ident].set()
        part=directory(ident)/'original.part'
        try:
            part.unlink(missing_ok=True)
        except PermissionError:
            # A probe may still hold the Windows handle; request finally/recovery retries.
            pass
        value.update(status=status,updated_at=time.time())
        upload_save(value)
        if not part.exists(): media_buffer.state(ident,'discarded')


class UploadInput(BaseModel):
    filename:str=Field(min_length=1,max_length=255)
    size_bytes:int|None=Field(default=None,gt=0,le=local_media.MAX_BYTES)


@router.post('/uploads',status_code=201)
def create_upload(body:UploadInput):
    try: name=local_media.display_name(body.filename)
    except ValueError as exc: raise HTTPException(400,str(exc))
    with LOCK:
        # Unused sessions own no bytes; expire them lazily as well as at restart.
        with store.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM file_uploads')]
        for item in rows:
            if item['status']=='created' and time.time()-item['created_at']>900: abort(item['id'],'expired')
        if sum(r['status']=='created' and time.time()-r['created_at']<=900 for r in rows)>=20:
            raise HTTPException(429,'待上传会话已满，请取消不用的上传')
        ident=uuid.uuid4().hex[:16]
        value={'id':ident,'filename':name,'expected_bytes':body.size_bytes,'status':'created','created_at':time.time()}
        directory(ident).mkdir(parents=True,exist_ok=False)
        media_buffer.register(ident)
        upload_save(value)
        return {'upload_id':ident,'max_bytes':local_media.MAX_BYTES,'max_seconds':local_media.MAX_SECONDS}


@router.delete('/uploads/{ident}')
def cancel_upload(ident:str):
    with LOCK:
        value=upload_get(ident)
        if value['status']=='accepted': raise HTTPException(409,'文件已入队，不能作为上传暂存删除')
        abort(ident)
    return {'status':'cancelled'}


@router.get('/uploads/{ident}')
def upload_status(ident:str):
    with LOCK:
        value=upload_get(ident)
        return {'upload_id':ident,'status':value['status'],'task_id':value.get('task_id')}


def write_chunk(ident,event,chunk,hasher,count):
    with LOCK,media_buffer.LOCK:
        if event.is_set(): raise InterruptedError('上传已取消')
        if count+len(chunk)>local_media.MAX_BYTES: raise ValueError('单文件不能超过1GB')
        path=directory(ident)/'original.part'
        for offset in range(0,len(chunk),256*1024):
            block=memoryview(chunk)[offset:offset+256*1024]
            media_buffer.ensure_space(len(block))
            with path.open('ab',buffering=0) as f: f.write(block)
            hasher.update(block)
    return count+len(chunk)


def accept(value,digest,count,event,source_override=None):
    part=directory(value['id'])/'original.part'
    info=local_media.inspect(part,value['filename'])
    fingerprint=hashlib.sha256((digest+'|'+MODEL_VERSION+'|local|auto-language|first-audio').encode()).hexdigest()
    ident=fingerprint[:16]
    with LOCK,media_buffer.LOCK:
        if event.is_set(): raise InterruptedError('上传已取消')
        with store.connect() as db:
            row=db.execute('SELECT task_id FROM file_index WHERE fingerprint=?',(fingerprint,)).fetchone()
        existing=store.get(row[0]) if row else None
        if row and not existing: raise RuntimeError('内容索引不完整，请保留文件并联系维护者')
        if existing:
            ident=existing['id']
            target=directory(ident)/'original.media'
            restored=not target.is_file()
            if restored:
                target.parent.mkdir(parents=True,exist_ok=True)
                part.replace(target)
                media_buffer.register(ident)
                media_buffer.state(ident,'awaiting_review')
            else: part.unlink(missing_ok=True)
            prepare_audio=existing['status']=='completed' and not local_media.cached_audio(directory(ident)/'audio.wav')
            if restored or prepare_audio:
                existing.update(media_available=True,media_restore_pending=bool(prepare_audio),message='原文件已补回，正在准备回听音频' if prepare_audio else '原文件已补回，可继续处理')
                store.save(existing)
                if prepare_audio: TASKS.put(ident)
            media_buffer.state(value['id'],'discarded')
            value.update(status='accepted',task_id=ident)
            upload_save(value)
            return {'id':ident,'cached':True,'restored':restored,'status':existing['status']}
        if store.get(ident): raise RuntimeError('内容编号冲突，未覆盖已有素材')
        if sum(t['status'] in {'queued','running'} for t in store.all_tasks())>=20:
            raise HTTPException(429,'待处理文件已满，请等待当前任务完成')
        target=directory(ident)
        target.mkdir(parents=True,exist_ok=True)
        media_buffer.register(ident)
        part.replace(target/'original.media')
        source=FileSource(original_name=value['filename'],sha256=digest,size_bytes=count).model_dump()
        if source_override is not None: source=source_override
        task={'id':ident,'source':source,'media_info':info,'title':Path(value['filename']).stem,'author':'',
              'provider':'local','status':'queued','stage':'queued','message':'文件已接收，等待解码与识别',
              'created_at':time.time(),'progress':0,'keep_media':False,'media_available':True}
        if source.get('kind')=='podcast': task.update(title=source['episode_title'],author=source['show_title'])
        task['warnings']=[f"发现 {info['audio_tracks']} 条音轨，仅识别第一条"] if info['audio_tracks']>1 else []
        # One transaction owns task/index/admission. Recovery removes only unclaimed managed files.
        value.update(status='accepted',task_id=ident)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO file_index VALUES (?,?)',(fingerprint,ident))
            db.execute('INSERT INTO tasks VALUES (?,?)',(ident,json.dumps(task,ensure_ascii=False)))
            db.execute('UPDATE file_uploads SET payload=? WHERE id=?',(json.dumps(value,ensure_ascii=False),value['id']))
        media_buffer.register(ident)
        media_buffer.state(value['id'],'discarded')
        TASKS.put(ident)
        return {'id':ident,'cached':False,'status':'queued','audio_tracks':info['audio_tracks']}


async def next_chunk(stream,event):
    reader=asyncio.create_task(stream.__anext__())
    started=time.monotonic()
    try:
        while True:
            if event.is_set(): raise InterruptedError('上传已取消')
            done,_=await asyncio.wait({reader},timeout=0.2)
            if done: return reader.result()
            if time.monotonic()-started>=60: raise asyncio.TimeoutError()
    finally:
        if not reader.done(): reader.cancel()
        await asyncio.gather(reader,return_exceptions=True)


@router.put('/uploads/{ident}')
async def receive_upload(ident:str,request:Request):
    with LOCK:
        value=upload_get(ident)
        if value['status']!='created': raise HTTPException(409,'请重新创建上传；不能续传已结束的会话')
        if not UPLOAD_SLOT.acquire(blocking=False): raise HTTPException(409,'当前已有文件上传，请等待或取消')
        event=threading.Event();ACTIVE[ident]=event
        value['status']='receiving'
        try:upload_save(value)
        except BaseException:
            ACTIVE.pop(ident,None);UPLOAD_SLOT.release()
            raise
    accepted=False
    submission=None
    try:
        declared=request.headers.get('content-length')
        if declared is not None and (not declared.isdigit() or not 0<int(declared)<=local_media.MAX_BYTES):
            raise ValueError('无效的请求大小或超过1GB')
        hasher=hashlib.sha256();count=0
        stream=request.stream().__aiter__()
        while True:
            try: chunk=await next_chunk(stream,event)
            except StopAsyncIteration: break
            count=await run_in_threadpool(write_chunk,ident,event,chunk,hasher,count)
        if not count or (declared is not None and int(declared)!=count) or (value['expected_bytes'] is not None and value['expected_bytes']!=count):
            raise ValueError('上传为空或字节数不完整，请重新选择文件')
        submission=asyncio.create_task(run_in_threadpool(accept,value,hasher.hexdigest(),count,event))
        result=await asyncio.shield(submission)
        accepted=True
        return result
    except media_buffer.BufferFull as exc: raise HTTPException(507,str(exc))
    except (ValueError,InterruptedError) as exc: raise HTTPException(400,str(exc))
    except (ClientDisconnect,asyncio.TimeoutError): raise HTTPException(408,'上传中断或超时，请重新选择文件')
    finally:
        # A disconnected coroutine must not orphan a still-running Windows probe
        # with an open handle. Wait for it before the final deletion attempt.
        if submission and not submission.done():
            event.set()
            while not submission.done():
                try: await asyncio.shield(submission)
                except asyncio.CancelledError: continue
                except Exception: break
        with LOCK:
            if not accepted: abort(ident,'interrupted')
            ACTIVE.pop(ident,None)
            UPLOAD_SLOT.release()


def update_task(ident,**fields):
    with LOCK:
        value=store.get(ident)
        value.update(fields);store.save(value)


def run_task(task,update):
    started=time.perf_counter()
    path=directory(task['id'])
    source=path/'original.media'
    if not source.is_file(): raise ValueError('原文件缺失，请重新选择同一文件补回')
    info=local_media.inspect(source,task['source']['original_name'])
    media_buffer.register(task['id'])
    update(stage='preparing',message='正在解码第一条音轨',duration=info['duration'],started_at=time.time())
    cached=local_media.cached_audio(path/'audio.wav')
    if not cached: (path/'audio.wav').unlink(missing_ok=True)
    with media_buffer.reserve(task['id'],0 if cached else local_media.wav_budget(info)):
        duration=local_media.prepare(source,path/'audio.wav',info,STOP.is_set)
    update(preparation_seconds=round(time.perf_counter()-started,3))
    if task.get('media_restore_pending'):
        media_buffer.state(task['id'],'awaiting_review')
        update(media_restore_pending=False,media_restore_waiting=False,media_error=None,media_available=True,stage='completed',message='回听音频已补回，原稿与编辑版本未改动')
        return
    from transcript_stage import finish_transcription
    last=[0.0]
    def progress_update(**fields):
        if STOP.is_set(): raise InterruptedError('正在暂停，重启后恢复已完成片段')
        now=time.monotonic()
        if fields.get('stage') or now-last[0]>=1:
            update(**fields);last[0]=now
    finish_transcription(task,progress_update,path,path/'audio.wav',duration,
                         {'title':task['title'],'author':task.get('author',''),'source':task['source']},started,True)


def worker():
    while not STOP.is_set():
        try: ident=TASKS.get(timeout=0.2)
        except queue.Empty: continue
        if ident.startswith('podcast:'):
            try:
                import podcasts
                podcasts.process(ident.split(':',1)[1])
            finally: TASKS.task_done()
            continue
        try:
            task=store.get(ident)
            if not task or task.get('source',{}).get('kind') not in {'local_file','podcast','link'}: continue
            if task['status'] not in {'queued','running'} and not task.get('media_restore_pending') and task.get('source',{}).get('kind')!='link': continue
            if not task.get('media_restore_pending') and task.get('source',{}).get('kind')!='link': update_task(ident,status='running',error=None)
            handler=HANDLERS.resolve(task) if HANDLERS else run_task
            if not handler: raise ValueError('未注册此来源处理器')
            handler(task,lambda **f:update_task(ident,**f))
        except media_buffer.BufferFull as exc:
            if task.get('media_restore_pending') and task['status']=='completed':
                update_task(ident,media_restore_waiting=True,message=str(exc))
            else: update_task(ident,status='waiting_space',stage='waiting_space',message=str(exc),error=None)
        except InterruptedError:
            update_task(ident,status='completed' if task.get('media_restore_pending') and task['status']=='completed' else 'queued',message='服务已暂停，重启后继续')
        except Exception as exc:
            message=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else '文件处理失败，请检查文件后重试'
            if task.get('media_restore_pending') and task['status']=='completed':
                update_task(ident,media_restore_pending=False,media_restore_waiting=False,media_error=message,message=message)
            else: update_task(ident,status='failed',stage='failed',message=message,error=message)
        finally: TASKS.task_done()


def start(handlers=None):
    global THREAD,TASKS,HANDLERS
    HANDLERS=handlers
    init();media_buffer.recover_reservations()
    TASKS=queue.Queue();STOP.clear()
    with store.connect() as db:
        uploads=[json.loads(r[0]) for r in db.execute('SELECT payload FROM file_uploads')]
    for value in uploads:
        if value['status']!='accepted':
            terminal=value['status'] in {'cancelled','discarded','expired','interrupted'}
            if not terminal or (directory(value['id'])/'original.part').exists():
                abort(value['id'],value['status'] if terminal else 'interrupted')
    # Crash between rename and task transaction: clean only fixed owned names in registered job directories.
    for row in media_buffer.inventory():
        ident=row['id'];task=store.get(ident)
        if not task:
            for name in ('original.media','audio.partial.wav'):
                (directory(ident)/name).unlink(missing_ok=True)
    for task in reversed(store.all_tasks()):
        if task.get('source',{}).get('kind') in {'local_file','podcast'}:
            (directory(task['id'])/'audio.partial.wav').unlink(missing_ok=True)
            if task['status'] in {'queued','running'} or task.get('media_restore_pending'): TASKS.put(task['id'])
    THREAD=threading.Thread(target=worker,daemon=True,name='core-file-worker');THREAD.start()
    if handlers and 'podcast' in handlers.kinds():
        import podcasts
        podcasts.recover()


def stop():
    STOP.set()
    if THREAD: THREAD.join()


@router.post('/tasks/{ident}/retry')
def retry(ident:str):
    with LOCK:
        value=store.get(ident)
        if not value or value.get('source',{}).get('kind') not in {'local_file','podcast'}: raise HTTPException(404,'本地任务不存在')
        if value['status'] not in {'failed','waiting_space'}: raise HTTPException(409,'此任务不需要重试')
        update_task(ident,status='queued',stage='queued',error=None,message='等待继续，将复用已完成语音片段')
        TASKS.put(ident)
    return {'id':ident}


def resume():
    media_buffer.ensure_space()
    count=0
    for task in store.all_tasks():
        if task.get('source',{}).get('kind') in {'local_file','podcast'}:
            if task['status']=='waiting_space': retry(task['id']);count+=1
            elif task.get('media_restore_waiting'):
                update_task(task['id'],media_restore_waiting=False)
                TASKS.put(task['id']);count+=1
    return {'resumed':count}
