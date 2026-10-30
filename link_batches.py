"""Private reference batches. Scheduling never executes media itself."""
import io,json,os,re,threading,time,uuid,zipfile,logging
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
import store,documents,link_ingest,link_jobs,organizer

router=APIRouter(prefix='/api/link-batches')
LOCK=threading.RLock();STOP=threading.Event();THREAD=None;BUSY=False;INFLIGHT=None;CURSOR=None
ALLOWED=('youtube','bilibili','douyin','rss','tiktok','twitter','xiaoyuzhou','spotify','xiaohongshu')

def init():
 with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS link_batches(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
def save(batch):
 batch['updated_at']=time.time()
 with store.connect() as db:db.execute('INSERT INTO link_batches VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(batch['id'],json.dumps(batch,ensure_ascii=False)))
def all_batches():
 init()
 with store.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM link_batches')]
def get(ident):
 if not re.fullmatch('[a-f0-9]{16}',ident):raise HTTPException(404,'批次不存在')
 init()
 with store.connect() as db:r=db.execute('SELECT payload FROM link_batches WHERE id=?',(ident,)).fetchone()
 if not r:raise HTTPException(404,'批次不存在')
 return json.loads(r[0])
def quota():
 day=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d');limit=organizer.daily_call_limit(day)
 with store.connect() as db:
  exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='organizer_calls'").fetchone()
  row=db.execute('SELECT count FROM organizer_calls WHERE day=?',(day,)).fetchone() if exists else None
 return {'day':day,'remaining':None if limit is None else max(0,limit-(row[0] if row else 0)),'limit':limit}
def summary_need(task_id):
 folder=store.DATA/'jobs'/task_id;path=folder/'transcript.json'
 if not path.is_file():return 2
 import hashlib,cli_summary,mindmap
 fingerprint=hashlib.sha256(task_id.encode()+path.read_bytes()+cli_summary.VERSION.encode()+organizer.MODEL.encode()+mindmap.VERSION.encode()).hexdigest()[:16]
 job=documents.generation_get(fingerprint) or {}
 return 0 if job.get('bundle') else 1 if job.get('content') else 2

def reconcile(batch):
 for item in batch['items']:
  if item.get('job_id') and item['status'] not in {'stopped','invalid','duplicate','selection'}:
   job=documents.generation_get(item['job_id'])
   if job:
    item.update(task_id=job['task_id'],stage=job.get('stage'),error=job.get('error'))
    item['status']=('waiting_summary' if item.get('summarize') and not job.get('summarize') else 'completed') if job['status']=='completed' else job['status']
    task=store.get(job['task_id'])
    if not item.get('summarize') and job.get('summarize') and task and task['status']=='completed' and (store.DATA/'jobs'/job['task_id']/'transcript.json').is_file():item['status']='completed'
    if item.get('summarize') and job['status']=='failed' and job.get('summarize') and '请求上限' in (job.get('error') or '') and (store.DATA/'jobs'/job['task_id']/'transcript.json').is_file():item['status']='waiting_summary'
 batch['counts']={s:sum(i['status']==s for i in batch['items']) for s in ('waiting','queued','running','completed','failed','waiting_summary','stopped','invalid','duplicate','selection')}
 if batch['status']=='active' and not any(i['status'] in {'waiting','queued','running','waiting_summary'} for i in batch['items']):batch['status']='partial' if batch['counts']['failed'] or batch['counts']['invalid'] else 'completed'
 return batch

def set_busy(value):
 global BUSY
 with LOCK:BUSY=value

def pump(enqueue,queue_empty):
 global INFLIGHT,CURSOR
 with LOCK:
  if INFLIGHT:
   job=documents.generation_get(INFLIGHT)
   if job and job['status'] in {'queued','running'}:return
   INFLIGHT=None
  batches=sorted(all_batches(),key=lambda b:b['created_at'])
  for b in batches:
   if b['status']!='draft':reconcile(b);save(b)
  if BUSY or not queue_empty():return
  active=[b for b in batches if b['status']=='active']
  if CURSOR in [b['id'] for b in active]:
   n=next(i for i,b in enumerate(active) if b['id']==CURSOR)+1;active=active[n:]+active[:n]
  for b in active:
   for item in b['items']:
    if item['status'] not in {'waiting','waiting_summary'}:continue
    want=item['status']=='waiting_summary'
    if want:
     remain=quota()['remaining'];need=summary_need(item['task_id'])
     if remain is not None and remain<need:continue
    args=SimpleNamespace(url=item['url'],language=b['language'],episode=item.get('episode'),summarize=False,allowed=list(ALLOWED))
    plan={**item['plan'],'local':Path(item['plan']['local'])}
    try:
     job=link_jobs.submit(args,plan,want,enqueue,batch_id=b['id'])
     item.update(job_id=job['id'],task_id=job['task_id'],status=job['status'],stage=job.get('stage'),error=None)
     for alias in b['items']:
      if alias is item or (alias['status']=='duplicate' and alias.get('task_id')==job['task_id']):
       if alias.get('feed_seq'):
        import subscriptions;subscriptions.bind(alias['feed_seq'],job)
       if alias['status']=='duplicate':alias['job_id']=job['id']
     INFLIGHT=job['id'] if job['status'] in {'queued','running'} else None
    except Exception:item.update(status='failed',error='无法派发，请重试此项')
    CURSOR=b['id'];save(b);return

def start(enqueue,queue_empty):
 global THREAD,INFLIGHT,CURSOR,BUSY
 init();STOP.clear();INFLIGHT=None;CURSOR=None;BUSY=False
 for b in all_batches():
  if b['status']=='active':b.update(status='paused',message='服务重启，已有成果保留，请手动继续');reconcile(b);save(b)
 def loop():
  while not STOP.wait(.3):
   try:pump(enqueue,queue_empty)
   except Exception:
    logging.getLogger(__name__).error('批次调度暂时失败，已有文稿保持不变；请查看批次状态')
    try:
     with LOCK:
      for b in all_batches():
       if b['status']=='active':b.update(status='paused',message='调度中断，已有成果保留，请手动继续');save(b)
    except Exception:logging.getLogger(__name__).error('暂时无法保存批次状态，请检查数据目录')
 THREAD=threading.Thread(target=loop,daemon=True,name='link-batch-dispatch');THREAD.start()
def stop():
 STOP.set()
 if THREAD:THREAD.join(timeout=3)

class Row(BaseModel):
 text:str=Field(max_length=5000,min_length=1)
 episode:int|None=Field(default=None,ge=1,le=500)
 episode_guid:str|None=Field(default=None,max_length=2000)
 episode_id:str|None=Field(default=None,max_length=100)
 feed_seq:int|None=None
 summarize:bool=False
class Preview(BaseModel):
 rows:list[Row]=Field(min_length=1,max_length=50)
 language:link_jobs.Input.model_fields['language'].annotation='auto'

def admit():
 if os.environ.get('SHIWEN_PUBLIC')=='1':raise HTTPException(403,'批量链接仅支持本机私有版')

@router.post('/preview')
def preview(body:Preview):
 admit();init();items=[];seen={}
 for n,row in enumerate(body.rows,1):
  item={'index':n,'text':row.text,'episode':row.episode,'summarize':row.summarize,'status':'waiting','feed_seq':row.feed_seq,'episode_id':row.episode_id,'episode_guid':row.episode_guid}
  try:
   url=link_jobs.normalize(row.text);kind=link_ingest.platform(url);item.update(url=url,platform=kind)
   args=SimpleNamespace(url=url,episode=row.episode,episode_id=row.episode_id,episode_guid=row.episode_guid,language=body.language,allowed=ALLOWED,summarize=False)
   if kind not in ALLOWED:raise ValueError('不支持此平台')
   # Video identity is local work; only RSS preview performs feed requests.
   existing=None
   if row.feed_seq is not None:
    import subscriptions
    _,source= subscriptions.rows_for([row.feed_seq])[0]
    if source['url']!=url:raise ValueError('订阅引用与输入链接不一致')
    args.episode_guid=source.get('episode_guid');args.episode_id=source.get('episode_id');args.episode_snapshot=source.get('episode_snapshot')
    existing=subscriptions.documents_job(source.get('job_id'))
   if existing and existing['arguments'].get('language')==body.language and (existing['status'] in {'queued','running'} or (existing['status']=='completed' and (store.DATA/'jobs'/existing['task_id']/'transcript.json').is_file())):
    plan={**existing['arguments']['plan'],'local':Path(existing['arguments']['plan']['local'])}
   else:plan=link_ingest.prepare(args)
   item['url']=args.url
   if 'feed' in plan:item.update(status='selection',feed=plan['feed'])
   elif plan['ident'] in seen:
    item.update(status='duplicate',task_id=plan['ident']);seen[plan['ident']]['summarize']|=row.summarize
   else:
    seen[plan['ident']]=item;item['plan']={**plan,'local':str(plan['local'])};item['task_id']=plan['ident']
  except Exception:item.update(status='invalid',error='链接无效或RSS暂时无法读取，请修改后重新预览')
  items.append(item)
 batch={'id':uuid.uuid4().hex[:16],'status':'draft','created_at':time.time(),'language':body.language,'items':items}
 n=sum(i['summarize'] and i['status']=='waiting' for i in items);batch['estimate']={'selected':n,'requests':2*n,**quota()};save(batch);return batch
@router.get('')
def listing():
 admit();return [reconcile(b) for b in sorted((b for b in all_batches() if b['status']!='draft'),key=lambda b:b['created_at'],reverse=True)[:30]]
@router.get('/{ident}')
def status(ident:str):
 admit();return reconcile(get(ident))
@router.post('/{ident}/{action}')
def control(ident:str,action:str):
 admit()
 with LOCK:
  b=get(ident);reconcile(b)
  if action in {'start','resume'}:
   if b['status']=='draft' and any(i['status']=='selection' for i in b['items']):raise HTTPException(400,'请先选择RSS单集并重新预览')
   if action=='resume':
    for item in b['items']:
     if item['status']=='failed' and '服务重启' in (item.get('error') or ''):item.update(status='waiting',job_id=None,error=None)
   b['status']='active'
  elif action=='pause':b['status']='paused'
  elif action=='stop':
   b['status']='stopped'
   for item in b['items']:
    if item['status']=='queued' and item.get('job_id'):
     with link_jobs.LOCK:
      job=documents.generation_get(item['job_id'])
      shared=any(o['id']!=ident and any(i.get('job_id')==item['job_id'] and i['status'] not in {'stopped','duplicate'} for i in o['items']) for o in all_batches())
      if job and job['status']=='queued' and job.get('created_by_batch') and not job.get('single_requested',True) and not shared:
       message='批次已停止，尚未开始的任务未执行'
       job.update(status='failed',error=message,message=message);documents.generation_save(job)
       task=store.get(job['task_id'])
       if task and task['status']!='completed':task.update(status='failed',stage='stopped',message=message);store.save(task)
    if item['status'] in {'waiting','queued','waiting_summary'}:item['status']='stopped'
  elif action=='retry':
   b['status']='active'
   for item in b['items']:
    if item['status']=='failed':item.update(status='waiting',job_id=None,error=None)
  else:raise HTTPException(404)
  save(b);return b
@router.get('/{ident}/export')
def export(ident:str):
 admit();b=reconcile(get(ident));output=io.BytesIO();manifest=[]
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for item in b['items']:
   entry={k:item.get(k) for k in ('index','url','status','task_id','job_id','error')};entry['files']=[];entry['missing']=[]
   from document_exports import write_task
   entry=write_task(z,item)
   manifest.append(entry)
  z.writestr('batch-manifest.json',json.dumps({'id':b['id'],'items':manifest},ensure_ascii=False,indent=2))
 return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="shiwen-batch-{ident}.zip"'})
