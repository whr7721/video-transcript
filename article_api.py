from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field
import articles
import documents
import store

router=APIRouter(prefix='/api/library')

class ImportInput(BaseModel):
    kind:Literal['url','text','html']
    content:str=Field(min_length=1,max_length=1_000_000)
    title:str=Field(default='',max_length=300)
    source_url:str=Field(default='',max_length=3000)

class NoteInput(BaseModel):
    revision:int=Field(ge=0)
    text:str=Field(max_length=40000)

class QuestionInput(BaseModel):
    question:str=Field(min_length=2,max_length=1000)

@router.get('/items')
def listing():
    return [{k:v for k,v in i.items() if k not in {'blocks','artifacts','note','fingerprint'}} for i in articles.listing()]

@router.post('/items')
def create(body:ImportInput):
    try:return articles.start(body.kind,body.content,body.title,body.source_url)
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get('/items/{ident}')
def get(ident:str):
    item=articles.get(ident)
    if not item:raise HTTPException(404,'素材不存在。')
    return item

@router.put('/items/{ident}/note')
def note(ident:str,body:NoteInput):
    try:return articles.note(ident,body.revision,body.text)
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post('/items/{ident}/question')
def question(ident:str,body:QuestionInput):
    try:return articles.ask(ident,body.question.strip())
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get('/items/{ident}/export')
def export(ident:str):
    try:return Response(articles.export(ident),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="article.md"'})
    except ValueError as exc:raise HTTPException(404,str(exc))

@router.get('/items/{ident}/assets/{name}')
def asset(ident:str,name:str):
    item=get(ident)
    allowed={b.get('asset_name') for b in item['blocks'] if b.get('asset_status')=='saved'}
    if name not in allowed or Path(name).name!=name:raise HTTPException(404,'图片不存在。')
    path=store.DATA/'articles'/ident/name
    if not path.is_file():raise HTTPException(404,'图片文件不可用。')
    return FileResponse(path,headers={'X-Content-Type-Options':'nosniff'})
