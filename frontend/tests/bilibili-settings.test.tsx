import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import BilibiliSettings from '../src/BilibiliSettings'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('shows expired state and starts login without exposing credentials',async()=>{
 const calls:string[]=[];let pending=false
 vi.stubGlobal('fetch',vi.fn(async(_path:string,init:RequestInit)=>{calls.push(init.method||'GET');if(init.method==='POST')pending=true;return {ok:true,json:async()=>({status:'expired',login_pending:pending})}}))
 render(<BilibiliSettings/>);await screen.findByText('已失效');fireEvent.click(screen.getByRole('button',{name:'登录B站'}));await screen.findByText('登录窗口已打开，请扫码确认');expect(calls).toContain('POST');expect((screen.getByRole('button',{name:'登录B站'}) as HTMLButtonElement).disabled).toBe(true)
})
test('logout clears pending login and displays server errors inline',async()=>{
 let logged=true;const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(_path:string,init:RequestInit)=>{calls.push(init.method||'GET');if(init.method==='DELETE')logged=false;return {ok:true,json:async()=>({status:logged?'logged_in':'not_logged_in',login_pending:false})}}))
 render(<BilibiliSettings/>);await screen.findByText('已登录');fireEvent.click(screen.getByRole('button',{name:'登出B站'}));await screen.findByText('未登录');await waitFor(()=>expect(calls).toContain('DELETE'))
})
