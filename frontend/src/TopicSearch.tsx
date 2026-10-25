import React,{useEffect,useRef,useState} from 'react'
import {ArrowUpRight,BookOpen,LoaderCircle,Search} from 'lucide-react'
import {Button} from '@/components/ui/button'
import './topic-search.css'

type Topic={id:string;title:string;notes_count:number}
type Hit={hit_id:string;uid:string;category:string;title:string;text:string;source_hash:string;version:string;basis:string;highlights:number[][];task_id?:string;note_id?:string;job_id?:string;ranges:{block_id:string;start:number;end:number}[]}
type Result={items:Hit[];offset:number;has_more:boolean;candidate_count:number;truncated:boolean;warnings:string[];title_matches:Pick<Hit,'uid'|'title'|'category'|'hit_id'|'source_hash'>[];scope:Record<string,number>;method:string}
type Context=Hit&{blocks:{id:string;text:string;offset:number;highlights:number[][];start?:number;end?:number;clipped:boolean}[]}
type Note={id:string;personal:string;revision:number}
const labels:Record<string,string>={personal:'我的笔记',selection:'保存选段',original:'来源原稿'}
const basisLabels:Record<string,string>={original:'原稿选段',chapter:'章节原话',draft:'编辑稿选段',manuscript:'AI整理稿选段',unknown:'来源类型未记录'}
const backupKey=(id:string)=>'shiwen-topic-note-draft:'+id

async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const r=await fetch('/api/studio/research'+path,{...init,headers:{'Content-Type':'application/json',...init.headers}})
 const value=await r.json()
 if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'请求未完成，请稍后重试。')
 return value
}
export function Highlight({text,ranges}:{text:string;ranges:number[][]}){
 const chars=Array.from(text),parts:React.ReactNode[]=[];let cursor=0
 for(const [start,end] of ranges){if(start<cursor||end>chars.length||end<=start)continue
  parts.push(chars.slice(cursor,start).join(''),<mark key={start}>{chars.slice(start,end).join('')}</mark>);cursor=end
 }
 parts.push(chars.slice(cursor).join(''));return <>{parts}</>
}

