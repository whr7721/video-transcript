/// <reference types="vite/client" />
import React from 'react'
import {createRoot} from 'react-dom/client'
import {App} from '../src/Studio'
import ArticleLibrary from '../src/ArticleLibrary'
import type {SourceUI} from '../src/source-ui'

const sourceUI:SourceUI={
 empty:'这里将保存你的本地音视频文稿。',
 description:'当前为核心隔离预览，本地文件入口将在下一阶段开放。',
 introduction:'原稿、整理与个人笔记，在这里连起来。\n本地文件入口将在下一阶段开放；现在可以使用图文素材库。',
 Capture:()=> <div className="dialog-form"><p>本地文件入口正在准备中。当前版本可使用图文素材库，导入文章或粘贴正文。</p><a className="text-link" href="/studio/?view=library">打开图文素材库</a></div>,
 Navigation:()=>null,
 Management:()=> <span>本地内容工作台</span>,
 SettingsLink:()=>null,
 SourceLink:({task})=>task.source?.original_name?<span>{task.source.original_name}</span>:null
}
export function CoreApp(){return new URLSearchParams(location.search).get('view')==='library'?<ArticleLibrary/>:<App sourceUI={sourceUI}/>}
if(import.meta.env.MODE!=='test')createRoot(document.getElementById('root')!).render(<CoreApp/>)
