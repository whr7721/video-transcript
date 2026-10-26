import {afterEach,expect,test,vi} from 'vitest'
import {installDeviceFetch} from '../core/main'

afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();localStorage.clear()})
test('device header persists and Request headers and bodies remain intact',async()=>{
 const fetcher:any=vi.fn(async()=>new Response('{}'));vi.stubGlobal('fetch',fetcher)
 installDeviceFetch()
 const input=new Request(new URL('/api/test',location.href),{method:'POST',headers:{'Content-Type':'text/plain'},body:'payload'})
 await window.fetch(input)
 const id=fetcher.mock.calls[0][1].headers.get('X-Device-Id')
 expect(id).toBe(localStorage.getItem('shiwen-device-id'));expect(id.length).toBeGreaterThan(8)
 expect(fetcher.mock.calls[0][1].headers.get('Content-Type')).toBe('text/plain')
 expect(fetcher.mock.calls[0][0]).toBe(input)
 await window.fetch('/api/another')
 expect(fetcher.mock.calls[1][1].headers.get('X-Device-Id')).toBe(id)
 await window.fetch('/api/override',{headers:{'X-Device-Id':'callerdevice'}})
 expect(fetcher.mock.calls[2][1].headers.get('X-Device-Id')).toBe('callerdevice')
})
test('external fetch is unchanged and blocked storage still permits API requests',async()=>{
 const fetcher:any=vi.fn(async()=>new Response('{}'));vi.stubGlobal('fetch',fetcher)
 installDeviceFetch()
 await window.fetch('https://example.org/api/test')
 expect(fetcher.mock.calls[0][1]).toBeUndefined()
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw Error('unavailable')})
 await window.fetch('/api/test')
 expect(fetcher.mock.calls[1][1].headers.has('X-Device-Id')).toBe(false)
})