export default function TopicSearch({topics,topicId,onTopic,onResearch,onNotesChanged}:{topics:Topic[];topicId:string;onTopic:(id:string)=>void;onResearch:(jobId:string)=>void;onNotesChanged:()=>Promise<void>}){
 const [query,setQuery]=useState(''),[category,setCategory]=useState('all'),[result,setResult]=useState<Result|null>(null)
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[context,setContext]=useState<Context|null>(null),[opening,setOpening]=useState(false)
 const [expanded,setExpanded]=useState<string[]>([]),[note,setNote]=useState<Note|null>(null),[draft,setDraft]=useState(''),[saving,setSaving]=useState(false)
 const [titleContext,setTitleContext]=useState(false)
 const request=useRef(0),locationRequest=useRef(0),abort=useRef<AbortController|null>(null),composing=useRef(false)
 const heading=useRef<HTMLHeadingElement>(null),contextHeading=useRef<HTMLHeadingElement>(null)
 const dirty=!!note&&note.personal!==draft
 function invalidate(){request.current++;locationRequest.current++;abort.current?.abort();setBusy(false);setOpening(false);setResult(null);setContext(null);setNote(null);setExpanded([]);setError('')}
 useEffect(()=>{invalidate();return()=>{request.current++;locationRequest.current++;abort.current?.abort()}},[topicId])
 async function run(offset=0){
  if(!topicId||!query.trim()||dirty||saving)return
  const id=++request.current;locationRequest.current++;abort.current?.abort();const controller=new AbortController();abort.current=controller
  setBusy(true);setError('');setContext(null);setNote(null);setOpening(false)
  try{const value=await api<Result>(`/topics/${encodeURIComponent(topicId)}/search?`+new URLSearchParams({q:query,category,offset:String(offset)}),{signal:controller.signal})
   if(id!==request.current)return;setResult(value);setExpanded([]);heading.current?.focus()
  }catch(e){if(id!==request.current)return;setResult(null);setError((e as Error).message)}finally{if(id===request.current)setBusy(false)}
 }
 async function open(hit:Pick<Hit,'hit_id'|'source_hash'>,titleOnly=false){
  if(dirty||saving){setError('请先保存或取消正在修改的理解。');return}
  const id=++locationRequest.current;setOpening(true);setContext(null);setNote(null);setError('')
  try{const value=await api<Context>(`/topics/${encodeURIComponent(topicId)}/search/context`,{method:'POST',body:JSON.stringify({hit_id:hit.hit_id,source_hash:hit.source_hash})})
   if(id!==locationRequest.current)return;setContext(value);setTitleContext(titleOnly)
   // Run after React has mounted the context heading.
   setTimeout(()=>{if(id===locationRequest.current)contextHeading.current?.focus()},0)
  }catch(e){if(id===locationRequest.current)setError((e as Error).message)}finally{if(id===locationRequest.current)setOpening(false)}
 }
 async function edit(){if(!context?.note_id)return
  const id=locationRequest.current;setOpening(true);setError('')
  try{const value=await api<Note>('/notes/'+context.note_id);if(id!==locationRequest.current)return
   setNote(value);setDraft(value.personal)
   const backup=localStorage.getItem(backupKey(value.id));if(backup){const old=JSON.parse(backup);if(typeof old.personal==='string'&&Number.isInteger(old.revision)){setDraft(old.personal);setNote({...value,revision:old.revision});setError('已恢复浏览器中未保存的理解。若版本已变化，保存会提示冲突；请先复制保留。')}}
  }catch(e){if(id===locationRequest.current)setError((e as Error).message)}finally{if(id===locationRequest.current)setOpening(false)}
 }
 async function save(){if(!note)return;setSaving(true);setError('')
  try{await api('/notes/'+note.id,{method:'PUT',body:JSON.stringify({revision:note.revision,personal:draft})});localStorage.removeItem(backupKey(note.id));setNote(null);setContext(null);setResult(null);await onNotesChanged();setError('理解已保存。请重新搜索查看最新结果。')}
  catch(e){setError((e as Error).message)}finally{setSaving(false)}
 }
 useEffect(()=>{if(!dirty)return;const leave=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};window.addEventListener('beforeunload',leave);return()=>window.removeEventListener('beforeunload',leave)},[dirty])
 const groups=new Map<string,Hit[]>();for(const hit of result?.items||[])groups.set(hit.uid,[...(groups.get(hit.uid)||[]),hit])
 return <section className="topic-search" aria-label="专题内搜索">
  <div className="topic-search-heading"><div><h3>在专题里找回资料</h3><p>搜索自己的理解、保存选段和关联原稿。全程在本机处理。</p></div><BookOpen size={20} aria-hidden="true"/></div>
  <label htmlFor="search-topic">搜索专题</label><select id="search-topic" value={topicId} disabled={dirty||saving} onChange={e=>onTopic(e.target.value)}><option value="">请选择一个专题</option>{topics.map(t=><option key={t.id} value={t.id}>{t.title}（{t.notes_count}）</option>)}</select>
  <form onSubmit={e=>{e.preventDefault();if(!composing.current)void run()}}>
   <label htmlFor="topic-query">关键词或问题</label><div className="topic-query-row"><input id="topic-query" type="search" maxLength={200} value={query} disabled={dirty||saving} autoComplete="off" placeholder="例如：客户、AI工具、公开过程" onCompositionStart={()=>{composing.current=true}} onCompositionEnd={()=>{composing.current=false}} onKeyDown={e=>{if(e.key==='Enter'&&(composing.current||e.nativeEvent.isComposing))e.preventDefault()}} onChange={e=>{invalidate();setQuery(e.target.value)}}/><Button type="submit" disabled={!topicId||!query.trim()||busy||dirty||saving}>{busy?<LoaderCircle className="spin" size={15} aria-hidden="true"/>:<Search size={15} aria-hidden="true"/>}搜索</Button></div>
   <label htmlFor="topic-category">查找范围</label><select id="topic-category" value={category} disabled={dirty||saving} onChange={e=>{invalidate();setCategory(e.target.value)}}><option value="all">全部文字</option>{Object.entries(labels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select>
  </form>
  {!topicId&&<p className="topic-search-hint">先选一个专题。没有专题时，可先选取原文并保存一条来源笔记。</p>}
  {error&&<p role="alert" className="topic-search-feedback">{error}</p>}
  {busy&&<p role="status">正在搜索本地资料…</p>}
  {result&&<div aria-busy={busy}>
   <h4 ref={heading} tabIndex={-1}>找到 {result.candidate_count}{result.truncated?'＋':''} 个匹配片段</h4>
   <p className="topic-search-hint">范围含 {result.scope.personal} 条个人笔记、{result.scope.selection} 条保存选段、{result.scope.original} 份原稿。匹配不代表能够回答问题。{result.method==='literal_single'?'当前按单字字面查找。':''}{result.truncated?'最多展示前50条，可缩短范围再查。':''}</p>
   {result.warnings.map(w=><p className="topic-search-feedback" key={w}>{w}</p>)}
   {!result.items.length&&<p className="topic-search-empty">当前范围未找到匹配。试试更短的关键词，或切换查找范围；同义表达可能尚未命中。</p>}
   {result.title_matches.length>0&&<details className="topic-title-matches"><summary>另有标题匹配（不代表正文命中）</summary>{result.title_matches.map(t=><div key={t.uid}><p>{labels[t.category]}：{t.title}</p><button className="topic-context-button" disabled={opening||dirty||saving} onClick={()=>void open(t,true)}>查看来源开头（仅标题匹配）</button></div>)}</details>}
   {[...groups].map(([uid,hits])=><section className="topic-result-group" key={uid}><h5>{hits[0].title}</h5><small>{labels[hits[0].category]} · {hits.length} 个本页片段{hits[0].category==='selection'?' · '+(basisLabels[hits[0].basis]||basisLabels.unknown):''}</small>{(expanded.includes(uid)?hits:hits.slice(0,2)).map(hit=><article key={hit.hit_id}><p><Highlight text={hit.text} ranges={hit.highlights}/></p><button className="topic-context-button" disabled={opening||dirty||saving} onClick={()=>void open(hit)}>查看原文位置与上下文</button></article>)}{hits.length>2&&<button className="topic-context-button" onClick={()=>setExpanded(old=>old.includes(uid)?old.filter(x=>x!==uid):[...old,uid])}>{expanded.includes(uid)?'收起同来源片段':`展开其余 ${hits.length-2} 个片段`}</button>}</section>)}
   <div className="topic-search-pagination"><Button size="sm" variant="outline" disabled={busy||dirty||saving||!result.offset} onClick={()=>void run(result.offset-10)}>上一页</Button><span>第 {Math.floor(result.offset/10)+1} 页</span><Button size="sm" variant="outline" disabled={busy||dirty||saving||!result.has_more} onClick={()=>void run(result.offset+10)}>下一页</Button></div>
  </div>}
  {opening&&<p role="status">正在核对来源版本…</p>}
  {context&&<section className="topic-context"><h4 ref={contextHeading} tabIndex={-1}>来源位置与相邻文字</h4><p className="topic-search-hint">{labels[context.category]} · {context.category==='selection'?(basisLabels[context.basis]||basisLabels.unknown):'本地保存内容'} · 版本 {context.version}</p>
   {titleContext&&<p className="topic-search-feedback">以下为来源开头，未标为查询命中的正文。</p>}
   {context.blocks.map(b=><blockquote key={b.id}><small>{b.id} · 字符位置 {b.offset}{b.start!=null?' · '+Math.floor(b.start/60)+':'+String(Math.floor(b.start%60)).padStart(2,'0'):''}</small><p><Highlight text={b.text} ranges={titleContext?[]:b.highlights}/></p>{b.clipped&&<small>仅展示附近文字</small>}</blockquote>)}
   <p className="topic-search-hint">高亮用于定位，不代表已核实观点。音频时间为语音段边界。</p>
   <div className="topic-context-actions">{context.task_id&&<a href={'/studio/?'+new URLSearchParams({task:context.task_id,search_topic:topicId,search_hit:context.hit_id,search_hash:context.source_hash})} target="_blank" rel="noreferrer">打开原稿位置 <ArrowUpRight size={13} aria-hidden="true"/></a>}{context.job_id&&<button disabled={dirty||saving} onClick={()=>onResearch(context.job_id!)}>回看深入与来源</button>}{context.note_id&&<button disabled={opening||saving||!!note} onClick={()=>void edit()}>补充自己的理解</button>}</div>
   {note&&<div className="topic-note-editor"><label htmlFor="topic-note-edit">修改自己的理解</label><textarea id="topic-note-edit" rows={5} maxLength={12000} disabled={saving} value={draft} onChange={e=>{setDraft(e.target.value);try{localStorage.setItem(backupKey(note.id),JSON.stringify({personal:e.target.value,revision:note.revision}))}catch{setError('浏览器备份失败，请先复制保留输入内容再离开。')}}}/><Button size="sm" disabled={saving} onClick={()=>void save()}>保存理解</Button><Button size="sm" variant="ghost" disabled={saving} onClick={()=>{localStorage.removeItem(backupKey(note.id));setNote(null);setDraft('')}}>取消修改</Button>{dirty&&<p className="topic-search-hint">有未保存修改；保存或取消后再切换搜索。浏览器备份可在重新打开此笔记时恢复。</p>}</div>}
  </section>}
 </section>
}
