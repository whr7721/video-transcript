import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import Knowledge from '../src/Knowledge'
const overview={groups:[{kind:'audio',sources:2,passages:8},{kind:'images',sources:1,passages:4}],history:[],memories:[],budget:{calls:0,reserved_cny:0,limit_cny:20}}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('displays mixed media inventory and free local search without asking the model',async()=>{
 const f=vi.fn(async(url:any)=>Response.json(String(url).endsWith('/projects')?[]:String(url).includes('/search?')?[{id:'x',title:'摄影课程',kind:'audio',text:'光圈影响景深',url:'/studio/?task=x'}]:overview));vi.stubGlobal('fetch',f)
 render(<Knowledge/>);await screen.findByText('音视频／播客 2份／8段')
 fireEvent.change(screen.getByLabelText('你的问题'),{target:{value:'摄影光圈'}});fireEvent.click(screen.getByText('本地找资料（免费）'))
 await screen.findByText('光圈影响景深');expect(f.mock.calls.some(c=>String(c[0]).endsWith('/ask'))).toBe(false)
})
it('renders citations, gaps and tool trace from saved research',async()=>{
 const j={id:'saved',question:'气候和天气',status:'completed',trace:[{tool:'search_library',query:'NOAA',hits:1}],result:{sections:[{kind:'source',heading:'时间尺度',text:'天气短期，气候长期',citations:[{id:'p',quote:'Weather reflects short-term conditions',title:'NOAA',url:'/studio/?view=library&item=noaa',kind:'article'}]}],gaps:['仍须核对上下文']}}
 vi.stubGlobal('fetch',vi.fn(async(url:any)=>Response.json(String(url).endsWith('/projects')?[]:{...overview,history:[j]})));render(<Knowledge/>);fireEvent.click(await screen.findByRole('button',{name:/气候和天气/}))
 expect(screen.getByText('天气短期，气候长期')).toBeTruthy();expect(screen.getByText('资料陈述')).toBeTruthy();expect(screen.getByText('仍须核对上下文')).toBeTruthy();expect(screen.getByText('打开原资料').getAttribute('href')).toContain('item=noaa')
})
it('saves personal memory only after explicit user action',async()=>{
 const f=vi.fn(async(url:any)=>Response.json(String(url).endsWith('/projects')?[]:overview));vi.stubGlobal('fetch',f);render(<Knowledge/>);await screen.findByText('音视频／播客 2份／8段');expect(f).toHaveBeenCalledTimes(2)
 fireEvent.change(screen.getByLabelText('标题'),{target:{value:'学习安排'}});fireEvent.change(screen.getByLabelText('记忆内容'),{target:{value:'每周练习两次摄影'}});fireEvent.click(screen.getByText('保存／更新同名记忆'))
 await waitFor(()=>expect(f.mock.calls.some(c=>String(c[0]).endsWith('/memories'))).toBe(true))
})
