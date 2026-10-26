from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
import documents
import research
from studio_api import task

router=APIRouter(prefix='/api/studio/research')


class ResearchInput(BaseModel):
    basis:Literal['original','draft','manuscript','chapter']='original'
    revision:int=Field(default=1,ge=1)
    generation_id:str|None=Field(default=None,max_length=64)
    chapter_revision:int|None=Field(default=None,ge=1)
    chapter_index:int|None=Field(default=None,ge=0,le=499)
    selection_start:int|None=Field(default=None,ge=0,le=200000)
    selection:str=Field(default='',max_length=4000)
    question:str=Field(default='',max_length=600)
    mode:Literal['explain','cases','limits','verify']='explain'
    online:bool=False


class NoteInput(BaseModel):
    job_id:str=Field(max_length=64)
    topic_title:str=Field(min_length=1,max_length=100)
    personal:str=Field(default='',max_length=12000)


class NoteEdit(BaseModel):
    revision:int=Field(ge=1)
    personal:str=Field(max_length=12000)


class ManualNote(ResearchInput):
    topic_title:str=Field(min_length=1,max_length=100)
    personal:str=Field(min_length=1,max_length=12000)


@router.post('/documents/{ident}/manual-note')
def manual_note(ident:str,body:ManualNote):
    try:return research.manual_note(task(ident),body)
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.post('/documents/{ident}')
def start(ident:str,body:ResearchInput):
    try:return research.start(task(ident),body)
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.get('/documents/{ident}')
def jobs(ident:str):
    task(ident)
    return research.listing(ident)


@router.get('/jobs/{ident}')
def get(ident:str):
    job=research.get(ident)
    if not job:raise HTTPException(404,'深入任务不存在。')
    return job


@router.post('/jobs/{ident}/cancel')
def cancel(ident:str):
    job=research.cancel(ident)
    if not job:raise HTTPException(404,'深入任务不存在。')
    return job


class ConfirmClaims(BaseModel):
    claim_ids:list[str]=Field(min_length=1,max_length=3)
    kinds:dict[str,Literal['fact','opinion']]=Field(default_factory=dict,max_length=3)


@router.post('/jobs/{ident}/confirm')
def confirm_claims(ident:str,body:ConfirmClaims):
    import verification
    try:return verification.confirm(ident,body.claim_ids,body.kinds)
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.get('/topics')
def topics():return research.topics()


class MaterialInput(BaseModel):
    item_id:str=Field(min_length=1,max_length=64)
    topic_title:str=Field(min_length=1,max_length=100)


@router.post('/materials')
def add_material(body:MaterialInput):
    try:return research.attach_material(body.item_id,body.topic_title)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.get('/topics/{ident}/search')
def search_topic(ident:str,q:str=Query(min_length=1,max_length=200),
                 category:Literal['all','personal','selection','original']='all',
                 offset:int=Query(default=0,ge=0,le=40),include_hidden:bool=False):
    import sqlite3
    import topic_search
    try:return topic_search.search(ident,q,category,offset,include_hidden=include_hidden)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))
    except sqlite3.Error:raise HTTPException(503,'本地索引暂不可用，请稍后重新搜索；没有返回旧结果。')


class SearchLocation(BaseModel):
    hit_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    source_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    include_hidden:bool=False


@router.post('/topics/{ident}/search/context')
def search_context(ident:str,body:SearchLocation):
    import topic_search
    try:return topic_search.context(ident,body.hit_id,body.source_hash,body.include_hidden)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except documents.Conflict as exc:raise HTTPException(409,str(exc))


@router.get('/notes')
def notes(topic_id:str|None=None):return research.note_list(topic_id)


@router.get('/notes/{ident}')
def get_note(ident:str):
    note=research.get_note(ident)
    if not note:raise HTTPException(404,'笔记不存在。')
    return note


@router.post('/notes')
def save_note(body:NoteInput):
    try:return research.save_note(body.job_id,body.topic_title,body.personal)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.put('/notes/{ident}')
def edit_note(ident:str,body:NoteEdit):
    try:return research.update_note(ident,body.revision,body.personal)
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(404,str(exc))


@router.get('/notes/{ident}/export')
def export(ident:str):
    try:body=research.export_note(ident)
    except ValueError as exc:raise HTTPException(404,str(exc))
    return Response(body,media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="shiwen-topic-note.md"'})
