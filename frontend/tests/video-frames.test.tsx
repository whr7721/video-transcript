import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import VideoFrames from '../src/VideoFrames'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('audio gives a clear unsupported reason',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({available:false,frames:[],reason:'音频任务不支持画面'})})))
 render(<VideoFrames taskId="a"/>);expect(await screen.findByText('音频任务不支持画面')).toBeTruthy();expect(screen.queryByRole('button',{name:'提取关键帧（免费）'})).toBeNull()
})
test('frame extraction and visual calls require separate clicks',async()=>{
 const posts:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init:any)=>{if(init)posts.push([path,JSON.parse(init.body)]);return {ok:true,json:async()=>({available:true,status:'ready',frames:path.endsWith('/extract')?[{index:0,timestamp:0,thumbnail:'/frame.jpg',status:'pending'}]:[]})}}))
 render(<VideoFrames taskId="a"/>);await screen.findByRole('button',{name:'提取关键帧（免费）'});fireEvent.click(screen.getByRole('button',{name:'提取关键帧（免费）'}));await screen.findByAltText('0秒关键帧');expect(posts).toHaveLength(1);fireEvent.click(screen.getByRole('button',{name:'描述所选 1 帧（模型请求）'}));await waitFor(()=>expect(posts[1][0]).toContain('/describe'))
})
