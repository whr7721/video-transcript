"""Persistent link workflow owned by each entry point's serial media queue."""
import hashlib,json,os,re,threading,time
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
import documents,store,link_ingest
import httpx

LOCK=threading.RLock()
ACTION='link_ingest'

class Input(BaseModel):
    url:str=Field(min_length=1,max_length=5000)
    language:Literal['auto','zh','en','ja','ko','yue']='auto'
    episode:int|None=Field(default=None,ge=1,le=500)
    summarize:bool=False

def normalize(text):
    urls=re.findall(r'https://[^\s<>"\']+',text)
    if len(urls)!=1:raise ValueError('请一次粘贴一个HTTPS链接')
    return urls[0].rstrip('，。；！）)]}')

def get(ident):
    if not re.fullmatch('[a-f0-9]{16}',ident):raise HTTPException(404,'链接任务不存在')
    job=documents.generation_get(ident)
    if not job or job.get('action')!=ACTION:raise HTTPException(404,'链接任务不存在')
    return job

def history(job,**fields):
    # Only finite stage transitions are retained; never store transcript progress text here.
    if fields.get('stage')=='completed':fields['stage']='transcribed'
    stage=fields.get('stage')
    if stage and (not job.get('stages') or job['stages'][-1]['stage']!=stage):
        job.setdefault('stages',[]).append({'stage':stage,'at':time.time()})
    job.update({k:v for k,v in fields.items() if k in {'stage','message','cached','progress','segment_count'}})
    documents.generation_save(job)

def run(task,update):
    job=get(task['link_job_id'])
    if job['status'] not in {'queued','running'}:return
    args=SimpleNamespace(**job['arguments']);args.plan={**args.plan,'local':Path(args.plan['local'])}
    job.update(status='running',error=None);documents.generation_save(job)
    try:
        link_ingest.add(args,lambda **f:history(job,**f))
        path=store.DATA/'jobs'/task['id']
        result=json.loads((path/'transcript.json').read_text(encoding='utf8'))
        update(status='completed',stage='completed',result=result,title=result.get('title','文稿'),duration=result.get('duration'))
        if job.get('summarize'):
            from cli_summary import summarize
            history(job,stage='summarizing',message='正在整理，原稿已保存')
            summarize(path)
        job.update(status='completed',completed_at=time.time())
        history(job,stage='done',message='处理完成')
    except Exception as exc:
        message=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else '链接处理失败，请检查网络或登录状态后重试'
        job.update(status='failed',error=message);documents.generation_save(job)
        if not (store.DATA/'jobs'/task['id']/'transcript.json').exists():update(status='failed',stage='failed',error=message,message=message)

def recover():
    with store.connect() as db:
        documents.init(db);jobs=[json.loads(r[0]) for r in db.execute('SELECT payload FROM generations')]
    for job in jobs:
        if job.get('action')==ACTION and job['status'] in {'queued','running'}:
            job.update(status='failed',error='服务重启中断了链接任务；缓存已保留，请点击重试');documents.generation_save(job)
            t=store.get(job['task_id'])
            if t and t['status'] in {'queued','running'}:t.update(status='failed',message=job['error']);store.save(t)

def router(enqueue,allowed):
    api=APIRouter(prefix='/api/link')
    @api.get('')
    def recent(task_id:str|None=None):
        with store.connect() as db:
            documents.init(db)
            jobs=[json.loads(r[0]) for r in db.execute('SELECT payload FROM generations')]
        return sorted((j for j in jobs if j.get('action')==ACTION and (task_id is None or j['task_id']==task_id)),key=lambda j:j['created_at'],reverse=True)[:20]
    @api.get('/capabilities')
    def capabilities():return {'platforms':list(allowed),'summarize':True}
    def admit():
        if os.environ.get('SHIWEN_PUBLIC')=='1':raise HTTPException(403,'链接处理仅支持本机入口')
    @api.post('')
    def create(body:Input):
        admit()
        try:
            url=normalize(body.url);kind=link_ingest.platform(url)
            if kind not in allowed:raise ValueError('此版本不支持抖音链接' if kind=='douyin' else '此版本不支持此平台链接')
            args=SimpleNamespace(url=url,language=body.language,episode=body.episode,summarize=False,allowed=list(allowed))
            plan=link_ingest.prepare(args)
            if 'feed' in plan:return {'selection_required':True,'feed':plan['feed']}
        except ValueError as exc:raise HTTPException(400,str(exc))
        except httpx.HTTPError:raise HTTPException(502,'无法读取播客，请检查网络后重试')
        ident=plan['ident'];jid=hashlib.sha256((ident+'|link|'+str(body.summarize)).encode()).hexdigest()[:16]
        with LOCK:
            job=documents.generation_get(jid)
            if job and (job['status'] in {'queued','running'} or (job['status']=='completed' and (store.DATA/'jobs'/ident/'transcript.json').is_file())):return {**job,'cached':job['status']=='completed'}
            active=store.get(ident)
            if active and active.get('link_job_id') and active['link_job_id']!=jid:
                other=documents.generation_get(active['link_job_id'])
                if other and other['status'] in {'queued','running'}:return other
            args.plan={**plan,'local':str(plan['local'])}
            job={'id':jid,'task_id':ident,'action':ACTION,'status':'queued','stage':'queued','stages':[],'created_at':time.time(),'arguments':{**vars(args),'summarize_requested':body.summarize}}
            job['arguments'].pop('summarize_requested');job['summarize']=body.summarize
            task=active or dict(id=ident,url=url,provider='local',language=body.language,created_at=time.time(),status='queued',source={'kind':'link','platform':kind})
            task['source']={'kind':'link','platform':kind};task['link_job_id']=jid
            if task.get('status')!='completed':task.update(status='queued',stage='queued')
            store.save(task);documents.generation_save(job)
            enqueue(ident)
            return job
    @api.get('/{ident}/export/{filename}')
    def export(ident:str,filename:str):
        job=get(ident)
        if filename not in {'summary.md','mindmap.html'}:raise HTTPException(404)
        path=store.DATA/'jobs'/job['task_id']/filename
        if not path.is_file():raise HTTPException(404,'产物尚未生成')
        return FileResponse(path,filename=filename,media_type='application/octet-stream')
    @api.get('/{ident}')
    def status(ident:str):return get(ident)
    @api.post('/{ident}/retry')
    def retry(ident:str):
        admit();job=get(ident)
        if job['arguments']['plan']['kind'] not in allowed:raise HTTPException(400,'此版本不支持此平台链接')
        with LOCK:
            if job['status'] in {'queued','running'}:return job
            if job['status']=='completed':return job
            task=store.get(job['task_id'])
            if not task:raise HTTPException(404,'原任务不存在')
            other=documents.generation_get(task.get('link_job_id',''))
            if other and other['id']!=ident and other['status'] in {'queued','running'}:raise HTTPException(409,'同一文稿已有任务正在处理')
            task['link_job_id']=ident
            if task['status']!='completed':task.update(status='queued',stage='queued')
            store.save(task)
            job.update(status='queued',error=None);documents.generation_save(job);enqueue(job['task_id'])
        return job
    return api
