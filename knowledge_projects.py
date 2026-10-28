"""Explicit personal projects: goal -> research -> adopted plan -> progress -> review."""
import json
import time
import uuid
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import store
import personal_kb as kb

router=APIRouter(prefix='/api/knowledge/projects')
def init(db):db.execute('CREATE TABLE IF NOT EXISTS kb_projects(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
def get(ident):
    with store.connect() as db:init(db);row=db.execute('SELECT payload FROM kb_projects WHERE id=?',(ident,)).fetchone()
    if not row:raise HTTPException(404,'工作区不存在。')
    return json.loads(row[0])
def modify(ident,revision,change):
    with store.connect() as db:
        init(db);db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT payload FROM kb_projects WHERE id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'工作区不存在。')
        p=json.loads(row[0])
        if p['revision']!=revision:raise HTTPException(409,'工作区已有更新，请重新打开后修改，避免覆盖另一个页面。')
        change(p);p.update(revision=revision+1,updated_at=time.time());db.execute('UPDATE kb_projects SET payload=? WHERE id=?',(json.dumps(p,ensure_ascii=False),ident))
    return p
class New(BaseModel):
    title:str=Field(min_length=1,max_length=100)
    goal:str=Field(min_length=2,max_length=1200)
    constraints:str=Field(default='',max_length=1200)
class Step(BaseModel):
    id:str=Field(max_length=64)
    title:str=Field(min_length=1,max_length=200)
    detail:str=Field(default='',max_length=2400)
    state:Literal['todo','doing','done']='todo'
    note:str=Field(default='',max_length=2000)
class Edit(BaseModel):
    revision:int=Field(ge=1)
    goal:str=Field(min_length=2,max_length=1200)
    constraints:str=Field(default='',max_length=1200)
    steps:list[Step]=Field(max_length=20)
    review:str=Field(default='',max_length=6000)
class Adopt(BaseModel):
    revision:int=Field(ge=1)
    job_id:str=Field(min_length=1,max_length=64)

@router.get('')
def listing():
    kb.private()
    with store.connect() as db:init(db);return [json.loads(r[0]) for r in db.execute('SELECT payload FROM kb_projects ORDER BY rowid DESC LIMIT 100')]
@router.post('')
def create(body:New):
    kb.private()
    if not body.title.strip() or not body.goal.strip():raise HTTPException(400,'请填写标题和目标。')
    p={'id':uuid.uuid4().hex,'title':body.title.strip(),'goal':body.goal,'constraints':body.constraints,'steps':[],'review':'','revision':1,'versions':[],'created_at':time.time()}
    with store.connect() as db:init(db);db.execute('INSERT INTO kb_projects VALUES (?,?)',(p['id'],json.dumps(p,ensure_ascii=False)))
    return p
@router.put('/{ident}')
def edit(ident:str,body:Edit):
    kb.private()
    if len({s.id for s in body.steps})!=len(body.steps):raise HTTPException(400,'步骤标识重复。')
    def change(p):
        citations={s['id']:s.get('citations',[]) for s in p['steps']}
        p.update(goal=body.goal,constraints=body.constraints,steps=[{**s.model_dump(),'citations':citations.get(s.id,[])} for s in body.steps],review=body.review)
    return modify(ident,body.revision,change)
@router.post('/{ident}/research')
def research(ident:str):
    kb.private();p=get(ident)
    progress='；'.join(s['title']+'：'+s['state']+' '+s['note'] for s in p['steps'])
    question='为我的目标制定有依据的步骤，说明资料缺口。目标：'+p['goal']+'。约束：'+p['constraints']+'。进度：'+progress+'。我的复盘：'+p['review']
    if len(question)>4000:raise HTTPException(400,'目标、约束与进度合计超过4000字，请精简后再研究；未截断提交。')
    return kb.ask(kb.Ask(question=question,mode='brief'))
@router.post('/{ident}/adopt')
def adopt(ident:str,body:Adopt):
    kb.private();job=kb.read(body.job_id)
    if job['status']!='completed' or not job.get('result',{}).get('sections'):raise HTTPException(400,'研究未完成或没有有据段落，不能采用。')
    if job.get('stale'):raise HTTPException(409,'资料库已变化，请重新研究后采用。')
    def change(p):
        p['versions'].append({'steps':p['steps'],'review':p['review'],'revision':p['revision'],'saved_at':time.time()})
        p['steps']=[{'id':uuid.uuid4().hex,'title':s['heading'] or '核对并落实此项','detail':s['text'],'state':'todo','note':'','citations':s['citations']} for s in job['result']['sections']]
        p['research_id']=body.job_id;p['gaps']=job['result']['gaps']
    return modify(ident,body.revision,change)
