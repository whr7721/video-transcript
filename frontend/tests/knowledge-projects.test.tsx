import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import Projects from '../src/KnowledgeProjects'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('creates a free workspace and manual step without model requests',async()=>{
 let p:any=null;const f=vi.fn(async(url:any,init?:RequestInit)=>{if(init?.method==='POST'){p={id:'p',title:'学习摄影',goal:'掌握曝光',constraints:'',steps:[],review:'',revision:1,versions:[]};return Response.json(p)}return Response.json(p?[p]:[])});vi.stubGlobal('fetch',f);render(<Projects/>);
 fireEvent.change(screen.getByLabelText('名称'),{target:{value:'学习摄影'}});fireEvent.change(screen.getByLabelText('具体目标'),{target:{value:'掌握曝光'}});fireEvent.click(screen.getByText('建立工作区'));
 await screen.findByRole('heading',{name:'学习摄影'});fireEvent.click(screen.getByText('手动添加步骤'));expect(screen.getByText('有未保存修改，请先保存再切换工作区或研究。当前页面离开前请保存。')).toBeTruthy();expect(f.mock.calls.some(c=>String(c[0]).includes('/research'))).toBe(false)
})
it('saves progress using the version token',async()=>{
 const p={id:'p',title:'摄影任务',goal:'掌握曝光',constraints:'45分钟',steps:[{id:'s',title:'练习光圈',detail:'拍一组照片',note:'',state:'todo'}],review:'',revision:4,versions:[]};let saved:any;
 vi.stubGlobal('fetch',vi.fn(async(_url:any,init?:RequestInit)=>{if(init?.method==='PUT'){saved=JSON.parse(String(init.body));return Response.json({...saved,revision:5})}return Response.json([p])}));render(<Projects/>);fireEvent.click(await screen.findByRole('button',{name:/摄影任务/}));fireEvent.change(screen.getByLabelText('步骤1状态'),{target:{value:'done'}});fireEvent.change(screen.getByLabelText('我的进展／结果'),{target:{value:'拍摄完成'}});fireEvent.click(screen.getByText('保存进度与复盘'));
 await waitFor(()=>expect(saved?.revision).toBe(4));expect(saved.steps[0].state).toBe('done');expect(saved.steps[0].note).toBe('拍摄完成')
})
