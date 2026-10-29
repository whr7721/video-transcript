import type {ComponentType} from 'react'
export type SourceUI={
 DocumentChat?:ComponentType<{taskId:string;onCitation:(id:string)=>void}>
 empty:string
 description:string
 introduction:string
 Capture:ComponentType<{onCreated:(id:string)=>Promise<void>;notify:(message:string)=>void;onBusyChange?:(busy:boolean)=>void}>
 ImageCapture?:ComponentType<{onCreated:(id:string)=>Promise<void>;notify:(message:string)=>void}>
 TaskActions?:ComponentType<{task:{id:string;status:string};onRefresh:()=>Promise<void>;notify:(message:string)=>void}>
 Navigation:ComponentType
 Management:ComponentType
 BatchCapture?:ComponentType<{onCreated:(id:string)=>Promise<void>}>
 PrivateSettings?:ComponentType
 SettingsLink:ComponentType
 SourceLink:ComponentType<{task:{video_id?:string;source?:{kind:string;original_name?:string;feed_url?:string;show_title?:string;ingest?:string}}}>
}
