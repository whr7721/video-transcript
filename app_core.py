"""Standalone core entry point; run in its own process."""
import os
import re
import sys
from pathlib import Path
from contextlib import asynccontextmanager

ROOT = Path(__file__).resolve().parent
CORE_DATA = Path(os.environ.get('SHIWEN_CORE_DATA_DIR', ROOT / 'data-core')).resolve()
if CORE_DATA == (ROOT / 'data').resolve():
    raise RuntimeError('核心入口必须使用独立数据目录')
if 'store' in sys.modules and sys.modules['store'].DATA != CORE_DATA:
    raise RuntimeError('请在独立进程启动核心入口，不能与其他入口共用模块状态')
os.environ['SHIWEN_DATA_DIR'] = str(CORE_DATA)
os.environ['SHIWEN_PROFILE'] = 'core'

import store
if store.DATA != CORE_DATA:
    raise RuntimeError('请在独立进程启动核心入口，不能与其他入口共用模块状态')
import settings
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app_shared import install_shared, recover_shared
from source_contract import TaskHandlers

handlers = TaskHandlers()  # File admission/processing is the next milestone.


@asynccontextmanager
async def lifespan(app):
    marker = CORE_DATA/'.core-profile'
    if CORE_DATA.exists() and any(CORE_DATA.iterdir()) and (
            not marker.is_file() or marker.read_text(encoding='utf-8') != 'core-v1'):
        raise RuntimeError('该目录不是核心数据目录；请指定空目录，不能自动迁移已有数据')
    CORE_DATA.mkdir(parents=True, exist_ok=True)
    marker.write_text('core-v1', encoding='utf-8')
    recover_shared()
    # Unknown source tasks are never dispatched or rewritten by this entry.
    yield


app = FastAPI(title='拾文 · 本地内容工作台', lifespan=lifespan, docs_url=None, redoc_url=None)
install_shared(app)


@app.get('/api/health')
def health():
    from transcribe import MODEL
    ready = all(p.is_file() for p in (MODEL/'model.int8.onnx', MODEL/'tokens.txt', ROOT/'models/silero_vad.onnx'))
    return {'status': 'ok', 'profile': 'core', 'models_ready': ready,
            'settings': settings.public(), 'capabilities': {'file_import': False, 'sources': handlers.kinds()}}


@app.get('/api/tasks')
def tasks():
    return [{k: v for k, v in task.items() if k not in {'result', 'partial_text'}}
            for task in store.all_tasks()[:200]]


def find_task(ident):
    value = store.get(ident) if re.fullmatch('[a-f0-9]{16}', ident) else None
    if not value:
        raise HTTPException(404, '任务不存在')
    return value


@app.get('/api/tasks/{ident}')
def detail(ident: str):
    return find_task(ident)


@app.get('/api/tasks/{ident}/export/{kind}')
def export(ident: str, kind: str):
    value = find_task(ident)
    if value['status'] != 'completed' or kind not in {'txt', 'md', 'json'}:
        raise HTTPException(404, '完整文稿尚未生成')
    path = store.DATA/'jobs'/ident/f'transcript.{kind}'
    if not path.is_file():
        raise HTTPException(404, '导出文件不存在')
    return FileResponse(path, filename=f'拾文-{ident}.{kind}')


class SettingsInput(BaseModel):
    provider: str = 'local'
    api_key: str | None = Field(default=None, max_length=512)
    deepseek_key: str | None = Field(default=None, max_length=512)


@app.get('/api/settings')
def get_settings():
    return settings.public()


@app.post('/api/settings')
def set_settings(body: SettingsInput):
    if body.provider not in {'local', 'cloud'}:
        raise HTTPException(400, '未知识别方式')
    settings.save(body.provider, body.api_key, body.deepseek_key)
    return settings.public()


@app.post('/api/studio/buffer/resume')
def resume_buffer():
    import media_buffer
    media_buffer.ensure_space()
    return {'resumed': 0, 'message': '本地文件任务入口尚未开放'}


assets = ROOT/'frontend'/'dist-core'
if assets.is_dir():
    app.mount('/studio', StaticFiles(directory=assets, html=True), name='studio')


@app.get('/')
def home():
    return RedirectResponse('/studio/')


@app.get('/logo.svg')
def logo():
    return FileResponse(assets/'logo.svg', media_type='image/svg+xml')
