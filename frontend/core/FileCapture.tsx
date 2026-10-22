import {useEffect,useRef,useState} from 'react'
import {FileAudio,UploadCloud,X,LoaderCircle,Check,RefreshCw} from 'lucide-react'
import {Button} from '@/components/ui/button'
import './files.css'

type Admission={id:string;cached?:boolean;restored?:boolean}
type Run={cancelled:boolean;id?:string;xhr?:XMLHttpRequest;accepted:boolean}
async function json(path:string,init?:RequestInit){
 const r=await fetch(path,{...init,headers:{'Content-Type':'application/json',...init?.headers}})
 const body=await r.json();if(!r.ok)throw Error(typeof body.detail==='string'?body.detail:'请求未完成，请稍后重试。');return body
}
const size=(n:number)=>new Intl.NumberFormat('zh-CN',{maximumFractionDigits:1}).format(n/1e6)+' MB'
export default function FileCapture({onCreated,notify,onBusyChange}:{onCreated:(id:string)=>Promise<void>;notify:(message:string)=>void;onBusyChange?:(busy:boolean)=>void}){
 const [file,setFile]=useState<File|null>(null),[phase,setPhase]=useState('idle'),[bytes,setBytes]=useState(0),[error,setError]=useState(''),[drag,setDrag]=useState(false),[ready,setReady]=useState<boolean|null>(null)
 const run=useRef<Run|null>(null),mounted=useRef(true),errorRef=useRef<HTMLParagraphElement>(null)
 const busy=['creating','uploading','validating','cancelling'].includes(phase)
 useEffect(()=>{mounted.current=true;json('/api/health').then(v=>{if(mounted.current)setReady(v.models_ready)}).catch(()=>{if(mounted.current)setError('连接不到本地服务，请启动核心服务后重试。')});return()=>{mounted.current=false;onBusyChange?.(false);const current=run.current;if(current&&!current.accepted){current.cancelled=true;current.xhr?.abort();if(current.id)json('/api/files/uploads/'+current.id,{method:'DELETE'}).catch(()=>{})}}},[])
 useEffect(()=>{onBusyChange?.(busy)},[busy,onBusyChange])
 useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(busy){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[busy])
 useEffect(()=>{if(error)errorRef.current?.focus()},[error])
 function choose(list:FileList|null){
  if(busy)return
  setError('');setBytes(0);setPhase('idle')
  if(!list?.length)return
  if(list.length!==1){setFile(null);setError('每次只导入一个文件，请重新选择。');return}
  const selected=list[0]
  if(!/\.(mp3|m4a|wav|flac|mp4|mov)$/i.test(selected.name)||!selected.size||selected.size>1e9){setFile(null);setError('请选择非空的 MP3/M4A/WAV/FLAC/MP4/MOV，单文件不超过 1GB。');return}
  setFile(selected)
 }
 async function cancel(){
  const current=run.current;if(!current||current.accepted)return
  current.cancelled=true;setPhase('cancelling');current.xhr?.abort()
  if(current.id){try{await json('/api/files/uploads/'+current.id,{method:'DELETE'})}catch{
   // Admission may have won the race; resolve the server state instead of claiming deletion.
   try{const state=await json('/api/files/uploads/'+current.id);if(state.status==='accepted'&&state.task_id){current.accepted=true;if(mounted.current)setPhase('done');await onCreated(state.task_id);notify('文件已入队，保留处理中任务；上传暂存未再删除。');return}}catch{}
  }}
  if(mounted.current){setBytes(0);setError('已取消上传。需要继续时可重新上传，已入库的内容会自动复用。')}
 }
 async function start(){
  if(!file||busy)return
  const current:Run={cancelled:false,accepted:false};run.current=current;setError('');setBytes(0);setPhase('creating')
  try{
   const session=await json('/api/files/uploads',{method:'POST',signal:AbortSignal.timeout(15000),body:JSON.stringify({filename:file.name,size_bytes:file.size})});current.id=session.upload_id
   if(current.cancelled){await json('/api/files/uploads/'+current.id,{method:'DELETE'});return}
   if(!mounted.current)return
   setPhase('uploading')
   const result=await new Promise<Admission>((resolve,reject)=>{
    const xhr=new XMLHttpRequest();current.xhr=xhr
    xhr.upload.onprogress=e=>{if(!mounted.current||current.cancelled)return;setBytes(e.loaded);if(e.loaded>=file.size)setPhase('validating')}
    xhr.onload=()=>{try{const value=JSON.parse(xhr.responseText);if(xhr.status<200||xhr.status>=300)reject(Error(typeof value.detail==='string'?value.detail:'上传未完成，请重试。'));else resolve(value)}catch{reject(Error('服务响应不完整，请重新上传以核对是否已入队。'))}}
    xhr.onerror=()=>reject(Error('网络连接中断。请重新上传，已入库内容不会重复创建。'))
    xhr.onabort=()=>reject(Error('上传已取消'))
    xhr.open('PUT','/api/files/uploads/'+current.id)
    xhr.setRequestHeader('Content-Type','application/octet-stream')
    xhr.send(file)
   })
   current.accepted=true
   if(mounted.current){setPhase('done');await onCreated(result.id);notify(result.restored?'已补回原文件，正在恢复回听；原稿与编辑版本保留。':result.cached?'这份内容已在文稿库中，已打开已有任务。':'文件已接收并入队，转写完成后即可阅读。')}
  }catch(e){if(!current.cancelled&&mounted.current){setError((e as Error).message);setPhase('failed')}}
  finally{
   if(current.id&&!current.accepted){try{await json('/api/files/uploads/'+current.id,{method:'DELETE'})}catch{}}
   if(mounted.current&&current.cancelled&&!current.accepted)setPhase('idle')
  }
 }
 return <div className="file-capture">
  <label className={`file-drop ${drag?'dragging':''} ${file?'selected':''}`} onDragOver={e=>{e.preventDefault();if(!busy)setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);choose(e.dataTransfer.files)}}>
   <input type="file" name="local_media" aria-label="选择本地音视频文件" accept=".mp3,.m4a,.wav,.flac,.mp4,.mov" disabled={busy} onChange={e=>{choose(e.target.files);e.target.value=''}}/>
   <span className="file-symbol">{file?<FileAudio aria-hidden="true"/>:<UploadCloud aria-hidden="true"/>}</span>
   <strong>{file?file.name:'把一段声音，留成可用的文字'}</strong><span>{file?size(file.size):'拖入一个文件，或点击选择'}</span>
   <small>MP3 · M4A · WAV · FLAC · MP4 · MOV</small>
  </label>
  <div className="file-boundaries"><span>最长 2 小时</span><span>单文件 ≤ 1GB</span><span>本地 CPU 识别</span></div>
  <p className="file-help">原文件与音轨进入 5GB 临时缓冲。确认最终稿后才可清理；文稿与笔记长期保留。格式与时长由服务端再次校验。</p>
  {ready===null&&!error&&<p className="file-help" role="status">正在检查本地模型…</p>}
  {ready===false&&<p className="file-warning" role="status">本地模型尚未就绪。请按 README 准备模型后重新打开此窗口；转写不需要云端 Key。</p>}
  {busy&&<div className="file-transfer" role="status" aria-live="polite"><div><LoaderCircle className="spin" size={16} aria-hidden="true"/><strong>{phase==='creating'?'正在准备上传…':phase==='validating'?'上传已发送，正在校验格式与时长…':phase==='cancelling'?'正在取消并清理暂存…':'正在上传到本机服务…'}</strong></div><progress aria-label="上传到本机的进度" max={file?.size||1} value={bytes}/><small>{size(bytes)} / {size(file?.size||0)} · 100% 发送完成仍需等待服务端确认</small></div>}
  {error&&<p ref={errorRef} tabIndex={-1} className="file-error" role="alert">{error}</p>}
  <div className="file-actions">{busy?<Button variant="outline" onClick={cancel} disabled={phase==='cancelling'}><X size={16} aria-hidden="true"/>取消上传</Button>:<Button onClick={start} disabled={!file||ready!==true}>{phase==='failed'?<RefreshCw size={16} aria-hidden="true"/>:<Check size={16} aria-hidden="true"/>}{phase==='failed'?'重新上传':'导入并转写'}</Button>}<span>无需配置 Key 即可转写和编辑</span></div>
 </div>
}

export function FileTaskActions({task,onRefresh,notify}:{task:{id:string;status:string};onRefresh:()=>Promise<void>;notify:(message:string)=>void}){
 const [busy,setBusy]=useState(false)
 if(!['failed','waiting_space'].includes(task.status))return null
 async function act(){setBusy(true);try{if(task.status==='waiting_space'){await json('/api/studio/buffer/cleanup',{method:'POST'});await json('/api/studio/buffer/resume',{method:'POST'})}else await json('/api/files/tasks/'+task.id+'/retry',{method:'POST'});await onRefresh();notify('已提交继续处理；空间仍不足时会保留等待状态。')}catch(e){notify((e as Error).message)}finally{setBusy(false)}}
 return <Button disabled={busy} variant="outline" onClick={act}><RefreshCw size={16} aria-hidden="true"/>{task.status==='waiting_space'?'清理已确认素材并继续':'重试，复用已完成片段'}</Button>
}
