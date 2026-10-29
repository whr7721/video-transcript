"""Creator discovery and resumable batches, sharing the single video worker."""
import hashlib
import io
import json
import os
import subprocess
import time
import zipfile

import store
from batch_rules import classify_post, creator_id
from pipeline import ROOT, MC_PY, get_metadata, resolve_id
from session import prepare_session


def reconcile(task):
    children = [store.get(i) for i in task.get('children', [])]
    children = [c for c in children if c]
    task['counts'] = {s: sum(c['status'] == s for c in children)
                      for s in ['completed', 'failed', 'skipped', 'queued', 'running', 'paused', 'waiting_space']}
    task['items'] = [{k: c.get(k) for k in ['id', 'title', 'status', 'message', 'video_id', 'duration']} for c in children]
    if task['status'] == 'processing' and all(c['status'] in {'completed', 'failed', 'skipped'} for c in children):
        task['status'] = 'partial' if task['counts']['failed'] else 'completed'
        task['message'] = '本批处理结束；可下载已完成文稿。' + ('主页尚有未处理作品。' if task.get('has_more') else '')
    return task


def run_creator(task, update, enqueue):
    directory = store.DATA / 'batches' / task['id']
    directory.mkdir(parents=True, exist_ok=True)
    update(status='running', stage='listing', message='正在确认作者并读取主页作品', error=None)
    sec_uid = task.get('sec_uid') or creator_id(task['url'])
    author = task.get('author', '')
    if not sec_uid:
        video_id = resolve_id(task['url'])
        cached = next((t for t in store.all_tasks() if t.get('video_id') == video_id and t.get('kind') != 'creator'), None)
        seed_dir = store.DATA / 'jobs' / cached['id'] if cached else directory
        metadata = get_metadata(video_id, seed_dir)
        user = metadata['detail'].get('author', {})
        sec_uid, author = user.get('sec_uid'), user.get('nickname', '')
    if not sec_uid:
        raise RuntimeError('未取得真实作者编号，请提供抖音主页链接。')
    update(sec_uid=sec_uid, author=author, title=f'{author or "博主"} · 批量原文')
    from source_enumeration import enumerate_source
    listing=enumerate_source('douyin',f'https://www.douyin.com/user/{sec_uid}',task['limit'],_directory=directory,_max_duration_sec=task.get('max_duration_sec',600))['_listing']
    if listing.get('status') != 'ok':
        raise RuntimeError(listing.get('error', '主页获取失败，未假定全部作品已获取。'))
    children, skipped, candidates = [], {}, 0
    existing_tasks = store.all_tasks()
    for post in listing.get('posts', []):
        rule, duration = classify_post(post, task.get('max_duration_sec', 600))
        if rule not in {'eligible', 'unknown'}:
            skipped[rule] = skipped.get(rule, 0) + 1
            continue
        candidates += 1
        if len(children) >= task['limit']:
            continue
        video_id = str(post['aweme_id'])
        old = next((t for t in existing_tasks if t.get('video_id') == video_id and t.get('provider') == task['provider'] and t.get('kind') != 'creator'), None)
        if old:
            children.append(old['id'])
            continue
        url = f'https://www.douyin.com/video/{video_id}'
        ident = hashlib.sha256((url+'|'+task['provider']).encode()).hexdigest()[:16]
        child = {'id': ident, 'video_id': video_id, 'url': url, 'provider': task['provider'],
                 'parent_id': task['id'], 'expected_sec_uid': sec_uid, 'max_duration_sec': task.get('max_duration_sec', 600),
                 'keep_media': task.get('keep_media', False), 'title': post.get('desc') or '未命名视频',
                 'author': author, 'duration': duration, 'status': 'queued', 'stage': 'queued',
                 'message': '等待批量转写', 'created_at': time.time(), 'progress': 0, 'error': None}
        urls = listing.get('sources', {}).get(video_id, [])
        if urls:
            store.atomic_json(store.DATA/'jobs'/ident/'source.json', {'status': 'ok', 'detail': post, 'urls': urls})
        store.save(child)
        children.append(ident)
        existing_tasks.append(child)
    update(children=list(dict.fromkeys(children)), discovered=len(listing.get('posts', [])), skipped=skipped,
           has_more=bool(listing.get('has_more')) or candidates > len(children),
           scan_complete=bool(listing.get('scan_complete')), status='processing', stage='processing',
           message='作品列表已保存，正在逐条转写')
    for ident in dict.fromkeys(children):
        if store.get(ident)['status'] == 'queued':
            enqueue(ident)


def export_zip(task):
    task = reconcile(task)
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('批次索引.json', json.dumps(task, ensure_ascii=False, indent=2))
        for ident in task.get('children', []):
            child = store.get(ident)
            if child and child['status'] == 'completed':
                for suffix in ['txt', 'md']:
                    path = store.DATA/'jobs'/ident/f'transcript.{suffix}'
                    if path.is_file():
                        archive.write(path, f'{child.get("video_id", ident)}.{suffix}')
    return memory.getvalue()
