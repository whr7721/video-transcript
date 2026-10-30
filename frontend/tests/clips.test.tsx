import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Clips,{CollectionClips} from '../src/Clips'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('missing media is explicit and cannot submit a paid selection',async()=>{
 const fetch=vi.fn(async()=>({ok:true,json:async()=>({status:'empty',clips:[],available:false,reason:'有文稿但没有可用媒体'})}));vi.stubGlobal('fetch',fetch)
 render(<Clips taskId="a"/>);expect(await screen.findByText('有文稿但没有可用媒体')).toBeTruthy();expect(screen.queryByRole('button',{name:'生成金句切片'})).toBeNull();expect(fetch.mock.calls).toHaveLength(1)
})
test('generation uses count and shows bilingual video and zip',async()=>{
 const posts:any[]=[];vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init)posts.push(JSON.parse(String(init.body)));return {ok:true,json:async()=>init?{status:'completed',clips:[{index:1,zh:'保持好奇',en:'Stay curious',start:0,end:2,duration:2,status:'completed',url:'/clip.mp4'}]}:{status:'empty',available:true,clips:[],quota:{remaining:30}}}}))
 render(<Clips taskId="a"/>);fireEvent.change(await screen.findByLabelText('切片数量'),{target:{value:'3'}});fireEvent.click(screen.getByRole('button',{name:'生成金句切片'}));expect(await screen.findByText('Stay curious')).toBeTruthy();expect(posts[0].count).toBe(3);expect(screen.getByLabelText('金句切片 1').getAttribute('src')).toBe('/clip.mp4');expect(screen.getByRole('link',{name:'全部下载 ZIP'})).toBeTruthy()
})
test('collection previews quota before user starts and renders individual failures',async()=>{
 let posts=0;vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{if(init)posts++;return {ok:true,json:async()=>path.endsWith('preview')?{requests:2,quota:{remaining:1}}:{items:init?[{uid:'audio:a',result:{status:'failed',error:'额度不足'}}]:[],status:init?'completed':'empty'}}}))
 render(<CollectionClips collectionId="b"/>);await screen.findByText(/预计约 2 次模型请求/);expect(posts).toBe(0);fireEvent.click(screen.getByRole('button',{name:'批量切片（每篇3条）'}));await waitFor(()=>expect(posts).toBe(1));expect(await screen.findByText(/audio:a · 额度不足/)).toBeTruthy()
})
