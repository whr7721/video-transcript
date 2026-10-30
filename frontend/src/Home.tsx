import Library from './Library'
import Subscriptions from './Subscriptions'
import {useEffect,useState} from 'react'
import LinkCapture from './LinkCapture'
import BatchCapture from './BatchCapture'
import SettingsFields from './SettingsFields'
import {sourceUI} from './private-source-ui'
import './home.css'
import './workbench-redesign.css'
type Task={id:string;title?:string;status:string;created_at:number;source?:{kind?:string;platform?:string};video_id?:string;kind?:string}
const labels:Record<string,string>={xiaohongshu:'小红书',tiktok:'TikTok',twitter:'Twitter/X',xiaoyuzhou:'小宇宙',spotify:'Spotify播客',youtube:'YouTube',bilibili:'B站',douyin:'抖音',rss:'播客',local_file:'本地文件',podcast:'播客',completed:'已完成',queued:'排队中',running:'处理中',failed:'需重试',waiting_space:'等待空间'}
async function api(path:string,body?:unknown){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const v=await r.json();if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'请求未完成');return v}
function Settings(){
 const [ready,setReady]=useState(false),[search,setSearch]=useState(false),[key,setKey]=useState(''),[deepseek,setDeepseek]=useState(''),[message,setMessage]=useState('')
 useEffect(()=>{api('/api/settings').then(v=>{setReady(v.key_configured);setSearch(v.search_key_configured)}).catch(e=>setMessage(e.message))},[])
 return <section className="home-settings"><h1>设置</h1><SettingsFields keyReady={ready} searchReady={search} keyValue={key} setKey={setKey} deepseekKey={deepseek} setDeepseekKey={setDeepseek} SettingsLink={sourceUI.SettingsLink} PrivateSettings={sourceUI.PrivateSettings} save={async()=>{try{const v=await api('/api/settings',{provider:'local',api_key:key||null,deepseek_key:deepseek||null});setReady(v.key_configured);setSearch(v.search_key_configured);setKey('');setDeepseek('');setMessage('设置已保存。')}catch(e){setMessage((e as Error).message)}}}/><p role="status">{message}</p></section>
}
export default function Home({view='home'}:{view?:string}){
 const [tasks,setTasks]=useState<Task[]>([]),[error,setError]=useState('')
 useEffect(()=>{if(view!=='home')return;let alive=true;async function refresh(){try{const v=await api('/api/tasks');if(alive)setTasks(Array.isArray(v)?v.filter((t:Task)=>t.kind!=='creator').sort((a:Task,b:Task)=>b.created_at-a.created_at):[])}catch(e){if(alive)setError((e as Error).message)}}void refresh();const timer=setInterval(refresh,5000);return()=>{alive=false;clearInterval(timer)}},[view])
 const open=async(id:string)=>{location.assign('/studio/?task='+encodeURIComponent(id))}
 return <div className="product-home"><header className="home-nav"><a className="home-brand" href="/studio/"><img src="/logo.svg" alt=""/>拾文</a><nav aria-label="主导航"><a href="/studio/" aria-current={view==='home'?'page':undefined}>文稿</a><a href="/studio/?view=batch" aria-current={view==='batch'?'page':undefined}>批量</a><a href="/studio/?view=subscriptions" aria-current={view==='subscriptions'?'page':undefined}>订阅</a><a href="/studio/?view=settings" aria-current={view==='settings'?'page':undefined}>设置</a></nav></header><main>{view==='subscriptions'?<Subscriptions/>:view==='settings'?<Settings/>:view==='batch'?<section className="home-batch" ref={node=>{node?.querySelector('details')?.setAttribute('open','')}}><h1>批量链接队列</h1><BatchCapture onCreated={open}/></section>:<><section className="home-hero"><h1>拾文 · 把视频读成文字</h1><p>从一个视频或播客链接开始。</p><div className="home-input"><LinkCapture variant="home" onCreated={open}/><a className="home-batch-link" href="/studio/?view=batch">＋ 批量</a></div></section><section className="home-recent" aria-labelledby="recent-title"><h2 id="recent-title">最近文稿</h2>{error&&<p role="alert">{error}</p>}<Library fallback={tasks}/></section></>}</main></div>
}
