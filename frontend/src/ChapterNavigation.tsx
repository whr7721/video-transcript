import {Skeleton} from './Motion'
import React, {useEffect, useRef, useState} from 'react'
import type {Passage} from './ResearchPanel'
type Section={review_required?:boolean;evidence?:{fragment_id:string;quote:string;status?:string}[];title:string;guide?:string;fragment_ids:string[];kind:string}
type Plan={revision:number;source_hash:string;fragment_limit:number;origin:string;stale:boolean;warning?:string;sections:Section[]}
type Range={source_id:string;start_offset:number;end_offset:number;text:string}
type Job={id:string;action:string;status:string;index?:number;base_revision:number;plan?:Plan;content?:{content?:{type:string;content?:{text?:string}[]}[]};uncertainties?:{original:string;suggestion:string;reason:string}[];ranges?:Range[];error?:string;completed_windows?:number;total_windows?:number}
type Budget={max_calls:number;cached_windows:number;quota:{remaining:number|null}}
async function request<T>(url:string,init?:RequestInit):Promise<T>{const response=await fetch(url,init);const body=await response.json();if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'章节请求失败');return body}
const post=(body:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
export default function ChapterNavigation({taskId,onLocate,onResearch,documentRevision=1}:{taskId:string;onLocate:(range:Range)=>void;onResearch?:(passage:Passage)=>void;documentRevision?:number}){
 const [plan,setPlan]=useState<Plan|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[chosen,setChosen]=useState<number|null>(null),[ranges,setRanges]=useState<Range[]>([])
 const [job,setJob]=useState<Job|null>(null),[jobs,setJobs]=useState<Job[]>([]),[budget,setBudget]=useState<Budget|null>(null),[action,setAction]=useState<'directory'|'clean'>('directory')
 const [rename,setRename]=useState(''),[splitAt,setSplitAt]=useState(''),[editNotice,setEditNotice]=useState('')
 const [readingChapter,setReadingChapter]=useState<number|null>(null)
 const alive=useRef(true),excerpt=useRef<HTMLDivElement>(null),selectionRequest=useRef(0)
 const base=`/api/studio/documents/${taskId}`
 useEffect(()=>{let stopped=false;alive.current=true
 request<Plan>(`${base}/chapters`).then(v=>{if(!stopped)setPlan(v)}).catch(e=>{if(!stopped)setError(e.message)})
 request<Job[]>(`${base}/chapter-jobs`).then(v=>{if(!stopped&&Array.isArray(v)){setJobs(v);setJob(v.find(j=>['queued','running'].includes(j.status))||v[0]||null)}}).catch(()=>{})
 return()=>{stopped=true;alive.current=false}
 },[base])
 useEffect(()=>{if(!job||!['queued','running'].includes(job.status))return;let stopped=false
 const timer=setInterval(()=>request<Job>(`${base}/chapter-jobs/${job.id}`).then(v=>{if(!stopped){setJob(v);setJobs(old=>[v,...old.filter(j=>j.id!==v.id)])}}).catch(e=>{if(!stopped)setError(e.message)}),1500)
 return()=>{stopped=true;clearInterval(timer)}
 },[base,job?.id,job?.status])
 useEffect(()=>{const root=document.querySelector('.paper-scroll');if(!root||!plan?.sections.length||typeof IntersectionObserver==='undefined')return;const visible=new Map<Element,number>();const sections=plan.sections;const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.set(entry.target,entry.boundingClientRect.top);else visible.delete(entry.target)}const element=[...visible].sort((a,b)=>a[1]-b[1])[0]?.[0];if(!element)return;const id=element.id.replace('source-','');const index=sections.findIndex(section=>section.fragment_ids.some(fragment=>fragment===id||fragment.startsWith(id+':')));if(index>=0)setReadingChapter(index)}, {root,rootMargin:'-2% 0px -65% 0px',threshold:0});root.querySelectorAll('[id^="source-"]').forEach(el=>observer.observe(el));return()=>observer.disconnect()},[plan,taskId])
 async function perform(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn()}catch(e){if(alive.current)setError((e as Error).message)}finally{if(alive.current)setBusy(false)}}
 async function persist(official=false,updated=plan){if(!updated)return
 await perform(async()=>{const value=await request<Plan>(`${base}/${official?'official-chapters':'chapters'}`,post({revision:updated.revision,plan:updated}));if(!alive.current)return;setPlan(value);setChosen(null);setRanges([]);setBudget(null);setEditNotice('已保存新目录版本，历史笔记仍引用原版本。')})}
 async function choose(index:number){const seq=++selectionRequest.current;setBudget(null)
 await perform(async()=>{const value=await request<{ranges:Range[]}>(`${base}/chapters/${index}/text`);if(!alive.current||seq!==selectionRequest.current)return;setChosen(index);setRename(plan?.sections[index].title||'');setSplitAt('');setRanges(value.ranges);if(value.ranges[0])onLocate(value.ranges[0])})}
 async function estimate(next:'directory'|'clean'){if(!plan)return;setAction(next)
 await perform(async()=>{const v=await request<Budget>(`${base}/chapter-estimate`,post({action:next,revision:plan.revision,index:chosen??0}));if(alive.current)setBudget(v)})}
 async function start(next=action,revision=plan?.revision,index=chosen??0){await perform(async()=>{const v=await request<Job>(`${base}/chapter-jobs`,post({action:next,revision,index}));if(alive.current){setJob(v);setBudget(null);setJobs(old=>[v,...old.filter(j=>j.id!==v.id)])}})}
 async function apply(){if(!plan||!job)return;await perform(async()=>{const value=await request<Plan>(`${base}/chapter-jobs/${job.id}/apply`,post({revision:plan.revision}));if(alive.current){setPlan(value);setChosen(null);setRanges([]);setEditNotice('AI目录已采用为新版本，原稿未改动。')}})}
 function edit(kind:'rename'|'split'|'merge'){if(!plan||chosen===null)return;const updated=structuredClone(plan);const s=updated.sections[chosen]
 if(kind==='rename')s.title=rename
 if(kind==='split'){const pos=s.fragment_ids.indexOf(splitAt);if(pos<=0)return;updated.sections.splice(chosen,1,{title:s.title+'（前段）',kind:'manual',fragment_ids:s.fragment_ids.slice(0,pos)},{title:s.title+'（后段）',kind:'manual',fragment_ids:s.fragment_ids.slice(pos)})}
 if(kind==='merge'){const next=updated.sections[chosen+1];if(!next)return;updated.sections.splice(chosen,2,{title:s.title,kind:'manual',fragment_ids:[...s.fragment_ids,...next.fragment_ids]})}
 updated.origin='manual';persist(false,updated)
 }
 function researchSelection(){if(!plan||chosen===null||!onResearch)return
 const body=ranges.map(r=>r.text).join('');let start=0,text=Array.from(body).slice(0,4000).join('')
 const selected=window.getSelection()
 if(selected?.rangeCount&&excerpt.current?.contains(selected.anchorNode)&&excerpt.current.contains(selected.focusNode)){
 const range=selected.getRangeAt(0);const prefix=range.cloneRange();prefix.selectNodeContents(excerpt.current);prefix.setEnd(range.startContainer,range.startOffset)
 start=Array.from(prefix.toString()).length;text=range.toString()
 }
 const leading=text.length-text.trimStart().length;start+=Array.from(text.slice(0,leading)).length;text=text.trim()
 if(!text||text.length>4000){setError('请选择4000字以内原话');return}
 onResearch({taskId,basis:'chapter',revision:documentRevision,chapter_revision:plan.revision,chapter_index:chosen,selection_start:start,selection:text})
 }
 const active=!!job&&['queued','running'].includes(job.status)
 const cleaned=jobs.find(j=>j.status==='completed'&&j.action==='clean'&&JSON.stringify(j.ranges)===JSON.stringify(ranges))
 return <details className="chapter-navigation"><summary>章节与导读 <small>按需生成，原稿保留</small></summary>
 {error&&<p role="alert">{error}</p>}{editNotice&&<p role="status">{editNotice}</p>}
 {!plan&&!error&&<Skeleton label="正在读取目录"/>}
 {plan&&<>{plan.stale?<p role="alert">目录对应旧原稿，请生成新目录；已有笔记未改动。</p>:<>
 <p className="muted-note">{plan.origin==='ai'?'AI语义章节 · 导读待核对':plan.origin==='official'?'节目官方目录 · 时间近似映射':plan.origin==='manual'?'人工修订目录':'本地阅读分段 · 按长度划分，不代表话题章节'} · {plan.revision?`版本 ${plan.revision}`:'尚未保存'}</p>
 <nav aria-label="原文阅读目录"><ol>{plan.sections.map((s,i)=><li key={i}><button disabled={busy} aria-current={(readingChapter??chosen)===i?'location':undefined} data-selected={chosen===i||undefined} onClick={()=>choose(i)}>{s.title}</button>{s.guide&&<p className="chapter-guide">{s.guide}{s.review_required&&<small>（回查原话未精确匹配；仅定位原文，导读需核对）</small>}</p>}</li>)}</ol></nav>
 {plan.warning&&<p>{plan.warning}</p>}
 <div className="chapter-actions"><button disabled={busy||plan.revision>0} onClick={()=>persist()}>保存阅读目录</button><button disabled={busy||active} onClick={()=>persist(true)}>加载节目官方目录</button><a href={`${base}/chapters/export/md`}>导出目录与整理稿</a></div>
 {chosen!==null&&<section className="chapter-excerpt" aria-label="所选章节精确原文"><h3>{plan.sections[chosen]?.title}</h3>
 <details><summary>查看导读的原文位置 · 不等于已验证语义支持</summary>{plan.sections[chosen]?.evidence?.map((e,i)=><blockquote key={i}>{e.quote}<small> {e.fragment_id} · {e.status==='location_only'?'程序提取的位置参考':'原话匹配'}</small></blockquote>)}</details><div className="chapter-actions"><button disabled={busy||!plan.revision||active} onClick={()=>estimate('clean')}>整理这一章</button><button disabled={!plan.revision||!onResearch} onClick={researchSelection}>研究本章原话</button></div>
 <details><summary>调整章节范围</summary><label>章节名称<input name="chapter_title" maxLength={200} value={rename} onChange={e=>setRename(e.target.value)}/></label><button disabled={busy||!rename.trim()} onClick={()=>edit('rename')}>保存名称</button><label>从哪个原文片段开始拆成下一章<select value={splitAt} onChange={e=>setSplitAt(e.target.value)}><option value="">选择拆分位置</option>{ranges.slice(1).map((r,i)=><option key={i} value={`${r.source_id}:${r.start_offset}:${r.end_offset}`}>{r.text.slice(0,36)}</option>)}</select></label><button disabled={busy||!splitAt} onClick={()=>edit('split')}>拆分并保存</button><button disabled={busy||chosen>=plan.sections.length-1} onClick={()=>edit('merge')}>与下一章合并</button><p>拆分或合并后清除对应旧导读，原稿与历史笔记不变。</p></details>
 {cleaned?.content&&<details open><summary>本章整理预览 · 未写入编辑稿</summary>{cleaned.content.content?.map((n,i)=>n.type==='heading'?<h4 key={i}>{n.content?.map(t=>t.text).join('')}</h4>:<p key={i}>{n.content?.map(t=>t.text).join('')}</p>)}{!!cleaned.uncertainties?.length&&<details><summary>待回听的疑词</summary>{cleaned.uncertainties.map((u,i)=><p key={i}>{u.original}：{u.suggestion}（{u.reason}）</p>)}</details>}</details>}
 <p className="muted-note">原话证据（可选择其中一段后研究；未选择则取开头最多4000字）</p><div ref={excerpt}>{ranges.map((r,i)=><span key={i} style={{whiteSpace:'pre-wrap'}}>{r.text}</span>)}</div></section>}
 </>}
 <div className="chapter-actions"><button disabled={busy||active} onClick={()=>estimate('directory')}>生成 AI 章节导读</button></div>
 {budget&&<div role="status"><p>本次最多 {budget.max_calls} 次请求，复用 {budget.cached_windows} 个窗口；今日剩余 {budget.quota.remaining??'不限'} 次。发送原稿至已配置文本模型，按平台计费。</p><button disabled={busy||active} onClick={()=>start()}>确认生成{action==='directory'?'章节导读':'本章整理'}</button><button onClick={()=>setBudget(null)}>暂不生成</button></div>}
 {job&&<section aria-label="章节生成任务"><p role="status">{job.action==='directory'?'章节导读':'按章整理'}：{({queued:'等待处理',running:'处理中',paused:'已暂停',completed:'结果已保存',cancelled:'已取消'} as Record<string,string>)[job.status]||job.status} {job.completed_windows??0}/{job.total_windows??0} 窗</p>{job.error&&<p role="alert">{job.error}</p>}
 {active&&<button onClick={()=>perform(async()=>{const value=await request<Job>(`${base}/chapter-jobs/${job.id}/cancel`,post({}));setJob(value)})}>取消后续调用</button>}
 {['paused','cancelled'].includes(job.status)&&<button disabled={busy} onClick={()=>start(job.action as 'directory'|'clean',job.base_revision,job.index??0)}>恢复未完成步骤</button>}
 {job.status==='completed'&&job.plan&&<><details><summary>预览生成目录</summary>{job.plan.sections.map((s,i)=><div key={i}><h4>{s.title}</h4><p>{s.guide}</p></div>)}</details><button disabled={busy} onClick={apply}>采用为新目录版本</button></>}
 </section>}
 </>}
 </details>
}
