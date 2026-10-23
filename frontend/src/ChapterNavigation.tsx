import React, {useEffect, useRef, useState} from 'react'

type Plan = {revision:number;source_hash:string;fragment_limit:number;origin:string;stale:boolean;warning?:string;sections:{title:string;fragment_ids:string[];kind:string}[]}
type Range = {source_id:string;start_offset:number;end_offset:number;text:string}
async function request<T>(url:string,init?:RequestInit):Promise<T>{
 const response=await fetch(url,init);const body=await response.json()
 if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'章节请求失败')
 return body
}
export default function ChapterNavigation({taskId,onLocate}:{taskId:string;onLocate:(range:Range)=>void}){
 const [plan,setPlan]=useState<Plan|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const [chosen,setChosen]=useState<number|null>(null),[ranges,setRanges]=useState<Range[]>([])
 const alive=useRef(true)
 const base=`/api/studio/documents/${taskId}`
 useEffect(()=>{let stopped=false;alive.current=true;setPlan(null);setError('');setChosen(null);setRanges([])
 request<Plan>(`${base}/chapters`).then(v=>{if(!stopped)setPlan(v)}).catch(e=>{if(!stopped)setError(e.message)})
 return()=>{stopped=true;alive.current=false}
 },[base])
 async function persist(official=false){if(!plan)return;setBusy(true);setError('')
 try{const value=await request<Plan>(`${base}/${official?'official-chapters':'chapters'}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:plan.revision,plan})});setPlan(value);setChosen(null);setRanges([])}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function choose(index:number){setBusy(true);setError('')
 try{const value=await request<{ranges:Range[]}>(`${base}/chapters/${index}/text`);if(!alive.current)return;setChosen(index);setRanges(value.ranges);if(value.ranges[0])onLocate(value.ranges[0])}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <details className="chapter-navigation"><summary>阅读目录 <small>不调用 AI</small></summary>
 <p className="muted-note">按原文范围导航。阅读分段按长度划分，不代表话题章节。</p>
 {error&&<p role="alert">{error}</p>}
 {!plan&&!error&&<p role="status">正在读取目录…</p>}
 {plan&&<>{plan.stale?<p role="alert">目录对应旧原稿，暂停定位。请重新生成目录。</p>:<>
 <nav aria-label="原文阅读目录"><ol>{plan.sections.map((s,i)=><li key={i}><button disabled={busy} aria-current={chosen===i?'location':undefined} onClick={()=>choose(i)}>{s.title}</button></li>)}</ol></nav>
 <div className="chapter-actions"><button disabled={busy||plan.revision>0} onClick={()=>persist()}>保存阅读目录</button><button disabled={busy} onClick={()=>persist(true)}>加载节目官方目录</button></div>
 <p className="muted-note">{plan.origin==='official'?'节目官方目录 · 时间为近似映射':'本地阅读分段'} · {plan.revision?`已保存版本 ${plan.revision}`:'尚未保存'}。官方目录只在点击后联网获取。</p>
 {plan.warning&&<p>{plan.warning}</p>}
 {chosen!==null&&<section className="chapter-excerpt" aria-label="所选章节精确原文"><h3>{plan.sections[chosen]?.title}</h3><p className="muted-note">以下是此范围的原话，尚未整理。</p>{ranges.map((r,i)=><p key={i} style={{whiteSpace:'pre-wrap'}}>{r.text}</p>)}</section>}
 </>}</>}
 </details>
}
