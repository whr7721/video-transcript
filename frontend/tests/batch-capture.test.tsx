import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import BatchCapture from '../src/BatchCapture'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('preview displays quota warning before explicit submission',async()=>{
 const paths:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{paths.push(path);return {ok:true,json:async()=>path.endsWith('/preview')?{id:'a',status:'draft',items:[{index:1,text:'https://youtu.be/a',platform:'youtube',status:'waiting',summarize:true}],estimate:{selected:1,requests:2,remaining:1}}:[]}}))
 render(<BatchCapture onCreated={async()=>{}}/>);fireEvent.change(screen.getByLabelText('批量链接'),{target:{value:'https://youtu.be/a'}});fireEvent.click(screen.getByLabelText('同时整理与导图'));fireEvent.click(screen.getByRole('button',{name:'预览批次'}));await screen.findByText('转写将完成、整理需次日或减少勾选');expect(screen.getByText(/当日配额剩余 1/)).toBeTruthy();expect(paths.some(p=>p.endsWith('/start'))).toBe(false)
 fireEvent.click(screen.getByRole('button',{name:'确认开始'}));await vi.waitFor(()=>expect(paths).toContain('/api/link-batches/a/start'))
})
test('changing a summary selection requires a new estimate',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/preview')?{id:'a',status:'draft',items:[{index:1,text:'https://youtu.be/a',status:'waiting',summarize:true}],estimate:{selected:1,requests:2,remaining:30}}:[]})))
 render(<BatchCapture onCreated={async()=>{}}/>);fireEvent.change(screen.getByLabelText('批量链接'),{target:{value:'https://youtu.be/a'}});fireEvent.click(screen.getByRole('button',{name:'预览批次'}));await screen.findByText('确认清单');fireEvent.click(screen.getByLabelText('整理此篇'));expect((screen.getByRole('button',{name:'确认开始'}) as HTMLButtonElement).disabled).toBe(true)
})
