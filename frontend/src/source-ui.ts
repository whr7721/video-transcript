import type {ComponentType} from 'react'
export type SourceUI={
 empty:string
 description:string
 introduction:string
 Capture:ComponentType<{onCreated:(id:string)=>Promise<void>;notify:(message:string)=>void}>
 Navigation:ComponentType
 Management:ComponentType
 SettingsLink:ComponentType
 SourceLink:ComponentType<{task:{video_id?:string;source?:{kind:string;original_name?:string}}}>
}
