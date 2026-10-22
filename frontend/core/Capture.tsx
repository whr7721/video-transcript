import {useState} from 'react'
import FileCapture from './FileCapture'
import PodcastCapture from './PodcastCapture'
import type {SourceUI} from '../src/source-ui'
import './podcasts.css'

type Props=React.ComponentProps<SourceUI['Capture']>
export default function Capture(props:Props){
 const [tab,setTab]=useState('file'),[busy,setBusy]=useState(false)
 const activeProps={...props,onBusyChange:(value:boolean)=>{setBusy(value);props.onBusyChange?.(value)}}
 return <div><div className="capture-options" role="group" aria-label="导入来源"><button type="button" disabled={busy} aria-pressed={tab==='file'} onClick={()=>setTab('file')}>本地文件</button><button type="button" disabled={busy} aria-pressed={tab==='podcast'} onClick={()=>setTab('podcast')}>播客 RSS</button></div>{tab==='file'?<FileCapture {...activeProps}/>:<PodcastCapture {...activeProps}/>}</div>
}
