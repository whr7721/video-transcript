import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Library from '../src/Library'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('searches full catalog and saves star and ordered collection members',async()=>{
 const calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init:any)=>{calls.push([path,init]);return {ok:true,json:async()=>path.endsWith('/collections')?[{id:'c',name:'学习',count:0}]:path.endsWith('/members')?[]:path.includes('?')?{items:[{uid:'audio:a',id:'a',title:'量子课程',url:'/studio/?task=a',platform:'youtube',status:'completed',created_at:1,starred:false}],stats:{total:1,duration:60,recent:1,platforms:{youtube:1}}}:{ok:true}}}))
 render(<Library/>);await screen.findByRole('heading',{name:'量子课程'});fireEvent.change(screen.getByLabelText('搜索全部资料'),{target:{value:'量子'}})
 await waitFor(()=>expect(calls.some(([p])=>p.includes('q=%E9%87%8F%E5%AD%90'))).toBe(true))
 fireEvent.click(screen.getByRole('button',{name:'收藏量子课程'}));await waitFor(()=>expect(calls.some(([p,i])=>p.endsWith('/star')&&JSON.parse(i.body).uid==='audio:a')).toBe(true))
 await waitFor(()=>expect(screen.getByRole('button',{name:'收藏量子课程'}).hasAttribute('disabled')).toBe(false))
 fireEvent.click(screen.getByLabelText(/选择量子课程/));fireEvent.change(screen.getByLabelText('加入目标合集'),{target:{value:'c'}});fireEvent.click(screen.getByRole('button',{name:'加入所选 1 篇'}))
 await waitFor(()=>expect(calls.some(([p,i])=>p.endsWith('/c/members')&&i.method==='PUT'&&JSON.parse(i.body).uids[0]==='audio:a')).toBe(true))
})


test('a real API failure never silently becomes demo records',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>{throw Error('offline')}))
 render(<Library/>);await screen.findByText('资料库暂时无法读取，请检查本地服务后重试。')
 expect(screen.queryByText('把注意力留给真正重要的事')).toBeNull()
})
