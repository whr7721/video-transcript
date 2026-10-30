import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {ProductApp} from '../src/main'
afterEach(()=>{cleanup();vi.unstubAllGlobals();history.replaceState(null,'','/');localStorage.clear()})
test('default entry ignores remembered document and renders input before recent cards',async()=>{
 history.replaceState(null,'','/studio/');localStorage.setItem('shiwen-selected','old');const paths:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{paths.push(path);return {ok:true,json:async()=>path==='/api/tasks'?[{id:'old',title:'最近的视频',status:'completed',created_at:1,source:{platform:'youtube'}}]:path.endsWith('capabilities')?{platforms:['youtube','rss']}:[]}}))
 render(<ProductApp/>);expect(await screen.findByLabelText('粘贴链接，直接读内容')).toBeTruthy();expect(await screen.findByRole('link',{name:/最近的视频/})).toBeTruthy();expect(screen.getByRole('link',{name:/最近的视频/}).getAttribute('href')).toBe('/studio/?task=old');expect(paths.some(p=>p.includes('/api/studio/documents/'))).toBe(false);expect(screen.queryByLabelText('文稿库')).toBeNull()
})
test('empty homepage explains supported input without advertising local paths',async()=>{
 history.replaceState(null,'','/studio/');vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('capabilities')?{platforms:['youtube']}:[]})))
 render(<ProductApp/>);expect(await screen.findByText('粘贴一个视频或播客链接，开始第一篇文稿。')).toBeTruthy();expect(screen.getByRole('link',{name:'＋ 批量'}).getAttribute('href')).toBe('/studio/?view=batch')
})
test('cached input uses existing link submission and displays the completed task card',async()=>{
 history.replaceState(null,'','/studio/');const posts:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init?.method==='POST')posts.push(path);return {ok:true,json:async()=>path.endsWith('capabilities')?{platforms:['youtube']}:init?.method==='POST'?{id:'job',task_id:'task',status:'completed',stage:'done',cached:true}:[]}}))
 render(<ProductApp/>);const input=await screen.findByLabelText('粘贴链接，直接读内容');fireEvent.change(input,{target:{value:'https://youtu.be/cache'}});fireEvent.keyDown(input,{key:'Enter'});expect(await screen.findByRole('button',{name:'打开文稿'})).toBeTruthy();expect(posts).toEqual(['/api/link'])
})
test('batch route reuses and opens the existing batch panel',async()=>{
 history.replaceState(null,'','/studio/?view=batch');vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>[]})))
 render(<ProductApp/>);expect(screen.getByLabelText('批量链接')).toBeTruthy();expect(document.querySelector('details')?.open).toBe(true)
})

test('an explicit task parameter still mounts the original workbench',async()=>{
 history.replaceState(null,'','/studio/?task=explicit');vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path==='/api/studio/buffer'?{capacity_bytes:5e9,used_bytes:0}:[]})))
 render(<ProductApp/>);expect(await screen.findByLabelText('文稿库')).toBeTruthy();expect(screen.queryByRole('heading',{name:'拾文 · 把视频读成文字'})).toBeNull()
})
test('home settings saves through the existing endpoint and clears entered keys',async()=>{
 history.replaceState(null,'','/studio/?view=settings');let posted:any
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init?.method==='POST')posted=JSON.parse(String(init.body));return {ok:true,json:async()=>path==='/api/settings'?{key_configured:!!posted,search_key_configured:false}:{status:'not_logged_in'}}}))
 render(<ProductApp/>);const input=await screen.findByLabelText(/硅基流动 API Key/);fireEvent.change(input,{target:{value:'fixture-key'}});fireEvent.click(screen.getByRole('button',{name:'保存设置'}));await screen.findByText('设置已保存。');expect(posted.api_key).toBe('fixture-key');expect((input as HTMLInputElement).value).toBe('')
})

test.each([['discovery','图文资料'],['knowledge','AI 资料助手'],['topics','发现话题'],['library','图文素材库']])('tool route %s keeps the shared desk navigation',async(view,title)=>{
 history.replaceState(null,'','/studio/?view='+view)
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/overview')?{groups:[],history:[],memories:[],budget:{calls:0,reserved_cny:0,limit_cny:20}}:[]})))
 render(<ProductApp/>);expect(screen.getByRole('navigation',{name:'主导航'})).toBeTruthy();expect(screen.getByRole('heading',{name:title,exact:true})).toBeTruthy();expect(document.querySelector('.desk-sidebar a[aria-current=page]')?.getAttribute('href')).toBe('/studio/?view='+view)
 expect(document.querySelectorAll('main').length).toBe(1)
 await screen.findByRole('heading',{name:title,exact:true})
})
