"""Metadata-only topic discovery. The external adapter owns its browser session.

Candidates and manual selections live independently of video/ASR tasks. No media
or model work can be scheduled from this module.
"""
import json
import math
import os
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
import store

ADAPTER = Path(os.environ.get('SHIWEN_DISCOVERY_ADAPTER',r'D:\zcode1\douyin-discovery\discovery.py'))
PYTHON = Path(os.environ.get('SHIWEN_MC_PYTHON',r'D:\zcode1\mediacrawler\.venv\Scripts\python.exe'))
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='discovery')
LOCK = threading.RLock()
STATUSES = {'ok', 'partial', 'login_required', 'user_action_required', 'rate_limited', 'unsupported', 'error'}


class Search(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(min_length=1, max_length=3)
    sort: Literal['general', 'most_liked', 'latest'] = 'general'
    published_within: Literal['unlimited', 'one_day', 'one_week', 'half_year'] = 'unlimited'
    max_candidates_total: int = Field(default=30, ge=1, le=100, strict=True)


def init():
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')


def save(value):
    value['updated_at'] = time.time()
    with store.connect() as db:
        db.execute('INSERT INTO discovery_jobs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                   (value['id'], json.dumps(value, ensure_ascii=False)))


def get(ident):
    if not re.fullmatch('[a-f0-9]{16}', ident):
        raise LookupError('搜索批次不存在')
    init()
    with store.connect() as db:
        row = db.execute('SELECT payload FROM discovery_jobs WHERE id=?', (ident,)).fetchone()
    if not row:
        raise LookupError('搜索批次不存在')
    return json.loads(row[0])


def all_jobs():
    init()
    with store.connect() as db:
        rows = db.execute('SELECT payload FROM discovery_jobs').fetchall()
    return sorted((json.loads(r[0]) for r in rows), key=lambda v: v['created_at'], reverse=True)


def recover():
    with LOCK:
        for value in all_jobs():
            if value['state'] in {'queued', 'running'}:
                checkpoint = store.DATA / 'discovery' / value['id'] / 'result.json'
                if checkpoint.is_file() and checkpoint.stat().st_size <= 5_000_000:
                    try:
                        parsed = validate_result(json.loads(checkpoint.read_text(encoding='utf-8')), value)
                        merged = {r['video_id']: r for r in value['items']}
                        merged.update({r['video_id']: r for r in parsed.pop('items')})
                        parsed['resume_token'] = parsed['resume_token'] or value.get('resume_token')
                        value.update(parsed, items=list(merged.values()))
                    except (ValueError, OSError, TypeError, OverflowError):
                        pass  # A corrupt/incomplete checkpoint never replaces durable state.
                value.update(state='interrupted', message='服务已重启；已有候选和勾选保留，需要时手动重试。')
                save(value)


def public(value):
    result = {k: v for k, v in value.items() if k != 'resume_token'}
    result['request'] = {k: v for k, v in value['request'].items() if k != 'resume_token'}
    result['can_resume'] = bool(value.get('resume_token'))
    # Read-only link to already available transcripts. Never schedules ASR.
    completed = {}
    for task in store.all_tasks():
        if task.get('status') == 'completed' and task.get('video_id') and task.get('kind') != 'creator':
            completed.setdefault(task['video_id'], task['id'])
    result['items'] = [{**row, 'transcript_id': completed.get(row['video_id'])} for row in value['items']]
    return result


def start(body):
    request = body.model_dump()
    request['topic'] = request['topic'].strip()
    queries = request['queries']
    if not request['topic'] or any(not q.strip() or len(q.strip()) > 128 for q in queries):
        raise ValueError('请填写主题和 1—3 条关键词，每条最多128字。')
    request['queries'] = list(dict.fromkeys(q.strip() for q in queries))
    with LOCK:
        if any(v['state'] in {'queued', 'running'} for v in all_jobs()):
            raise RuntimeError('已有搜索正在进行，请完成后再提交，避免浏览器会话冲突。')
        ident = uuid.uuid4().hex[:16]
        request.update(schema_version=1, request_id=ident, channel='video', metadata_only=True, resume_token=None)
        value = dict(id=ident, request=request, state='queued', adapter_status=None,
                     created_at=time.time(), items=[], selected_ids=[], selection_revision=1,
                     resume_token=None, warnings=[], per_query_progress=[], stopped_reason=None,
                     message='等待搜索；本阶段仅获取元信息。')
        save(value)
        EXECUTOR.submit(run, ident)
        return public(value)


def resume(ident, limit):
    with LOCK:
        value = get(ident)
        if any(v['state'] in {'queued', 'running'} for v in all_jobs()):
            raise RuntimeError('已有搜索正在进行，请稍后再试。')
        if not len(value['items']) < limit <= 100:
            raise ValueError('续采总上限必须大于当前候选数，且不超过100。')
        # Same request id, same file, same query signature. Failed startup may
        # overwrite the adapter file; reconstruct it from our durable snapshot.
        directory = store.DATA / 'discovery' / ident
        directory.mkdir(parents=True, exist_ok=True)
        if value.get('resume_token'):
            store.atomic_json(directory / 'result.json', {
                'resume_token': value['resume_token'], 'items': value['items']})
        value['request'].update(max_candidates_total=limit, resume_token=value.get('resume_token'))
        value.update(state='queued', message='继续搜索，已有候选和勾选保留。')
        save(value)
        EXECUTOR.submit(run, ident)
        return public(value)


def validate_result(raw, value):
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        raise ValueError('适配器输出版本不受支持')
    status = raw.get('status')
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError('适配器返回未知状态')
    # v1 startup failures omit request_id, all useful results must match it.
    startup = status == 'error' and raw.get('stopped_reason') == 'startup_error' and raw.get('items') == []
    if raw.get('request_id') != value['id'] and not (startup and not raw.get('request_id')):
        raise ValueError('适配器输出与本批次不匹配')
    rows = raw.get('items')
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError('适配器候选数量无效')
    clean = {}
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r'\d{15,22}', str(row.get('video_id', ''))):
            raise ValueError('候选作品ID无效')
        ident = str(row['video_id'])
        if row.get('canonical_url') != f'https://www.douyin.com/video/{ident}':
            raise ValueError('候选来源链接无效')
        if not isinstance(row.get('media_type'), str) or row['media_type'] not in {'video', 'image', 'unknown'}:
            raise ValueError('候选媒体类型无效')
        matched = row.get('matched_queries')
        if not isinstance(matched, list) or any(q not in value['request']['queries'] for q in matched):
            raise ValueError('候选搜索词不匹配')
        duration = row.get('duration_sec')
        if duration is not None and (type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0):
            duration = None
        fields = ('caption', 'author_name', 'author_id', 'published_at', 'metadata_checked_at')
        if any(row.get(f) is not None and not isinstance(row[f], str) for f in fields):
            raise ValueError('候选字段格式无效')
        clean[ident] = {k: (row.get(k) or '')[:2000] for k in fields}
        clean[ident].update(video_id=ident, canonical_url=row['canonical_url'],
                            duration_sec=duration, media_type=row['media_type'], matched_queries=matched,
                            digg_count=row.get('digg_count') if type(row.get('digg_count')) is int and row['digg_count'] >= 0 else None)
    warnings = raw.get('warnings', [])
    progress = raw.get('per_query_progress', [])
    token = raw.get('resume_token')
    if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
        raise ValueError('适配器警告格式无效')
    if not isinstance(progress, list) or any(not isinstance(p, dict) or p.get('query') not in value['request']['queries'] for p in progress):
        raise ValueError('适配器进度格式无效')
    if any(type(p.get('pages')) is not int or p['pages'] < 0 or type(p.get('exhausted')) is not bool for p in progress):
        raise ValueError('适配器页数或结束状态无效')
    if token is not None and (not isinstance(token, str) or len(token) > 200000):
        raise ValueError('适配器续采信息无效')
    return dict(adapter_status=status, items=list(clean.values()), resume_token=token,
                warnings=[w[:1000] for w in warnings[:30]],
                per_query_progress=[{k: p[k] for k in ('query', 'pages', 'exhausted')} for p in progress],
                stopped_reason=str(raw.get('stopped_reason', 'unknown'))[:100])


def invoke(request_path, output_path):
    from douyin_session_guard import session_guard
    with session_guard():return _invoke(request_path,output_path)

def _invoke(request_path, output_path):
    if not ADAPTER.is_file() or not PYTHON.is_file():
        raise ValueError('未找到独立搜索适配器或已有 Python 环境，请检查安装路径。')
    process = subprocess.Popen([str(PYTHON), '-X', 'utf8', str(ADAPTER), 'search',
                                '--request', str(request_path), '--output', str(output_path)],
                               cwd=ADAPTER.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        process.wait(timeout=240)
        return False
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        else:
            process.kill()
        process.wait(timeout=15)
        return True


def run(ident):
    try:
        with LOCK:
            value = get(ident)
            value.update(state='running', message='正在搜索标题、作者和时长；不会下载视频。')
            save(value)
        directory = store.DATA / 'discovery' / ident
        directory.mkdir(parents=True, exist_ok=True)
        request_path, output_path = directory / 'request.json', directory / 'result.json'
        store.atomic_json(request_path, value['request'])
        # Rename stale output on retries without a usable token, so timeout can
        # never be mistaken for a fresh adapter success.
        if output_path.exists() and not value['request'].get('resume_token'):
            output_path.replace(directory / 'previous-result.json')
        timed_out = invoke(request_path, output_path)
        if not output_path.is_file() or output_path.stat().st_size > 5_000_000:
            raise ValueError('搜索未返回可用结果；已有候选已保留，请稍后重试。')
        parsed = validate_result(json.loads(output_path.read_text(encoding='utf-8')), value)
        with LOCK:
            current = get(ident)  # Preserve selections saved while the process ran.
            merged = {row['video_id']: row for row in current['items']}
            merged.update({row['video_id']: row for row in parsed.pop('items')})
            if not parsed['resume_token']:
                parsed['resume_token'] = current.get('resume_token')
            current.update(parsed, items=list(merged.values()), state='finished',
                           message='搜索已结束。请人工判断内容价值，标题和点赞数不代表案例真实。')
            if timed_out:
                current.update(adapter_status='partial' if merged else 'error',
                               message='搜索超时；已经写入的候选保留，可手动继续。')
            save(current)
    except Exception as exc:
        with LOCK:
            current = get(ident)
            message = str(exc) if isinstance(exc, ValueError) else '搜索执行失败，请检查适配器状态；已有候选已保留。'
            # JSON parser errors can contain source fragments; use a fixed message.
            if isinstance(exc, json.JSONDecodeError):
                message = '适配器结果不是有效JSON；已有候选已保留。'
            current.update(state='failed', message=message, adapter_status='error')
            save(current)


def select(ident, revision, ids):
    with LOCK:
        value = get(ident)
        if revision != value['selection_revision']:
            raise RuntimeError('候选勾选已在其他页面更新，请刷新后重试。')
        known = {r['video_id'] for r in value['items']}
        if any(i not in known for i in ids):
            raise ValueError('勾选包含不属于当前批次的作品。')
        selectable = {r['video_id'] for r in value['items'] if r['media_type'] == 'video'}
        if any(i not in selectable for i in ids):
            raise ValueError('当前仅支持勾选视频作品，图片及类型未知不可选。')
        value.update(selected_ids=list(dict.fromkeys(ids)), selection_revision=revision + 1)
        save(value)
        return public(value)
