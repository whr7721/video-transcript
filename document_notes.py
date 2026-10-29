"""Private anchored notes and explicit local/Notion document exports."""
import hashlib,json,re,string,time,uuid
from datetime import datetime
from pathlib import Path
import httpx
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
import documents,library,settings,store
from document_chat import task

router=APIRouter(prefix='/api/document-notes')
def init(db):
 db.execute('CREATE TABLE IF NOT EXISTS document_notes(task_id TEXT NOT NULL,id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL)')
 db.execute('CREATE TABLE IF NOT EXISTS document_exports(task_id TEXT NOT NULL,target TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(task_id,target))')
def notes(ident):
 with store.connect() as db:init(db);return [json.loads(r[0]) for r in db.execute('SELECT payload FROM document_notes WHERE task_id=? ORDER BY rowid',(ident,))]
def options():
 v=settings.read();return {'vaultPath':v.get('vaultPath',''),'filenameTemplate':v.get('filenameTemplate','{title}-{id}.md'),'notionParentId':v.get('notionParentId',''),'notionConfigured':bool(v.get('encrypted_notion_token'))}
class Options(BaseModel):
 vaultPath:str=Field('',max_length=2000)
 filenameTemplate:str=Field('{title}-{id}.md',min_length=1,max_length=200)
 notionParentId:str=Field('',max_length=40)
 notionToken:str|None=Field(None,max_length=1000)
def filename(template,metadata):
 try:
  for _,key,spec,conversion in string.Formatter().parse(template):
   if key is not None and (key not in {'title','id','date','platform'} or spec or conversion):raise ValueError()
  result=template.format_map(metadata)
 except (ValueError,KeyError):raise HTTPException(400,'文件名模板仅支持 {title}/{id}/{date}/{platform}，不支持格式表达式')
 result=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',result).strip(' .')[:180]
 if not result or result.upper().split('.')[0] in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise HTTPException(400,'文件名无效')
 return result if result.lower().endswith('.md') else result+'.md'
@router.get('/settings')
def get_settings():return options()
@router.put('/settings')
def put_settings(body:Options):
 filename(body.filenameTemplate,dict(title='test',id='a'*16,date='2026-10-29',platform='local'))
 if body.vaultPath and not Path(body.vaultPath).is_absolute():raise HTTPException(400,'vaultPath 必须是绝对目录')
 if body.notionParentId and not re.fullmatch('[a-fA-F0-9-]{32,36}',body.notionParentId):raise HTTPException(400,'Notion父页面请填写32位ID或UUID')
 with settings.SAVE_LOCK:
  v=settings.read();v.update(vaultPath=body.vaultPath,filenameTemplate=body.filenameTemplate,notionParentId=body.notionParentId)
  if body.notionToken is not None:v['encrypted_notion_token']=settings.protect(body.notionToken) if body.notionToken else ''
  store.atomic_json(settings.FILE,v)
 return options()
class Note(BaseModel):
 text:str=Field(min_length=1,max_length=10000)
 block_id:str|None=None
 revision:int=Field(0,ge=0)
def anchor(t,body):
 if not body.text.strip():raise HTTPException(400,'笔记不能为空')
 s=next((b for b in library.sources(t) if b['id']==body.block_id),None) if body.block_id else None
 if body.block_id and not s:raise HTTPException(400,'锚定段落不存在')
 return {'block_id':body.block_id,'timestamp':s.get('start') if s else None,'source_quote':s['text'][:120] if s else ''}
@router.get('/{ident}')
def listing(ident:str):t=task(ident);return {'notes':notes(ident),'anchors':[{'id':b['id'],'text':b['text'][:100],'start':b.get('start')} for b in library.sources(t)],'options':options()}
@router.post('/{ident}')
def create(ident:str,body:Note):
 t=task(ident);n={'id':uuid.uuid4().hex[:16],'text':body.text.strip(),**anchor(t,body),'revision':1,'created_at':time.time(),'updated_at':time.time()}
 with store.connect() as db:init(db);db.execute('INSERT INTO document_notes VALUES (?,?,?,?)',(ident,n['id'],1,json.dumps(n,ensure_ascii=False)))
 return n
@router.put('/{ident}/{note_id}')
def edit(ident:str,note_id:str,body:Note):
 t=task(ident);a=anchor(t,body)
 with store.connect() as db:
  init(db);db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT payload,revision FROM document_notes WHERE task_id=? AND id=?',(ident,note_id)).fetchone()
  if not old:raise HTTPException(404,'笔记不存在')
  if old['revision']!=body.revision:raise HTTPException(409,'笔记已有更新，请刷新后再编辑')
  n={**json.loads(old['payload']),'text':body.text.strip(),**a,'revision':body.revision+1,'updated_at':time.time()};db.execute('UPDATE document_notes SET revision=?,payload=? WHERE id=?',(n['revision'],json.dumps(n,ensure_ascii=False),note_id))
 return n
