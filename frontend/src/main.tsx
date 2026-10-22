import React from 'react'
import {createRoot} from 'react-dom/client'
import {App as Studio} from './Studio'
import ArticleLibrary from './ArticleLibrary'
import Discovery from './Discovery'
import {sourceUI} from './private-source-ui'
export function App(){return <Studio sourceUI={sourceUI}/>}
if(import.meta.env.MODE!=='test')createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('view')==='discovery'?<Discovery/>:new URLSearchParams(location.search).get('view')==='library'?<ArticleLibrary extraNavigation={<sourceUI.Navigation/>}/>:<App/>)
