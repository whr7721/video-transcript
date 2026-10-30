"""Private discovery metadata, independent of media jobs."""
import json,time,uuid,threading,unicodedata
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,quote
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import store,source_enumeration as sources,link_ingest,link_jobs,link_batches
router=APIRouter(prefix='/api/subscriptions');EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='source-check');LOCK=threading.RLock()
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
   aliases=[json.loads(r[0]) for r in db.execute('SELECT payload FROM channels WHERE platform=? AND id!=?',(c['platform'],ident))]
   if any(a.get('identity')==result['identity'] for a in aliases):raise ValueError('该频道已有另一URL订阅，请使用已有订阅并退订此别名')
   for row in reversed(result['items']):
    old=db.execute('SELECT payload FROM feed_items WHERE channel_id=? AND content_id=?',(ident,row['id'])).fetchone()
    if old:
     oldrow=json.loads(old[0]);oldrow.update(row);db.execute('UPDATE feed_items SET payload=? WHERE channel_id=? AND content_id=?',(json.dumps(oldrow,ensure_ascii=False),ident,row['id']))
    db.execute('INSERT OR IGNORE INTO feed_items(channel_id,content_id,payload) VALUES (?,?,?)',(ident,row['id'],json.dumps({**row,'read':False,'discovered_at':time.time()},ensure_ascii=False)))
   c.update(title=result['title'],identity=result['identity'],status='idle' if result.get('status')=='ok' else 'partial',last_success=time.time() if result.get('status')=='ok' else c.get('last_success'),error=result.get('message') if result.get('status')!='ok' else None)
   db.execute('UPDATE channels SET payload=? WHERE id=?',(json.dumps(c,ensure_ascii=False),ident))
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
