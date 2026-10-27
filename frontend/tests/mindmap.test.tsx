import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Mindmap from '../src/Mindmap'
import {mapData,exportSvg} from '../src/mindmap-render'
vi.mock('markmap-view',()=>({Markmap:{create:()=>({setData:vi.fn(async()=>{}),fit:vi.fn(async()=>{}),rescale:vi.fn(),destroy:vi.fn()})}}))
const tree={text:'测试主题',children:[{text:'第一分支',children:[]},{text:'中文换行与细节',children:[]}]}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('opening a cached map never fetches or generates and keyboard outline remains readable',async()=>{
 const fetcher=vi.fn(),generate=vi.fn();vi.stubGlobal('fetch',fetcher)
 render(<Mindmap jobs={[{id:'saved',status:'completed',mindmap:tree}]} busy={false} onGenerate={generate} notify={()=>{}}/>)
 expect(screen.getByText('测试主题',{selector:'h2'})).toBeTruthy()
 fireEvent.click(screen.getByText('查看文字大纲'));expect(screen.getByText('第一分支')).toBeTruthy()
 await waitFor(()=>expect((screen.getByRole('button',{name:'适应窗口'}) as HTMLButtonElement).disabled).toBe(false))
 expect(fetcher).not.toHaveBeenCalled();expect(generate).not.toHaveBeenCalled()
 expect(screen.getByRole('link',{name:'下载 Markdown 大纲'}).getAttribute('href')).toContain('/generations/saved/')
 fireEvent.click(screen.getByRole('button',{name:'放大查看'}))
 expect(screen.getByRole('dialog')).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'关闭大图'}));expect(screen.queryByRole('dialog')).toBeNull()
})
test('a failed newer map keeps the older result and retry is explicit',()=>{
 const generate=vi.fn()
 render(<Mindmap jobs={[{id:'new',status:'failed',error:'结构不合格'},{id:'old',status:'completed',mindmap:tree}]} busy={false} onGenerate={generate} notify={()=>{}}/>)
 expect(screen.getByText('测试主题',{selector:'h2'})).toBeTruthy();expect(generate).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'重试生成'}));expect(generate).toHaveBeenCalledTimes(1)
})
test('blocked source cannot submit generation',()=>{
 const generate=vi.fn()
 render(<Mindmap jobs={[]} blocked="超过24000字" busy={false} onGenerate={generate} notify={()=>{}}/>)
 fireEvent.click(screen.getByRole('button',{name:'生成思维导图'}));expect(generate).not.toHaveBeenCalled()
})
test('renderer escapes label markup and PNG SVG contains plain text for every descendant',()=>{
 expect(mapData({text:'<img src=x onerror=bad()> &',children:[]}).content).toContain('&lt;img')
 function node(text:string,x:number,y:number,children:any[]=[]):any{return {content:mapData({text,children:[]}).content,children,state:{rect:{x,y,width:120,height:44}}}}
 const child=node('中文完整分支',180,40),root=node('根',0,0,[child])
 const exported=exportSvg({state:{rect:{x1:0,x2:300,y1:0,y2:84},data:root},options:{color:()=> '#123456'}} as any,text=>text.length*14)
 expect(exported.text).toContain('中文完整分支');expect(exported.text).not.toContain('foreignObject')
 expect(exported.text).not.toContain('<script');expect(exported.width).toBe(364)
 expect(new DOMParser().parseFromString(exported.text,'image/svg+xml').querySelector('parsererror')).toBeNull()
})
