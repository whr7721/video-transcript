import {useEffect,useRef,useState} from 'react'
import type {Markmap} from 'markmap-view'
import {Button} from '@/components/ui/button'
import {Dialog,DialogClose,DialogContent,DialogDescription,DialogHeader,DialogTitle} from '@/components/ui/dialog'
import {createMap,downloadBlob,mapData,mindmapPng,type MindmapNode} from './mindmap-render'
import './mindmap.css'
export type MindmapJob={id:string;status:string;error?:string;mindmap?:MindmapNode;source_hash?:string}
function Outline({node}:{node:MindmapNode}){return <li>{node.text}{node.children.length>0&&<ul>{node.children.map((child,i)=><Outline key={i} node={child}/>)}</ul>}</li>}
function Canvas({root}:{root:MindmapNode}){
 const svg=useRef<SVGSVGElement>(null),map=useRef<Markmap|undefined>(undefined),[ready,setReady]=useState(false),[error,setError]=useState('')
 useEffect(()=>{let stopped=false;setReady(false);setError('')
  createMap(svg.current!,root,2).then(value=>{if(stopped)value.destroy();else{map.current=value;setReady(true)}}).catch(()=>{if(!stopped)setError('导图显示未完成，可先查看下方文字大纲。')})
  return()=>{stopped=true;map.current?.destroy();map.current=undefined}
 },[root])
 async function fold(level:number){if(map.current){await map.current.setData(mapData(root),{initialExpandLevel:level});await map.current.fit()}}
 return <><div className="mindmap-tools" role="group" aria-label="导图查看工具">
  <Button size="sm" variant="outline" disabled={!ready} onClick={()=>map.current?.rescale(1.25)}>放大</Button>
  <Button size="sm" variant="outline" disabled={!ready} onClick={()=>map.current?.rescale(.8)}>缩小</Button>
  <Button size="sm" variant="outline" disabled={!ready} onClick={()=>map.current?.fit()}>适应窗口</Button>
  <Button size="sm" variant="outline" disabled={!ready} onClick={()=>fold(-1)}>展开全部</Button>
  <Button size="sm" variant="outline" disabled={!ready} onClick={()=>fold(1)}>收起分支</Button>
 </div>{error&&<p role="alert">{error}</p>}<svg ref={svg} className="mindmap-canvas" role="img" aria-label={`${root.text}思维导图，文字内容见下方大纲`} tabIndex={0}
 onKeyDown={e=>{if(e.key==='+'||e.key==='='){e.preventDefault();map.current?.rescale(1.25)}if(e.key==='-'){e.preventDefault();map.current?.rescale(.8)}if(e.key==='0'){e.preventDefault();map.current?.fit()}}}/></>
}
export default function Mindmap({jobs,blocked,sourceHash,busy,onGenerate,notify}:{jobs:MindmapJob[];blocked?:string;sourceHash?:string;busy:boolean;onGenerate:()=>void;notify:(text:string)=>void}){
 const [large,setLarge]=useState(false),[exporting,setExporting]=useState(false)
 const working=jobs.some(job=>['queued','running'].includes(job.status)),latest=jobs[0],success=jobs.find(job=>job.status==='completed'&&job.mindmap),root=success?.mindmap
 const stale=!!(success?.source_hash&&sourceHash&&success.source_hash!==sourceHash)
 async function png(){if(!root)return;setExporting(true);try{downloadBlob(await mindmapPng(root),'拾文-思维导图.png');notify('已导出完整展开的导图图片')}catch(e){notify((e as Error).message)}finally{setExporting(false)}}
 return <section className="mindmap-panel" aria-label="思维导图" aria-busy={working||busy}>
  <header className="mindmap-heading"><div><h2>{root?.text||'先看清这份内容的结构'}</h2><p>基于原稿概括，允许改写；不代替完整阅读和事实核实。</p></div>
  {(!root||stale)&&<Button disabled={busy||working||!!blocked} onClick={onGenerate}>{working?'正在生成…':stale?'根据当前原稿生成':'生成思维导图'}</Button>}
  </header>
  {blocked&&<p className="inline-error">{blocked}</p>}
  {stale&&<p className="inline-error">原稿已有更新，当前显示此前生成的导图。</p>}
  {working&&<p role="status">正在通读原稿并归纳结构，可以切换文稿，稍后回来查看。</p>}
  {latest?.status==='failed'&&<div className="mindmap-retry"><p role="alert">{latest.error||'导图未完成，原稿和已有结果保留。'}</p><Button variant="outline" disabled={busy||working||!!blocked} onClick={onGenerate}>重试生成</Button></div>}
  {root&&<><Canvas key={success!.id} root={root}/><div className="mindmap-tools"><Button variant="outline" onClick={()=>setLarge(true)}>放大查看</Button><Button variant="outline" disabled={exporting} onClick={png}>{exporting?'正在导出…':'导出 PNG'}</Button><a className="mindmap-download" href={`/api/studio/generations/${success!.id}/mindmap.md`}>下载 Markdown 大纲</a><a className="mindmap-download" href={`/api/studio/generations/${success!.id}/mindmap.xmind`}>导出 XMind</a></div>
   <p className="mindmap-help">拖动空白处移动，滚轮缩放，点击分支圆点折叠；键盘 + / − 缩放，0 适应窗口。</p>
   <details className="mindmap-outline"><summary>查看文字大纲</summary><ul><Outline node={root}/></ul></details>
   <Dialog open={large} onOpenChange={setLarge}><DialogContent className="mindmap-dialog" showCloseButton={false}><DialogHeader><DialogTitle>{root.text}</DialogTitle><DialogDescription>拖动与缩放查看分支；按 Esc 关闭大图。</DialogDescription><DialogClose asChild><Button variant="outline">关闭大图</Button></DialogClose></DialogHeader>{large&&<Canvas root={root}/>}</DialogContent></Dialog>
  </>}
 </section>
}
