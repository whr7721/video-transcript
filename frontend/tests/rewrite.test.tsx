import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Rewrite from '../src/Rewrite'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('platform selection estimates only cache misses and does not auto-generate',async()=>{
 let posts=0;vi.stubGlobal('fetch',vi.fn(async(_p:string,init:any)=>{if(init?.method==='POST')posts++;return {ok:true,json:async()=>({versions:[],cached_styles:['xiaohongshu'],quota:{remaining:3}})}}))
 render(<Rewrite taskId="a"/>);await screen.findByText(/预计 0 次请求/);fireEvent.click(screen.getByLabelText('知乎回答'));await screen.findByText(/预计 1 次请求/);expect(posts).toBe(0);fireEvent.click(screen.getByRole('button',{name:'生成所选平台版本'}));await waitFor(()=>expect(posts).toBe(1))
})
test('edits remain intact during polling and conflict preserves entered text',async()=>{
 const v={id:'v',style:'xiaohongshu',status:'completed',text:'模型初稿',revision:0,result:{blocks:[],reused_quotes:[],notes:[]},original:'模型初稿'}
 vi.stubGlobal('fetch',vi.fn(async(_p:string,init:any)=>({ok:init?.method!=='PUT',json:async()=>init?.method==='PUT'?{detail:'版本已变化，请刷新'}:{versions:[v],cached_styles:['xiaohongshu'],quota:{remaining:3}}})))
 render(<Rewrite taskId="a"/>);const input=await screen.findByLabelText('小红书笔记正文');fireEvent.change(input,{target:{value:'我的改稿'}});fireEvent.click(screen.getByRole('button',{name:'保存版本'}));await screen.findByText('版本已变化，请刷新');expect((input as HTMLTextAreaElement).value).toBe('我的改稿')
})
