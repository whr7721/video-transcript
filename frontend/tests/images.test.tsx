import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ImageReader from '../src/ImageReader'
import ImageImport from '../src/ImageImport'
import ArticleLibrary from '../src/ArticleLibrary'
import PrivateImageCapture from '../src/PrivateImageCapture'
import OcrEvaluation from '../src/OcrEvaluation'
import ImageEditorial from '../src/ImageEditorial'
const blocks=[{id:'image-1',type:'image',text:'',page:1,asset_status:'saved',asset_name:'one.jpg',width:100,height:200},
 {id:'image-1-r1',type:'ocr',text:'Agent上下文原话',source_image_id:'image-1',region_id:'r1',revision:1,bbox:[1,2,80,30],score:.8},
 {id:'image-2',type:'image',text:'',page:2,asset_status:'missing',asset_error:'下载失败'}]
const reading={revision:0,source_hash:'hash',counts:{fold:1},regions:[{...blocks[1],category:'body',state:'fold',reason:'低分',origin:'rule',source_key:'key',uncertain:false}]}
beforeEach(()=>localStorage.clear())
afterEach(()=>{cleanup();vi.unstubAllGlobals();history.replaceState(null,'','/')})

test('ordered pages retain a missing page and locate exact OCR rectangle',async()=>{
 const locate=vi.fn(),update=vi.fn();render(<ImageReader id="one" blocks={blocks} reading={reading} activeBlock="image-1-r1" onLocate={locate} onUpdate={update} notify={()=>{}}/>)
 expect(screen.getByAltText('第1张原图')).toBeTruthy();expect(document.querySelector('rect')?.getAttribute('x')).toBe('1')
 fireEvent.click(screen.getByText('Agent上下文原话'));expect(locate).toHaveBeenCalledWith('image-1-r1')
 fireEvent.click(screen.getByText('下一张'));await screen.findAllByText('本页图片未保存：下载失败')
})
test('region draft restores original base revision and conflict keeps input',async()=>{
 localStorage.setItem('shiwen-image-region:one:image-1-r1',JSON.stringify({text:'未保存的旧校对',revision:1}))
 const notify=vi.fn(),fetcher=vi.fn(async()=>({ok:false,json:async()=>({detail:'版本冲突，未覆盖'})}));vi.stubGlobal('fetch',fetcher)
 render(<ImageReader id="one" blocks={blocks.map(b=>({...b,revision:2}))} onLocate={()=>{}} onUpdate={()=>{}} notify={notify}/>)
 fireEvent.click(screen.getByText('查看本页原图与区域'));fireEvent.click(screen.getByText('校对'));expect((screen.getByLabelText('校对这一区域') as HTMLTextAreaElement).value).toBe('未保存的旧校对')
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
 const item={id:'one',kind:'images',title:'面试资料',status:'ready',image_status:'completed',expected_images:2,ocr_completed:2,reading,blocks,note:'',note_revision:0,artifacts:[],warnings:['OCR待核对'],question_status:'idle'}
 history.replaceState(null,'','/?view=library&item=one')
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/items')?[item]:url.endsWith('/materials')?{topic_id:'topic'}:item})))
 render(<ArticleLibrary/>);await screen.findByText('面试资料',{selector:'h2'})
 expect(screen.queryByAltText('第1张原图')).toBeNull()
 expect(screen.getByRole('button',{name:'完整整理稿'}).getAttribute('aria-pressed')).toBe('true')
 fireEvent.click(screen.getByRole('button',{name:'原图与识别稿'}))
 fireEvent.click(screen.getByText('查看本页原图与区域'));expect(screen.getByAltText('第1张原图')).toBeTruthy()
 fireEvent.change(screen.getByLabelText('专题名称'),{target:{value:'Agent学习'}});fireEvent.click(screen.getByText('把这份材料加入专题'))
 await screen.findByText('在专题里搜索这份材料')
 expect(screen.getByText('在专题里搜索这份材料').getAttribute('href')).toContain('view=topics&topic=topic')
 fireEvent.click(screen.getByText('提炼学习重点'));expect((screen.getByLabelText('我的问题') as HTMLTextAreaElement).value).toContain('学习重点')
})

