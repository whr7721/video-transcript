import {useEffect,useRef,useState} from 'react';
import type {Markmap} from 'markmap-view';
import type {Tree} from '../worker/validation';
import {download} from './download';
export const escapeHtml=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
function data(t:Tree):any{return{content:escapeHtml(t.text),children:t.children.map(data)}}
function Outline({node}:{node:Tree}){return <li>{node.text}{node.children.length>0&&<ul>{node.children.map((c,i)=><Outline node={c} key={i}/>)}</ul>}</li>}
export function offlineHtml(root:Tree,title:string){
 // Offline HTML has a semantic tree and native fold controls, without CDN or executable model text.
 function tree(t:Tree):string{return t.children.length?`<li><details open><summary>${escapeHtml(t.text)}</summary><ul>${t.children.map(tree).join('')}</ul></details></li>`:`<li>${escapeHtml(t.text)}</li>`}
 return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>${escapeHtml(title)}</title><style>body{font:17px/1.8 system-ui,sans-serif;color:#1e3553;margin:40px auto;padding:0 24px;max-width:1000px}ul{padding-left:24px}li{margin:12px 0}summary{cursor:pointer;color:#175bd5}details>ul{border-left:2px solid #dae5f6}small{color:#62728a}</style></head><body><h1>${escapeHtml(title)}</h1><small>拾文思维导图 · 点击分支可折叠 · AI归纳，请对照原文核实</small><ul>${tree(root)}</ul></body></html>`;
}
export default function Map({root,title}:{root:Tree;title:string}){
 const svg=useRef<SVGSVGElement>(null),map=useRef<Markmap|null>(null),[error,setError]=useState('');
 useEffect(()=>{let stopped=false;import('markmap-view').then(async({Markmap})=>{
  if(stopped||!svg.current)return;const m=Markmap.create(svg.current,{duration:0,maxWidth:200,initialExpandLevel:2,autoFit:true},data(root));map.current=m;
  try{await m.fit()}catch{if(!stopped)setError('图形暂不可用，请阅读下方文字大纲。')}
 }).catch(()=>setError('图形加载失败，请阅读文字大纲。'));return()=>{stopped=true;map.current?.destroy();map.current=null}},[root]);
 return <section className="map-section" aria-label="思维导图"><div className="map-tools"><button onClick={()=>void map.current?.rescale(1.3)} aria-label="放大导图">＋</button><button onClick={()=>void map.current?.rescale(0.77)} aria-label="缩小导图">−</button><button onClick={()=>void map.current?.fit()}>适应画布</button><button onClick={()=>download(offlineHtml(root,title),'text/html;charset=utf-8','拾文导图.html')}>导出 HTML</button></div>{error&&<p role="alert">{error}</p>}<svg ref={svg} role="img" aria-label={title+'思维导图，可拖拽缩放'}/><details><summary>阅读文字大纲</summary><ul><Outline node={root}/></ul></details></section>;
}
