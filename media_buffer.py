"""Owned media quota. Never evict active, unconfirmed, pinned or leased media."""
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
import store

CAPACITY = 5_000_000_000
LOCK = threading.RLock()


class BufferFull(RuntimeError):
    pass


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS media_buffer (id TEXT PRIMARY KEY, state TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, used_at REAL NOT NULL, lease_until REAL NOT NULL DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS media_reservations (token TEXT PRIMARY KEY,id TEXT NOT NULL,budget INTEGER NOT NULL,baseline INTEGER NOT NULL)')


def files(ident):
    base = (store.DATA / 'jobs').resolve()
    if not base.is_relative_to(store.DATA.resolve()):
        raise RuntimeError('媒体根目录不在本工具数据目录内。')
    directory = base / ident
    if not directory.resolve().is_relative_to(base) or directory.is_symlink():
        raise RuntimeError('媒体路径不在本工具目录内。')
    paths = [directory/name for name in ('original.mp4', 'original.media', 'original.part', 'audio.wav', 'audio.partial.wav')]
    paths += list((directory/'cloud_chunks').glob('*.mp3'))
    return [p for p in paths if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(base)]


def register(ident, pinned=False):
    with LOCK, store.connect() as db:
        init(db)
        db.execute("INSERT INTO media_buffer(id,state,pinned,used_at) VALUES (?,'active',?,?) ON CONFLICT(id) DO UPDATE SET state='active', pinned=MAX(pinned,excluded.pinned), used_at=excluded.used_at", (ident, int(pinned), time.time()))


def state(ident, value):
    with LOCK, store.connect() as db:
        init(db)
        db.execute('UPDATE media_buffer SET state=?, used_at=? WHERE id=?', (value, time.time(), ident))


def pin(ident, value):
    with LOCK, store.connect() as db:
        init(db)
        db.execute('UPDATE media_buffer SET pinned=? WHERE id=?', (int(value), ident))


def migrate_known():
    """Inventory known historical jobs without moving or deleting any files."""
    with LOCK, store.connect() as db:
        init(db)
        known={r[0] for r in db.execute('SELECT id FROM media_buffer')}
    for task in store.all_tasks():
        if task.get('kind') != 'creator' and task['id'] not in known and files(task['id']):
            register(task['id'],pinned=bool(task.get('keep_media',False)))
            state(task['id'],'awaiting_review')


def mark_evicted(ident):
    task=store.get(ident)
    if task and task['status']=='completed':
        local = task.get('source',{}).get('kind') == 'local_file'
        task.update(media_available=bool(files(ident)),message='文稿已保存，请重新选择原文件以补回媒体' if local else '文稿已保存，已清理的媒体可按需重新获取')
        store.save(task)


def touch(ident):
    with LOCK, store.connect() as db:
        init(db)
        db.execute('UPDATE media_buffer SET used_at=?,lease_until=? WHERE id=?', (time.time(), time.time()+300, ident))


def inventory():
    with store.connect() as db:
        init(db)
        rows = [dict(row) for row in db.execute('SELECT * FROM media_buffer ORDER BY used_at')]
    active={t['id'] for t in store.all_tasks() if t['status'] in {'queued','running','processing'} or t.get('media_restore_pending')}
    for row in rows:
        row['bytes'] = sum(p.stat().st_size for p in files(row['id']))
        row['evictable'] = row['state'] == 'finalized' and not row['pinned'] and row['lease_until'] < time.time() and row['id'] not in active
    return rows


def public():
    with LOCK:
        rows = inventory()
        return {'capacity_bytes': CAPACITY, 'used_bytes': sum(r['bytes'] for r in rows), 'reserved_bytes': reserved_bytes(),
                'reclaimable_bytes': sum(r['bytes'] for r in rows if r['evictable']),
                'protected_bytes': sum(r['bytes'] for r in rows if not r['evictable']),
                'waiting': sum(t['status'] == 'waiting_space' for t in store.all_tasks())}


def ensure_space(required=0):
    required = max(0, int(required))
    with LOCK:
        rows = inventory()
        promised = reserved_bytes()
        used = sum(r['bytes'] for r in rows) + promised
        for row in rows:
            if used + required <= CAPACITY and shutil.disk_usage(store.DATA).free >= required + promised + 100_000_000:
                return
            if row['evictable']:
                removed = 0
                for path in files(row['id']):
                    try:
                        size = path.stat().st_size
                        path.unlink()
                        removed += size
                    except OSError:
                        pass  # Windows can hold an open playback handle.
                used -= removed
                if removed: mark_evicted(row['id'])
        if used + required > CAPACITY or shutil.disk_usage(store.DATA).free < required + promised + 100_000_000:
            raise BufferFull('5GB缓冲区或磁盘空间不足。已保护待确认素材；请确认已完成文稿或取消不再需要的保留，再继续排队。')


def reserved_bytes():
    with store.connect() as db:
        init(db)
        rows = list(db.execute('SELECT id,budget,baseline FROM media_reservations'))
    return sum(max(0, r['budget'] - max(0, sum(p.stat().st_size for p in files(r['id'])) - r['baseline'])) for r in rows)


@contextmanager
def reserve(ident, budget):
    """Count promised output once; as it appears on disk, remaining promise shrinks."""
    token = uuid.uuid4().hex
    with LOCK:
        ensure_space(budget)
        baseline = sum(p.stat().st_size for p in files(ident))
        with store.connect() as db:
            init(db)
            db.execute('INSERT INTO media_reservations VALUES (?,?,?,?)', (token,ident,budget,baseline))
    try:
        yield
    finally:
        with LOCK, store.connect() as db:
            db.execute('DELETE FROM media_reservations WHERE token=?',(token,))


def recover_reservations():
    """Only call after acquiring the single-core-instance OS lock."""
    with LOCK, store.connect() as db:
        init(db)
        db.execute('DELETE FROM media_reservations')


def cleanup():
    with LOCK:
        removed = 0
        for row in inventory():
            if row['evictable']:
                for path in files(row['id']):
                    try:
                        size = path.stat().st_size
                        path.unlink()
                        removed += size
                    except OSError:
                        pass
                mark_evicted(row['id'])
        return removed
