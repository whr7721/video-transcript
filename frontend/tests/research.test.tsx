import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ResearchPanel from '../src/ResearchPanel'

const passage={taskId:'aaaaaaaaaaaaaaaa',basis:'original' as const,revision:1,selection:'公开过程可以帮助理解。'}
const result={id:'research-1',task_id:passage.taskId,question:'有什么前提？',mode:'explain',online:false,status:'completed',stage:'done',
 context:{selection:passage.selection,basis:'original',version:'original'},warnings:['本次未联网，解释不是已查证事实。'],sources:[],
 sections:[{heading:'先理解再验证',text:'这是一段帮助理解的解释。',basis:'model_analysis',citations:[]}],open_questions:['实际效果如何？']}
let notes:any[]=[],configured=false,saves=0,starts=0
beforeEach(()=>{
 notes=[];configured=false;saves=0;starts=0
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  let value:any
  if(path==='/api/settings')value={search_key_configured:configured}
  else if(path==='/api/studio/research/documents/'+passage.taskId&&options?.method==='POST'){starts++;value=result}
  else if(path.endsWith('/documents/'+passage.taskId))value=[]
  else if(path.endsWith('/topics'))value=[]
  else if(path.endsWith('/notes')&&options?.method==='POST'){saves++;const body=JSON.parse(String(options.body));notes=[{id:'note-1',topic_id:'topic-1',job_id:result.id,topic_title:body.topic_title,personal:body.personal,revision:1,created:1}];value=notes[0]}
  else if(path.endsWith('/notes'))value=notes
  else value=result
  return {ok:true,json:async()=>value}
 }))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

test('passage explanation can be saved with personal understanding and source job',async()=>{
 render(<ResearchPanel passage={passage} onSettings={()=>{}}/>)
 await screen.findByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')
 expect((screen.getByLabelText(/本次选段/) as HTMLTextAreaElement).value).toBe(passage.selection)
 fireEvent.change(screen.getByLabelText('想弄明白什么？'),{target:{value:'有什么前提？'}})
 fireEvent.click(screen.getByRole('button',{name:'开始深入'}))
 await screen.findByText('这是一段帮助理解的解释。')
 expect(starts).toBe(1);expect(saves).toBe(0)
 expect(screen.getByText('AI分析 · 待核实')).toBeTruthy()
 fireEvent.change(screen.getByLabelText('我的理解／对我有什么用'),{target:{value:'我会先拿小项目验证。'}})
 fireEvent.click(screen.getByRole('button',{name:'保存到专题'}))
 await waitFor(()=>expect(saves).toBe(1))
 expect(notes[0].job_id).toBe(result.id);expect(notes[0].personal).toContain('小项目')
 fireEvent.click(screen.getByRole('button',{name:'专题笔记'}))
 await screen.findByText('我会先拿小项目验证。')
 expect(screen.getByRole('link',{name:'导出 Markdown'}).getAttribute('href')).toContain('note-1/export')
})

test('real case search waits for configured key instead of inventing cases',async()=>{
 const onSettings=vi.fn();render(<ResearchPanel passage={passage} onSettings={onSettings}/>)
 await screen.findByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')
 fireEvent.click(screen.getByLabelText('找真实案例'))
 fireEvent.click(screen.getByRole('button',{name:'开始深入'}))
 await screen.findByRole('alert')
 expect(starts).toBe(0)
 fireEvent.click(screen.getByRole('button',{name:'配置搜索 Key'}));expect(onSettings).toHaveBeenCalledOnce()
})

test('manual source note works without model key and never starts AI',async()=>{
 const original=fetch
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/api/settings')return {ok:true,json:async()=>({key_configured:false,search_key_configured:false})}
  if(path.endsWith('/manual-note')){saves++;return {ok:true,json:async()=>({id:'manual-1'})}}
  return original(path,options)
 }))
 render(<ResearchPanel passage={passage} onSettings={()=>{}}/>)
 await screen.findByRole('button',{name:'配置文本模型 Key'})
 screen.getByText('只记自己的理解 · 不调用 AI').closest('details')!.open=true
 fireEvent.change(screen.getByLabelText('我的来源笔记'),{target:{value:'我会先验证前提。'}})
 fireEvent.click(screen.getByRole('button',{name:'保存手动笔记'}))
 await screen.findByText('手动笔记已保存，来源与版本一并保留；没有调用AI。')
 expect(saves).toBe(1);expect(starts).toBe(0)
})

test('saving settings updates search availability without losing selected passage',async()=>{
 const {rerender}=render(<ResearchPanel passage={passage} onSettings={()=>{}} settingsVersion={0}/>)
 await screen.findByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')
 configured=true;rerender(<ResearchPanel passage={passage} onSettings={()=>{}} settingsVersion={1}/>)
 await waitFor(()=>expect(screen.queryByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')).toBeNull())
 expect((screen.getByLabelText(/本次选段/) as HTMLTextAreaElement).value).toBe(passage.selection)
})


test('verification waits for explicit claim selection and submits only chosen ids',async()=>{
 configured=true
 const awaiting={...result,id:'verify-1',mode:'verify',status:'awaiting_confirmation',claims:[
  {id:'1',original:'原话第一句。',statement:'第一条事实',kind:'fact'},
  {id:'2',original:'原话第二句。',statement:'第二条建议',kind:'opinion'}]}
 const posted:any[]=[]
 const previous=globalThis.fetch
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path.endsWith('/documents/'+passage.taskId)&&options?.method!=='POST')return {ok:true,json:async()=>[awaiting]}
  if(path.endsWith('/confirm')){posted.push(JSON.parse(String(options?.body)));return {ok:true,json:async()=>({...result,id:'verify-1',mode:'verify',sections:[{...result.sections[0],heading:'证据不足：第一条事实'}]})}}
  return previous(path,options)
 }))
 render(<ResearchPanel passage={passage} onSettings={()=>{}}/>)
 await screen.findByText('先确认要查哪句话')
 expect(posted).toEqual([])
 await waitFor(()=>expect((screen.getByLabelText(/第二条建议/) as HTMLInputElement).checked).toBe(true))
 fireEvent.click(screen.getByLabelText(/第二条建议/))
 fireEvent.click(screen.getByRole('button',{name:'确认所选命题，开始核实'}))
 await screen.findByText('证据不足：第一条事实')
 expect(posted).toEqual([{claim_ids:['1'],kinds:{'1':'fact'}}]);expect(saves).toBe(0)
})

test('cannot submit verification when all claims are deselected',async()=>{
 const previous=globalThis.fetch
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path.endsWith('/documents/'+passage.taskId)&&options?.method!=='POST')return {ok:true,json:async()=>[{...result,id:'v',status:'awaiting_confirmation',claims:[{id:'1',original:'原话。',statement:'唯一命题',kind:'fact'}]}]}
  return previous(path,options)
 }))
 render(<ResearchPanel passage={passage} onSettings={()=>{}}/>)
 await screen.findByText('唯一命题')
 await waitFor(()=>expect((screen.getByLabelText(/唯一命题/) as HTMLInputElement).checked).toBe(true))
 fireEvent.click(screen.getByLabelText(/唯一命题/))
 expect((screen.getByRole('button',{name:'确认所选命题，开始核实'}) as HTMLButtonElement).disabled).toBe(true)
})
