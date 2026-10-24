"""Fetch only pinned official model artifacts; no user text is transmitted."""
import hashlib,json,urllib.request,time
from pathlib import Path
MODEL='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
REVISION='1427fd652930e4ba29e8149678df786c240d8825'
FILES={'onnx/model_quint8_avx2.onnx':(118620016,'6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b'),
       'tokenizer.json':(17082660,'62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626')}
root=Path('runtime/k1-rerank/model').resolve();root.mkdir(parents=True,exist_ok=True)
for name,(size,digest) in FILES.items():
 target=root/Path(name).name
 if target.exists() and target.stat().st_size==size and hashlib.sha256(target.read_bytes()).hexdigest()==digest:
  print('Verified cached',target.name,flush=True);continue
 temporary=target.with_suffix(target.suffix+'.part');count=0;h=hashlib.sha256();started=time.monotonic()
 try:
  with urllib.request.urlopen(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}',timeout=60) as response,temporary.open('wb') as stream:
   while block:=response.read(1024*1024):
    count+=len(block)
    if count>size:raise ValueError('Model artifact larger than pinned size')
    h.update(block);stream.write(block)
  if count!=size or h.hexdigest()!=digest:raise ValueError('Model artifact checksum mismatch')
  temporary.replace(target);print('Downloaded',target.name,count,'bytes',round(time.monotonic()-started,2),'sec',flush=True)
 except Exception:
  temporary.unlink(missing_ok=True);raise
metadata={'model_id':MODEL,'revision':REVISION,'license':'Apache-2.0','official_url':'https://huggingface.co/'+MODEL,
          'artifacts':{Path(n).name:{'bytes':s,'sha256':d} for n,(s,d) in FILES.items()},'download_sends_user_text':False}
Path('experiments/retrieval_rerank/MODEL_MANIFEST.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
