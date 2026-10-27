import React,{Suspense,lazy,useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {createClient,type SupabaseClient,type Session} from '@supabase/supabase-js';
import {prepareAudio} from './audio';
import {download} from './download';
import type {Artifact} from '../worker/validation';
import './style.css';
const Map=lazy(()=>import('./Map'));
const API=(import.meta.env.VITE_API_URL||'').replace(/\/$/,'');
type Job={id:string;title:string;status:string;duration_sec:number;segments?:{idx:number;state:string;text:string}[];artifact?:Artifact;artifact_state?:string};
async function request(path:string,session:Session|null=null,init:RequestInit={}){
 const res=await fetch(API+path,{...init,headers:{...(session?{Authorization:'Bearer '+session.access_token}:{}),...init.headers},cache:'no-store'});
 let body;try{body=await res.json()}catch{throw new Error('服务响应异常，请稍后重试。')}
 if(!res.ok)throw new Error(body.error||'请求未完成。');return body;
}
function Result({job}:{job:Job}){
 const [tab,setTab]=useState('summary'),a=job.artifact;
 const raw=job.segments?.filter(s=>s.state==='done').map(s=>s.text).join('\n')||'';
 return <><div className="document-heading"><div><p className="muted">{Math.ceil(job.duration_sec)}秒音频</p><h2>{job.title}</h2></div><button onClick={()=>download(`# ${job.title}\n\n${a?'## 摘要\n'+a.summary+'\n\n'+a.highlights.map(x=>'- '+x).join('\n'):''}\n\n## 转写原稿\n${raw}`,'text/markdown;charset=utf-8','拾文文稿.md')}>导出文稿</button></div><nav className="tabs" aria-label="阅读视图">{[['summary','摘要'],['mindmap','思维导图'],['original','转写原稿']].map(([id,label])=><button key={id} aria-pressed={tab===id} onClick={()=>setTab(id)}>{label}</button>)}</nav><div className="document">{tab==='original'?<div className="prose">{raw||'尚未完成转写。'}</div>:!a?<p className="muted">完成全部转写后，可生成摘要与思维导图。</p>:tab==='mindmap'?<Suspense fallback={<p>正在打开导图…</p>}><Map root={a.mindmap} title={job.title}/></Suspense>:<><div className="prose">{a.summary}</div><h3>值得留下的要点</h3><ul className="highlights">{a.highlights.map((s,i)=><li key={i}>{s}</li>)}</ul></>}</div><p className="fine">AI 转写与归纳可能遗漏或出错，请对照原音频核实。</p></>;
}
export function App(){
 const [client,setClient]=useState<SupabaseClient|null>(null),[session,setSession]=useState<Session|null>(null),[email,setEmail]=useState(''),[password,setPassword]=useState('');
 const [jobs,setJobs]=useState<Job[]>([]),[job,setJob]=useState<Job|null>(null),[error,setError]=useState(''),[status,setStatus]=useState(''),[busy,setBusy]=useState(false),[consent,setConsent]=useState(false),[includeRaw,setIncludeRaw]=useState(false),[share,setShare]=useState('');
 const [publicView,setPublicView]=useState<Job|null>(null),[ready,setReady]=useState(false);
 const shareToken=new URLSearchParams(location.hash.slice(1)).get('share');
 useEffect(()=>{
  if(shareToken){if(!/^[a-f0-9]{64}$/.test(shareToken)){setError('分享链接无效。');setReady(true);return}request('/api/share/'+shareToken).then(v=>setPublicView({...v,id:'shared',status:'completed',segments:v.text?[{idx:0,state:'done',text:v.text}]:[]})).catch(e=>setError(e.message)).finally(()=>setReady(true));return}
  let unsub:(()=>void)|undefined,stopped=false;
  request('/api/config').then(async c=>{if(stopped)return;const sb=createClient(c.supabaseUrl,c.supabaseAnonKey,{auth:{flowType:'pkce',detectSessionInUrl:true}});setClient(sb);const {data}=await sb.auth.getSession();if(!stopped)setSession(data.session);const {data:listener}=sb.auth.onAuthStateChange((_event,s)=>setSession(s));unsub=()=>listener.subscription.unsubscribe()}).catch(e=>setError(e.message)).finally(()=>setReady(true));
  return()=>{stopped=true;unsub?.()};
 },[]);
 async function refresh(){if(session)setJobs(await request('/api/jobs',session))}
 useEffect(()=>{setJob(null);setJobs([]);setShare('');if(session)refresh().catch(e=>setError(e.message))},[session?.user.id]);
 async function action(fn:()=>Promise<void>){setError('');setBusy(true);try{await fn()}catch(e){setError(e instanceof Error?e.message:'操作未完成。')}finally{setBusy(false);setStatus('')}}
 async function signIn(register=false){if(!client)return;await action(async()=>{if(!email||password.length<8)throw new Error('请输入邮箱及至少8位密码。');const {error,data}=register?await client.auth.signUp({email,password,options:{emailRedirectTo:location.origin}}):await client.auth.signInWithPassword({email,password});if(error)throw new Error(register?'注册未完成，请检查邮箱、密码或稍后重试。':'登录失败，请检查邮箱和密码。');if(register&&!data.session)setError('请在邮箱中确认注册，然后返回登录。')})}
 async function open(id:string){if(session)await action(async()=>{setShare('');setIncludeRaw(false);setJob(await request('/api/jobs/'+id,session))})}
 async function upload(file:File){if(!session)return;await action(async()=>{
  if(!consent)throw new Error('请先确认你有权处理音频，并同意云端处理。');
  setStatus('正在本机解码并切分音频…');const audio=await prepareAudio(file);
  const j=await request('/api/jobs',session,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:file.name.slice(0,200),source_hash:audio.hash,duration_sec:audio.duration,rights_confirmed:true})});
  setShare('');setJob(await request('/api/jobs/'+j.id,session));
  for(const part of audio.parts){setStatus(`正在转写第${part.idx+1}/${audio.parts.length}段…`);await request(`/api/jobs/${j.id}/segments/${part.idx}`,session,{method:'POST',headers:{'Content-Type':'audio/wav'},body:part.wav});setJob(await request('/api/jobs/'+j.id,session))}
  setStatus('正在整理摘要与导图…');await request('/api/jobs/'+j.id+'/summarize',session,{method:'POST'});setJob(await request('/api/jobs/'+j.id,session));await refresh();
 })}
 async function summarize(){if(job&&session)await action(async()=>{setStatus('正在整理摘要与导图…');await request('/api/jobs/'+job.id+'/summarize',session,{method:'POST'});setJob(await request('/api/jobs/'+job.id,session));await refresh()})}
 async function makeShare(){if(job&&session)await action(async()=>{const v=await request('/api/jobs/'+job.id+'/share',session,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({include_transcript:includeRaw})});setShare(location.origin+'/#share='+v.token)})}
 return <><header className="site-header"><a href="/" className="brand"><span className="brand-mark" aria-hidden="true">拾</span>拾文<span className="edition">云端版</span></a><div className="header-actions">{session&&<><span className="account">{session.user.email}</span><button disabled={busy} onClick={()=>void client?.auth.signOut()}>退出登录</button></>}<a href="#privacy">处理与隐私说明</a></div></header><main>
 {shareToken?<section className="reader shared">{publicView?<><p className="muted">来自拾文的只读分享</p><Result job={publicView}/></>:<p role={error?'alert':'status'}>{error||'正在读取分享…'}</p>}<a href="/">使用拾文整理自己的音频</a></section>:<>
 <section className="intro"><div><p className="kicker">听过的内容，值得留下。</p><h1>让音频成为<br/>一份清楚的文稿。</h1><p className="intro-text">上传一段音频，得到转写、摘要和思维导图。<br/>读完、保存，再分享给需要的人。</p><div className="limits"><span>免安装</span><span>每份最长5分钟</span><span>登录体验3份</span></div></div><div className="workflow" aria-label="处理流程"><div><span>01</span><strong>上传音频</strong><p>在浏览器切成独立音频段</p></div><div><span>02</span><strong>留下重点</strong><p>中文转写、摘要、思维导图</p></div><div><span>03</span><strong>读完与分享</strong><p>导出文稿，或创建只读链接</p></div></div></section>
 {!session?<section className="login-panel"><div><h2>从第一段音频开始</h2><p>登录后保存文稿，在不同设备继续阅读。</p></div><form onSubmit={e=>{e.preventDefault();void signIn()}}><label>邮箱<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label>密码<input type="password" minLength={8} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label><div className="login-actions"><button className="primary" disabled={busy||!client}>登录</button><button type="button" disabled={busy||!client} onClick={()=>void signIn(true)}>注册账号</button><button type="button" disabled={busy||!client} onClick={()=>void action(async()=>{const {error}=await client!.auth.signInWithOAuth({provider:'github',options:{redirectTo:location.origin}});if(error)throw new Error('GitHub登录暂不可用，请使用邮箱登录。')})}>GitHub 登录</button></div></form></section>:<div className="workspace"><aside><div className="sidebar-heading"><h2>我的文稿</h2><button disabled={busy} onClick={()=>void action(refresh)}>刷新</button></div>{jobs.length?jobs.map(j=><button disabled={busy} className={'job '+(job?.id===j.id?'selected':'')} key={j.id} onClick={()=>void open(j.id)}><strong>{j.title}</strong><span>{j.status==='completed'?'已整理':'待继续'} · {Math.ceil(j.duration_sec)}秒</span></button>):<p className="muted">第一份文稿会保存在这里。</p>}<p className="fine">最多体验3份不同音频。同一原文件重开会复用结果；中断后重新选择原文件继续。</p></aside><section className="reader"><div className="upload"><div><h2>选一段，交给拾文</h2><p>MP3、M4A、WAV 等，5分钟以内，最多20MB。</p></div><label className={'upload-button '+(busy?'disabled':'')}>{busy?'处理中…':'选择音频'}<input aria-label="选择音频文件" type="file" accept="audio/*,.m4a,.flac,.opus" disabled={busy} onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void upload(f)}}/></label><label className="consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/>我有权处理此音频，同意将音频分段及文稿发送至云端服务处理。</label></div>{job?<><Result job={job}/>{!job.artifact&&<button disabled={busy||job.segments?.filter(s=>s.state==='done').length!==Math.ceil(job.duration_sec/30)} onClick={()=>void summarize()}>生成／重试摘要与导图</button>}{job.artifact&&<div className="share-box"><h3>把这一份分享出去</h3><label><input type="checkbox" checked={includeRaw} disabled={busy} onChange={e=>setIncludeRaw(e.target.checked)}/>同时分享转写原稿</label><div className="share-actions"><button disabled={busy} onClick={()=>void makeShare()}>创建／更新分享链接</button><button disabled={busy} onClick={()=>void action(async()=>{await request('/api/jobs/'+job.id+'/share',session,{method:'DELETE'});setShare('')})}>撤销分享</button></div>{share&&<label>拥有此链接的人可以阅读；更新链接会使旧链接失效。<input readOnly value={share} onFocus={e=>e.target.select()}/></label>}</div>}</>:<div className="empty"><span aria-hidden="true">〰</span><h3>先听见，再看清。</h3><p>上传后，文稿和整理结果会出现在这里。</p></div>}</section></div>}
 {error&&<div className="notice error" role="alert">{error}</div>}{(!ready||status)&&<div className="notice" role="status" aria-live="polite">{status||'正在连接云端…'}</div>}
 </>}
 <footer id="privacy"><h2>关于处理与隐私</h2><p>音频在你的浏览器切段后发送给 Cloudflare Workers AI 转写；文稿发送给硅基流动生成摘要和导图，结果与账号信息保存在 Supabase。这是云端产品，不承诺数据不出机器。各服务可能在境外处理数据，请勿上传敏感或未经授权的内容。</p><p>拾文服务端不长期保存原音频。分享默认关闭，创建链接后拥有链接的人可阅读选定内容；撤销不能收回他人已经保存的副本。体验额度有限，用尽后暂停新任务。当前为需求验证版，尚未提供在线付费。</p><p>问题反馈：请通过邀请你体验拾文的渠道联系维护者。</p></footer>
 </main></>;
}
const mount=document.getElementById('root');
if(mount)createRoot(mount).render(<React.StrictMode><App/></React.StrictMode>);