test('clean reading defaults to original text and low-score regions stay folded',()=>{
 const clean={...reading,regions:[{...reading.regions[0],text:'机器原字不纠正',state:'keep'},{...reading.regions[0],id:'low',text:'疑难词',state:'fold'}]}
 render(<ImageReader id="one" blocks={blocks} reading={clean} onLocate={()=>{}} onUpdate={()=>{}} notify={()=>{}}/>)
 expect(screen.queryByAltText('第1张原图')).toBeNull()
 expect(screen.getByText('机器原字不纠正')).toBeTruthy();expect(screen.queryByText('疑难词')).toBeNull()
 fireEvent.click(screen.getByText('展开本页 1 处识别存疑'));expect(screen.getByText('疑难词')).toBeTruthy()
 fireEvent.click(screen.getByText('查看本页原图与区域'));expect(screen.getByRole('complementary',{name:'第1页原始OCR对照'})).toBeTruthy()
 fireEvent.click(screen.getByText('关闭对照'));expect(screen.queryByAltText('第1张原图')).toBeNull()
})

test('human evaluation does not prefill a model category or save until explicitly confirmed',async()=>{
 const metric={human_confirmed:0,pending:1,splits:{holdout:{n:0,body_exclusion_rate:null,body_fold_rate:null,noise_removal_rate:null}}}
 const report={rows:[{id:'r1',item_id:'one',title:'样本',page:1,text:'OCR原字',source_key:'source',split:'holdout',width:100,height:500,bbox:[1,150,90,170],asset_name:'one.jpg'}],stale_samples:0,comparisons:{all:metric,rules:metric,ai:metric}}
 const calls:any[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{calls.push([url,options]);return{ok:true,json:async()=>report}}))
 render(<OcrEvaluation notify={()=>{}}/>);await screen.findByText('OCR原字')
 expect((screen.getByLabelText('人工判断') as HTMLSelectElement).value).toBe('')
 expect(calls.length).toBe(1)
 fireEvent.change(screen.getByLabelText('人工判断'),{target:{value:'body'}})
 expect(calls.length).toBe(1)
 fireEvent.click(screen.getByText('确认标签并继续'));await waitFor(()=>expect(calls.length).toBe(2))
 expect(JSON.parse(calls[1][1].body)).toMatchObject({category:'body',revision:0,source_key:'source'})
})

test('editorial reading never charges on mount and an explicit click generates the whole document',async()=>{
 const update=vi.fn(),fetcher=vi.fn(async()=>({ok:true,json:async()=>({id:'one',editorial:{status:'queued'}})}));vi.stubGlobal('fetch',fetcher)
 render(<ImageEditorial id="one" mode="article" onUpdate={update} onSource={()=>{}} notify={()=>{}}/>)
 expect(fetcher).not.toHaveBeenCalled()
 fireEvent.click(screen.getByText('生成完整整理稿与精华'));await waitFor(()=>expect(update).toHaveBeenCalled())
 expect(fetcher.mock.calls[0][0]).toBe('/api/library/image-items/one/editorial')
})

test('full article and essence are distinct readable outputs with original access',()=>{
 const source=vi.fn(),value={status:'completed',source_pages:45,content:{content:[{type:'paragraph',content:[{text:'完整稿包含例子和做法'}]}]},essence_content:{content:[{type:'paragraph',content:[{text:'精华版'}]}]}}
 const result=render(<ImageEditorial id="one" value={value} mode="article" onUpdate={()=>{}} onSource={source} notify={()=>{}}/>)
 expect(screen.getByText('完整稿包含例子和做法')).toBeTruthy();expect(screen.queryByText('精华版')).toBeNull()
 fireEvent.click(screen.getByText('查看原图与识别稿'));expect(source).toHaveBeenCalled()
 result.rerender(<ImageEditorial id="one" value={value} mode="essence" onUpdate={()=>{}} onSource={source} notify={()=>{}}/>)
 expect(screen.getByText('精华版')).toBeTruthy()
})
