import React from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Discovery,{filterCandidates,type Candidate} from '../src/Discovery'

const row:Candidate={video_id:'1234567890123456789',canonical_url:'https://www.douyin.com/video/1234567890123456789',caption:'真实客户交付案例',author_name:'作者',published_at:'2026-10-21',duration_sec:85,media_type:'video',matched_queries:['AI 接单'],digg_count:3,transcript_id:'old-task'}
const unknown={...row,video_id:'1234567890123456790',caption:'时长未知案例',duration_sec:null}
const long={...row,video_id:'1234567890123456791',caption:'长视频案例',duration_sec:720}
const job={id:'1234567890abcdef',request:{topic:'AI工具的实际变现',queries:['AI 接单'],max_candidates_total:30},state:'finished',adapter_status:'ok',items:[row,unknown,long],selected_ids:[],selection_revision:1,can_resume:true,warnings:[],message:'搜索已结束',stopped_reason:'target_reached',per_query_progress:[]}
function mock(conflict=false){
 const calls:{path:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  calls.push({path,init})
  const saving=init?.method==='PUT'
  const body=saving?{...job,selected_ids:[row.video_id],selection_revision:2}:path==='/api/discovery'&&!init?.method?[{id:job.id,topic:job.request.topic,state:'finished',count:3,created_at:1}]:job
  return new Response(JSON.stringify(saving&&conflict?{detail:'勾选已在其他页面更新'}:body),{status:saving&&conflict?409:200})
 }))
 return calls
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();history.replaceState(null,'','/')})
it('filters duration explicitly and never equates unknown to zero',()=>{
 expect(filterCandidates([row,unknown,long],'','',600,true)).toEqual([row,unknown])
 expect(filterCandidates([row,unknown,long],'','',600,false)).toEqual([row])
 expect(filterCandidates([row,unknown,long],'','',1200,true)).toHaveLength(3)
 expect(filterCandidates([row],'客户','交付',600,true)).toHaveLength(0)
})
it('keeps the ten minute boundary inclusive and excludes non-video metadata',()=>{
 const rows=[599,600,601].map((seconds,i)=>({...row,video_id:String(i),duration_sec:seconds}))
 expect(filterCandidates([...rows,{...row,media_type:'image'},{...row,media_type:'unknown'}],'','',600,true).map(r=>r.duration_sec)).toEqual([599,600])
})
it('loads candidate metadata and existing transcript without auto scheduling',async()=>{
 const calls=mock();render(<Discovery/>);await screen.findByText('真实客户交付案例')
 expect(screen.queryByText('长视频案例')).toBeNull()
 expect(screen.getByText('时长待核实')).toBeTruthy()
 expect(screen.getAllByText('已有文稿 · 打开')[0].getAttribute('href')).toBe('/studio/?task=old-task')
 expect(calls.every(c=>!c.init?.method)).toBe(true)
})
it('preserves hidden selections and explicitly saves a shortlist only',async()=>{
 const calls=mock();render(<Discovery/>);await screen.findByText('真实客户交付案例')
 fireEvent.click(screen.getByLabelText('选择 真实客户交付案例'))
 fireEvent.change(screen.getByLabelText('排除词'),{target:{value:'客户'}})
 expect(screen.getByText(/含 1 条当前筛选隐藏/)).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'保存候选清单'}))
 await waitFor(()=>expect(calls.some(c=>c.init?.method==='PUT')).toBe(true))
 const call=calls.find(c=>c.init?.method==='PUT')!
 expect(call.path).toBe(`/api/discovery/${job.id}/selection`)
 expect(JSON.parse(call.init!.body as string)).toEqual({revision:1,video_ids:[row.video_id]})
 expect(calls.some(c=>c.path.includes('/tasks')||c.path.includes('/generate'))).toBe(false)
})
it('keeps the users selection after a save conflict',async()=>{
 mock(true);render(<Discovery/>);await screen.findByText('真实客户交付案例')
 fireEvent.click(screen.getByLabelText('选择 真实客户交付案例'))
 fireEvent.click(screen.getByRole('button',{name:'保存候选清单'}))
 await screen.findByText('勾选已在其他页面更新')
 expect(screen.getByLabelText('选择 真实客户交付案例')).toHaveProperty('checked',true)
 expect(screen.getByText(/已勾选 1 条 · 未保存/)).toBeTruthy()
})
