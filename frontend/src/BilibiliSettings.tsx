import {useEffect,useState} from 'react'
import {Button} from '@/components/ui/button'
type State={status:string;message?:string;login_pending?:boolean;login_error?:string}
async function request(method='GET'){
 const r=await fetch('/api/bilibili/'+(method==='GET'?'status':'login'),{method});const value=await r.json()
 if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'B站登录操作未完成');return value
}
export default function BilibiliSettings(){
 const [state,setState]=useState<State>({status:'checking'}),[busy,setBusy]=useState(false),[error,setError]=useState('')
 async function refresh(){try{setState(await request());setError('')}catch(e){setError((e as Error).message)}}
 useEffect(()=>{void refresh()},[])
 useEffect(()=>{if(!state.login_pending)return;const timer=setInterval(()=>void refresh(),2000);return()=>clearInterval(timer)},[state.login_pending])
 async function act(method:string){setBusy(true);setError('');try{await request(method);await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const names:Record<string,string>={checking:'正在检查',not_logged_in:'未登录',logged_in:'已登录',expired:'已失效',unknown:'暂时无法验证'}
 return <section aria-label="B站登录" style={{borderTop:'1px solid #d5dfef',paddingTop:16}}><strong>B站登录</strong><p role="status" aria-live="polite">{state.login_pending?'登录窗口已打开，请扫码确认':names[state.status]||'未登录'}</p><p className="muted-note">用于优先读取 AI / CC 字幕。登录态仅保存在本机；无字幕时继续本地转写。</p>{state.message&&<p className="muted-note">{state.message}</p>}{(error||state.login_error)&&<p role="alert" className="inline-error">{error||state.login_error}</p>}<div className="form-row"><Button variant="outline" disabled={busy||state.login_pending||state.status==='checking'} onClick={()=>void act('POST')}>{state.status==='logged_in'?'重新登录B站':'登录B站'}</Button><Button variant="outline" disabled={busy} onClick={()=>void act('DELETE')}>{state.login_pending?'取消登录并登出':'登出B站'}</Button><Button variant="ghost" disabled={busy} onClick={()=>void refresh()}>刷新状态</Button></div></section>
}
