import Library from './Library'
import Subscriptions from './Subscriptions'
import {useEffect,useState,useRef} from 'react'
import {AudioLines,ArrowUpRight,Layers3,BookOpen,Compass,Menu,Plus,Rss,Settings2,Sparkles,Image,ShieldCheck} from 'lucide-react'
import LinkCapture from './LinkCapture'
import BatchCapture from './BatchCapture'
import SettingsFields from './SettingsFields'
import {sourceUI} from './private-source-ui'
import {Skeleton} from './Motion'
import './home.css'
import './workbench-redesign.css'
type Task={id:string;title?:string;status:string;created_at:number;source?:{kind?:string;platform?:string};video_id?:string;kind?:string}
async function api(path:string,body?:unknown){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const v=await r.json();if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'请求未完成');return v}
function Settings(){
 const [ready,setReady]=useState(false),[search,setSearch]=useState(false),[key,setKey]=useState(''),[deepseek,setDeepseek]=useState(''),[message,setMessage]=useState(''),[settingsLoading,setSettingsLoading]=useState(true)
 useEffect(()=>{api('/api/settings').then(v=>{setReady(Boolean(v.key_configured));setSearch(Boolean(v.search_key_configured))}).catch(e=>setMessage(e.message)).finally(()=>setSettingsLoading(false))},[])
 return <section className="home-settings"><h1>设置</h1>{settingsLoading&&<Skeleton label="正在读取设置"/>}<SettingsFields keyReady={ready} searchReady={search} keyValue={key} setKey={setKey} deepseekKey={deepseek} setDeepseekKey={setDeepseek} SettingsLink={sourceUI.SettingsLink} PrivateSettings={sourceUI.PrivateSettings} save={async()=>{try{const v=await api('/api/settings',{provider:'local',api_key:key||null,deepseek_key:deepseek||null});setReady(Boolean(v.key_configured));setSearch(Boolean(v.search_key_configured));setKey('');setDeepseek('');setMessage('设置已保存。')}catch(e){setMessage((e as Error).message)}}}/><p role="status">{message}</p></section>
}

