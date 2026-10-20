"""Versioned local drafts; the transcription is never modified."""
import hashlib
import json
import time
import store


class Conflict(ValueError):
    pass


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, content TEXT NOT NULL, updated REAL NOT NULL, finalized REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS document_versions (id TEXT NOT NULL, revision INTEGER NOT NULL, content TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(id,revision))')
    db.execute('CREATE TABLE IF NOT EXISTS generations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')


def sources(task):
    segments = task.get('result', {}).get('segments', [])
    if not segments:
        segments = [{'text': task.get('result', {}).get('text', ''), 'start': 0, 'end': task.get('duration', 0)}]
    return [{**s, 'id': f'seg-{i}'} for i, s in enumerate(segments) if s.get('text', '').strip()]


def baseline(task):
    return {'type': 'doc', 'content': [{'type': 'paragraph', 'attrs': {'id': f'block-{s["id"]}', 'sourceIds': [s['id']]},
                                      'content': [{'type': 'text', 'text': s['text']}]} for s in sources(task)]}


def validate(content):
    count, length = 0, 0
    def visit(node, depth=0):
        nonlocal count, length
        count += 1
        if depth > 12 or count > 12000 or not isinstance(node, dict):
            raise ValueError('文稿结构过大或格式不正确。')
        kind = node.get('type')
        if kind not in {'doc', 'paragraph', 'heading', 'text', 'bulletList', 'orderedList', 'listItem', 'blockquote', 'hardBreak', 'horizontalRule'}:
            raise ValueError('文稿包含不支持的格式，请仅使用标题、段落、列表和引用。')
        out = {'type': kind}
        if kind == 'text':
            value = node.get('text', '')
            if not isinstance(value, str): raise ValueError('正文格式不正确。')
            length += len(value)
            if not value or length > 200000: raise ValueError('正文为空或超过20万字限制。')
            out['text'] = value
            marks = node.get('marks', [])
            out['marks'] = [{'type': m['type']} for m in marks if isinstance(m, dict) and m.get('type') in {'bold','italic','underline','strike'}]
        attrs = node.get('attrs') or {}
        if not isinstance(attrs, dict): raise ValueError('段落属性不正确。')
        safe = {}
        if kind in {'paragraph','heading','blockquote','listItem'}:
            if isinstance(attrs.get('id'), str): safe['id'] = attrs['id'][:100]
            if isinstance(attrs.get('sourceIds'), list): safe['sourceIds'] = [s[:60] for s in attrs['sourceIds'] if isinstance(s,str)][:100]
        if kind == 'heading': safe['level'] = int(attrs.get('level', 2)) if attrs.get('level') in (1,2,3) else 2
        if kind == 'orderedList': safe['start'] = 1
        if safe: out['attrs'] = safe
        children = node.get('content', [])
        if not isinstance(children, list): raise ValueError('文稿格式不正确。')
        child_types = {'doc':{'paragraph','heading','bulletList','orderedList','blockquote','horizontalRule'},
                       'paragraph':{'text','hardBreak'},'heading':{'text','hardBreak'},
                       'bulletList':{'listItem'},'orderedList':{'listItem'},
                       'listItem':{'paragraph','heading','bulletList','orderedList','blockquote'},
                       'blockquote':{'paragraph','heading','bulletList','orderedList'},
                       'text':set(),'hardBreak':set(),'horizontalRule':set()}
        if any(not isinstance(c,dict) or c.get('type') not in child_types[kind] for c in children):
            raise ValueError('文稿的段落或列表嵌套不正确。')
        if children: out['content'] = [visit(child, depth+1) for child in children]
        return out
    if content.get('type') != 'doc': raise ValueError('文稿根节点必须是文档。')
    return visit(content)


def text(content):
    def visit(node):
        if node['type'] == 'text': return node['text']
        if node['type'] == 'hardBreak': return '\n'
        separator = '\n\n' if node['type'] in {'doc','bulletList','orderedList','blockquote','listItem'} else ''
        return separator.join(visit(c) for c in node.get('content', []))
    return visit(content)


def get(task):
    with store.connect() as db:
        init(db)
        initial = json.dumps(baseline(task), ensure_ascii=False)
        db.execute('INSERT OR IGNORE INTO documents VALUES (?,1,?,?,NULL)', (task['id'], initial, time.time()))
        row = db.execute('SELECT * FROM documents WHERE id=?', (task['id'],)).fetchone()
        db.execute('INSERT OR IGNORE INTO document_versions VALUES (?,?,?,?)', (task['id'], row['revision'], row['content'], row['updated']))
        versions = [dict(r) for r in db.execute('SELECT revision,created FROM document_versions WHERE id=? ORDER BY revision DESC LIMIT 60', (task['id'],))]
        jobs = [json.loads(r[0]) for r in db.execute('SELECT payload FROM generations WHERE json_extract(payload,\'$.task_id\')=? ORDER BY rowid DESC LIMIT 20', (task['id'],))]
    return {'task_id': task['id'], 'revision': row['revision'], 'content': json.loads(row['content']),
            'updated_at': row['updated'], 'finalized_at': row['finalized'], 'sources': sources(task), 'versions': versions, 'generations': jobs}


def save(task, revision, content, finalize=False):
    content = validate(content)
    encoded = json.dumps(content, ensure_ascii=False)
    get(task)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM documents WHERE id=?', (task['id'],)).fetchone()
        if row['revision'] != revision: raise Conflict('这份文稿已有更新，请先保留本地草稿并重新加载；没有覆盖较新的版本。')
        updated = time.time()
        number = revision + 1
        db.execute('UPDATE documents SET revision=?,content=?,updated=?,finalized=? WHERE id=?', (number, encoded, updated, updated if finalize else None, task['id']))
        db.execute('INSERT INTO document_versions VALUES (?,?,?,?)', (task['id'], number, encoded, updated))
        db.execute('DELETE FROM document_versions WHERE id=? AND revision!=1 AND revision NOT IN (SELECT revision FROM document_versions WHERE id=? ORDER BY revision DESC LIMIT 60)', (task['id'],task['id']))
    import media_buffer
    media_buffer.state(task['id'], 'finalized' if finalize else 'awaiting_review')
    return get(task)


def generation_save(job):
    job['updated_at'] = time.time()
    with store.connect() as db:
        init(db)
        db.execute('INSERT INTO generations VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (job['id'], json.dumps(job, ensure_ascii=False)))


def generation_get(ident):
    with store.connect() as db:
        init(db)
        row = db.execute('SELECT payload FROM generations WHERE id=?', (ident,)).fetchone()
    return json.loads(row[0]) if row else None
