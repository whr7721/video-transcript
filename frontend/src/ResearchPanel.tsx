import {Skeleton} from './Motion'
import { useEffect, useState } from 'react'
import { BookOpen, ExternalLink, LoaderCircle, Search, Save, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import TopicSearch from './TopicSearch'

export type Passage = {taskId:string;basis:'original'|'draft'|'manuscript'|'chapter';revision:number;generation_id?:string;chapter_revision?:number;chapter_index?:number;selection_start?:number;selection:string}
type Citation={source_id:string;quote:string;relation?:string}
type ResearchJob={id:string;task_id:string;question:string;mode:string;status:string;stage:string;online:boolean;error?:string;
 context:{selection:string;basis:string;version:string};warnings:string[];rejected?:number;open_questions?:string[];
 claims?:{id:string;original:string;statement:string;kind:string}[];
 sections?:{heading:string;text:string;basis:string;citations:Citation[];support_status?:string;support_note?:string}[];
 sources:{id:string;title:string;url:string;kind:string;body:string;published_at?:string;retrieved_at:number}[]}
type Note={id:string;topic_id:string;job_id:string;topic_title:string;personal:string;revision:number;created:number}
type Topic={id:string;title:string;notes_count:number}

async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const response=await fetch('/api/studio/research'+path,{...init,headers:{'Content-Type':'application/json',...init.headers}})
 const body=await response.json()
 if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'请求未完成，请稍后重试。')
 return body
}
const stageNames:Record<string,string>={queued:'等待处理…',prepare:'准备选段…',search:'正在查找来源…',fetch:'正在读取网页正文…',answer:'正在整理解释与证据…',review:'正在核对引用是否支持结论…',confirm_claims:'等待选择核实命题' }

