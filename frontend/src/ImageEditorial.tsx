import {useState} from 'react'
import {Button} from '@/components/ui/button'
type Content={content:{type:string;content?:{text?:string}[]}[]}
export type Editorial={status:string;content?:Content;essence_content?:Content;error?:string;essence_error?:string;model?:string;source_pages?:number;stale?:boolean;uncertainties?:{original:string;suggestion:string;reason:string}[]}
export default function ImageEditorial({id,value,mode,onUpdate,onSource,notify}:{id:string;value?:Editorial;mode:'article'|'essence';onUpdate:(v:any)=>void;onSource:()=>void;notify:(text:string)=>void}){
 const [busy,setBusy]=useState(false)
 const working=['queued','running'].includes(value?.status||'')
 async function generate(){setBusy(true);try{const r=await fetch(`/api/library/image-items/${id}/editorial`,{method:'POST'});const v=await r.json();if(!r.ok)throw Error(v.detail||'整理暂未完成');onUpdate(v)}catch(e){notify((e as Error).message)}finally{setBusy(false)}}
 const body=mode==='essence'?value?.essence_content:value?.content
 async function copy(){try{if(body)await navigator.clipboard.writeText(body.content.map(n=>n.content?.map(t=>t.text||'').join('')||'').join('\n\n'));notify('已复制当前阅读稿')}catch{notify('复制未成功，可使用导出整理稿')}}
 return <section className="image-editorial" aria-label={mode==='essence'?'AI精华':'AI完整整理稿'}>
  <div className="editorial-caption"><p>{value?.content?`根据整份${value.source_pages||''}页识别稿整理 · AI可改写表达`:'把整份图集，整理成一篇可以顺畅阅读的文章。'}</p>{value?.content&&<span>{body&&<button className="article-locate" onClick={copy}>复制正文</button>} <a href={`/api/library/image-items/${id}/editorial/export`}>导出整理稿</a></span>}</div>
  {value?.stale&&<p className="article-error">OCR原文已有更新，当前是旧阅读稿。可重新生成，原稿仍保留。</p>}
  {body?<div className="editorial-prose">{body.content.map((node,index)=>{const text=node.content?.map(n=>n.text||'').join('')||'';return node.type==='heading'?<h3 key={index}>{text}</h3>:<p key={index}>{text}</p>})}</div>:<div className="editorial-empty"><h3>{mode==='essence'?'先有完整整理稿，再看精华。':'不用逐页拼文字，直接阅读整理稿。'}</h3><p>DeepSeek将一次读取全部OCR文字，合并同主题内容、去掉界面杂讯，保留主要信息与例子。原图和识别稿另外保留。</p></div>}
  {working&&<p role="status">{value?.content?'完整稿已保存，正在生成精华…':'正在通读整份资料并整理，长图集可能需要几分钟。可以离开页面，稍后回来。'}</p>}
  {(value?.error||value?.essence_error)&&<p role="alert" className="article-error">{value.error||value.essence_error}</p>}
  {(!value?.content||value.status==='failed'||value.stale||value.essence_error)&&<Button disabled={busy||working} onClick={generate}>{working?'正在整理…':value?.content?'重试未完成的整理':'生成完整整理稿与精华'}</Button>}
  <p className="article-help">AI整理稿允许改写，不代表原文已核实。术语、数字与图解有疑问时，<button className="article-locate" onClick={onSource}>查看原图与识别稿</button>。</p>
  {!!value?.uncertainties?.length&&<details><summary>有 {value.uncertainties.length} 处文字建议核对</summary>{value.uncertainties.map((d,i)=><p key={i}>{d.original}：{d.suggestion}。{d.reason}</p>)}</details>}
 </section>
}
