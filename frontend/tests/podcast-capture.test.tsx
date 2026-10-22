import React from 'react'
import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import PodcastCapture from '../core/PodcastCapture'
let calls:{path:string;init?:RequestInit}[]
const feed={id:'a'.repeat(16),title:'技术访谈',feed_url:'https://example.org/rss',truncated:false,episodes:[{id:'ep',title:'AI 工具的一次真实实践',published:'',duration_seconds:3600,audio_url:'https://example.org/a.mp3',transcripts:[{url:'https://example.org/t.vtt',type:'text/vtt'}],importable:true}]}
beforeEach(()=>{calls=[];localStorage.clear();vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{calls.push({path,init});return {ok:true,json:async()=>path.endsWith('/feeds')?feed:{id:'b'.repeat(16),status:'accepted',bytes:1234,task_id:'c'.repeat(16),message:'节目文字已入库'}}}))})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function preview(){fireEvent.change(screen.getByLabelText('公开 RSS 地址'),{target:{value:'https://example.org/rss'}});fireEvent.click(screen.getByRole('button',{name:'读取列表'}));await screen.findByText('技术访谈')}
test('preview and selection do not start download; explicit confirmation uses text path',async()=>{
 const open=vi.fn(async()=>{});render(<PodcastCapture onCreated={open} notify={()=>{}}/>);await preview()
 expect(calls.every(c=>!c.path.endsWith('/imports'))).toBe(true)
 fireEvent.click(screen.getByRole('radio'));expect((screen.getByLabelText('导入方式') as HTMLSelectElement).value).toBe('text')
 expect(calls.every(c=>!c.path.endsWith('/imports'))).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'确认导入这一集'}));await screen.findByText('这一集已接收')
 const sent=JSON.parse(calls.find(c=>c.path.endsWith('/imports'))!.init!.body as string);expect(sent.mode).toBe('text');expect(sent.episode_id).toBe('ep')
 expect(open).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'打开文稿与进度'}));await waitFor(()=>expect(open).toHaveBeenCalledWith('c'.repeat(16)))
})
test('cancel waits for server state and displays acknowledged cleanup',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>({ok:true,json:async()=>path.endsWith('/feeds')?feed:init?.method==='DELETE'?{id:'b'.repeat(16),status:'cancelled',message:'已取消并清理',bytes:0}:{id:'b'.repeat(16),status:'running',message:'正在获取',bytes:2000}})))
 render(<PodcastCapture onCreated={async()=>{}} notify={()=>{}}/>);await preview();fireEvent.click(screen.getByRole('radio'));fireEvent.click(screen.getByRole('button',{name:'确认导入这一集'}));await screen.findByText('这一集正在后台获取');fireEvent.click(screen.getByRole('button',{name:'取消获取'}));await screen.findByText('已取消并清理');expect(screen.getByRole('button',{name:'重新获取这一集'})).toBeTruthy()
})
test('invalid feed error is inline and no import is submitted',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({detail:'需要公开RSS地址'})})))
 render(<PodcastCapture onCreated={async()=>{}} notify={()=>{}}/>);fireEvent.change(screen.getByLabelText('公开 RSS 地址'),{target:{value:'https://example.org/page'}});fireEvent.click(screen.getByRole('button',{name:'读取列表'}));expect((await screen.findByRole('alert')).textContent).toContain('需要公开RSS地址')
})
test('long list renders at most twenty rows and can be paged',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({...feed,episodes:Array.from({length:42},(_,i)=>({...feed.episodes[0],id:String(i),title:'第'+i+'集'}))})})))
 render(<PodcastCapture onCreated={async()=>{}} notify={()=>{}}/>);await preview();expect(screen.getAllByRole('radio')).toHaveLength(20);fireEvent.click(screen.getByRole('button',{name:'下一页'}));expect(screen.getByText('第20集')).toBeTruthy();expect(screen.queryByText('第0集')).toBeNull()
})
