import {Skeleton,useFirstReveal} from './Motion'
import Creation from './Creation'
import React,{useEffect,useRef,useState} from 'react'
import {ArrowLeft,ArrowUpRight,BookOpen,Download,FileText,Link,LoaderCircle,Plus,Search} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Dialog,DialogContent,DialogDescription,DialogHeader,DialogTitle} from '@/components/ui/dialog'
import './articles.css'
import ImageImport from './ImageImport'
import ImageEditorial,{type Editorial} from './ImageEditorial'
import ImageReader,{type ImageBlock,type Reading} from './ImageReader'

type Block=ImageBlock&{level?:number;rows?:string[][];url?:string}
type Section={heading:string;text:string;quote:string;block_id:string}
type Artifact={id:string;question:string;sections:Section[];gaps:string[];rejected:number;source_hash?:string;image_page?:number}
type Item={editorial?:Editorial;reading?:Reading;reading_status?:string;reading_error?:string;id:string;kind?:string;image_status?:string;expected_images?:number;ocr_completed?:number;source_share?:string;content_hash?:string;title:string;author?:string;status:string;error?:string;source_url?:string;warnings:string[];completeness?:string;blocks:Block[];note:string;note_revision:number;artifacts:Artifact[];question_status:string;question_error?:string}
async function api<T>(path:string,init?:RequestInit):Promise<T>{
 const r=await fetch('/api/library'+path,{...init,headers:{'Content-Type':'application/json'}})
 if(!r.ok){const v=await r.json();throw new Error(typeof v.detail==='string'?v.detail:'输入格式有误，请检查后重试。')}
 return r.json()
}
const stateName=(s:string)=>({queued:'等待导入',running:'正在导入',ready:'可阅读',failed:'需要处理'}[s]||s)
export default function ArticleLibrary({extraNavigation,imageCapture:PrivateCapture}:{extraNavigation?:React.ReactNode;imageCapture?:React.ComponentType<{onCreated:(id:string)=>Promise<void>;notify:(text:string)=>void}>}){
 const [initialLoading,setInitialLoading]=useState(true)
 const reveal=useFirstReveal(!initialLoading)
 const [items,setItems]=useState<Item[]>([]),[item,setItem]=useState<Item|null>(null),[filter,setFilter]=useState('')
 const [dialog,setDialog]=useState(false),[kind,setKind]=useState('url'),[content,setContent]=useState(''),[title,setTitle]=useState(''),[url,setUrl]=useState('')
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[note,setNote]=useState(''),[question,setQuestion]=useState(''),[saving,setSaving]=useState(false)
 const [activeBlock,setActiveBlock]=useState(''),[topicTitle,setTopicTitle]=useState(''),[topicSaved,setTopicSaved]=useState('')
 const [imageView,setImageView]=useState<'article'|'essence'|'source'>('article')
 const [imagePage,setImagePage]=useState(1),[questionScope,setQuestionScope]=useState('all')
 const current=useRef(''),seq=useRef(0),dirty=useRef(false)
 dirty.current=!!item&&note!==item.note
 async function refreshList(){setItems(await api<Item[]>('/items'))}
 async function load(id:string,initial=false){
  if(!initial&&dirty.current&&!window.confirm('笔记尚未保存。输入已暂存在本机浏览器，确定切换材料？'))return
  const n=++seq.current;const next=await api<Item>('/items/'+id)
  if(n!==seq.current)return
  let draft:string|null=null
  try{draft=localStorage.getItem('shiwen-article-note-'+id)}catch{setMessage('当前浏览器不能暂存输入，请及时保存笔记。')}
  current.current=id;setItem(next);setNote(draft??next.note);setQuestion('');setActiveBlock('');setTopicSaved('');setImageView('article')
  if(!initial)history.replaceState(null,'','/studio/?view=library&item='+id)
 }
 useEffect(()=>{refreshList().catch(e=>setMessage(e.message)).finally(()=>setInitialLoading(false));const id=new URLSearchParams(location.search).get('item');if(id)load(id,true).catch(e=>setMessage(e.message))},[])
 useEffect(()=>{if(!item)return;const params=new URLSearchParams(location.search),topic=params.get('search_topic'),hit=params.get('search_hit'),hash=params.get('search_hash');if(!topic||!hit||!hash)return;let stopped=false
  fetch(`/api/studio/research/topics/${encodeURIComponent(topic)}/search/context`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hit_id:hit,source_hash:hash,include_hidden:params.get('search_hidden')==='true'})}).then(async r=>{const value=await r.json();if(!r.ok)throw Error(value.detail||'来源位置已变化');return value}).then(value=>{
   if(stopped)return;const exact=value.ranges.map((r:{block_id:string;start:number;end:number})=>{const b=(item.kind==='images'?item.reading?.regions||[]:item.blocks).find(b=>b.id===r.block_id);return b?Array.from(b.text).slice(r.start,r.end).join(''):null})
   if(value.article_id!==item.id||exact.includes(null)||exact.join('\n\n')!==value.text)throw Error('图文位置与当前版本不一致，请重新搜索')
   go(value.ranges[0].block_id)
  }).catch(e=>{if(!stopped)setMessage(e.message)});return()=>{stopped=true}
 },[item?.id])
 useEffect(()=>{
  const id=item?.id
  if(!id||(!['queued','running'].includes(item.status)&&!['queued','running'].includes(item.question_status)&&!['queued','running'].includes(item.reading_status||'')&&!['queued','running'].includes(item.editorial?.status||'')))return
  const timer=setInterval(async()=>{try{
   const next=await api<Item>('/items/'+id)
   if(current.current!==id)return
   setItem(next);await refreshList()
  }catch(e){setMessage((e as Error).message)}},3000)
  return()=>clearInterval(timer)
 },[item?.id,item?.status,item?.question_status,item?.reading_status,item?.editorial?.status])
 useEffect(()=>{if(item){try{localStorage.setItem('shiwen-article-note-'+item.id,note)}catch{setMessage('浏览器暂存空间不可用，请点击保存笔记；当前输入仍保留。')}}},[item?.id,note])
 useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(dirty.current){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[])
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setMessage('');try{
  const next=await api<Item>('/items',{method:'POST',body:JSON.stringify({kind,content,title,source_url:url})})
  await refreshList();await load(next.id);setDialog(false);setContent('');setTitle('');setUrl('')
 }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}
 async function saveNote(){if(!item)return;setSaving(true);try{
  const next=await api<Item>('/items/'+item.id+'/note',{method:'PUT',body:JSON.stringify({revision:item.note_revision,text:note})})
  if(current.current===next.id)setItem(next);setMessage('笔记已保存，原文保持不变。')
 }catch(e){setMessage((e as Error).message)}finally{setSaving(false)}}
 async function ask(e:React.FormEvent){e.preventDefault();if(!item)return;setBusy(true);try{
  const next=await api<Item>('/items/'+item.id+'/question',{method:'POST',body:JSON.stringify({question,image_page:item.kind==='images'&&questionScope==='page'?imagePage:null})})
  if(current.current===next.id)setItem(next)
 }catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}
 function go(id:string){setImageView('source');setActiveBlock(id);setTimeout(()=>{const el=document.getElementById('article-'+id);el?.scrollIntoView({block:'center'});el?.focus({preventScroll:true})},0)}
 function goQuote(section:Section){if(!item)return;const block=item.blocks.find(b=>b.id===section.block_id);const body=block?.type==='image'?item.blocks.filter(b=>b.source_image_id===block.id).map(b=>b.text).join('\n'):block?.text;if(!body?.includes(section.quote)){setMessage('摘录与当前识别稿不一致，请重新提问或回原图核对。');return}go(section.block_id)}
 async function imported(id:string){await refreshList();await load(id);setDialog(false);setContent('');setTitle('');setUrl('')}
 async function recognize(){if(!item)return;try{const value=await api<Item>(`/image-items/${item.id}/recognize`,{method:'POST'});if(current.current===value.id)setItem(value)}catch(e){setMessage((e as Error).message)}}
 async function refetch(){if(!item)return;try{const r=await fetch('/api/private/image-posts/'+item.id+'/retry',{method:'POST'});const v=await r.json();if(!r.ok)throw Error(v.detail||'重试失败');setItem(v)}catch(e){setMessage((e as Error).message)}}
 async function addTopic(){if(!item)return;setBusy(true);try{const r=await fetch('/api/studio/research/materials',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:item.id,topic_title:topicTitle})});const v=await r.json();if(!r.ok)throw Error(v.detail||'保存专题失败');setTopicSaved(v.topic_id);setMessage('已加入专题，正文和识别稿可在专题中搜索。')}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}}
 const working=item&&['queued','running'].includes(item.question_status)
 return <div data-enter={reveal.enter} onPointerDown={reveal.cancel} onFocusCapture={reveal.cancel} className="article-app">{(initialLoading||busy)&&<Skeleton label="正在读取图文资料"/>}
  <a className="article-skip" href="#article-reading">跳到原文</a>
  <aside className="article-nav" aria-label="图文素材库">
   <a className="article-brand" href="/studio/?view=library"><img src="/logo.svg" width="34" height="34" alt=""/><span>拾文<small>收藏之后，继续读懂</small></span></a>
   <Button className="article-import" onClick={()=>setDialog(true)}><Plus size={17}/>导入图文</Button>
   <div className="article-nav-title"><h1>图文素材</h1><span>{items.length}</span></div>
   <label className="article-search"><Search size={16}/><span className="sr-only">搜索图文标题或作者</span><input type="search" autoComplete="off" name="article_search" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="标题、作者…"/></label>
   <nav className="article-item-list" aria-label="已导入材料">{items.filter(i=>(i.title+' '+(i.author||'')).includes(filter)).map(i=><button key={i.id} className={item?.id===i.id?'selected':''} aria-current={item?.id===i.id?'page':undefined} onClick={()=>load(i.id).catch(e=>setMessage(e.message))}><FileText size={17}/><span><strong>{i.title}</strong><small>{i.author||'手动导入或待解析'} · {stateName(i.status)}</small></span></button>)}{items.length===0&&<p>先留下一篇真正想读的内容。<br/>支持文章链接、粘贴正文和网页 HTML。</p>}</nav>
   {extraNavigation}
   <a className="article-back" href="/studio/?view=topics">专题资料与搜索</a>
   <a className="article-back" href="/studio/"><ArrowLeft size={16}/>视频文稿工作台</a>
  </aside>
  <main id="article-reading" className="article-main" aria-busy={item?.status==='running'}>
   {item?<><header className="article-toolbar"><span>原文阅读</span><Creation key={item.id} sourceKey={'article-'+item.id} source={item.editorial?.content?item.editorial.content.content.map(n=>n.content?.map(t=>t.text||'').join('')||'').join('\n\n'):item.blocks.map(b=>b.text||'').join('\n\n')}/><Button variant="outline" onClick={()=>{try{const body=item.kind==='images'?(imageView==='essence'?item.editorial?.essence_content:item.editorial?.content):null;const text=body?body.content.map(n=>(n.type==='heading'?'## ':'')+(n.content?.map(t=>t.text||'').join('')||'')).join('\n\n'):item.blocks.map(b=>b.text||'').join('\n\n');localStorage.setItem('shiwen-card-import','# '+item.title+'\n\n'+text);window.open('/cards/app/','_blank','noopener')}catch{setMessage('请导出Markdown后在图文工具中导入。')}}}>转图文卡片</Button><a href={'/api/library/items/'+item.id+'/export?reading_mode=clean'}><Download size={16}/>{item.kind==='images'?'导出识别稿':'导出 Markdown'}</a></header>
    <article className="article-paper"><div className="article-meta">{item.author||'作者未提供'}{item.completeness==='partial'?' · 部分内容缺失':item.status==='ready'?' · 完整性待核对':''}</div><h2>{item.title}</h2>
     {item.source_url&&<a className="article-origin" href={item.source_url} target="_blank" rel="noreferrer">打开来源页面<ArrowUpRight size={15}/></a>}
     {item.kind==='images'&&<div className="image-pipeline-status" role="status">{({fetching:'正在获取原图',uploading:'等待图片上传完成',queued:'等待识别',running:'正在本地识字',completed:'图片文字已提取，待核对',partial:'部分图片未完成识别',failed:'需要重试'} as Record<string,string>)[item.image_status||'']||'图片资料'} · {item.expected_images??'未知'} 张，已识别 {item.ocr_completed||0} 张{item.error&&<p>{item.error}</p>}{!['fetching','queued','running'].includes(item.image_status||'')&&<div><Button variant="outline" size="sm" onClick={recognize}>重新识别已保存图片</Button>{item.image_status==='uploading'&&<Button variant="ghost" size="sm" onClick={async()=>{try{setItem(await api<Item>(`/image-items/${item.id}/stop-upload`,{method:'POST'}))}catch(e){setMessage((e as Error).message)}}}>结束上传并保留已收图片</Button>}{PrivateCapture&&item.source_share&&<Button variant="ghost" size="sm" onClick={refetch}>重取缺失图片</Button>}</div>}</div>}
     {item.status==='ready'&&<details className="article-scope" open={item.completeness==='partial'}><summary>查看导入范围与缺失提示</summary><ul>{item.warnings.map(w=><li key={w}>{w}</li>)}</ul><p>{item.kind==='images'?'识别文字保留原图与区域位置，可能有错字或错序。':'本材料配图尚未进行文字识别。'} 导出包含文字与来源标记，不包含图片文件。</p></details>}
     {item.kind==='images'?<><div className="image-view-tabs" role="group" aria-label="图文阅读方式">{([['article','完整整理稿'],['essence','精华'],['source','原图与识别稿']] as const).map(([key,label])=><button key={key} aria-pressed={imageView===key} onClick={()=>setImageView(key)}>{label}</button>)}</div>{imageView==='source'?<><ImageReader id={item.id} blocks={item.blocks} reading={item.reading} readingStatus={item.reading_status} readingError={item.reading_error} activeBlock={activeBlock} onLocate={go} onPageChange={setImagePage} onUpdate={value=>{if(current.current===value.id)setItem(value)}} notify={setMessage}/></>:<ImageEditorial id={item.id} value={item.editorial} mode={imageView} onUpdate={value=>{if(current.current===value.id)setItem(value)}} onSource={()=>setImageView('source')} notify={setMessage}/>}</>:item.status==='failed'?<div className="article-failure" role="alert"><p>{item.error}</p><Button variant="outline" onClick={()=>setDialog(true)}>换一种方式导入</Button></div>:item.status!=='ready'?<p role="status"><LoaderCircle size={18}/>正在读取正文与图片，图片较多时需要更久。你可以先切换到其他材料。</p>:item.blocks.map(b=><div key={b.id} id={'article-'+b.id} className="article-block" tabIndex={-1}>
      {b.type==='image'?<figure>{b.asset_status==='saved'?<img loading="lazy" width={b.width||960} height={b.height||640} src={'/api/library/items/'+item.id+'/assets/'+b.asset_name} alt={b.text||'原文配图'}/>:<div className="article-image-missing">图片未保存：{b.asset_error||'超过本次图片数量限制'}</div>}{b.text&&<figcaption>{b.text}</figcaption>}{b.url&&<a href={b.url} target="_blank" rel="noreferrer">查看原图来源</a>}</figure>:
       b.type==='code'?<pre><code>{b.text}</code></pre>:b.type==='table'?<div className="article-table-wrap"><table><tbody>{b.rows?.map((r,n)=><tr key={n}>{r.map((c,m)=><td key={m}>{c}</td>)}</tr>)}</tbody></table></div>:
       b.type==='heading'?<h3>{b.text}</h3>:b.type==='quote'?<blockquote>{b.text}</blockquote>:b.type==='link'?<a className="article-source-link" href={b.url} target="_blank" rel="noreferrer"><Link size={13}/>{b.text}</a>:<p>{b.text}</p>}
     </div>)}
    </article></>:<div className="article-empty"><BookOpen size={38}/><h2>把一份材料，读成自己的理解。</h2><p>先保留原文、图片与出处。<br/>带着一个问题阅读，再留下你的笔记。</p><Button onClick={()=>setDialog(true)}><Plus size={17}/>导入第一篇图文</Button><p className="article-empty-note">基础导入不调用 AI；需要时再提问。</p></div>}
  </main>
  {item?.status==='ready'&&<aside className="article-notes" aria-label="问题与个人笔记"><h2>带着问题读</h2><p className="article-help">你想从这篇材料里解决什么？说明将附原文摘录，未提供的信息会单独列出。</p>
   <form onSubmit={ask}>{item.kind==='images'&&<><label htmlFor="image-question-scope">参考范围</label><select id="image-question-scope" value={questionScope} onChange={e=>setQuestionScope(e.target.value)}><option value="all">整份图集的识别稿</option><option value="page">当前第 {imagePage} 张</option></select><div><button type="button" className="article-locate" onClick={()=>setQuestion('请根据识别稿提炼学习重点、概念之间的关系和需要进一步核实的问题。不要替原文补充不存在的答案。')}>提炼学习重点</button><button type="button" className="article-locate" onClick={()=>setQuestion('请整理材料介绍的工具用途、适用场景和未说明的限制，明确区分原作者说法与需要核实的事项。')}>整理工具要点</button></div></>}<label htmlFor="article-question">我的问题</label><textarea id="article-question" autoComplete="off" name="article_question" maxLength={1000} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="例如：这套方法有哪些前置条件？"/><small>点击后将当前范围的文字与问题发送给已配置的云端模型；不发送原图、不联网搜索，沿用文本调用额度。图片问答参考识别稿，不自动理解图解箭头。</small><Button disabled={busy||!!working||question.trim().length<2} type="submit">{working?<><LoaderCircle className="spin"/>正在结合原文整理</>:'结合原文解释'}</Button></form>
   {item.question_error&&<p className="article-error" role="alert">{item.question_error}</p>}
   {item.artifacts.slice().reverse().map(a=><section className="article-answer" key={a.id}><h3>{a.question}</h3><p className="article-help">AI 解释，仅校验摘录位置，未等同事实核实。{a.image_page?' 参考第'+a.image_page+'张。':''}</p>{a.source_hash&&a.source_hash!==item.content_hash&&<p className="article-error">生成时的正文或识别稿已有变化，请重新提问核对。</p>}{a.sections.map((s,n)=><div key={n}><h4>{s.heading}</h4><p>{s.text}</p><blockquote>{s.quote}</blockquote><button className="article-locate" onClick={()=>goQuote(s)}>定位原文</button></div>)}{a.gaps.length>0&&<><h4>原文没有回答</h4><ul>{a.gaps.map((g,n)=><li key={n}>{g}</li>)}</ul></>}{a.rejected>0&&<p>有 {a.rejected} 段无法逐字定位，未展示。</p>}<Button variant="outline" onClick={()=>setNote(v=>v+(v?'\n\n':'')+a.question+'\n'+a.sections.map(s=>s.text+(item.kind==='images'?'\n识别稿摘录：':'\n原话：')+s.quote+' ['+s.block_id+']').join('\n\n')+(a.gaps.length?'\n待解决：'+a.gaps.join('；'):''))}>加入笔记草稿</Button></section>)}
   <section className="article-personal"><h2>我的笔记</h2><label htmlFor="article-note" className="sr-only">个人笔记</label><textarea id="article-note" autoComplete="off" name="article_note" value={note} maxLength={40000} onChange={e=>setNote(e.target.value)} placeholder="留下理解、疑问，或下一步想尝试的事。"/><small>输入暂存于当前浏览器；保存后进入本机素材库。</small><Button onClick={saveNote} disabled={saving||note===item.note}>{saving?'正在保存…':'保存笔记'}</Button></section>
   <section className="article-topic-save"><h2>留在一个专题里</h2><label htmlFor="article-topic">专题名称</label><input id="article-topic" maxLength={100} value={topicTitle} onChange={e=>setTopicTitle(e.target.value)} placeholder="例如：Agent面试准备"/><Button variant="outline" disabled={busy||!topicTitle.trim()} onClick={addTopic}>把这份材料加入专题</Button>{topicSaved&&<a href={'/studio/?view=topics&topic='+topicSaved}>在专题里搜索这份材料</a>}<small>加入的是正文与识别稿，AI说明不会自动混入原文。</small></section>
  </aside>}
  <Dialog open={dialog} onOpenChange={setDialog}><DialogContent className="article-dialog"><DialogHeader><DialogTitle>留下一份值得读的材料</DialogTitle><DialogDescription>直接读取文字与图文，不经过音频转换。受限链接可改用正文或网页 HTML。</DialogDescription></DialogHeader>
   <form onSubmit={submit}><label htmlFor="article-kind">导入方式</label><select id="article-kind" autoComplete="off" name="article_kind" value={kind} onChange={e=>{setKind(e.target.value);setContent('')}}><option value="url">文章链接</option><option value="text">粘贴正文</option><option value="html">网页 HTML</option><option value="images">图片 / 截图 / 多图</option>{PrivateCapture&&<option value="private">分享图文链接（自用）</option>}</select>
    <label htmlFor="article-title">标题（选填）</label><input id="article-title" autoComplete="off" name="article_title" maxLength={300} value={title} onChange={e=>setTitle(e.target.value)}/>
    {kind==='private'&&PrivateCapture?<PrivateCapture onCreated={imported} notify={setMessage}/>:kind==='images'?<ImageImport title={title} onCreated={imported} notify={setMessage}/>:<>
    {kind!=='url'&&<><label htmlFor="article-source">原文链接（选填）</label><input id="article-source" autoComplete="off" name="article_source" type="url" value={url} onChange={e=>setUrl(e.target.value)}/></>}
    <label htmlFor="article-content">{kind==='url'?'文章链接':kind==='html'?'网页 HTML 内容':'正文内容'}</label><textarea id="article-content" autoComplete="off" name="article_content" required maxLength={1000000} value={content} onChange={e=>setContent(e.target.value)} placeholder={kind==='url'?'https://…':kind==='html'?'粘贴或选择已保存的 HTML 文件；本版不读取网页 ZIP 内附件。':'粘贴原文。单独出现的“图片”会标为原图未导入。'}/>
    {kind!=='url'&&<label className="article-file">或读取 {kind==='html'?'HTML':'TXT'} 文件<input autoComplete="off" name="article_file" type="file" accept={kind==='html'?'.html,.htm':'.txt'} onChange={async e=>{const f=e.target.files?.[0];if(f){if(f.size>1000000){setMessage('文件超过1MB，请缩小后重试。');return}setContent(await f.text())}}}/></label>}
    <p className="article-help">公众号与普通文章优先支持。知乎、小红书链接尚未完成真实样本验收；本版不处理登录、验证码或付费全文。HTML 配图仅支持可直接访问的网络图片。</p>
    <Button disabled={busy||!content.trim()} type="submit">{busy?'正在提交…':'导入并保留原文'}</Button></>}
   </form></DialogContent></Dialog>
  {message&&<div className="article-message" role="status">{message}<button aria-label="关闭提示" onClick={()=>setMessage('')}>关闭</button></div>}
 </div>
}
