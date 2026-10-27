// @vitest-environment jsdom
import React from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
const mocks=vi.hoisted(()=>({session:null as any}));
vi.mock('@supabase/supabase-js',()=>({createClient:()=>({auth:{getSession:async()=>({data:{session:mocks.session}}),onAuthStateChange:()=>({data:{subscription:{unsubscribe:()=>{}}}}),signOut:vi.fn(),signInWithPassword:vi.fn(),signUp:vi.fn(),signInWithOAuth:vi.fn()}})}));
vi.mock('../src/audio',()=>({prepareAudio:vi.fn(async()=>({hash:'a'.repeat(64),duration:60,parts:[{idx:0,wav:new ArrayBuffer(44)},{idx:1,wav:new ArrayBuffer(44)}]}))}));
vi.mock('../src/Map',()=>({default:()=> <div>可读导图夹具</div>}));
import {App} from '../src/main';
const artifact={summary:'完整的中文摘要',highlights:['保留限制条件'],mindmap:{text:'主题',children:[]}};
beforeEach(()=>{history.replaceState(null,'','/');mocks.session=null});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('shows cloud processing disclosure and requires login before choosing a file',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({supabaseUrl:'https://fixture.supabase.co',supabaseAnonKey:'anon'})));
 render(<App/>);await screen.findByRole('button',{name:'注册账号'});
 expect(screen.queryByLabelText('选择音频文件')).toBeNull();expect(screen.getByText(/这是云端产品，不承诺数据不出机器/)).toBeTruthy();
 expect(screen.getByLabelText('邮箱')).toBeTruthy();
});
it('fails visibly when cloud configuration is missing',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({error:'云端尚未配置完成，请稍后再来。'},{status:503})));
 render(<App/>);expect(await screen.findByRole('alert')).toHaveProperty('textContent','云端尚未配置完成，请稍后再来。');expect((screen.getByRole('button',{name:'登录'}) as HTMLButtonElement).disabled).toBe(true);
});
it('uploads both independent segments before summarizing; shares summaries by default',async()=>{
 mocks.session={access_token:'fixture',user:{id:'fixture',email:'fixture@example.test'}};
 let done=0,generated=false;const paths:string[]=[];
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{const p=String(url);paths.push((init?.method||'GET')+' '+p);
  if(p==='/api/config')return Response.json({supabaseUrl:'https://fixture.supabase.co',supabaseAnonKey:'anon'});
  if(p==='/api/jobs'&&init?.method==='POST')return Response.json({id:'fixture'});
  if(p==='/api/jobs')return Response.json([]);
  if(p.includes('/segments/')){done++;return Response.json({text:'第'+done+'段'})}
  if(p.endsWith('/summarize')){expect(done).toBe(2);generated=true;return Response.json(artifact)}
  if(p.endsWith('/share')){expect(JSON.parse(String(init?.body))).toEqual({include_transcript:false});return Response.json({token:'b'.repeat(64)})}
  return Response.json({id:'fixture',title:'我的音频.mp3',duration_sec:60,status:generated?'completed':'transcribing',segments:Array.from({length:done},(_,i)=>({idx:i,state:'done',text:'第'+i+'段'})),artifact:generated?artifact:null});
 });vi.stubGlobal('fetch',fetcher);render(<App/>);
 const input=await screen.findByLabelText('选择音频文件');
 fireEvent.click(screen.getByRole('checkbox',{name:/我有权处理此音频/}));
 fireEvent.change(input,{target:{files:[new File(['audio'],'我的音频.mp3',{type:'audio/mpeg'})]}});
 await screen.findByText('完整的中文摘要');
 expect(paths.indexOf('POST /api/jobs/fixture/segments/1')).toBeLessThan(paths.indexOf('POST /api/jobs/fixture/summarize'));
 fireEvent.click(screen.getByRole('button',{name:'创建／更新分享链接'}));
 await waitFor(()=>expect(screen.getByDisplayValue(location.origin+'/#share='+'b'.repeat(64))).toBeTruthy());
});
it('requires consent before any audio decoding or create request',async()=>{
 mocks.session={access_token:'fixture',user:{id:'fixture'}};
 const f=vi.fn(async(url:string)=>Response.json(url==='/api/config'?{supabaseUrl:'https://fixture.supabase.co',supabaseAnonKey:'anon'}:[]));vi.stubGlobal('fetch',f);render(<App/>);
 fireEvent.change(await screen.findByLabelText('选择音频文件'),{target:{files:[new File(['audio'],'fixture.mp3')]}});
 expect(await screen.findByRole('alert')).toHaveProperty('textContent','请先确认你有权处理音频，并同意云端处理。');expect(f.mock.calls.some(c=>c[0].includes('/segments/'))).toBe(false);
});
it('a public share never needs a login or loads the owner document list',async()=>{
 history.replaceState(null,'','/#share='+'a'.repeat(64));const f=vi.fn(async()=>Response.json({title:'分享文稿',duration_sec:60,artifact}));vi.stubGlobal('fetch',f);render(<App/>);
 await screen.findByText('完整的中文摘要');expect(screen.queryByLabelText('邮箱')).toBeNull();expect(f.mock.calls).toHaveLength(1);
});
