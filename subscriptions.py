"""Private discovery metadata, independent of media jobs."""
import json,time,uuid,threading,unicodedata
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,quote
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import store,source_enumeration as sources,link_ingest,link_jobs,link_batches
router=APIRouter(prefix='/api/subscriptions');STOP=threading.Event();THREAD=None
EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='source-check');LOCK=threading.RLock()
def init():
 with store.connect() as db:
  db.execute('CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY,url TEXT UNIQUE NOT NULL,platform TEXT NOT NULL,payload TEXT NOT NULL)')
  db.execute('CREATE TABLE IF NOT EXISTS feed_items(seq INTEGER PRIMARY KEY AUTOINCREMENT,channel_id TEXT NOT NULL,content_id TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(channel_id,content_id))')
def channels():
 init()
 with store.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM channels ORDER BY rowid DESC')]
def get(ident):
 for c in channels():
  if c['id']==ident:return c
 raise HTTPException(404,'订阅不存在')
def save(c):
 with store.connect() as db:db.execute('UPDATE channels SET payload=? WHERE id=?',(json.dumps(c,ensure_ascii=False),c['id']))
def check(ident,limit):
 try:
  c=get(ident);result=sources.enumerate_source(c['platform'],c.get('query') or c['url'],limit)
  with LOCK,store.connect() as db:
   # Unsubscribe while a request runs must not resurrect entries.
   current=db.execute('SELECT payload FROM channels WHERE id=?',(ident,)).fetchone()
   if not current:return
   c=json.loads(current[0])
   if c['platform']=='douyin_favorites' and c.get('identity') and c['identity']!=result['identity']:raise ValueError('收藏登录账号已变化，请退订后重新添加收藏源，已有文稿会保留')
   aliases=[json.loads(r[0]) for r in db.execute('SELECT payload FROM channels WHERE platform=? AND id!=?',(c['platform'],ident))]
   if any(a.get('identity')==result['identity'] for a in aliases):raise ValueError('该频道已有另一URL订阅，请使用已有订阅并退订此别名')
   first_check=not c.get('initialized')
   if not first_check and result.get('window_has_more') and result['items'] and not any(db.execute('SELECT 1 FROM feed_items WHERE channel_id=? AND content_id=?',(ident,r['id'])).fetchone() for r in result['items']):
    result.update(status='partial',message='最近检查窗口内全部是新收藏，可能还有未覆盖的新内容；请提高检查条数或缩短间隔，本次未宣称同步完整收藏')
   for row in reversed(result['items']):
    old=db.execute('SELECT payload FROM feed_items WHERE channel_id=? AND content_id=?',(ident,row['id'])).fetchone()
    if old:
     oldrow=json.loads(old[0]);oldrow.update(row);db.execute('UPDATE feed_items SET payload=? WHERE channel_id=? AND content_id=?',(json.dumps(oldrow,ensure_ascii=False),ident,row['id']))
    db.execute('INSERT OR IGNORE INTO feed_items(channel_id,content_id,payload) VALUES (?,?,?)',(ident,row['id'],json.dumps({**row,'read':False,'discovered_at':time.time(),'auto_pending':bool(not first_check and c.get('automation',{}).get('auto_extract'))},ensure_ascii=False)))
   c.update(initialized=True,title=result['title'],identity=result['identity'],status='idle' if result.get('status')=='ok' else 'partial',last_success=time.time() if result.get('status')=='ok' else c.get('last_success'),error=result.get('message') if result.get('status')!='ok' else None)
   db.execute('UPDATE channels SET payload=? WHERE id=?',(json.dumps(c,ensure_ascii=False),ident))
  dispatch_auto(ident)
 except Exception as e:
  with LOCK:
   try:c=get(ident)
   except HTTPException:return
   c.update(status='error',error=str(e) if isinstance(e,ValueError) else '检查未完成，请检查网络、登录状态后重试');save(c)
def recover():
 init()
 for c in channels():
  if c['status']=='checking':c.update(status='error',error='服务重启中断检查，请手动重试');save(c)
class Subscribe(BaseModel):
 url:str=Field(min_length=1,max_length=2000)
 confirm_topic:bool=False
