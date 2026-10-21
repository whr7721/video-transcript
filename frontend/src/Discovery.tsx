import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowUpRight, Check, Compass, LoaderCircle, Search, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import './discovery.css'

export type Candidate = {video_id:string; canonical_url:string; caption:string; author_name:string; published_at:string; duration_sec:number|null; media_type:string; matched_queries:string[]; digg_count:number|null; transcript_id?:string|null}
type Job = {id:string; request:{topic:string; queries:string[]; max_candidates_total:number}; state:string; adapter_status:string|null; items:Candidate[]; selected_ids:string[]; selection_revision:number; can_resume:boolean; warnings:string[]; message:string; stopped_reason:string; per_query_progress:{query:string; pages:number; exhausted:boolean}[]}
type Brief = {id:string; topic:string; state:string; count:number; created_at:number}
const statusNames:Record<string,string> = {queued:'等待搜索',running:'搜索中',interrupted:'已中断',failed:'未完成',ok:'本轮结束',partial:'部分结果',login_required:'需要登录',user_action_required:'需要人工验证',rate_limited:'访问受限',unsupported:'暂不支持',error:'未完成'}
async function api<T>(url:string, init?:RequestInit):Promise<T> {
 const response = await fetch(url,{...init,headers:{'Content-Type':'application/json',...init?.headers}})
 const body = await response.json()
 if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'请检查输入后重试。')
 return body
}
export function filterCandidates(items:Candidate[], term:string, exclude:string, duration:number, unknown:boolean) {
 const includes = term.trim().toLowerCase().split(/\s+/).filter(Boolean)
 const excludes = exclude.trim().toLowerCase().split(/\s+/).filter(Boolean)
 return items.filter(row=>{
  const text = `${row.caption} ${row.author_name}`.toLowerCase()
  return row.media_type==='video' && includes.every(t=>text.includes(t)) && !excludes.some(t=>text.includes(t)) &&
   (row.duration_sec===null?unknown:duration===0||row.duration_sec<=duration)
 })
}
function durationLabel(value:number|null) {return value===null?'时长待核实':`${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`}

