import {installDesignPreview} from './preview-api'
import Home from './Home'
import Knowledge from './Knowledge'
import './knowledge.css'
import React from 'react'
import {createRoot} from 'react-dom/client'
import {App as Studio} from './Studio'
import ArticleLibrary from './ArticleLibrary'
import Discovery from './Discovery'
import TopicLibrary from './TopicLibrary'
import {sourceUI} from './private-source-ui'
export function App(){return <Studio sourceUI={sourceUI}/>}
export function ProductApp(){const p=new URLSearchParams(location.search);return p.get('task')?<App/>:<Home view={p.get('view')||'home'}/>}
if(import.meta.env.MODE!=='test')installDesignPreview()
if(import.meta.env.MODE!=='test')createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('view')==='knowledge'?<Knowledge/>:new URLSearchParams(location.search).get('view')==='topics'?<TopicLibrary/>:new URLSearchParams(location.search).get('view')==='discovery'?<Discovery/>:new URLSearchParams(location.search).get('view')==='library'?<ArticleLibrary extraNavigation={<sourceUI.Navigation/>} imageCapture={sourceUI.ImageCapture}/>:<ProductApp/>)
