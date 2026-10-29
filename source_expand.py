import json,time,uuid
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import store,source_enumeration as sources,link_batches
router=APIRouter(prefix='/api/source-expand')
class Input(BaseModel):
 rows:list[str]=Field(min_length=1,max_length=50)
 limit:int=20
 confirm_topics:bool=False
class Selection(BaseModel):
 keys:list[str]=Field(min_length=1,max_length=50)
 language:link_batches.Preview.model_fields['language'].annotation='auto'
 summarize:bool=False

def init():
 with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS source_previews(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
@router.post('/preview')
def preview(body:Input):
 link_batches.admit();init()
 if body.limit not in {10,20,50}:raise HTTPException(400,'请选择10/20/50条')
 topics=[r for r in body.rows if '://' not in r]
 if topics and not body.confirm_topics:return {'confirmation_required':True,'topics':topics}
 groups=[]
 for index,text in enumerate(body.rows):
  group={'input':text,'items':[]}
  try:
   kind,url=sources.identify(text)
   if kind=='single':result={'identity':url,'title':'单条链接','items':[{'id':url,'title':url,'url':url}],'status':'ok'}
   else:result=sources.enumerate_source(kind,url,body.limit)
   group.update(title=result['title'],status=result.get('status'),message=result.get('message'),platform=kind,raw_count=result.get('raw_count'),excluded_nonvideo=result.get('excluded_nonvideo',0))
   group['items']=[{**r,'key':f'{index}:{r["id"]}'} for r in result['items']]
  except Exception as e:group.update(status='error',message=str(e) if isinstance(e,ValueError) else '展开失败，请检查网络/登录后重试')
  groups.append(group)
 value={'id':uuid.uuid4().hex[:16],'created_at':time.time(),'groups':groups}
 with store.connect() as db:db.execute('INSERT INTO source_previews VALUES (?,?)',(value['id'],json.dumps(value,ensure_ascii=False)))
 return value
@router.post('/{ident}/batch')
def select(ident:str,body:Selection):
 link_batches.admit();init()
 with store.connect() as db:r=db.execute('SELECT payload FROM source_previews WHERE id=?',(ident,)).fetchone()
 if not r:raise HTTPException(404,'展开清单不存在，请重新预览')
 value=json.loads(r[0]);mapping={i['key']:i for g in value['groups'] for i in g['items']};keys=list(dict.fromkeys(body.keys))
 if any(k not in mapping for k in keys):raise HTTPException(400,'选择不属于该清单')
 return link_batches.preview(link_batches.Preview(language=body.language,rows=[link_batches.Row(text=mapping[k]['url'],episode_id=mapping[k].get('episode_id'),episode_guid=mapping[k].get('episode_guid'),summarize=body.summarize) for k in keys]))
