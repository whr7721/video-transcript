"""Explicit real-model experiment. Credentials stay in memory; outputs stay in runtime."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['SHIWEN_DATA_DIR']=str(ROOT/'runtime/r2-a/preview-data')
import sys
sys.path.insert(0,str(ROOT))
import json,sqlite3,time
from datetime import datetime,timezone,timedelta
import settings,store,chapters,chapter_jobs,organizer,manuscript,documents

key=settings.protect(json.loads((ROOT/'data/settings.json').read_text(encoding='utf-8'))['encrypted_key'],decrypt=True)
settings.cloud_key=lambda:key
store.init()
day=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
# Conservatively inherit any higher existing daily usage; never reset or bypass quota.
used=0
for source in ('data','runtime/r1/core-data','runtime/r2-a/preview-data'):
    path=ROOT/source/'tasks.sqlite3'
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='organizer_calls'").fetchone():
        row=db.execute('SELECT count FROM organizer_calls WHERE day=?',(day,)).fetchone();used=max(used,row[0] if row else 0)
    db.close()
with store.connect() as db:
    db.execute('CREATE TABLE IF NOT EXISTS organizer_calls (day TEXT PRIMARY KEY,count INTEGER NOT NULL)')
    db.execute('INSERT INTO organizer_calls VALUES (?,?) ON CONFLICT(day) DO UPDATE SET count=max(count,excluded.count)',(day,used))
print('Daily usage before experiment:',used,flush=True)
original=organizer.request_json

def request(system,user,max_tokens=1400):
    started=time.monotonic()
    value,usage=original(system,user,max_tokens)
    print(json.dumps({'call_seconds':round(time.monotonic()-started,2),'tokens':usage.get('total_tokens'),'quota':chapter_jobs.quota()},ensure_ascii=True),flush=True)
    return value,usage
organizer.request_json=request

out=ROOT/'runtime/r2/real-model';out.mkdir(parents=True,exist_ok=True)
results=[]
original_checked=chapter_jobs.checked
def checked(window,value):
    try:return original_checked(window,value)
    except ValueError:
        (out/'rejected-window.json').write_text(json.dumps({'window':window,'value':value},ensure_ascii=False,indent=2),encoding='utf-8')
        raise
chapter_jobs.checked=checked
for folder,ident in [('runtime/r1/core-data','8235b98d9f210623'),('runtime/v1-b/core-data','b33db03eb1b9a504'),('runtime/r1/core-data','34b3090a47421637')]:
    db=sqlite3.connect((ROOT/folder/'tasks.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    task=json.loads(db.execute('SELECT payload FROM tasks WHERE id=?',(ident,)).fetchone()[0]);db.close()
    if not store.get(ident):store.save(task)
    plan=chapters.get(task)
    print('Starting directory',ident,chapter_jobs.estimate(task),flush=True)
    job=chapter_jobs.start(task,'directory',plan['revision'])
    while job['status'] in {'queued','running'}:
        time.sleep(1);job=chapter_jobs.get(job['id'])
    record={k:job.get(k) for k in ('id','task_id','status','calls','usage','elapsed_seconds','error')}
    if job.get('plan'):
        chapters.validate(chapters.snapshot(task),job['plan'])
        record['sections']=len(job['plan']['sections']);record['coverage_valid']=True
        current=chapters.get(task)
        saved=current if current['sections']==job['plan']['sections'] else chapters.save(task,job['plan'],current['revision']);record['revision']=saved['revision']
        (out/(ident+'-directory.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    results.append(record)
    print('Directory result',json.dumps(record,ensure_ascii=True),flush=True)
    (ROOT/'experiments/chapters/MODEL_RESULTS_20261023.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if job['status']!='completed':break
print('FINISHED',flush=True)