class Check(BaseModel):limit:int=20
class Seen(BaseModel):seq:int|None=None;channel_id:str|None=None
class Extract(BaseModel):seqs:list[int]=Field(min_length=1,max_length=50);summarize:bool=False

def admit():link_batches.admit()
@router.get('/channels')
def listing():admit();return channels()
@router.post('/channels')
def subscribe(body:Subscribe):
 admit();init()
 from link_jobs import normalize
 try:
  query=None
  if '://' not in body.url:
   kind,query=sources.identify(unicodedata.normalize('NFKC',body.url).strip())
   if not body.confirm_topic:raise ValueError('纯文字将作为抖音话题持续追踪，请明确确认；仅在手动检查时搜索')
   url='douyin-topic:'+quote(query.casefold(),safe='')
  else:
   url=normalize(body.url);link_ingest.platform(url);kind,url=sources.identify(url)
   if kind=='single':
    if link_ingest.platform(url)!='rss':raise ValueError('请提供频道/博主主页，而不是单条视频链接')
    kind='rss'
   if kind not in {'rss','youtube','bilibili','douyin'} or (kind=='youtube' and urlsplit(url).path=='/playlist'):raise ValueError('请选择RSS、YouTube频道、B站UP主或抖音博主；播放列表仅支持即时展开')
   p=urlsplit(url);path=p.path.rstrip('/')
   if kind=='youtube':path=path.removesuffix('/videos').removesuffix('/shorts')
   if kind=='bilibili':path='/'+path.strip('/').split('/')[0]
   if kind=='douyin':path='/user/'+path.split('/user/')[1].split('/')[0]
   host='www.youtube.com' if kind=='youtube' else 'www.douyin.com' if kind=='douyin' else p.netloc.lower()
   url=urlunsplit((p.scheme,host,path,p.query if kind=='rss' else '', ''))
 except ValueError as e:raise HTTPException(400,str(e))
 with LOCK,store.connect() as db:
  old=db.execute('SELECT payload FROM channels WHERE url=?',(url,)).fetchone()
  if old:return json.loads(old[0])
  c={'id':uuid.uuid4().hex[:16],'url':url,'platform':kind,'title':('话题：'+query if query else url),'query':query,'added_at':time.time(),'last_check':None,'last_success':None,'cursor':0,'status':'idle','error':None}
  db.execute('INSERT INTO channels VALUES (?,?,?,?)',(c['id'],url,kind,json.dumps(c,ensure_ascii=False)));return c
@router.post('/favorites')
def favorites():
 admit();init()
 with LOCK,store.connect() as db:
  old=db.execute("SELECT payload FROM channels WHERE url='douyin-favorites:self'").fetchone()
  if old:return json.loads(old[0])
  c={'id':uuid.uuid4().hex[:16],'url':'douyin-favorites:self','platform':'douyin_favorites','title':'我的抖音收藏','added_at':time.time(),'last_check':None,'last_success':None,'cursor':0,'status':'idle','error':None}
  db.execute('INSERT INTO channels VALUES (?,?,?,?)',(c['id'],c['url'],c['platform'],json.dumps(c,ensure_ascii=False)));return c

class Automation(BaseModel):
 enabled:bool=False
 interval_minutes:int=Field(default=60,ge=15,le=1440)
 limit:int=Field(default=20,ge=10,le=50)
 auto_extract:bool=False
 daily_limit:int=Field(default=10,ge=1,le=50)

@router.put('/channels/{ident}/automation')
def automation(ident:str,body:Automation):
 admit()
 if body.limit not in {10,20,50}:raise HTTPException(400,'请选择10/20/50条')
 with LOCK:
  c=get(ident)
  if body.auto_extract and not c.get('initialized'):raise HTTPException(400,'请先检查一次并预览历史内容，再开启自动提取')
  c['automation']=body.model_dump();c['next_check']=time.time()+body.interval_minutes*60 if body.enabled else None;save(c)
 return c

