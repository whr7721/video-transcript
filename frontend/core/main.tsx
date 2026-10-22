/// <reference types="vite/client" />
import React from 'react'
import {createRoot} from 'react-dom/client'
import {App} from '../src/Studio'
import ArticleLibrary from '../src/ArticleLibrary'
import type {SourceUI} from '../src/source-ui'
import FileCapture,{FileTaskActions} from './FileCapture'

const sourceUI:SourceUI={
 empty:'这里将保存你的本地音视频文稿。',
 description:'选择本地音视频，转写、回听与笔记在同一个工作台完成。',
 introduction:'从一段本地声音开始。\n原话、编辑稿与自己的理解，各自保留，在这里连起来。',
 Capture:FileCapture,
 TaskActions:FileTaskActions,
 Navigation:()=>null,
 Management:()=> <span>本地内容工作台</span>,
 SettingsLink:()=>null,
 SourceLink:({task})=>task.source?.original_name?<span>{task.source.original_name}</span>:null
}
export function CoreApp(){return new URLSearchParams(location.search).get('view')==='library'?<ArticleLibrary/>:<App sourceUI={sourceUI}/>}
if(import.meta.env.MODE!=='test')createRoot(document.getElementById('root')!).render(<CoreApp/>)