export default function Home({view='home'}:{view?:string}){
 const [tasks,setTasks]=useState<Task[]>([]),[navOpen,setNavOpen]=useState(false)
 useEffect(()=>{if(!['home','documents'].includes(view))return;let alive=true;async function refresh(){try{const v=await api('/api/tasks');if(alive)setTasks(Array.isArray(v)?v.filter((t:Task)=>t.kind!=='creator').sort((a:Task,b:Task)=>b.created_at-a.created_at):[])}catch{if(alive)setTasks([])}}void refresh();const timer=setInterval(refresh,5000);return()=>{alive=false;clearInterval(timer)}},[view])
 useEffect(()=>{if(!navOpen)return;const previous=document.activeElement as HTMLElement|null;const panel=document.getElementById('desk-sidebar');const targets=()=>Array.from(panel?.querySelectorAll<HTMLAnchorElement>('a[href]')||[]);targets()[0]?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setNavOpen(false);if(e.key==='Tab'){const list=targets(),first=list[0],last=list[list.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus()}},[navOpen])
 const navRef=useRef<HTMLElement>(null),[indicator,setIndicator]=useState({y:0,height:43})
 useEffect(()=>{const nav=navRef.current;if(!nav)return;const update=()=>{const item=nav.querySelector<HTMLElement>('[aria-current=page]');if(item)setIndicator({y:item.offsetTop,height:item.offsetHeight})};update();const observer=typeof ResizeObserver!=='undefined'?new ResizeObserver(update):null;observer?.observe(nav);return()=>observer?.disconnect()},[view])
 const open=async(id:string)=>{location.assign('/studio/?task='+encodeURIComponent(id))}
 const nav=[{view:'home',label:'开始阅读',icon:Plus},{view:'documents',label:'我的资料',icon:BookOpen},{view:'batch',label:'批量任务',icon:Layers3},{view:'subscriptions',label:'订阅动态',icon:Rss}]
 const title=({home:'工作台',documents:'我的资料',batch:'批量任务',subscriptions:'订阅动态',settings:'设置'} as Record<string,string>)[view]||'工作台'
 return <div className="product-home" onClick={event=>{const link=(event.target as HTMLElement).closest('a') as HTMLAnchorElement|null;if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0||!link.closest('.desk-sidebar'))return;const url=new URL(link.href,location.href),next=url.searchParams.get('view')||'home';if(url.origin===location.origin&&url.pathname==='/studio/'&&['home','documents','batch','subscriptions','settings'].includes(next)){event.preventDefault();history.pushState(null,'',url);window.dispatchEvent(new PopStateEvent('popstate'));setNavOpen(false)}}}>
  <a className="desk-skip" href="#desk-content">跳到主要内容</a>
  <aside className={'desk-sidebar '+(navOpen?'is-open':'')} id="desk-sidebar" aria-label="工作区导航">
   <a className="desk-brand" href={'/studio/'}><span className="desk-logomark"><AudioLines size={24}/></span><strong>拾文<span>Shiwen</span></strong></a>
   <div className="desk-space"><span className="space-avatar">拾</span><div><strong>我的知识空间</strong><small>给好内容一个去处</small></div></div>
   <nav ref={navRef} aria-label="主导航"><i className="nav-indicator" style={{'--nav-offset':indicator.y+'px','--nav-height':indicator.height+'px',opacity:nav.some(n=>n.view===view)?1:0} as import('react').CSSProperties} aria-hidden="true"/>{nav.map(n=><a key={n.view} className={view===n.view?'active':''} href={'/studio/'+(n.view==='home'?'':'?view='+n.view)} aria-current={view===n.view?'page':undefined}><n.icon size={18}/>{n.label}{n.view==='home'&&<kbd>↵</kbd>}</a>)}</nav>
   <div className="desk-nav-label">探索与整理</div>
   <nav aria-label="更多工具"><a href={'/studio/?view=library'}><Image size={18}/>图文资料</a><a href={'/studio/?view=knowledge'}><Sparkles size={18}/>AI 资料助手</a><a href={'/studio/?view=discovery'}><Compass size={18}/>发现话题</a></nav>
   <div className="desk-sidebar-bottom"><div className="desk-local"><ShieldCheck size={17}/><div><strong>本地工作台</strong><p>原稿保留，按自己的节奏整理</p></div></div><a className="desk-settings" href={'/studio/?view=settings'}><Settings2 size={18}/>设置与账号</a><div className="desk-profile"><span>我</span><strong>个人工作区<small>拾文自用版</small></strong><span className="profile-dot"/></div></div>
  </aside>
  {navOpen&&<button className="desk-scrim" aria-label="关闭导航" onClick={()=>setNavOpen(false)}/>}
  <div className="desk-body"><header className="desk-topbar"><div><button className="desk-menu" aria-label="打开导航" aria-controls="desk-sidebar" aria-expanded={navOpen} onClick={()=>setNavOpen(!navOpen)}><Menu size={20}/></button><span className="desk-breadcrumb">我的空间</span><span className="desk-divider">/</span><strong>{title}</strong></div><div className="desk-topbar-right"><span className="desk-private"><ShieldCheck size={14}/>专注于你的内容</span><a href={'/studio/?view=settings'} aria-label="打开设置" className="desk-avatar">我</a></div></header>
  <main id="desk-content" className={'desk-content '+(view==='home'?'desk-home':'')}>
   {view==='subscriptions'?<Subscriptions/>:view==='settings'?<Settings/>:view==='batch'?<section className="home-batch" ref={node=>{node?.querySelector('details')?.setAttribute('open','')}}><div className="desk-page-heading"><Layers3 size={22}/><div><h1>一次整理，多份收获。</h1><p>把待看的链接放进队列，留出时间认真阅读。</p></div></div><BatchCapture onCreated={open}/></section>:view==='documents'?<section className="desk-library-page"><div className="desk-page-heading"><BookOpen size={22}/><div><h1>你的内容，在这里连起来。</h1><p>搜索、收藏、归入合集。让看过的，真正留下来。</p></div></div><Library fallback={tasks}/></section>:<>
    <section className="home-hero"><div className="desk-greeting"><span className="desk-greeting-icon"><AudioLines size={23}/></span><span>每一段内容，都值得认真读。</span></div><h1>把看过的，<br className="mobile-break"/>变成自己的。</h1><p>视频、播客、图文。一处收集，慢慢读懂。</p><div className="home-input"><LinkCapture variant="home" onCreated={open}/></div><div className="desk-input-shortcuts"><a href={'/studio/?view=batch'}>＋ 批量</a><span/><a href={'/studio/?view=library'}><Image size={14}/>导入图文</a><small>粘贴链接，按 Enter 开始</small></div></section>
    <section className="home-recent" aria-labelledby="recent-title"><div className="desk-section-heading"><div><h2 id="recent-title">继续你的阅读</h2><p>最近收集的灵感，等你回来。</p></div><a href={'/studio/?view=documents'}>查看全部<ArrowUpRight size={15}/></a></div><Library fallback={tasks} compact/></section>
   </>}
  </main><footer className="desk-footer"><AudioLines size={13}/><span>拾文</span><span>信息有所归，思考有所依。</span></footer></div>
 </div>
}
