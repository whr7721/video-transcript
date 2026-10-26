import {useState} from 'react'
import {Button} from '@/components/ui/button'
export default function PrivateImageCapture({onCreated,notify}:{onCreated:(id:string)=>Promise<void>;notify:(text:string)=>void}){
 const [share,setShare]=useState(''),[busy,setBusy]=useState(false)
 async function submit(){setBusy(true);try{const response=await fetch('/api/private/image-posts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({share_text:share})});const value=await response.json();if(!response.ok)throw Error(value.detail||'导入未完成');await onCreated(value.id)}catch(e){notify((e as Error).message)}finally{setBusy(false)}}
 return <div className="image-private-capture"><label htmlFor="image-share">抖音图文分享链接</label><textarea id="image-share" autoComplete="off" maxLength={5000} rows={4} value={share} onChange={e=>setShare(e.target.value)} placeholder="粘贴单张或多张图文的分享文字…"/><p className="article-help">复用独立登录态，只获取这一条作品的图片，不下载视频或配乐。原图保存在本机素材库，再本地识字；遇到登录或验证会明确提示。</p><Button disabled={busy||!share.trim()} onClick={submit}>{busy?'正在提交…':'获取图片并识别'}</Button></div>
}
