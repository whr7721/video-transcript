import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB = DATA / "tasks.sqlite3"


@contextmanager
def connect():
    DATA.mkdir(exist_ok=True)
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")


def save(task):
    task["updated_at"] = time.time()
    with connect() as db:
        db.execute("INSERT INTO tasks VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                   (task["id"], json.dumps(task, ensure_ascii=False)))


def get(task_id):
    with connect() as db:
        row = db.execute("SELECT payload FROM tasks WHERE id=?", (task_id,)).fetchone()
    return json.loads(row[0]) if row else None


def all_tasks():
    with connect() as db:
        rows = db.execute("SELECT payload FROM tasks").fetchall()
    return sorted((json.loads(r[0]) for r in rows), key=lambda t: t["created_at"], reverse=True)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
