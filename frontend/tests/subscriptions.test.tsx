import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ExpandSources from '../src/ExpandSources'
import Subscriptions from '../src/Subscriptions'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('topic confirmation precedes enumeration and selected links enter existing preview',async()=>{
 const bodies:any[]=[];const callback=vi.fn()
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{const body=JSON.parse(String(init?.body));bodies.push(body);return {ok:true,json:async()=>path.endsWith('/batch')?{id:'draft'}:body.confirm_topics?{id:'source',groups:[{title:'话题',status:'ok',items:[{key:'1',title:'第一条'},{key:'2',title:'第二条'}]}]}:{confirmation_required:true,topics:['Python']}}}))
 render(<ExpandSources text="Python" language="auto" summarize={false} onPreview={callback}/>);fireEvent.click(screen.getByRole('button',{name:'展开来源'}));await screen.findByText(/以下无URL文字/);expect(bodies.length).toBe(1);expect(bodies[0].confirm_topics).toBe(false)
 fireEvent.click(screen.getByRole('button',{name:'确认作为抖音话题搜索'}));await screen.findByText('第一条');fireEvent.click(screen.getByLabelText('第一条'));fireEvent.click(screen.getByRole('button',{name:'将所选内容放入批量预览'}));await waitFor(()=>expect(callback).toHaveBeenCalledWith({id:'draft'}));expect(bodies[2].keys).toEqual(['1'])
})
test('subscription page loads local state without automatically checking sources',async()=>{
 const calls:{path:string;method?:string}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{calls.push({path,method:init?.method});return {ok:true,json:async()=>path.endsWith('/channels')?[{id:'one',title:'我的播客',platform:'rss',status:'idle'}]:[]}}))
 render(<Subscriptions/>);await screen.findByRole('heading',{name:'我的播客'});expect(calls.every(c=>c.method==='GET')).toBe(true);fireEvent.click(screen.getByRole('button',{name:'检查更新'}));await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/one/check')&&c.method==='POST')).toBe(true))
})

test('favorites source is explicit and automatic extraction requires a first preview',async()=>{
 const calls:{path:string;body:any;method:string}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{calls.push({path,body:init?.body?JSON.parse(String(init.body)):null,method:init?.method||'GET'});return {ok:true,json:async()=>path.endsWith('/channels')?[{id:'saved',title:'我的抖音收藏',platform:'douyin_favorites',status:'idle'}]:path.endsWith('/feed?unread=true')?[]:{id:'saved'}}}))
 render(<Subscriptions/>);await screen.findByRole('heading',{name:'我的抖音收藏'});fireEvent.click(screen.getByRole('button',{name:'添加我的抖音收藏'}));await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/favorites')&&c.method==='POST')).toBe(true));fireEvent.click(screen.getByRole('button',{name:'收集设置'}));expect((screen.getByLabelText('新增内容自动提取（不整理）') as HTMLInputElement).disabled).toBe(true)
})

test('collection automation settings save without requesting AI summarization',async()=>{
 const calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{calls.push({path,method:init?.method,body:init?.body?JSON.parse(String(init.body)):null});return {ok:true,json:async()=>path.endsWith('/channels')?[{id:'saved',title:'我的抖音收藏',platform:'douyin_favorites',status:'idle',initialized:true}]:[]}}))
 render(<Subscriptions/>);await screen.findByRole('heading',{name:'我的抖音收藏'});fireEvent.click(screen.getByRole('button',{name:'收集设置'}));fireEvent.click(screen.getByLabelText('开启定时检查'));fireEvent.click(screen.getByLabelText('新增内容自动提取（不整理）'));fireEvent.click(screen.getByRole('button',{name:'保存收集设置'}));await waitFor(()=>expect(calls.find(c=>c.method==='PUT')?.body).toEqual({enabled:true,auto_extract:true,interval_minutes:60,daily_limit:10,limit:20}))
})
