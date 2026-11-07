import asyncio
import hashlib
import json
import os
import queue
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

if os.environ.get('SHIWEN_PROFILE') == 'core':
    raise RuntimeError('私有入口和核心入口必须使用独立进程')

import settings
import link_ingest, link_jobs
import xhs_auth
import bilibili_auth
import link_batches
import content_classification
import rewrite
import clips
import video_frames
import share_snapshot
import document_notes
import document_chat
import library
import subscriptions
import source_expand
link_ingest.configure(private=True)
import store
import batches
import media_buffer
import organizer
import research
import articles
import discovery
from discovery_api import router as discovery_router
from article_api import router as article_router
from research_api import router as research_router
from studio_api import router as studio_router
from pipeline import MC_PY, input_url, run_task
from session import prepare_session
from source_contract import TaskHandlers

ROOT = Path(__file__).resolve().parent
TASKS = queue.Queue()
MUTEX = threading.RLock()
LOGIN = None
SOURCE_HANDLERS = TaskHandlers()
SOURCE_HANDLERS.register('link', link_jobs.run)
SOURCE_HANDLERS.register('platform_video', lambda task, update: run_task(
    task, update, settings.cloud_key() if task['provider'] == 'cloud' else ''))
SOURCE_HANDLERS.register('platform_creator', lambda task, update: batches.run_creator(task, update, TASKS.put))


def private_handler(task):
    # Legacy records are interpreted here, without migrating stored user data.
    source = task.get('source') or {'kind': 'platform_creator' if task.get('kind') == 'creator' else 'platform_video'}
    handler = SOURCE_HANDLERS.resolve({'source': source})
    if handler is None:
        raise ValueError('当前入口未注册此来源处理器')
    return handler


def worker():
    while True:
        task_id = TASKS.get()
        if task_id is None:
            TASKS.task_done()
            return
        link_batches.set_busy(True)
        if isinstance(task_id,str) and task_id.startswith('clips:'):
            try:clips.run(task_id[6:])
            finally:
                TASKS.task_done()
                link_batches.set_busy(False)
            continue
        with MUTEX:
            task = store.get(task_id)
        try:
            def update(**fields):
                with MUTEX:
                    current = store.get(task_id)
                    current.update(fields)
                    store.save(current)

            if not task or (task['status'] not in {'queued', 'running'} and task.get('source',{}).get('kind')!='link'):
                continue
            with MUTEX:
                parent = store.get(task.get('parent_id', ''))
                if parent and parent.get('paused'):
                    update(status='paused', message='批次已暂停，等待继续')
                    continue
            private_handler(task)(task, update)
        except media_buffer.BufferFull as exc:
            update(status='waiting_space',stage='waiting_space',error=None,message=str(exc))
        except Exception as exc:
            # Public errors are controlled messages only. HTTP clients can carry
            # credentials/URLs in their repr, so never expose arbitrary traces.
            message = str(exc) if isinstance(exc, (RuntimeError, ValueError)) else f"处理失败（{type(exc).__name__}），请重试。已完成片段会保留。"
            update(status="failed", stage="failed", error=message, message=message,
                   elapsed_seconds=round(time.time() - store.get(task_id).get("started_at", time.time()), 2))
        finally:
            with MUTEX:
                for parent_task in store.all_tasks():
                    if parent_task.get('kind') == 'creator' and parent_task.get('status') == 'processing':
                        store.save(batches.reconcile(parent_task))
            TASKS.task_done()
            link_batches.set_busy(False)


@asynccontextmanager
async def lifespan(app):
    recover_shared()
    link_jobs.recover()
    discovery.recover()
    subscriptions.recover()
    document_chat.recover()
    video_frames.recover()
    clips.recover(TASKS.put)
    rewrite.recover()
    content_classification.recover()
    for task in reversed(store.all_tasks()):
        if task["status"] in {"queued", "running"} and task.get("source",{}).get("kind")!="link":
            task.update(status="queued", message="正在恢复上次未完成的任务")
            store.save(task)
            TASKS.put(task["id"])
    thread = threading.Thread(target=worker, daemon=True, name="shiwen-worker")
    thread.start()
    link_batches.start(TASKS.put,TASKS.empty)
    yield
    link_batches.stop()
    await bilibili_auth.stop()
    await xhs_auth.stop()
    TASKS.put(None)
    thread.join(timeout=3)


