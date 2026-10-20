import React from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ArticleLibrary from '../src/ArticleLibrary'

const item={id:'article1',title:'工具教程',author:'作者',status:'ready',source_url:'https://example.com',warnings:['完整性待核对'],completeness:'unverified',blocks:[{id:'b1',type:'code',text:'pip install demo\n  --flag'},{id:'b2',type:'image',text:'图示',asset_status:'missing',asset_error:'来源无法读取',url:'https://example.com/img.png'}],note:'已有笔记',note_revision:1,question_status:'idle',artifacts:[]}
function mock(){
 const calls:{path:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  calls.push({path,init})
  return new Response(JSON.stringify(path.endsWith('/items')&&init?.method!=='POST'?[item]:item),{status:200,headers:{'Content-Type':'application/json'}})
 }))
 return calls
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();history.replaceState(null,'','/')})

it('renders exact source code, missing images and does not auto-call AI',async()=>{
 history.replaceState(null,'','/studio/?view=library&item=article1');const calls=mock();render(<ArticleLibrary/>);
 await screen.findByText('pip install demo --flag',{exact:false})
 expect(screen.getByText(/图片未保存/)).toBeTruthy()
 expect(calls.some(c=>c.path.endsWith('/question'))).toBe(false)
 expect(screen.getByLabelText('个人笔记')).toHaveProperty('value','已有笔记')
})

it('imports pasted source explicitly without passing it through audio',async()=>{
 const calls=mock();render(<ArticleLibrary/>);fireEvent.click(screen.getByRole('button',{name:'导入图文'}));
 fireEvent.change(screen.getByLabelText('导入方式'),{target:{value:'text'}})
 fireEvent.change(screen.getByLabelText('正文内容'),{target:{value:'原始文章内容，不做改写。'}})
 fireEvent.click(screen.getByRole('button',{name:'导入并保留原文'}))
 await waitFor(()=>expect(calls.some(c=>c.init?.method==='POST')).toBe(true))
 const create=calls.find(c=>c.init?.method==='POST')!
 expect(create.path).toBe('/api/library/items')
 expect(JSON.parse(create.init!.body as string)).toMatchObject({kind:'text',content:'原始文章内容，不做改写。'})
})

it('keeps personal input after a version conflict',async()=>{
 history.replaceState(null,'','/studio/?view=library&item=article1');mock();render(<ArticleLibrary/>);
 const field=await screen.findByLabelText('个人笔记');fireEvent.change(field,{target:{value:'不能丢失的新输入'}})
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:'笔记已有更新'}),{status:409})))
 fireEvent.click(screen.getByRole('button',{name:'保存笔记'}));await screen.findByText('笔记已有更新')
 expect(field).toHaveProperty('value','不能丢失的新输入')
 expect(localStorage.getItem('shiwen-article-note-article1')).toBe('不能丢失的新输入')
})
