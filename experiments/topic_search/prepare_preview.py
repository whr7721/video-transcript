"""Prepare an isolated, explicitly marked fixture profile without copying credentials."""
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parents[2]
target=ROOT/'runtime/k1-production/preview-data'
if target.exists():
    raise RuntimeError('预览目录已存在，拒绝覆盖；可继续使用原验收目录。')
source=max((ROOT/'runtime/k1-production/real-corpus').glob('acceptance-*.sqlite3'),key=lambda p:p.stat().st_mtime)
target.mkdir()
with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as origin, sqlite3.connect(target/'tasks.sqlite3') as destination:
    origin.backup(destination)
    destination.execute("UPDATE research_topics SET title='K1验收专题（夹具笔记）' WHERE id='acceptance'")
(target/'.core-profile').write_text('core-v1',encoding='utf-8')
print(str(target))
