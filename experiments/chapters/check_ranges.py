"""Read-only real transcript coverage check; outputs metadata, never source text."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import chapters


def check(database, maximum=3):
    connection=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        tasks=[json.loads(r[0]) for r in connection.execute('SELECT payload FROM tasks')]
    finally:connection.close()
    tasks=[t for t in tasks if t.get('status')=='completed' and len(t.get('result',{}).get('text','')) >= 1000]
    tasks.sort(key=lambda t:len(t['result']['text']),reverse=True)
    results=[]
    for task in tasks[:maximum]:
        before=hashlib.sha256(json.dumps(task,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        view=chapters.snapshot(task);plan=chapters.reading_sections(view)
        chapters.validate(view,plan)
        resolved=[chapters.resolve(view,plan,i) for i in range(len(plan['sections']))]
        assert ''.join(r['text'] for r in resolved)==''.join(s['text'] for s in view['sources'])
        assert before==hashlib.sha256(json.dumps(task,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        results.append({'task_id':task['id'],'characters':sum(len(s['text']) for s in view['sources']),
                        'source_hash':view['source_hash'],'sections':len(plan['sections']),
                        'segments':len(view['sources']),'lossless':True,'source_unchanged':True})
    return results

if __name__=='__main__':
    print(json.dumps([r for db in sys.argv[1:] for r in check(db)],ensure_ascii=False,indent=2))
