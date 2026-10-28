import {describe,it,expect,vi} from 'vitest';
import gateway from '../public/_worker.js';

describe('same-origin Pages gateway',()=>{
  it('forwards authenticated audio requests unchanged through the service binding',async()=>{
    const req=new Request('https://shiwen.pages.dev/api/jobs/id/segments/0',{method:'POST',headers:{Authorization:'Bearer fixture','CF-Connecting-IP':'192.0.2.1'},body:new Uint8Array([1,2,3])});
    const api={fetch:vi.fn(async r=>{expect(r).toBe(req);expect(r.headers.get('CF-Connecting-IP')).toBe('192.0.2.1');expect([...new Uint8Array(await r.arrayBuffer())]).toEqual([1,2,3]);return new Response('ok')})};
    expect(await (await gateway.fetch(req,{API:api})).text()).toBe('ok');
  });
  it('serves non-API requests from assets without invoking the backend',async()=>{
    const API={fetch:vi.fn()},ASSETS={fetch:vi.fn(async()=>new Response('page'))};
    expect(await (await gateway.fetch(new Request('https://shiwen.pages.dev/'),{API,ASSETS})).text()).toBe('page');
    expect(API.fetch).not.toHaveBeenCalled();
  });
});
