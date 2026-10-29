"""Private catalog and derived lexical passages, shared with document questions."""
import io,json,re,threading,time,uuid,zipfile
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import Response
from pydantic import BaseModel,Field
import documents,store,topic_search

router=APIRouter(prefix='/api/library');LOCK=threading.RLock()

def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS library_meta(uid TEXT PRIMARY KEY,starred INTEGER NOT NULL DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS library_collections(id TEXT PRIMARY KEY,name TEXT NOT NULL,created REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS library_members(collection_id TEXT NOT NULL,uid TEXT NOT NULL,position INTEGER NOT NULL,PRIMARY KEY(collection_id,uid))')
    db.execute('CREATE TABLE IF NOT EXISTS library_passages(id INTEGER PRIMARY KEY,uid TEXT NOT NULL,payload TEXT NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS library_scope ON library_passages(uid)')
    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(tokens)')
    db.execute('CREATE TABLE IF NOT EXISTS library_state(id INTEGER PRIMARY KEY,fingerprint TEXT NOT NULL)')

def sources(task):
    result=task.get('result') or {}
    blocks=documents.sources(task) if result.get('segments') else []
    if not blocks:
        for n,s in enumerate(result.get('subtitlesArray') or task.get('subtitlesArray') or []):
            if s.get('text','').strip():blocks.append({'id':f'seg-{n}','text':s['text'],'start':s.get('startTime'),'end':s.get('end')})
    if not blocks:
        text=result.get('text') or task.get('transcript') or ''
        if text:blocks=[{'id':'seg-0','text':text}]
    # Some imports have full text beyond their subtitle cues; retain it for search.
    raw=result.get('text') or task.get('transcript') or ''
    if raw and raw.strip()!= '\n'.join(b['text'] for b in blocks).strip():blocks.append({'id':'transcript','text':raw})
    return blocks

def catalog():
    with store.connect() as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def rows(table):return [json.loads(r[0]) for r in db.execute('SELECT payload FROM '+table)] if table in tables else []
        tasks=rows('tasks');articles=rows('article_items');generations=rows('generations')
        drafts={r['id']:documents.text(json.loads(r['content'])) for r in db.execute('SELECT id,content FROM documents')} if 'documents' in tables else {}
        memories=[dict(r) for r in db.execute('SELECT * FROM kb_memories')] if 'kb_memories' in tables else []
        notes=[dict(r) for r in db.execute('SELECT id,personal FROM research_notes')] if 'research_notes' in tables else []
    summaries={}
    for g in generations:
        if g.get('status')!='completed' or g.get('action') not in {'summary','manuscript'}:continue
        parts=[]
        if g.get('content'):parts.append(documents.text(g['content']))
        parts.extend(i.get('text','') for i in g.get('items',[]))
        for key in ('summary','highlights','quotes'):
            parts.extend(i.get('text','') for i in (g.get('bundle') or {}).get(key,[]))
        summaries.setdefault(g.get('task_id'),[]).extend(parts)
    result=[]
    for t in tasks:
        if t.get('kind')=='creator':continue
        tid=t['id'];blocks=sources(t);summary='\n\n'.join(summaries.get(tid,[]))
        directory=store.DATA/'jobs'/tid if re.fullmatch('[a-f0-9]{16}',tid) else None
        if directory and (directory/'summary.md').is_file():summary+='\n'+(directory/'summary.md').read_text(encoding='utf8')
        if summary:blocks.append({'id':'summary','text':summary})
        if drafts.get(tid):blocks.append({'id':'draft','text':drafts[tid]})
        result.append({'uid':'audio:'+tid,'id':tid,'kind':'audio','title':t.get('title') or '未命名文稿','platform':(t.get('source') or {}).get('platform') or (t.get('source') or {}).get('kind') or ('douyin' if t.get('video_id') else 'local_file'),'created_at':t.get('created_at',0),'duration':t.get('duration') or (t.get('result') or {}).get('duration') or 0,'status':t.get('status','unknown'),'url':'/studio/?task='+tid,'blocks':blocks})
    for a in articles:
        if a.get('kind')=='images':
            import ocr_reading
            blocks=ocr_reading.blocks(a)
        else:blocks=[b for b in a.get('blocks',[]) if b.get('type')!='image' and b.get('text')]
        if a.get('note'):blocks=[*blocks,{'id':'note','text':a['note']}]
        for key in ('content','essence_content'):
            content=(a.get('editorial') or {}).get(key)
            if content:blocks=[*blocks,{'id':'editorial-'+key,'text':documents.text(content)}]
        result.append({'uid':'article:'+a['id'],'id':a['id'],'kind':a.get('kind','article'),'title':a.get('title') or '未命名图文','platform':'images' if a.get('kind')=='images' else 'article','created_at':a.get('created_at',0),'duration':0,'status':a.get('status','unknown'),'url':'/studio/?view=library&item='+a['id'],'blocks':blocks})
    for kind,items in [('memory',memories),('note',notes)]:
        for a in items:result.append({'uid':kind+':'+a['id'],'id':a['id'],'kind':kind,'title':a.get('title') or '个人专题笔记','platform':kind,'created_at':a.get('updated',0),'duration':0,'status':'ready','url':'/studio/?view=knowledge' if kind=='memory' else '/studio/?view=topics','blocks':[{'id':'personal','text':a.get('text') or a.get('personal','')}]})
    return result

def sync():
    with LOCK:
        records=catalog(); fingerprint=topic_search.digest(records)
        with store.connect() as db:
            init(db);old=db.execute('SELECT fingerprint FROM library_state WHERE id=1').fetchone()
            if not old or old[0]!=fingerprint:
                db.execute('DELETE FROM library_passages');db.execute('DELETE FROM library_fts')
                for r in records:
                    for block in [{'id':'title','text':r['title']},*r['blocks']]:
                        for offset in range(0,len(block.get('text','')),800):
                            p={'uid':r['uid'],'block_id':block['id'],'offset':offset,'text':block['text'][offset:offset+800],**{k:block[k] for k in ('start','end') if k in block}}
                            ident=db.execute('INSERT INTO library_passages(uid,payload) VALUES (?,?)',(r['uid'],json.dumps(p,ensure_ascii=False))).lastrowid
                            db.execute('INSERT INTO library_fts(rowid,tokens) VALUES (?,?)',(ident,' '.join(topic_search.terms(p['text'],False))))
                db.execute('INSERT OR REPLACE INTO library_state VALUES (1,?)',(fingerprint,))
        return records

def retrieve(query,uid=None,limit=12):
    terms=topic_search.terms(query)[:48]
    with store.connect() as db:
        init(db)
        if terms:
            expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
            rows=db.execute('SELECT p.id,p.payload FROM library_fts f JOIN library_passages p ON p.id=f.rowid WHERE library_fts MATCH ? AND (? IS NULL OR p.uid=?) ORDER BY bm25(library_fts),p.id LIMIT ?',(expression,uid,uid,limit)).fetchall()
        else:
            rows=db.execute('SELECT id,payload FROM library_passages WHERE (? IS NULL OR uid=?) AND instr(lower(json_extract(payload,\'$.text\')),?)>0 LIMIT ?',(uid,uid,topic_search.normalize(query),limit)).fetchall() if query.strip() else []
    return [{**json.loads(r['payload']),'citation_id':str(r['id'])} for r in rows]

def require(uid):
    row=next((r for r in catalog() if r['uid']==uid),None)
    if not row:raise HTTPException(404,'资料不存在')
    return row

@router.get('')
def listing(q:str=Query('',max_length=200),starred:bool=False,collection_id:str|None=None):
    records=sync(); hits={}
    if q.strip():
        for p in retrieve(q,limit=10000):hits.setdefault(p['uid'],p['text'])
    with store.connect() as db:
        stars={r[0] for r in db.execute('SELECT uid FROM library_meta WHERE starred=1')}
        members={r[0]:r[1] for r in db.execute('SELECT uid,position FROM library_members WHERE collection_id=?',(collection_id,))} if collection_id else {}
    items=[{**{k:v for k,v in r.items() if k!='blocks'},'starred':r['uid'] in stars,'snippet':hits.get(r['uid'],'')[:240]} for r in records if (not starred or r['uid'] in stars) and (not collection_id or r['uid'] in members) and (not q.strip() or r['uid'] in hits)]
    items.sort(key=lambda r:members[r['uid']] if collection_id else -r['created_at'])
    platforms={}
    for r in records:platforms[r['platform']]=platforms.get(r['platform'],0)+1
    return {'items':items,'stats':{'total':len(records),'duration':sum(r['duration'] for r in records if isinstance(r['duration'],(int,float))),'platforms':platforms,'recent':sum(r['created_at']>=time.time()-7*86400 for r in records)}}

class Star(BaseModel):uid:str;value:bool
@router.post('/star')
def star(body:Star):
    require(body.uid)
    with store.connect() as db:init(db);db.execute('INSERT OR REPLACE INTO library_meta VALUES (?,?)',(body.uid,int(body.value)))
    return {'ok':True}

class Collection(BaseModel):name:str=Field(min_length=1,max_length=80)
class Members(BaseModel):uids:list[str]=Field(max_length=1000)
def collection(ident):
    with store.connect() as db:
        init(db);row=db.execute('SELECT * FROM library_collections WHERE id=?',(ident,)).fetchone()
    if not row:raise HTTPException(404,'合集不存在')
    return dict(row)
@router.get('/collections')
def collections():
    with store.connect() as db:init(db);return [dict(r) for r in db.execute('SELECT c.*,COUNT(m.uid) count FROM library_collections c LEFT JOIN library_members m ON m.collection_id=c.id GROUP BY c.id ORDER BY c.created DESC')]
@router.post('/collections')
def create(body:Collection):
    name=body.name.strip()
    if not name:raise HTTPException(400,'合集名称不能为空')
    value={'id':uuid.uuid4().hex[:16],'name':name,'created':time.time()}
    with store.connect() as db:init(db);db.execute('INSERT INTO library_collections VALUES (:id,:name,:created)',value)
    return value
@router.put('/collections/{ident}')
def rename(ident:str,body:Collection):
    collection(ident)
    if not body.name.strip():raise HTTPException(400,'合集名称不能为空')
    with store.connect() as db:db.execute('UPDATE library_collections SET name=? WHERE id=?',(body.name.strip(),ident))
    return collection(ident)
@router.put('/collections/{ident}/members')
def replace(ident:str,body:Members):
    collection(ident);uids=list(dict.fromkeys(body.uids));valid={r['uid'] for r in catalog()}
    if any(uid not in valid for uid in uids):raise HTTPException(400,'部分资料已不存在，请刷新')
    with store.connect() as db:
        db.execute('DELETE FROM library_members WHERE collection_id=?',(ident,));db.executemany('INSERT INTO library_members VALUES (?,?,?)',[(ident,u,i) for i,u in enumerate(uids)])
    return {'uids':uids}
@router.get('/collections/{ident}/members')
def members(ident:str):
    collection(ident)
    with store.connect() as db:return [r[0] for r in db.execute('SELECT uid FROM library_members WHERE collection_id=? ORDER BY position',(ident,))]
@router.delete('/collections/{ident}')
def remove(ident:str):
    collection(ident)
    with store.connect() as db:db.execute('DELETE FROM library_members WHERE collection_id=?',(ident,));db.execute('DELETE FROM library_collections WHERE id=?',(ident,))
    return {'ok':True}
@router.get('/collections/{ident}/export')
def export(ident:str):
    from document_exports import write_task
    c=collection(ident);records={r['uid']:r for r in catalog()};output=io.BytesIO();manifest=[]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for i,uid in enumerate(members(ident),1):
            r=records.get(uid)
            if not r:manifest.append({'uid':uid,'missing':['source']});continue
            if r['kind']=='audio':entry=write_task(z,{'index':i,'task_id':r['id'],'status':r['status'],'summarize':True,'url':r['url']})
            else:
                name=f'{i:03}-source.txt';z.writestr(name,r['title']+'\n\n'+'\n\n'.join(b['text'] for b in r['blocks']));entry={'files':[name],'missing':[]}
            manifest.append({'uid':uid,**entry})
        z.writestr('collection-manifest.json',json.dumps({**c,'items':manifest},ensure_ascii=False,indent=2))
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="shiwen-collection-{ident}.zip"'})
