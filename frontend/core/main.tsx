/// <reference types="vite/client" />
import React from 'react'
import {createRoot} from 'react-dom/client'
import {App} from '../src/Studio'
import ArticleLibrary from '../src/ArticleLibrary'
import TopicLibrary from '../src/TopicLibrary'
import type {SourceUI} from '../src/source-ui'
import {FileTaskActions} from './FileCapture'
import Capture from './Capture'

const sourceUI:SourceUI={
 empty:'这里将保存你的音视频与播客文稿。',
 description:'导入本地音视频或一集播客，阅读、研究与笔记在这里连起来。',
 introduction:'从一段本地声音开始。\n原话、编辑稿与自己的理解，各自保留，在这里连起来。',
 Capture,
 TaskActions:FileTaskActions,
 Navigation:()=>null,
 Management:()=> <span>本地内容工作台</span>,
 SettingsLink:()=>null,
 SourceLink:({task})=>task.source?.kind==='podcast'?<span>{task.source.show_title} · {task.source.ingest==='publisher_text'?'节目提供文字':'本地转写'} {task.source.feed_url&&<a href={task.source.feed_url} target="_blank" rel="noreferrer">节目RSS</a>}</span>:task.source?.original_name?<span>{task.source.original_name}</span>:null
}
export function CoreApp(){return new URLSearchParams(location.search).get('view')==='topics'?<TopicLibrary/>:new URLSearchParams(location.search).get('view')==='library'?<ArticleLibrary/>:<App sourceUI={sourceUI}/>}
const DEVICE_KEY='shiwen-device-id'
function ensureDeviceId(){try{
 let value=localStorage.getItem(DEVICE_KEY)
 if(!value){value=crypto.randomUUID();localStorage.setItem(DEVICE_KEY,value)}
 return localStorage.getItem(DEVICE_KEY)||''
}catch{return ''}}
export function installDeviceFetch(){
 const originalFetch=window.fetch.bind(window)
 window.fetch=(input,init)=>{
  const url=new URL(input instanceof Request?input.url:String(input),location.href)
  if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return originalFetch(input,init)
  const headers=new Headers(init?.headers??(input instanceof Request?input.headers:undefined))
  const id=ensureDeviceId()
  if(id&&!headers.has('X-Device-Id'))headers.set('X-Device-Id',id)
  return originalFetch(input,{...init,headers})
 }
}
if(import.meta.env.MODE!=='test'){
 installDeviceFetch()
 createRoot(document.getElementById('root')!).render(<CoreApp/>)
}
