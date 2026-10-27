import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {App} from '../src/main'
vi.mock('markmap-view',()=>({Markmap:{create:()=>({setData:vi.fn(async()=>{}),fit:vi.fn(async()=>{}),rescale:vi.fn(),destroy:vi.fn()})}}))
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();history.replaceState(null,'','/')})
test('workbench generates a map once, keeps draft and reloads the saved graph',async()=>{
 const text='原稿保留，导图只读。',task={id:'aaaaaaaaaaaaaaaa',title:'导图集成',status:'completed',result:{text},created_at:1}
 const content={type:'doc',content:[{type:'paragraph',content:[{type:'text',text}]}]}
 let jobs:any[]=[],generated=0
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  let body:any
  if(path==='/api/tasks')body=[task]
  else if(path==='/api/settings')body={key_configured:true}
  else if(path==='/api/studio/buffer')body={used_bytes:0,capacity_bytes:5e9,waiting:0}
  else if(path.endsWith('/generate')){expect(JSON.parse(String(options?.body)).action).toBe('mindmap');generated++;body={id:'map1',task_id:task.id,action:'mindmap',status:'completed',base_revision:1,mindmap:{text:'归纳主题',children:[{text:'保留来源',children:[]}]}};jobs=[body]}
  else body={task_id:task.id,revision:1,content,sources:[{id:'seg-0',text}],versions:[],generations:jobs}
  return {ok:true,json:async()=>body}
 }))
 localStorage.clear();render(<App/>);await screen.findByRole('textbox',{name:'整理稿编辑区'})
 fireEvent.keyDown(screen.getByRole('tab',{name:'思维导图'}),{key:'Enter'})
 fireEvent.click(await screen.findByRole('button',{name:'生成思维导图'}))
 await screen.findByText('归纳主题',{selector:'h2'});expect(generated).toBe(1)
 fireEvent.keyDown(screen.getByRole('tab',{name:'编辑稿'}),{key:'Enter'});expect(screen.getByRole('textbox',{name:'整理稿编辑区'}).textContent).toBe(text)
 cleanup();render(<App/>);await screen.findByRole('textbox',{name:'整理稿编辑区'})
 fireEvent.keyDown(screen.getByRole('tab',{name:'思维导图'}),{key:'Enter'});await screen.findByText('归纳主题',{selector:'h2'})
 await waitFor(()=>expect(generated).toBe(1))
})
