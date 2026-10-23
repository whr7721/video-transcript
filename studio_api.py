import json
import re
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import documents
import media_buffer
import organizer
import store

router = APIRouter(prefix='/api/studio')
on_finalize = None


def task(ident):
    if not re.fullmatch('[a-f0-9]{16}',ident): raise HTTPException(404,'文稿不存在')
    value=store.get(ident)
    if not value or value.get('kind')=='creator' or value['status']!='completed': raise HTTPException(404,'完整文稿尚未生成')
    return value


class Draft(BaseModel):
    revision: int = Field(ge=1)
    content: dict
    finalize: bool = False


class Generate(BaseModel):
    revision: int = Field(ge=1)
    action: Literal['paragraphs','summary','quotes','manuscript']


class Pin(BaseModel):
    value: bool


@router.get('/buffer')
def buffer_status():
    return media_buffer.public()


@router.post('/buffer/cleanup')
def cleanup():
    return {'removed_bytes':media_buffer.cleanup(),**media_buffer.public()}


@router.get('/documents/{ident}')
def get_document(ident:str):
    value=task(ident)
    record=next((r for r in media_buffer.inventory() if r['id']==ident),None)
    with store.connect() as db:
        associations=[json.loads(r[0]) for r in db.execute('SELECT payload FROM source_associations WHERE task_id=?',(ident,))] if db.execute("SELECT 1 FROM sqlite_master WHERE name='source_associations'").fetchone() else []
    return {**documents.get(value),'source':value.get('source',{}),'source_associations':associations,
            'timing_precision':value.get('result',{}).get('timing_precision','vad_segments'),
            'audio_available':(store.DATA/'jobs'/ident/'audio.wav').is_file(),
            'video_available':(store.DATA/'jobs'/ident/'original.mp4').is_file(),
            'media_pinned':bool(record and record['pinned']), 'model':organizer.MODEL,
            'generation_capabilities':organizer.capabilities(value)}


@router.get('/documents/{ident}/media-status')
def media_status(ident:str):
    task(ident)
    return {'audio_available':(store.DATA/'jobs'/ident/'audio.wav').is_file()}


@router.post('/documents/{ident}/pin')
def pin(ident:str,body:Pin):
    task(ident)
    media_buffer.pin(ident,body.value)
    return {'media_pinned':body.value}


@router.put('/documents/{ident}')
def save_document(ident:str,body:Draft):
    try:
        result=documents.save(task(ident),body.revision,body.content,body.finalize)
        if body.finalize and on_finalize:
            try: on_finalize()
            except media_buffer.BufferFull: pass
        return result
    except documents.Conflict as exc: raise HTTPException(409,str(exc))
    except ValueError as exc: raise HTTPException(400,str(exc))


@router.post('/documents/{ident}/editing')
def editing(ident:str):
    task(ident)
    media_buffer.state(ident,'awaiting_review')
    media_buffer.touch(ident)
    return {'status':'protected'}


@router.get('/documents/{ident}/versions/{revision}')
def version(ident:str,revision:int):
    task(ident)
    with store.connect() as db:
        documents.init(db)
        row=db.execute('SELECT content FROM document_versions WHERE id=? AND revision=?',(ident,revision)).fetchone()
    if not row: raise HTTPException(404,'版本不存在')
    return {'content':json.loads(row[0]),'revision':revision}


@router.get('/documents/{ident}/export/{kind}')
def export(ident:str,kind:str):
    value=task(ident);doc=documents.get(value)
    if kind not in {'json','txt'}: raise HTTPException(404,'不支持的格式')
    payload=json.dumps({**doc,'title':value.get('title',''),'source':value.get('source',{}),
                        'source_associations':get_document(ident)['source_associations']},ensure_ascii=False,indent=2) if kind=='json' else documents.text(doc['content'])
    return Response(payload,media_type='application/json' if kind=='json' else 'text/plain; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="shiwen-draft-{ident}.{kind}"'})


@router.get('/documents/{ident}/audio')
def audio(ident:str):
    task(ident)
    path=store.DATA/'jobs'/ident/'audio.wav'
    if not path.is_file(): raise HTTPException(404,'该历史任务的音频已被旧规则清理，当前无法回听。原稿仍可使用。')
    media_buffer.touch(ident)
    return FileResponse(path,media_type='audio/wav')


@router.post('/documents/{ident}/generate')
def generate(ident:str,body:Generate):
    try: return organizer.start(task(ident),body.action,body.revision)
    except documents.Conflict as exc: raise HTTPException(409,str(exc))
    except ValueError as exc: raise HTTPException(400,str(exc))


@router.get('/generations/{ident}')
def generation(ident:str):
    value=documents.generation_get(ident)
    if not value: raise HTTPException(404,'整理任务不存在')
    return value

# Chapter navigation is a derived view; these routes never write document drafts.
class ChapterSave(BaseModel):
    revision: int = Field(ge=0)
    plan: dict


@router.get('/documents/{ident}/chapters')
def get_chapters(ident: str):
    import chapters
    try:
        return chapters.get(task(ident))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post('/documents/{ident}/chapters')
def save_chapters(ident: str, body: ChapterSave):
    import chapters
    try:
        clean = {k: body.plan[k] for k in ('source_hash', 'fragment_limit', 'sections') if k in body.plan}
        clean['origin'] = 'manual'
        return chapters.save(task(ident), clean, body.revision)
    except chapters.Conflict as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get('/documents/{ident}/chapters/{index}/text')
def chapter_text(ident: str, index: int):
    import chapters
    value = task(ident)
    try:
        return chapters.resolve(chapters.snapshot(value), chapters.get(value), index)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post('/documents/{ident}/official-chapters')
def official_chapters(ident: str, body: ChapterSave):
    import chapters
    import article_fetch
    import httpx
    value = task(ident)
    url = value.get('source', {}).get('chapters_url')
    if not url:
        raise HTTPException(400, '该来源没有保存官方章节地址；旧任务不会自动联网补充')
    try:
        data, _, _ = article_fetch.fetch(url, limit=1_000_000)
        plan = chapters.official_plan(chapters.snapshot(value), data, value.get('duration'))
        return chapters.save(value, plan, body.revision)
    except chapters.Conflict as exc:
        raise HTTPException(409, str(exc))
    except (ValueError, OSError, httpx.HTTPError) as exc:
        raise HTTPException(400, str(exc))