@router.delete('/channels/{ident}')
def unsubscribe(ident:str):
 admit();get(ident)
 with LOCK,store.connect() as db:db.execute('DELETE FROM feed_items WHERE channel_id=?',(ident,));db.execute('DELETE FROM channels WHERE id=?',(ident,))
 return {'ok':True}
@router.post('/check')
def check_all(body:Check):
 admit()
 if body.limit not in {10,20,50}:raise HTTPException(400,'请选择10/20/50条')
 return {'sources':[start_check(c['id'],body.limit) for c in channels()]}
def start_check(ident,limit):
 with LOCK:
  c=get(ident)
  if c['status']!='checking':c.update(status='checking',last_check=time.time(),error=None);save(c);EXECUTOR.submit(check,ident,limit)
  return c
@router.post('/channels/{ident}/check')
def check_one(ident:str,body:Check):
 admit()
 if body.limit not in {10,20,50}:raise HTTPException(400,'请选择10/20/50条')
 return start_check(ident,body.limit)
@router.get('/feed')
def feed(unread:bool=True,channel_id:str|None=None):
 admit();mapping={c['id']:c for c in channels()};rows=[]
 with store.connect() as db:
  for r in db.execute('SELECT seq,channel_id,payload FROM feed_items ORDER BY seq DESC'):
   c=mapping.get(r['channel_id'])
   if not c or (channel_id and c['id']!=channel_id):continue
   row=json.loads(r['payload']);seen=row.get('read') or r['seq']<=c['cursor']
   if unread and seen:continue
   job=documents_job(row.get('job_id'))
   rows.append({**row,'seq':r['seq'],'channel_id':c['id'],'source_title':c['title'],'platform':c['platform'],'read':bool(seen),'job_status':job.get('status') if job else None,'task_id':job.get('task_id') if job else row.get('task_id')})
 return rows[:500]
def documents_job(ident):
 if not ident:return None
 import documents
 return documents.generation_get(ident)
@router.post('/seen')
def seen(body:Seen):
 admit();init()
 with LOCK,store.connect() as db:
  if body.seq is not None:
   r=db.execute('SELECT payload FROM feed_items WHERE seq=?',(body.seq,)).fetchone()
   if not r:raise HTTPException(404,'条目不存在')
   row=json.loads(r[0]);row['read']=True;db.execute('UPDATE feed_items SET payload=? WHERE seq=?',(json.dumps(row,ensure_ascii=False),body.seq))
  elif body.channel_id:
   c=get(body.channel_id);c['cursor']=db.execute('SELECT COALESCE(MAX(seq),0) FROM feed_items WHERE channel_id=?',(c['id'],)).fetchone()[0];db.execute('UPDATE channels SET payload=? WHERE id=?',(json.dumps(c,ensure_ascii=False),c['id']))
  else:raise HTTPException(400,'请指定条目或订阅源')
 return {'ok':True}
def rows_for(ids):
 init();rows=[]
 with store.connect() as db:
  for seq in dict.fromkeys(ids):
   r=db.execute('SELECT payload FROM feed_items WHERE seq=?',(seq,)).fetchone()
   if not r:raise HTTPException(404,'条目不存在')
   row=json.loads(r[0]);rows.append((seq,row))
 return rows
def bind(seq,job):
 with store.connect() as db:
  r=db.execute('SELECT payload FROM feed_items WHERE seq=?',(seq,)).fetchone()
  if r:
   row=json.loads(r[0]);row.update(job_id=job['id'],task_id=job['task_id']);db.execute('UPDATE feed_items SET payload=? WHERE seq=?',(json.dumps(row,ensure_ascii=False),seq))