app = FastAPI(title="拾文 · 视频原文工作台", lifespan=lifespan, docs_url=None, redoc_url=None)
from app_shared import install_shared, recover_shared
install_shared(app)
app.include_router(xhs_auth.router)
app.include_router(bilibili_auth.router)
app.include_router(link_batches.router)
app.include_router(video_frames.router)
app.include_router(share_snapshot.router)
app.include_router(document_notes.router)
app.include_router(document_chat.router)
app.include_router(library.router)
app.include_router(subscriptions.router)
app.include_router(source_expand.router)
app.include_router(content_classification.router)
app.include_router(rewrite.router)
app.include_router(clips.router(TASKS.put))
app.include_router(link_jobs.router(TASKS.put, ('youtube','bilibili','douyin','rss','tiktok','twitter','xiaoyuzhou','spotify','xiaohongshu')))

class NewTask(BaseModel):
    share_text: str = Field(min_length=1, max_length=5000)
    provider: str = "local"


class SettingsInput(BaseModel):
    provider: str = "local"
    api_key: str | None = Field(default=None, max_length=512)
    deepseek_key: str | None = Field(default=None, max_length=512)


def find_task(task_id):
    if not re.fullmatch(r"[a-f0-9]{16}", task_id):
        raise HTTPException(404, "任务不存在")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@app.get("/api/health")
def health():
    from transcribe import MODEL
    return {"status": "ok", "models_ready": (MODEL / "model.int8.onnx").is_file(),
            "collector_ready": MC_PY.is_file(), "settings": settings.public(),
            "login_running": LOGIN is not None and LOGIN.poll() is None}


@app.get("/api/tasks")
def tasks():
    return [{k: v for k, v in task.items() if k not in {"result", "partial_text"}}
            for task in store.all_tasks()[:200]]


@app.get("/api/tasks/{task_id}")
def detail(task_id: str):
    task = find_task(task_id)
    return batches.reconcile(task) if task.get('kind') == 'creator' else task


class NewBatch(NewTask):
    limit: int = Field(default=10, ge=1, le=100)
    keep_media: bool = False
    max_duration_sec: Literal[600, 1200, 1800] = 600


