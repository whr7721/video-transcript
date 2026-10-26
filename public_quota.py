"""Opt-in public request quotas. Cloud transcription is not gated in this phase."""
import os
import re
import sqlite3
import threading
import time
from fastapi import HTTPException, Request

PUBLIC = os.environ.get('SHIWEN_PUBLIC', '') == '1'
# Cloud transcribe will be wired when the public cloud-provider path is enabled.
LIMITS = {'editorial': (3, 10), 'classify': (3, 10),
          'question': (10, 20), 'research': (5, 10)}
DEVICE_PATTERN = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
OVER_LIMIT_MESSAGE = '今日免费次数已用完，明天再来。'
_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None


def _connection():
    global _CONN
    if _CONN is None:
        import store
        store.DATA.mkdir(parents=True, exist_ok=True)
        _CONN = sqlite3.connect(str(store.DATA/'public_quota.db'), check_same_thread=False)
        _CONN.execute('CREATE TABLE IF NOT EXISTS usage ('
                      'day TEXT NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, '
                      'count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day,kind,subject))')
        _CONN.commit()
    return _CONN


def _reset_for_tests():
    global _CONN
    with _LOCK:
        if _CONN is not None: _CONN.close()
        _CONN = None


def client_ip(request: Request):
    first = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    return (first or (request.client.host if request.client else 'unknown'))[:64]


def gate(kind: str, device: str, ip: str, today: str | None = None):
    if kind not in LIMITS: raise ValueError(f'unknown quota kind: {kind}')
    device_limit, ip_limit = LIMITS[kind]
    day = today or time.strftime('%Y-%m-%d')
    device_key = device if device else f'ip:{ip}'
    ip_key = f'ip:{ip}'
    with _LOCK:
        conn = _connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            rows = {}
            for subject in {device_key, ip_key}:
                row = conn.execute('SELECT count FROM usage WHERE day=? AND kind=? AND subject=?',
                                   (day, kind, subject)).fetchone()
                rows[subject] = row[0] if row else 0
            if rows[device_key] >= device_limit or rows[ip_key] >= ip_limit:
                raise HTTPException(429, OVER_LIMIT_MESSAGE)
            for subject in {device_key, ip_key}:
                conn.execute('INSERT INTO usage VALUES (?,?,?,1) '
                             'ON CONFLICT(day,kind,subject) DO UPDATE SET count=count+1',
                             (day, kind, subject))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {'device_remaining': max(0, device_limit-rows[device_key]-1),
                'ip_remaining': max(0, ip_limit-rows[ip_key]-1)}


def require_quota(kind: str):
    def dependency(request: Request):
        if not PUBLIC: return
        header = request.headers.get('x-device-id', '')
        device = header if DEVICE_PATTERN.fullmatch(header) else ''
        gate(kind, device, client_ip(request))
    return dependency


def settings_guard():
    if PUBLIC: raise HTTPException(403, '公开版不支持在线查看或修改设置。')
