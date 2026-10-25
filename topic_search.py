"""Local topic-scoped lexical retrieval. Derived indexes never edit source content."""
import hashlib
import json
import re
import unicodedata
import documents
import research
import store

VERSION = 'topic-bigram-v1'
CATEGORIES = {'all', 'personal', 'selection', 'original'}


def normalize(text):
    return unicodedata.normalize('NFKC', text).casefold()


def terms(text, unique=True):
    result = []
    for word in re.findall(r'[\u3400-\u9fff]+|[a-z0-9_]+', normalize(text)):
        if re.fullmatch('[a-z0-9_]+', word):
            result.append(word)
        elif len(word) >= 2:
            result.extend(word[i:i+2] for i in range(len(word)-1))
    return list(dict.fromkeys(result)) if unique else result


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS topic_search_state (topic_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS topic_search_passages (id INTEGER PRIMARY KEY, topic_id TEXT NOT NULL, uid TEXT NOT NULL, category TEXT NOT NULL, payload TEXT NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS topic_search_scope ON topic_search_passages(topic_id,category)')
    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS topic_search_fts USING fts5(tokens)')


def projection(db, topic_id):
    topic = db.execute('SELECT * FROM research_topics WHERE id=?', (topic_id,)).fetchone()
    if not topic:
        raise LookupError('专题不存在。')
    # Deliberately not research.note_list(): that reader is capped at 200 notes.
    rows = db.execute('SELECT n.*,j.payload FROM research_notes n LEFT JOIN research_jobs j ON j.id=n.job_id WHERE n.topic_id=? ORDER BY n.id', (topic_id,)).fetchall()
    records, warnings, seen = [], [], set()

    def add(uid, category, title, blocks, **extra):
        blocks = [b for b in blocks if b.get('text', '').strip()]
        if blocks:
            records.append({'uid': uid, 'category': category, 'title': title or '未命名来源',
                            'blocks': blocks, 'source_hash': digest(blocks), **extra})

    for row in rows:
        note_id = row['id']
        job = json.loads(row['payload']) if row['payload'] else None
        title = (job or {}).get('title') or topic['title']
        common = {'note_id': note_id, 'job_id': row['job_id']}
        add('note:'+note_id, 'personal', title, [{'id': 'personal', 'text': row['personal']}],
            version='note-'+str(row['revision']), basis='personal', **common)
        if not job:
            warnings.append('有笔记的深入记录缺失；个人理解仍可搜索。')
            continue
        ctx = job.get('context', {})
        add('selection:'+note_id, 'selection', title, [{'id': 'selection', 'text': ctx.get('selection', '')}],
            version=ctx.get('version', 'unknown'), basis=ctx.get('basis', 'unknown'), **common)
        task_id = job.get('task_id')
        if not task_id or task_id in seen:
            continue
        seen.add(task_id)
        source = db.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
        task = json.loads(source[0]) if source else None
        if not task or task.get('status') != 'completed' or task.get('kind') == 'creator':
            warnings.append('部分关联原稿尚未就绪或已不存在；保存选段仍保留。')
            continue
        add('transcript:'+task_id, 'original', task.get('title', title),
            documents.sources(task), version='original', basis='original', task_id=task_id)
    return dict(topic), records, list(dict.fromkeys(warnings))


def passages(records, limit=500):
    result = []
    for record in records:
        current, size = [], 0

        def emit():
            refs = [{k: r[k] for k in ('block_id', 'start', 'end')} for r in current]
            result.append({**{k: v for k, v in record.items() if k != 'blocks'},
                           'hit_id': digest([record['uid'], refs])[:32], 'ranges': refs,
                           'text': '\n\n'.join(r['text'] for r in current)})

        for block in record['blocks']:
            for start in range(0, len(block['text']), limit):
                text = block['text'][start:start+limit]
                if current and size+len(text) > limit:
                    emit(); current, size = [], 0
                current.append({'block_id': block['id'], 'start': start, 'end': start+len(text), 'text': text})
                size += len(text)
        if current:
            emit()
    return result


def sync(db, topic_id, records):
    fingerprint = digest([VERSION, records])
    old = db.execute('SELECT fingerprint FROM topic_search_state WHERE topic_id=?', (topic_id,)).fetchone()
    if old and old[0] == fingerprint:
        return
    db.execute('DELETE FROM topic_search_fts WHERE rowid IN (SELECT id FROM topic_search_passages WHERE topic_id=?)', (topic_id,))
    db.execute('DELETE FROM topic_search_passages WHERE topic_id=?', (topic_id,))
    for passage in passages(records):
        row = db.execute('INSERT INTO topic_search_passages(topic_id,uid,category,payload) VALUES (?,?,?,?)',
                         (topic_id, passage['uid'], passage['category'], json.dumps(passage, ensure_ascii=False)))
        db.execute('INSERT INTO topic_search_fts(rowid,tokens) VALUES (?,?)',
                   (row.lastrowid, ' '.join(terms(passage['text'], unique=False))))
    db.execute('INSERT OR REPLACE INTO topic_search_state VALUES (?,?)', (topic_id, fingerprint))


def marks(text, tokens):
    # Keep offsets in original Unicode code points, including width/case expansions.
    transformed, offsets = [], []
    for i, char in enumerate(text):
        folded = normalize(char)
        transformed.append(folded); offsets.extend([(i, i+1)]*len(folded))
    value = ''.join(transformed)
    if value != normalize(text):
        return []
    spans = []
    for token in tokens:
        start = 0
        while (pos := value.find(token, start)) >= 0:
            spans.append([offsets[pos][0], offsets[pos+len(token)-1][1]])
            start = pos+1
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def search(topic_id, query, category='all', offset=0, limit=10):
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ValueError('请输入1—200字的查询。')
    if category not in CATEGORIES or type(offset) is not int or not 0 <= offset <= 40 or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('搜索范围或分页不正确。')
    tokens = terms(query)
    literal = normalize(query).strip()
    single = not tokens and len(literal) == 1 and '\u3400' <= literal <= '\u9fff'
    with store.connect() as db:
        research.init(db); init(db)
        db.execute('BEGIN IMMEDIATE')
        topic, records, warnings = projection(db, topic_id)
        sync(db, topic_id, records)
        args = [topic_id, category, category]
        if tokens:
            expression = ' OR '.join('"'+t.replace('"', '""')+'"' for t in tokens)
            # Scope BEFORE LIMIT. BM25 corpus statistics cover this local index.
            rows = db.execute('SELECT p.payload,bm25(topic_search_fts) AS score FROM topic_search_fts JOIN topic_search_passages p ON p.id=topic_search_fts.rowid WHERE p.topic_id=? AND (?=\'all\' OR p.category=?) AND topic_search_fts MATCH ? ORDER BY score,p.id LIMIT 51', (*args, expression)).fetchall()
        elif single:
            rows = db.execute('SELECT payload,0 AS score FROM topic_search_passages WHERE topic_id=? AND (?=\'all\' OR category=?) AND instr(json_extract(payload,\'$.text\'),?)>0 ORDER BY id LIMIT 51', (*args, literal)).fetchall()
        else:
            rows = []
            warnings.append('请输入中文词语或英文名称；标点不能用于检索。')
        pool = [json.loads(r['payload']) for r in rows[:50]]
        visible = pool[offset:offset+limit]
        for item in visible:
            item['highlights'] = marks(item['text'], tokens or ([literal] if single else []))
        title_hits = [{k: r[k] for k in ('uid', 'category', 'title', 'version')} for r in records
                      if (category == 'all' or r['category'] == category) and literal in normalize(r['title'])][:10]
        return {'topic': {'id': topic['id'], 'title': topic['title']}, 'query': query, 'category': category,
                'method': 'literal_single' if single else 'bigram_bm25', 'items': visible,
                'offset': offset, 'has_more': offset+limit < len(pool), 'candidate_count': len(pool),
                'truncated': len(rows) > 50, 'title_matches': title_hits, 'warnings': warnings,
                'scope': {c: sum(r['category'] == c for r in records) for c in CATEGORIES-{'all'}}}


def context(topic_id, hit_id, source_hash):
    with store.connect() as db:
        research.init(db)
        db.execute('BEGIN')
        _, records, _ = projection(db, topic_id)
        # Resolve against fresh source snapshots, never against a stale index row.
        for record in records:
            for passage in passages([record]):
                if passage['hit_id'] != hit_id:
                    continue
                if passage['source_hash'] != source_hash:
                    raise documents.Conflict('内容已有变化，请重新搜索；未跳转到其他位置。')
                indices = {b['id']: i for i, b in enumerate(record['blocks'])}
                refs = {r['block_id']: r for r in passage['ranges']}
                first = min(indices[k] for k in refs); last = max(indices[k] for k in refs)
                blocks = []
                # Neighbors are previews, not an assertion of semantic support.
                for b in record['blocks'][max(0, first-1):last+2]:
                    ref = refs.get(b['id']); lo = max(0, ref['start']-180) if ref else 0
                    hi = min(len(b['text']), ref['end']+180) if ref else min(len(b['text']), 180)
                    blocks.append({**b, 'text': b['text'][lo:hi], 'offset': lo,
                                   'highlights': [[ref['start']-lo, ref['end']-lo]] if ref else [],
                                   'clipped': lo > 0 or hi < len(b['text'])})
                return {**passage, 'blocks': blocks}
    raise documents.Conflict('命中内容已不在该专题中，请重新搜索。')
