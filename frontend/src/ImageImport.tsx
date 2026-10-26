import {useState} from 'react'
import {Button} from '@/components/ui/button'
export default function ImageImport({title,onCreated,notify}:{title:string;onCreated:(id:string)=>Promise<void>;notify:(text:string)=>void}){
 const [files,setFiles]=useState<File[]>([]),[busy,setBusy]=useState(false),[progress,setProgress]=useState('')
 function add(incoming:File[]){const next=[...files,...incoming];if(next.length>64||next.some(f=>f.size>8000000)||next.reduce((n,f)=>n+f.size,0)>64000000){notify('最多64张，每张8MB、合计64MB以内；请分成多份材料导入。');return}setFiles(next)}
 async function submit(){setBusy(true);let ident='';try{
  let response=await fetch('/api/library/image-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:title||files[0]?.name,count:files.length})});let value=await response.json();if(!response.ok)throw Error(value.detail||'创建材料失败');ident=value.id
  for(let i=0;i<files.length;i++){setProgress(`正在上传第 ${i+1}/${files.length} 张`);response=await fetch(`/api/library/image-items/${ident}/${i}`,{method:'PUT',body:files[i]});value=await response.json();if(!response.ok)throw Error(value.detail||'图片上传失败')}
  response=await fetch(`/api/library/image-items/${ident}/recognize`,{method:'POST'});value=await response.json();if(!response.ok)throw Error(value.detail||'识别未启动');await onCreated(ident)
 }catch(e){notify((e as Error).message+(ident?'；已保存的图片可在素材库中查看或重新识别。':''));if(ident){await fetch(`/api/library/image-items/${ident}/stop-upload`,{method:'POST'}).catch(()=>{});await onCreated(ident)}}finally{setBusy(false);setProgress('')}}
 return <div className="image-import" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy)add(Array.from(e.dataTransfer.files))}} onPaste={e=>{const images=Array.from(e.clipboardData.items).filter(x=>x.type.startsWith('image/')).map(x=>x.getAsFile()).filter((f):f is File=>!!f);if(images.length&&!busy){e.preventDefault();add(images)}}} tabIndex={0} aria-label="图片选择、拖入或粘贴区域">
  <label htmlFor="image-files">选择图片（可多选）</label><input id="image-files" type="file" multiple disabled={busy} accept="image/png,image/jpeg,image/webp,image/gif" onChange={e=>{add(Array.from(e.target.files||[]));e.target.value=''}}/>
  <p className="article-help">也可以拖入图片，或点此区域后粘贴截图。以下顺序就是图集顺序；文字、图解和原图一起保留。</p>
  <ol className="image-file-order">{files.map((file,i)=><li key={i}><span>{i+1}. {file.name}</span><button type="button" disabled={busy||i===0} aria-label={`上移第${i+1}张`} onClick={()=>setFiles(old=>{const next=[...old];[next[i-1],next[i]]=[next[i],next[i-1]];return next})}>上移</button><button type="button" disabled={busy} aria-label={`移除第${i+1}张`} onClick={()=>setFiles(old=>old.filter((_,index)=>index!==i))}>移除</button></li>)}</ol>
  {progress&&<p role="status">{progress}</p>}<Button type="button" disabled={busy||!files.length} onClick={submit}>{busy?'正在导入…':`保留原图并识字${files.length?'（'+files.length+'张）':''}`}</Button>
 </div>
}