export default function ResearchPanel({passage,onSettings,settingsVersion=0}:{passage:Passage;onSettings:()=>void;settingsVersion?:number}){
 const [claimIds,setClaimIds]=useState<string[]>([])
 const [claimKinds,setClaimKinds]=useState<Record<string,string>>({})
 const [question,setQuestion]=useState(''),[mode,setMode]=useState('explain'),[online,setOnline]=useState(false)
 const [selection,setSelection]=useState(passage.selection),[selectedBasis,setSelectedBasis]=useState(passage)
 const [jobs,setJobs]=useState<ResearchJob[]>([]),[job,setJob]=useState<ResearchJob|null>(null),[busy,setBusy]=useState(false)
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[searchReady,setSearchReady]=useState(false)
 const [view,setView]=useState('research'),[topic,setTopic]=useState('我的学习与创作'),[personal,setPersonal]=useState('')
 const [topics,setTopics]=useState<Topic[]>([]),[notes,setNotes]=useState<Note[]>([]),[filter,setFilter]=useState(''),[editing,setEditing]=useState<Note|null>(null)
 const [editText,setEditText]=useState(''),[manualText,setManualText]=useState(''),[manualBusy,setManualBusy]=useState(false),[modelReady,setModelReady]=useState(true)
 const [historyLoading,setHistoryLoading]=useState(true)
 const taskId=passage.taskId
 useEffect(()=>{setSelection(passage.selection);setSelectedBasis(passage)},[passage.selection,passage.basis,passage.revision,passage.generation_id,passage.chapter_revision,passage.chapter_index,passage.selection_start])
 useEffect(()=>{let disposed=false;setHistoryLoading(true)
  Promise.all([api<ResearchJob[]>('/documents/'+taskId),api<Topic[]>('/topics'),api<Note[]>('/notes')]).then(([js,ts,ns])=>{if(!disposed){setJobs(js);setJob(js[0]||null);setTopics(ts);setNotes(ns)}}).catch(()=>{if(!disposed)setError('无法载入深入记录，请刷新页面重试。')}).finally(()=>{if(!disposed)setHistoryLoading(false)})
  return()=>{disposed=true}
 },[taskId])
 useEffect(()=>{let disposed=false;fetch('/api/settings').then(r=>r.json()).then(v=>{if(!disposed){setSearchReady(!!v.search_key_configured);setModelReady(v.key_configured!==false)}}).catch(()=>{});return()=>{disposed=true}},[taskId,settingsVersion])
 useEffect(()=>{if(!job||!['queued','running'].includes(job.status))return;let stopped=false
  const timer=setInterval(()=>api<ResearchJob>('/jobs/'+job.id).then(next=>{if(!stopped){setJob(next);setJobs(old=>[next,...old.filter(x=>x.id!==next.id)])}}).catch(()=>{if(!stopped)setError('读取任务进度失败，可刷新后继续查看。')}),1500)
  return()=>{stopped=true;clearInterval(timer)}
 },[job?.id,job?.status])
 async function saveManual(){setError('');setNotice('');setManualBusy(true);try{await api('/documents/'+taskId+'/manual-note',{method:'POST',body:JSON.stringify({...selectedBasis,selection,topic_title:topic,personal:manualText})});await refreshNotes();setManualText('');setNotice('手动笔记已保存，来源与版本一并保留；没有调用AI。')}catch(e){setError((e as Error).message)}finally{setManualBusy(false)}}
 async function refreshNotes(){const [ts,ns]=await Promise.all([api<Topic[]>('/topics'),api<Note[]>('/notes')]);setTopics(ts);setNotes(ns)}
 async function start(){
  setError('');setNotice('')
  if(!modelReady){setError('AI深入需要硅基流动 Key；仍可先手动记笔记。');return}
  if(online&&!searchReady){setError('联网需要 DeepSeek 官方搜索 Key。请打开设置配置，或取消联网先解释。');return}
  if(mode!=='explain'&&!online){setError('真实案例和外部局限需要开启联网，避免把模型举例当成事实。');return}
  setBusy(true)
  try{const next=await api<ResearchJob>('/documents/'+taskId,{method:'POST',body:JSON.stringify({...selectedBasis,selection,question,mode,online})});setJob(next);setJobs(old=>[next,...old.filter(x=>x.id!==next.id)]);setPersonal('')}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function saveNote(){if(!job)return;setBusy(true);setError('');try{await api('/notes',{method:'POST',body:JSON.stringify({job_id:job.id,topic_title:topic,personal})});await refreshNotes();setNotice('已保存到专题，来源和你的理解一起保留。')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function saveEdit(){if(!editing)return;setBusy(true);try{await api('/notes/'+editing.id,{method:'PUT',body:JSON.stringify({revision:editing.revision,personal:editText})});await refreshNotes();setEditing(null);setNotice('个人理解已保存。')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{setClaimIds(job?.claims?.map(c=>c.id)||[]);setClaimKinds(Object.fromEntries(job?.claims?.map(c=>[c.id,c.kind])||[]))},[job?.id,job?.claims?.length])
 async function confirmClaims(){if(!job)return;setBusy(true);setError('');try{setJob(await api<ResearchJob>('/jobs/'+job.id+'/confirm',{method:'POST',body:JSON.stringify({claim_ids:claimIds,kinds:Object.fromEntries(claimIds.map(id=>[id,claimKinds[id]]))})}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const pending=!!job&&['queued','running'].includes(job.status)
 return <section className="research-panel" aria-label="段落深入与专题笔记">{(historyLoading||busy)&&<Skeleton label={historyLoading?'正在读取深入记录':'正在处理研究任务'}/>}
  <details className="manual-note-form"><summary>只记自己的理解 · 不调用 AI</summary><p className="research-hint">保存当前选段与来源版本，无需任何 Key。</p><label htmlFor="manual-topic" className="research-label">笔记专题</label><input id="manual-topic" name="manual_topic" autoComplete="off" maxLength={100} value={topic} onChange={e=>setTopic(e.target.value)}/><label htmlFor="manual-note" className="research-label">我的来源笔记</label><textarea id="manual-note" name="manual_note" maxLength={12000} value={manualText} onChange={e=>setManualText(e.target.value)} placeholder="用自己的话记录理解、疑问或下一步…"/><Button disabled={manualBusy||!manualText.trim()||!topic.trim()} onClick={saveManual}><Save size={14} aria-hidden="true"/>保存手动笔记</Button></details>
  {!modelReady&&<p className="research-hint">AI整理与深入需要硅基流动 Key。<button className="text-link" onClick={onSettings}>配置文本模型 Key</button> 手动笔记不受影响。</p>}
  <div className="research-navigation"><Button size="sm" variant={view==='research'?'default':'ghost'} aria-pressed={view==='research'} onClick={()=>setView('research')}><Search size={14} aria-hidden="true"/>深入一下</Button><Button size="sm" variant={view==='notes'?'default':'ghost'} aria-pressed={view==='notes'} onClick={()=>setView('notes')}><BookOpen size={14} aria-hidden="true"/>专题笔记</Button></div>
  {error&&<p className="inline-error" role="alert">{error}</p>}{notice&&<p className="research-notice" role="status">{notice}</p>}
  <div hidden={view!=='notes'}><TopicSearch topics={topics} topicId={filter} onTopic={setFilter} onNotesChanged={refreshNotes} onResearch={id=>{api<ResearchJob>('/jobs/'+id).then(value=>{setJob(value);setJobs(old=>[value,...old.filter(x=>x.id!==value.id)]);setView('research')}).catch(e=>setError(e.message))}}/></div>
  {view==='research'?<>
   <p className="research-intro">选中文章中的一段，带着问题继续读。解释、案例和你的理解都可以留下。</p>
   <label className="research-label" htmlFor="research-selection">本次选段 <small>{selectedBasis.basis==='chapter'?'章节精确原话':selectedBasis.basis==='original'?'识别原稿':selectedBasis.basis==='draft'?'编辑稿':'完整整理稿'}</small></label>
   <textarea id="research-selection" name="research_selection" value={selection} maxLength={4000} rows={4} onChange={e=>setSelection(e.target.value)} placeholder="先在左侧选中文字，再点“深入一下”…"/>
   <label className="research-label" htmlFor="research-question">想弄明白什么？</label><textarea id="research-question" name="research_question" value={question} maxLength={600} rows={2} onChange={e=>setQuestion(e.target.value)} placeholder="例如：这个观点有什么适用条件？"/>
   <fieldset className="research-modes"><legend>这次深入的方向</legend>{[['explain','解释概念'],['cases','找真实案例'],['limits','找局限与反例'],['verify','核实这段说法']].map(([value,label])=><label key={value}><input type="radio" name="research_mode" value={value} checked={mode===value} onChange={()=>{setMode(value);if(value!=='explain')setOnline(true)}}/>{label}</label>)}</fieldset>
   <label className="research-online"><input type="checkbox" checked={online} onChange={e=>setOnline(e.target.checked)}/>联网查找公开资料</label>
   <p className="research-hint">{online?'选段与问题将用于搜索；每次最多3次查询、读取5篇正文。':'不联网时只作AI解释，不能视为已查证事实。'} 未选段时只参考有限的文稿上下文。</p>
   {!searchReady&&<div className="research-key-prompt"><p>联网功能需要单独配置 DeepSeek 官方搜索 Key。</p><Button size="sm" variant="outline" onClick={onSettings}>配置搜索 Key</Button></div>}
   <Button className="research-start" disabled={busy||pending||job?.status==='awaiting_confirmation'} onClick={start}>{pending?<LoaderCircle className="spin" size={15} aria-hidden="true"/>:<Search size={15} aria-hidden="true"/>}{pending?(stageNames[job.stage]||'处理中…'):mode==='verify'?'先拆出核实命题':'开始深入'}</Button>
   {(pending||job?.status==='awaiting_confirmation')&&<Button size="sm" variant="ghost" onClick={async()=>{try{setJob(await api<ResearchJob>('/jobs/'+job.id+'/cancel',{method:'POST'}))}catch(e){setError((e as Error).message)}}}><X size={14} aria-hidden="true"/>取消后续处理</Button>}
   {jobs.length>1&&<label className="research-label">本篇深入记录<select value={job?.id||''} onChange={e=>{setJob(jobs.find(j=>j.id===e.target.value)||null);setPersonal('');setNotice('')}}>{jobs.map(j=><option value={j.id} key={j.id}>{j.question||j.context.selection.slice(0,35)||j.mode} · {j.status==='awaiting_confirmation'?'待确认命题':j.status==='completed'?'已完成':j.status==='failed'?'未完成':j.status==='cancelled'?'已取消':'处理中'}</option>)}</select></label>}
   {job?.status==='awaiting_confirmation'&&<div className="verify-confirm" aria-label="选择待核实命题"><h3>先确认要查哪句话</h3><p className="research-hint">请对照原话检查数字、时间、否定和范围。未选中的命题不查；拆解不准确可取消后缩小选段。</p><fieldset><legend>选择命题（最多3条）</legend>{job.claims?.map(c=><label className="verify-claim" key={c.id}><input type="checkbox" name="verify_claim" value={c.id} checked={claimIds.includes(c.id)} onChange={e=>setClaimIds(old=>e.target.checked?[...old,c.id]:old.filter(id=>id!==c.id))}/><span><strong>{c.statement}</strong><small>{claimKinds[c.id]==='opinion'?'主观判断／建议，不作真假判定':'待核实事实命题'}</small><blockquote>{c.original}</blockquote></span></label>)}{job.claims?.map(c=><label className="research-label" key={'kind-'+c.id}>第{c.id}条如何处理<select name={'verify_kind_'+c.id} value={claimKinds[c.id]||c.kind} onChange={e=>setClaimKinds(old=>({...old,[c.id]:e.target.value}))}><option value="fact">按可检验事实查证</option><option value="opinion">按主观判断保留</option></select></label>)}</fieldset><Button disabled={busy||!claimIds.length} onClick={confirmClaims}>确认所选命题，开始核实</Button></div>}
   {job?.status==='failed'&&<p className="inline-error" role="alert">{job.error}</p>}{job?.status==='cancelled'&&<p className="research-hint">任务已取消，正在进行的远端请求可能仍计费。</p>}
   {job?.status==='completed'&&<div className="research-result"><h3>{job.question||'这段内容的深入理解'}</h3>{job.mode==='manual'&&<p className="research-hint">手动记录 · 未调用AI</p>}<a className="research-origin" href={'/studio/?task='+job.task_id}>查看来源文稿</a><p className="research-hint">以下针对该次选段与文稿版本生成，切换选段不会自动改写已有结果。</p>{job.warnings.map((w,i)=><p className="research-warning" key={i}>{w}</p>)}
    {job.sections?.map((item,i)=><section className="research-answer" key={i}><h4>{item.heading}</h4><p>{item.text}</p><small>{item.support_status==='model_checked'?'附来源摘录 · AI已复核，非人工核实':item.basis==='has_source_excerpt'?'附来源摘录，仍需判断是否支持结论':'AI分析 · 待核实'}</small>{item.support_status==='needs_review'&&<p className="research-warning">来源支持不足：{item.support_note}</p>}{item.citations.map((c,j)=>{const source=job.sources.find(s=>s.id===c.source_id);return <details key={j}><summary>{source?.title||'本次文稿上下文'}</summary>{c.relation&&<p className="research-hint">证据关系：{c.relation==='supports'?'支持':c.relation==='contradicts'?'反驳':'部分支持'}（AI建议）</p>}<blockquote>{c.quote}</blockquote>{source?.url?<a href={source.url} target="_blank" rel="noreferrer">打开原始来源 <ExternalLink size={12} aria-hidden="true"/></a>:<p className="research-hint">来自本次选段上下文，不代表作者观点已被外部验证。</p>}</details>})}</section>)}
    {!!job.open_questions?.length&&<details><summary>尚未解决的问题</summary><ul>{job.open_questions.map((q,i)=><li key={i}>{q}</li>)}</ul></details>}
    {!!job.sources.filter(s=>s.kind==='web').length&&<details className="research-sources"><summary>本次读取的外部来源</summary>{job.sources.filter(s=>s.kind==='web').map(s=><p key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a><small>{s.published_at?'发布：'+s.published_at:''} · 读取：{new Date(s.retrieved_at*1000).toLocaleDateString('zh-CN')}</small></p>)}</details>}
    <div className="research-save"><h4>把这次理解留下</h4><label className="research-label" htmlFor="research-topic">专题名称</label><input id="research-topic" name="research_topic" list="research-topics" autoComplete="off" maxLength={100} value={topic} onChange={e=>setTopic(e.target.value)}/><datalist id="research-topics">{topics.map(t=><option value={t.title} key={t.id}/>)}</datalist><label className="research-label" htmlFor="research-personal">我的理解／对我有什么用</label><textarea id="research-personal" name="research_personal" rows={3} maxLength={12000} value={personal} onChange={e=>setPersonal(e.target.value)} placeholder="用自己的话补充，或记录下一步要验证的事…"/><Button disabled={busy||!topic.trim()} onClick={saveNote}><Save size={14} aria-hidden="true"/>保存到专题</Button><p className="research-hint">保存表示留存，不等于已核实；不会写入左侧文稿。</p></div>
   </div>}
  </>:<div className="research-notes"><h3>专题笔记</h3><p className="research-hint">显示最近200条笔记，导出会保留来源与未决问题。</p><label className="research-label" htmlFor="research-filter">查看专题</label><select id="research-filter" name="research_filter" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">全部专题</option>{topics.map(t=><option key={t.id} value={t.id}>{t.title}（{t.notes_count}）</option>)}</select>{notes.filter(n=>!filter||n.topic_id===filter).map(n=><section key={n.id} className="research-note"><h4>{n.topic_title}</h4><p>{n.personal||'尚未补充自己的理解。'}</p><div><Button size="sm" variant="outline" onClick={async()=>{try{const value=await api<ResearchJob>('/jobs/'+n.job_id);setJob(value);setJobs(old=>[value,...old.filter(x=>x.id!==value.id)]);setView('research')}catch(e){setError((e as Error).message)}}}>回看结果与来源</Button><a href={'/api/studio/research/notes/'+n.id+'/export'}>导出 Markdown</a><Button size="sm" variant="ghost" onClick={()=>{setEditing(n);setEditText(n.personal)}}>补充理解</Button></div>{editing?.id===n.id&&<div><label className="research-label" htmlFor={'note-edit-'+n.id}>修改自己的理解</label><textarea id={'note-edit-'+n.id} maxLength={12000} rows={4} value={editText} onChange={e=>setEditText(e.target.value)}/><Button size="sm" disabled={busy} onClick={saveEdit}>保存理解</Button><Button size="sm" variant="ghost" onClick={()=>setEditing(null)}>取消</Button></div>}</section>)}{!notes.length&&<p className="research-intro">把一次有用的深入保存下来，来源和自己的理解会一起出现在这里。</p>}</div>}
 </section>
}
