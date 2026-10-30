/** Explicit, in-memory design fixtures. Never activate because a real request failed. */
import {demoDocument,demoLibraryItems,demoLibraryStats,demoTasks} from './demo-data'
const enabled=typeof location!=='undefined'&&new URLSearchParams(location.search).get('preview')==='1'
export function isDesignPreview(){return enabled}
export function previewHref(path:string){if(!enabled)return path;const url=new URL(path,location.origin);url.searchParams.set('preview','1');return url.pathname+url.search+url.hash}
export function installDesignPreview(){
 if(!enabled)return
 const original=window.fetch.bind(window)
 window.fetch=async(input:RequestInfo|URL,init?:RequestInit)=>{
  const url=new URL(typeof input==='string'?input:input instanceof URL?input.toString():input.url,location.origin)
  if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return original(input,init)
  const method=(init?.method||(input instanceof Request?input.method:'GET')).toUpperCase()
  const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
  if(method!=='GET')return response({detail:'当前为只读设计预览，请在本地工作台执行此操作。'},409)
  const path=url.pathname
  if(path==='/api/tasks')return response(demoTasks)
  if(path==='/api/link/capabilities')return response({platforms:['youtube','bilibili','douyin','rss','xiaohongshu','xiaoyuzhou','tiktok','twitter','spotify'],summarize:true})
  if(path==='/api/library'){
   const q=url.searchParams.get('q')||'',starred=url.searchParams.get('starred')==='true'
   return response({items:demoLibraryItems.filter(r=>(!starred||r.starred)&&(!q||(r.title+r.snippet).includes(q))),stats:demoLibraryStats,channels:[]})
  }
  if(path==='/api/library/collections')return response([])
  if(path==='/api/studio/buffer')return response({capacity_bytes:5e9,used_bytes:0,reclaimable_bytes:0,waiting:0})
  if(path==='/api/settings')return response({provider:'local',key_configured:false,search_key_configured:false})
  if(path.endsWith('/status'))return response({status:'not_logged_in'})
  const doc=path.match(/^\/api\/studio\/documents\/(demo:[1-6])$/)
  if(doc)return response(demoDocument(doc[1]))
  if(path.endsWith('/chapters'))return response({revision:0,kind:'reading',sections:[],warnings:[]})
  if(path.endsWith('/media-status'))return response({audio_available:false,video_available:false})
  if(path.endsWith('/chat'))return response({messages:[]})
  return response([])
 }
 document.documentElement.classList.add('is-design-preview')
 document.addEventListener('click',event=>{
  const a=(event.target as HTMLElement).closest('a[href]') as HTMLAnchorElement|null
  if(!a)return
  const url=new URL(a.href,location.origin)
  if(url.origin===location.origin&&url.pathname.startsWith('/studio/')){url.searchParams.set('preview','1');a.href=url.toString()}
 })
}
