"""Private single-post image acquisition using the existing isolated collector session."""
import json
import os
from pathlib import Path
import re
import subprocess
import threading
from urllib.parse import urljoin
import httpx
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import articles
import job_retry
import article_fetch
import image_documents
from pipeline import input_url,MC_PY
from session import prepare_session
import store

router=APIRouter(prefix='/api/private/image-posts')
LOCK=threading.Lock()


def resolve(share):
    url=input_url(share)
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=15) as client:
        for _ in range(6):
            match=re.search(r'/(?:share/)?(?:note|video)/(\d{15,22})(?:[/?#]|$)|[?&]modal_id=(\d{15,22})',url)
            if match:return next(g for g in match.groups() if g)
            response=client.get(url,headers={'User-Agent':'Mozilla/5.0'})
            if not response.headers.get('location'):break
            url=input_url(urljoin(url,response.headers['location']))
    raise ValueError('无法解析图文作品编号，请提供完整作品链接')


def metadata(post_id):
    directory=store.DATA/'image-sources'/post_id;directory.mkdir(parents=True,exist_ok=True)
    output=directory/'source.json'
    if output.exists():
        old=json.loads(output.read_text(encoding='utf-8'))
        if old.get('status')=='ok' and old.get('id')==post_id:return old
    with LOCK:
        prepare_session()
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(key,None)
        try:
            subprocess.run([str(MC_PY),'-B','-X','utf8',str(store.ROOT/'extractor.py'),'images','--id',post_id,'--output',str(output.resolve())],
                           env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=130,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired:raise ValueError('获取图集超时；请检查独立登录状态后重试') from None
    value=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    if value.get('status')!='ok':raise ValueError(value.get('error') or '采集组件未返回图集；请检查登录状态')
    if value.get('id')!=post_id:raise ValueError('作品编号不匹配，未导入')
    return value


def start(share):
    input_url(share)
    item=image_documents.create('正在获取分享图文',1)
    image_documents.update(item['id'],image_status='fetching',expected_images=None,blocks=[],source_share=share)
    articles.EXECUTOR.submit(run,item['id'],share)
    return articles.get(item['id'])


def run(ident,share):
    try:
        post_id=resolve(share);meta=metadata(post_id)
        count=meta.get('total')
        if type(count) is not int or not 1<=count<=image_documents.MAX_IMAGES or count!=len(meta.get('images',[])):
            raise ValueError('图集页数无效或超过64张，未截断导入')
        item=articles.get(ident)
        if item.get('expected_images') is None:
            caption=meta.get('title','')
            blocks=([{'id':'caption','type':'paragraph','text':caption}] if caption else [])
            blocks += [{'id':f'image-{i+1}','type':'image','text':'','page':i+1,'asset_status':'missing','asset_error':'等待下载','ocr_status':'pending'} for i in range(count)]
            image_documents.update(ident,title=caption.split('\n')[0][:160] or '分享图文',author=meta.get('author',''),expected_images=count,
                                   source_url='https://www.douyin.com/note/'+post_id,private_post_id=post_id,blocks=blocks)
        elif item['expected_images']!=count:raise ValueError('图集页数已变化，原有版本保留，请重新导入')
        image_documents.update(ident,image_status='fetching',status='running',error=None)
        for i,image in enumerate(meta['images']):
            item=articles.get(ident)
            block=next(b for b in item['blocks'] if b.get('page')==i+1)
            if block.get('asset_status')=='saved' and (store.DATA/'articles'/ident/block['asset_name']).is_file():continue
            message='该页没有可用图片地址'
            for url in list(reversed(image.get('urls',[])))[:3]:
                try:
                    data,_,_=article_fetch.fetch(url,limit=image_documents.MAX_IMAGE_BYTES,referer=item['source_url'])
                    image_documents.put_image(ident,i,data);message='';break
                except (ValueError,httpx.HTTPError,OSError) as exc:
                    message=str(exc) if isinstance(exc,ValueError) else '图片下载失败，可重试缺失页'
            if message:
                with articles.LOCK:
                    item=articles.get(ident);block=next(b for b in item['blocks'] if b.get('page')==i+1)
                    block.update(asset_status='missing',asset_error=message);articles.save(item)
        image_documents.run_ocr(ident)
    except Exception as exc:
        image_documents.update(ident,status='ready',image_status='failed',completeness='partial',
                               error=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else '图文获取未完成，请检查登录；未绕过任何验证')


class Share(BaseModel):
    share_text:str=Field(min_length=1,max_length=5000)


@router.post('')
def create(body:Share):
    try:return start(body.share_text)
    except ValueError as exc:raise HTTPException(400,str(exc))


@router.post('/{ident}/retry')
def retry(ident:str):
    item=articles.get(ident)
    if not item or not item.get('source_share'):raise HTTPException(404,'图文采集任务不存在')
    if item.get('image_status') not in {'failed','partial'}:raise HTTPException(409,'当前任务无需重试')
    job_retry.requeue(item,articles.save,lambda: articles.EXECUTOR.submit(run,ident,item['source_share']),image_status='fetching',status='running')
    return articles.get(ident)
