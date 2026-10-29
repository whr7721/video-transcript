import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import DocumentTools from '../src/DocumentTools'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('notes submit anchors and Notion is disabled without token',async()=>{
 const calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init:any)=>{calls.push([path,init]);return {ok:true,json:async()=>init.method==='POST'?{id:'n'}:{notes:[],anchors:[{id:'seg-0',text:'原文',start:5}],options:{notionConfigured:false}}}}))
 render(<DocumentTools taskId="d" onCitation={()=>{}}/>);await screen.findByText('5s · 原文');expect(screen.getByRole('button',{name:'导出 Notion 页面'}).hasAttribute('disabled')).toBe(true)
 fireEvent.change(screen.getByLabelText('笔记内容'),{target:{value:'重点'}});fireEvent.change(screen.getByLabelText('锚定原文'),{target:{value:'seg-0'}});fireEvent.click(screen.getByRole('button',{name:'添加笔记'}));await waitFor(()=>expect(calls.some(([_,i])=>i.method==='POST'&&JSON.parse(i.body).block_id==='seg-0')).toBe(true))
})
