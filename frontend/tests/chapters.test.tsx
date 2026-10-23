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
 expect(calls).toEqual(['/api/studio/documents/sample/chapters'])
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
 expect(fetcher).toHaveBeenCalledTimes(1)
 fireEvent.click(screen.getByRole('button',{name:'加载节目官方目录'}));await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('没有官方目录'))
})
