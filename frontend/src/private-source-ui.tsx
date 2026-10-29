import DocumentChat from './DocumentChat'
import BatchCapture from './BatchCapture'
import BilibiliSettings from './BilibiliSettings'
import LinkCapture from './LinkCapture'
import React,{useState} from 'react'
import {ArrowUpRight,LoaderCircle,Plus} from 'lucide-react'
import {Button} from '@/components/ui/button'
import type {SourceUI} from './source-ui'
import PrivateImageCapture from './PrivateImageCapture'
async function api<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(path,{...init,headers:{'Content-Type':'application/json'}});const v=await r.json();if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'提交失败');return v}
function Capture({onCreated,notify}:{onCreated:(id:string)=>Promise<void>;notify:(message:string)=>void}){
 const [share,setShare]=useState(''),[mode,setMode]=useState('single'),[limit,setLimit]=useState('10'),[duration,setDuration]=useState('600'),[submitting,setSubmitting]=useState(false)
 async function create(){try{if(!share.trim())throw Error('请先粘贴抖音分享链接。');setSubmitting(true);const value=await api<{id:string}>(mode==='batch'?'/api/batches':'/api/tasks',{method:'POST',body:JSON.stringify({share_text:share,provider:'local',limit:Number(limit),max_duration_sec:Number(duration),keep_media:false})});await onCreated(value.id);notify('已加入处理队列，完成后可直接整理。')}catch(e){notify((e as Error).message)}finally{setSubmitting(false)}}
return <div className="dialog-form"><label>提取方式<select name="capture_mode" autoComplete="off" value={mode} onChange={e=>setMode(e.target.value)}><option value="single">单条视频</option><option value="batch">博主批量</option></select></label>{mode==='batch'&&<div className="form-row"><label>本批数量<select name="batch_limit" autoComplete="off" value={limit} onChange={e=>setLimit(e.target.value)}>{['10','30','100'].map(v=><option key={v} value={v}>{v} 条</option>)}</select></label><label>视频最长<select name="max_duration" autoComplete="off" value={duration} onChange={e=>setDuration(e.target.value)}>{['600','1200','1800'].map(v=><option key={v} value={v}>{Number(v)/60} 分钟</option>)}</select></label></div>}{mode==='single'?<LinkCapture onCreated={onCreated}/>:<><label>抖音分享链接<textarea name="share_text" autoComplete="off" value={share} onChange={e=>setShare(e.target.value)} placeholder="粘贴链接，或从抖音复制的整段分享文字…" maxLength={5000} rows={4}/></label><p className="muted-note">素材进入5GB缓冲，待你确认最终稿；满额时先清理已确认素材，不足则暂停下载。</p><Button onClick={create} disabled={submitting}>{submitting?<LoaderCircle className="spin"/>:<Plus/>}开始提取</Button></>}</div>
}
export const sourceUI:SourceUI={
 DocumentChat,
 empty:'从一个抖音链接开始。', description:'粘贴抖音分享文字，使用本地识别。',
 introduction:'选择左侧已有文稿，或粘贴一个链接。\n原稿、整理、编辑和来源，在这里连起来。',
 Capture,
 PrivateSettings:BilibiliSettings,
 BatchCapture,
 ImageCapture:PrivateImageCapture,
 Navigation:()=> <><a className="text-link" href="/studio/?view=knowledge">我的资料助手</a><a className="text-link" style={{padding:'12px 8px'}} href="/studio/?view=discovery">抖音话题发现<ArrowUpRight size={13}/></a></>,
 Management:()=> <a href="/">转写与批量管理<ArrowUpRight size={13}/></a>,
 SettingsLink:()=> <a className="text-link" href="/">抖音登录与完整转写设置<ArrowUpRight size={14}/></a>,
 SourceLink:({task})=>task.video_id?<a href={`https://www.douyin.com/video/${task.video_id}`} target="_blank" rel="noreferrer" aria-label="在抖音打开来源"><ArrowUpRight size={16}/></a>:null
}