@router.delete('/{ident}/{note_id}')
def remove(ident:str,note_id:str,revision:int):
 task(ident)
 with store.connect() as db:
  init(db);r=db.execute('DELETE FROM document_notes WHERE task_id=? AND id=? AND revision=?',(ident,note_id,revision))
  if not r.rowcount:raise HTTPException(409,'笔记已更新或不存在，请刷新')
 return {'ok':True}
def bundle(ident):
 t=task(ident);doc=documents.get(t);record=library.require('audio:'+ident)
 summary='\n\n'.join(b['text'] for b in record['blocks'] if b['id']=='summary')
 return {'title':t.get('title') or '未命名文稿','source':t.get('url') or (t.get('source') or {}).get('url',''),'platform':record['platform'],'created_at':t.get('created_at',0),'transcript':documents.text(doc['content']),'sources':library.sources(t),'summary':summary,'notes':notes(ident),'generations':doc['generations']}
def markdown(b):
 lines=['# '+b['title'],'','来源：'+b['source'],'平台：'+b['platform'],'','## 文稿','',b['transcript'],'','## 摘要','',b['summary'] or '尚未生成摘要','','## 笔记']
 for n in b['notes']:lines+=['',f"### {n['block_id'] or '整篇'}"+(f" · {n['timestamp']}s" if n['timestamp'] is not None else ''),n['text']]
 return '\n'.join(lines)+'\n'
def export_get(ident,target):
 with store.connect() as db:init(db);r=db.execute('SELECT payload FROM document_exports WHERE task_id=? AND target=?',(ident,target)).fetchone()
 return json.loads(r[0]) if r else None
def export_save(ident,target,v):
 with store.connect() as db:init(db);db.execute('INSERT OR REPLACE INTO document_exports VALUES (?,?,?)',(ident,target,json.dumps(v,ensure_ascii=False)))
@router.post('/{ident}/export/obsidian')
def obsidian(ident:str):
 b=bundle(ident);o=options();vault=Path(o['vaultPath']).resolve() if o['vaultPath'] else None
 if not vault or not vault.is_dir():raise HTTPException(400,'请先设置已存在的 Obsidian vault 目录')
 name=filename(o['filenameTemplate'],dict(title=b['title'],id=ident,date=datetime.fromtimestamp(b['created_at']).strftime('%Y-%m-%d'),platform=b['platform']));target=(vault/name).resolve()
 if target.parent!=vault:raise HTTPException(400,'导出文件必须位于 vault 内')
 old=export_get(ident,str(target))
 if target.exists() and (not old or hashlib.sha256(target.read_bytes()).hexdigest()!=old.get('hash')):raise HTTPException(409,'目标文件已有外部内容或被手动编辑；请换文件名模板，未覆盖笔记')
 content=markdown(b).encode('utf8')
 # Atomic replace only a previously exported unchanged file; first creation is exclusive.
 if not target.exists():
  with target.open('xb') as f:f.write(content)
 else:
  tmp=target.with_name(target.name+'.shiwen.tmp');tmp.write_bytes(content);tmp.replace(target)
 export_save(ident,str(target),{'hash':hashlib.sha256(content).hexdigest()});return {'path':str(target)}
def notion_request(method,path,token,payload):
 try:
  with httpx.Client(trust_env=False,timeout=40) as c:r=c.request(method,'https://api.notion.com/v1/'+path,headers={'Authorization':'Bearer '+token,'Notion-Version':'2022-06-28','Content-Type':'application/json'},json=payload)
 except httpx.HTTPError:raise HTTPException(502,'Notion请求中断，远端可能已经写入；请核对页面后再操作') from None
 if r.status_code>=400:raise HTTPException(502,f'Notion返回HTTP {r.status_code}，请检查父页面共享权限与integration token')
 return r.json()
@router.post('/{ident}/export/notion')
def notion(ident:str):
 b=bundle(ident);v=settings.read();encrypted=v.get('encrypted_notion_token');parent=v.get('notionParentId')
 if not encrypted or not parent:raise HTTPException(400,'请先配置Notion integration token和父页面ID，并将父页面连接给integration')
 raw=markdown(b);key='notion:'+hashlib.sha256((parent+raw).encode()).hexdigest();old=export_get(ident,key)
 if old:return old
 token=settings.protect(encrypted,decrypt=True)
 children=[{'object':'block','type':'paragraph','paragraph':{'rich_text':[{'type':'text','text':{'content':raw[i:i+1800]}}]}} for i in range(0,len(raw),1800)]
 page=notion_request('POST','pages',token,{'parent':{'page_id':parent},'properties':{'title':{'type':'title','title':[{'type':'text','text':{'content':b['title'][:2000]}}]}},'children':children[:100]})
 result={'page_id':page['id'],'url':page.get('url'),'status':'partial','written':min(100,len(children))};export_save(ident,key,result)
 try:
  for i in range(100,len(children),100):
   notion_request('PATCH','blocks/'+page['id']+'/children',token,{'children':children[i:i+100]});result['written']=i+len(children[i:i+100]);export_save(ident,key,result)
 except HTTPException:
  raise HTTPException(502,'Notion页面已部分创建；请打开页面核对，未自动重复创建。页面ID：'+page['id']) from None
 result['status']='completed';export_save(ident,key,result);return result
