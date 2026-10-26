import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ImageReader from '../src/ImageReader'
import ImageImport from '../src/ImageImport'
import ArticleLibrary from '../src/ArticleLibrary'
import PrivateImageCapture from '../src/PrivateImageCapture'
const blocks=[{id:'image-1',type:'image',text:'',page:1,asset_status:'saved',asset_name:'one.jpg',width:100,height:200},
 {id:'image-1-r1',type:'ocr',text:'Agent上下文原话',source_image_id:'image-1',region_id:'r1',revision:1,bbox:[1,2,80,30],score:.8},
 {id:'image-2',type:'image',text:'',page:2,asset_status:'missing',asset_error:'下载失败'}]
beforeEach(()=>localStorage.clear())
afterEach(()=>{cleanup();vi.unstubAllGlobals();history.replaceState(null,'','/')})

test('ordered pages retain a missing page and locate exact OCR rectangle',async()=>{
 const locate=vi.fn(),update=vi.fn();render(<ImageReader id="one" blocks={blocks} activeBlock="image-1-r1" onLocate={locate} onUpdate={update} notify={()=>{}}/>)
 expect(screen.getByAltText('第1张原图')).toBeTruthy();expect(document.querySelector('rect')?.getAttribute('x')).toBe('1')
 fireEvent.click(screen.getByText('Agent上下文原话'));expect(locate).toHaveBeenCalledWith('image-1-r1')
 fireEvent.click(screen.getByText('下一张'));await screen.findByText('本页图片未保存：下载失败')
})
test('region draft restores original base revision and conflict keeps input',async()=>{
 localStorage.setItem('shiwen-image-region:one:image-1-r1',JSON.stringify({text:'未保存的旧校对',revision:1}))
 const notify=vi.fn(),fetcher=vi.fn(async()=>({ok:false,json:async()=>({detail:'版本冲突，未覆盖'})}));vi.stubGlobal('fetch',fetcher)
 render(<ImageReader id="one" blocks={blocks.map(b=>({...b,revision:2}))} onLocate={()=>{}} onUpdate={()=>{}} notify={notify}/>)
 fireEvent.click(screen.getByText('校对'));expect((screen.getByLabelText('校对这一区域') as HTMLTextAreaElement).value).toBe('未保存的旧校对')
 fireEvent.click(screen.getByText('保存校对'));await waitFor(()=>expect(notify).toHaveBeenCalledWith('版本冲突，未覆盖'))
 expect(JSON.parse(fetcher.mock.calls[0][1].body).revision).toBe(1)
 expect((screen.getByLabelText('校对这一区域') as HTMLTextAreaElement).value).toBe('未保存的旧校对')
})
test('local images upload in selected order and explicitly start OCR once',async()=>{
 const created=vi.fn(),calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{calls.push([url,options]);return{ok:true,json:async()=>({id:'new'})}}))
 render(<ImageImport title="截图资料" onCreated={created} notify={()=>{}}/>)
 const a=new File(['a'],'first.png',{type:'image/png'}),b=new File(['b'],'second.png',{type:'image/png'})
 fireEvent.change(screen.getByLabelText('选择图片（可多选）'),{target:{files:[a,b]}})
 fireEvent.click(screen.getByRole('button',{name:'保留原图并识字（2张）'}));await waitFor(()=>expect(created).toHaveBeenCalledWith('new'))
 expect(calls.map(c=>c[0])).toEqual(['/api/library/image-items','/api/library/image-items/new/0','/api/library/image-items/new/1','/api/library/image-items/new/recognize'])
 expect(calls[1][1].body).toBe(a);expect(calls[2][1].body).toBe(b)
})
test('private share capture uses the private adapter rather than article HTML',async()=>{
 const created=vi.fn(),fetcher=vi.fn(async()=>({ok:true,json:async()=>({id:'post'})}));vi.stubGlobal('fetch',fetcher)
 render(<PrivateImageCapture onCreated={created} notify={()=>{}}/>)
 fireEvent.change(screen.getByLabelText('抖音图文分享链接'),{target:{value:'https://v.douyin.com/sample/'}})
 fireEvent.click(screen.getByText('获取图片并识别'));await waitFor(()=>expect(created).toHaveBeenCalledWith('post'))
 expect(fetcher.mock.calls[0][0]).toBe('/api/private/image-posts')
})
test('image material adds to topic, exposes search and keeps full image source visible',async()=>{
 const item={id:'one',kind:'images',title:'面试资料',status:'ready',image_status:'completed',expected_images:2,ocr_completed:2,blocks,note:'',note_revision:0,artifacts:[],warnings:['OCR待核对'],question_status:'idle'}
 history.replaceState(null,'','/?view=library&item=one')
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/items')?[item]:url.endsWith('/materials')?{topic_id:'topic'}:item})))
 render(<ArticleLibrary/>);await screen.findByText('面试资料',{selector:'h2'})
 expect(screen.getByAltText('第1张原图')).toBeTruthy()
 fireEvent.change(screen.getByLabelText('专题名称'),{target:{value:'Agent学习'}});fireEvent.click(screen.getByText('把这份材料加入专题'))
 await screen.findByText('在专题里搜索这份材料')
 expect(screen.getByText('在专题里搜索这份材料').getAttribute('href')).toContain('view=topics&topic=topic')
 fireEvent.click(screen.getByText('提炼学习重点'));expect((screen.getByLabelText('我的问题') as HTMLTextAreaElement).value).toContain('学习重点')
})
