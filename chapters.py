"""Lossless chapter ranges and append-only navigation versions; no model calls."""
import hashlib
import json
import documents
import math
import time
import store

VERSION = 'chapter-source-v1'


def snapshot(task):
    sources = documents.sources(task)
    if not task.get('result', {}).get('segments'):
        sources = [{'id': 'seg-0', 'text': task.get('result', {}).get('text', '')}]
        sources = [s for s in sources if s['text'].strip()]
    # Hash segment boundaries and timing as well as words: both affect citations.
    if len(sources) > 12000 or sum(len(s['text']) for s in sources) > 200000:
        raise ValueError('原稿超过章节处理容量')
    canonical = json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return {'task_id': task['id'], 'version': VERSION,
            'source_hash': hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
            'sources': sources}


def fragments(view, limit=1200):
    if type(limit) is not int or limit < 1:
        raise ValueError('Invalid fragment limit')
    result = []
    for source in view['sources']:
        text = source['text']
        offset = 0
        while offset < len(text):
            end = min(offset + limit, len(text))
            if end < len(text):
                boundary = max(text.rfind(mark, offset, end) for mark in '。！？\n')
                if boundary >= offset + limit // 2:
                    end = boundary + 1
            result.append({'id': f"{source['id']}:{offset}:{end}",
                           'source_id': source['id'], 'start_offset': offset,
                           'end_offset': end, 'text': text[offset:end]})
            offset = end
    return result


def reading_sections(view, target=6000):
    if type(target) is not int or target < 1:
        raise ValueError('Invalid section target')
    parts = fragments(view, min(1200, target))
    groups, current, size = [], [], 0
    for part in parts:
        if current and size + len(part['text']) > target:
            groups.append(current)
            current, size = [], 0
        current.append(part)
        size += len(part['text'])
    if current:
        groups.append(current)
    sections = [{'title': f'阅读分段 {i + 1}', 'kind': 'reading',
                 'fragment_ids': [p['id'] for p in group]} for i, group in enumerate(groups)]
    return {'source_hash': view['source_hash'], 'fragment_limit': min(1200, target),
            'sections': sections}


