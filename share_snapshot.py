"""Portable read-only snapshots: no remote assets, account or server required."""
import html,json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
import cli_summary,document_notes,mindmap,store

router=APIRouter(prefix='/api/share-snapshots')
def stamp(value):
 return f'{int(value)//3600:02}:{int(value)//60%60:02}:{int(value)%60:02}' if type(value) in (int,float) and value>=0 else '无时间戳'
def render(b):
 esc=lambda v:html.escape(str(v),quote=True)
 root=None
 for g in b['generations']:
  if g.get('status')=='completed' and (g.get('mindmap') or (g.get('bundle') or {}).get('root')):
   root=mindmap.validate({'root':g.get('mindmap') or g['bundle']['root']});break
 def tree(n):return {'content':esc(n['text']),'children':[tree(c) for c in n.get('children',[])]}
 source=b['source'];link='<a href="'+esc(source)+'" target="_blank" rel="noreferrer">'+esc(source)+'</a>' if urlsplit(source).scheme in {'https','http'} else esc(source)
 body='<header><p>拾文 · 阅读快照</p><h1>'+esc(b['title'])+'</h1><p>'+esc(b['platform'])+' · '+esc(datetime.fromtimestamp(b['created_at']).strftime('%Y-%m-%d %H:%M'))+'</p><p>来源：'+link+'</p></header>'
 body+='<nav><a href="#draft">文稿</a><a href="#timeline">时间轴</a><a href="#summary">摘要</a><a href="#mindmap">导图</a></nav><main><section id="draft"><h2>文稿</h2><div class="prose">'+esc(b['transcript'])+'</div></section><section id="timeline"><h2>原文时间轴</h2>'
 for i,s in enumerate(b['sources']):body+='<article id="seg-'+str(i)+'"><small>'+esc(s['id'])+' · '+stamp(s.get('start'))+'</small><p>'+esc(s['text'])+'</p></article>'
 body+='</section><section id="summary"><h2>摘要</h2><div class="prose">'+esc(b['summary'] or '尚未生成摘要')+'</div></section><section id="mindmap"><h2>思维导图</h2>'
 scripts=''
 if root:
  assets=Path(__file__).resolve().parent/'cli_assets'
  scripts='\n'.join((assets/p).read_text(encoding='utf8') for p in ['d3-7.9.0.min.js','markmap-view-0.18.12.js']).replace('</script','<\\/script')
  data=json.dumps(tree(root),ensure_ascii=True).replace('<','\\u003c')
  scripts+='\nconst m=markmap.Markmap.create("#map",{initialExpandLevel:-1},'+data+');document.getElementById("fit").onclick=()=>m.fit();'
  body+='<button id="fit" type="button">适应窗口</button><svg id="map" role="img" aria-label="思维导图"></svg><details><summary>文字大纲</summary><pre>'+esc(mindmap.to_markdown(root))+'</pre></details>'
 else:body+='<p>本篇尚无导图，快照不会自动付费生成。</p>'
 body+='</section><section><h2>笔记</h2>'
 for n in b['notes']:body+='<article><small>'+esc(n['block_id'] or '整篇')+' · '+stamp(n['timestamp'])+'</small><p>'+esc(n['text'])+'</p></article>'
 body+='</section></main><footer>由拾文生成 · 只读离线快照 · AI整理与原始内容请自行核对</footer>'
 license='\n'.join((Path(__file__).resolve().parent/'cli_assets'/n).read_text(encoding='utf8') for n in ['D3-LICENSE','MARKMAP-LICENSE']) if root else ''
 css='body{margin:0;background:#fff;color:#202026;font:16px/1.8 -apple-system,Segoe UI,Roboto,sans-serif}header,main,nav,footer{max-width:900px;margin:auto;padding:24px}h1{font-size:38px;line-height:1.3}h2{border-bottom:1px solid #eee}nav{display:flex;gap:24px;flex-wrap:wrap}a{color:#b52573;overflow-wrap:anywhere}.prose,p,pre{white-space:pre-wrap;overflow-wrap:anywhere}section{margin-bottom:40px}article{padding:12px 0;border-bottom:1px solid #eee}small,footer{color:#666}svg{width:100%;height:520px}button{padding:12px;border:1px solid #ddd;border-radius:8px;background:#fff}button:focus-visible,a:focus-visible{outline:2px solid #ce3080}@media(max-width:500px){header,main,nav,footer{padding:16px}h1{font-size:28px}svg{height:400px}}'
 return '<!doctype html><!-- '+license.replace('--','- -')+' --><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'"><title>'+esc(b['title'])+'</title><style>'+css+'</style></head><body>'+body+('<script>'+scripts+'</script>' if scripts else '')+'</body></html>'
@router.post('/{ident}')
def generate(ident:str):
 b=document_notes.bundle(ident);directory=store.DATA/'jobs'/ident;directory.mkdir(parents=True,exist_ok=True)
 path=directory/('share-'+ident+'.html');cli_summary.atomic_text(path,render(b))
 return {'filename':path.name,'download':'/api/share-snapshots/'+ident+'/download'}
@router.get('/{ident}/download')
def download(ident:str):
 document_notes.task(ident);path=store.DATA/'jobs'/ident/('share-'+ident+'.html')
 if not path.is_file():raise HTTPException(404,'请先生成分享快照')
 return FileResponse(path,media_type='text/html; charset=utf-8',filename=path.name)
