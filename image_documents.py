"""Ordered image originals and derived OCR blocks; no platform-specific dependency."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import articles
import documents
import store

MAX_IMAGES=64
MAX_IMAGE_BYTES=8_000_000
MAX_POST_BYTES=64_000_000


def content_hash(blocks):
    fields=('id','type','text','source_image_id','region_id','bbox','revision','asset_name','width','height','ocr_version')
    return hashlib.sha256(json.dumps([{k:b[k] for k in fields if k in b} for b in blocks],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def update(ident, **fields):
    with articles.LOCK:
        item=articles.get(ident)
        if not item:raise ValueError('图文材料不存在')
        item.update(fields);articles.save(item);return item


def create(title, count, source_url='', author='', description=''):
    if type(count) is not int or not 1<=count<=MAX_IMAGES:raise ValueError('本版支持1—64张图片；不会截取后宣布完整')
    with articles.LOCK:
        active=sum(i.get('image_status') in {'uploading','queued','running','fetching'} for i in articles.listing())
        if active>=3:raise ValueError('已有3份图集在处理中，请稍后再导入')
        ident=uuid.uuid4().hex[:16]
        blocks=([{'id':'caption','type':'paragraph','text':description}] if description else [])
        blocks += [{'id':f'image-{i+1}','type':'image','text':'','page':i+1,'asset_status':'missing','asset_error':'等待获取图片','ocr_status':'pending'} for i in range(count)]
        item={'id':ident,'kind':'images','title':title.strip()[:300] or '图片资料','author':author,
              'source_url':source_url,'status':'running','image_status':'uploading','created_at':time.time(),
              'blocks':blocks,'note':'','note_revision':0,'question_status':'idle','artifacts':[],
              'expected_images':count,'ocr_completed':0,'completeness':'partial',
              'warnings':['图片识别尚未完成；原图和识别文字需要对照核实。'],'asset_bytes':0}
        articles.save(item)
        return item


def put_image(ident, index, data):
    with articles.LOCK:
        item=articles.get(ident)
        if not item or item.get('kind')!='images':raise ValueError('图片材料不存在')
        if item.get('image_status') not in {'uploading','fetching','failed'}:raise ValueError('当前图集不接受上传，请新建材料')
        images=[b for b in item['blocks'] if b['type']=='image']
        if not 0<=index<len(images):raise ValueError('图片序号无效')
        ext=articles.image_type(data)
        if not ext or not 0<len(data)<=MAX_IMAGE_BYTES:raise ValueError('仅支持8MB以内的PNG/JPEG/WebP/GIF图片')
        block=images[index]
        amount=sum(b.get('bytes',0) for b in images)-block.get('bytes',0)+len(data)
        if amount>MAX_POST_BYTES:raise ValueError('本图集超过64MB上限，已保存图片保留')
        directory=store.DATA/'articles'/ident;directory.mkdir(parents=True,exist_ok=True)
        name=hashlib.sha256(data).hexdigest()+'.'+ext;path=directory/name
        used=sum(p.stat().st_size for p in (store.DATA/'articles').rglob('*') if p.is_file())
        if not path.exists() and used+len(data)>articles.ASSET_CAPACITY:raise ValueError('图片库已达500MB上限；没有删除已有资料')
        if not path.exists():
            temporary=path.with_suffix('.tmp');temporary.write_bytes(data);temporary.replace(path)
        block.update(asset_status='saved',asset_name=name,bytes=len(data),asset_error=None,ocr_status='pending')
        item['asset_bytes']=amount;articles.save(item);return item


def worker_python():
    explicit=os.environ.get('SHIWEN_OCR_PYTHON')
    candidates=[Path(explicit)] if explicit else [store.ROOT/'.venv-ocr/Scripts/python.exe',store.ROOT/'runtime/image-ocr/venv/Scripts/python.exe',store.ROOT/'.venv-ocr/bin/python']
    for path in candidates:
        if path.is_file():return path
    raise ValueError('可选OCR组件未安装；请按图片识别说明准备组件，原图仍保留')


def start_ocr(ident):
    worker_python()
    with articles.LOCK:
        item=articles.get(ident)
        if not item or item.get('kind')!='images':raise ValueError('图片材料不存在')
        if item.get('image_status') in {'queued','running','fetching'}:raise ValueError('图集仍在处理，请稍后')
        if not any(b.get('asset_status')=='saved' for b in item['blocks'] if b['type']=='image'):raise ValueError('还没有成功保存的图片')
        item.update(image_status='queued',status='running',error=None);articles.save(item)
        articles.EXECUTOR.submit(run_ocr,ident);return item


def commit_pages(ident, result, final=False):
    with articles.LOCK:
        item=articles.get(ident)
        images=[b for b in item['blocks'] if b['type']=='image']
        results={p['id']:p for p in result.get('pages',[])}
        old={b['id']:b for b in item['blocks'] if b.get('source_image_id')}
        for image in images:
            page=results.get(image['id'])
            if page and page.get('status')=='ok' and image.get('ocr_version') not in {None,page['version']} and any(b.get('corrected') and b.get('source_image_id')==image['id'] for b in old.values()):
                raise ValueError('识别版本变化且已有人工校对，请保留当前资料并新建导入；未覆盖校对文字')
        rebuilt=[b for b in item['blocks'] if b['type']!='image' and not b.get('source_image_id')]
        for image in images:
            page=results.get(image['id'])
            if page:
                image['ocr_status']=page['status'];image['ocr_error']=page.get('error')
                if page['status']=='ok':
                    image.update(width=page['width'],height=page['height'],ocr_version=page['version'],ocr_seconds=page['seconds'])
                    # Immutable machine output lives beside the original image cache.
                    image['ocr_original']={r['id']:r for r in page['regions']}
            rebuilt.append(image)
            if image.get('ocr_status')=='ok':
                for region in image.get('ocr_original',{}).values():
                    bid=image['id']+'-'+region['id']
                    rebuilt.append(old[bid] if old.get(bid,{}).get('corrected') else {'id':bid,'type':'ocr','text':region['text'],
                        'source_image_id':image['id'],'region_id':region['id'],'bbox':region['bbox'],
                        'score':region['score'],'revision':1,'corrected':False})
        changed=content_hash(item['blocks'])!=content_hash(rebuilt)
        item['blocks']=rebuilt;item['ocr_completed']=sum(p.get('status')=='ok' and bool(p.get('regions')) for p in results.values())
        if changed or not item.get('content_hash'):item['content_hash']=content_hash(rebuilt)
        if final:
            failed=sum(b.get('ocr_status')!='ok' or not b.get('ocr_original') for b in images)
            item.update(status='ready',image_status='partial' if failed else 'completed',
                        completeness='partial' if failed else 'unverified',finished_at=time.time())
            item['warnings']=['文字由本地OCR识别，可能漏字、错序；图解关系尚未自动理解。']
            if failed:item['warnings'].append(f'{failed}/{len(images)}张图片未完成有效文字识别，保留原位置，可重试。')
        articles.save(item)


def run_ocr(ident):
    proc=None
    try:
        item=update(ident,image_status='running',error=None)
        directory=store.DATA/'articles'/ident
        rows=[{'id':b['id'],'path':str((directory/b['asset_name']).resolve())} for b in item['blocks'] if b['type']=='image' and b.get('asset_status')=='saved']
        work=store.DATA/'image-jobs'/ident;work.mkdir(parents=True,exist_ok=True)
        import core_instance
        try:
            with core_instance.acquire(work/'.ocr.lock'):pass
        except RuntimeError:raise ValueError('同一图集的识别进程仍在运行，请等待结束后重试；没有删除它的进度') from None
        manifest=work/'input.json';output=work/'output.json';output.unlink(missing_ok=True)
        store.atomic_json(manifest,rows)
        env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'}
        proc=subprocess.Popen([str(worker_python()),'-B',str(store.ROOT/'ocr_worker.py'),'--input',str(manifest),'--output',str(output)],
                              env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        started=time.monotonic();count=-1
        while proc.poll() is None:
            if time.monotonic()-started>900:
                proc.terminate();proc.wait(timeout=10);raise ValueError('图片识别超过15分钟，已保留原图和成功缓存，可重试')
            if output.exists():
                value=json.loads(output.read_text(encoding='utf-8'))
                if len(value.get('pages',[]))!=count:commit_pages(ident,value);count=len(value.get('pages',[]))
            time.sleep(.4)
        value=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
        if proc.returncode or value.get('error'):raise ValueError(value.get('error') or 'OCR组件退出，原图和成功缓存保留')
        commit_pages(ident,value,final=True)
    except Exception as exc:
        if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=10)
        update(ident,status='ready',image_status='failed',completeness='partial',error=str(exc) if isinstance(exc,ValueError) else '图片识别未完成，原图保留，可重试')


def correct(ident, block_id, revision, text):
    if not isinstance(text,str) or len(text)>4000:raise ValueError('单个区域文字最多4000字')
    with articles.LOCK:
        item=articles.get(ident)
        if not item or item.get('image_status') in {'queued','running','fetching'}:raise ValueError('请等待识别完成后再校对')
        block=next((b for b in item['blocks'] if b['id']==block_id and b['type']=='ocr'),None)
        if not block:raise ValueError('识别区域不存在')
        if block['revision']!=revision:raise documents.Conflict('这一区域已有更新，请保留输入后刷新')
        block.update(text=text,revision=revision+1,corrected=True)
        item['content_hash']=content_hash(item['blocks'])
        articles.save(item);return item
