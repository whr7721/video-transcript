import React from 'react'
import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {CoreApp} from '../core/main'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('core entry exposes an honest preview and cannot submit a source link',async()=>{
 localStorage.clear()
 const fetcher=vi.fn(async(path:string)=>({ok:true,json:async()=>path==='/api/tasks'?[]:{used_bytes:0,capacity_bytes:5e9,reclaimable_bytes:0,waiting:0}}))
 vi.stubGlobal('fetch',fetcher)
 render(<CoreApp/>)
 expect(await screen.findByText('这里将保存你的本地音视频文稿。')).toBeTruthy()
 fireEvent.click(screen.getAllByRole('button',{name:/新建提取/})[0])
 expect(await screen.findByText('文件处理接口已就绪，图形化导入将在下一阶段开放。')).toBeTruthy()
 expect(screen.queryByRole('textbox',{name:/分享链接/})).toBeNull()
 expect(document.querySelector('[href*="view=discovery"]')).toBeNull()
 expect(fetcher.mock.calls.some(([,options]:any)=>options?.method==='POST')).toBe(false)
})