@router.post('/extract')
def extract(body:Extract):
 admit()
 if len(body.seqs)!=1:raise HTTPException(400,'多项请进入批量预览')
 seq,row=rows_for(body.seqs)[0]
 existing=documents_job(row.get('job_id'))
 usable=existing and (existing['status'] in {'queued','running'} or (existing['status']=='completed' and store.get(existing['task_id']) and (store.DATA/'jobs'/existing['task_id']/'transcript.json').is_file()))
 if usable:
  if not body.summarize or existing.get('summarize'):return {**existing,'cached':existing['status']=='completed'}
  args=SimpleNamespace(**existing['arguments']);plan={**args.plan,'local':Path(args.plan['local'])}
 else:
  args=SimpleNamespace(url=row['url'],language='auto',episode=None,episode_id=row.get('episode_id'),episode_guid=row.get('episode_guid'),episode_snapshot=row.get('episode_snapshot'),summarize=False,allowed=list(link_batches.ALLOWED))
  try:plan=link_ingest.prepare(args)
  except ValueError as e:raise HTTPException(400,str(e))
 import app
 job=link_jobs.submit(args,plan,body.summarize,app.TASKS.put);bind(seq,job);return job
@router.post('/batch')
def batch(body:Extract):
 admit();rows=rows_for(body.seqs)
 preview=link_batches.preview(link_batches.Preview(rows=[link_batches.Row(text=r['url'],episode_id=r.get('episode_id'),episode_guid=r.get('episode_guid'),feed_seq=seq,summarize=body.summarize) for seq,r in rows]))
 return preview


def dispatch_auto(ident):
 """Persist batch references before starting; replay starts the same batch after a crash."""
 with LOCK:
  c=get(ident);config=c.get('automation',{})
  if not config.get('enabled') or not config.get('auto_extract'):return
  # Resume only drafts reserved by this source; paused/stopped batches stay stopped.
  with store.connect() as db:
   rows=[(r['seq'],json.loads(r['payload'])) for r in db.execute('SELECT seq,payload FROM feed_items WHERE channel_id=? ORDER BY seq',(ident,))]
  for bid in {r.get('auto_batch') for _,r in rows if r.get('auto_batch')}:
   b=link_batches.get(bid)
   if b['status']=='draft':link_batches.control(bid,'start')
  from datetime import datetime,timezone,timedelta
  day=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
  used=c.get('auto_count',0) if c.get('auto_day')==day else 0
  remaining=max(0,config.get('daily_limit',10)-used)
  pending=[(seq,r) for seq,r in rows if r.get('auto_pending') and not r.get('auto_batch')][:remaining]
  if not pending:return
  preview=batch(Extract(seqs=[seq for seq,_ in pending],summarize=False))
  if any(i['status']=='selection' for i in preview['items']):raise ValueError('自动收集遇到需手选的条目，请在时间线手动提取')
  with store.connect() as db:
   for seq,_ in pending:
    current=db.execute('SELECT payload FROM feed_items WHERE seq=? AND channel_id=?',(seq,ident)).fetchone()
    if current:
     r=json.loads(current[0]);r.update(auto_batch=preview['id'],auto_pending=False)
     db.execute('UPDATE feed_items SET payload=? WHERE seq=?',(json.dumps(r,ensure_ascii=False),seq))
   c=get(ident);c.update(auto_day=day,auto_count=used+len(pending),last_auto_batch=preview['id'])
   db.execute('UPDATE channels SET payload=? WHERE id=?',(json.dumps(c,ensure_ascii=False),ident))
  link_batches.control(preview['id'],'start')

def tick(now=None):
 if __import__('os').environ.get('SHIWEN_PUBLIC')=='1':return
 now=time.time() if now is None else now
 for c in channels():
  config=c.get('automation',{})
  if config.get('enabled') and c.get('status')!='checking' and (c.get('next_check') or 0)<=now:
   with LOCK:
    current=get(c['id'])
    config=current.get('automation',{})
    if not config.get('enabled') or current.get('status')=='checking' or (current.get('next_check') or 0)>now:continue
    current['next_check']=now+config.get('interval_minutes',60)*60;save(current)
    start_check(c['id'],config.get('limit',20))

def start():
 global THREAD
 if THREAD and THREAD.is_alive():return
 STOP.clear()
 def loop():
  while not STOP.is_set():
   try:tick()
   except Exception:__import__('logging').getLogger(__name__).exception('订阅定时检查未完成')
   STOP.wait(15)
 THREAD=threading.Thread(target=loop,daemon=True,name='shiwen-subscriptions');THREAD.start()

def stop():
 STOP.set()
 if THREAD:THREAD.join(timeout=2)
