import React from 'react'
import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import FileCapture from '../core/FileCapture'

class XHR{
 static instances:XHR[]=[]
 upload:{onprogress:((e:{loaded:number})=>void)|null}={onprogress:null}
 onload:(()=>void)|null=null;onerror:(()=>void)|null=null;onabort:(()=>void)|null=null
 status=200;responseText='';sent:unknown
 constructor(){XHR.instances.push(this)}
 open=vi.fn();setRequestHeader=vi.fn()
 send=(file:unknown)=>{this.sent=file}
 abort=vi.fn(()=>this.onabort?.())
 finish(value:unknown,status=200){this.status=status;this.responseText=JSON.stringify(value);this.onload?.()}
}
let requests:{path:string;method?:string}[],serial=0,ready=true
beforeEach(()=>{XHR.instances=[];requests=[];serial=0;ready=true
 vi.stubGlobal('XMLHttpRequest',XHR)
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{requests.push({path,method:init?.method});return {ok:true,json:async()=>path==='/api/health'?{models_ready:ready}:init?.method==='POST'?{upload_id:'upload-'+(++serial)}:{status:'cancelled'}}}))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function select(){const input=screen.getByLabelText('选择本地音视频文件');const file=new File(['voice'],'讲话.wav',{type:'audio/wav'});fireEvent.change(input,{target:{files:[file]}});await waitFor(()=>expect((screen.getByRole('button',{name:'导入并转写'}) as HTMLButtonElement).disabled).toBe(false));return file}

test('uploads File directly and 100% waits for server admission',async()=>{
 const created=vi.fn(async()=>{});render(<FileCapture onCreated={created} notify={()=>{}}/>);const file=await select()
 fireEvent.click(screen.getByRole('button',{name:'导入并转写'}));await waitFor(()=>expect(XHR.instances.length).toBe(1))
 const xhr=XHR.instances[0];expect(xhr.sent).toBe(file);expect(xhr.open).toHaveBeenCalledWith('PUT','/api/files/uploads/upload-1')
 act(()=>xhr.upload.onprogress?.({loaded:file.size}));expect(screen.getByText(/正在校验格式与时长/)).toBeTruthy();expect(created).not.toHaveBeenCalled()
 await act(async()=>xhr.finish({id:'task-1'}));expect(created).toHaveBeenCalledWith('task-1')
})

test('cancel aborts XHR and deletes temporary session before allowing retry',async()=>{
 const created=vi.fn(async()=>{});render(<FileCapture onCreated={created} notify={()=>{}}/>);await select()
 fireEvent.click(screen.getByRole('button',{name:'导入并转写'}));await waitFor(()=>expect(XHR.instances.length).toBe(1))
 fireEvent.click(screen.getByRole('button',{name:'取消上传'}));await screen.findByRole('button',{name:'导入并转写'})
 expect(XHR.instances[0].abort).toHaveBeenCalled();expect(created).not.toHaveBeenCalled()
 expect(requests.some(r=>r.path==='/api/files/uploads/upload-1'&&r.method==='DELETE')).toBe(true)
})

test('unmount cancels an in-flight upload and resets parent busy state',async()=>{
 const busy=vi.fn();const view=render(<FileCapture onCreated={async()=>{}} notify={()=>{}} onBusyChange={busy}/>);await select()
 fireEvent.click(screen.getByRole('button',{name:'导入并转写'}));await waitFor(()=>expect(XHR.instances.length).toBe(1));view.unmount()
 expect(XHR.instances[0].abort).toHaveBeenCalled();expect(busy).toHaveBeenLastCalledWith(false)
})

test('invalid file and absent model block upload with actionable messages',async()=>{
 ready=false;render(<FileCapture onCreated={async()=>{}} notify={()=>{}}/>);await screen.findByText(/本地模型尚未就绪/)
 fireEvent.change(screen.getByLabelText('选择本地音视频文件'),{target:{files:[new File(['bad'],'playlist.m3u8')]}})
 expect(await screen.findByRole('alert')).toBeTruthy();expect((screen.getByRole('button',{name:'导入并转写'}) as HTMLButtonElement).disabled).toBe(true)
 expect(requests.some(r=>r.method==='POST')).toBe(false)
})

test('server quota rejection retains selected file and offers a fresh-session retry',async()=>{
 render(<FileCapture onCreated={async()=>{}} notify={()=>{}}/>);await select();fireEvent.click(screen.getByRole('button',{name:'导入并转写'}))
 await waitFor(()=>expect(XHR.instances.length).toBe(1));await act(async()=>XHR.instances[0].finish({detail:'缓冲不足，已保护待确认素材'},507))
 expect(await screen.findByRole('alert')).toHaveProperty('textContent','缓冲不足，已保护待确认素材')
 fireEvent.click(screen.getByRole('button',{name:'重新上传'}));await waitFor(()=>expect(XHR.instances.length).toBe(2))
 expect(XHR.instances[1].open).toHaveBeenCalledWith('PUT','/api/files/uploads/upload-2')
})

test('cancel while creating cleans the eventual session and never sends bytes',async()=>{
 let resolveCreate:(value:unknown)=>void=()=>{}
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{requests.push({path,method:init?.method});if(init?.method==='POST')return await new Promise(resolve=>{resolveCreate=resolve});return {ok:true,json:async()=>path==='/api/health'?{models_ready:true}:{status:'cancelled'}}}))
 render(<FileCapture onCreated={async()=>{}} notify={()=>{}}/>);await select();fireEvent.click(screen.getByRole('button',{name:'导入并转写'}))
 await screen.findByText('正在准备上传…');fireEvent.click(screen.getByRole('button',{name:'取消上传'}))
 await act(async()=>resolveCreate({ok:true,json:async()=>({upload_id:'late'})}));await screen.findByRole('button',{name:'导入并转写'})
 expect(XHR.instances.length).toBe(0);expect(requests.some(r=>r.path.endsWith('/late')&&r.method==='DELETE')).toBe(true)
})

test('warns on page navigation during transfer and stops warning after acceptance',async()=>{
 render(<FileCapture onCreated={async()=>{}} notify={()=>{}}/>);await select();fireEvent.click(screen.getByRole('button',{name:'导入并转写'}))
 await waitFor(()=>expect(XHR.instances.length).toBe(1))
 const pending=new Event('beforeunload',{cancelable:true});window.dispatchEvent(pending);expect(pending.defaultPrevented).toBe(true)
 await act(async()=>XHR.instances[0].finish({id:'task-1'}))
 const done=new Event('beforeunload',{cancelable:true});window.dispatchEvent(done);expect(done.defaultPrevented).toBe(false)
})

test('cancel/admission race opens the accepted task and never claims it was deleted',async()=>{
 const created=vi.fn(async()=>{}),notify=vi.fn()
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(init?.method==='DELETE')return {ok:false,json:async()=>({detail:'already accepted'})}
  return {ok:true,json:async()=>path==='/api/health'?{models_ready:true}:init?.method==='POST'?{upload_id:'race'}:{status:'accepted',task_id:'accepted-task'}}
 }))
 render(<FileCapture onCreated={created} notify={notify}/>);await select();fireEvent.click(screen.getByRole('button',{name:'导入并转写'}))
 await waitFor(()=>expect(XHR.instances.length).toBe(1));fireEvent.click(screen.getByRole('button',{name:'取消上传'}))
 await waitFor(()=>expect(created).toHaveBeenCalledWith('accepted-task'))
 expect(notify).toHaveBeenCalledWith(expect.stringContaining('文件已入队'))
})
