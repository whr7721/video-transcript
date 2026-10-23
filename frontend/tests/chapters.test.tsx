import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ChapterNavigation from '../src/ChapterNavigation'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const plan={revision:0,source_hash:'hash',fragment_limit:1200,origin:'reading',stale:false,sections:[{title:'阅读分段 1',kind:'reading',fragment_ids:['seg-1:0:4']}]}
test('directory read is free of writes; precise range selected only on click',async()=>{
 const calls:string[]=[];const locate=vi.fn()
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return{ok:true,json:async()=>url.endsWith('/text')?{ranges:[{source_id:'seg-1',start_offset:0,end_offset:4,text:'重复句。'}]}:plan}}))
 render(<ChapterNavigation taskId="sample" onLocate={locate}/>);await screen.findByRole('button',{name:'阅读分段 1'})
 expect(calls).toEqual(['/api/studio/documents/sample/chapters','/api/studio/documents/sample/chapter-jobs'])
 fireEvent.click(screen.getByRole('button',{name:'阅读分段 1'}));await screen.findByText('重复句。')
 expect(locate).toHaveBeenCalledWith(expect.objectContaining({source_id:'seg-1'}))
})
test('stale source prevents chapter navigation',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({...plan,stale:true})})))
 render(<ChapterNavigation taskId="sample" onLocate={()=>{}}/>);await screen.findByRole('alert')
 expect(screen.queryByRole('button',{name:'阅读分段 1'})).toBeNull()
})
test('official fetch requires explicit click and shows errors',async()=>{
 const fetcher=vi.fn(async(_url:string,init?:RequestInit)=>({ok:!init,json:async()=>init?{detail:'没有官方目录'}:plan}));vi.stubGlobal('fetch',fetcher)
 render(<ChapterNavigation taskId="sample" onLocate={()=>{}}/>);await screen.findByRole('button',{name:'加载节目官方目录'})
 expect(fetcher).toHaveBeenCalledTimes(2)
 fireEvent.click(screen.getByRole('button',{name:'加载节目官方目录'}));await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('没有官方目录'))
})

test('AI budget preview does not start paid generation until confirmation',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return {ok:true,json:async()=>url.endsWith('/chapter-estimate')?{max_calls:3,cached_windows:2,quota:{remaining:8}}:url.endsWith('/chapter-jobs')?(init?{id:'job',action:'directory',status:'paused',base_revision:0,error:'额度耗尽，窗口保留'}:[]):plan}}))
 render(<ChapterNavigation taskId="sample" onLocate={()=>{}}/>);await screen.findByRole('button',{name:'生成 AI 章节导读'})
 fireEvent.click(screen.getByRole('button',{name:'生成 AI 章节导读'}));await screen.findByRole('button',{name:'确认生成章节导读'})
 expect(calls.some(c=>c.url.endsWith('/chapter-jobs')&&c.init?.method==='POST')).toBe(false)
 fireEvent.click(screen.getByRole('button',{name:'确认生成章节导读'}));await screen.findByText('额度耗尽，窗口保留')
 expect(calls.filter(c=>c.url.endsWith('/chapter-jobs')&&c.init?.method==='POST')).toHaveLength(1)
})

test('chapter research sends exact source range with code point offsets',async()=>{
 const research=vi.fn()
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/chapter-jobs')?[]:url.endsWith('/text')?{ranges:[{source_id:'seg-1',start_offset:0,end_offset:6,text:'🙂重复句。'}]}:{...plan,revision:2}})))
 render(<ChapterNavigation taskId="sample" onLocate={()=>{}} onResearch={research}/>);await screen.findByRole('button',{name:'阅读分段 1'})
 fireEvent.click(screen.getByRole('button',{name:'阅读分段 1'}));await screen.findByText('🙂重复句。')
 fireEvent.click(screen.getByRole('button',{name:'研究本章原话'}))
 expect(research).toHaveBeenCalledWith(expect.objectContaining({basis:'chapter',chapter_revision:2,chapter_index:0,selection_start:0,selection:'🙂重复句。'}))
})
