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

test('saving settings updates search availability without losing selected passage',async()=>{
 const {rerender}=render(<ResearchPanel passage={passage} onSettings={()=>{}} settingsVersion={0}/>)
 await screen.findByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')
 configured=true;rerender(<ResearchPanel passage={passage} onSettings={()=>{}} settingsVersion={1}/>)
 await waitFor(()=>expect(screen.queryByText('联网功能需要单独配置 DeepSeek 官方搜索 Key。')).toBeNull())
 expect((screen.getByLabelText(/本次选段/) as HTMLTextAreaElement).value).toBe(passage.selection)
})