def validate(view, plan):
    if not isinstance(plan, dict) or type(plan.get('fragment_limit')) is not int or not 1 <= plan['fragment_limit'] <= 1200:
        raise ValueError('章节片段大小无效')
    if not isinstance(plan.get('sections'), list) or len(plan['sections']) > 500:
        raise ValueError('章节列表无效')
    if plan.get('source_hash') != view['source_hash']:
        raise ValueError('原稿版本不匹配')
    expected = [p['id'] for p in fragments(view, plan['fragment_limit'])]
    actual = []
    for section in plan['sections']:
        if not isinstance(section, dict) or not isinstance(section.get('title'), str) or not 1 <= len(section['title'].strip()) <= 200:
            raise ValueError('章节标题无效')
        ids = section.get('fragment_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 200000 or any(not isinstance(i, str) for i in ids):
            raise ValueError('章节范围为空')
        actual.extend(ids)
    if actual != expected:
        raise ValueError('章节范围遗漏、重复或顺序错误')
    return True


def resolve(view, plan, index):
    validate(view, plan)
    if type(index) is not int or not 0 <= index < len(plan['sections']):
        raise ValueError('未知章节')
    parts = {p['id']: p for p in fragments(view, plan['fragment_limit'])}
    selected = [parts[key] for key in plan['sections'][index]['fragment_ids']]
    # Do not synthesize timestamps for partial segments or untimed sources.
    return {'source_hash': view['source_hash'], 'ranges': selected,
            'text': ''.join(p['text'] for p in selected)}


class Conflict(ValueError):
    pass


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS chapter_versions (task_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(task_id,revision))')


def get(task):
    view = snapshot(task)
    with store.connect() as db:
        init(db)
        row = db.execute('SELECT revision,payload FROM chapter_versions WHERE task_id=? ORDER BY revision DESC LIMIT 1', (task['id'],)).fetchone()
    if not row:
        return {**reading_sections(view), 'revision': 0, 'origin': 'reading', 'stale': False}
    value = json.loads(row['payload'])
    return {**value, 'revision': row['revision'], 'stale': value['source_hash'] != view['source_hash']}


def save(task, plan, revision):
    view = snapshot(task)
    validate(view, plan)
    if type(revision) is not int or revision < 0:
        raise ValueError('章节版本无效')
    payload = {k: plan[k] for k in ('source_hash', 'fragment_limit', 'sections')}
    payload.update(origin=plan.get('origin', 'manual'), created_at=time.time())
    for key in ('official_markers', 'warning'):
        if key in plan: payload[key] = plan[key]
    # Transaction serializes competing saves without overwriting any prior version.
    with store.connect() as db:
        init(db)
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT COALESCE(MAX(revision),0) FROM chapter_versions WHERE task_id=?', (task['id'],)).fetchone()[0]
        if current != revision:
            raise Conflict('章节版本已变化，请刷新后重试')
        db.execute('INSERT INTO chapter_versions VALUES (?,?,?)', (task['id'], revision+1, json.dumps(payload, ensure_ascii=False)))
    return {**payload, 'revision': revision+1, 'stale': False}


def official_plan(view, data, duration):
    if not isinstance(data, bytes) or not data or len(data) > 1_000_000:
        raise ValueError('章节文件为空或超过1MB')
    try:
        value = json.loads(data.decode('utf-8-sig'))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('章节JSON无效') from None
    if not isinstance(value, dict) or value.get('version') != '1.2':
        raise ValueError('仅支持JSON Chapters 1.2')
    rows = value.get('chapters')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError('章节数量无效')
    if isinstance(duration, bool) or not isinstance(duration, (int,float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('缺少可靠时长，不能映射官方时间')
    previous = -1
    visible = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict): raise ValueError('章节格式无效')
        start = row.get('startTime')
        end = row.get('endTime')
        if type(start) not in (int,float) or not math.isfinite(start) or not previous < start < duration:
            raise ValueError('章节时间越界或未严格递增')
        if end is not None and (type(end) not in (int,float) or not math.isfinite(end) or not start < end <= duration):
            raise ValueError('章节结束时间无效')
        if end is not None:
            following = rows[position+1].get('startTime') if position+1 < len(rows) and isinstance(rows[position+1], dict) else duration
            if type(following) not in (int,float) or end != following:
                raise ValueError('章节结束时间存在空隙或重叠，请改用阅读分段')
        if 'toc' in row and type(row['toc']) is not bool: raise ValueError('toc格式无效')
        previous = start
        if row.get('toc') is not False:
            title = row.get('title') or '未命名章节'
            if not isinstance(title, str) or len(title) > 200: raise ValueError('章节标题无效')
            visible.append({'time': start, 'title': title})
    parts = fragments(view)
    sources = {s['id']: s for s in view['sources']}
    if any(type(s.get('start')) not in (int,float) or not math.isfinite(s['start']) or not 0 <= s['start'] < duration for s in sources.values()):
        raise ValueError('原文没有可靠时间，不能强行映射章节')
    starts = [s['start'] for s in view['sources']]
    if starts != sorted(starts): raise ValueError('原文时间未按顺序排列')
    markers = ([{'time': 0, 'title': '开场（补充原文范围）', 'supplement': True}] if not visible or visible[0]['time'] > 0 else []) + visible
    sections = []
    for part in parts:
        timestamp = sources[part['source_id']]['start']
        marker = max((i for i,m in enumerate(markers) if m['time'] <= timestamp), default=0)
        if not sections or sections[-1]['marker'] != marker:
            sections.append({'title': markers[marker]['title'], 'kind': 'official', 'marker': marker,
                             'official_start': markers[marker]['time'], 'fragment_ids': []})
        sections[-1]['fragment_ids'].append(part['id'])
    plan = {'source_hash': view['source_hash'], 'fragment_limit': 1200, 'sections': sections,
            'origin': 'official', 'official_markers': rows,
            'warning': '时间按原始语音段近似映射；无对应文字的目录项不成为独立阅读章节。'}
    validate(view, plan)
    return plan
