"""Optional isolated CPU OCR worker. Never imports the application or sends images out."""
import argparse
import hashlib
import json
from pathlib import Path
import time

VERSION = 'rapidocr-3.9.2-ppocr6-cpu-v2-tile1800'
MODEL_HASHES = {
    'PP-OCRv6_det_small.onnx':'090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f',
    'PP-OCRv6_rec_small.onnx':'6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884',
    'ch_ppocr_mobile_v2.0_cls_mobile.onnx':'e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c',
}


def write(path, value):
    path=Path(path);temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temporary.replace(path)


def recognize(image, engine):
    import numpy as np
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS=60_000_000
    with Image.open(image) as opened:
        if opened.width*opened.height>60_000_000 or max(opened.size)>20000:
            raise ValueError('图片尺寸超过20000边长或6000万像素限制')
        if getattr(opened,'n_frames',1)>1:
            raise ValueError('本版只识别静态图片，请导出需要的单帧')
        opened.load();picture=ImageOps.exif_transpose(opened).convert('RGB')
    width,height=picture.size;regions=[];tiles=0
    for y in range(0,height,1680):
        bottom=min(height,y+1800)
        result=engine(np.asarray(picture.crop((0,y,width,bottom))))
        tiles+=1
        for box,text,score in zip(result.boxes if result.boxes is not None else [],result.txts or [],result.scores or []):
            if not text.strip():continue
            points=[[round(float(x),1),round(float(yy)+y,1)] for x,yy in box]
            left=min(p[0] for p in points);right=max(p[0] for p in points)
            top=min(p[1] for p in points);end=max(p[1] for p in points)
            # Overlap tiles can contain the same line. Never deduplicate equal text elsewhere.
            def clean(value):return ''.join(value.split()).casefold()
            normalized=clean(text);duplicate=False
            for previous in list(regions[-100:]):
                x1,y1,x2,y2=previous['bbox']
                overlap_y=max(0,min(y2,end)-max(y1,top))/max(1,min(y2-y1,end-top))
                overlap_x=max(0,min(x2,right)-max(x1,left))/max(1,min(x2-x1,right-left))
                original=clean(previous['text'])
                if overlap_y>.65 and overlap_x>.6 and (normalized in original or original in normalized):
                    if len(normalized)<=len(original):duplicate=True;break
                    regions.remove(previous)
            if duplicate:continue
            regions.append({'id':'r'+str(len(regions)+1),'text':text,'score':round(float(score),4),
                            'bbox':[max(0,left),max(0,top),min(width,right),min(height,end)]})
        if bottom==height:break
    regions.sort(key=lambda r:(r['bbox'][1],r['bbox'][0]))
    for i,r in enumerate(regions):r['id']='r'+str(i+1)
    # Spatial text order is not a semantic reconstruction of multi-column diagrams.
    return {'width':width,'height':height,'regions':regions,'tiles':tiles,
            'text':'\n'.join(r['text'] for r in regions),'version':VERSION}


def run(manifest, output):
    import rapidocr
    import onnxruntime
    from rapidocr import RapidOCR
    onnxruntime.disable_telemetry_events()
    models=Path(rapidocr.__file__).parent/'models'
    for name,expected in MODEL_HASHES.items():
        file=models/name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('OCR模型缺失或与固定版本不符；未自动下载替换')
    engine=RapidOCR(params={'Det.model_path':str(models/'PP-OCRv6_det_small.onnx'),
                           'Rec.model_path':str(models/'PP-OCRv6_rec_small.onnx'),
                           'Cls.model_path':str(models/'ch_ppocr_mobile_v2.0_cls_mobile.onnx'),
                           'Global.text_score':0.0,'Global.max_side_len':3000,'Global.log_level':'error',
                           'Det.limit_side_len':1280,'EngineConfig.onnxruntime.intra_op_num_threads':4,
                           'EngineConfig.onnxruntime.inter_op_num_threads':1})
    rows=json.loads(Path(manifest).read_text(encoding='utf-8'));results=[]
    for row in rows:
        started=time.monotonic();path=Path(row['path'])
        cache=path.with_name(path.name+'.'+hashlib.sha256(VERSION.encode()).hexdigest()[:12]+'.ocr.json')
        try:
            fingerprint=hashlib.sha256(path.read_bytes()+VERSION.encode()).hexdigest()
            previous=json.loads(cache.read_text(encoding='utf-8')) if cache.is_file() else None
            if previous and previous.get('fingerprint')==fingerprint:
                result={**previous,'cached':True}
            else:
                result={**recognize(path,engine),'fingerprint':fingerprint,'cached':False}
                write(cache,result)
            results.append({'id':row['id'],'status':'ok',**result,'seconds':round(time.monotonic()-started,3)})
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else '图片解码或识别失败（'+type(exc).__name__+'）'
            results.append({'id':row['id'],'status':'failed','error':message})
        write(output,{'version':VERSION,'pages':results})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    import core_instance
    try:lock=core_instance.acquire(Path(args.output).parent/'.ocr.lock')
    except RuntimeError:raise SystemExit(2)
    try:run(args.input,args.output)
    except Exception as exc:
        write(args.output,{'version':VERSION,'error':str(exc) if isinstance(exc,RuntimeError) else 'OCR组件启动失败（'+type(exc).__name__+'）','pages':[]})
        raise SystemExit(1)
    finally:lock.close()
