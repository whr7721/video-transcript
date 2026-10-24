"""Offline pinned ONNX cross-encoder; long pairs use auditable overlapping windows."""
import hashlib,json,math,time
from pathlib import Path


class Semantic:
 def __init__(self,model_dir,manifest,threads=4):
  import onnxruntime as ort
  from tokenizers import Tokenizer
  ort.disable_telemetry_events()
  self.np=__import__('numpy');root=Path(model_dir);self.manifest=manifest
  for name,info in manifest['artifacts'].items():
   path=root/name
   if not path.is_file() or path.stat().st_size!=info['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:
    raise ValueError('Pinned artifact mismatch: '+name)
  started=time.perf_counter();self.tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'))
  self.tokenizer.no_padding();self.tokenizer.no_truncation()
  self.pad_id=self.tokenizer.token_to_id('<pad>')
  if self.pad_id is None:raise ValueError('Pinned tokenizer has no padding token')
  options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
  self.session=ort.InferenceSession(str(root/'model_quint8_avx2.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
  self.load_seconds=time.perf_counter()-started;self.ort_version=ort.__version__
  self.inputs=[i.name for i in self.session.get_inputs()]

 def encodings(self,query,text):
  self.tokenizer.no_truncation();full=self.tokenizer.encode(query,text)
  if len(self.tokenizer.encode(query).ids)+4>=512:raise ValueError('Query exceeds pair budget; not truncated')
  expected={offset for sequence,offset in zip(full.sequence_ids,full.offsets) if sequence==1}
  self.tokenizer.enable_truncation(max_length=512,strategy='only_second',stride=64)
  encoded=self.tokenizer.encode(query,text);windows=[encoded,*encoded.overflowing]
  covered={offset for w in windows for sequence,offset in zip(w.sequence_ids,w.offsets) if sequence==1}
  if expected-covered:raise ValueError('Pair windows do not cover every document token')
  return windows

 def rank(self,query,pool):
  started=time.perf_counter();windows=[];owners=[]
  for i,p in enumerate(pool):
   encoded=self.encodings(query,p['text']);windows.extend(encoded);owners.extend([i]*len(encoded))
  scores=[-math.inf]*len(pool)
  for start in range(0,len(windows),4):
   batch=windows[start:start+4];width=max(len(e.ids) for e in batch)
   values={'input_ids':self.np.array([e.ids+[self.pad_id]*(width-len(e.ids)) for e in batch],dtype=self.np.int64),
           'attention_mask':self.np.array([e.attention_mask+[0]*(width-len(e.ids)) for e in batch],dtype=self.np.int64)}
   if 'token_type_ids' in self.inputs:values['token_type_ids']=self.np.array([e.type_ids+[0]*(width-len(e.ids)) for e in batch],dtype=self.np.int64)
   output=self.session.run(None,{k:values[k] for k in self.inputs})[0].reshape(-1)
   if len(output)!=len(batch) or not self.np.isfinite(output).all():raise ValueError('Invalid semantic scores')
   for j,value in enumerate(output):scores[owners[start+j]]=max(scores[owners[start+j]],float(value))
  ranked=sorted([{**p,'semantic_score':score} for p,score in zip(pool,scores)],key=lambda p:(-p['semantic_score'],p['id']))
  return ranked,{'seconds':time.perf_counter()-started,'pairs':len(pool),'scored_windows':len(windows),
                 'extra_windows':len(windows)-len(pool),'cache_used':False}
