import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import TopicSearch,{Highlight} from '../src/TopicSearch'

const hit={hit_id:'a'.repeat(32),uid:'note:one',category:'personal',title:'真实交付',text:'🙂AI工具要交付',source_hash:'b'.repeat(64),version:'note-1',basis:'personal',highlights:[[1,3]],note_id:'one',job_id:'job',ranges:[{block_id:'personal',start:0,end:9}]}
const result={items:[hit],offset:0,has_more:false,candidate_count:1,truncated:false,warnings:[],title_matches:[],scope:{personal:1,selection:1,original:1},method:'bigram_bm25'}
const context={...hit,blocks:[{id:'personal',text:hit.text,offset:0,highlights:[[0,9]],clipped:false}]}
let fetchMock:ReturnType<typeof vi.fn>
beforeEach(()=>{localStorage.clear();fetchMock=vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/context')?context:path.includes('/notes/')?{id:'one',personal:'原理解',revision:1}:result}));vi.stubGlobal('fetch',fetchMock)})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function mount(){return render(<TopicSearch topics={[{id:'t',title:'我的专题',notes_count:1}]} topicId="t" onTopic={()=>{}} onResearch={()=>{}} onNotesChanged={async()=>{}}/>)}
async function find(){fireEvent.change(screen.getByLabelText('关键词或问题'),{target:{value:'AI'}});fireEvent.click(screen.getByRole('button',{name:'搜索'}));await screen.findByText('找到 1 个匹配片段')}

test('Unicode highlight uses code points and never interprets source HTML',()=>{
 const {container}=render(<Highlight text={'🙂AI<script>bad</script>'} ranges={[[1,3]]}/>);expect(container.querySelector('mark')?.textContent).toBe('AI');expect(container.querySelector('script')).toBeNull()
})
test('scope, source snapshot, edit and local backup survive an unmount',async()=>{
 const first=mount();await find();expect(fetchMock.mock.calls[0][0]).toContain('/topics/t/search?')
 fireEvent.click(screen.getByText('查看原文位置与上下文'));await screen.findByText('来源位置与相邻文字')
 fireEvent.click(screen.getByText('补充自己的理解'));await screen.findByLabelText('修改自己的理解')
 fireEvent.change(screen.getByLabelText('修改自己的理解'),{target:{value:'新增自己的理解'}})
 expect((screen.getByLabelText('搜索专题') as HTMLSelectElement).disabled).toBe(true)
 expect(localStorage.getItem('shiwen-topic-note-draft:one')).toContain('新增自己的理解')
 first.unmount();mount();await find();fireEvent.click(screen.getByText('查看原文位置与上下文'));await screen.findByText('来源位置与相邻文字');fireEvent.click(screen.getByText('补充自己的理解'))
 await waitFor(()=>expect((screen.getByLabelText('修改自己的理解') as HTMLTextAreaElement).value).toBe('新增自己的理解'))
 fireEvent.click(screen.getByText('保存理解'));await screen.findByText('理解已保存。请重新搜索查看最新结果。')
 expect(localStorage.getItem('shiwen-topic-note-draft:one')).toBeNull()
 expect(fetchMock.mock.calls.some(([,options])=>options?.method==='PUT'&&JSON.parse(String(options.body)).revision===1)).toBe(true)
})
test('an older response cannot replace a changed query',async()=>{
 let resolve!:(value:unknown)=>void;fetchMock.mockImplementationOnce(()=>new Promise(r=>{resolve=r}))
 mount();fireEvent.change(screen.getByLabelText('关键词或问题'),{target:{value:'旧查询'}});fireEvent.click(screen.getByRole('button',{name:'搜索'}))
 fireEvent.change(screen.getByLabelText('关键词或问题'),{target:{value:'新查询'}})
 await act(async()=>resolve({ok:true,json:async()=>result}));expect(screen.queryByText('找到 1 个匹配片段')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'搜索'}));await screen.findByText('找到 1 个匹配片段')
})
test('IME composition does not submit; empty results give a useful next action',async()=>{
 fetchMock.mockResolvedValue({ok:true,json:async()=>({...result,items:[],candidate_count:0})})
 mount();const input=screen.getByLabelText('关键词或问题');fireEvent.compositionStart(input);fireEvent.change(input,{target:{value:'客户'}});fireEvent.submit(input.closest('form')!);expect(fetchMock).not.toHaveBeenCalled()
 fireEvent.compositionEnd(input);fireEvent.click(screen.getByRole('button',{name:'搜索'}));await screen.findByText(/当前范围未找到匹配/)
})
test('stale locations display server error rather than a guessed passage',async()=>{
 mount();await find();fetchMock.mockResolvedValueOnce({ok:false,json:async()=>({detail:'内容已有变化，请重新搜索；未跳转到其他位置。'})})
 fireEvent.click(screen.getByText('查看原文位置与上下文'));await screen.findByRole('alert');expect(screen.queryByText('来源位置与相邻文字')).toBeNull()
})

test('title-only match opens the source beginning without claiming body evidence',async()=>{
 fetchMock.mockResolvedValueOnce({ok:true,json:async()=>({...result,items:[],candidate_count:0,title_matches:[hit]})})
 mount();fireEvent.change(screen.getByLabelText('关键词或问题'),{target:{value:'真实交付'}});fireEvent.click(screen.getByRole('button',{name:'搜索'}))
 await screen.findByText('另有标题匹配（不代表正文命中）')
 screen.getByText('另有标题匹配（不代表正文命中）').closest('details')!.open=true
 fireEvent.click(screen.getByText('查看来源开头（仅标题匹配）'));await screen.findByText('以下为来源开头，未标为查询命中的正文。')
 expect(screen.getByText(hit.text).querySelector('mark')).toBeNull()
})
