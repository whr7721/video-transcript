import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import LinkCapture from '../src/LinkCapture'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('capabilities control platform hints, Enter respects IME and opens completed result',async()=>{
 const sent:unknown[]=[];const open=vi.fn(async()=>{})
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>({ok:true,json:async()=>path.endsWith('capabilities')?{platforms:['youtube','rss']}:init?.method==='POST'?(sent.push(JSON.parse(init.body as string)),{id:'a',task_id:'doc',status:'completed',stage:'done'}):[]})))
 render(<LinkCapture onCreated={open}/>);const input=await screen.findByLabelText('粘贴链接，直接读内容')
 expect(screen.queryByText(/B站/)).toBeNull();fireEvent.change(input,{target:{value:'https://youtu.be/test'}})
 fireEvent.keyDown(input,{key:'Enter',isComposing:true});expect(sent.length).toBe(0)
 fireEvent.keyDown(input,{key:'Enter'});await screen.findByText('处理完成');expect(sent.length).toBe(1)
 fireEvent.click(screen.getByRole('button',{name:'打开文稿'}));await waitFor(()=>expect(open).toHaveBeenCalledWith('doc'))
})
test('failed stage can retry without submitting the link again',async()=>{
 const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init)calls.push(path);return {ok:true,json:async()=>path.endsWith('capabilities')?{platforms:['youtube']}:path.endsWith('/retry')?{id:'a',task_id:'doc',status:'completed'}:[{id:'a',task_id:'doc',status:'failed',error:'网络断开'}]}}))
 render(<LinkCapture onCreated={async()=>{}}/>);await screen.findByText('网络断开');fireEvent.click(screen.getByRole('button',{name:'重试失败阶段'}));await screen.findByText('处理完成');expect(calls).toEqual(['/api/link/a/retry'])
})

test('capability failures leave the skeleton and show a real error',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>{throw Error('offline')}))
 render(<LinkCapture onCreated={async()=>{}}/>);await screen.findByText('提取能力暂时无法读取，请检查本地服务')
 expect(screen.queryByRole('status',{name:'正在读取提取能力'})).toBeNull()
})