@app.post('/api/batches')
def create_batch(body: NewBatch):
    if body.provider not in {'local', 'cloud'} or (body.provider == 'cloud' and not settings.public()['key_configured']):
        raise HTTPException(400, '请先选择可用的识别方式。')
    if LOGIN is not None and LOGIN.poll() is None:
        raise HTTPException(409, '请先关闭登录窗口。')
    try:
        url = input_url(body.share_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with MUTEX:
        if any(t.get('kind') == 'creator' and t['status'] in {'queued', 'running', 'processing'} for t in store.all_tasks()):
            raise HTTPException(409, '已有批次正在处理，请等待该批次结束后再创建。')
        ident = hashlib.sha256((url + str(time.time_ns())).encode()).hexdigest()[:16]
        store.save({'id': ident, 'kind': 'creator', 'url': url, 'provider': body.provider,
                    'limit': body.limit, 'keep_media': body.keep_media, 'max_duration_sec': body.max_duration_sec, 'title': '正在读取博主主页',
                    'status': 'queued', 'stage': 'queued', 'message': '等待获取作品列表',
                    'created_at': time.time(), 'children': [], 'paused': False})
        TASKS.put(ident)
    return {'id': ident, 'status': 'queued'}


@app.post('/api/batches/{task_id}/{action}')
def batch_action(task_id: str, action: str):
    with MUTEX:
        task = find_task(task_id)
        if task.get('kind') != 'creator':
            raise HTTPException(400, '不是博主批次。')
        if action == 'pause':
            task['paused'] = True
        elif action == 'resume':
            if LOGIN is not None and LOGIN.poll() is None:
                raise HTTPException(409, '请先关闭登录窗口。')
            task['paused'] = False
            for ident in task.get('children', []):
                child = store.get(ident)
                if child['status'] == 'paused':
                    child.update(status='queued', message='批次已继续')
                    store.save(child)
                    TASKS.put(ident)
        elif action in {'retry', 'more'}:
            if task['status'] in {'queued', 'running', 'processing'}:
                raise HTTPException(409, '请等待当前批次结束。')
            if LOGIN is not None and LOGIN.poll() is None:
                raise HTTPException(409, '请先关闭登录窗口。')
            if action == 'more':
                if not task.get('has_more') or task['limit'] >= 10000:
                    raise HTTPException(400, '当前批次已到末尾或累计10000条保护上限。')
                task['limit'] = min(10000, task['limit'] + 10)
            for ident in task.get('children', []):
                child = store.get(ident)
                if child['status'] == 'failed':
                    child.update(status='queued', error=None, message='等待重试')
                    store.save(child)
            task.update(status='queued', paused=False, error=None)
            TASKS.put(task_id)
        else:
            raise HTTPException(404, '未知操作')
        store.save(task)
    return {'id': task_id}


@app.get('/api/batches/{task_id}/export')
def batch_export(task_id: str):
    task = find_task(task_id)
    if task.get('kind') != 'creator':
        raise HTTPException(404, '批次不存在')
    return Response(batches.export_zip(task), media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="shiwen-{task_id}.zip"'})


@app.post("/api/tasks")
def create(body: NewTask):
    if body.provider not in {"local", "cloud"}:
        raise HTTPException(400, "请选择本地或云端识别。")
    if body.provider == "cloud" and not settings.public()["key_configured"]:
        raise HTTPException(400, "请先配置硅基流动 Key，或使用本地识别。")
    if LOGIN is not None and LOGIN.poll() is None:
        raise HTTPException(409, "登录窗口正在使用会话，请完成登录并关闭窗口后再提交。")
    try:
        url = input_url(body.share_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    task_id = hashlib.sha256((url + "|" + body.provider).encode()).hexdigest()[:16]
    with MUTEX:
        existing = store.get(task_id)
        if existing:
            return {"id": task_id, "cached": True, "status": existing["status"]}
        if sum(t["status"] in {"queued", "running"} for t in store.all_tasks()) >= 20:
            raise HTTPException(429, "待处理任务已满，请等待当前任务完成。")
        task = {"id": task_id, "url": url, "provider": body.provider, "title": "正在读取视频信息",
                "author": "", "status": "queued", "stage": "queued", "message": "等待处理",
                "created_at": time.time(), "progress": 0, "error": None, "keep_media": False}
        store.save(task)
        TASKS.put(task_id)
    return {"id": task_id, "cached": False, "status": "queued"}


@app.post("/api/tasks/{task_id}/retry")
def retry(task_id: str):
    with MUTEX:
        task = find_task(task_id)
        if task["status"] not in {"failed", "waiting_space"}:
            raise HTTPException(409, "只有失败任务需要重试。")
        if LOGIN is not None and LOGIN.poll() is None:
            raise HTTPException(409, "请先关闭登录窗口。")
        task.update(status="queued", stage="queued", error=None, message="等待重试，将复用已完成片段")
        store.save(task)
        TASKS.put(task_id)
    return {"id": task_id}


@app.get("/api/tasks/{task_id}/export/{kind}")
def export(task_id: str, kind: str):
    task = find_task(task_id)
    if task["status"] != "completed" or kind not in {"txt", "md", "json"}:
        raise HTTPException(404, "完整文稿尚未生成。")
    path = store.DATA / "jobs" / task_id / f"transcript.{kind}"
    return FileResponse(path, filename=f"拾文-{task.get('video_id', task_id)}.{kind}")


@app.get("/api/tasks/{task_id}/media")
def media(task_id: str):
    find_task(task_id)
    path = store.DATA / "jobs" / task_id / "original.mp4"
    if not path.exists():
        raise HTTPException(404, "原视频尚未下载完成。")
    media_buffer.touch(task_id)
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/settings")
def get_settings():
    return settings.public()


@app.post("/api/settings")
def set_settings(body: SettingsInput):
    if body.provider not in {"local", "cloud"}:
        raise HTTPException(400, "未知识别方式")
    settings.save(body.provider, body.api_key, body.deepseek_key)
    return settings.public()


@app.post("/api/login")
def login():
    global LOGIN
    with MUTEX:
        if any(t["status"] in {"queued", "running"} for t in store.all_tasks()):
            raise HTTPException(409, "任务正在处理，请完成后再打开登录窗口。")
        if LOGIN is not None and LOGIN.poll() is None:
            return {"status": "already_open"}
        from douyin_session_guard import session_guard
        with session_guard():prepare_session(for_login=True)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
            env.pop(key, None)
        LOGIN = subprocess.Popen([str(MC_PY), "-B", "-X", "utf8", str(ROOT / "extractor.py"), "login",
                                  "--output", str(store.DATA / "login-result.json")],
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return {"status": "opened"}


app.include_router(discovery_router)
from private_images import router as private_images_router
app.include_router(private_images_router)


@app.post('/api/studio/buffer/resume')
def resume_buffer():
    with MUTEX:
        media_buffer.ensure_space()
        count=0
        for task in store.all_tasks():
            if task['status']=='waiting_space':
                task.update(status='queued',stage='queued',error=None,message='空间已释放，等待继续')
                store.save(task);TASKS.put(task['id']);count+=1
    return {'resumed':count}


import knowledge_projects
app.include_router(knowledge_projects.router)

import personal_kb
app.include_router(personal_kb.router)

import creation
app.include_router(creation.router)

import studio_api
studio_api.on_finalize = resume_buffer


if (ROOT/'tools'/'md2card'/'dist').is_dir():
    app.mount('/cards', StaticFiles(directory=ROOT/'tools'/'md2card'/'dist',html=True),name='cards')

if (ROOT/'frontend'/'dist').is_dir():
    app.mount('/studio', StaticFiles(directory=ROOT/'frontend'/'dist',html=True),name='studio')
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
