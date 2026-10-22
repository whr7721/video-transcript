import React from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App } from '../src/main'

const source='这是一段用于核对原稿的真实测试文字。'
let revision=1, saved:any, puts=0
const task={id:'aaaaaaaaaaaaaaaa',title:'文稿保存验证',author:'测试作者',status:'completed',created_at:1,video_id:'7692820343819455785',result:{text:source}}
function doc(){return {task_id:task.id,revision,content:saved,sources:[{id:'seg-0',text:source,start:0,end:10}],versions:[{revision,created:1}],generations:[],audio_available:false}}
beforeEach(()=>{
 localStorage.clear();revision=1;puts=0;saved={type:'doc',content:[{type:'paragraph',attrs:{id:'block-0',sourceIds:['seg-0']},content:[{type:'text',text:source}]}]}
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  let body:any
  if(path==='/api/tasks')body=[task]
  else if(path==='/api/settings')body={search_key_configured:false,key_configured:true}
  else if(path.startsWith('/api/studio/research/'))body=[]
  else if(path==='/api/studio/buffer')body={used_bytes:0,capacity_bytes:5e9,reclaimable_bytes:0,waiting:0}
  else if(path.endsWith('/generate')&&JSON.parse(String(options?.body)).action==='manuscript')body={id:'test-full',action:'manuscript',status:'completed',base_revision:revision,content:{type:'doc',content:[{type:'heading',attrs:{level:2},content:[{type:'text',text:'完整文章标题'}]},{type:'paragraph',content:[{type:'text',text:'完整整理稿保留具体例子，先预览后采用。'}]}]},essence_content:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'精华回顾文字。'}]}]}}
  else if(path.endsWith('/generate'))body={id:'test-summary',action:'summary',status:'completed',base_revision:revision,items:[{text:'归纳：先收集问题，再提供解决方案。',source_ids:['seg-0']}]}
  else if(options?.method==='PUT'){const v=JSON.parse(String(options.body));saved=v.content;revision++;puts++;body=doc()}
  else body=doc()
  return {ok:true,json:async()=>body}
 }))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

test('mounts actual editor with saved source and keeps draft separate',async()=>{
 render(<App/> )
 const editor=await screen.findByRole('textbox',{name:'整理稿编辑区'})
 expect(editor.textContent).toContain(source)
 expect(screen.getByRole('tab',{name:'编辑稿'}).getAttribute('data-state')).toBe('active')
 expect(screen.getByText('文稿保存验证',{selector:'h1'})).toBeTruthy()
})

test('oversized source exposes full text but blocks whole-manuscript calls',async()=>{
 const original=fetch;let generated=0
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path.endsWith('/generate'))generated++
  const response=await original(path,options);const data=await response.json()
  if(path==='/api/studio/documents/'+task.id&&!options?.method){data.generation_capabilities={raw_characters:36793,manuscript_limit:24000,manuscript:{available:false,reason:'超限'},summary:{available:true,reason:''},quotes:{available:true,reason:''}}}
  return {ok:true,json:async()=>data}
 }))
 render(<App/>);await screen.findByRole('textbox',{name:'整理稿编辑区'})
 expect(await screen.findByText(/超过完整整理稿 24,000 字上限/)).toBeTruthy()
 expect((screen.getByRole('button',{name:'生成完整整理稿'}) as HTMLButtonElement).disabled).toBe(true)
 expect(screen.getByRole('button',{name:'改用选段研究'})).toBeTruthy();expect(generated).toBe(0)
})

test('editor mutation autosaves a new revision and survives task polling',async()=>{
 render(<App/> )
 const editor=await screen.findByRole('textbox',{name:'整理稿编辑区'})
 editor.querySelector('p')!.textContent='人工修改后的文稿，不覆盖识别原稿。'
 fireEvent.input(editor,{inputType:'insertText'})
 await waitFor(()=>expect(puts).toBeGreaterThan(0),{timeout:5000})
 expect(JSON.stringify(saved)).toContain('人工修改后的文稿')
 expect(task.result.text).toBe(source)
 expect(screen.getByText('已保存到本机',{exact:false})).toBeTruthy()
})

test('generated summary stays in preview until explicitly adopted',async()=>{
 render(<App/> )
 const editor=await screen.findByRole('textbox',{name:'整理稿编辑区'})
 screen.getByText('更多操作').closest('details')!.open=true
 fireEvent.click(screen.getByRole('button',{name:'生成摘要'}))
 await screen.findByText('归纳：先收集问题，再提供解决方案。')
 expect(editor.textContent).not.toContain('归纳：')
 fireEvent.click(screen.getByRole('button',{name:'加入稿件'}))
 await waitFor(()=>expect(editor.textContent).toContain('归纳：'))
 expect(task.result.text).toBe(source)
})


test('full manuscript previews in main reading area and requires explicit adoption',async()=>{
 render(<App/> )
 await screen.findByRole('textbox',{name:'整理稿编辑区'})
 fireEvent.click(screen.getByRole('button',{name:'生成完整整理稿'}))
 await screen.findByText('完整文章标题')
 expect(puts).toBe(0)
 expect(JSON.stringify(saved)).not.toContain('完整整理稿保留')
 expect(screen.getByText('精华版 · 快速回顾')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'采用到编辑稿'}))
 expect(puts).toBe(0)
 fireEvent.click(screen.getByRole('button',{name:'确认采用并保存新版本'}))
 await waitFor(()=>expect(puts).toBe(1))
 expect(JSON.stringify(saved)).toContain('完整整理稿保留')
 expect(task.result.text).toBe(source)
 expect(await screen.findByRole('textbox',{name:'整理稿编辑区'})).toBeTruthy()
})


test('selected editor passage reaches research without changing manuscript',async()=>{
 render(<App/>)
 const editor=await screen.findByRole('textbox',{name:'整理稿编辑区'})
 const node=editor.querySelector('p')!.firstChild!
 const selected=vi.spyOn(window,'getSelection').mockReturnValue({toString:()=>source,anchorNode:node,focusNode:node} as unknown as Selection)
 fireEvent.mouseUp(editor)
 fireEvent.click(screen.getByRole('button',{name:'深入一下'}))
 const input=await screen.findByLabelText(/本次选段/)
 expect((input as HTMLTextAreaElement).value).toBe(source)
 expect(puts).toBe(0)
 expect(task.result.text).toBe(source)
 selected.mockRestore()
})
