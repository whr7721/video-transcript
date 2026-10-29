import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import DocumentChat from '../src/DocumentChat'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('loads history sends question and opens checked original citation',async()=>{
 const open=vi.fn(),posts:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(_path:string,init:any)=>({ok:true,json:async()=>{if(init?.method==='POST'){posts.push(JSON.parse(init.body));return {id:posts[0].id,question:'如何浇水',status:'completed',answer:{unknown:false,sections:[{text:'先检查土壤',citations:[{block_id:'seg-0',offset:0,quote:'土壤潮湿时不要浇水',start:10}]}]}}}return []}})))
 render(<DocumentChat taskId="a" onCitation={open}/>);await screen.findByRole('button',{name:'检查状态'});fireEvent.change(screen.getByLabelText('关于这篇的问题'),{target:{value:'如何浇水'}});fireEvent.click(screen.getByRole('button',{name:'发送追问'}));await screen.findByText('先检查土壤');expect(posts).toHaveLength(1);fireEvent.click(screen.getByRole('button',{name:/seg-0 · 0:10/}));expect(open).toHaveBeenCalledWith('seg-0')
})
test('switching document clears history and ignores old response',async()=>{
 let resolve:any;vi.stubGlobal('fetch',vi.fn((path:string)=>path.endsWith('/a')?new Promise(r=>{resolve=r}):Promise.resolve({ok:true,json:async()=>[]})))
 const {rerender}=render(<DocumentChat taskId="a" onCitation={()=>{}}/>);rerender(<DocumentChat taskId="b" onCitation={()=>{}}/>);resolve({ok:true,json:async()=>[{id:'old',question:'旧篇问题',status:'completed',answer:{unknown:true,text:'旧篇答案'}}]});await waitFor(()=>expect(screen.queryByText('旧篇答案')).toBeNull())
})
