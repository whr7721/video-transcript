from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field
import articles
import documents
import store

router=APIRouter(prefix='/api/library')


@router.get('/ocr-evaluation')
def ocr_evaluation_report():
    import ocr_evaluation
    return ocr_evaluation.report()


class HumanLabel(BaseModel):
    item_id:str=Field(max_length=64)
    region_id:str=Field(max_length=100)
    source_key:str=Field(pattern=r'^[a-f0-9]{64}$')
    category:Literal['body','watermark','furniture','interface','unknown']
    revision:int=Field(ge=0)


@router.put('/ocr-evaluation/labels')
def human_label(body:HumanLabel):
    import ocr_evaluation
    try:return ocr_evaluation.label(**body.model_dump())
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))


class ReadingEdit(BaseModel):
    source_key:str=Field(pattern=r'^[a-f0-9]{64}$')
    revision:int=Field(ge=0)
    category:Literal['body','watermark','furniture','interface','unknown']|None=None
    state:Literal['keep','exclude','fold']|None=None


@router.put('/image-items/{ident}/selection/{block_id}')
def reading_override(ident:str,block_id:str,body:ReadingEdit):
    import ocr_reading
    try:return ocr_reading.override(ident,block_id,**body.model_dump())
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.post('/image-items/{ident}/classify')
def classify_regions(ident:str):
    import ocr_classification
    try:return ocr_classification.start(ident)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.get('/ocr-classification-budget')
def classification_budget():
    import ocr_classification
    return ocr_classification.budget()


class ImageCreate(BaseModel):
    title:str=Field(default='',max_length=300)
    count:int=Field(ge=1,le=64)


@router.post('/image-items')
def create_images(body:ImageCreate):
    import image_documents
    try:return image_documents.create(body.title,body.count)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.put('/image-items/{ident}/{index}')
async def upload_image(ident:str,index:int,request:Request):
    import image_documents
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>image_documents.MAX_IMAGE_BYTES:raise HTTPException(413,'图片超过8MB上限')
        data.extend(chunk)
    try:return image_documents.put_image(ident,index,bytes(data))
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.post('/image-items/{ident}/recognize')
def recognize_images(ident:str):
    import image_documents
    try:return image_documents.start_ocr(ident)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.post('/image-items/{ident}/stop-upload')
def stop_image_upload(ident:str):
    import image_documents
    with articles.LOCK:
        item=articles.get(ident)
        if not item or item.get('image_status')!='uploading':raise HTTPException(409,'当前没有待结束的上传')
        return image_documents.update(ident,status='ready',image_status='failed',completeness='partial',error='上传已结束；已保存图片保留，未上传页仍标记缺失。')


class RegionEdit(BaseModel):
    revision:int=Field(ge=1)
    text:str=Field(max_length=4000)


@router.put('/image-items/{ident}/regions/{block_id}')
def correct_region(ident:str,block_id:str,body:RegionEdit):
    import image_documents
    import ocr_reading
    try:return ocr_reading.view(image_documents.correct(ident,block_id,body.revision,body.text))
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))

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
    image_page:int|None=Field(default=None,ge=1,le=64)

@router.get('/items')
def listing():
    return [{k:v for k,v in i.items() if k not in {'blocks','artifacts','note','fingerprint','reading_selection'}} for i in articles.listing()]

@router.post('/items')
def create(body:ImportInput):
    try:return articles.start(body.kind,body.content,body.title,body.source_url)
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get('/items/{ident}')
def get(ident:str):
    item=articles.get(ident)
    if not item:raise HTTPException(404,'素材不存在。')
    import ocr_reading
    return ocr_reading.view(item)

@router.put('/items/{ident}/note')
def note(ident:str,body:NoteInput):
    import ocr_reading
    try:return ocr_reading.view(articles.note(ident,body.revision,body.text))
    except documents.Conflict as exc:raise HTTPException(409,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post('/items/{ident}/question')
def question(ident:str,body:QuestionInput):
    import ocr_reading
    try:return ocr_reading.view(articles.ask(ident,body.question.strip(),body.image_page))
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get('/items/{ident}/export')
def export(ident:str,reading_mode:Literal['clean','original']='clean'):
    try:return Response(articles.export(ident,reading_mode),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="article.md"'})
    except ValueError as exc:raise HTTPException(404,str(exc))

@router.get('/items/{ident}/assets/{name}')
def asset(ident:str,name:str):
    item=get(ident)
    allowed={b.get('asset_name') for b in item['blocks'] if b.get('asset_status')=='saved'}
    if name not in allowed or Path(name).name!=name:raise HTTPException(404,'图片不存在。')
    path=store.DATA/'articles'/ident/name
    if not path.is_file():raise HTTPException(404,'图片文件不可用。')
    return FileResponse(path,headers={'X-Content-Type-Options':'nosniff'})