export default function Discovery() {
 const [jobs,setJobs] = useState<Brief[]>([]), [job,setJob] = useState<Job|null>(null)
 const [topic,setTopic] = useState('AI工具的实际变现'), [queries,setQueries] = useState('AI工具 变现 实操\nAI 接单 客户 交付\nAI工具 收费 案例')
 const [sort,setSort] = useState('general'), [windowValue,setWindowValue] = useState('unlimited'), [limit,setLimit] = useState(30)
 const [term,setTerm] = useState(''), [exclude,setExclude] = useState(''), [duration,setDuration] = useState(600), [unknown,setUnknown] = useState(true)
 const [selected,setSelected] = useState<string[]>([]), [dirty,setDirty] = useState(false), [busy,setBusy] = useState(false), [notice,setNotice] = useState('')
 const dirtyRef = useRef(false), activeRef = useRef(''), revisionRef = useRef(1)
 const running = job?.state==='running'||job?.state==='queued'
 const visible = filterCandidates(job?.items||[],term,exclude,duration,unknown)
 const shownIds = new Set(visible.map(row=>row.video_id))
 const hiddenSelected = selected.filter(id=>!shownIds.has(id)).length
 const excludedMedia = job?.items.filter(row=>row.media_type!=='video').length||0
 const excludedDuration = job?.items.filter(row=>row.media_type==='video'&&row.duration_sec!==null&&duration>0&&row.duration_sec>duration).length||0
 const excludedUnknown = !unknown?(job?.items.filter(row=>row.media_type==='video'&&row.duration_sec===null).length||0):0
 const label = job ? statusNames[job.state] || statusNames[job.adapter_status||''] || '已保存' : ''
 function mark(ids:string[]) {dirtyRef.current=true;setDirty(true);setSelected(ids)}
 function receive(value:Job) {setJob(value);if(!dirtyRef.current){setSelected(value.selected_ids);revisionRef.current=value.selection_revision}}
 async function list() {setJobs(await api<Brief[]>('/api/discovery'))}
 async function open(id:string) {
  if(dirtyRef.current)return
  setNotice('');activeRef.current=id
  try {const value=await api<Job>(`/api/discovery/${id}`);if(activeRef.current!==id)return;receive(value);const url=new URL(location.href);url.searchParams.set('discovery',id);history.replaceState(null,'',url)}catch(e){setNotice((e as Error).message)}
 }
 useEffect(()=>{let live=true;api<Brief[]>('/api/discovery').then(rows=>{if(!live)return;setJobs(rows);const id=new URLSearchParams(location.search).get('discovery')||rows[0]?.id;if(id)void open(id)}).catch(e=>setNotice(e.message));return()=>{live=false}},[])
 useEffect(()=>{
  if(!running||!job)return
  const id=job.id
  const timer=setInterval(async()=>{try{const value=await api<Job>(`/api/discovery/${id}`);if(activeRef.current===id){receive(value);if(!['running','queued'].includes(value.state))await list()}}catch(e){setNotice((e as Error).message)}},1800)
  return()=>clearInterval(timer)
 },[job?.id,running])
 useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(dirtyRef.current){e.preventDefault();e.returnValue=''}};addEventListener('beforeunload',warn);return()=>removeEventListener('beforeunload',warn)},[])
 async function search(e:React.FormEvent) {
  e.preventDefault();setBusy(true);setNotice('')
  try {const value=await api<Job>('/api/discovery',{method:'POST',body:JSON.stringify({topic,queries:queries.split('\n').map(v=>v.trim()).filter(Boolean),sort,published_within:windowValue,max_candidates_total:limit})});activeRef.current=value.id;receive(value);const url=new URL(location.href);url.searchParams.set('discovery',value.id);history.replaceState(null,'',url);await list()}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}
 }
 async function save() {
  if(!job)return
  setBusy(true);setNotice('')
  try {const value=await api<Job>(`/api/discovery/${job.id}/selection`,{method:'PUT',body:JSON.stringify({revision:revisionRef.current,video_ids:selected})});dirtyRef.current=false;setDirty(false);receive(value);setNotice('候选清单已保存。本轮不会下载或转写。')}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}
 }
 async function resume() {
  if(!job)return
  setBusy(true);setNotice('')
  try {const total=Math.min(100,Math.max(job.request.max_candidates_total,job.items.length)+20);const value=await api<Job>(`/api/discovery/${job.id}/resume`,{method:'POST',body:JSON.stringify({max_candidates_total:total})});receive(value);await list()}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="discovery-page">
  <a className="discovery-skip" href="#discovery-main">跳到候选内容</a>
  <aside className="discovery-nav" aria-label="话题发现导航">
   <a className="brand" href="/studio/"><img src="/logo.svg" alt="" width="36" height="36"/><span>拾文<small>把值得留下的，整理成文</small></span></a>
   <div className="discovery-nav-title"><Compass size={17}/>话题发现 <span>M1</span></div>
   <p className="discovery-caption">先挑值得读的，再留下全文。</p>
   <div className="discovery-history-title">搜索记录 <span>{jobs.length}</span></div>
   <nav className="discovery-history" aria-label="搜索记录">{jobs.map(row=><button key={row.id} disabled={dirty||busy} aria-current={job?.id===row.id?'page':undefined} onClick={()=>void open(row.id)}><strong>{row.topic}</strong><span>{new Date(row.created_at*1000).toLocaleDateString('zh-CN')} · {row.count} 条候选{row.state==='running'?' · 搜索中':''}</span></button>)}{!jobs.length&&<p className="discovery-caption">第一次搜索会保存在这里。</p>}</nav>
   <div className="discovery-nav-footer"><a href="/studio/"><ArrowLeft size={15}/>视频文稿</a><a href="/studio/?view=library">图文素材库<ArrowUpRight size={15}/></a></div>
  </aside>
  <main className="discovery-main" id="discovery-main" tabIndex={-1}>
   <header className="discovery-header"><div><span className="discovery-eyebrow">DISCOVER / 抖音话题</span><h1>从一个问题，找到值得读的内容。</h1><p>搜索作品信息，人工筛选候选。先看内容方向，再决定是否深入。</p></div><span className="discovery-mode"><Check size={14}/>仅搜索元信息</span></header>
   <form className="discovery-form" onSubmit={search}>
    <div className="discovery-query"><label>研究主题<input name="discovery_topic" autoComplete="off" value={topic} onChange={e=>setTopic(e.target.value)} maxLength={200} required/></label><label>搜索词 <small>每行一组，最多三组；按顺序搜索，共用总上限</small><textarea name="discovery_queries" autoComplete="off" rows={3} value={queries} onChange={e=>setQueries(e.target.value)} maxLength={386} required spellCheck={false}/></label></div>
    <div className="discovery-options"><label>排序<select name="discovery_sort" autoComplete="off" value={sort} onChange={e=>setSort(e.target.value)}><option value="general">综合相关</option><option value="most_liked">最多点赞</option><option value="latest">最新发布</option></select></label><label>发布时间<select name="discovery_window" autoComplete="off" value={windowValue} onChange={e=>setWindowValue(e.target.value)}><option value="unlimited">不限时间</option><option value="one_day">最近一天</option><option value="one_week">最近一周</option><option value="half_year">最近半年</option></select></label><label>候选总上限<select name="discovery_limit" autoComplete="off" value={limit} onChange={e=>setLimit(Number(e.target.value))}>{[10,30,50,100].map(n=><option key={n} value={n}>{n} 条</option>)}</select></label><Button type="submit" disabled={busy||running||dirty}>{busy||running?<LoaderCircle className="spin" size={16}/>:<Search size={16}/>}搜索候选</Button></div>
   </form>
   <div className="discovery-notice" role="status" aria-live="polite">{notice|| (dirty?'勾选尚未保存，请先保存或撤销，再切换记录。':'本轮不调用文本模型，也不下载音视频。搜索结果不代表平台全部作品。')}</div>
   <section className="discovery-results" aria-labelledby="discovery-results-title" aria-busy={!!running}>
    <div className="discovery-results-heading"><div><span className="discovery-eyebrow">CANDIDATES / 候选池</span><h2 id="discovery-results-title">{job?.request.topic||'等待一次有目的的搜索'}</h2></div>{job&&<span className={`discovery-state ${running?'is-running':''}`}>{running&&<LoaderCircle className="spin" size={14}/>} {label}</span>}</div>
    {job&&<><p className="discovery-caption">{job.message}</p><div className="discovery-progress">{job.per_query_progress.map(p=><span key={p.query}>{p.query} · {p.pages} 页{p.exhausted?' · 平台返回空页':''}</span>)}</div>{job.warnings.length>0&&<details className="discovery-warnings"><summary>本轮有 {job.warnings.length} 条提示</summary>{job.warnings.map((w,i)=><p key={i}>{w}</p>)}</details>}{['login_required','user_action_required','rate_limited'].includes(job.adapter_status||'')&&<p className="discovery-warnings">需要在独立爬虫浏览器完成登录或验证后再重试。系统不会自动反复请求。</p>}</>}
    <div className="discovery-filters"><SlidersHorizontal size={16} aria-hidden="true"/><label>标题 / 作者包含<input name="discovery_include" autoComplete="off" type="search" placeholder="例如：客户 交付…" value={term} onChange={e=>setTerm(e.target.value)}/></label><label>排除词<input name="discovery_exclude" autoComplete="off" type="search" placeholder="例如：课程 招生…" value={exclude} onChange={e=>setExclude(e.target.value)}/></label><label>时长<select name="discovery_duration" autoComplete="off" value={duration} onChange={e=>setDuration(Number(e.target.value))}><option value={600}>10 分钟内</option><option value={1200}>20 分钟内</option><option value={1800}>30 分钟内</option><option value={0}>不限时长</option></select></label><label className="discovery-check"><input type="checkbox" checked={unknown} onChange={e=>setUnknown(e.target.checked)}/>显示时长未知</label></div>
    <div className="discovery-list-top"><span aria-live="polite">显示 {visible.length} / {job?.items.length||0} 条 <small>· 图片及类型未知不进入视频候选</small></span><button disabled={!visible.length||busy} onClick={()=>mark([...new Set([...selected,...visible.map(r=>r.video_id)])])}>勾选当前可见</button></div>
    {job&&<p className="discovery-caption">隐藏原因：非视频或类型未知 {excludedMedia} 条 · 超出时长 {excludedDuration} 条 · 时长未知未显示 {excludedUnknown} 条 · 标题 / 作者关键词不匹配 {(job.items.length-visible.length-excludedMedia-excludedDuration-excludedUnknown)} 条</p>}
    <ul className="discovery-list" aria-label="视频候选">{visible.map((row,index)=><li key={row.video_id} className={selected.includes(row.video_id)?'is-selected':''}><label className="discovery-select"><input type="checkbox" aria-label={`选择 ${row.caption||row.video_id}`} checked={selected.includes(row.video_id)} disabled={busy} onChange={e=>mark(e.target.checked?[...selected,row.video_id]:selected.filter(id=>id!==row.video_id))}/><span>{String(index+1).padStart(2,'0')}</span></label><div className="discovery-row-body"><a href={row.canonical_url} target="_blank" rel="noreferrer" className="discovery-title">{row.caption||'无标题作品'}<ArrowUpRight size={14}/></a><div className="discovery-metadata"><strong>{row.author_name||'作者未知'}</strong><span>{row.published_at?row.published_at.slice(0,10):'发布日期未知'}</span><span>{durationLabel(row.duration_sec)}</span><span>{row.digg_count===null?'点赞未知':`${row.digg_count.toLocaleString('zh-CN')} 赞`}</span>{row.transcript_id&&<a href={`/studio/?task=${row.transcript_id}`}>已有文稿 · 打开</a>}</div><div className="discovery-query-tags">{row.matched_queries.map(q=><span key={q}>{q}</span>)}</div></div></li>)}</ul>
    {!visible.length&&<div className="discovery-empty"><Compass size={32}/><h3>{running?'正在寻找相关作品…':job?.items.length?'当前筛选下没有视频':'候选将出现在这里'}</h3><p>{job?.items.length?'试着减少关键词、移除排除词，或调整时长。隐藏候选不会删除已保存勾选。':'可先搜索“AI工具 变现 实操”，观察标题是否包含具体客户、交付或案例。'}</p></div>}
    {job&&<footer className="discovery-selection"><div><strong>已勾选 {selected.length} 条{dirty?' · 未保存':''}</strong><small>{hiddenSelected?`含 ${hiddenSelected} 条当前筛选隐藏的候选。`:'勾选记录在本机保存。'}后续阶段再接入下载与转写。</small></div><div className="discovery-selection-actions">{dirty&&<button disabled={busy} onClick={()=>{dirtyRef.current=false;setDirty(false);setSelected(job.selected_ids);void open(job.id)}}>撤销勾选修改</button>}<Button variant="outline" disabled={busy||running||dirty||job.items.length>=100} onClick={resume}>{job.can_resume?'继续搜索':'重试搜索'}（总上限 {Math.min(100,Math.max(job.request.max_candidates_total,job.items.length)+20)}）</Button><Button disabled={busy||!dirty} onClick={save}><Check size={16}/>保存候选清单</Button></div></footer>}
   </section>
  </main>
 </div>
}
