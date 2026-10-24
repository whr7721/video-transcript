"""Read-only evaluation projections. No imports or writes to application stores."""
import hashlib
import json
from pathlib import Path
import sqlite3

SOURCES=[('data','tasks','52629a7fe41fa4d9'),('data','tasks','36ea6f81362d47ff'),
 ('data','tasks','1a4ce9bc1b5d386f'),('data','tasks','601bf25bf1ac2788'),
 ('data','tasks','888eb3f5f7c9f8ad'),('data','tasks','dcc1120e99471935'),
 ('data','article_items','158ea53511714a2a'),('data','article_items','293354d7072f4a2b'),
 ('runtime/r1/core-data','tasks','8235b98d9f210623'),('runtime/v1-b/core-data','tasks','b33db03eb1b9a504')]
VERSION='k1-projection-v1-500'


def fingerprint(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def load(root):
 documents=[];snapshots=[]
 for profile,table,ident in SOURCES:
  path=(Path(root)/profile/'tasks.sqlite3').resolve()
  connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
  try:
   connection.execute('BEGIN')
   before=connection.execute('SELECT payload FROM '+table+' WHERE id=?',(ident,)).fetchone()
   if not before:raise ValueError('Missing evaluation source '+ident)
   item=json.loads(before[0])
   if table=='tasks':
    blocks=[{'id':'seg-'+str(i),'text':s['text'],**{k:s[k] for k in ('start','end') if k in s}}
            for i,s in enumerate(item.get('result',{}).get('segments',[])) if s.get('text','').strip()]
    if not blocks and item.get('result',{}).get('text','').strip():blocks=[{'id':'seg-0','text':item['result']['text']}]
    kind='transcript';ready=item.get('status')=='completed'
   else:
    blocks=[{'id':b['id'],'text':b['text']} for b in item.get('blocks',[])
            if b.get('type')!='image' and b.get('text','').strip()]
    kind='article';ready=item.get('status')=='ready'
   if not ready:raise ValueError('Source not ready '+ident)
   source_hash=fingerprint(blocks)
   documents.append({'uid':kind+':'+ident,'kind':kind,'item_id':ident,'title':item.get('title',''),
                     'version':'original','source_hash':source_hash,'blocks':blocks})
   after=connection.execute('SELECT payload FROM '+table+' WHERE id=?',(ident,)).fetchone()
   assert before==after
   snapshots.append({'uid':kind+':'+ident,'selected_payload_hash':hashlib.sha256(before[0].encode()).hexdigest(),
                     'source_hash':source_hash,'blocks':len(blocks),'characters':sum(len(b['text']) for b in blocks),
                     'title_characters':len(item.get('title','')),'read_only':True})
  finally:connection.close()
 return documents,snapshots


def passages(documents,limit=500):
 if type(limit) is not int or limit<1:raise ValueError('Invalid passage limit')
 result=[]
 for doc in documents:
  current=[];size=0
  def emit():
   refs=[{k:p[k] for k in ('block_id','start','end')} for p in current]
   result.append({'id':doc['uid']+':'+fingerprint(refs)[:20],'source_uid':doc['uid'],'kind':doc['kind'],
                  'source_hash':doc['source_hash'],'version':doc['version'],'title':doc['title'],
                  'text':'\n\n'.join(p['text'] for p in current),'ranges':refs})
  for block in doc['blocks']:
   for offset in range(0,len(block['text']),limit):
    text=block['text'][offset:offset+limit]
    if current and size+len(text)>limit:emit();current=[];size=0
    current.append({'block_id':block['id'],'start':offset,'end':offset+len(text),'text':text});size+=len(text)
  if current:emit()
 return result


def resolve(documents,passage):
 doc=next((d for d in documents if d['uid']==passage['source_uid']),None)
 if not doc or doc['source_hash']!=passage['source_hash']:raise ValueError('Stale source reference')
 blocks={b['id']:b['text'] for b in doc['blocks']};values=[]
 for r in passage['ranges']:
  if r['block_id'] not in blocks or not 0<=r['start']<r['end']<=len(blocks[r['block_id']]):raise ValueError('Invalid range')
  values.append(blocks[r['block_id']][r['start']:r['end']])
 return '\n\n'.join(values)
