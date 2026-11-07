import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import Classification from '../src/Classification'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('closed classification does not call model or load data',()=>{const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<Classification uid="audio:a" onSaved={()=>{}}/>);expect(screen.getByText('待分类')).toBeTruthy();expect(fetch).not.toHaveBeenCalled()})
test('manual correction is free and keeps primary separate from topics',async()=>{
 const calls:any[]=[];vi.stubGlobal('fetch',vi.fn(async(_p:string,init:any)=>{calls.push(init);return {ok:true,json:async()=>({revision:init.method==='PUT'?1:0,status:'ready',manual:init.method==='PUT'?{primary:'tutorial',secondary:null,topics:['软件']}:null})}}))
 render(<Classification uid="audio:a" onSaved={()=>{}}/>);const details=screen.getByText('待分类').closest('details')!;details.open=true;fireEvent(details,new Event('toggle'));await screen.findByText('AI分类为建议，可修改后保存');fireEvent.change(screen.getByLabelText('主类型'),{target:{value:'tutorial'}});fireEvent.change(screen.getByLabelText('话题（用顿号分隔，最多5个）'),{target:{value:'软件'}});fireEvent.click(screen.getByRole('button',{name:'保存人工分类（免费）'}));await screen.findByText('人工已确认');expect(calls.some(c=>c.method==='POST')).toBe(false)
})
test('polling newer revisions cannot silently authorize an old draft overwrite',async()=>{
 let read=0,posted:any;vi.stubGlobal('fetch',vi.fn(async(_p:string,init:any)=>{if(init.method==='PUT'){posted=JSON.parse(init.body);return {ok:false,json:async()=>({detail:'分类已有更新'})}}read++;return {ok:true,json:async()=>({revision:read>1?1:0,status:'ready'})}}))
 render(<Classification uid="audio:a" onSaved={()=>{}}/>);const details=screen.getByText('待分类').closest('details')!;details.open=true;fireEvent(details,new Event('toggle'));await screen.findByText('AI分类为建议，可修改后保存');fireEvent.change(screen.getByLabelText('主类型'),{target:{value:'tutorial'}});await new Promise(r=>setTimeout(r,2100));fireEvent.click(screen.getByRole('button',{name:'保存人工分类（免费）'}));await screen.findByText('分类已有更新');expect(posted.revision).toBe(0)
})
