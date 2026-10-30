import Home from './Home'
import './knowledge.css'
import React,{useEffect,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {App as Studio} from './Studio'
import {sourceUI} from './private-source-ui'
import './motion.css'
export function App(){return <Studio sourceUI={sourceUI}/>}
export function ProductApp(){const [search,setSearch]=useState(location.search);useEffect(()=>{const update=()=>setSearch(location.search);window.addEventListener('popstate',update);return()=>window.removeEventListener('popstate',update)},[]);const p=new URLSearchParams(search);return p.get('task')?<App/>:<Home view={p.get('view')||'home'}/>}
if(import.meta.env.MODE!=='test')createRoot(document.getElementById('root')!).render(<ProductApp/>)
