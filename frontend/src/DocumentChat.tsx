import {useEffect,useRef,useState} from 'react'
type Citation={block_id:string;offset:number;quote:string;start?:number;end?:number}
type Turn={id:string;question:string;status:string;error?:string;coverage?:string;answer?:{text:string;unknown:boolean;sections:{text:string;citations:Citation[]}[]}}
const stamp=(s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`
export default function DocumentChat({taskId,onCitation}:{taskId:string;onCitation:(id:string)=>void}){
 const [turns,setTurns]=useState<Turn[]>([]),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const active=useRef(taskId),token=useRef(0)
 useEffect(()=>{active.current=taskId;const n=++token.current;setTurns([]);setQuestion('');setBusy(false);setError('');let alive=true
  fetch('/api/document-chat/'+taskId).then(async r=>{const v=await r.json();if(!r.ok)throw Error(v.detail||'无法读取追问历史');if(alive&&token.current===n)setTurns(Array.isArray(v)?v:[])}).catch(e=>{if(alive)setError(e.message)})
  return()=>{alive=false;token.current++}
 },[taskId])
 async function ask(turn?:Turn){const text=turn?.question||question.trim();if(!text||busy)return;const id=turn?.id||crypto.randomUUID();const document=taskId,n=token.current;setBusy(true);setError('')
  setTurns(old=>turn?old.map(v=>v.id===id?{...v,status:'running'}:v):[...old,{id,question:text,status:'running'}]);setQuestion('')
  try{const r=await fetch('/api/document-chat/'+document,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,question:text,retry:!!turn})});const v=await r.json();if(!r.ok)throw Error(v.detail||'追问未完成');if(active.current===document&&n===token.current)setTurns(old=>old.map(t=>t.id===id?v:t))}
  catch(e){if(active.current===document&&n===token.current){setError((e as Error).message);setTurns(old=>old.map(t=>t.id===id?{...t,status:'failed',error:'连接中断，可点击“检查状态”读取已保存结果；重试不会覆盖原稿。'}:t))}}
  finally{if(active.current===document&&n===token.current)setBusy(false)}
 }
 async function refresh(){try{const r=await fetch('/api/document-chat/'+taskId);const v=await r.json();if(!r.ok)throw Error(v.detail||'读取失败');if(active.current===taskId)setTurns(Array.isArray(v)?v:[])}catch(e){setError((e as Error).message)}}
 return <section className="document-chat" aria-label="文档 AI 追问"><h3>向这篇文稿追问</h3><p className="muted-note">仅检索本篇原文与摘要。每次有依据的模型回答消耗一次共享请求；无依据会明确说明不知道。引用可回到原文核对。</p><button type="button" disabled={busy} onClick={()=>void refresh()}>检查状态</button><div role="log" aria-label="追问消息" aria-live="polite">{turns.map(t=><article key={t.id}><p className="chat-question">你：{t.question}</p>{t.status==='running'?<p role="status">正在检索本篇并回答…</p>:t.status==='failed'?<><p role="alert">{t.error}</p><button disabled={busy} onClick={()=>void ask(t)}>重试本条追问</button></>:<><p className="small-label">AI 回答 · 请核对引用含义</p>{t.answer?.unknown?<p>{t.answer.text}</p>:t.answer?.sections.map((s,i)=><div key={i}><p>{s.text}</p>{s.citations.map((c,j)=><button className="chat-citation" key={j} onClick={()=>onCitation(c.block_id)}><span>{c.block_id} · {c.start==null?`段内位置 ${c.offset}`:stamp(c.start)}</span><q>{c.quote}</q></button>)}</div>)}<small>{t.coverage}</small></>}</article>)}</div><form onSubmit={e=>{e.preventDefault();void ask()}}><label htmlFor={'chat-question-'+taskId}>关于这篇的问题</label><textarea id={'chat-question-'+taskId} value={question} onChange={e=>setQuestion(e.target.value)} maxLength={1000} rows={3} placeholder="作者为什么这样建议？原文有哪些依据？"/><button disabled={busy||!question.trim()||turns.some(t=>t.status==='running')}>发送追问</button></form>{error&&<p role="alert">{error}</p>}</section>
}
